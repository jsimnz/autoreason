#!/usr/bin/env python3
"""
Analyze autoreason experiment results.

Produces:
- Per-task judge pick distributions
- Overall statistics
- Blind evaluation pairs for human raters
- stats.md summary

Usage:
    python analyze.py                # full analysis
    python analyze.py --blind 5      # generate 5 blind pairs per task
"""

import argparse
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path


def load_results(results_dir):
    """Load all judge.json files into a flat list."""
    rows = []
    for task_dir in sorted(results_dir.iterdir()):
        if not task_dir.is_dir() or not task_dir.name.startswith("task_"):
            continue
        for run_dir in sorted(task_dir.iterdir()):
            if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                continue
            judge_file = run_dir / "judge.json"
            if not judge_file.exists():
                continue
            data = json.loads(judge_file.read_text())
            rows.append({
                "task": task_dir.name,
                "run": run_dir.name,
                "run_dir": run_dir,
                "pick": data.get("pick"),
                "elapsed": data.get("elapsed_seconds"),
                "reasoning": data.get("raw_judgment", ""),
            })
    return rows


def print_stats(rows):
    """Print per-task and overall statistics."""
    tasks = sorted(set(r["task"] for r in rows))

    print("=" * 60)
    print("AUTOREASON EXPERIMENT RESULTS")
    print("=" * 60)
    print()

    overall = Counter()
    task_stats = {}

    for task in tasks:
        task_rows = [r for r in rows if r["task"] == task]
        picks = Counter(r["pick"] for r in task_rows if r["pick"])
        total = sum(picks.values())
        task_stats[task] = {"picks": picks, "total": total}
        overall.update(picks)

        print(f"━━━ {task} (n={total})")
        for label in ("A", "B", "AB"):
            count = picks.get(label, 0)
            pct = count / total * 100 if total else 0
            bar = "█" * int(pct / 2)
            print(f"  {label:>2}: {count:3d} ({pct:5.1f}%) {bar}")

        errors = sum(1 for r in task_rows if not r["pick"])
        if errors:
            print(f"  Parse errors: {errors}")

        times = [r["elapsed"] for r in task_rows if r.get("elapsed")]
        if times:
            print(f"  Time: {min(times):.0f}s - {max(times):.0f}s (median {sorted(times)[len(times)//2]:.0f}s)")
        print()

    # Overall
    total = sum(overall.values())
    print(f"━━━ OVERALL (n={total})")
    for label in ("A", "B", "AB"):
        count = overall.get(label, 0)
        pct = count / total * 100 if total else 0
        bar = "█" * int(pct / 2)
        print(f"  {label:>2}: {count:3d} ({pct:5.1f}%) {bar}")
    print()

    # Key diagnostics
    a_pct = overall.get("A", 0) / total * 100 if total else 0
    if a_pct < 10:
        print("⚠  Judge picks A < 10% — possible compliance bias. Investigate if B/AB are genuinely better or just different.")
    elif a_pct > 40:
        print("⚠  Judge picks A > 40% — revisions may not be adding value. Check if strawman is finding real problems.")
    else:
        print(f"✓  Judge picks A {a_pct:.0f}% of the time — fitness function appears to have real selection pressure.")
    print()

    return task_stats


def generate_blind_pairs(rows, eval_dir, n_per_task=5):
    """Generate blind evaluation pairs for human raters."""
    blind_dir = eval_dir / "blind_pairs"
    blind_dir.mkdir(parents=True, exist_ok=True)

    # Clean existing
    for f in blind_dir.glob("*.md"):
        f.unlink()

    tasks = sorted(set(r["task"] for r in rows))
    manifest = []

    for task in tasks:
        task_rows = [r for r in rows if r["task"] == task and r["pick"]]
        if not task_rows:
            continue

        sampled = random.sample(task_rows, min(n_per_task, len(task_rows)))

        for i, row in enumerate(sampled, 1):
            run_dir = row["run_dir"]
            version_a = (run_dir / "version_a.md").read_text()

            # Load the judge's pick
            pick = row["pick"]
            if pick == "A":
                winner = version_a
            elif pick == "B":
                winner = (run_dir / "version_b.md").read_text()
            elif pick == "AB":
                winner = (run_dir / "version_ab.md").read_text()
            else:
                continue

            # Randomly assign X/Y labels
            if random.random() < 0.5:
                prop_x, prop_y = version_a, winner
                key = {"X": "A_original", "Y": f"{pick}_reviewed"}
            else:
                prop_x, prop_y = winner, version_a
                key = {"X": f"{pick}_reviewed", "Y": "A_original"}

            # Load task prompt
            task_file = Path(__file__).parent / "tasks" / f"{row['task']}.md"
            task_prompt = task_file.read_text().strip() if task_file.exists() else "(task prompt not found)"

            pair_id = f"{row['task']}_pair_{i:02d}"
            pair_file = blind_dir / f"{pair_id}.md"

            pair_file.write_text(f"""# Blind Evaluation: {pair_id}

## Task
{task_prompt}

---

## Proposal X

{prop_x}

---

## Proposal Y

{prop_y}
""")

            manifest.append({
                "pair_id": pair_id,
                "task": row["task"],
                "run": row["run"],
                "label_x": key["X"],
                "label_y": key["Y"],
            })

    # Write manifest (answer key — don't share with raters)
    manifest_file = eval_dir / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2))

    print(f"Generated {len(manifest)} blind pairs in {blind_dir}/")
    print(f"Answer key: {manifest_file} (do not share with raters)")


def write_stats_md(rows, task_stats, output_path):
    """Write a human-readable stats.md."""
    total = sum(sum(ts["picks"].values()) for ts in task_stats.values())
    overall = Counter()
    for ts in task_stats.values():
        overall.update(ts["picks"])

    lines = ["# Autoreason Experiment Results\n"]
    lines.append(f"Total runs: {total}\n")

    lines.append("## Overall Pick Distribution\n")
    lines.append("| Version | Count | Percentage |")
    lines.append("|---------|-------|------------|")
    for label in ("A", "B", "AB"):
        count = overall.get(label, 0)
        pct = count / total * 100 if total else 0
        lines.append(f"| {label} | {count} | {pct:.1f}% |")

    lines.append("\n## Per-Task Breakdown\n")
    for task, ts in sorted(task_stats.items()):
        t = ts["total"]
        lines.append(f"### {task} (n={t})\n")
        lines.append("| Version | Count | Percentage |")
        lines.append("|---------|-------|------------|")
        for label in ("A", "B", "AB"):
            count = ts["picks"].get(label, 0)
            pct = count / t * 100 if t else 0
            lines.append(f"| {label} | {count} | {pct:.1f}% |")
        lines.append("")

    output_path.write_text("\n".join(lines))
    print(f"Stats written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Analyze autoreason experiment results")
    parser.add_argument("--blind", type=int, default=5, help="Number of blind pairs per task (default: 5)")
    args = parser.parse_args()

    root = Path(__file__).parent
    results_dir = root / "results"

    if not results_dir.exists():
        print("No results directory found. Run run.py first.")
        sys.exit(1)

    rows = load_results(results_dir)
    if not rows:
        print("No results found.")
        sys.exit(1)

    task_stats = print_stats(rows)
    generate_blind_pairs(rows, root / "evaluation", n_per_task=args.blind)
    write_stats_md(rows, task_stats, root / "stats.md")


if __name__ == "__main__":
    main()
