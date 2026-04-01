#!/usr/bin/env python3
"""
Analyze and visualize degradation trajectories for Haiku baselines.
Uses existing data — no new API calls needed.

Produces a JSON dataset suitable for plotting:
  - Word count at each pass for each baseline
  - Quality score (from intermediate judge evals if available, or word count as proxy)
"""

import json
from pathlib import Path

def count_words(path):
    if path.exists():
        return len(path.read_text().split())
    return None

def main():
    root = Path(__file__).parent
    bl_dir = root / "results_small_model_baselines_haiku35"

    results = {}
    for task_name in ["pitch", "policy", "gtm"]:
        task_dir = bl_dir / task_name
        if not task_dir.exists():
            continue

        task_results = {}

        # Initial A
        init = task_dir / "initial_a.md"
        init_words = count_words(init) if init.exists() else None

        for baseline in ["improve_this", "critique_and_revise", "conservative", "harsh_critic"]:
            bdir = task_dir / baseline
            if not bdir.exists():
                continue

            # Check for intermediate outputs
            trajectory = []
            if init_words:
                trajectory.append({"pass": 0, "words": init_words, "label": "initial"})

            # The baselines save final_output.md but not intermediates
            # Check if there are pass files
            for p in range(1, 16):
                pf = bdir / f"pass_{p:02d}.md"
                if not pf.exists():
                    pf = bdir / f"pass_{p}.md"
                if pf.exists():
                    trajectory.append({"pass": p, "words": count_words(pf)})

            final = bdir / "final_output.md"
            if final.exists():
                final_words = count_words(final)
                if not trajectory or trajectory[-1].get("pass") != 15:
                    trajectory.append({"pass": 15, "words": final_words, "label": "final"})

            task_results[baseline] = {
                "initial_words": init_words,
                "final_words": count_words(final) if final.exists() else None,
                "trajectory": trajectory,
            }

        # Also get autoreason trajectory
        svb_ar = root / "results_small_vs_big" / task_name / "haiku35_autoreason"
        ar_hist = svb_ar / "history.json"
        if ar_hist.exists():
            hist = json.loads(ar_hist.read_text())
            ar_traj = [{"pass": h["pass"], "words": h.get("words", 0), "winner": h["winner"]} for h in hist]
            ar_init = svb_ar / "initial_a.md"
            task_results["autoreason"] = {
                "initial_words": count_words(ar_init) if ar_init.exists() else None,
                "final_words": count_words(svb_ar / "final_output.md"),
                "trajectory": ar_traj,
            }

        results[task_name] = task_results

    # Print summary
    print("DEGRADATION ANALYSIS")
    print("=" * 60)
    for task_name, task_data in results.items():
        print(f"\n  {task_name}:")
        print(f"  {'Method':<25} {'Initial':>8} {'Final':>8} {'Change':>8}")
        print(f"  {'-'*50}")
        for method, data in task_data.items():
            init = data.get("initial_words", "?")
            final = data.get("final_words", "?")
            if isinstance(init, int) and isinstance(final, int):
                change = f"{final - init:+d}"
                pct = f"({(final-init)/init*100:+.0f}%)"
            else:
                change = "?"
                pct = ""
            print(f"  {method:<25} {str(init):>8} {str(final):>8} {change:>8} {pct}")

    # Save for plotting
    output_file = root / "results_degradation_analysis.json"
    output_file.write_text(json.dumps(results, indent=2))
    print(f"\nSaved to {output_file}")

    # Generate a text-based "chart" for the paper
    print("\n\nTEXT CHART: Word Count Trajectories (Haiku 3.5)")
    print("=" * 60)
    for task_name, task_data in results.items():
        print(f"\n  {task_name}:")
        for method, data in task_data.items():
            init = data.get("initial_words", 0) or 0
            final = data.get("final_words", 0) or 0
            bar_init = "█" * (init // 20)
            bar_final = "█" * (final // 20)
            print(f"    {method:<20} init: {bar_init} ({init}w)")
            print(f"    {'':20} final: {bar_final} ({final}w)")


if __name__ == "__main__":
    main()
