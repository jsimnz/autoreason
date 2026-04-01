#!/usr/bin/env python3
"""
Best-of-N baseline: generate N independent outputs, have judges pick the best.
This is the key control — if best-of-N matches autoreason, the structured
refinement adds no value beyond diversity + selection.

Design:
  - best_of_6_haiku: 6 independent Haiku outputs, Sonnet picks best (matched compute to autoreason)
  - best_of_6_sonnet: 6 independent Sonnet outputs, Sonnet picks best
  - autoreason_haiku: reuse existing (Haiku author, Sonnet judges)
  - autoreason_sonnet: reuse existing Sonnet autoreason output
  - haiku_single: 1 Haiku output
  - sonnet_single: 1 Sonnet output

Final eval: 7 Sonnet judges, blind panel of the best-of-N winner vs autoreason vs single-pass.
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

HAIKU = "openrouter/anthropic/claude-3.5-haiku"
SONNET = "anthropic/claude-sonnet-4-20250514"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
NUM_JUDGES = 7
N = 6  # best-of-N

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

AUTHOR_SYSTEM = "You are a senior consultant producing professional deliverables. Be specific, concrete, and practical. Follow all constraints exactly."
COT_JUDGE_SYSTEM = "You are an independent evaluator. You have no authorship stake. Think carefully."
GENERATE_A = "{task_prompt}\n\nProduce your response now."


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


async def generate_n(task_prompt, model, n, out_dir, label=""):
    """Generate N independent outputs and have Sonnet judges pick the best."""
    out_dir.mkdir(parents=True, exist_ok=True)
    best_file = out_dir / "best_output.md"
    if best_file.exists():
        text = best_file.read_text()
        print(f"  {label}: cached ({len(text.split())} words)")
        return text

    # Generate N candidates
    print(f"  {label}: generating {n} candidates...", end="", flush=True)
    gen_tasks = []
    for i in range(n):
        gen_tasks.append(call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt),
                                   model, AUTHOR_TEMP, MAX_TOKENS))
    candidates = await asyncio.gather(*gen_tasks, return_exceptions=True)
    candidates = [c for c in candidates if isinstance(c, str)]
    print(f" got {len(candidates)}")

    for i, c in enumerate(candidates):
        (out_dir / f"candidate_{i+1}.md").write_text(c)

    if len(candidates) < 2:
        best_file.write_text(candidates[0] if candidates else "")
        return candidates[0] if candidates else ""

    # Tournament: have Sonnet judges rank all N, pick the winner
    # If N > 5, do pairwise rounds
    if len(candidates) <= 5:
        best = await _judge_pool(task_prompt, candidates, out_dir)
    else:
        # Split into groups, judge each, then final
        mid = len(candidates) // 2
        group_a = candidates[:mid]
        group_b = candidates[mid:]
        print(f"    Round 1: group A ({len(group_a)}) vs group B ({len(group_b)})")
        winner_a = await _judge_pool(task_prompt, group_a, out_dir / "round1_a")
        winner_b = await _judge_pool(task_prompt, group_b, out_dir / "round1_b")
        print(f"    Final: comparing top 2")
        best = await _judge_pool(task_prompt, [winner_a, winner_b], out_dir / "final")

    best_file.write_text(best)
    print(f"  {label}: best = {len(best.split())} words")
    return best


async def _judge_pool(task_prompt, candidates, out_dir):
    """Have 3 Sonnet judges rank candidates, return the Borda winner."""
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(candidates)
    labels = list("ABCDEFG")[:n]

    JUDGE_PROMPT = f"""ORIGINAL TASK:
---
{{task_prompt}}
---

{{proposals}}

Think step by step about each. Rank all from best to worst:
RANKING: {', '.join(f'[{l}]' for l in labels)}"""

    judge_tasks, judge_orders = [], []
    for _ in range(3):  # 3 judges for selection, 7 for final eval
        shuffled = list(range(n))
        random.shuffle(shuffled)
        order = {labels[i]: shuffled[i] for i in range(n)}
        judge_orders.append(order)
        parts = [f"VERSION {labels[i]}:\n---\n{candidates[order[labels[i]]]}\n---" for i in range(n)]
        judge_tasks.append(call_llm(COT_JUDGE_SYSTEM,
            JUDGE_PROMPT.format(task_prompt=task_prompt, proposals="\n\n".join(parts)),
            SONNET, JUDGE_TEMP, MAX_TOKENS))

    responses = await asyncio.gather(*judge_tasks, return_exceptions=True)
    scores = [0] * n
    points = list(range(n, 0, -1))

    for resp, order in zip(responses, judge_orders):
        if isinstance(resp, Exception):
            continue
        ranking = parse_ranking(resp, "".join(labels))
        if not ranking:
            continue
        for pos, label in enumerate(ranking[:n]):
            if label in order and pos < len(points):
                scores[order[label]] += points[pos]

    best_idx = max(range(n), key=lambda i: scores[i])
    return candidates[best_idx]


async def run_eval(task_prompt, methods, out_dir):
    """7-judge blind panel."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results_file = out_dir / "results.json"
    if results_file.exists():
        r = json.loads(results_file.read_text())
        print(f"    Eval: cached")
        sorted_m = sorted(r["borda"].items(), key=lambda x: -x[1])
        for method, score in sorted_m:
            print(f"    {method:<30} {score:>4}")
        return r

    method_names = list(methods.keys())
    n = len(method_names)
    labels = list("ABCDEFG")[:n]

    EVAL_PROMPT = f"""ORIGINAL TASK:
---
{{task_prompt}}
---

{{n}} documents produced by different methods — some use single generation, some use iterative refinement, some use sampling + selection.

{{proposals}}

Think step by step about each. Rank all from best to worst:
RANKING: {', '.join(f'[{l}]' for l in labels[:n])}"""

    judge_tasks, judge_orders = [], []
    for _ in range(NUM_JUDGES):
        shuffled = method_names.copy()
        random.shuffle(shuffled)
        order = {labels[i]: shuffled[i] for i in range(n)}
        judge_orders.append(order)
        parts = [f"VERSION {labels[i]}:\n---\n{methods[order[labels[i]]]}\n---" for i in range(n)]
        judge_tasks.append(call_llm(COT_JUDGE_SYSTEM,
            EVAL_PROMPT.format(task_prompt=task_prompt, n=n, proposals="\n\n".join(parts)),
            SONNET, JUDGE_TEMP, MAX_TOKENS))

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
    sorted_m = sorted(borda.items(), key=lambda x: -x[1])
    print(f"\n    {'Method':<30} {'Borda':>6}/{max_borda} {'1st':>5}")
    print(f"    {'-'*45}")
    for method, score in sorted_m:
        print(f"    {method:<30} {score:>6} {first_place[method]:>5}")

    results = {"valid_judges": valid, "max_borda": max_borda, "borda": borda,
               "first_place": first_place,
               "word_counts": {m: len(methods[m].split()) for m in method_names}}
    results_file.write_text(json.dumps(results, indent=2))
    return results


async def main():
    root = Path(__file__).parent
    base_dir = root / "results_best_of_n"
    base_dir.mkdir(parents=True, exist_ok=True)

    print(f"Best-of-N Baseline Comparison")
    print(f"N={N}, Sonnet judges for selection + final eval\n")

    all_results = {}
    for task_name, task_prompt in TASKS.items():
        print(f"\n{'='*60}")
        print(f"Task: {task_name}")
        print(f"{'='*60}")

        task_dir = base_dir / task_name
        methods = {}

        # Best-of-6 Haiku (matched compute: 6 calls ≈ 1 autoreason pass)
        methods["best_of_6_haiku"] = await generate_n(
            task_prompt, HAIKU, N, task_dir / "best_of_6_haiku", "Best-of-6 Haiku")

        # Best-of-6 Sonnet
        methods["best_of_6_sonnet"] = await generate_n(
            task_prompt, SONNET, N, task_dir / "best_of_6_sonnet", "Best-of-6 Sonnet")

        # Reuse existing outputs
        svb_dir = root / "results_small_vs_big" / task_name

        ar_haiku = svb_dir / "haiku35_autoreason" / "final_output.md"
        if ar_haiku.exists():
            methods["autoreason_haiku"] = ar_haiku.read_text()

        sonnet_single = svb_dir / "sonnet4_single" / "final_output.md"
        if sonnet_single.exists():
            methods["sonnet_single"] = sonnet_single.read_text()

        haiku_single = svb_dir / "haiku35_single" / "final_output.md"
        if haiku_single.exists():
            methods["haiku_single"] = haiku_single.read_text()

        print(f"\n  Methods: {list(methods.keys())}")
        print(f"\n  --- 7-Judge Final Eval ---")
        r = await run_eval(task_prompt, methods, task_dir / "eval")
        all_results[task_name] = r

    # Summary
    print(f"\n\n{'='*60}")
    print("BEST-OF-N SUMMARY")
    print(f"{'='*60}")
    for task_name, r in all_results.items():
        print(f"\n  {task_name}:")
        sorted_m = sorted(r["borda"].items(), key=lambda x: -x[1])
        for method, score in sorted_m:
            print(f"    {method:<30} {score:>4} Borda  {r['first_place'].get(method,0):>2} 1st")

    (base_dir / "all_results.json").write_text(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
