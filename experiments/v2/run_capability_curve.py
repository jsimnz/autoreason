#!/usr/bin/env python3
"""
Experiment 1: More points on the capability curve.

Run all baselines with Gemini Flash and Llama 8B (we already have Haiku and Sonnet 4).
This gives us 4 model tiers to plot autoreason's advantage margin against capability.

For each model, run:
  - single pass
  - autoreason (reuse from small_vs_big if exists)
  - critique & revise (15 passes)
  - harsh critic (15 passes)

Then eval with Sonnet 4 judges.

Usage:
    python run_capability_curve.py --model gemini_flash --task pitch
    python run_capability_curve.py --model llama8b --task all
    python run_capability_curve.py --model all --task all
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

MODELS = {
    "gemini_flash": "openrouter/google/gemini-2.0-flash-001",
    "llama8b": "openrouter/meta-llama/llama-3.1-8b-instruct",
}

SONNET = "anthropic/claude-sonnet-4-20250514"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
NUM_PASSES = 15
NUM_JUDGES_INLOOP = 3
NUM_JUDGES_EVAL = 7
MAX_AR_PASSES = 15
CONVERGENCE = 2

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
CRITIC_SYSTEM = "You are a critical reviewer. Find real problems only. Be specific. Do not suggest fixes."
AUTHOR_B_SYSTEM = "You are revising a document based on specific criticisms. Address each valid criticism. Do not make unmotivated changes. Follow all constraints."
SYNTHESIZER_SYSTEM = "You are given two versions as equal inputs. Take the strongest elements from each and produce a coherent synthesis. Follow all constraints."
COT_JUDGE_SYSTEM = "You are an independent evaluator. You have no authorship stake. Think carefully."

BASELINE_PROMPTS = {
    "critique_and_revise": "Review this document critically. Find real problems. Then revise to fix every problem. Follow all original constraints.\n\n---\n{current}\n---\n\nProduce the complete revised document.",
    "harsh_critic": "Find every flaw in this document. Rewrite from scratch to address all of them. Follow all original constraints.\n\n---\n{current}\n---\n\nProduce the complete revised document.",
}

GENERATE_A = "{task_prompt}\n\nProduce your response now."
CRITIC_PROMPT = "TASK:\n---\n{task_prompt}\n---\n\nDOCUMENT:\n---\n{version_a}\n---\n\nFind real problems. Do NOT propose fixes."
AUTHOR_B_PROMPT = "TASK:\n---\n{task_prompt}\n---\n\nDOCUMENT:\n---\n{version_a}\n---\n\nPROBLEMS:\n---\n{critic}\n---\n\nRevise to address these problems."
SYNTHESIZER_PROMPT = "TASK:\n---\n{task_prompt}\n---\n\nVERSION X:\n---\n{version_x}\n---\n\nVERSION Y:\n---\n{version_y}\n---\n\nSynthesize: keep strongest elements from both."
JUDGE_3WAY = "ORIGINAL TASK:\n---\n{task_prompt}\n---\n\n{judge_proposals}\n\nThink step by step. Rank all three:\nRANKING: [best], [second], [worst]\nWhere each slot is 1, 2, or 3."


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


async def run_autoreason(task_prompt, author_model, out_dir, label=""):
    out_dir.mkdir(parents=True, exist_ok=True)
    final_file = out_dir / "final_output.md"
    if final_file.exists():
        text = final_file.read_text()
        print(f"  {label}: cached ({len(text.split())} words)")
        return text

    print(f"  {label}: running...")
    current_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt),
                                author_model, AUTHOR_TEMP, MAX_TOKENS)
    (out_dir / "initial_a.md").write_text(current_a)

    streak, history = 0, []
    for p in range(1, MAX_AR_PASSES + 1):
        pass_dir = out_dir / f"pass_{p:02d}"
        pass_dir.mkdir(parents=True, exist_ok=True)
        (pass_dir / "version_a.md").write_text(current_a)

        critic = await call_llm(CRITIC_SYSTEM, CRITIC_PROMPT.format(
            version_a=current_a, task_prompt=task_prompt), author_model, AUTHOR_TEMP, MAX_TOKENS)
        vb = await call_llm(AUTHOR_B_SYSTEM, AUTHOR_B_PROMPT.format(
            task_prompt=task_prompt, version_a=current_a, critic=critic), author_model, AUTHOR_TEMP, MAX_TOKENS)
        vx, vy = (current_a, vb) if random.random() < 0.5 else (vb, current_a)
        vab = await call_llm(SYNTHESIZER_SYSTEM, SYNTHESIZER_PROMPT.format(
            task_prompt=task_prompt, version_x=vx, version_y=vy), author_model, AUTHOR_TEMP, MAX_TOKENS)

        (pass_dir / "critic.md").write_text(critic)
        (pass_dir / "version_b.md").write_text(vb)
        (pass_dir / "version_ab.md").write_text(vab)

        # Strong judges
        jtasks, jorders = [], []
        for _ in range(NUM_JUDGES_INLOOP):
            proposals, order = randomize_for_judge(current_a, vb, vab)
            jorders.append(order)
            jtasks.append(call_llm(COT_JUDGE_SYSTEM, JUDGE_3WAY.format(
                task_prompt=task_prompt, judge_proposals=proposals), SONNET, JUDGE_TEMP, MAX_TOKENS))

        jresps = await asyncio.gather(*jtasks, return_exceptions=True)
        rankings = []
        for resp, order in zip(jresps, jorders):
            if isinstance(resp, Exception):
                rankings.append(None)
            else:
                r = parse_ranking(resp, "123")
                if r:
                    r = [order.get(n, n) for n in r]
                rankings.append(r)

        winner, scores, valid = aggregate_3way(rankings)
        history.append({"pass": p, "winner": winner, "scores": scores})
        print(f"    Pass {p}: {winner}")

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
    print(f"  {label}: done ({len(current_a.split())} words)")
    return current_a


async def run_baseline(task_prompt, model, name, prompt_template, initial_a, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    final_file = out_dir / "final_output.md"
    if final_file.exists():
        text = final_file.read_text()
        print(f"    {name}: cached ({len(text.split())} words)")
        return text
    print(f"    {name}: {NUM_PASSES} passes...", end="", flush=True)
    current = initial_a
    for p in range(NUM_PASSES):
        current = await call_llm(AUTHOR_SYSTEM, prompt_template.format(current=current),
                                  model, AUTHOR_TEMP, MAX_TOKENS)
        if (p+1) % 5 == 0:
            print(f" {p+1}", end="", flush=True)
    final_file.write_text(current)
    print(f" → {len(current.split())}w")
    return current


async def run_eval(task_prompt, methods, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    results_file = out_dir / "results.json"
    if results_file.exists():
        return json.loads(results_file.read_text())

    method_names = list(methods.keys())
    n = len(method_names)
    labels = list("ABCDEFG")[:n]

    EVAL_PROMPT = f"""ORIGINAL TASK:
---
{{task_prompt}}
---

{{n}} documents produced by different methods.

{{proposals}}

Think step by step. Rank all from best to worst:
RANKING: {', '.join(f'[{l}]' for l in labels[:n])}"""

    judge_tasks, judge_orders = [], []
    for _ in range(NUM_JUDGES_EVAL):
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
            continue
        ranking = parse_ranking(resp, "".join(labels))
        if not ranking:
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

    results = {"valid_judges": valid, "max_borda": valid * n, "borda": borda,
               "first_place": first_place,
               "word_counts": {m: len(methods[m].split()) for m in method_names}}
    results_file.write_text(json.dumps(results, indent=2))

    sorted_m = sorted(borda.items(), key=lambda x: -x[1])
    print(f"\n    {'Method':<25} {'Borda':>6}/{valid*n}")
    for method, score in sorted_m:
        print(f"    {method:<25} {score:>6}")

    return results


async def run_model_task(model_key, model_id, task_name, task_prompt, base_dir):
    print(f"\n{'='*60}")
    print(f"{model_key} × {task_name}")
    print(f"{'='*60}")

    task_dir = base_dir / model_key / task_name
    task_dir.mkdir(parents=True, exist_ok=True)

    # Single pass
    single_file = task_dir / "single_pass.md"
    if single_file.exists():
        initial_a = single_file.read_text()
    else:
        initial_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt),
                                    model_id, AUTHOR_TEMP, MAX_TOKENS)
        single_file.write_text(initial_a)
    print(f"  Single pass: {len(initial_a.split())} words")

    methods = {"single_pass": initial_a}

    # Autoreason (reuse from small_vs_big if exists, otherwise run new)
    svb_ar = base_dir.parent / "results_small_vs_big" / task_name / f"{model_key}_autoreason" / "final_output.md"
    if svb_ar.exists():
        methods["autoreason"] = svb_ar.read_text()
        print(f"  Autoreason: reusing ({len(methods['autoreason'].split())} words)")
    else:
        methods["autoreason"] = await run_autoreason(
            task_prompt, model_id, task_dir / "autoreason", f"autoreason ({model_key})")

    # Baselines
    for bname, bprompt in BASELINE_PROMPTS.items():
        methods[bname] = await run_baseline(
            task_prompt, model_id, bname, bprompt, initial_a, task_dir / bname)

    # Eval
    print(f"\n  --- Eval ---")
    return await run_eval(task_prompt, methods, task_dir / "eval")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="all", choices=list(MODELS.keys()) + ["all"])
    parser.add_argument("--task", default="all", choices=list(TASKS.keys()) + ["all"])
    args = parser.parse_args()

    root = Path(__file__).parent
    base_dir = root / "results_capability_curve"
    base_dir.mkdir(parents=True, exist_ok=True)

    models = list(MODELS.items()) if args.model == "all" else [(args.model, MODELS[args.model])]
    tasks = list(TASKS.items()) if args.task == "all" else [(args.task, TASKS[args.task])]

    all_results = {}
    for model_key, model_id in models:
        for task_name, task_prompt in tasks:
            r = await run_model_task(model_key, model_id, task_name, task_prompt, base_dir)
            all_results[f"{model_key}_{task_name}"] = r

    # Summary
    print(f"\n\n{'='*60}")
    print("CAPABILITY CURVE SUMMARY")
    print(f"{'='*60}")
    for key, r in all_results.items():
        print(f"\n  {key}:")
        sorted_m = sorted(r["borda"].items(), key=lambda x: -x[1])
        for method, score in sorted_m:
            print(f"    {method:<25} {score:>4}")

    (base_dir / "all_results.json").write_text(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
