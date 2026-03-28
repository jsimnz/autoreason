#!/usr/bin/env python3
"""
Quick single-pass test with Opus as both author and judge.
3 runs on task 01 only. Compares baseline vs 1-pass autoreason.
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
from run import (
    AUTHOR_SYSTEM, JUDGE_SYSTEM,
    STEP1_USER, STEP2_USER, STEP3_USER, STEP4_USER, STEP5_USER,
    call_llm, randomize_for_judge, parse_judgment,
)
from run_blind_eval_v2_pass2 import (
    EVAL_SYSTEM, EVAL_PROMPT, parse_scores, extract_score,
)

MODEL = "anthropic/claude-opus-4-20250514"
AUTHOR_TEMP = 1.0
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
RUNS = 3


async def main():
    root = Path(__file__).parent
    task_prompt = (root / "tasks" / "task_01.md").read_text().strip()
    results_dir = root / "results_opus_quick"
    results_dir.mkdir(parents=True, exist_ok=True)

    all_evals = []

    for run_idx in range(1, RUNS + 1):
        run_dir = results_dir / f"run_{run_idx:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)

        print(f"━━━ Run {run_idx}/{RUNS}")

        # Step 1: Version A
        print("  Generating Version A...")
        version_a = await call_llm(AUTHOR_SYSTEM, STEP1_USER.format(task_prompt=task_prompt),
                                    MODEL, AUTHOR_TEMP, MAX_TOKENS)
        (run_dir / "version_a.md").write_text(version_a)

        # Step 2: Strawman
        print("  Strawman...")
        strawman = await call_llm(AUTHOR_SYSTEM, STEP2_USER.format(version_a=version_a),
                                   MODEL, AUTHOR_TEMP, MAX_TOKENS)
        (run_dir / "strawman.md").write_text(strawman)

        # Step 3: Version B
        print("  Version B...")
        version_b = await call_llm(AUTHOR_SYSTEM,
                                    STEP3_USER.format(version_a=version_a, strawman=strawman),
                                    MODEL, AUTHOR_TEMP, MAX_TOKENS)
        (run_dir / "version_b.md").write_text(version_b)

        # Step 4: Version AB
        print("  Version AB...")
        version_ab = await call_llm(AUTHOR_SYSTEM,
                                     STEP4_USER.format(version_a=version_a, version_b=version_b),
                                     MODEL, AUTHOR_TEMP, MAX_TOKENS)
        (run_dir / "version_ab.md").write_text(version_ab)

        # Step 5: Judge (blind, randomized)
        print("  Judge...")
        judge_proposals, order_map = randomize_for_judge(version_a, version_b, version_ab)
        judgment = await call_llm(JUDGE_SYSTEM,
                                   STEP5_USER.format(task_prompt=task_prompt,
                                                     judge_proposals=judge_proposals),
                                   MODEL, JUDGE_TEMP, MAX_TOKENS)
        pick, pick_num = parse_judgment(judgment, order_map)
        (run_dir / "judge.json").write_text(json.dumps({
            "pick": pick, "pick_position": pick_num,
            "presentation_order": order_map, "raw_judgment": judgment,
        }, indent=2, ensure_ascii=False))

        print(f"  Judge picked: {pick or '?'} (position {pick_num}, order={list(order_map.values())})")

        # Get winner text
        if pick == "B":
            winner = version_b
        elif pick == "AB":
            winner = version_ab
        else:
            winner = version_a
        (run_dir / "winner.md").write_text(winner)

        # Blind eval: score both baseline and winner
        print("  Scoring baseline...")
        baseline_eval = await call_llm(
            EVAL_SYSTEM,
            EVAL_PROMPT.format(task_prompt=task_prompt, proposal=version_a),
            MODEL, JUDGE_TEMP, MAX_TOKENS)
        baseline_scores = parse_scores(baseline_eval)
        baseline_total = sum(extract_score(v) for v in baseline_scores.values()) if baseline_scores else None

        print("  Scoring winner...")
        winner_eval = await call_llm(
            EVAL_SYSTEM,
            EVAL_PROMPT.format(task_prompt=task_prompt, proposal=winner),
            MODEL, JUDGE_TEMP, MAX_TOKENS)
        winner_scores = parse_scores(winner_eval)
        winner_total = sum(extract_score(v) for v in winner_scores.values()) if winner_scores else None

        print(f"  Baseline: {baseline_total}/30  |  Winner ({pick}): {winner_total}/30  |  Delta: {(winner_total or 0) - (baseline_total or 0):+d}")

        all_evals.append({
            "run": run_idx,
            "pick": pick,
            "baseline_total": baseline_total,
            "baseline_scores": baseline_scores,
            "winner_total": winner_total,
            "winner_scores": winner_scores,
        })
        print()

    # Summary
    print("=" * 60)
    print("OPUS AUTHOR + OPUS JUDGE: SINGLE PASS")
    print("=" * 60)

    dims = ["solves_problem", "completeness", "coherence", "specificity",
            "anticipates_objections", "appropriate_complexity"]

    b_totals = [e["baseline_total"] for e in all_evals if e["baseline_total"]]
    w_totals = [e["winner_total"] for e in all_evals if e["winner_total"]]

    print(f"\n  Overall (max=30, n={len(b_totals)}):")
    print(f"    Baseline:  avg={sum(b_totals)/len(b_totals):.1f}  scores={b_totals}")
    print(f"    1-pass:    avg={sum(w_totals)/len(w_totals):.1f}  scores={w_totals}")
    print(f"    Delta:     {sum(w_totals)/len(w_totals) - sum(b_totals)/len(b_totals):+.1f}")

    print(f"\n  Per dimension:")
    for dim in dims:
        b_dim = [extract_score(e["baseline_scores"].get(dim, 0)) for e in all_evals if e["baseline_scores"]]
        w_dim = [extract_score(e["winner_scores"].get(dim, 0)) for e in all_evals if e["winner_scores"]]
        if b_dim and w_dim:
            b_avg = sum(b_dim) / len(b_dim)
            w_avg = sum(w_dim) / len(w_dim)
            print(f"    {dim:25s}: baseline={b_avg:.2f}  1-pass={w_avg:.2f}  delta={w_avg-b_avg:+.2f}")

    print(f"\n  Judge picks: {[e['pick'] for e in all_evals]}")

    (results_dir / "summary.json").write_text(json.dumps(all_evals, indent=2, ensure_ascii=False))
    print(f"\nSaved to {results_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
