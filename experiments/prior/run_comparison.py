#!/usr/bin/env python3
"""
Autoreason vs Adversarial vs Objective comparison experiment.

Three conditions on the same tasks, 5 runs each.
- Autoreason: A → strawman → B → AB → blind judge. Stop on 2 consecutive A picks. Max 7 passes.
- Adversarial: "Find problems and fix them." Iterative, same agent. Matched pass count.
- Objective: "Find problems but be honest — decline if none." Iterative. Stops on decline or matched count.

Usage:
    python run_comparison.py                    # run all
    python run_comparison.py --condition autoreason  # one condition
    python run_comparison.py --dry-run
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

sys.path.insert(0, str(Path(__file__).parent))
from run import (
    AUTHOR_SYSTEM, JUDGE_SYSTEM,
    STEP1_USER, STEP2_USER, STEP3_USER, STEP4_USER, STEP5_USER,
    call_llm, randomize_for_judge, parse_judgment,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MODEL = "anthropic/claude-sonnet-4-20250514"
AUTHOR_TEMP = 1.0
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
MAX_PASSES = 7
STOP_CONSECUTIVE_A = 2
RUNS_PER_CONDITION = 5
TASKS = [1, 4]
BATCH_SIZE = 5

# ---------------------------------------------------------------------------
# Condition: Autoreason
# ---------------------------------------------------------------------------

ADVERSARIAL_PROMPT = """Here is a proposal:

---
{current}
---

Find the problems with this proposal and fix them. Produce a complete revised version."""

OBJECTIVE_PROMPT = """Here is a proposal:

---
{current}
---

Review this proposal critically but objectively. If there are real problems, identify them and produce a revised version. If the proposal is already strong and you don't see meaningful improvements to make, say "NO CHANGES NEEDED" on the first line and explain why the proposal is solid as-is. Do not make changes just for the sake of changing things."""


async def run_autoreason_chain(task_prompt, run_dir, dry_run=False):
    """Run autoreason passes until 2 consecutive A picks or max passes."""
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_file = run_dir / "summary.json"
    if summary_file.exists():
        existing = json.loads(summary_file.read_text())
        if existing.get("complete"):
            print(f"      ↳ Skipping (already complete)")
            return existing

    if dry_run:
        print(f"      ↳ [DRY RUN] autoreason, up to {MAX_PASSES} passes")
        return {"condition": "autoreason", "passes": 0, "picks": [], "complete": True}

    t0 = time.time()

    # Generate initial A
    version_a = await call_llm(AUTHOR_SYSTEM, STEP1_USER.format(task_prompt=task_prompt),
                                MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (run_dir / "pass_0_version_a.md").write_text(version_a)

    current_a = version_a
    picks = []
    consecutive_a = 0

    for pass_idx in range(MAX_PASSES):
        prefix = f"pass_{pass_idx + 1}"

        # Strawman
        strawman = await call_llm(AUTHOR_SYSTEM, STEP2_USER.format(version_a=current_a),
                                   MODEL, AUTHOR_TEMP, MAX_TOKENS)
        (run_dir / f"{prefix}_strawman.md").write_text(strawman)

        # Version B
        version_b = await call_llm(AUTHOR_SYSTEM, STEP3_USER.format(version_a=current_a, strawman=strawman),
                                    MODEL, AUTHOR_TEMP, MAX_TOKENS)
        (run_dir / f"{prefix}_version_b.md").write_text(version_b)

        # Version AB
        version_ab = await call_llm(AUTHOR_SYSTEM, STEP4_USER.format(version_a=current_a, version_b=version_b),
                                     MODEL, AUTHOR_TEMP, MAX_TOKENS)
        (run_dir / f"{prefix}_version_ab.md").write_text(version_ab)

        # Judge (blind, randomized)
        judge_proposals, order_map = randomize_for_judge(current_a, version_b, version_ab)
        judgment = await call_llm(JUDGE_SYSTEM,
                                   STEP5_USER.format(task_prompt=task_prompt, judge_proposals=judge_proposals),
                                   MODEL, JUDGE_TEMP, MAX_TOKENS)
        pick, pick_num = parse_judgment(judgment, order_map)

        (run_dir / f"{prefix}_judge.json").write_text(json.dumps({
            "pick": pick, "pick_position": pick_num,
            "presentation_order": order_map, "raw_judgment": judgment,
        }, indent=2, ensure_ascii=False))

        picks.append(pick)
        pick_display = pick or "?"
        print(f"      ↳ Pass {pass_idx + 1}: {pick_display}")

        if pick == "A":
            consecutive_a += 1
            if consecutive_a >= STOP_CONSECUTIVE_A:
                print(f"      ↳ Stopped: {STOP_CONSECUTIVE_A} consecutive A picks")
                break
        else:
            consecutive_a = 0
            if pick == "B":
                current_a = version_b
            elif pick == "AB":
                current_a = version_ab
            # else parse error, keep current_a

    (run_dir / "final_output.md").write_text(current_a)
    elapsed = time.time() - t0

    summary = {
        "condition": "autoreason",
        "passes": len(picks),
        "picks": picks,
        "stopped_reason": "consecutive_a" if consecutive_a >= STOP_CONSECUTIVE_A else "max_passes",
        "elapsed_seconds": round(elapsed, 1),
        "complete": True,
    }
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


async def run_adversarial_chain(task_prompt, run_dir, max_passes, dry_run=False):
    """Run adversarial review for a fixed number of passes."""
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_file = run_dir / "summary.json"
    if summary_file.exists():
        existing = json.loads(summary_file.read_text())
        if existing.get("complete"):
            print(f"      ↳ Skipping (already complete)")
            return existing

    if dry_run:
        print(f"      ↳ [DRY RUN] adversarial, {max_passes} passes")
        return {"condition": "adversarial", "passes": 0, "complete": True}

    t0 = time.time()

    # Generate initial A
    current = await call_llm(AUTHOR_SYSTEM, STEP1_USER.format(task_prompt=task_prompt),
                              MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (run_dir / "pass_0_version_a.md").write_text(current)

    for pass_idx in range(max_passes):
        prefix = f"pass_{pass_idx + 1}"

        revised = await call_llm(AUTHOR_SYSTEM,
                                  ADVERSARIAL_PROMPT.format(current=current),
                                  MODEL, AUTHOR_TEMP, MAX_TOKENS)
        (run_dir / f"{prefix}_revised.md").write_text(revised)
        current = revised
        print(f"      ↳ Pass {pass_idx + 1}: revised")

    (run_dir / "final_output.md").write_text(current)
    elapsed = time.time() - t0

    summary = {
        "condition": "adversarial",
        "passes": max_passes,
        "elapsed_seconds": round(elapsed, 1),
        "complete": True,
    }
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


async def run_objective_chain(task_prompt, run_dir, max_passes, dry_run=False):
    """Run objective review — agent can decline to make changes."""
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_file = run_dir / "summary.json"
    if summary_file.exists():
        existing = json.loads(summary_file.read_text())
        if existing.get("complete"):
            print(f"      ↳ Skipping (already complete)")
            return existing

    if dry_run:
        print(f"      ↳ [DRY RUN] objective, up to {max_passes} passes")
        return {"condition": "objective", "passes": 0, "declined_at": None, "complete": True}

    t0 = time.time()

    # Generate initial A
    current = await call_llm(AUTHOR_SYSTEM, STEP1_USER.format(task_prompt=task_prompt),
                              MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (run_dir / "pass_0_version_a.md").write_text(current)

    declined_at = None
    actual_passes = 0

    for pass_idx in range(max_passes):
        prefix = f"pass_{pass_idx + 1}"

        response = await call_llm(AUTHOR_SYSTEM,
                                   OBJECTIVE_PROMPT.format(current=current),
                                   MODEL, AUTHOR_TEMP, MAX_TOKENS)
        (run_dir / f"{prefix}_response.md").write_text(response)
        actual_passes += 1

        # Check if agent declined
        first_line = response.strip().split("\n")[0].upper()
        if "NO CHANGES NEEDED" in first_line:
            print(f"      ↳ Pass {pass_idx + 1}: declined (no changes needed)")
            declined_at = pass_idx + 1
            break
        else:
            current = response
            print(f"      ↳ Pass {pass_idx + 1}: revised")

    (run_dir / "final_output.md").write_text(current)
    elapsed = time.time() - t0

    summary = {
        "condition": "objective",
        "passes": actual_passes,
        "declined_at": declined_at,
        "stopped_reason": "declined" if declined_at else "max_passes",
        "elapsed_seconds": round(elapsed, 1),
        "complete": True,
    }
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_tasks(tasks_dir, task_nums):
    tasks = []
    for n in task_nums:
        f = tasks_dir / f"task_{n:02d}.md"
        if f.exists():
            tasks.append((f.stem, f.read_text().strip()))
    return tasks


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=["autoreason", "adversarial", "objective"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).parent
    tasks = load_tasks(root / "tasks", TASKS)
    results_dir = root / "results_comparison"
    conditions = ["autoreason", "adversarial", "objective"]

    if args.condition:
        conditions = [args.condition]

    print(f"Comparison experiment: {len(conditions)} conditions × {len(tasks)} tasks × {RUNS_PER_CONDITION} runs")
    print(f"Model: {MODEL}, author_temp={AUTHOR_TEMP}, judge_temp={JUDGE_TEMP}")
    print(f"Max passes: {MAX_PASSES}, stop on {STOP_CONSECUTIVE_A} consecutive A picks")
    print()

    # Phase 1: Run autoreason first to get pass counts
    autoreason_passes = {}  # (task_name, run_idx) → pass_count

    if "autoreason" in conditions:
        print("══ Phase 1: Autoreason (determines pass counts for other conditions)")
        for task_name, task_prompt in tasks:
            print(f"  ━━ {task_name}")
            for run_idx in range(RUNS_PER_CONDITION):
                run_dir = results_dir / "autoreason" / task_name / f"run_{run_idx + 1:02d}"
                print(f"    Run {run_idx + 1}/{RUNS_PER_CONDITION}")
                result = await run_autoreason_chain(task_prompt, run_dir, args.dry_run)
                autoreason_passes[(task_name, run_idx)] = result.get("passes", MAX_PASSES)
        print()

    # Load autoreason pass counts if we skipped phase 1
    if not autoreason_passes:
        for task_name, _ in tasks:
            for run_idx in range(RUNS_PER_CONDITION):
                sf = results_dir / "autoreason" / task_name / f"run_{run_idx + 1:02d}" / "summary.json"
                if sf.exists():
                    data = json.loads(sf.read_text())
                    autoreason_passes[(task_name, run_idx)] = data.get("passes", MAX_PASSES)
                else:
                    autoreason_passes[(task_name, run_idx)] = MAX_PASSES

    # Phase 2: Run adversarial and objective with matched pass counts
    for condition in conditions:
        if condition == "autoreason":
            continue

        print(f"══ {condition.title()}")
        for task_name, task_prompt in tasks:
            print(f"  ━━ {task_name}")

            batch = []
            batch_meta = []

            for run_idx in range(RUNS_PER_CONDITION):
                pass_count = autoreason_passes.get((task_name, run_idx), MAX_PASSES)
                run_dir = results_dir / condition / task_name / f"run_{run_idx + 1:02d}"
                print(f"    Run {run_idx + 1}/{RUNS_PER_CONDITION} ({pass_count} passes)")

                if condition == "adversarial":
                    batch.append(run_adversarial_chain(task_prompt, run_dir, pass_count, args.dry_run))
                elif condition == "objective":
                    batch.append(run_objective_chain(task_prompt, run_dir, pass_count, args.dry_run))

                batch_meta.append((condition, task_name, run_idx))

                if len(batch) >= BATCH_SIZE:
                    await asyncio.gather(*batch, return_exceptions=True)
                    batch = []
                    batch_meta = []

            if batch:
                await asyncio.gather(*batch, return_exceptions=True)
        print()

    # Summary
    print("=" * 60)
    print("COMPARISON SUMMARY")
    print("=" * 60)

    for condition in ["autoreason", "adversarial", "objective"]:
        cond_dir = results_dir / condition
        if not cond_dir.exists():
            continue

        pass_counts = []
        declined = 0
        total = 0

        for sf in sorted(cond_dir.rglob("summary.json")):
            data = json.loads(sf.read_text())
            if data.get("complete"):
                total += 1
                pass_counts.append(data.get("passes", 0))
                if data.get("declined_at"):
                    declined += 1

        if not total:
            continue

        avg_passes = sum(pass_counts) / len(pass_counts) if pass_counts else 0
        print(f"\n{condition} (n={total}):")
        print(f"  Avg passes: {avg_passes:.1f}")
        print(f"  Pass range: {min(pass_counts)}-{max(pass_counts)}")

        if condition == "autoreason":
            # Show pick distribution
            all_picks = []
            for sf in sorted(cond_dir.rglob("summary.json")):
                data = json.loads(sf.read_text())
                all_picks.extend(data.get("picks", []))
            from collections import Counter
            pc = Counter(p for p in all_picks if p)
            pt = sum(pc.values())
            if pt:
                for l in ("A", "B", "AB"):
                    print(f"  {l}: {pc.get(l,0)} ({pc.get(l,0)/pt*100:.0f}%)")

            stops = Counter(json.loads(sf.read_text()).get("stopped_reason", "?")
                           for sf in sorted(cond_dir.rglob("summary.json")))
            print(f"  Stop reasons: {dict(stops)}")

        if condition == "objective":
            print(f"  Declined (said no changes needed): {declined}/{total}")


if __name__ == "__main__":
    asyncio.run(main())
