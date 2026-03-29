#!/usr/bin/env python3
"""
CoT autoreason on Task 2 (notification system) + baselines + CoT 7-judge panel.
Tests whether CoT judges improve autoreason's worst-performing task.
"""

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

MODEL = "anthropic/claude-sonnet-4-20250514"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
MAX_PASSES = 30
CONVERGENCE = 2

AUTHOR_SYSTEM = "You are a senior consultant producing professional deliverables. Be specific, concrete, and practical."
CRITIC_SYSTEM = "You are a critical reviewer. Find real problems. Be specific. Do not suggest fixes."
AUTHOR_B_SYSTEM = "You are a senior consultant revising a proposal based on criticisms. Address each valid criticism directly."
SYNTH_SYSTEM = "You are a senior consultant. Take the strongest elements from two versions and produce a coherent synthesis."

COT_JUDGE_SYSTEM = "You are an independent evaluator. You have no authorship stake. Think carefully before deciding."

GENERATE_A = "{task_prompt}\n\nProduce a complete, detailed proposal."
CRITIC_PROMPT = "Find real problems with this proposal. No fixes.\n\n---\n{version_a}\n---"
AUTHOR_B_PROMPT = "TASK:\n---\n{task_prompt}\n---\n\nPROPOSAL:\n---\n{version_a}\n---\n\nPROBLEMS:\n---\n{critic}\n---\n\nRevise to address these problems."
SYNTH_PROMPT = "TASK:\n---\n{task_prompt}\n---\n\nVERSION X:\n---\n{vx}\n---\n\nVERSION Y:\n---\n{vy}\n---\n\nSynthesize the strongest elements."

COT_JUDGE_3WAY = """ORIGINAL TASK:
---
{task_prompt}
---

Three proposals:

{proposals}

For each proposal, think step by step:
1. What does it get right about the task?
2. What does it get wrong or miss?
3. Are the numbers and claims defensible?
4. Is the detail level appropriate or bloated?

After reasoning through each, rank all three from best to worst.

RANKING: [best], [second], [worst]"""

COT_JUDGE_5WAY = """ORIGINAL TASK:
---
{task_prompt}
---

INITIAL OUTPUT (starting point):
---
{initial_output}
---

Five teams independently improved the initial output:

{proposals}

For each version, think step by step:
1. How well does it accomplish the task?
2. How much has it improved over the initial output?
3. Are claims and numbers grounded?
4. Is detail appropriate or bloated?

After reasoning, rank all five from best to worst:

RANKING: [best], [second], [third], [fourth], [worst]"""

BASELINE_PROMPTS = {
    "improve_this": "Improve this proposal. Make it stronger and more thorough.\n\n---\n{current_version}\n---\n\nORIGINAL TASK:\n---\n{task_prompt}\n---\n\nProduce the complete improved proposal.",
    "critique_and_revise": "Review critically. Find real problems. Then revise to fix every problem.\n\n---\n{current_version}\n---\n\nORIGINAL TASK:\n---\n{task_prompt}\n---\n\nProduce the complete revised proposal.",
    "conservative": "Make changes only if genuinely wrong or missing. If already good, leave as is.\n\n---\n{current_version}\n---\n\nORIGINAL TASK:\n---\n{task_prompt}\n---\n\nProduce the complete proposal.",
    "harsh_critic": "Find every flaw. Rewrite from scratch to address all of them.\n\n---\n{current_version}\n---\n\nORIGINAL TASK:\n---\n{task_prompt}\n---\n\nProduce the complete revised proposal.",
}


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
                await asyncio.sleep(wait)
            else:
                if attempt < max_retries - 1:
                    await asyncio.sleep(10)
                else:
                    raise
    raise RuntimeError(f"Failed after {max_retries} retries")


def randomize_proposals(va, vb, vab):
    versions = [("A", va), ("B", vb), ("AB", vab)]
    random.shuffle(versions)
    order = {str(i+1): label for i, (label, _) in enumerate(versions)}
    parts = [f"PROPOSAL {i+1}:\n---\n{content}\n---" for i, (_, content) in enumerate(versions)]
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


async def run_pass(task_prompt, current_a, pass_num, pass_dir):
    pass_dir.mkdir(parents=True, exist_ok=True)
    result_file = pass_dir / "result.json"
    if result_file.exists():
        ex = json.loads(result_file.read_text())
        if ex.get("winner"):
            w = ex["winner"]
            if w == "A": return w, current_a, ex
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
    vab = await call_llm(SYNTH_SYSTEM, SYNTH_PROMPT.format(task_prompt=task_prompt, vx=vx, vy=vy), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_ab.md").write_text(vab)

    # CoT judges
    rankings, order_maps = [], []
    for _ in range(3):
        proposals, om = randomize_proposals(current_a, vb, vab)
        order_maps.append(om)
        resp = await call_llm(COT_JUDGE_SYSTEM, COT_JUDGE_3WAY.format(task_prompt=task_prompt, proposals=proposals), MODEL, JUDGE_TEMP, MAX_TOKENS)
        raw = parse_ranking(resp)
        rankings.append([om.get(r, r) for r in raw] if raw else None)

    scores = {"A": 0, "B": 0, "AB": 0}
    points = [3, 2, 1]
    valid = 0
    for r in rankings:
        if not r: continue
        valid += 1
        for pos, label in enumerate(r):
            if label in scores and pos < 3:
                scores[label] += points[pos]

    priority = {"A": 0, "B": 1, "AB": 2}
    winner = sorted(scores.keys(), key=lambda k: (-scores[k], priority[k]))[0]
    elapsed = time.time() - t0

    vmap = {"A": current_a, "B": vb, "AB": vab}
    result = {"pass": pass_num, "winner": winner, "scores": scores, "valid": valid, "elapsed": round(elapsed, 1)}
    (pass_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return winner, vmap[winner], result


async def main():
    task_prompt = Path("/root/autoreason-experiment/tasks/task_02.md").read_text().strip()
    root = Path(__file__).parent
    out_dir = root / "results_cot_task02"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"CoT Autoreason — Task 2 (worst performer)")
    print(f"Model: {MODEL}")
    print(f"{'='*60}\n")

    # Autoreason with CoT judges
    ar_dir = out_dir / "autoreason"
    ar_dir.mkdir(parents=True, exist_ok=True)
    init_file = ar_dir / "initial_a.md"
    if init_file.exists():
        current_a = init_file.read_text()
    else:
        current_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
        init_file.write_text(current_a)
    print(f"  Initial A: {len(current_a.split())} words")

    initial_a = current_a  # save for baselines
    streak, history = 0, []
    for p in range(1, MAX_PASSES + 1):
        winner, winner_text, result = await run_pass(task_prompt, current_a, p, ar_dir / f"pass_{p:02d}")
        history.append({"pass": p, "winner": winner, "scores": result.get("scores", {})})
        print(f"  Pass {p}: {winner} (A={result['scores']['A']}, B={result['scores']['B']}, AB={result['scores']['AB']}) [{result['elapsed']:.0f}s]")
        if winner == "A":
            streak += 1
        else:
            streak = 0
            current_a = winner_text
            (ar_dir / f"incumbent_after_{p:02d}.md").write_text(current_a)
        if streak >= CONVERGENCE:
            print(f"  ✔ Converged at pass {p}")
            break

    ar_output = current_a
    (ar_dir / "final_output.md").write_text(ar_output)
    (ar_dir / "history.json").write_text(json.dumps(history, indent=2))
    traj = " → ".join(h["winner"] for h in history)
    print(f"  Final: {len(ar_output.split())} words, {traj}\n")

    # Baselines (15 passes each from same initial A)
    print(f"  Running baselines...")
    baseline_outputs = {}
    for bname, bprompt in BASELINE_PROMPTS.items():
        bf = out_dir / f"baseline_{bname}.md"
        if bf.exists():
            baseline_outputs[bname] = bf.read_text()
            print(f"    {bname}: already complete")
        else:
            print(f"    Running {bname} (15 passes)...")
            current = initial_a
            for p in range(15):
                current = await call_llm(AUTHOR_SYSTEM, bprompt.format(current_version=current, task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
            bf.write_text(current)
            baseline_outputs[bname] = current
            print(f"    {bname}: {len(current.split())} words")

    # CoT 7-judge panel
    print(f"\n  Running CoT 7-judge panel...")
    all_outputs = {"autoreason_cot": ar_output}
    all_outputs.update(baseline_outputs)
    method_names = list(all_outputs.keys())
    labels = ["A", "B", "C", "D", "E"]

    jtasks, jorders = [], []
    for _ in range(7):
        shuffled = method_names.copy()
        random.shuffle(shuffled)
        order = {labels[i]: shuffled[i] for i in range(5)}
        jorders.append(order)
        parts = [f"VERSION {labels[i]}:\n---\n{all_outputs[order[labels[i]]]}---" for i in range(5)]
        jtasks.append(call_llm(COT_JUDGE_SYSTEM, COT_JUDGE_5WAY.format(
            task_prompt=task_prompt, initial_output=initial_a, proposals="\n\n".join(parts)
        ), MODEL, JUDGE_TEMP, MAX_TOKENS))

    jresps = await asyncio.gather(*jtasks, return_exceptions=True)
    borda = {n: 0 for n in method_names}
    first_place = {n: 0 for n in method_names}
    points = [5, 4, 3, 2, 1]
    for resp, order in zip(jresps, jorders):
        if isinstance(resp, Exception): continue
        ranking = parse_ranking(resp, "ABCDE")
        if ranking:
            mapped = [order.get(l, l) for l in ranking]
            for pos, method in enumerate(mapped):
                if method in borda and pos < len(points):
                    borda[method] += points[pos]
            if mapped[0] in first_place:
                first_place[mapped[0]] += 1

    sorted_methods = sorted(borda.items(), key=lambda x: -x[1])
    print(f"\n  Results (CoT judges):")
    for name, score in sorted_methods:
        print(f"    {name:25s} Borda={score:3d} 1st={first_place.get(name, 0)}")

    print(f"\n  Previous result (baseline judges):")
    print(f"    critique_and_revise: 22, autoreason: 19, conservative: 19, harsh_critic: 19, improve_this: 11")

    result = {"borda": borda, "first_place": first_place}
    (out_dir / "judge_results.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
