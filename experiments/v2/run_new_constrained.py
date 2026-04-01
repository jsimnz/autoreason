#!/usr/bin/env python3
"""
Run autoreason + baselines on new constrained tasks (task_02_constrained, task_03_constrained)
with Sonnet 4.6 to replicate the scope finding from the original constrained experiment.

Phase 1: Run autoreason to convergence on each task
Phase 2: Run 4 baselines (15 passes each) from the same initial output
Phase 3: 7-judge blind panel comparing all 5 methods

Usage:
    python run_new_constrained.py --task 2       # run task 2 constrained
    python run_new_constrained.py --task 3       # run task 3 constrained
    python run_new_constrained.py --task 2 --phase autoreason   # only autoreason
    python run_new_constrained.py --task 2 --phase baselines    # only baselines
    python run_new_constrained.py --task 2 --phase eval         # only 7-judge eval
"""

import argparse
import asyncio
import json
import os
import random
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

MODEL = "anthropic/claude-sonnet-4-6"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
NUM_JUDGES_INLOOP = 3
NUM_JUDGES_EVAL = 7
MAX_PASSES = 25
CONVERGENCE = 2

# System prompts
AUTHOR_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Avoid generic advice. "
    "Follow all constraints exactly as stated in the task."
)

CRITIC_SYSTEM = (
    "You are a critical reviewer. Your only job is to find real problems "
    "with the document you are given. Be specific and concrete. Do not "
    "suggest fixes or improvements — only identify weaknesses. "
    "Pay special attention to whether the output follows the stated constraints."
)

AUTHOR_B_SYSTEM = (
    "You are a senior consultant revising a document based on specific criticisms. "
    "Address each valid criticism directly. Do not make changes that aren't "
    "motivated by an identified problem. Follow all constraints exactly."
)

SYNTHESIZER_SYSTEM = (
    "You are a senior consultant. You are given two versions of a document as equal inputs. "
    "Take the strongest elements from each and produce a coherent synthesis. "
    "This is not a compromise — pick the best answer per dimension. "
    "Follow all constraints exactly."
)

COT_JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no authorship stake. "
    "Think carefully before deciding."
)

# Prompt templates
GENERATE_A = "{task_prompt}\n\nProduce your response now."

CRITIC_PROMPT = """Here is a document produced for the following task:

ORIGINAL TASK AND CONSTRAINTS:
---
{task_prompt}
---

DOCUMENT TO REVIEW:
---
{version_a}
---

Find real problems. Focus on:
- Things that don't work as described
- Constraint violations
- Assumptions that are wrong
- Missing required elements
- Unnecessary filler or hedging

Do NOT propose fixes. Just the problems."""

AUTHOR_B_PROMPT = """ORIGINAL TASK AND CONSTRAINTS:
---
{task_prompt}
---

Here is a document and the problems identified with it.

CURRENT DOCUMENT:
---
{version_a}
---

PROBLEMS FOUND:
---
{critic}
---

Revise the document to address these problems.
For each change, state which problem it fixes.
Do not make changes that aren't motivated by an identified problem."""

SYNTHESIZER_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Here are two versions of a document. Treat them as equal inputs.

VERSION X:
---
{version_x}
---

VERSION Y:
---
{version_y}
---

Produce a synthesis that keeps the strongest elements from both.
Pick the best answer per dimension and make them cohere."""

JUDGE_3WAY_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Three documents have been produced independently. Evaluate how well each accomplishes the task, including adherence to all stated constraints.

{judge_proposals}

For each version, think step by step:
1. Does it follow all stated constraints (word count, structure, etc.)?
2. Does it cover all required elements?
3. Is the content specific and well-justified?
4. Is there unnecessary filler?

After reasoning, rank all three from best to worst:

RANKING: [best], [second], [worst]

Where each slot is 1, 2, or 3."""

JUDGE_5WAY_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

INITIAL OUTPUT (starting point for all methods):
---
{initial_output}
---

Five teams independently improved the initial output using different methods:

{proposals}

For each version, think step by step:
1. Does it follow all stated constraints?
2. Does it cover all required elements with appropriate specificity?
3. Is every claim justified or sourced where required?
4. Does every sentence earn its place?
5. Which most faithfully accomplishes the original task?

After reasoning, rank all five from best to worst:

RANKING: [best], [second], [third], [fourth], [worst]"""

BASELINE_PROMPTS = {
    "improve_this": "Improve this document. Make it stronger, more precise, and tighter. Follow all original constraints.\n\n---\n{current}\n---\n\nProduce the complete improved document.",
    "critique_and_revise": "Review this document critically. Find real problems. Then revise to fix every problem. Follow all original constraints.\n\n---\n{current}\n---\n\nProduce the complete revised document.",
    "conservative": "Make changes only if genuinely wrong or weak. If already good, leave as is. Follow all original constraints.\n\n---\n{current}\n---\n\nProduce the complete document.",
    "harsh_critic": "Find every flaw in this document. Rewrite from scratch to address all of them. Follow all original constraints.\n\n---\n{current}\n---\n\nProduce the complete revised document.",
}


async def call_llm(system, user, model=MODEL, temperature=0.7, max_tokens=MAX_TOKENS, max_retries=8):
    for attempt in range(max_retries):
        try:
            response = await litellm.acompletion(
                model=model, messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ], temperature=temperature, max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "429" in err or "overloaded" in err or "529" in err:
                wait = min((2 ** attempt) * 5, 120)
                print(f"    [Rate limited, retrying in {wait}s...]")
                await asyncio.sleep(wait)
            else:
                if attempt < max_retries - 1:
                    await asyncio.sleep(10)
                else:
                    raise
    raise RuntimeError(f"Failed after {max_retries} retries")


def randomize_for_judge(va, vb, vab):
    versions = [("A", va), ("B", vb), ("AB", vab)]
    random.shuffle(versions)
    order = {}
    parts = []
    for i, (label, content) in enumerate(versions, 1):
        order[str(i)] = label
        parts.append(f"PROPOSAL {i}:\n---\n{content}\n---")
    return "\n\n".join(parts), order


def parse_ranking_3way(text):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            nums = [c for c in raw if c in ("1", "2", "3")]
            if len(nums) >= 2:
                return nums
    return None


def parse_ranking_5way(text, valid_chars="ABCDE"):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            items = [c for c in raw.upper() if c in valid_chars]
            if len(items) >= 3:
                return items
    return None


def aggregate_3way(rankings):
    scores = {"A": 0, "B": 0, "AB": 0}
    points = [3, 2, 1]
    valid = [r for r in rankings if r is not None]
    for ranking in valid:
        for pos, label in enumerate(ranking):
            if label in scores and pos < len(points):
                scores[label] += points[pos]
    priority = {"A": 0, "B": 1, "AB": 2}
    ranked = sorted(scores.keys(), key=lambda k: (-scores[k], priority[k]))
    return ranked[0], scores, valid


async def run_autoreason_pass(task_prompt, current_a, pass_num, pass_dir):
    """Run a single autoreason pass: critic -> author B -> synthesizer -> 3 judges."""
    pass_dir.mkdir(parents=True, exist_ok=True)

    result_file = pass_dir / "result.json"
    if result_file.exists():
        existing = json.loads(result_file.read_text())
        if existing.get("winner"):
            w = existing["winner"]
            print(f"    ↳ Skipping ({w})")
            if w == "A":
                return w, current_a, existing
            wf = pass_dir / f"version_{w.lower()}.md"
            return w, wf.read_text() if wf.exists() else current_a, existing

    t0 = time.time()
    (pass_dir / "version_a.md").write_text(current_a)

    print(f"    → Critic...")
    critic = await call_llm(CRITIC_SYSTEM, CRITIC_PROMPT.format(
        version_a=current_a, task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "critic.md").write_text(critic)

    print(f"    → Author B...")
    vb = await call_llm(AUTHOR_B_SYSTEM, AUTHOR_B_PROMPT.format(
        task_prompt=task_prompt, version_a=current_a, critic=critic), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_b.md").write_text(vb)

    print(f"    → Synthesizer...")
    if random.random() < 0.5:
        vx, vy = current_a, vb
    else:
        vx, vy = vb, current_a
    vab = await call_llm(SYNTHESIZER_SYSTEM, SYNTHESIZER_PROMPT.format(
        task_prompt=task_prompt, version_x=vx, version_y=vy), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_ab.md").write_text(vab)

    print(f"    → Judge panel ({NUM_JUDGES_INLOOP} judges)...")
    jtasks = []
    jorders = []
    for _ in range(NUM_JUDGES_INLOOP):
        proposals, order = randomize_for_judge(current_a, vb, vab)
        jorders.append(order)
        jtasks.append(call_llm(COT_JUDGE_SYSTEM, JUDGE_3WAY_PROMPT.format(
            task_prompt=task_prompt, judge_proposals=proposals), MODEL, JUDGE_TEMP, MAX_TOKENS))

    jresps = await asyncio.gather(*jtasks, return_exceptions=True)
    rankings = []
    jdetails = []
    for j, (resp, order) in enumerate(zip(jresps, jorders)):
        if isinstance(resp, Exception):
            print(f"      Judge {j+1}: ERROR")
            rankings.append(None)
            jdetails.append({"error": str(resp)})
        else:
            r = parse_ranking_3way(resp)
            if r:
                r = [order.get(n, n) for n in r]
            rankings.append(r)
            jdetails.append({"ranking": r, "order": order, "raw": resp})
            print(f"      Judge {j+1}: {' > '.join(r) if r else 'PARSE_ERROR'}")

    winner, scores, valid = aggregate_3way(rankings)
    elapsed = time.time() - t0

    vmap = {"A": current_a, "B": vb, "AB": vab}
    result = {"pass": pass_num, "winner": winner, "scores": scores,
              "num_valid": len(valid), "judge_details": jdetails, "elapsed": round(elapsed, 1)}
    (pass_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"    ↳ Winner: {winner} (A={scores['A']}, B={scores['B']}, AB={scores['AB']}) [{elapsed:.0f}s]")
    return winner, vmap[winner], result


async def run_autoreason(task_prompt, out_dir):
    """Run autoreason to convergence."""
    out_dir.mkdir(parents=True, exist_ok=True)

    init_file = out_dir / "initial_a.md"
    if init_file.exists():
        current_a = init_file.read_text()
        print(f"  Using existing initial A ({len(current_a.split())} words)")
    else:
        print("  Generating initial A...")
        current_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt),
                                    MODEL, AUTHOR_TEMP, MAX_TOKENS)
        init_file.write_text(current_a)
        print(f"  Initial A: {len(current_a.split())} words")

    streak = 0
    history = []

    for p in range(1, MAX_PASSES + 1):
        print(f"\n  ━━━ Pass {p} (streak: {streak}/{CONVERGENCE}) ━━━")
        winner, winner_text, result = await run_autoreason_pass(
            task_prompt, current_a, p, out_dir / f"pass_{p:02d}")
        history.append({"pass": p, "winner": winner, "scores": result.get("scores", {}),
                        "words": len(winner_text.split())})

        if winner == "A":
            streak += 1
        else:
            streak = 0
            current_a = winner_text
            (out_dir / f"incumbent_after_pass_{p:02d}.md").write_text(current_a)

        if streak >= CONVERGENCE:
            print(f"\n  ✔ Converged after {p} passes")
            break

    (out_dir / "final_output.md").write_text(current_a)
    (out_dir / "history.json").write_text(json.dumps(history, indent=2))
    print(f"\n  Final: {len(current_a.split())} words")
    print(f"  History: {' → '.join(h['winner'] for h in history)}")
    return current_a


async def run_baselines(task_prompt, initial_a, out_dir, num_passes=15):
    """Run 4 baselines from the same initial output."""
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}

    for bname, bprompt in BASELINE_PROMPTS.items():
        bf = out_dir / f"baseline_{bname}.md"
        if bf.exists():
            outputs[bname] = bf.read_text()
            print(f"  {bname}: {len(outputs[bname].split())}w (cached)")
        else:
            print(f"  {bname}: running {num_passes} passes...", end="", flush=True)
            current = initial_a
            for p in range(num_passes):
                current = await call_llm(AUTHOR_SYSTEM, bprompt.format(current=current),
                                          MODEL, AUTHOR_TEMP, MAX_TOKENS)
                if (p + 1) % 5 == 0:
                    print(f" {p+1}", end="", flush=True)
            bf.write_text(current)
            outputs[bname] = current
            print(f" → {len(current.split())}w")

    return outputs


async def run_eval(task_prompt, initial_a, autoreason_output, baseline_outputs, out_dir):
    """Run 7-judge blind panel."""
    out_dir.mkdir(parents=True, exist_ok=True)

    all_outputs = {"autoreason": autoreason_output}
    all_outputs.update(baseline_outputs)
    method_names = list(all_outputs.keys())
    labels = list("ABCDE")

    print(f"\n  Running {NUM_JUDGES_EVAL}-judge CoT panel...")
    judge_tasks = []
    judge_orders = []
    for _ in range(NUM_JUDGES_EVAL):
        shuffled = method_names.copy()
        random.shuffle(shuffled)
        order = {labels[i]: shuffled[i] for i in range(len(method_names))}
        judge_orders.append(order)
        parts = [f"VERSION {labels[i]}:\n---\n{all_outputs[order[labels[i]]]}\n---"
                 for i in range(len(method_names))]
        judge_tasks.append(call_llm(
            COT_JUDGE_SYSTEM,
            JUDGE_5WAY_PROMPT.format(task_prompt=task_prompt, initial_output=initial_a,
                                     proposals="\n\n".join(parts)),
            MODEL, JUDGE_TEMP, MAX_TOKENS))

    responses = await asyncio.gather(*judge_tasks, return_exceptions=True)

    borda = {n: 0 for n in method_names}
    first_place = {n: 0 for n in method_names}
    points = [5, 4, 3, 2, 1]
    valid = 0

    for j, (resp, order) in enumerate(zip(responses, judge_orders)):
        if isinstance(resp, Exception):
            print(f"  Judge {j+1}: ERROR - {resp}")
            continue
        ranking = parse_ranking_5way(resp)
        if not ranking:
            print(f"  Judge {j+1}: PARSE FAILED")
            (out_dir / f"judge_{j+1}_raw.txt").write_text(resp)
            continue
        valid += 1
        mapped = [order.get(l, l) for l in ranking[:5]]
        for pos, method in enumerate(mapped):
            if method in borda and pos < len(points):
                borda[method] += points[pos]
        if mapped[0] in first_place:
            first_place[mapped[0]] += 1
        print(f"  Judge {j+1}: {', '.join(mapped[:3])}...")
        (out_dir / f"judge_{j+1}_raw.txt").write_text(resp)

    sorted_methods = sorted(borda.items(), key=lambda x: -x[1])
    max_borda = valid * 5

    print(f"\n{'='*60}")
    print(f"RESULTS ({valid} valid judges, max Borda = {max_borda})")
    print(f"{'='*60}")
    print(f"{'Method':<25} {'Borda':>8} {'1st':>5} {'Words':>7}")
    print(f"{'-'*25} {'-'*8} {'-'*5} {'-'*7}")
    for method, score in sorted_methods:
        wc = len(all_outputs[method].split())
        print(f"{method:<25} {score:>8} {first_place[method]:>5} {wc:>7}")

    results = {
        "task": "constrained",
        "model": MODEL,
        "valid_judges": valid,
        "max_borda": max_borda,
        "borda": borda,
        "first_place": first_place,
        "word_counts": {n: len(all_outputs[n].split()) for n in method_names},
    }
    (out_dir / "eval_results.json").write_text(json.dumps(results, indent=2))
    return results


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=int, required=True, choices=[2, 3])
    parser.add_argument("--phase", choices=["autoreason", "baselines", "eval", "all"], default="all")
    args = parser.parse_args()

    root = Path(__file__).parent
    task_path = root.parent.parent / "tasks" / f"task_{args.task:02d}_constrained.md"
    task_prompt = task_path.read_text().strip()
    base_dir = root / f"results_46_new_constrained_task{args.task:02d}"

    print(f"{'='*60}")
    print(f"Constrained Task {args.task} — Sonnet 4.6")
    print(f"Model: {MODEL}")
    print(f"Phase: {args.phase}")
    print(f"{'='*60}\n")

    ar_dir = base_dir / "autoreason"
    bl_dir = base_dir / "baselines"
    eval_dir = base_dir / "eval"

    # Phase 1: Autoreason
    if args.phase in ("autoreason", "all"):
        print("━━━ Phase 1: Autoreason ━━━")
        ar_output = await run_autoreason(task_prompt, ar_dir)

    # Phase 2: Baselines
    if args.phase in ("baselines", "all"):
        print("\n━━━ Phase 2: Baselines (15 passes each) ━━━")
        initial_a = (ar_dir / "initial_a.md").read_text()
        await run_baselines(task_prompt, initial_a, bl_dir)

    # Phase 3: Evaluation
    if args.phase in ("eval", "all"):
        print("\n━━━ Phase 3: 7-Judge Blind Evaluation ━━━")
        ar_output = (ar_dir / "final_output.md").read_text()
        initial_a = (ar_dir / "initial_a.md").read_text()
        baseline_outputs = {}
        for bname in BASELINE_PROMPTS:
            bf = bl_dir / f"baseline_{bname}.md"
            if bf.exists():
                baseline_outputs[bname] = bf.read_text()
            else:
                print(f"  WARNING: {bname} not found, skipping")
        await run_eval(task_prompt, initial_a, ar_output, baseline_outputs, eval_dir)


if __name__ == "__main__":
    asyncio.run(main())
