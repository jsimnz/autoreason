#!/usr/bin/env python3
"""
Autoreason matrix experiment — multiple temperature combos and pass counts.

Usage:
    python run_matrix.py                  # run full matrix
    python run_matrix.py --variant chaos_1pass  # run one variant
    python run_matrix.py --dry-run        # print plan
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Load env
# ---------------------------------------------------------------------------
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

# Import shared components from run.py
sys.path.insert(0, str(Path(__file__).parent))
from run import (
    AUTHOR_SYSTEM, JUDGE_SYSTEM,
    STEP1_USER, STEP2_USER, STEP3_USER, STEP4_USER, STEP5_USER,
    call_llm, randomize_for_judge, parse_judgment,
)


async def run_single_pass(task_prompt, version_a, author_model, author_temp,
                          judge_model, judge_temp, max_tokens):
    """Run one autoreason pass starting from version_a. Returns (pick, artifacts)."""

    # Step 2: Strawman
    strawman = await call_llm(
        AUTHOR_SYSTEM,
        STEP2_USER.format(version_a=version_a),
        author_model, author_temp, max_tokens,
    )

    # Step 3: Version B
    version_b = await call_llm(
        AUTHOR_SYSTEM,
        STEP3_USER.format(version_a=version_a, strawman=strawman),
        author_model, author_temp, max_tokens,
    )

    # Step 4: Version AB
    version_ab = await call_llm(
        AUTHOR_SYSTEM,
        STEP4_USER.format(version_a=version_a, version_b=version_b),
        author_model, author_temp, max_tokens,
    )

    # Step 5: Judge (blind, randomized)
    judge_proposals, order_map = randomize_for_judge(version_a, version_b, version_ab)
    judgment = await call_llm(
        JUDGE_SYSTEM,
        STEP5_USER.format(task_prompt=task_prompt, judge_proposals=judge_proposals),
        judge_model, judge_temp, max_tokens,
    )
    pick, pick_num = parse_judgment(judgment, order_map)

    # Get the winning version text
    if pick == "A":
        winner_text = version_a
    elif pick == "B":
        winner_text = version_b
    elif pick == "AB":
        winner_text = version_ab
    else:
        winner_text = version_ab  # fallback

    artifacts = {
        "strawman": strawman,
        "version_b": version_b,
        "version_ab": version_ab,
        "judgment": judgment,
        "pick": pick,
        "pick_position": pick_num,
        "presentation_order": order_map,
    }

    return pick, winner_text, artifacts


async def run_multi_pass(task_prompt, run_dir, variant, config, dry_run=False):
    """Run N autoreason passes, chaining the winner as new A each time."""
    author_model = config["author_model"]
    judge_model = config["judge_model"]
    author_temp = variant["author_temperature"]
    judge_temp = variant["judge_temperature"]
    passes = variant["passes"]
    max_tokens = config["max_tokens"]

    run_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing results
    summary_file = run_dir / "summary.json"
    if summary_file.exists():
        existing = json.loads(summary_file.read_text())
        if existing.get("picks"):
            print(f"    ↳ Skipping (already complete)")
            return existing

    if dry_run:
        print(f"    ↳ [DRY RUN] {passes} pass(es), {passes * 5} LLM calls")
        return {"picks": ["DRY"] * passes}

    t0 = time.time()

    # Step 1: Version A (only on first pass)
    version_a = await call_llm(
        AUTHOR_SYSTEM,
        STEP1_USER.format(task_prompt=task_prompt),
        author_model, author_temp, max_tokens,
    )
    (run_dir / "pass_0_version_a.md").write_text(version_a)

    current_a = version_a
    picks = []

    for pass_idx in range(passes):
        prefix = f"pass_{pass_idx + 1}"
        pick, winner_text, artifacts = await run_single_pass(
            task_prompt, current_a,
            author_model, author_temp,
            judge_model, judge_temp,
            max_tokens,
        )

        # Save artifacts
        (run_dir / f"{prefix}_strawman.md").write_text(artifacts["strawman"])
        (run_dir / f"{prefix}_version_b.md").write_text(artifacts["version_b"])
        (run_dir / f"{prefix}_version_ab.md").write_text(artifacts["version_ab"])
        (run_dir / f"{prefix}_judge.json").write_text(json.dumps({
            "pick": artifacts["pick"],
            "pick_position": artifacts["pick_position"],
            "presentation_order": artifacts["presentation_order"],
            "raw_judgment": artifacts["judgment"],
        }, indent=2, ensure_ascii=False))

        picks.append(pick)
        current_a = winner_text
        pick_display = pick or "PARSE_ERROR"
        print(f"    ↳ Pass {pass_idx + 1}: {pick_display}")

    # Save final winner
    (run_dir / "final_output.md").write_text(current_a)

    elapsed = time.time() - t0
    summary = {
        "picks": picks,
        "variant": variant["name"],
        "author_temperature": author_temp,
        "judge_temperature": judge_temp,
        "passes": passes,
        "elapsed_seconds": round(elapsed, 1),
    }
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"    ↳ Done: {' → '.join(p or '?' for p in picks)} ({elapsed:.0f}s)")
    return summary


def load_tasks(tasks_dir, task_nums):
    """Load specific task prompts."""
    tasks = []
    for n in task_nums:
        f = tasks_dir / f"task_{n:02d}.md"
        if f.exists():
            tasks.append((f.stem, f.read_text().strip()))
        else:
            print(f"Warning: {f} not found")
    return tasks


async def main():
    parser = argparse.ArgumentParser(description="Autoreason matrix experiment")
    parser.add_argument("--variant", type=str, help="Run only this variant")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).parent
    config = yaml.safe_load((root / "config_matrix.yaml").read_text())

    task_nums = config.get("tasks", [1, 4])
    tasks = load_tasks(root / "tasks", task_nums)
    variants = config["variants"]
    runs_per = config["runs_per_variant"]
    batch_size = config.get("batch_size", 5)

    if args.variant:
        variants = [v for v in variants if v["name"] == args.variant]
        if not variants:
            print(f"Variant '{args.variant}' not found")
            sys.exit(1)

    total_calls = sum(v["passes"] * 5 + 1 for v in variants) * len(tasks) * runs_per
    print(f"Matrix experiment: {len(variants)} variants × {len(tasks)} tasks × {runs_per} runs")
    print(f"Estimated LLM calls: ~{total_calls}")
    print()

    results_dir = root / "results_matrix"
    all_results = []

    for variant in variants:
        vname = variant["name"]
        print(f"══ {vname} (author={variant['author_temperature']}, judge={variant['judge_temperature']}, passes={variant['passes']})")

        for task_name, task_prompt in tasks:
            print(f"  ━━ {task_name}")

            batch = []
            run_meta = []
            for run_idx in range(runs_per):
                run_dir = results_dir / vname / task_name / f"run_{run_idx + 1:02d}"
                print(f"    Run {run_idx + 1}/{runs_per}")
                batch.append(run_multi_pass(task_prompt, run_dir, variant, config, args.dry_run))
                run_meta.append((vname, task_name, run_idx + 1))

                # Flush batch
                if len(batch) >= batch_size:
                    results = await asyncio.gather(*batch, return_exceptions=True)
                    for (v, t, r), res in zip(run_meta, results):
                        if isinstance(res, Exception):
                            print(f"    ↳ ERROR: {res}")
                            all_results.append({"variant": v, "task": t, "run": r, "error": str(res)})
                        else:
                            all_results.append({"variant": v, "task": t, "run": r, **res})
                    batch = []
                    run_meta = []

            # Flush remaining
            if batch:
                results = await asyncio.gather(*batch, return_exceptions=True)
                for (v, t, r), res in zip(run_meta, results):
                    if isinstance(res, Exception):
                        print(f"    ↳ ERROR: {res}")
                        all_results.append({"variant": v, "task": t, "run": r, "error": str(res)})
                    else:
                        all_results.append({"variant": v, "task": t, "run": r, **res})

        print()

    # Summary
    summary_file = results_dir / "matrix_summary.json"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(json.dumps(all_results, indent=2, ensure_ascii=False, default=str))

    # Print quick stats
    if not args.dry_run:
        from collections import Counter
        print("=" * 60)
        print("MATRIX RESULTS")
        print("=" * 60)

        for variant in config["variants"]:
            vname = variant["name"]
            vresults = [r for r in all_results if r.get("variant") == vname and "picks" in r]
            if not vresults:
                continue

            # Count final picks (last pass)
            final_picks = Counter()
            for r in vresults:
                picks = r["picks"]
                if picks:
                    final = picks[-1]
                    if final:
                        final_picks[final] += 1

            total = sum(final_picks.values())
            if not total:
                continue

            passes = variant["passes"]
            print(f"\n{vname} (a={variant['author_temperature']}, j={variant['judge_temperature']}, {passes}p, n={total}):")
            for label in ("A", "B", "AB"):
                count = final_picks.get(label, 0)
                pct = count / total * 100
                bar = "█" * int(pct / 2)
                print(f"  {label:>2}: {count:2d} ({pct:4.0f}%) {bar}")

            # For multi-pass, show per-pass picks
            if passes > 1:
                for p in range(passes):
                    pass_picks = Counter()
                    for r in vresults:
                        if len(r["picks"]) > p and r["picks"][p]:
                            pass_picks[r["picks"][p]] += 1
                    pt = sum(pass_picks.values())
                    if pt:
                        parts = [f"{l}={pass_picks.get(l,0)}" for l in ("A","B","AB")]
                        print(f"    Pass {p+1}: {', '.join(parts)}")


if __name__ == "__main__":
    asyncio.run(main())
