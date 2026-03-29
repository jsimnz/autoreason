#!/usr/bin/env python3
"""
Run autoreason v2 on the constrained task.
Same architecture as run_v2.py but takes a single task file argument.

Usage:
    python run_constrained.py
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

# Config
MODEL = "anthropic/claude-sonnet-4-20250514"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
NUM_JUDGES = 3
MAX_PASSES = 25
CONVERGENCE = 2

# System prompts
AUTHOR_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Avoid generic advice. "
    "Follow all constraints exactly as stated in the task."
)

CRITIC_SYSTEM = (
    "You are a critical reviewer. Your only job is to find real problems "
    "with the proposal you are given. Be specific and concrete. Do not "
    "suggest fixes or improvements — only identify weaknesses. "
    "Pay special attention to whether the output follows the stated constraints."
)

AUTHOR_B_SYSTEM = (
    "You are a senior consultant revising a proposal based on specific criticisms. "
    "Address each valid criticism directly. Do not make changes that aren't "
    "motivated by an identified problem. Follow all constraints exactly."
)

SYNTHESIZER_SYSTEM = (
    "You are a senior consultant. You are given two versions of a proposal as equal inputs. "
    "Take the strongest elements from each and produce a coherent synthesis. "
    "This is not a compromise — pick the best answer per dimension. "
    "Follow all constraints exactly."
)

JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no authorship stake in any "
    "version. Evaluate which version best accomplishes the original task "
    "as described, including all stated constraints."
)

# Prompts
GENERATE_A = "{task_prompt}\n\nProduce your response now."

CRITIC_PROMPT = """Here is a proposal:

---
{version_a}
---

ORIGINAL TASK AND CONSTRAINTS:
---
{task_prompt}
---

Find real problems. Focus on:
- Violations of stated constraints (word count, section requirements, specificity)
- Things that won't work as described
- Generic advice that could apply to any developer tool
- Numbers without justification
- Missing required sections or deliverables

Do NOT propose fixes. Just the problems."""

AUTHOR_B_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Here is a proposal and the problems identified with it.

CURRENT PROPOSAL:
---
{version_a}
---

PROBLEMS FOUND:
---
{critic}
---

Revise the proposal to address these problems.
For each change, state which problem it fixes.
Do not make changes that aren't motivated by an identified problem."""

SYNTHESIZER_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Here are two versions of a proposal. Treat them as equal inputs.

VERSION X:
---
{version_x}
---

VERSION Y:
---
{version_y}
---

Produce a synthesis that keeps the strongest elements from both.
Pick the best answer per dimension and make them cohere."""

JUDGE_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Three proposals have been produced independently. Evaluate how well each accomplishes the task, including adherence to all stated constraints.

{judge_proposals}

For each proposal:
1. Does it follow the word count constraint?
2. Does it cover all 6 required sections with the specified deliverables?
3. Are the numbers justified?
4. Is the advice specific to this product, not generic?

Rank all three from best to worst:

RANKING: [best], [second], [worst]

Where each slot is 1, 2, or 3."""


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


def randomize_for_judge(va, vb, vab):
    versions = [("A", va), ("B", vb), ("AB", vab)]
    random.shuffle(versions)
    order = {}
    parts = []
    for i, (label, content) in enumerate(versions, 1):
        order[str(i)] = label
        parts.append(f"PROPOSAL {i}:\n---\n{content}\n---")
    return "\n\n".join(parts), order


def parse_ranking(text, order_map):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            nums = [c for c in raw if c in ("1", "2", "3")]
            if len(nums) >= 2:
                return [order_map.get(n, n) for n in nums]
    return None


def aggregate(rankings):
    scores = {"A": 0, "B": 0, "AB": 0}
    points = [3, 2, 1]
    valid = [r for r in rankings if r is not None]
    for ranking in valid:
        for pos, label in enumerate(ranking):
            if label in scores and pos < len(points):
                scores[label] += points[pos]
    priority = {"A": 0, "B": 1, "AB": 2}
    ranked = sorted(scores.keys(), key=lambda k: (-scores[k], priority[k]))
    return ranked[0], scores, valid


async def run_pass(task_prompt, current_a, pass_num, pass_dir):
    pass_dir.mkdir(parents=True, exist_ok=True)

    result_file = pass_dir / "result.json"
    if result_file.exists():
        existing = json.loads(result_file.read_text())
        if existing.get("winner"):
            w = existing["winner"]
            print(f"    ↳ Skipping ({w})")
            if w == "A":
                return w, current_a, existing
            wf = pass_dir / f"version_{w.lower()}.md"
            return w, wf.read_text() if wf.exists() else current_a, existing

    t0 = time.time()
    (pass_dir / "version_a.md").write_text(current_a)

    print(f"    → Critic...")
    critic = await call_llm(CRITIC_SYSTEM, CRITIC_PROMPT.format(version_a=current_a, task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "critic.md").write_text(critic)

    print(f"    → Author B...")
    vb = await call_llm(AUTHOR_B_SYSTEM, AUTHOR_B_PROMPT.format(task_prompt=task_prompt, version_a=current_a, critic=critic), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_b.md").write_text(vb)

    print(f"    → Synthesizer...")
    if random.random() < 0.5:
        vx, vy = current_a, vb
    else:
        vx, vy = vb, current_a
    vab = await call_llm(SYNTHESIZER_SYSTEM, SYNTHESIZER_PROMPT.format(task_prompt=task_prompt, version_x=vx, version_y=vy), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_ab.md").write_text(vab)

    print(f"    → Judge panel ({NUM_JUDGES} judges)...")
    jtasks = []
    jorders = []
    for _ in range(NUM_JUDGES):
        proposals, order = randomize_for_judge(current_a, vb, vab)
        jorders.append(order)
        jtasks.append(call_llm(JUDGE_SYSTEM, JUDGE_PROMPT.format(task_prompt=task_prompt, judge_proposals=proposals), MODEL, JUDGE_TEMP, MAX_TOKENS))

    jresps = await asyncio.gather(*jtasks, return_exceptions=True)
    rankings = []
    jdetails = []
    for j, (resp, order) in enumerate(zip(jresps, jorders)):
        if isinstance(resp, Exception):
            print(f"      Judge {j+1}: ERROR")
            rankings.append(None)
            jdetails.append({"error": str(resp)})
        else:
            r = parse_ranking(resp, order)
            rankings.append(r)
            jdetails.append({"ranking": r, "order": order, "raw": resp})
            print(f"      Judge {j+1}: {' > '.join(r) if r else 'PARSE_ERROR'}")

    winner, scores, valid = aggregate(rankings)
    elapsed = time.time() - t0

    vmap = {"A": current_a, "B": vb, "AB": vab}
    result = {"pass": pass_num, "winner": winner, "scores": scores, "num_valid": len(valid), "judge_details": jdetails, "elapsed": round(elapsed, 1)}
    (pass_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"    ↳ Winner: {winner} (A={scores['A']}, B={scores['B']}, AB={scores['AB']}) [{elapsed:.0f}s]")
    return winner, vmap[winner], result


async def main():
    root = Path(__file__).parent
    task_path = root.parent.parent / "tasks" / "task_01_constrained.md"
    task_prompt = task_path.read_text().strip()
    out_dir = root / "results_constrained" / "task_01"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Constrained scope test")
    print(f"Model: {MODEL} (author temp={AUTHOR_TEMP}, judge temp={JUDGE_TEMP})")
    print(f"Judges: {NUM_JUDGES}, convergence: {CONVERGENCE}")
    print()

    init_file = out_dir / "initial_a.md"
    if init_file.exists():
        current_a = init_file.read_text()
        print(f"  Using existing initial A ({len(current_a.split())} words)")
    else:
        print("  Generating initial A...")
        current_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
        init_file.write_text(current_a)
        print(f"  Initial A: {len(current_a.split())} words")

    streak = 0
    history = []

    for p in range(1, MAX_PASSES + 1):
        print(f"\n  ━━━ Pass {p} (streak: {streak}/{CONVERGENCE}) ━━━")
        winner, winner_text, result = await run_pass(task_prompt, current_a, p, out_dir / f"pass_{p:02d}")
        history.append({"pass": p, "winner": winner, "scores": result.get("scores", {}), "words": len(winner_text.split())})

        if winner == "A":
            streak += 1
        else:
            streak = 0
            current_a = winner_text
            (out_dir / f"incumbent_after_pass_{p:02d}.md").write_text(current_a)

        if streak >= CONVERGENCE:
            print(f"\n  ✔ Converged after {p} passes")
            break

    (out_dir / "final_output.md").write_text(current_a)
    (out_dir / "history.json").write_text(json.dumps(history, indent=2))
    wc_traj = " → ".join(str(h["words"]) for h in history)
    print(f"\n  Final: {len(current_a.split())} words")
    print(f"  History: {' → '.join(h['winner'] for h in history)}")
    print(f"  Word counts: {wc_traj}")


if __name__ == "__main__":
    asyncio.run(main())
