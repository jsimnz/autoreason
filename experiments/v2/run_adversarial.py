#!/usr/bin/env python3
"""
Pure adversarial iteration baseline.

Same starting point as autoreason v2, but uses a single agent that
critiques and revises in a loop — no A/B/AB structure, no independent judge,
no fresh agents. This is what most people do when they ask an LLM to
"find problems and fix them" iteratively.

Usage:
    python run_adversarial.py --passes 15
    python run_adversarial.py --passes 15 --dry-run
"""

import argparse
import asyncio
import json
import os
import shutil
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

import yaml

# ---------------------------------------------------------------------------
# Prompts — single agent does everything (the standard approach)
# ---------------------------------------------------------------------------

AUTHOR_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Avoid generic advice. "
    "Tailor everything to the constraints stated in the task."
)

CRITIQUE_AND_REVISE = """Here is a proposal you produced:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

Review this proposal critically. Find real problems — things that won't work as described, complexity that doesn't pay for itself, assumptions that are wrong, missing pieces that block the design.

Then revise the proposal to fix every problem you found. For each change, state which problem it addresses. Produce the complete revised proposal."""


# ---------------------------------------------------------------------------
# LLM call wrapper
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="Pure adversarial iteration baseline")
    parser.add_argument("--passes", type=int, default=15)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).parent
    config = yaml.safe_load((root / "config_v2.yaml").read_text())
    
    model = config["author_model"]
    temp = config["author_temperature"]
    max_tok = config["max_tokens"]

    # Use the same initial A as the autoreason experiment
    initial_a_path = root / "results_v2" / "task_01" / "initial_a.md"
    if not initial_a_path.exists():
        print(f"Error: {initial_a_path} not found")
        sys.exit(1)

    task_path = root.parent.parent / "tasks" / "task_01.md"
    if not task_path.exists():
        task_path = root.parent / "tasks" / "task_01.md"
    if not task_path.exists():
        # Try from repo root
        for p in [Path("/root/autoreason-experiment/tasks/task_01.md")]:
            if p.exists():
                task_path = p
                break

    task_prompt = task_path.read_text().strip()
    current_version = initial_a_path.read_text()

    out_dir = root / "results_adversarial" / "task_01"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save initial
    (out_dir / "pass_00_initial.md").write_text(current_version)

    print(f"Pure adversarial iteration: {args.passes} passes")
    print(f"Model: {model} (temp={temp})")
    print(f"Starting from: {initial_a_path}")
    print()

    for pass_num in range(1, args.passes + 1):
        print(f"  Pass {pass_num}/{args.passes}...")
        
        if args.dry_run:
            print(f"    [DRY RUN] Would make 1 LLM call")
            continue

        t0 = time.time()
        revised = await call_llm(
            AUTHOR_SYSTEM,
            CRITIQUE_AND_REVISE.format(
                current_version=current_version,
                task_prompt=task_prompt,
            ),
            model, temp, max_tok
        )
        elapsed = time.time() - t0

        (out_dir / f"pass_{pass_num:02d}.md").write_text(revised)
        
        wc = len(revised.split())
        print(f"    Done ({elapsed:.0f}s, {wc} words)")

        current_version = revised

    if not args.dry_run:
        # Save final
        (out_dir / "final_output.md").write_text(current_version)
        print(f"\nFinal output: {out_dir / 'final_output.md'}")
        print(f"Word count: {len(current_version.split())}")


if __name__ == "__main__":
    asyncio.run(main())
