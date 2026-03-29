#!/usr/bin/env python3
"""
v1-lite: Critic → B → Judge(A vs B). 3 calls.
Compare against other single-pass methods on all 5 tasks.
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

MODEL = "anthropic/claude-sonnet-4-20250514"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096

AUTHOR_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Avoid generic advice."
)

CRITIC_SYSTEM = (
    "You are a critical reviewer. Find real problems. Be specific. Do not suggest fixes."
)

AUTHOR_B_SYSTEM = (
    "You are a senior consultant revising a proposal based on specific criticisms. "
    "Address each valid criticism directly. Do not make changes that aren't motivated by an identified problem."
)

JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no authorship stake in either version."
)

GENERATE_A = "{task_prompt}\n\nProduce a complete, detailed proposal."

CRITIC_PROMPT = """Here is a proposal:

---
{version_a}
---

Find real problems. Focus on things that won't work, wrong assumptions, missing pieces, generic advice. Do NOT propose fixes."""

AUTHOR_B_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

CURRENT PROPOSAL:
---
{version_a}
---

PROBLEMS FOUND:
---
{critic}
---

Revise the proposal to address these problems. For each change, state which problem it fixes."""

JUDGE_AB_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Two versions of a proposal. One is the original, one is a revision. You don't know which is which.

VERSION 1:
---
{v1}
---

VERSION 2:
---
{v2}
---

Which version better accomplishes the original task? Pick one.

WINNER: [1 or 2]
REASONING: [one sentence]"""

BASELINE_PROMPTS = {
    "improve_this": "Improve this proposal. Make it stronger and more thorough.\n\n---\n{current_version}\n---\n\nORIGINAL TASK:\n---\n{task_prompt}\n---\n\nProduce the complete improved proposal.",
    "critique_and_revise": "Review critically. Find real problems. Then revise to fix every problem.\n\n---\n{current_version}\n---\n\nORIGINAL TASK:\n---\n{task_prompt}\n---\n\nProduce the complete revised proposal.",
    "conservative": "Make changes only if genuinely wrong or missing. If already good, leave as is.\n\n---\n{current_version}\n---\n\nORIGINAL TASK:\n---\n{task_prompt}\n---\n\nProduce the complete proposal.",
    "harsh_critic": "Find every flaw. Rewrite from scratch to address all of them.\n\n---\n{current_version}\n---\n\nORIGINAL TASK:\n---\n{task_prompt}\n---\n\nProduce the complete revised proposal.",
}

JUDGE_5WAY_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

INITIAL OUTPUT (starting point):
---
{initial_output}
---

Five teams each made one attempt to improve the initial output:

{proposals}

Rank all five from best to worst:

RANKING: [best], [second], [third], [fourth], [worst]

Where each slot is the version letter (A, B, C, D, or E)."""


async def call_llm(system, user, model, temperature, max_tokens, max_retries=8):
    for attempt in range(max_retries):
        try:
            response = await litellm.acompletion(
                model=model, messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ], temperature=temperature, max_tokens=max_tokens,
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


def parse_winner_12(text):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip()
        if line.upper().startswith("WINNER:"):
            raw = line.split(":", 1)[1].strip()
            for c in raw:
                if c in ("1", "2"):
                    return c
    return None

def parse_ranking(text, valid_chars):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            items = [c for c in raw if c in valid_chars]
            if len(items) >= 2:
                return items
    return None


async def run_v1_lite(task_prompt, initial_a):
    """Critic → B → Judge(A vs B). Returns winner text."""
    critic = await call_llm(CRITIC_SYSTEM, CRITIC_PROMPT.format(version_a=initial_a), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    vb = await call_llm(AUTHOR_B_SYSTEM, AUTHOR_B_PROMPT.format(task_prompt=task_prompt, version_a=initial_a, critic=critic), MODEL, AUTHOR_TEMP, MAX_TOKENS)

    # Judge: randomize A vs B presentation
    if random.random() < 0.5:
        v1_text, v2_text = initial_a, vb
        order = {"1": "A", "2": "B"}
    else:
        v1_text, v2_text = vb, initial_a
        order = {"1": "B", "2": "A"}

    judge_resp = await call_llm(JUDGE_SYSTEM, JUDGE_AB_PROMPT.format(
        task_prompt=task_prompt, v1=v1_text, v2=v2_text
    ), MODEL, JUDGE_TEMP, MAX_TOKENS)

    pick = parse_winner_12(judge_resp)
    if pick:
        winner = order[pick]
    else:
        winner = "B"  # default to revision if parse fails

    return (initial_a if winner == "A" else vb), winner, critic


async def main():
    import numpy as np
    tasks_dir = Path("/root/autoreason-experiment/tasks")
    root = Path(__file__).parent
    out_root = root / "results_v1_lite"

    print(f"v1-lite: Critic → B → Judge(A vs B)")
    print(f"Model: {MODEL}")
    print(f"{'='*60}\n")

    all_results = {}

    for task_num in range(1, 6):
        task_prompt = (tasks_dir / f"task_{task_num:02d}.md").read_text().strip()
        task_dir = out_root / f"task_{task_num:02d}"
        task_dir.mkdir(parents=True, exist_ok=True)

        print(f"{'━'*60}")
        print(f"Task {task_num}")
        print(f"{'━'*60}")

        # Use same initial A as v1 comparison for fair comparison
        v1_init = root / "results_v1_comparison" / f"task_{task_num:02d}" / "initial_a.md"
        if v1_init.exists():
            initial_a = v1_init.read_text()
        else:
            initial_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
        (task_dir / "initial_a.md").write_text(initial_a)
        print(f"  Initial A: {len(initial_a.split())} words")

        # v1-lite
        lite_file = task_dir / "v1_lite_output.md"
        if lite_file.exists():
            lite_output = lite_file.read_text()
            print(f"  v1-lite: already complete ({len(lite_output.split())} words)")
        else:
            print(f"  Running v1-lite (3 calls)...")
            lite_output, winner, critic = await run_v1_lite(task_prompt, initial_a)
            lite_file.write_text(lite_output)
            (task_dir / "critic.md").write_text(critic)
            print(f"  v1-lite: judge picked {winner}, {len(lite_output.split())} words")

        # Load v1 baselines from previous run
        v1_dir = root / "results_v1_comparison" / f"task_{task_num:02d}"
        baseline_outputs = {}
        for bname in BASELINE_PROMPTS:
            bf = v1_dir / f"baseline_{bname}.md"
            if bf.exists():
                baseline_outputs[bname] = bf.read_text()
            else:
                print(f"  Running {bname}...")
                output = await call_llm(AUTHOR_SYSTEM, BASELINE_PROMPTS[bname].format(
                    current_version=initial_a, task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
                baseline_outputs[bname] = output

        # 7-judge panel
        judge_file = task_dir / "judge_results.json"
        if judge_file.exists():
            judge_result = json.loads(judge_file.read_text())
        else:
            print(f"  Running 7-judge panel...")
            all_outputs = {"autoreason_v1_lite": lite_output}
            all_outputs.update(baseline_outputs)
            method_names = list(all_outputs.keys())
            labels = ["A", "B", "C", "D", "E"]

            jtasks, jorders = [], []
            for _ in range(7):
                shuffled = method_names.copy()
                random.shuffle(shuffled)
                order = {labels[i]: shuffled[i] for i in range(5)}
                jorders.append(order)
                parts = [f"VERSION {labels[i]}:\n---\n{all_outputs[order[labels[i]]]}---" for i in range(5)]
                jtasks.append(call_llm(JUDGE_SYSTEM, JUDGE_5WAY_PROMPT.format(
                    task_prompt=task_prompt, initial_output=initial_a, proposals="\n\n".join(parts)
                ), MODEL, JUDGE_TEMP, MAX_TOKENS))

            jresps = await asyncio.gather(*jtasks, return_exceptions=True)
            borda = {n: 0 for n in method_names}
            first_place = {n: 0 for n in method_names}
            points = [5, 4, 3, 2, 1]
            for resp, order in zip(jresps, jorders):
                if isinstance(resp, Exception): continue
                ranking = parse_ranking(resp, "ABCDE")
                if ranking:
                    mapped = [order.get(l, l) for l in ranking]
                    for pos, method in enumerate(mapped):
                        if method in borda and pos < len(points):
                            borda[method] += points[pos]
                    if mapped[0] in first_place:
                        first_place[mapped[0]] += 1

            judge_result = {"borda": borda, "first_place": first_place}
            judge_file.write_text(json.dumps(judge_result, indent=2))

        borda = judge_result["borda"]
        fp = judge_result["first_place"]
        sorted_methods = sorted(borda.items(), key=lambda x: -x[1])
        print(f"  Results:")
        for name, score in sorted_methods:
            print(f"    {name:25s} Borda={score:3d} 1st={fp.get(name, 0)}")

        all_results[f"task_{task_num:02d}"] = judge_result
        await asyncio.sleep(3)

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    method_names = ["autoreason_v1_lite", "critique_and_revise", "harsh_critic", "conservative", "improve_this"]
    print(f"\n{'Method':25s}", end="")
    for t in range(1, 6): print(f" T{t}", end="")
    print("  Avg")
    for m in method_names:
        scores = [all_results[f"task_{t:02d}"]["borda"].get(m, 0) for t in range(1, 6)]
        print(f"{m:25s}", end="")
        for s in scores: print(f" {s:2d}", end="")
        print(f"  {sum(scores)/len(scores):.1f}")

    (out_root / "all_results.json").write_text(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
