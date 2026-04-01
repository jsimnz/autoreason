#!/usr/bin/env python3
"""
Evaluate compute-matched baselines: autoreason vs critique_and_revise@15 vs critique_and_revise@90.
7-judge blind panel, same methodology as other evaluations.

This addresses the reviewer concern about unfair compute comparison.
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

TASK_PROMPTS = {
    1: Path("/workspace/autoreason/tasks/task_01.md").read_text().strip(),
}

COT_JUDGE_3WAY = """ORIGINAL TASK:
---
{task_prompt}
---

Three teams independently produced proposals for this task using different methods and different compute budgets:

{proposals}

For each version, think step by step:
1. How well does it accomplish the original task?
2. Is the content specific and actionable, or generic?
3. Is the level of detail appropriate — enough substance without bloat?
4. Are numbers and claims defensible?

After reasoning, rank all three from best to worst:

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


async def main():
    root = Path(__file__).parent
    out_dir = root / "results_compute_matched_eval"
    out_dir.mkdir(parents=True, exist_ok=True)

    for task_num in [1]:
        task_prompt = TASK_PROMPTS[task_num]
        
        # Load outputs
        # Autoreason converged output (from v1 comparison — the output used in original Table 2)
        ar_path = root / "results_v1_comparison" / f"task_{task_num:02d}" / "v1_output.md"
        # Critique & revise at 15 passes — use the checkpoint from the 90-pass run
        cr15_candidates = [
            root / "results_compute_matched" / f"task_{task_num:02d}" / "critique_and_revise_90" / "pass_15.md",
            root / "results_baselines" / f"task_{task_num:02d}" / "critique_and_revise" / "pass_15.md",
            root / "results_v1_comparison" / f"task_{task_num:02d}" / "baseline_critique_and_revise.md",
        ]
        # Critique & revise at 90 passes (compute matched)
        cr90_path = root / "results_compute_matched" / f"task_{task_num:02d}" / "critique_and_revise_90" / "pass_90.md"

        ar_output = ar_path.read_text()
        cr90_output = cr90_path.read_text()
        
        cr15_output = None
        for p in cr15_candidates:
            if p.exists():
                cr15_output = p.read_text()
                break
        
        if cr15_output is None:
            # Fall back: check results_v2
            alt = root / "results_v2" / f"task_{task_num:02d}" / "baselines" / "critique_and_revise_15.md"
            if alt.exists():
                cr15_output = alt.read_text()
            else:
                print(f"  WARNING: Could not find critique_and_revise@15 for task {task_num}, skipping")
                continue

        methods = {
            "autoreason": ar_output,
            "cr_15": cr15_output,
            "cr_90": cr90_output,
        }
        labels = list("ABC")

        print(f"\n{'='*60}")
        print(f"Task {task_num}: Compute-Matched Evaluation")
        print(f"  autoreason: {len(ar_output.split())} words (~90 LLM calls)")
        print(f"  critique_and_revise@15: {len(cr15_output.split())} words (~15 LLM calls)")
        print(f"  critique_and_revise@90: {len(cr90_output.split())} words (~90 LLM calls)")
        print(f"{'='*60}")

        method_names = list(methods.keys())
        judge_tasks = []
        judge_orders = []

        for _ in range(NUM_JUDGES):
            shuffled = method_names.copy()
            random.shuffle(shuffled)
            order = {labels[i]: shuffled[i] for i in range(len(method_names))}
            judge_orders.append(order)
            parts = [f"VERSION {labels[i]}:\n---\n{methods[order[labels[i]]]}\n---"
                     for i in range(len(method_names))]
            judge_tasks.append(call_llm(
                COT_JUDGE_SYSTEM,
                COT_JUDGE_3WAY.format(task_prompt=task_prompt, proposals="\n\n".join(parts)),
                MODEL, JUDGE_TEMP, MAX_TOKENS))

        responses = await asyncio.gather(*judge_tasks, return_exceptions=True)

        borda = {n: 0 for n in method_names}
        first_place = {n: 0 for n in method_names}
        points = [3, 2, 1]
        valid = 0

        for j, (resp, order) in enumerate(zip(responses, judge_orders)):
            if isinstance(resp, Exception):
                print(f"  Judge {j+1}: ERROR - {resp}")
                continue
            ranking = parse_ranking(resp)
            if not ranking:
                print(f"  Judge {j+1}: PARSE FAILED")
                (out_dir / f"task{task_num}_judge_{j+1}_raw.txt").write_text(resp)
                continue
            valid += 1
            mapped = [order.get(l, l) for l in ranking[:3]]
            for pos, method in enumerate(mapped):
                if method in borda and pos < len(points):
                    borda[method] += points[pos]
            if mapped[0] in first_place:
                first_place[mapped[0]] += 1
            print(f"  Judge {j+1}: {' > '.join(mapped)}")
            (out_dir / f"task{task_num}_judge_{j+1}_raw.txt").write_text(resp)

        max_borda = valid * 3
        sorted_methods = sorted(borda.items(), key=lambda x: -x[1])

        print(f"\n{'Method':<25} {'Borda':>8}/{max_borda} {'1st':>5} {'Words':>7} {'Calls':>7}")
        print(f"{'-'*60}")
        call_counts = {"autoreason": "~90", "cr_15": "~15", "cr_90": "~90"}
        for method, score in sorted_methods:
            wc = len(methods[method].split())
            print(f"{method:<25} {score:>8} {first_place[method]:>5} {wc:>7} {call_counts[method]:>7}")

        results = {
            "task": task_num,
            "model": MODEL,
            "valid_judges": valid,
            "borda": borda,
            "first_place": first_place,
            "word_counts": {n: len(methods[n].split()) for n in method_names},
        }
        (out_dir / f"task{task_num}_results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
