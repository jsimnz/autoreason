#!/usr/bin/env python3
"""
Blind comparison: autoreason pass 14-15 incumbent vs pass 24-25 incumbent.
Tests whether additional passes after first convergence point improve quality.
"""

import asyncio
import json
import os
import random
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

JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no prior knowledge of how "
    "either version was produced. Evaluate based solely on the content."
)

JUDGE_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

INITIAL OUTPUT (the starting point both versions were derived from):
---
{initial_output}
---

Two teams independently worked to improve the initial output. Here are their final versions:

{proposals}

Evaluate both final versions against the original task and the initial output. Consider:
- How well does each version accomplish what the task asks for?
- How much has each version improved over the initial output?
- Are the claims, numbers, and assumptions grounded and defensible?
- Is the level of detail appropriate for the task, or is there unnecessary bloat?
- Which would you trust more as a basis for real decisions?

Pick the version you would choose. Respond with your verdict in this exact format at the end:

WINNER: [1 or 2]
REASONING: [one paragraph explaining your choice]"""


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


def parse_winner(text):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip()
        if line.upper().startswith("WINNER:"):
            raw = line.split(":", 1)[1].strip().strip("*").strip()
            for char in raw:
                if char in ("1", "2"):
                    return char
    return None


async def main():
    root = Path(__file__).parent

    task_prompt = Path("/root/autoreason-experiment/tasks/task_01.md").read_text().strip()
    initial_output = (root / "results_v2" / "task_01" / "initial_a.md").read_text()
    pass15 = (root / "results_v2" / "task_01" / "pass_15" / "version_a.md").read_text()
    pass25 = (root / "results_v2" / "task_01" / "pass_25" / "version_a.md").read_text()

    print(f"Pass 15 incumbent: {len(pass15.split())} words")
    print(f"Pass 25 incumbent: {len(pass25.split())} words")
    print()

    num_judges = 7
    model = "anthropic/claude-sonnet-4-20250514"
    temperature = 0.3

    out_dir = root / "results_comparison_v2"
    out_dir.mkdir(parents=True, exist_ok=True)

    judge_tasks = []
    judge_orders = []

    for j in range(num_judges):
        if random.random() < 0.5:
            v1, v2 = pass15, pass25
            order = {"1": "pass15", "2": "pass25"}
        else:
            v1, v2 = pass25, pass15
            order = {"1": "pass25", "2": "pass15"}

        judge_orders.append(order)
        proposals = f"VERSION 1:\n---\n{v1}\n---\n\nVERSION 2:\n---\n{v2}\n---"

        judge_tasks.append(
            call_llm(
                JUDGE_SYSTEM,
                JUDGE_PROMPT.format(
                    task_prompt=task_prompt,
                    initial_output=initial_output,
                    proposals=proposals,
                ),
                model, temperature, 4096
            )
        )

    print(f"Running {num_judges} blind judges...")
    t0 = time.time()
    responses = await asyncio.gather(*judge_tasks, return_exceptions=True)
    elapsed = time.time() - t0

    results = []
    pass15_wins = 0
    pass25_wins = 0

    for j, (response, order) in enumerate(zip(responses, judge_orders)):
        if isinstance(response, Exception):
            print(f"  Judge {j+1}: ERROR - {response}")
            results.append({"judge": j+1, "error": str(response)})
            continue

        pick_num = parse_winner(response)
        if pick_num:
            pick_method = order[pick_num]
            if pick_method == "pass15":
                pass15_wins += 1
            else:
                pass25_wins += 1
        else:
            pick_method = "PARSE_ERROR"

        # Extract reasoning
        reasoning = ""
        for line in response.split("\n"):
            if line.strip().upper().startswith("REASONING:"):
                reasoning = line.strip()[10:].strip()[:200]
                break

        print(f"  Judge {j+1}: {pick_method} — {reasoning}")

        results.append({
            "judge": j + 1,
            "pick_position": pick_num,
            "pick_method": pick_method,
            "presentation_order": order,
            "raw_response": response,
        })

    print(f"\nResults ({elapsed:.0f}s):")
    print(f"  Pass 15 (first convergence):  {pass15_wins}/{num_judges}")
    print(f"  Pass 25 (second convergence): {pass25_wins}/{num_judges}")

    summary = {
        "pass15_wins": pass15_wins,
        "pass25_wins": pass25_wins,
        "num_judges": num_judges,
        "model": model,
        "temperature": temperature,
        "pass15_words": len(pass15.split()),
        "pass25_words": len(pass25.split()),
        "judges": results,
    }

    (out_dir / "pass15_vs_pass25.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False)
    )
    print(f"\nSaved to {out_dir / 'pass15_vs_pass25.json'}")


if __name__ == "__main__":
    asyncio.run(main())
