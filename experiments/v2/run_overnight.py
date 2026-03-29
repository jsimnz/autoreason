#!/usr/bin/env python3
"""
Overnight batch runner: Monte Carlo (5 runs task 1) + Tasks 2-5 autoreason + baselines + judges.
Designed to run unattended. Handles rate limits, retries, and logs everything.
"""

import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

def load_dotenv(path):
    if not Path(path).exists():
        return
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())

load_dotenv(os.path.expanduser("~/.hermes/.env"))

import litellm
litellm.suppress_debug_info = True

# ── Config ──────────────────────────────────────────────────────────────
MODEL = "anthropic/claude-sonnet-4-20250514"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
NUM_JUDGES = 3
CONVERGENCE = 2
MAX_PASSES_AUTOREASON = 30
MAX_PASSES_BASELINE = 15
JUDGE_PANEL_SIZE = 7

ROOT = Path(__file__).parent
TASKS_DIR = ROOT.parent.parent / "tasks"

# ── Prompts ─────────────────────────────────────────────────────────────
AUTHOR_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Avoid generic advice. "
    "Tailor everything to the constraints stated in the task."
)

CRITIC_SYSTEM = (
    "You are a critical reviewer. Your only job is to find real problems. "
    "Be specific and concrete. Do not suggest fixes."
)

AUTHOR_B_SYSTEM = (
    "You are a senior consultant revising a proposal based on specific criticisms. "
    "Address each valid criticism directly. Do not make changes that aren't "
    "motivated by an identified problem."
)

SYNTHESIZER_SYSTEM = (
    "You are a senior consultant. You are given two versions as equal inputs. "
    "Take the strongest elements from each and produce a coherent synthesis. "
    "This is not a compromise — pick the best answer per dimension."
)

JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no authorship stake in any "
    "version. Evaluate which version best accomplishes the original task."
)

GENERATE_A = "{task_prompt}\n\nProduce a complete, detailed proposal."

CRITIC_PROMPT = """Here is a proposal:

---
{version_a}
---

Find real problems with this proposal. Focus on:
- Things that won't work as described
- Complexity that doesn't pay for itself
- Assumptions that are wrong
- Missing pieces that block the design

Do NOT propose fixes. Just the problems."""

AUTHOR_B_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Here is a proposal and the problems identified with it.

CURRENT PROPOSAL:
---
{version_a}
---

PROBLEMS FOUND:
---
{critic}
---

Revise the proposal to address these problems.
For each change, state which problem it fixes.
Do not make changes that aren't motivated by an identified problem."""

SYNTHESIZER_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Here are two versions of a proposal. Treat them as equal inputs.

VERSION X:
---
{version_x}
---

VERSION Y:
---
{version_y}
---

Produce a synthesis that keeps the strongest elements from both.
Pick the best version of each section and make them cohere."""

JUDGE_RANK_3_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Three proposals have been produced independently. Evaluate how well each accomplishes the stated task.

{judge_proposals}

For each proposal, state what it gets right and what it gets wrong.
Then rank all three from best to worst:

RANKING: [best], [second], [worst]

Where each slot is 1, 2, or 3."""

JUDGE_RANK_5_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

INITIAL OUTPUT (the starting point all versions were derived from):
---
{initial_output}
---

Five teams independently worked to improve the initial output. Here are their final versions:

{proposals}

Evaluate all five against the original task and initial output. Consider:
- How well does each accomplish what the task asks for?
- How much has each improved over the initial output?
- Are claims and numbers grounded and defensible?
- Is detail appropriate or is there unnecessary bloat?

Rank all five from best to worst:

RANKING: [best], [second], [third], [fourth], [worst]

Where each slot is the version letter (A, B, C, D, or E)."""

BASELINE_PROMPTS = {
    "improve_this": """Here is a proposal:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

Improve this proposal. Make it stronger, more compelling, and more thorough. Produce the complete improved proposal.""",

    "critique_and_revise": """Here is a proposal you produced:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

Review this proposal critically. Find real problems. Then revise to fix every problem you found. Produce the complete revised proposal.""",

    "conservative": """Here is a proposal:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

Review this proposal. Make changes only if something is genuinely wrong, unrealistic, or missing. If a section is already good, leave it as is. Do not add complexity for its own sake.

If the proposal is already strong and no changes are needed, return it unchanged.

Produce the complete proposal with any necessary changes.""",

    "harsh_critic": """Here is a proposal:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

You are a harsh, uncompromising critic. Find every flaw. After identifying every problem, rewrite the proposal from scratch to address all of them. Produce the complete revised proposal.""",
}


# ── LLM wrapper ─────────────────────────────────────────────────────────
async def call_llm(system, user, model, temperature, max_tokens, max_retries=8):
    for attempt in range(max_retries):
        try:
            response = await litellm.acompletion(
                model=model, messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ], temperature=temperature, max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "429" in err or "overloaded" in err or "529" in err:
                wait = min((2 ** attempt) * 5, 120)
                print(f"      [Rate limited, retry {attempt+1}/{max_retries} in {wait}s]")
                await asyncio.sleep(wait)
            else:
                if attempt < max_retries - 1:
                    wait = 10
                    print(f"      [Error: {str(e)[:80]}, retry in {wait}s]")
                    await asyncio.sleep(wait)
                else:
                    raise
    raise RuntimeError(f"Failed after {max_retries} retries")


# ── Helpers ──────────────────────────────────────────────────────────────
def randomize_for_judge(va, vb, vab):
    versions = [("A", va), ("B", vb), ("AB", vab)]
    random.shuffle(versions)
    order = {}
    parts = []
    for i, (label, content) in enumerate(versions, 1):
        order[str(i)] = label
        parts.append(f"PROPOSAL {i}:\n---\n{content}\n---")
    return "\n\n".join(parts), order


def parse_ranking(text, valid_chars="123"):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            items = [c for c in raw if c in valid_chars]
            if len(items) >= 2:
                return items
    return None


def aggregate_rankings(rankings, labels, tiebreak_winner=None):
    scores = {l: 0 for l in labels}
    n = len(labels)
    valid = [r for r in rankings if r is not None]
    for ranking in valid:
        for pos, label in enumerate(ranking):
            if label in scores and pos < n:
                scores[label] += (n - pos)
    if tiebreak_winner:
        priority = {l: (0 if l == tiebreak_winner else i+1) for i, l in enumerate(labels)}
    else:
        priority = {l: i for i, l in enumerate(labels)}
    ranked = sorted(scores.keys(), key=lambda k: (-scores[k], priority[k]))
    return ranked[0], scores, valid


# ── Autoreason pass ──────────────────────────────────────────────────────
async def run_autoreason_pass(task_prompt, current_a, pass_num, pass_dir):
    pass_dir.mkdir(parents=True, exist_ok=True)
    result_file = pass_dir / "result.json"
    if result_file.exists():
        ex = json.loads(result_file.read_text())
        if ex.get("winner"):
            w = ex["winner"]
            if w == "A":
                return w, current_a, ex
            wf = pass_dir / f"version_{w.lower()}.md"
            return w, wf.read_text() if wf.exists() else current_a, ex

    t0 = time.time()
    (pass_dir / "version_a.md").write_text(current_a)

    critic = await call_llm(CRITIC_SYSTEM, CRITIC_PROMPT.format(version_a=current_a), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "critic.md").write_text(critic)

    vb = await call_llm(AUTHOR_B_SYSTEM, AUTHOR_B_PROMPT.format(task_prompt=task_prompt, version_a=current_a, critic=critic), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_b.md").write_text(vb)

    if random.random() < 0.5:
        vx, vy = current_a, vb
    else:
        vx, vy = vb, current_a
    vab = await call_llm(SYNTHESIZER_SYSTEM, SYNTHESIZER_PROMPT.format(task_prompt=task_prompt, version_x=vx, version_y=vy), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_ab.md").write_text(vab)

    jtasks, jorders = [], []
    for _ in range(NUM_JUDGES):
        proposals, order = randomize_for_judge(current_a, vb, vab)
        jorders.append(order)
        jtasks.append(call_llm(JUDGE_SYSTEM, JUDGE_RANK_3_PROMPT.format(task_prompt=task_prompt, judge_proposals=proposals), MODEL, JUDGE_TEMP, MAX_TOKENS))

    jresps = await asyncio.gather(*jtasks, return_exceptions=True)
    rankings, jdetails = [], []
    for j, (resp, order) in enumerate(zip(jresps, jorders)):
        if isinstance(resp, Exception):
            rankings.append(None)
            jdetails.append({"error": str(resp)})
        else:
            raw_ranking = parse_ranking(resp, "123")
            mapped = [order.get(r, r) for r in raw_ranking] if raw_ranking else None
            rankings.append(mapped)
            jdetails.append({"ranking": mapped, "order": order})

    winner, scores, valid = aggregate_rankings(rankings, ["A", "B", "AB"], tiebreak_winner="A")
    elapsed = time.time() - t0

    vmap = {"A": current_a, "B": vb, "AB": vab}
    result = {"pass": pass_num, "winner": winner, "scores": scores, "valid_judges": len(valid), "elapsed": round(elapsed, 1), "judge_details": jdetails}
    (pass_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return winner, vmap[winner], result


async def run_autoreason(task_prompt, out_dir, label=""):
    out_dir.mkdir(parents=True, exist_ok=True)
    init_file = out_dir / "initial_a.md"
    if init_file.exists():
        current_a = init_file.read_text()
    else:
        current_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
        init_file.write_text(current_a)
    print(f"  [{label}] Initial A: {len(current_a.split())} words")

    streak, history = 0, []
    for p in range(1, MAX_PASSES_AUTOREASON + 1):
        winner, winner_text, result = await run_autoreason_pass(task_prompt, current_a, p, out_dir / f"pass_{p:02d}")
        history.append({"pass": p, "winner": winner, "scores": result.get("scores", {}), "words": len(winner_text.split())})
        print(f"  [{label}] Pass {p}: {winner} (A={result['scores'].get('A',0)}, B={result['scores'].get('B',0)}, AB={result['scores'].get('AB',0)}) [{result.get('elapsed',0):.0f}s]")

        if winner == "A":
            streak += 1
        else:
            streak = 0
            current_a = winner_text
            (out_dir / f"incumbent_after_{p:02d}.md").write_text(current_a)

        if streak >= CONVERGENCE:
            print(f"  [{label}] ✔ Converged at pass {p}")
            break

    (out_dir / "final_output.md").write_text(current_a)
    (out_dir / "history.json").write_text(json.dumps(history, indent=2))
    print(f"  [{label}] Final: {len(current_a.split())} words, trajectory: {' → '.join(h['winner'] for h in history)}")
    return current_a, history


# ── Baseline runner ──────────────────────────────────────────────────────
async def run_baseline(name, task_prompt, initial_a, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    final_file = out_dir / "final_output.md"
    if final_file.exists():
        print(f"    {name}: already complete")
        return final_file.read_text()

    current = initial_a
    (out_dir / "pass_00_initial.md").write_text(current)
    prompt_template = BASELINE_PROMPTS[name]

    for p in range(1, MAX_PASSES_BASELINE + 1):
        current = await call_llm(AUTHOR_SYSTEM, prompt_template.format(current_version=current, task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
        (out_dir / f"pass_{p:02d}.md").write_text(current)

    (out_dir / "final_output.md").write_text(current)
    summary = {"baseline": name, "final_words": len(current.split())}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"    {name}: {len(current.split())} words")
    return current


# ── 5-way judge panel ────────────────────────────────────────────────────
async def run_5way_judge(task_prompt, initial_output, outputs, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    result_file = out_dir / "5way_results.json"
    if result_file.exists():
        print(f"    5-way judge: already complete")
        return json.loads(result_file.read_text())

    method_names = list(outputs.keys())
    labels = ["A", "B", "C", "D", "E"]

    jtasks, jorders = [], []
    for _ in range(JUDGE_PANEL_SIZE):
        shuffled = method_names.copy()
        random.shuffle(shuffled)
        order = {labels[i]: shuffled[i] for i in range(5)}
        jorders.append(order)
        parts = [f"VERSION {labels[i]}:\n---\n{outputs[order[labels[i]]]}\n---" for i in range(5)]
        proposals = "\n\n".join(parts)
        jtasks.append(call_llm(JUDGE_SYSTEM, JUDGE_RANK_5_PROMPT.format(task_prompt=task_prompt, initial_output=initial_output, proposals=proposals), MODEL, JUDGE_TEMP, MAX_TOKENS))

    jresps = await asyncio.gather(*jtasks, return_exceptions=True)

    borda = {n: 0 for n in method_names}
    first_place = {n: 0 for n in method_names}
    points = [5, 4, 3, 2, 1]

    for j, (resp, order) in enumerate(zip(jresps, jorders)):
        if isinstance(resp, Exception):
            continue
        ranking_letters = parse_ranking(resp, "ABCDE")
        if ranking_letters:
            ranking_methods = [order.get(l, l) for l in ranking_letters]
            for pos, method in enumerate(ranking_methods):
                if method in borda and pos < len(points):
                    borda[method] += points[pos]
            if ranking_methods[0] in first_place:
                first_place[ranking_methods[0]] += 1

    result = {"borda": borda, "first_place": first_place, "num_judges": JUDGE_PANEL_SIZE}
    result_file.write_text(json.dumps(result, indent=2))

    sorted_methods = sorted(borda.items(), key=lambda x: -x[1])
    for name, score in sorted_methods:
        print(f"    {name:25s} Borda={score:3d} 1st={first_place[name]}")
    return result


# ── Main ─────────────────────────────────────────────────────────────────
async def main():
    start = time.time()
    print(f"{'='*60}")
    print(f"OVERNIGHT BATCH RUN")
    print(f"Model: {MODEL}")
    print(f"Convergence: {CONVERGENCE}, max passes: {MAX_PASSES_AUTOREASON}")
    print(f"Baselines: {MAX_PASSES_BASELINE} passes each")
    print(f"Judge panels: {JUDGE_PANEL_SIZE} judges")
    print(f"{'='*60}\n")

    # ── Phase 1: Monte Carlo (5 runs of task 1) ──────────────────────
    print(f"{'━'*60}")
    print(f"PHASE 1: Monte Carlo — 5 runs of Task 01")
    print(f"{'━'*60}\n")

    task1_prompt = (TASKS_DIR / "task_01.md").read_text().strip()
    mc_dir = ROOT / "results_monte_carlo" / "task_01"

    mc_histories = []
    for run_idx in range(1, 6):
        print(f"\n  Monte Carlo run {run_idx}/5:")
        run_dir = mc_dir / f"run_{run_idx:02d}"
        _, history = await run_autoreason(task1_prompt, run_dir, label=f"MC-{run_idx}")
        mc_histories.append(history)
        # Brief pause between runs to avoid rate limit stacking
        await asyncio.sleep(5)

    # Save MC summary
    mc_summary = {
        "num_runs": 5,
        "convergence_passes": [len(h) for h in mc_histories],
        "final_words": [h[-1]["words"] for h in mc_histories],
        "trajectories": [" → ".join(x["winner"] for x in h) for h in mc_histories],
    }
    (mc_dir / "monte_carlo_summary.json").write_text(json.dumps(mc_summary, indent=2))
    print(f"\n  MC Summary:")
    for i, h in enumerate(mc_histories):
        traj = " → ".join(x["winner"] for x in h)
        print(f"    Run {i+1}: {len(h)} passes, {h[-1]['words']} words, {traj}")

    # ── Phase 2: Tasks 2-5 autoreason + baselines + judges ───────────
    for task_num in range(2, 6):
        print(f"\n{'━'*60}")
        print(f"PHASE 2: Task {task_num:02d}")
        print(f"{'━'*60}\n")

        task_file = TASKS_DIR / f"task_{task_num:02d}.md"
        task_prompt = task_file.read_text().strip()
        task_dir = ROOT / "results_multi_task" / f"task_{task_num:02d}"

        # Run autoreason
        print(f"  Running autoreason...")
        ar_output, ar_history = await run_autoreason(task_prompt, task_dir / "autoreason", label=f"T{task_num}-AR")

        # Get initial A for baselines
        initial_a = (task_dir / "autoreason" / "initial_a.md").read_text()

        # Run baselines
        print(f"\n  Running baselines...")
        baseline_outputs = {}
        for bname in ["conservative", "improve_this", "harsh_critic", "critique_and_revise"]:
            print(f"    Running {bname}...")
            output = await run_baseline(bname, task_prompt, initial_a, task_dir / "baselines" / bname)
            baseline_outputs[bname] = output
            await asyncio.sleep(2)

        # 5-way judge panel
        print(f"\n  Running 7-judge panel...")
        all_outputs = {"autoreason": ar_output}
        all_outputs.update(baseline_outputs)
        judge_result = await run_5way_judge(task_prompt, initial_a, all_outputs, task_dir / "comparison")

        await asyncio.sleep(5)

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"OVERNIGHT RUN COMPLETE")
    print(f"Total time: {elapsed/3600:.1f} hours")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
