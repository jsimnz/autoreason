#!/usr/bin/env python3
"""
Run multiple iterative prompting baselines from the same starting point.

Each baseline uses a different prompting strategy but the same model,
temperature, and number of passes. All start from the same initial_a.md.

Usage:
    python run_baselines.py --passes 15
    python run_baselines.py --passes 15 --dry-run
    python run_baselines.py --passes 15 --baseline improve_this
"""

import argparse
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

load_dotenv(os.path.expanduser("~/.hermes/.env"))

import litellm
litellm.suppress_debug_info = True

import yaml

# ---------------------------------------------------------------------------
# Baseline definitions
# ---------------------------------------------------------------------------

AUTHOR_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Avoid generic advice. "
    "Tailor everything to the constraints stated in the task."
)

BASELINES = {
    "improve_this": {
        "description": "Pure sycophantic mode — just 'make it better'",
        "prompt": """Here is a proposal:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

Improve this proposal. Make it stronger, more compelling, and more thorough. Produce the complete improved proposal.""",
    },

    "critique_and_revise": {
        "description": "Single agent critiques then revises in one pass",
        "prompt": """Here is a proposal you produced:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

Review this proposal critically. Find real problems — things that won't work as described, complexity that doesn't pay for itself, assumptions that are wrong, missing pieces that block the design.

Then revise the proposal to fix every problem you found. For each change, state which problem it addresses. Produce the complete revised proposal.""",
    },

    "conservative": {
        "description": "Conservative mode — only change what's actually wrong",
        "prompt": """Here is a proposal:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

Review this proposal. Make changes only if something is genuinely wrong, unrealistic, or missing. If a section is already good, leave it as is. Do not add complexity or detail for its own sake. Do not rewrite sections that are already working.

If you believe the proposal is already strong and no changes are needed, return it unchanged.

Produce the complete proposal with any necessary changes.""",
    },

    "harsh_critic": {
        "description": "Maximum adversarial pressure — find every flaw",
        "prompt": """Here is a proposal:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

You are a harsh, uncompromising critic. Find every flaw in this proposal — every weak assumption, every unrealistic number, every gap, every piece of hand-waving. Nothing should survive scrutiny.

After identifying every problem, rewrite the proposal from scratch to address all of them. The revised version must be bulletproof. Produce the complete revised proposal.""",
    },
}


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
# Run a single baseline
# ---------------------------------------------------------------------------

async def run_baseline(name, config, task_prompt, initial_version, num_passes, out_dir, model, temp, max_tok, dry_run=False):
    baseline = BASELINES[name]
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'━' * 60}")
    print(f"Baseline: {name}")
    print(f"  {baseline['description']}")
    print(f"  {num_passes} passes, model={model}, temp={temp}")
    print(f"{'━' * 60}")

    (out_dir / "pass_00_initial.md").write_text(initial_version)
    current_version = initial_version
    word_counts = [len(initial_version.split())]

    for pass_num in range(1, num_passes + 1):
        print(f"  Pass {pass_num}/{num_passes}...", end=" ", flush=True)

        if dry_run:
            print("[DRY RUN]")
            continue

        t0 = time.time()
        revised = await call_llm(
            AUTHOR_SYSTEM,
            baseline["prompt"].format(
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

    if not dry_run:
        (out_dir / "final_output.md").write_text(current_version)
        summary = {
            "baseline": name,
            "description": baseline["description"],
            "num_passes": num_passes,
            "model": model,
            "temperature": temp,
            "word_counts": word_counts,
            "final_words": word_counts[-1],
        }
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        print(f"\n  Final: {word_counts[-1]} words")
        print(f"  Trajectory: {' → '.join(str(w) for w in word_counts)}")

    return current_version


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="Run iterative prompting baselines")
    parser.add_argument("--passes", type=int, default=15)
    parser.add_argument("--baseline", type=str, help="Run only this baseline")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).parent
    config = yaml.safe_load((root / "config_v2.yaml").read_text())

    model = config["author_model"]
    temp = config["author_temperature"]
    max_tok = config["max_tokens"]

    task_prompt = Path("/root/autoreason-experiment/tasks/task_01.md").read_text().strip()
    initial_version = (root / "results_v2" / "task_01" / "initial_a.md").read_text()

    baselines_to_run = [args.baseline] if args.baseline else list(BASELINES.keys())

    # Skip critique_and_revise if we already have the adversarial run
    adversarial_final = root / "results_adversarial" / "task_01" / "final_output.md"
    if "critique_and_revise" in baselines_to_run and adversarial_final.exists():
        print(f"Note: critique_and_revise already exists at {adversarial_final}")
        print(f"  Skipping (use --baseline critique_and_revise to force rerun)")
        baselines_to_run.remove("critique_and_revise")

    for name in baselines_to_run:
        if name not in BASELINES:
            print(f"Unknown baseline: {name}")
            print(f"Available: {', '.join(BASELINES.keys())}")
            sys.exit(1)

        out_dir = root / "results_baselines" / "task_01" / name
        await run_baseline(
            name, config, task_prompt, initial_version,
            args.passes, out_dir, model, temp, max_tok, args.dry_run
        )

    print(f"\n{'━' * 60}")
    print("All baselines complete.")


if __name__ == "__main__":
    asyncio.run(main())
