#!/usr/bin/env python3
"""
Autoreason experiment runner.

Runs N autoreason cycles per task, saves all intermediate artifacts,
and produces a summary TSV.

Usage:
    python run.py                     # run all tasks, all trials
    python run.py --task 1            # run task 1 only
    python run.py --task 1 --runs 3   # run 3 trials on task 1 (sanity check)
    python run.py --dry-run           # print what would run without calling LLM
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Load env from .hermes/.env so we get ANTHROPIC_API_KEY
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

# Suppress litellm noise
litellm.suppress_debug_info = True

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

AUTHOR_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Avoid generic advice. "
    "Tailor everything to the constraints stated in the task."
)

JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no authorship stake in any "
    "version. You have no preference between versions. Pick whichever version "
    "best solves the original problem."
)

STEP1_USER = "{task_prompt}\n\nProduce a complete, detailed proposal."

STEP2_USER = """Here is a proposal:

---
{version_a}
---

Find real problems with this proposal. Focus on:
- Things that won't work as described
- Complexity that doesn't pay for itself
- Assumptions that are wrong
- Missing pieces that block the design

Do NOT propose fixes. Just the problems."""

STEP3_USER = """Here is a proposal and the problems identified with it.

ORIGINAL PROPOSAL:
---
{version_a}
---

PROBLEMS FOUND:
---
{strawman}
---

Revise the proposal to address these problems.
For each change, state which problem it fixes.
Do not make changes that aren't motivated by an identified problem."""

STEP4_USER = """Here are two versions of a proposal.

VERSION A (original):
---
{version_a}
---

VERSION B (revised):
---
{version_b}
---

Produce VERSION AB — a synthesis that keeps the correct pieces from
both versions. This is not a compromise or average. Take the best
answer per dimension and make them cohere. Every departure from
Version A must be justified."""

STEP5_USER = """ORIGINAL TASK:
---
{task_prompt}
---

Three proposals have been produced independently. Evaluate all three.

{judge_proposals}

For each proposal, state what it gets right and what it gets wrong.
Then pick one. Respond in this exact format at the end:

WINNER: [1, 2, or 3]
REASONING: [your explanation]"""


# ---------------------------------------------------------------------------
# LLM call wrapper
# ---------------------------------------------------------------------------

async def call_llm(system, user, model, temperature, max_tokens, max_retries=3):
    """Make a single LLM call with retry on rate limit."""
    import asyncio as _asyncio
    for attempt in range(max_retries):
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "429" in err or "overloaded" in err:
                wait = (2 ** attempt) * 5
                print(f"    [Rate limited, retrying in {wait}s...]")
                await _asyncio.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Failed after {max_retries} retries")


def randomize_for_judge(version_a, version_b, version_ab):
    """Randomize presentation order and return (formatted_text, order_map).

    order_map maps position (1,2,3) back to original label (A, B, AB).
    """
    import random as _random
    versions = [("A", version_a), ("B", version_b), ("AB", version_ab)]
    _random.shuffle(versions)
    order_map = {}
    parts = []
    for i, (label, content) in enumerate(versions, 1):
        order_map[str(i)] = label
        parts.append(f"PROPOSAL {i}:\n---\n{content}\n---")
    return "\n\n".join(parts), order_map


def parse_judgment(text, order_map):
    """Extract WINNER from judge response and map back to original label."""
    pick_num = None
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip()
        if line.upper().startswith("WINNER:"):
            raw = line.split(":", 1)[1].strip()
            raw = raw.strip("*").strip()
            # Extract just the number
            for char in raw:
                if char in ("1", "2", "3"):
                    pick_num = char
                    break
            break
    if pick_num and pick_num in order_map:
        return order_map[pick_num], pick_num
    return None, pick_num


# ---------------------------------------------------------------------------
# Single autoreason run
# ---------------------------------------------------------------------------

async def run_autoreason(task_prompt, run_dir, config, dry_run=False):
    """Execute one full autoreason cycle, save all artifacts."""
    model = config["author_model"]
    temp = config["author_temperature"]
    jmodel = config["judge_model"]
    jtemp = config["judge_temperature"]
    max_tok = config["max_tokens"]

    run_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing results (resume support)
    judge_file = run_dir / "judge.json"
    if judge_file.exists():
        existing = json.loads(judge_file.read_text())
        if existing.get("pick"):
            print(f"  ↳ Skipping (already complete: {existing['pick']})")
            return existing["pick"]

    if dry_run:
        print(f"  ↳ [DRY RUN] Would run 5 LLM calls")
        return "DRY"

    t0 = time.time()

    # Step 1: Version A
    version_a = await call_llm(AUTHOR_SYSTEM, STEP1_USER.format(task_prompt=task_prompt), model, temp, max_tok)
    (run_dir / "version_a.md").write_text(version_a)

    # Step 2: Strawman
    strawman = await call_llm(AUTHOR_SYSTEM, STEP2_USER.format(version_a=version_a), model, temp, max_tok)
    (run_dir / "strawman.md").write_text(strawman)

    # Step 3: Version B
    version_b = await call_llm(AUTHOR_SYSTEM, STEP3_USER.format(version_a=version_a, strawman=strawman), model, temp, max_tok)
    (run_dir / "version_b.md").write_text(version_b)

    # Step 4: Version AB
    version_ab = await call_llm(AUTHOR_SYSTEM, STEP4_USER.format(version_a=version_a, version_b=version_b), model, temp, max_tok)
    (run_dir / "version_ab.md").write_text(version_ab)

    # Step 5: Judge (FRESH CONTEXT — different system prompt, no history)
    # Randomize presentation order to eliminate positional bias
    judge_proposals, order_map = randomize_for_judge(version_a, version_b, version_ab)
    judgment = await call_llm(JUDGE_SYSTEM, STEP5_USER.format(
        task_prompt=task_prompt,
        judge_proposals=judge_proposals,
    ), jmodel, jtemp, max_tok)

    pick, pick_num = parse_judgment(judgment, order_map)
    elapsed = time.time() - t0

    result = {
        "pick": pick,
        "pick_position": pick_num,
        "presentation_order": order_map,
        "raw_judgment": judgment,
        "author_model": model,
        "judge_model": jmodel,
        "author_temperature": temp,
        "judge_temperature": jtemp,
        "elapsed_seconds": round(elapsed, 1),
    }
    (run_dir / "judge.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

    pick_display = pick or "PARSE_ERROR"
    print(f"  ↳ Judge picked: {pick_display} (pos={pick_num}, order={list(order_map.values())}, {elapsed:.0f}s)")
    return pick


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_tasks(tasks_dir):
    """Load task prompts from tasks/ directory."""
    tasks = []
    for f in sorted(tasks_dir.glob("task_*.md")):
        tasks.append((f.stem, f.read_text().strip()))
    return tasks


async def main():
    parser = argparse.ArgumentParser(description="Autoreason experiment runner")
    parser.add_argument("--task", type=int, help="Run only this task number (1-indexed)")
    parser.add_argument("--runs", type=int, help="Override number of runs per task")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without calling LLM")
    args = parser.parse_args()

    root = Path(__file__).parent
    config = yaml.safe_load((root / "config.yaml").read_text())

    if args.runs:
        config["runs_per_task"] = args.runs

    tasks = load_tasks(root / "tasks")
    if not tasks:
        print("No tasks found in tasks/")
        sys.exit(1)

    if args.task:
        if args.task < 1 or args.task > len(tasks):
            print(f"Task {args.task} out of range (1-{len(tasks)})")
            sys.exit(1)
        tasks = [tasks[args.task - 1]]

    results_dir = root / "results"
    runs_per_task = config["runs_per_task"]
    batch_size = config.get("batch_size", 5)

    total_runs = len(tasks) * runs_per_task
    total_calls = total_runs * 5
    print(f"Autoreason experiment: {len(tasks)} tasks × {runs_per_task} runs = {total_runs} trials ({total_calls} LLM calls)")
    print(f"Author: {config['author_model']} (temp={config['author_temperature']})")
    print(f"Judge:  {config['judge_model']} (temp={config['judge_temperature']})")
    print()

    summary_rows = []

    for task_name, task_prompt in tasks:
        task_num = task_name.replace("task_", "")
        print(f"━━━ Task {task_num}: {task_prompt[:80]}...")
        task_dir = results_dir / task_name

        for batch_start in range(0, runs_per_task, batch_size):
            batch_end = min(batch_start + batch_size, runs_per_task)
            batch = []
            run_indices = []

            for run_idx in range(batch_start, batch_end):
                run_dir = task_dir / f"run_{run_idx + 1:02d}"
                run_name = f"  Run {run_idx + 1:02d}/{runs_per_task}"
                print(run_name)
                batch.append(run_autoreason(task_prompt, run_dir, config, args.dry_run))
                run_indices.append(run_idx + 1)

            picks = await asyncio.gather(*batch, return_exceptions=True)

            for run_idx, pick in zip(run_indices, picks):
                if isinstance(pick, Exception):
                    print(f"  ↳ ERROR: {pick}")
                    pick = "ERROR"
                summary_rows.append({
                    "task": task_name,
                    "run": run_idx,
                    "pick": pick,
                })

        print()

    # Write summary TSV
    summary_file = root / "summary.tsv"
    with open(summary_file, "w") as f:
        f.write("task\trun\tpick\n")
        for row in summary_rows:
            f.write(f"{row['task']}\t{row['run']}\t{row['pick']}\n")

    print(f"Summary written to {summary_file}")

    # Quick stats
    if not args.dry_run:
        from collections import Counter
        picks = Counter(r["pick"] for r in summary_rows if r["pick"] not in ("DRY", "ERROR", None))
        total = sum(picks.values())
        if total:
            print(f"\nOverall judge picks (n={total}):")
            for label in ("A", "B", "AB"):
                count = picks.get(label, 0)
                pct = count / total * 100
                print(f"  {label}: {count} ({pct:.0f}%)")


if __name__ == "__main__":
    asyncio.run(main())
