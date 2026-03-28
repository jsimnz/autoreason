#!/usr/bin/env python3
"""
Blind evaluation of autoreason vs adversarial vs objective outputs.

For each task, takes the final output from all 3 conditions (+ unreviewed Version A as baseline),
randomizes them, and has a fresh judge score each on the rubric.

Each judge call is fully blind — neutral labels, randomized order, no knowledge of condition.
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

sys.path.insert(0, str(Path(__file__).parent))
from run import call_llm

MODEL = "anthropic/claude-sonnet-4-20250514"
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096

EVAL_SYSTEM = """You are an independent evaluator scoring proposals on a rubric. You have no knowledge of how these proposals were produced. Score each one independently on its merits.

Be rigorous. A score of 5 should be rare. Most good proposals are 3-4. Only give 1-2 if there are serious problems."""

EVAL_PROMPT = """TASK:
---
{task_prompt}
---

Score the following proposal on four dimensions (1-5 each).

PROPOSAL:
---
{proposal}
---

Score each dimension and provide brief justification. Respond in this exact JSON format:

{{
  "solves_problem": {{"score": N, "note": "..."}},
  "completeness": {{"score": N, "note": "..."}},
  "coherence": {{"score": N, "note": "..."}},
  "simplicity": {{"score": N, "note": "..."}}
}}"""

TASKS = {
    "task_01": None,
    "task_04": None,
}


def load_tasks(tasks_dir):
    for task_name in TASKS:
        f = tasks_dir / f"{task_name}.md"
        if f.exists():
            TASKS[task_name] = f.read_text().strip()


def collect_outputs(results_dir):
    """Collect all final outputs + baseline Version A for each task/run."""
    entries = []

    for task_name in TASKS:
        for run_idx in range(1, 6):
            run_label = f"run_{run_idx:02d}"

            # Baseline: unreviewed Version A (from autoreason chain)
            baseline_file = results_dir / "autoreason" / task_name / run_label / "pass_0_version_a.md"
            if baseline_file.exists():
                entries.append({
                    "task": task_name,
                    "run": run_idx,
                    "condition": "baseline",
                    "text": baseline_file.read_text(),
                })

            # Final outputs from each condition
            for condition in ["autoreason", "adversarial", "objective"]:
                final_file = results_dir / condition / task_name / run_label / "final_output.md"
                if final_file.exists():
                    entries.append({
                        "task": task_name,
                        "run": run_idx,
                        "condition": condition,
                        "text": final_file.read_text(),
                    })

    return entries


def parse_scores(text):
    """Extract scores from judge response."""
    # Try to find JSON in the response
    import re
    # Look for JSON block
    json_match = re.search(r'\{[^{}]*"solves_problem"[^{}]*\}', text, re.DOTALL)
    if not json_match:
        # Try to find it with nested objects
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

    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: try the whole response
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def evaluate_single(task_prompt, proposal_text, entry_id):
    """Score a single proposal blind."""
    response = await call_llm(
        EVAL_SYSTEM,
        EVAL_PROMPT.format(task_prompt=task_prompt, proposal=proposal_text),
        MODEL, JUDGE_TEMP, MAX_TOKENS,
    )

    scores = parse_scores(response)
    if scores:
        total = sum(
            dim.get("score", 0) if isinstance(dim, dict) else dim
            for dim in scores.values()
            if isinstance(dim, (dict, int, float))
        )
        return {
            "entry_id": entry_id,
            "scores": scores,
            "total": total,
            "raw": response,
        }
    else:
        return {
            "entry_id": entry_id,
            "scores": None,
            "total": None,
            "raw": response,
            "error": "Failed to parse scores",
        }


async def main():
    root = Path(__file__).parent
    load_tasks(root / "tasks")
    results_dir = root / "results_comparison"
    eval_dir = root / "evaluation_comparison"
    eval_dir.mkdir(parents=True, exist_ok=True)

    entries = collect_outputs(results_dir)
    print(f"Collected {len(entries)} outputs to evaluate")
    print(f"  Conditions: {set(e['condition'] for e in entries)}")
    print(f"  Tasks: {set(e['task'] for e in entries)}")
    print()

    # Shuffle to avoid any ordering effects in batch processing
    random.shuffle(entries)

    # Evaluate in batches
    BATCH_SIZE = 10
    all_results = []

    for i in range(0, len(entries), BATCH_SIZE):
        batch = entries[i:i+BATCH_SIZE]
        print(f"Evaluating batch {i//BATCH_SIZE + 1}/{(len(entries)-1)//BATCH_SIZE + 1} ({len(batch)} proposals)...")

        tasks = []
        for j, entry in enumerate(batch):
            entry_id = f"{entry['task']}_{entry['condition']}_run{entry['run']}"
            task_prompt = TASKS[entry["task"]]
            tasks.append(evaluate_single(task_prompt, entry["text"], entry_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for entry, result in zip(batch, results):
            if isinstance(result, Exception):
                print(f"  ERROR: {entry['task']} {entry['condition']} run{entry['run']}: {result}")
                all_results.append({
                    "task": entry["task"],
                    "run": entry["run"],
                    "condition": entry["condition"],
                    "error": str(result),
                })
            else:
                scores = result.get("scores", {})
                total = result.get("total")
                cond = entry["condition"]
                print(f"  {cond:12s} {entry['task']} run{entry['run']}: total={total}")
                all_results.append({
                    "task": entry["task"],
                    "run": entry["run"],
                    "condition": entry["condition"],
                    "scores": scores,
                    "total": total,
                    "raw_judgment": result.get("raw", ""),
                })

    # Save raw results
    (eval_dir / "raw_results.json").write_text(
        json.dumps(all_results, indent=2, ensure_ascii=False))

    # Summary statistics
    print("\n" + "=" * 60)
    print("BLIND EVALUATION RESULTS")
    print("=" * 60)

    from collections import defaultdict
    by_condition = defaultdict(list)
    by_condition_task = defaultdict(list)

    for r in all_results:
        if r.get("total") is not None:
            by_condition[r["condition"]].append(r["total"])
            by_condition_task[(r["condition"], r["task"])].append(r["total"])

    # Overall by condition
    print("\n  Overall scores (sum of 4 dimensions, max=20):")
    for cond in ["baseline", "autoreason", "adversarial", "objective"]:
        scores = by_condition.get(cond, [])
        if scores:
            avg = sum(scores) / len(scores)
            mn, mx = min(scores), max(scores)
            print(f"    {cond:12s}: avg={avg:.1f}  range=[{mn}-{mx}]  n={len(scores)}")

    # Per task
    for task in sorted(TASKS.keys()):
        print(f"\n  {task}:")
        for cond in ["baseline", "autoreason", "adversarial", "objective"]:
            scores = by_condition_task.get((cond, task), [])
            if scores:
                avg = sum(scores) / len(scores)
                print(f"    {cond:12s}: avg={avg:.1f}  scores={scores}")

    # Per dimension
    print("\n  Per dimension (averaged across all runs):")
    dims = ["solves_problem", "completeness", "coherence", "simplicity"]
    for dim in dims:
        print(f"\n    {dim}:")
        for cond in ["baseline", "autoreason", "adversarial", "objective"]:
            dim_scores = []
            for r in all_results:
                if r.get("scores") and r["condition"] == cond:
                    s = r["scores"].get(dim, {})
                    if isinstance(s, dict):
                        dim_scores.append(s.get("score", 0))
                    elif isinstance(s, (int, float)):
                        dim_scores.append(s)
            if dim_scores:
                avg = sum(dim_scores) / len(dim_scores)
                print(f"      {cond:12s}: {avg:.2f}")

    # Save summary
    summary = {
        "overall": {cond: {"avg": sum(s)/len(s), "n": len(s), "scores": s}
                    for cond, s in by_condition.items()},
        "by_task": {f"{cond}_{task}": {"avg": sum(s)/len(s), "scores": s}
                    for (cond, task), s in by_condition_task.items()},
    }
    (eval_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nResults saved to {eval_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
