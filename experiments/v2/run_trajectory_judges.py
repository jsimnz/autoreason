#!/usr/bin/env python3
"""
Trajectory-history judges: evaluate outputs in context of their generation trajectory.

Instead of blind comparison of final outputs, judges see the trajectory of changes
(pass-by-pass summaries) and evaluate whether the trajectory-level quality matches
the per-pass judgments. Inspired by Meta-Harness's trajectory context approach.

This addresses the concern that per-pass judgments may not compose into trajectory-level quality.

We take existing trajectories and run two evaluation modes:
1. Standard blind: judge sees only final outputs (existing approach)
2. Trajectory-aware: judge sees final outputs + trajectory summary (pass winners, word counts, 
   what changed at each step)

If trajectory-aware judges produce different rankings, it suggests per-pass judgments
don't fully capture quality — a limitation worth documenting.
"""

import asyncio
import json
import os
import random
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
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
NUM_JUDGES = 7

COT_JUDGE_SYSTEM = "You are an independent evaluator. You have no authorship stake. Think carefully before deciding."

# Load task prompts
TASK_PROMPTS = {}
for i in range(1, 6):
    tp = Path(f"/workspace/autoreason/tasks/task_{i:02d}.md")
    if tp.exists():
        TASK_PROMPTS[i] = tp.read_text().strip()

# Standard blind judge prompt (control)
BLIND_JUDGE_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Three documents have been produced for this task using different improvement methods:

{proposals}

For each version, think step by step:
1. How well does it accomplish the task?
2. Is the content specific and actionable?
3. Is the level of detail appropriate?
4. Are claims defensible?

After reasoning, rank all three from best to worst:

RANKING: [best], [second], [worst]

Where each slot is A, B, or C."""

# Trajectory-aware judge prompt (experimental)
TRAJECTORY_JUDGE_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Three documents have been produced for this task using different improvement methods. 
You will see both the final output AND a summary of how it was produced.

{proposals_with_trajectory}

For each version, think step by step:
1. How well does the final output accomplish the task?
2. Does the improvement trajectory suggest genuine refinement or just churn/drift?
3. Is the final output's quality consistent with its trajectory?
4. Would you trust this output more or less knowing how it was produced?

After reasoning, rank all three from best to worst based on final output quality 
(trajectory context should inform but not override your quality judgment):

RANKING: [best], [second], [worst]

Where each slot is A, B, or C."""


async def call_llm(system, user, model=MODEL, temperature=0.3, max_tokens=MAX_TOKENS, max_retries=8):
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


def parse_ranking(text, valid_chars="ABC"):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            items = [c for c in raw.upper() if c in valid_chars]
            if len(items) >= 2:
                return items
    return None


def build_trajectory_summary(history, method_name):
    """Build a human-readable trajectory summary from history data."""
    if not history:
        return f"Method: {method_name}\nNo trajectory data available (single-pass method)."
    
    lines = [f"Method: {method_name}", f"Total passes: {len(history)}"]
    winners = [h["winner"] for h in history]
    lines.append(f"Winner sequence: {' → '.join(winners)}")
    
    word_counts = [h.get("words", "?") for h in history]
    lines.append(f"Word count trajectory: {' → '.join(str(w) for w in word_counts)}")
    
    a_wins = sum(1 for w in winners if w == "A")
    lines.append(f"Incumbent survived {a_wins}/{len(winners)} passes ({a_wins/len(winners)*100:.0f}%)")
    
    return "\n".join(lines)


async def run_comparison(task_num, methods, trajectories, out_dir, mode="blind"):
    """Run a judge panel comparison in blind or trajectory-aware mode."""
    out_dir.mkdir(parents=True, exist_ok=True)
    
    task_prompt = TASK_PROMPTS[task_num]
    method_names = list(methods.keys())
    labels = list("ABC")[:len(method_names)]
    
    judge_tasks = []
    judge_orders = []
    
    for _ in range(NUM_JUDGES):
        shuffled = method_names.copy()
        random.shuffle(shuffled)
        order = {labels[i]: shuffled[i] for i in range(len(method_names))}
        judge_orders.append(order)
        
        if mode == "blind":
            parts = [f"VERSION {labels[i]}:\n---\n{methods[order[labels[i]]]}\n---"
                     for i in range(len(method_names))]
            prompt = BLIND_JUDGE_PROMPT.format(
                task_prompt=task_prompt, proposals="\n\n".join(parts))
        else:  # trajectory-aware
            parts = []
            for i in range(len(method_names)):
                m = order[labels[i]]
                traj = trajectories.get(m, None)
                traj_summary = build_trajectory_summary(traj, "Method " + labels[i])
                parts.append(
                    f"VERSION {labels[i]}:\n"
                    f"[Trajectory]\n{traj_summary}\n\n"
                    f"[Final Output]\n---\n{methods[m]}\n---"
                )
            prompt = TRAJECTORY_JUDGE_PROMPT.format(
                task_prompt=task_prompt,
                proposals_with_trajectory="\n\n".join(parts))
        
        judge_tasks.append(call_llm(COT_JUDGE_SYSTEM, prompt, MODEL, JUDGE_TEMP, MAX_TOKENS))
    
    responses = await asyncio.gather(*judge_tasks, return_exceptions=True)
    
    borda = {n: 0 for n in method_names}
    first_place = {n: 0 for n in method_names}
    points = [3, 2, 1]
    valid = 0
    
    for j, (resp, order) in enumerate(zip(responses, judge_orders)):
        if isinstance(resp, Exception):
            print(f"    Judge {j+1}: ERROR - {resp}")
            continue
        ranking = parse_ranking(resp, "".join(labels))
        if not ranking:
            print(f"    Judge {j+1}: PARSE FAILED")
            (out_dir / f"judge_{j+1}_raw.txt").write_text(str(resp))
            continue
        valid += 1
        mapped = [order.get(l, l) for l in ranking[:len(method_names)]]
        for pos, method in enumerate(mapped):
            if method in borda and pos < len(points):
                borda[method] += points[pos]
        if mapped[0] in first_place:
            first_place[mapped[0]] += 1
        print(f"    Judge {j+1}: {' > '.join(mapped)}")
        (out_dir / f"judge_{j+1}_raw.txt").write_text(resp)
    
    results = {
        "mode": mode, "task": task_num, "valid_judges": valid,
        "borda": borda, "first_place": first_place,
        "word_counts": {n: len(methods[n].split()) for n in method_names},
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    return results


async def main():
    root = Path(__file__).parent
    out_dir = root / "results_trajectory_judges"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # For tasks 1 and 4, compare autoreason vs critique_and_revise vs harsh_critic
    # using both blind and trajectory-aware judges
    
    for task_num in [1, 4]:
        print(f"\n{'='*60}")
        print(f"Task {task_num}: Trajectory-Aware Judge Comparison")
        print(f"{'='*60}")
        
        # Load final outputs
        v1_dir = root / "results_v1_comparison" / f"task_{task_num:02d}"
        methods = {}
        
        ar_path = v1_dir / "v1_output.md"
        cr_path = v1_dir / "baseline_critique_and_revise.md"
        hc_path = v1_dir / "baseline_harsh_critic.md"
        
        if not all(p.exists() for p in [ar_path, cr_path, hc_path]):
            print(f"  Missing files for task {task_num}, skipping")
            continue
        
        methods = {
            "autoreason": ar_path.read_text(),
            "critique_revise": cr_path.read_text(),
            "harsh_critic": hc_path.read_text(),
        }
        
        # Load trajectory data
        trajectories = {}
        
        # Autoreason trajectory
        hist_candidates = [
            root / "results_multi_task" / f"task_{task_num:02d}" / "autoreason" / "history.json",
            root / "results_v2" / f"task_{task_num:02d}" / "history.json",
        ]
        for hc in hist_candidates:
            if hc.exists():
                trajectories["autoreason"] = json.loads(hc.read_text())
                break
        
        # Baselines don't have per-pass trajectory data, just mark as "15 single-agent passes"
        trajectories["critique_revise"] = [{"winner": "revised", "words": "?"} for _ in range(15)]
        trajectories["harsh_critic"] = [{"winner": "revised", "words": "?"} for _ in range(15)]
        
        # Mode 1: Blind (control)
        print(f"\n  --- Blind Mode (control) ---")
        blind_results = await run_comparison(
            task_num, methods, {}, 
            out_dir / f"task_{task_num:02d}_blind", mode="blind")
        
        # Mode 2: Trajectory-aware
        print(f"\n  --- Trajectory-Aware Mode ---")
        traj_results = await run_comparison(
            task_num, methods, trajectories,
            out_dir / f"task_{task_num:02d}_trajectory", mode="trajectory")
        
        # Compare
        print(f"\n  {'Method':<20} {'Blind':>8} {'Traj':>8} {'Delta':>8}")
        print(f"  {'-'*46}")
        for m in methods:
            b = blind_results["borda"].get(m, 0)
            t = traj_results["borda"].get(m, 0)
            d = t - b
            print(f"  {m:<20} {b:>8} {t:>8} {d:>+8}")
    
    print(f"\n{'='*60}")
    print("Done. Results in results_trajectory_judges/")


if __name__ == "__main__":
    asyncio.run(main())
