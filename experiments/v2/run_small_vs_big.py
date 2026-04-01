#!/usr/bin/env python3
"""
Small model + autoreason vs large model single-pass.

Hypothesis: A cheap model ($0.25/M) with autoreason structure and strong judges
can beat an expensive model ($3/M) generating a single output.

Design:
  A) Haiku 3.5 single-pass (1 call, cheap baseline)
  B) Haiku 3.5 + autoreason (cheap author/critic/synth, Sonnet 4 judges)
  C) Sonnet 4 single-pass (1 call, expensive baseline)
  D) Gemini Flash + autoreason (cheap author/critic/synth, Sonnet 4 judges)
  E) Llama 3.1 8B + autoreason (cheapest author, Sonnet 4 judges)

Final evaluation: 7 Sonnet 4 judges, blind panel, CoT.

Usage:
    python run_small_vs_big.py --task pitch     # constrained pitch
    python run_small_vs_big.py --task policy    # constrained policy
    python run_small_vs_big.py --task all       # all tasks
"""

import argparse
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

# Model configs
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Cheap models (authors/critics/synthesizers) — via OpenRouter
CHEAP_MODELS = {
    "haiku35": "openrouter/anthropic/claude-3.5-haiku",
    "gemini_flash": "openrouter/google/gemini-2.0-flash-001",
    "llama8b": "openrouter/meta-llama/llama-3.1-8b-instruct",
}

# Expensive model (the "big" baseline)
BIG_MODEL = "anthropic/claude-sonnet-4-20250514"

# Judge model (always strong)
JUDGE_MODEL = "anthropic/claude-sonnet-4-20250514"

AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
NUM_JUDGES_INLOOP = 3
NUM_JUDGES_EVAL = 7
MAX_PASSES = 15
CONVERGENCE = 2

# Tasks
TASKS = {}
task_dir = Path(__file__).parent.parent.parent / "tasks"
for name, filename in [
    ("pitch", "task_01_constrained.md"),
    ("policy", "task_03_constrained.md"),
    ("gtm", "task_01.md"),
]:
    p = task_dir / filename
    if p.exists():
        TASKS[name] = p.read_text().strip()

# System prompts
AUTHOR_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Follow all constraints exactly."
)
CRITIC_SYSTEM = (
    "You are a critical reviewer. Find real problems only. Be specific. "
    "Do not suggest fixes. Pay attention to constraint violations."
)
AUTHOR_B_SYSTEM = (
    "You are revising a document based on specific criticisms. "
    "Address each valid criticism. Do not make unmotivated changes. Follow all constraints."
)
SYNTHESIZER_SYSTEM = (
    "You are given two versions as equal inputs. Take the strongest elements "
    "from each and produce a coherent synthesis. Follow all constraints."
)
COT_JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no authorship stake. Think carefully."
)

GENERATE_A = "{task_prompt}\n\nProduce your response now."

CRITIC_PROMPT = """TASK AND CONSTRAINTS:
---
{task_prompt}
---

DOCUMENT TO REVIEW:
---
{version_a}
---

Find real problems: constraint violations, wrong assumptions, missing elements, filler.
Do NOT propose fixes."""

AUTHOR_B_PROMPT = """TASK AND CONSTRAINTS:
---
{task_prompt}
---

CURRENT DOCUMENT:
---
{version_a}
---

PROBLEMS FOUND:
---
{critic}
---

Revise to address these problems. State which problem each change fixes."""

SYNTHESIZER_PROMPT = """TASK:
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

Synthesize: keep the strongest elements from both."""

JUDGE_3WAY = """ORIGINAL TASK:
---
{task_prompt}
---

{judge_proposals}

For each, think step by step about constraint adherence, specificity, quality.
Rank all three: RANKING: [best], [second], [worst]
Where each slot is 1, 2, or 3."""

JUDGE_EVAL = """ORIGINAL TASK:
---
{task_prompt}
---

{num_methods} teams independently produced documents for this task using different methods and models.
Some used expensive frontier models; some used cheap models with structured refinement.
You do not know which is which.

{proposals}

For each version, think step by step:
1. Does it follow all stated constraints?
2. Is the content specific, actionable, and well-justified?
3. Does every sentence earn its place?
4. Overall quality?

Rank all from best to worst:

RANKING: {ranking_format}"""


async def call_llm(system, user, model, temperature=0.7, max_tokens=MAX_TOKENS, max_retries=8):
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


def parse_ranking(text, valid_chars):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            items = [c for c in raw.upper() if c in valid_chars]
            if len(items) >= 2:
                return items
    return None


def randomize_for_judge(va, vb, vab):
    versions = [("A", va), ("B", vb), ("AB", vab)]
    random.shuffle(versions)
    order = {}
    parts = []
    for i, (label, content) in enumerate(versions, 1):
        order[str(i)] = label
        parts.append(f"PROPOSAL {i}:\n---\n{content}\n---")
    return "\n\n".join(parts), order


def aggregate_3way(rankings):
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


async def run_autoreason(task_prompt, author_model, judge_model, out_dir, label=""):
    """Run autoreason with cheap author and strong judges."""
    out_dir.mkdir(parents=True, exist_ok=True)

    final_file = out_dir / "final_output.md"
    if final_file.exists():
        text = final_file.read_text()
        print(f"  {label}: cached ({len(text.split())} words)")
        return text

    print(f"  {label}: generating initial A with {author_model}...")
    current_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt),
                                author_model, AUTHOR_TEMP, MAX_TOKENS)
    (out_dir / "initial_a.md").write_text(current_a)
    print(f"    Initial: {len(current_a.split())} words")

    streak, history = 0, []
    for p in range(1, MAX_PASSES + 1):
        pass_dir = out_dir / f"pass_{p:02d}"
        pass_dir.mkdir(parents=True, exist_ok=True)
        (pass_dir / "version_a.md").write_text(current_a)

        # Critic (cheap)
        critic = await call_llm(CRITIC_SYSTEM, CRITIC_PROMPT.format(
            version_a=current_a, task_prompt=task_prompt), author_model, AUTHOR_TEMP, MAX_TOKENS)
        (pass_dir / "critic.md").write_text(critic)

        # Author B (cheap)
        vb = await call_llm(AUTHOR_B_SYSTEM, AUTHOR_B_PROMPT.format(
            task_prompt=task_prompt, version_a=current_a, critic=critic), author_model, AUTHOR_TEMP, MAX_TOKENS)
        (pass_dir / "version_b.md").write_text(vb)

        # Synthesizer (cheap)
        if random.random() < 0.5:
            vx, vy = current_a, vb
        else:
            vx, vy = vb, current_a
        vab = await call_llm(SYNTHESIZER_SYSTEM, SYNTHESIZER_PROMPT.format(
            task_prompt=task_prompt, version_x=vx, version_y=vy), author_model, AUTHOR_TEMP, MAX_TOKENS)
        (pass_dir / "version_ab.md").write_text(vab)

        # Judges (STRONG — this is the key)
        jtasks, jorders = [], []
        for _ in range(NUM_JUDGES_INLOOP):
            proposals, order = randomize_for_judge(current_a, vb, vab)
            jorders.append(order)
            jtasks.append(call_llm(COT_JUDGE_SYSTEM, JUDGE_3WAY.format(
                task_prompt=task_prompt, judge_proposals=proposals), judge_model, JUDGE_TEMP, MAX_TOKENS))

        jresps = await asyncio.gather(*jtasks, return_exceptions=True)
        rankings = []
        for j, (resp, order) in enumerate(zip(jresps, jorders)):
            if isinstance(resp, Exception):
                rankings.append(None)
            else:
                r = parse_ranking(resp, "123")
                if r:
                    r = [order.get(n, n) for n in r]
                rankings.append(r)

        winner, scores, valid = aggregate_3way(rankings)
        history.append({"pass": p, "winner": winner, "scores": scores, "words": len(current_a.split())})

        w_str = f"A={scores['A']},B={scores['B']},AB={scores['AB']}"
        print(f"    Pass {p}: {winner} ({w_str})")

        if winner == "A":
            streak += 1
        else:
            streak = 0
            vmap = {"A": current_a, "B": vb, "AB": vab}
            current_a = vmap[winner]

        if streak >= CONVERGENCE:
            print(f"    ✔ Converged at pass {p}")
            break

    (out_dir / "final_output.md").write_text(current_a)
    (out_dir / "history.json").write_text(json.dumps(history, indent=2))
    print(f"  {label}: done ({len(current_a.split())} words, {len(history)} passes)")
    return current_a


async def run_single_pass(task_prompt, model, out_dir, label=""):
    """Generate a single output (no refinement)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    final_file = out_dir / "final_output.md"
    if final_file.exists():
        text = final_file.read_text()
        print(f"  {label}: cached ({len(text.split())} words)")
        return text

    print(f"  {label}: generating with {model}...")
    output = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt),
                             model, AUTHOR_TEMP, MAX_TOKENS)
    final_file.write_text(output)
    print(f"  {label}: {len(output.split())} words")
    return output


async def run_eval(task_prompt, methods, out_dir):
    """7-judge blind panel."""
    out_dir.mkdir(parents=True, exist_ok=True)
    method_names = list(methods.keys())
    n = len(method_names)
    labels = list("ABCDEFG")[:n]

    ranking_format = "[" + "], [".join(["best"] + [f"{i}" for i in range(2, n)] + ["worst"]) + "]"

    judge_tasks, judge_orders = [], []
    for _ in range(NUM_JUDGES_EVAL):
        shuffled = method_names.copy()
        random.shuffle(shuffled)
        order = {labels[i]: shuffled[i] for i in range(n)}
        judge_orders.append(order)
        parts = [f"VERSION {labels[i]}:\n---\n{methods[order[labels[i]]]}\n---" for i in range(n)]
        judge_tasks.append(call_llm(
            COT_JUDGE_SYSTEM,
            JUDGE_EVAL.format(task_prompt=task_prompt, num_methods=n,
                              proposals="\n\n".join(parts), ranking_format=ranking_format),
            JUDGE_MODEL, JUDGE_TEMP, MAX_TOKENS))

    responses = await asyncio.gather(*judge_tasks, return_exceptions=True)
    borda = {m: 0 for m in method_names}
    first_place = {m: 0 for m in method_names}
    points = list(range(n, 0, -1))
    valid = 0

    for j, (resp, order) in enumerate(zip(responses, judge_orders)):
        if isinstance(resp, Exception):
            print(f"    Judge {j+1}: ERROR")
            continue
        ranking = parse_ranking(resp, "".join(labels))
        if not ranking:
            print(f"    Judge {j+1}: PARSE FAILED")
            (out_dir / f"judge_{j+1}_raw.txt").write_text(str(resp))
            continue
        valid += 1
        mapped = [order.get(l, l) for l in ranking[:n]]
        for pos, method in enumerate(mapped):
            if method in borda and pos < len(points):
                borda[method] += points[pos]
        if mapped[0] in first_place:
            first_place[mapped[0]] += 1
        print(f"    Judge {j+1}: {' > '.join(mapped[:3])}...")
        (out_dir / f"judge_{j+1}_raw.txt").write_text(resp)

    max_borda = valid * n
    sorted_methods = sorted(borda.items(), key=lambda x: -x[1])

    print(f"\n    {'Method':<30} {'Borda':>6}/{max_borda} {'1st':>5} {'Words':>7}")
    print(f"    {'-'*55}")
    for method, score in sorted_methods:
        wc = len(methods[method].split())
        print(f"    {method:<30} {score:>6} {first_place[method]:>5} {wc:>7}")

    results = {
        "valid_judges": valid, "max_borda": max_borda,
        "borda": borda, "first_place": first_place,
        "word_counts": {m: len(methods[m].split()) for m in method_names},
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    return results


async def run_task(task_name, task_prompt, base_dir):
    print(f"\n{'='*60}")
    print(f"Task: {task_name}")
    print(f"{'='*60}\n")

    methods = {}

    # A) Haiku single-pass (cheap baseline)
    methods["haiku35_single"] = await run_single_pass(
        task_prompt, CHEAP_MODELS["haiku35"],
        base_dir / "haiku35_single", "Haiku 3.5 single")

    # B) Sonnet 4 single-pass (expensive baseline)
    methods["sonnet4_single"] = await run_single_pass(
        task_prompt, BIG_MODEL,
        base_dir / "sonnet4_single", "Sonnet 4 single")

    # C) Haiku 3.5 + autoreason (cheap author, strong judges)
    methods["haiku35_autoreason"] = await run_autoreason(
        task_prompt, CHEAP_MODELS["haiku35"], JUDGE_MODEL,
        base_dir / "haiku35_autoreason", "Haiku 3.5 + autoreason")

    # D) Gemini Flash + autoreason
    methods["flash_autoreason"] = await run_autoreason(
        task_prompt, CHEAP_MODELS["gemini_flash"], JUDGE_MODEL,
        base_dir / "flash_autoreason", "Gemini Flash + autoreason")

    # E) Llama 8B + autoreason
    methods["llama8b_autoreason"] = await run_autoreason(
        task_prompt, CHEAP_MODELS["llama8b"], JUDGE_MODEL,
        base_dir / "llama8b_autoreason", "Llama 8B + autoreason")

    # Evaluation
    print(f"\n  --- 7-Judge Evaluation ---")
    results = await run_eval(task_prompt, methods, base_dir / "eval")
    return results


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="all", choices=list(TASKS.keys()) + ["all"])
    args = parser.parse_args()

    root = Path(__file__).parent
    base_dir = root / "results_small_vs_big"
    base_dir.mkdir(parents=True, exist_ok=True)

    print("Small Model + Autoreason vs Big Model Single-Pass")
    print(f"Cheap models: {', '.join(CHEAP_MODELS.keys())}")
    print(f"Big model: {BIG_MODEL}")
    print(f"Judge model: {JUDGE_MODEL}")

    tasks_to_run = list(TASKS.items()) if args.task == "all" else [(args.task, TASKS[args.task])]

    all_results = {}
    for task_name, task_prompt in tasks_to_run:
        r = await run_task(task_name, task_prompt, base_dir / task_name)
        all_results[task_name] = r

    # Summary
    print(f"\n\n{'='*60}")
    print("OVERALL SUMMARY")
    print(f"{'='*60}")
    for task_name, r in all_results.items():
        print(f"\n  {task_name}:")
        sorted_m = sorted(r["borda"].items(), key=lambda x: -x[1])
        for method, score in sorted_m:
            print(f"    {method:<30} {score:>4} Borda  {r['first_place'][method]:>2} 1st")

    (base_dir / "all_results.json").write_text(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
