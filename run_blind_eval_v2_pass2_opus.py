#!/usr/bin/env python3
"""
Blind evaluation v2 with Opus as judge — same rubric, same outputs.
Compare against Sonnet judge results.
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
from run_blind_eval_v2_pass2 import (
    EVAL_SYSTEM, EVAL_PROMPT, TASKS,
    load_tasks, collect_outputs, parse_scores, extract_score, evaluate_single,
)

# Override model
MODEL = "anthropic/claude-opus-4-20250514"
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096


async def evaluate_single_opus(task_prompt, proposal_text):
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
    eval_dir = root / "evaluation_comparison_v2_pass2_opus"
    eval_dir.mkdir(parents=True, exist_ok=True)

    entries = collect_outputs(results_dir)
    random.shuffle(entries)

    print(f"Evaluating {len(entries)} outputs with OPUS judge")
    print(f"Model: {MODEL}")
    print()

    BATCH_SIZE = 5  # Opus is slower, smaller batches
    all_results = []

    for i in range(0, len(entries), BATCH_SIZE):
        batch = entries[i:i+BATCH_SIZE]
        print(f"Batch {i//BATCH_SIZE + 1}/{(len(entries)-1)//BATCH_SIZE + 1}...")

        tasks = [evaluate_single_opus(TASKS[e["task"]], e["text"]) for e in batch]
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

    from collections import defaultdict

    print("\n" + "=" * 60)
    print("OPUS JUDGE: PASS 2 vs PASS 7 vs BASELINE")
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

    # Comparison with Sonnet judge
    sonnet_file = root / "evaluation_comparison_v2_pass2" / "summary.json"
    if sonnet_file.exists():
        sonnet = json.loads(sonnet_file.read_text())
        print(f"\n  Sonnet vs Opus judge comparison:")
        print(f"    {'':20s}  {'Sonnet':>8s}  {'Opus':>8s}  {'Delta':>8s}")
        for cond in ["baseline", "autoreason_2pass", "autoreason_7pass"]:
            s_scores = sonnet.get("overall", {}).get(cond, {}).get("scores", [])
            o_scores = by_condition.get(cond, [])
            if s_scores and o_scores:
                s_avg = sum(s_scores) / len(s_scores)
                o_avg = sum(o_scores) / len(o_scores)
                print(f"    {cond:20s}  {s_avg:8.1f}  {o_avg:8.1f}  {o_avg - s_avg:+8.1f}")

    (eval_dir / "summary.json").write_text(json.dumps({
        "judge_model": MODEL,
        "overall": {cond: {"avg": sum(s)/len(s) if s else 0, "scores": s}
                    for cond, s in by_condition.items() if s},
    }, indent=2))
    print(f"\nSaved to {eval_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
