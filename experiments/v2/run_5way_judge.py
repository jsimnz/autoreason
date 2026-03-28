#!/usr/bin/env python3
"""
7-judge blind panel comparing all 5 methods.

Each judge sees the original task, the initial output, and all 5 final
versions with randomized labels (A through E). Judges rank all 5.
"""

import asyncio
import json
import os
import random
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

JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no prior knowledge of how "
    "any version was produced. Evaluate based solely on the content."
)

JUDGE_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

INITIAL OUTPUT (the starting point all versions were derived from):
---
{initial_output}
---

Five teams independently worked to improve the initial output. Here are their final versions:

{proposals}

Evaluate all five final versions against the original task and the initial output. Consider:
- How well does each version accomplish what the task asks for?
- How much has each version improved over the initial output?
- Are the claims, numbers, and assumptions grounded and defensible?
- Is the level of detail appropriate for the task, or is there unnecessary bloat?
- Which would you trust most as a basis for real decisions?

Rank all five versions from best to worst. Respond with your ranking in this exact format at the end:

RANKING: [best], [second], [third], [fourth], [worst]

Where each slot is the version letter (A, B, C, D, or E)."""


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


def parse_ranking(text):
    """Extract RANKING line, return list of letters."""
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            letters = [c for c in raw.upper() if c in "ABCDE"]
            if len(letters) >= 3:
                return letters
    return None


async def main():
    root = Path(__file__).parent
    
    task_prompt = Path("/root/autoreason-experiment/tasks/task_01.md").read_text().strip()
    initial_output = (root / "results_v2" / "task_01" / "initial_a.md").read_text()

    # Load all 5 outputs
    methods = {
        "autoreason": (root / "results_v2" / "task_01" / "pass_14" / "version_a.md").read_text(),
        "critique_and_revise": (root / "results_adversarial" / "task_01" / "final_output.md").read_text(),
        "improve_this": (root / "results_baselines" / "task_01" / "improve_this" / "final_output.md").read_text(),
        "conservative": (root / "results_baselines" / "task_01" / "conservative" / "final_output.md").read_text(),
        "harsh_critic": (root / "results_baselines" / "task_01" / "harsh_critic" / "final_output.md").read_text(),
    }

    print("Methods and word counts:")
    for name, text in methods.items():
        print(f"  {name:25s} {len(text.split()):5d} words")
    print()

    num_judges = 7
    model = "anthropic/claude-sonnet-4-20250514"
    temperature = 0.3
    labels = ["A", "B", "C", "D", "E"]

    out_dir = root / "results_comparison_v2"
    out_dir.mkdir(parents=True, exist_ok=True)

    judge_tasks = []
    judge_orders = []  # maps label -> method name

    method_names = list(methods.keys())

    for j in range(num_judges):
        # Randomize assignment of labels to methods
        shuffled = method_names.copy()
        random.shuffle(shuffled)
        order = {labels[i]: shuffled[i] for i in range(5)}
        judge_orders.append(order)

        parts = []
        for i, label in enumerate(labels):
            method_name = order[label]
            parts.append(f"VERSION {label}:\n---\n{methods[method_name]}\n---")

        proposals = "\n\n".join(parts)

        judge_tasks.append(
            call_llm(
                JUDGE_SYSTEM,
                JUDGE_PROMPT.format(
                    task_prompt=task_prompt,
                    initial_output=initial_output,
                    proposals=proposals,
                ),
                model, temperature, 8192
            )
        )

    print(f"Running {num_judges} blind judges...")
    t0 = time.time()
    responses = await asyncio.gather(*judge_tasks, return_exceptions=True)
    elapsed = time.time() - t0

    # Borda count: 5 points for 1st, 4 for 2nd, 3 for 3rd, 2 for 4th, 1 for 5th
    borda = {name: 0 for name in method_names}
    points = [5, 4, 3, 2, 1]
    results = []
    first_place_counts = {name: 0 for name in method_names}

    for j, (response, order) in enumerate(zip(responses, judge_orders)):
        if isinstance(response, Exception):
            print(f"  Judge {j+1}: ERROR - {response}")
            results.append({"judge": j+1, "error": str(response)})
            continue

        ranking_letters = parse_ranking(response)
        if ranking_letters:
            ranking_methods = [order.get(l, l) for l in ranking_letters]
            for pos, method in enumerate(ranking_methods):
                if method in borda and pos < len(points):
                    borda[method] += points[pos]
            if ranking_methods[0] in first_place_counts:
                first_place_counts[ranking_methods[0]] += 1
            rank_str = " > ".join(ranking_methods)
        else:
            ranking_methods = None
            rank_str = "PARSE_ERROR"

        print(f"  Judge {j+1}: {rank_str}")

        results.append({
            "judge": j + 1,
            "ranking_letters": ranking_letters,
            "ranking_methods": ranking_methods,
            "presentation_order": order,
            "raw_response": response,
        })

    # Sort by Borda score
    sorted_methods = sorted(borda.items(), key=lambda x: -x[1])

    print(f"\nBorda Scores ({elapsed:.0f}s):")
    print(f"  {'Method':25s} {'Score':>6s} {'1st Place':>10s}")
    print(f"  {'─' * 25} {'─' * 6} {'─' * 10}")
    for name, score in sorted_methods:
        print(f"  {name:25s} {score:6d} {first_place_counts[name]:10d}")

    summary = {
        "borda_scores": dict(sorted_methods),
        "first_place_counts": first_place_counts,
        "num_judges": num_judges,
        "model": model,
        "temperature": temperature,
        "word_counts": {name: len(text.split()) for name, text in methods.items()},
        "judges": results,
    }

    (out_dir / "5way_comparison.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False)
    )
    print(f"\nSaved to {out_dir / '5way_comparison.json'}")


if __name__ == "__main__":
    asyncio.run(main())
