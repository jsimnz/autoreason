#!/usr/bin/env python3
"""
Run compute-matched baselines: critique_and_revise at 90 passes.

Autoreason uses ~6 calls/pass × 15 passes = 90 calls.
Baselines use 1 call/pass × 15 passes = 15 calls.
This runs baselines at 90 passes to match the compute budget.
"""

import asyncio
import json
import os
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

load_dotenv("/workspace/.hermes-state/.env")

import litellm
litellm.suppress_debug_info = True

AUTHOR_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Avoid generic advice. "
    "Tailor everything to the constraints stated in the task."
)

CRITIQUE_AND_REVISE_PROMPT = """Here is a proposal you produced:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

Review this proposal critically. Find real problems — things that won't work as described, complexity that doesn't pay for itself, assumptions that are wrong, missing pieces that block the design.

Then revise the proposal to fix every problem you found. For each change, state which problem it addresses. Produce the complete revised proposal."""


async def call_llm(system, user, model, temperature, max_tokens, max_retries=5):
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
                await asyncio.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Failed after {max_retries} retries")


async def run_task(task_num, num_passes, model, temp, max_tok):
    root = Path(__file__).parent
    tasks_dir = root.parent.parent / "tasks"
    
    task_file = tasks_dir / f"task_{task_num:02d}.md"
    task_prompt = task_file.read_text().strip()
    
    # Get initial version — check multiple locations
    initial_file = None
    for candidate in [
        root / "results_v2" / f"task_{task_num:02d}" / "initial_a.md",
        root / "results_v1_lite" / f"task_{task_num:02d}" / "initial_a.md",
        root / "results_v1_comparison" / f"task_{task_num:02d}" / "initial_a.md",
        root / "results_multi_task" / f"task_{task_num:02d}" / "autoreason" / "initial_a.md",
    ]:
        if candidate.exists():
            initial_file = candidate
            break
    
    if not initial_file:
        print(f"  No initial version found for task {task_num}, skipping")
        return None
    
    initial_version = initial_file.read_text()
    print(f"  Using initial from: {initial_file.relative_to(root)}")
    
    out_dir = root / "results_compute_matched" / f"task_{task_num:02d}" / "critique_and_revise_90"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Resume from existing passes
    existing = sorted(out_dir.glob("pass_*.md"))
    if existing:
        last_pass = int(existing[-1].stem.split("_")[1])
        current_version = existing[-1].read_text()
        start_pass = last_pass + 1
        word_counts = []
        for f in sorted(out_dir.glob("pass_*.md")):
            word_counts.append(len(f.read_text().split()))
        print(f"  Resuming from pass {last_pass}")
    else:
        current_version = initial_version
        start_pass = 1
        word_counts = [len(initial_version.split())]
        (out_dir / "pass_00_initial.md").write_text(initial_version)
    
    for pass_num in range(start_pass, num_passes + 1):
        print(f"  Pass {pass_num}/{num_passes}...", end=" ", flush=True)
        
        t0 = time.time()
        revised = await call_llm(
            AUTHOR_SYSTEM,
            CRITIQUE_AND_REVISE_PROMPT.format(
                current_version=current_version,
                task_prompt=task_prompt,
            ),
            model, temp, max_tok
        )
        elapsed = time.time() - t0
        
        (out_dir / f"pass_{pass_num:02d}.md").write_text(revised)
        wc = len(revised.split())
        word_counts.append(wc)
        print(f"Done ({elapsed:.0f}s, {wc} words)")
        
        current_version = revised
    
    (out_dir / "final_output.md").write_text(current_version)
    summary = {
        "task": task_num,
        "baseline": "critique_and_revise",
        "num_passes": num_passes,
        "model": model,
        "temperature": temp,
        "word_counts": word_counts,
        "final_words": word_counts[-1],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    
    return current_version


async def main():
    model = "anthropic/claude-sonnet-4-20250514"
    temp = 0.8
    max_tok = 4096
    num_passes = 90
    
    print(f"=== Compute-Matched Baselines ===")
    print(f"Strategy: critique_and_revise at {num_passes} passes")
    print(f"Model: {model}")
    print()
    
    for task_num in range(1, 6):
        print(f"\n{'━' * 60}")
        print(f"Task {task_num}")
        print(f"{'━' * 60}")
        await run_task(task_num, num_passes, model, temp, max_tok)
    
    print(f"\n{'━' * 60}")
    print("All tasks complete.")


if __name__ == "__main__":
    asyncio.run(main())
