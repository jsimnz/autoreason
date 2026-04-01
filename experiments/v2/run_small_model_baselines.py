#!/usr/bin/env python3
"""
Run all refinement baselines with cheap models to compare against autoreason.

For each cheap model, run:
  - single pass (already have from small_vs_big)
  - autoreason (already have from small_vs_big)
  - critique & revise (15 passes)
  - harsh critic (15 passes)
  - improve this (15 passes)
  - conservative (15 passes)

Then 7-judge eval comparing all 6 methods at the same model tier.
This measures whether autoreason's advantage is *disproportionately* large
for weaker models vs the same comparison at frontier tier.

Usage:
    python run_small_model_baselines.py --model haiku35 --task pitch
    python run_small_model_baselines.py --model haiku35 --task all
"""

import argparse
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

CHEAP_MODELS = {
    "haiku35": "openrouter/anthropic/claude-3.5-haiku",
}

JUDGE_MODEL = "anthropic/claude-sonnet-4-20250514"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
NUM_PASSES = 15
NUM_JUDGES = 7

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

AUTHOR_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Follow all constraints exactly."
)

COT_JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no authorship stake. Think carefully."
)

BASELINE_PROMPTS = {
    "improve_this": "Improve this document. Make it stronger, more precise, and tighter. Follow all original constraints.\n\n---\n{current}\n---\n\nProduce the complete improved document.",
    "critique_and_revise": "Review this document critically. Find real problems. Then revise to fix every problem. Follow all original constraints.\n\n---\n{current}\n---\n\nProduce the complete revised document.",
    "conservative": "Make changes only if genuinely wrong or weak. If already good, leave as is. Follow all original constraints.\n\n---\n{current}\n---\n\nProduce the complete document.",
    "harsh_critic": "Find every flaw in this document. Rewrite from scratch to address all of them. Follow all original constraints.\n\n---\n{current}\n---\n\nProduce the complete revised document.",
}

JUDGE_EVAL = """ORIGINAL TASK:
---
{task_prompt}
---

{n} teams independently improved a document using different refinement methods with the same underlying model.

{proposals}

For each version, think step by step:
1. Does it follow all stated constraints?
2. Is the content specific, actionable, and well-justified?
3. Does every sentence earn its place?

Rank all from best to worst:

RANKING: {ranking_slots}"""


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


async def run_baseline(task_prompt, model, baseline_name, baseline_prompt, initial_a, out_dir, num_passes=NUM_PASSES):
    """Run a baseline refinement for num_passes."""
    out_dir.mkdir(parents=True, exist_ok=True)
    final_file = out_dir / "final_output.md"
    if final_file.exists():
        text = final_file.read_text()
        print(f"    {baseline_name}: cached ({len(text.split())} words)")
        return text

    print(f"    {baseline_name}: {num_passes} passes...", end="", flush=True)
    current = initial_a
    for p in range(num_passes):
        current = await call_llm(AUTHOR_SYSTEM, baseline_prompt.format(current=current),
                                  model, AUTHOR_TEMP, MAX_TOKENS)
        if (p + 1) % 5 == 0:
            print(f" {p+1}", end="", flush=True)
    final_file.write_text(current)
    print(f" → {len(current.split())}w")
    return current


async def run_eval(task_prompt, methods, out_dir):
    """7-judge blind panel."""
    out_dir.mkdir(parents=True, exist_ok=True)

    results_file = out_dir / "results.json"
    if results_file.exists():
        print(f"    Eval: cached")
        return json.loads(results_file.read_text())

    method_names = list(methods.keys())
    n = len(method_names)
    labels = list("ABCDEFG")[:n]
    ranking_slots = ", ".join(f"[{l}]" for l in labels)

    judge_tasks, judge_orders = [], []
    for _ in range(NUM_JUDGES):
        shuffled = method_names.copy()
        random.shuffle(shuffled)
        order = {labels[i]: shuffled[i] for i in range(n)}
        judge_orders.append(order)
        parts = [f"VERSION {labels[i]}:\n---\n{methods[order[labels[i]]]}\n---" for i in range(n)]
        judge_tasks.append(call_llm(
            COT_JUDGE_SYSTEM,
            JUDGE_EVAL.format(task_prompt=task_prompt, n=n,
                              proposals="\n\n".join(parts), ranking_slots=ranking_slots),
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
    print(f"\n    {'Method':<25} {'Borda':>6}/{max_borda} {'1st':>5} {'Words':>7}")
    print(f"    {'-'*50}")
    for method, score in sorted_methods:
        wc = len(methods[method].split())
        print(f"    {method:<25} {score:>6} {first_place[method]:>5} {wc:>7}")

    results = {
        "valid_judges": valid, "max_borda": max_borda,
        "borda": borda, "first_place": first_place,
        "word_counts": {m: len(methods[m].split()) for m in method_names},
    }
    results_file.write_text(json.dumps(results, indent=2))
    return results


async def run_task(task_name, task_prompt, model_key, model_id, base_dir):
    print(f"\n{'='*60}")
    print(f"Task: {task_name} | Model: {model_key}")
    print(f"{'='*60}")

    task_dir = base_dir / task_name
    task_dir.mkdir(parents=True, exist_ok=True)

    methods = {}

    # Get initial A (shared starting point for all methods)
    init_file = task_dir / "initial_a.md"
    if init_file.exists():
        initial_a = init_file.read_text()
    else:
        # Check if small_vs_big already has one
        svb_init = base_dir.parent / "results_small_vs_big" / task_name / f"{model_key}_single" / "final_output.md"
        svb_ar_init = base_dir.parent / "results_small_vs_big" / task_name / f"{model_key}_autoreason" / "initial_a.md"
        if svb_ar_init.exists():
            initial_a = svb_ar_init.read_text()
        else:
            print(f"  Generating initial A...")
            initial_a = await call_llm(AUTHOR_SYSTEM,
                f"{task_prompt}\n\nProduce your response now.",
                model_id, AUTHOR_TEMP, MAX_TOKENS)
        init_file.write_text(initial_a)
    print(f"  Initial A: {len(initial_a.split())} words")

    # Single pass (just the initial)
    methods["single_pass"] = initial_a

    # Autoreason (reuse from small_vs_big if exists)
    ar_file = base_dir.parent / "results_small_vs_big" / task_name / f"{model_key}_autoreason" / "final_output.md"
    if ar_file.exists():
        methods["autoreason"] = ar_file.read_text()
        print(f"  autoreason: reusing ({len(methods['autoreason'].split())} words)")
    else:
        print(f"  WARNING: autoreason output not found at {ar_file}, skipping")

    # Run all baselines
    for bname, bprompt in BASELINE_PROMPTS.items():
        methods[bname] = await run_baseline(
            task_prompt, model_id, bname, bprompt, initial_a,
            task_dir / bname)

    # Eval
    print(f"\n  --- 7-Judge Evaluation ---")
    results = await run_eval(task_prompt, methods, task_dir / "eval")
    return results


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="haiku35", choices=list(CHEAP_MODELS.keys()))
    parser.add_argument("--task", default="all", choices=list(TASKS.keys()) + ["all"])
    args = parser.parse_args()

    model_key = args.model
    model_id = CHEAP_MODELS[model_key]

    root = Path(__file__).parent
    base_dir = root / f"results_small_model_baselines_{model_key}"
    base_dir.mkdir(parents=True, exist_ok=True)

    print(f"Small Model Baseline Comparison")
    print(f"Model: {model_key} ({model_id})")
    print(f"Judge: {JUDGE_MODEL}")

    tasks_to_run = list(TASKS.items()) if args.task == "all" else [(args.task, TASKS[args.task])]

    all_results = {}
    for task_name, task_prompt in tasks_to_run:
        r = await run_task(task_name, task_prompt, model_key, model_id, base_dir)
        all_results[task_name] = r

    # Summary
    print(f"\n\n{'='*60}")
    print(f"SUMMARY: {model_key} — autoreason vs baselines")
    print(f"{'='*60}")
    for task_name, r in all_results.items():
        print(f"\n  {task_name}:")
        sorted_m = sorted(r["borda"].items(), key=lambda x: -x[1])
        for method, score in sorted_m:
            marker = " ←" if method == "autoreason" else ""
            print(f"    {method:<25} {score:>4} Borda  {r['first_place'].get(method,0):>2} 1st{marker}")

    (base_dir / "all_results.json").write_text(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
