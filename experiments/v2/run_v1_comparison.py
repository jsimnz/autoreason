#!/usr/bin/env python3
"""
v1 (single pass) comparison across all 5 tasks.

For each task:
1. Generate initial A
2. Run one autoreason pass (critic → B → AB → 3-judge pick)
3. Run each baseline once from the same initial A
4. 7-judge blind panel comparing all 5 outputs
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

MODEL = "anthropic/claude-sonnet-4-20250514"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096

AUTHOR_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Avoid generic advice. "
    "Tailor everything to the constraints stated in the task."
)

CRITIC_SYSTEM = (
    "You are a critical reviewer. Your only job is to find real problems. "
    "Be specific and concrete. Do not suggest fixes."
)

AUTHOR_B_SYSTEM = (
    "You are a senior consultant revising a proposal based on specific criticisms. "
    "Address each valid criticism directly. Do not make changes that aren't "
    "motivated by an identified problem."
)

SYNTHESIZER_SYSTEM = (
    "You are a senior consultant. You are given two versions as equal inputs. "
    "Take the strongest elements from each and produce a coherent synthesis."
)

JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no authorship stake in any version."
)

GENERATE_A = "{task_prompt}\n\nProduce a complete, detailed proposal."

CRITIC_PROMPT = """Here is a proposal:

---
{version_a}
---

Find real problems. Focus on things that won't work, wrong assumptions, missing pieces. Do NOT propose fixes."""

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

SYNTHESIZER_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

VERSION X:
---
{version_x}
---

VERSION Y:
---
{version_y}
---

Produce a synthesis keeping the strongest elements from both."""

JUDGE_PICK_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Three proposals produced independently:

{proposals}

Rank all three from best to worst:

RANKING: [best], [second], [worst]

Where each slot is 1, 2, or 3."""

BASELINE_PROMPTS = {
    "improve_this": """Here is a proposal:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

Improve this proposal. Make it stronger, more compelling, and more thorough. Produce the complete improved proposal.""",

    "critique_and_revise": """Here is a proposal:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

Review critically. Find real problems. Then revise to fix every problem. Produce the complete revised proposal.""",

    "conservative": """Here is a proposal:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

Make changes only if something is genuinely wrong or missing. If already good, leave as is. Produce the complete proposal.""",

    "harsh_critic": """Here is a proposal:

---
{current_version}
---

ORIGINAL TASK:
---
{task_prompt}
---

Find every flaw. Then rewrite from scratch to address all of them. Produce the complete revised proposal.""",
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
                print(f"      [Rate limited, retry in {wait}s]")
                await asyncio.sleep(wait)
            else:
                if attempt < max_retries - 1:
                    await asyncio.sleep(10)
                else:
                    raise
    raise RuntimeError(f"Failed after {max_retries} retries")


def parse_ranking(text, valid_chars):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            items = [c for c in raw if c in valid_chars]
            if len(items) >= 2:
                return items
    return None


async def run_v1_pass(task_prompt, initial_a):
    """Run one autoreason v1 pass. Returns the judge's pick."""
    # Critic
    critic = await call_llm(CRITIC_SYSTEM, CRITIC_PROMPT.format(version_a=initial_a), MODEL, AUTHOR_TEMP, MAX_TOKENS)

    # Author B
    vb = await call_llm(AUTHOR_B_SYSTEM, AUTHOR_B_PROMPT.format(task_prompt=task_prompt, version_a=initial_a, critic=critic), MODEL, AUTHOR_TEMP, MAX_TOKENS)

    # Synthesizer
    if random.random() < 0.5:
        vx, vy = initial_a, vb
    else:
        vx, vy = vb, initial_a
    vab = await call_llm(SYNTHESIZER_SYSTEM, SYNTHESIZER_PROMPT.format(task_prompt=task_prompt, version_x=vx, version_y=vy), MODEL, AUTHOR_TEMP, MAX_TOKENS)

    # 3-judge panel to pick winner
    versions = [("A", initial_a), ("B", vb), ("AB", vab)]
    random.shuffle(versions)
    order_map = {str(i+1): label for i, (label, _) in enumerate(versions)}
    parts = [f"PROPOSAL {i+1}:\n---\n{content}\n---" for i, (_, content) in enumerate(versions)]
    proposals = "\n\n".join(parts)

    jtasks = []
    jorders = []
    for _ in range(3):
        random.shuffle(versions)
        om = {str(i+1): label for i, (label, _) in enumerate(versions)}
        jorders.append(om)
        ps = [f"PROPOSAL {i+1}:\n---\n{content}\n---" for i, (_, content) in enumerate(versions)]
        jtasks.append(call_llm(JUDGE_SYSTEM, JUDGE_PICK_PROMPT.format(task_prompt=task_prompt, proposals="\n\n".join(ps)), MODEL, JUDGE_TEMP, MAX_TOKENS))

    jresps = await asyncio.gather(*jtasks, return_exceptions=True)

    scores = {"A": 0, "B": 0, "AB": 0}
    for resp, om in zip(jresps, jorders):
        if isinstance(resp, Exception):
            continue
        ranking = parse_ranking(resp, "123")
        if ranking:
            mapped = [om.get(r, r) for r in ranking]
            for pos, label in enumerate(mapped):
                if label in scores and pos < 3:
                    scores[label] += (3 - pos)

    # Pick winner (A wins ties)
    priority = {"A": 0, "B": 1, "AB": 2}
    winner = sorted(scores.keys(), key=lambda k: (-scores[k], priority[k]))[0]

    version_map = {"A": initial_a, "B": vb, "AB": vab}
    return version_map[winner], winner, scores


async def main():
    tasks_dir = Path("/root/autoreason-experiment/tasks")
    root = Path(__file__).parent
    out_root = root / "results_v1_comparison"

    print(f"v1 Single-Pass Comparison")
    print(f"Model: {MODEL}")
    print(f"{'='*60}\n")

    all_results = {}

    for task_num in range(1, 6):
        task_file = tasks_dir / f"task_{task_num:02d}.md"
        task_prompt = task_file.read_text().strip()
        task_dir = out_root / f"task_{task_num:02d}"
        task_dir.mkdir(parents=True, exist_ok=True)

        print(f"{'━'*60}")
        print(f"Task {task_num}: {task_prompt[:60]}...")
        print(f"{'━'*60}")

        # Generate initial A
        init_file = task_dir / "initial_a.md"
        if init_file.exists():
            initial_a = init_file.read_text()
        else:
            print(f"  Generating initial A...")
            initial_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
            init_file.write_text(initial_a)
        print(f"  Initial A: {len(initial_a.split())} words")

        # v1 autoreason pass
        v1_file = task_dir / "v1_output.md"
        if v1_file.exists():
            v1_output = v1_file.read_text()
            print(f"  v1 autoreason: already complete ({len(v1_output.split())} words)")
        else:
            print(f"  Running v1 autoreason (1 pass)...")
            v1_output, winner, scores = await run_v1_pass(task_prompt, initial_a)
            v1_file.write_text(v1_output)
            (task_dir / "v1_result.json").write_text(json.dumps({"winner": winner, "scores": scores}, indent=2))
            print(f"  v1 pick: {winner} (A={scores['A']}, B={scores['B']}, AB={scores['AB']}), {len(v1_output.split())} words")

        # Baselines (1 pass each)
        baseline_outputs = {}
        for bname, prompt_template in BASELINE_PROMPTS.items():
            bf = task_dir / f"baseline_{bname}.md"
            if bf.exists():
                baseline_outputs[bname] = bf.read_text()
                print(f"  {bname}: already complete")
            else:
                print(f"  Running {bname} (1 pass)...")
                output = await call_llm(AUTHOR_SYSTEM, prompt_template.format(current_version=initial_a, task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
                bf.write_text(output)
                baseline_outputs[bname] = output
                print(f"  {bname}: {len(output.split())} words")

        # 7-judge blind panel
        judge_file = task_dir / "judge_results.json"
        if judge_file.exists():
            judge_result = json.loads(judge_file.read_text())
            print(f"  Judges: already complete")
        else:
            print(f"  Running 7-judge panel...")
            all_outputs = {"autoreason_v1": v1_output}
            all_outputs.update(baseline_outputs)

            method_names = list(all_outputs.keys())
            labels = ["A", "B", "C", "D", "E"]

            jtasks = []
            jorders = []
            for _ in range(7):
                shuffled = method_names.copy()
                random.shuffle(shuffled)
                order = {labels[i]: shuffled[i] for i in range(5)}
                jorders.append(order)
                parts = [f"VERSION {labels[i]}:\n---\n{all_outputs[order[labels[i]]]}---" for i in range(5)]
                proposals = "\n\n".join(parts)
                jtasks.append(call_llm(JUDGE_SYSTEM, JUDGE_5WAY_PROMPT.format(
                    task_prompt=task_prompt, initial_output=initial_a, proposals=proposals
                ), MODEL, JUDGE_TEMP, MAX_TOKENS))

            jresps = await asyncio.gather(*jtasks, return_exceptions=True)

            borda = {n: 0 for n in method_names}
            first_place = {n: 0 for n in method_names}
            points = [5, 4, 3, 2, 1]

            for resp, order in zip(jresps, jorders):
                if isinstance(resp, Exception):
                    continue
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

        # Print results
        borda = judge_result["borda"]
        fp = judge_result["first_place"]
        sorted_methods = sorted(borda.items(), key=lambda x: -x[1])
        print(f"  Results:")
        for name, score in sorted_methods:
            print(f"    {name:25s} Borda={score:3d} 1st={fp.get(name, 0)}")

        all_results[f"task_{task_num:02d}"] = judge_result
        await asyncio.sleep(3)

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY: v1 Single-Pass Results")
    print(f"{'='*60}")

    method_names = ["autoreason_v1", "critique_and_revise", "harsh_critic", "conservative", "improve_this"]
    print(f"\n{'Method':25s}", end="")
    for t in range(1, 6):
        print(f" T{t:d}", end="")
    print("  Avg")

    for m in method_names:
        scores = [all_results[f"task_{t:02d}"]["borda"].get(m, 0) for t in range(1, 6)]
        print(f"{m:25s}", end="")
        for s in scores:
            print(f" {s:2d}", end="")
        print(f"  {np.mean(scores):.1f}" if 'np' in dir() else f"  {sum(scores)/len(scores):.1f}")

    (out_root / "all_results.json").write_text(json.dumps(all_results, indent=2))
    print(f"\nSaved to {out_root / 'all_results.json'}")


if __name__ == "__main__":
    import numpy as np
    asyncio.run(main())
