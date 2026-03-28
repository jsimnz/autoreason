#!/usr/bin/env python3
"""
Blind evaluation v2 — comparing baseline vs pass 2 outputs from autoreason.
Tests whether early passes add value before later passes destroy it.
"""

import asyncio
import json
import os
import random
import sys
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

sys.path.insert(0, str(Path(__file__).parent))
from run import call_llm

MODEL = "anthropic/claude-sonnet-4-20250514"
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096

EVAL_SYSTEM = """You are an independent evaluator scoring professional deliverables. You have no knowledge of how these proposals were produced. Score each one independently on its merits.

These are meant to be working documents that teams execute from. A first draft that's clean but shallow should score lower than a thorough document that covers edge cases, even if the thorough one is longer. Depth and specificity are virtues when the problem warrants them.

Be rigorous. A score of 5 should be rare. Most good proposals are 3-4. Only give 1-2 if there are serious problems."""

EVAL_PROMPT = """TASK:
---
{task_prompt}
---

Score the following proposal on six dimensions (1-5 each).

PROPOSAL:
---
{proposal}
---

Dimensions:

1. SOLVES_PROBLEM: Does it directly address the core problem stated in the task?
2. COMPLETENESS: Does it cover all required elements with appropriate depth?
3. COHERENCE: Is it internally consistent and well-organized?
4. SPECIFICITY: Are recommendations concrete and actionable? Could someone execute from this without guessing what you meant?
5. ANTICIPATES_OBJECTIONS: Does it address likely pushback, risks, and failure modes?
6. APPROPRIATE_COMPLEXITY: Is the level of detail right-sized for the problem? Too simple for a complex problem is bad. Unnecessarily complex for a simple problem is also bad. Caveats and nuance are good when the problem warrants them.

Score each dimension and provide brief justification. Respond in this exact JSON format:

{{
  "solves_problem": {{"score": N, "note": "..."}},
  "completeness": {{"score": N, "note": "..."}},
  "coherence": {{"score": N, "note": "..."}},
  "specificity": {{"score": N, "note": "..."}},
  "anticipates_objections": {{"score": N, "note": "..."}},
  "appropriate_complexity": {{"score": N, "note": "..."}}
}}"""

TASKS = {"task_01": None, "task_04": None}


def load_tasks(tasks_dir):
    for task_name in TASKS:
        f = tasks_dir / f"{task_name}.md"
        if f.exists():
            TASKS[task_name] = f.read_text().strip()


def extract_score(dim_value):
    if isinstance(dim_value, dict):
        return dim_value.get("score", 0)
    elif isinstance(dim_value, (int, float)):
        return dim_value
    return 0


def parse_scores(text):
    brace_count = 0
    start = None
    for i, c in enumerate(text):
        if c == '{':
            if brace_count == 0:
                start = i
            brace_count += 1
        elif c == '}':
            brace_count -= 1
            if brace_count == 0 and start is not None:
                try:
                    parsed = json.loads(text[start:i+1])
                    if "solves_problem" in parsed:
                        return parsed
                except json.JSONDecodeError:
                    continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def get_pass2_output(run_dir):
    """Get the winning version after pass 2 of an autoreason chain."""
    judge_file = run_dir / "pass_2_judge.json"
    if not judge_file.exists():
        return None

    judge_data = json.loads(judge_file.read_text())
    pick = judge_data.get("pick")

    if pick == "A":
        # A at pass 2 means the pass 1 winner (need to reconstruct)
        # The "A" in pass 2 is whatever won pass 1
        # Check pass 1 judge
        j1 = run_dir / "pass_1_judge.json"
        if j1.exists():
            p1 = json.loads(j1.read_text()).get("pick")
            if p1 == "A":
                f = run_dir / "pass_0_version_a.md"
            elif p1 == "B":
                f = run_dir / "pass_1_version_b.md"
            elif p1 == "AB":
                f = run_dir / "pass_1_version_ab.md"
            else:
                return None
            return f.read_text() if f.exists() else None
        return None
    elif pick == "B":
        f = run_dir / "pass_2_version_b.md"
    elif pick == "AB":
        f = run_dir / "pass_2_version_ab.md"
    else:
        return None

    return f.read_text() if f.exists() else None


def collect_outputs(results_dir):
    entries = []
    for task_name in TASKS:
        for run_idx in range(1, 6):
            run_label = f"run_{run_idx:02d}"

            # Baseline
            baseline_file = results_dir / "autoreason" / task_name / run_label / "pass_0_version_a.md"
            if baseline_file.exists():
                entries.append({
                    "task": task_name, "run": run_idx,
                    "condition": "baseline", "text": baseline_file.read_text(),
                })

            # Pass 2 autoreason output
            run_dir = results_dir / "autoreason" / task_name / run_label
            pass2_text = get_pass2_output(run_dir)
            if pass2_text:
                entries.append({
                    "task": task_name, "run": run_idx,
                    "condition": "autoreason_2pass", "text": pass2_text,
                })

            # Pass 7 (final) autoreason output for comparison
            final_file = results_dir / "autoreason" / task_name / run_label / "final_output.md"
            if final_file.exists():
                entries.append({
                    "task": task_name, "run": run_idx,
                    "condition": "autoreason_7pass", "text": final_file.read_text(),
                })

    return entries


async def evaluate_single(task_prompt, proposal_text):
    response = await call_llm(
        EVAL_SYSTEM,
        EVAL_PROMPT.format(task_prompt=task_prompt, proposal=proposal_text),
        MODEL, JUDGE_TEMP, MAX_TOKENS,
    )
    scores = parse_scores(response)
    if scores:
        total = sum(extract_score(v) for v in scores.values())
        return {"scores": scores, "total": total, "raw": response}
    return {"scores": None, "total": None, "raw": response, "error": "parse_failed"}


async def main():
    root = Path(__file__).parent
    load_tasks(root / "tasks")
    results_dir = root / "results_comparison"
    eval_dir = root / "evaluation_comparison_v2_pass2"
    eval_dir.mkdir(parents=True, exist_ok=True)

    entries = collect_outputs(results_dir)
    random.shuffle(entries)

    conditions_found = set(e["condition"] for e in entries)
    print(f"Evaluating {len(entries)} outputs: {conditions_found}")
    print()

    BATCH_SIZE = 10
    all_results = []

    for i in range(0, len(entries), BATCH_SIZE):
        batch = entries[i:i+BATCH_SIZE]
        print(f"Batch {i//BATCH_SIZE + 1}/{(len(entries)-1)//BATCH_SIZE + 1}...")

        tasks = [evaluate_single(TASKS[e["task"]], e["text"]) for e in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for entry, result in zip(batch, results):
            if isinstance(result, Exception):
                print(f"  ERROR: {entry['condition']} {entry['task']} run{entry['run']}: {result}")
                all_results.append({
                    "task": entry["task"], "run": entry["run"],
                    "condition": entry["condition"], "error": str(result),
                })
            else:
                total = result.get("total")
                print(f"  {entry['condition']:20s} {entry['task']} run{entry['run']}: {total}/30")
                all_results.append({
                    "task": entry["task"], "run": entry["run"],
                    "condition": entry["condition"],
                    "scores": result.get("scores"), "total": total,
                    "raw_judgment": result.get("raw", ""),
                })

    (eval_dir / "raw_results.json").write_text(
        json.dumps(all_results, indent=2, ensure_ascii=False))

    # Summary
    from collections import defaultdict

    print("\n" + "=" * 60)
    print("PASS 2 vs PASS 7 vs BASELINE")
    print("=" * 60)

    by_condition = defaultdict(list)
    by_condition_task = defaultdict(list)

    for r in all_results:
        if r.get("total") is not None:
            by_condition[r["condition"]].append(r["total"])
            by_condition_task[(r["condition"], r["task"])].append(r["total"])

    print(f"\n  Overall scores (max=30):")
    for cond in ["baseline", "autoreason_2pass", "autoreason_7pass"]:
        scores = by_condition.get(cond, [])
        if scores:
            avg = sum(scores) / len(scores)
            mn, mx = min(scores), max(scores)
            print(f"    {cond:20s}: avg={avg:.1f}  range=[{mn}-{mx}]  n={len(scores)}")

    baseline_avg = sum(by_condition["baseline"]) / len(by_condition["baseline"]) if by_condition["baseline"] else 0
    print(f"\n  Delta from baseline:")
    for cond in ["autoreason_2pass", "autoreason_7pass"]:
        scores = by_condition.get(cond, [])
        if scores:
            avg = sum(scores) / len(scores)
            print(f"    {cond:20s}: {avg - baseline_avg:+.1f}")

    dims = ["solves_problem", "completeness", "coherence", "specificity",
            "anticipates_objections", "appropriate_complexity"]
    print(f"\n  Per dimension:")
    for dim in dims:
        line_parts = [f"    {dim:25s}:"]
        for cond in ["baseline", "autoreason_2pass", "autoreason_7pass"]:
            dim_scores = []
            for r in all_results:
                if r.get("scores") and r["condition"] == cond:
                    dim_scores.append(extract_score(r["scores"].get(dim, 0)))
            if dim_scores:
                avg = sum(dim_scores) / len(dim_scores)
                line_parts.append(f"{cond}={avg:.2f}")
        print("  ".join(line_parts))

    for task in sorted(TASKS.keys()):
        print(f"\n  {task}:")
        for cond in ["baseline", "autoreason_2pass", "autoreason_7pass"]:
            scores = by_condition_task.get((cond, task), [])
            if scores:
                avg = sum(scores) / len(scores)
                print(f"    {cond:20s}: avg={avg:.1f}  scores={scores}")

    (eval_dir / "summary.json").write_text(json.dumps({
        "overall": {cond: {"avg": sum(s)/len(s), "scores": s}
                    for cond, s in by_condition.items()},
    }, indent=2))
    print(f"\nSaved to {eval_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
