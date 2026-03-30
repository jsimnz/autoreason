#!/usr/bin/env python3
"""
Blind 7-judge evaluation: margin-converged autoreason outputs vs baselines.
Tests whether margin-forced convergence produces quality output, not just stability.

Compares 7 versions:
  1. autoreason_margin (converged pass 15)
  2. autoreason_combined (converged pass 17)
  3. autoreason_baseline (original 50-pass, no convergence)
  4. critique_and_revise (15 passes)
  5. improve_this (15 passes)
  6. harsh_critic (15 passes)
  7. conservative (15 passes)

7 CoT judges, Sonnet 4.6, blind randomized labels.
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

MODEL = "anthropic/claude-sonnet-4-6"
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096

COT_JUDGE_SYSTEM = "You are an independent evaluator. You have no authorship stake. Think carefully before deciding."

COT_JUDGE_7WAY = """ORIGINAL TASK:
---
{task_prompt}
---

INITIAL OUTPUT (starting point for all methods):
---
{initial_output}
---

Seven teams independently improved the initial output using different methods:

{proposals}

For each version, think step by step:
1. How well does it accomplish the task?
2. How much has it improved over the initial output?
3. Are claims and numbers grounded?
4. Is detail appropriate or bloated?

After reasoning, rank all seven from best to worst:

RANKING: [1st], [2nd], [3rd], [4th], [5th], [6th], [7th]"""


async def call_llm(system, user, model, temperature, max_tokens, max_retries=8):
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
                await asyncio.sleep(wait)
            else:
                if attempt < max_retries - 1:
                    await asyncio.sleep(10)
                else:
                    raise
    raise RuntimeError(f"Failed after {max_retries} retries")


def parse_ranking(text, valid_chars="ABCDEFG"):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            items = [c for c in raw.upper() if c in valid_chars]
            if len(items) >= 5:
                return items
    return None


async def main():
    root = Path(__file__).parent
    task_prompt = Path("/root/autoreason-experiment/tasks/task_02.md").read_text().strip()
    initial_a = (root / "results_46_task02" / "autoreason" / "initial_a.md").read_text()

    # Load all outputs
    outputs = {
        "autoreason_margin": (root / "results_46_remedy_margin" / "autoreason" / "final_output.md").read_text(),
        "autoreason_combined": (root / "results_46_remedy_combined" / "autoreason" / "final_output.md").read_text(),
        "autoreason_baseline": (root / "results_46_task02" / "autoreason" / "final_output.md").read_text(),
        "critique_and_revise": (root / "results_46_task02" / "baseline_critique_and_revise.md").read_text(),
        "improve_this": (root / "results_46_task02" / "baseline_improve_this.md").read_text(),
        "harsh_critic": (root / "results_46_task02" / "baseline_harsh_critic.md").read_text(),
        "conservative": (root / "results_46_task02" / "baseline_conservative.md").read_text(),
    }

    method_names = list(outputs.keys())
    labels = list("ABCDEFG")

    print(f"7-Way Blind Evaluation: Remedy Outputs vs Baselines")
    print(f"Model: {MODEL}")
    print(f"Methods: {', '.join(method_names)}")
    print(f"Word counts: {', '.join(f'{k}={len(v.split())}' for k, v in outputs.items())}")
    print(f"{'='*70}\n")

    # Run 7 judges in parallel
    judge_tasks = []
    judge_orders = []

    for j in range(7):
        shuffled = method_names.copy()
        random.shuffle(shuffled)
        order = {labels[i]: shuffled[i] for i in range(7)}
        judge_orders.append(order)

        parts = [f"VERSION {labels[i]}:\n---\n{outputs[order[labels[i]]]}\n---" for i in range(7)]
        prompt = COT_JUDGE_7WAY.format(
            task_prompt=task_prompt,
            initial_output=initial_a,
            proposals="\n\n".join(parts),
        )
        judge_tasks.append(call_llm(COT_JUDGE_SYSTEM, prompt, MODEL, JUDGE_TEMP, MAX_TOKENS))

    print("Running 7 judges in parallel...")
    responses = await asyncio.gather(*judge_tasks, return_exceptions=True)

    # Score
    borda = {n: 0 for n in method_names}
    first_place = {n: 0 for n in method_names}
    points = [7, 6, 5, 4, 3, 2, 1]
    valid_judges = 0

    for j, (resp, order) in enumerate(zip(responses, judge_orders)):
        if isinstance(resp, Exception):
            print(f"  Judge {j+1}: ERROR - {resp}")
            continue
        ranking = parse_ranking(resp)
        if not ranking:
            print(f"  Judge {j+1}: PARSE FAILED")
            # Save raw response for debugging
            (root / f"remedy_eval_judge_{j+1}_raw.txt").write_text(resp)
            continue

        valid_judges += 1
        mapped = [order.get(l, l) for l in ranking[:7]]
        for pos, method in enumerate(mapped):
            if method in borda and pos < len(points):
                borda[method] += points[pos]
        if mapped[0] in first_place:
            first_place[mapped[0]] += 1

        top3 = ', '.join(mapped[:3])
        print(f"  Judge {j+1}: {top3}")

    # Results
    sorted_methods = sorted(borda.items(), key=lambda x: -x[1])
    max_borda = valid_judges * 7

    print(f"\n{'='*70}")
    print(f"Results ({valid_judges} valid judges, max Borda = {max_borda}):\n")
    print(f"  {'Method':30s} {'Borda':>6s} {'1st':>4s}")
    print(f"  {'-'*30} {'-'*6} {'-'*4}")
    for name, score in sorted_methods:
        marker = " ***" if name.startswith("autoreason_margin") or name.startswith("autoreason_combined") else ""
        print(f"  {name:30s} {score:6d} {first_place.get(name, 0):4d}{marker}")

    results = {
        "borda": borda,
        "first_place": first_place,
        "valid_judges": valid_judges,
        "max_borda": max_borda,
        "method_word_counts": {k: len(v.split()) for k, v in outputs.items()},
    }
    out_file = root / "results_46_remedy_eval.json"
    out_file.write_text(json.dumps(results, indent=2))
    print(f"\nSaved to {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
