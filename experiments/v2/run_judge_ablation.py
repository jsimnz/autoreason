#!/usr/bin/env python3
"""
Experiment 3: Judge capability ablation.

Haiku autoreason with Haiku judges vs Haiku autoreason with Sonnet judges.
Isolates external evaluation as the variable.

If Haiku+Haiku judges ≈ baselines (bad), and Haiku+Sonnet judges = 42/42,
then it's specifically judge capability that matters, not the architecture.

Runs on all 3 tasks (pitch, policy, gtm), then 7-judge eval (Sonnet) comparing:
  - haiku_autoreason_sonnet_judges (reuse from small_vs_big)
  - haiku_autoreason_haiku_judges (new)
  - haiku_single_pass (reuse)
  - haiku_critique_and_revise (reuse from baselines)
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
NUM_JUDGES_INLOOP = 3
NUM_JUDGES_EVAL = 7
MAX_PASSES = 15
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


async def run_autoreason(task_prompt, author_model, judge_model, out_dir, label=""):
    out_dir.mkdir(parents=True, exist_ok=True)
    final_file = out_dir / "final_output.md"
    if final_file.exists():
        text = final_file.read_text()
        print(f"  {label}: cached ({len(text.split())} words)")
        return text

    print(f"  {label}: generating...")
    current_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt),
                                author_model, AUTHOR_TEMP, MAX_TOKENS)
    (out_dir / "initial_a.md").write_text(current_a)

    streak, history = 0, []
    for p in range(1, MAX_PASSES + 1):
        pass_dir = out_dir / f"pass_{p:02d}"
        pass_dir.mkdir(parents=True, exist_ok=True)
        (pass_dir / "version_a.md").write_text(current_a)

        critic = await call_llm(CRITIC_SYSTEM, CRITIC_PROMPT.format(
            version_a=current_a, task_prompt=task_prompt), author_model, AUTHOR_TEMP, MAX_TOKENS)
        (pass_dir / "critic.md").write_text(critic)

        vb = await call_llm(AUTHOR_B_SYSTEM, AUTHOR_B_PROMPT.format(
            task_prompt=task_prompt, version_a=current_a, critic=critic), author_model, AUTHOR_TEMP, MAX_TOKENS)
        (pass_dir / "version_b.md").write_text(vb)

        vx, vy = (current_a, vb) if random.random() < 0.5 else (vb, current_a)
        vab = await call_llm(SYNTHESIZER_SYSTEM, SYNTHESIZER_PROMPT.format(
            task_prompt=task_prompt, version_x=vx, version_y=vy), author_model, AUTHOR_TEMP, MAX_TOKENS)
        (pass_dir / "version_ab.md").write_text(vab)

        # Judges
        jtasks, jorders = [], []
        for _ in range(NUM_JUDGES_INLOOP):
            proposals, order = randomize_for_judge(current_a, vb, vab)
            jorders.append(order)
            jtasks.append(call_llm(COT_JUDGE_SYSTEM, JUDGE_3WAY.format(
                task_prompt=task_prompt, judge_proposals=proposals), judge_model, JUDGE_TEMP, MAX_TOKENS))

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
        history.append({"pass": p, "winner": winner, "scores": scores, "words": len(current_a.split())})
        print(f"    Pass {p}: {winner} (A={scores['A']},B={scores['B']},AB={scores['AB']})")

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


async def run_eval(task_prompt, methods, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    results_file = out_dir / "results.json"
    if results_file.exists():
        print(f"    Eval: cached")
        return json.loads(results_file.read_text())

    method_names = list(methods.keys())
    n = len(method_names)
    labels = list("ABCDEFG")[:n]

    EVAL_PROMPT = f"""ORIGINAL TASK:
---
{{task_prompt}}
---

{{n}} documents produced by different refinement methods with the same base model.

{{proposals}}

Think step by step about each. Rank all from best to worst:

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
    print(f"\n    {'Method':<35} {'Borda':>6}/{max_borda} {'1st':>5}")
    print(f"    {'-'*50}")
    for method, score in sorted_methods:
        print(f"    {method:<35} {score:>6} {first_place[method]:>5}")

    results = {"valid_judges": valid, "max_borda": max_borda, "borda": borda,
               "first_place": first_place,
               "word_counts": {m: len(methods[m].split()) for m in method_names}}
    results_file.write_text(json.dumps(results, indent=2))
    return results


async def main():
    root = Path(__file__).parent
    base_dir = root / "results_judge_ablation"
    base_dir.mkdir(parents=True, exist_ok=True)

    print("Judge Capability Ablation: Haiku+Sonnet judges vs Haiku+Haiku judges")
    print(f"Author: {HAIKU}")
    print(f"Judge models: {SONNET} (strong) vs {HAIKU} (weak)")
    print()

    all_results = {}
    for task_name, task_prompt in TASKS.items():
        print(f"\n{'='*60}")
        print(f"Task: {task_name}")
        print(f"{'='*60}")

        task_dir = base_dir / task_name
        methods = {}

        # Haiku + autoreason + HAIKU judges (the ablation)
        methods["autoreason_haiku_judges"] = await run_autoreason(
            task_prompt, HAIKU, HAIKU,
            task_dir / "autoreason_haiku_judges", "autoreason (Haiku judges)")

        # Reuse existing outputs
        svb_dir = root / "results_small_vs_big" / task_name
        bl_dir = root / "results_small_model_baselines_haiku35" / task_name

        ar_sonnet = svb_dir / "haiku35_autoreason" / "final_output.md"
        if ar_sonnet.exists():
            methods["autoreason_sonnet_judges"] = ar_sonnet.read_text()

        single = bl_dir / "initial_a.md"
        if not single.exists():
            single = svb_dir / "haiku35_single" / "final_output.md"
        if single.exists():
            methods["single_pass"] = single.read_text()

        cr = bl_dir / "critique_and_revise" / "final_output.md"
        if cr.exists():
            methods["critique_and_revise"] = cr.read_text()

        print(f"\n  Methods loaded: {list(methods.keys())}")
        print(f"\n  --- 7-Judge Eval (Sonnet judges) ---")
        r = await run_eval(task_prompt, methods, task_dir / "eval")
        all_results[task_name] = r

    print(f"\n\n{'='*60}")
    print("SUMMARY: Judge Ablation")
    print(f"{'='*60}")
    for task_name, r in all_results.items():
        print(f"\n  {task_name}:")
        sorted_m = sorted(r["borda"].items(), key=lambda x: -x[1])
        for method, score in sorted_m:
            print(f"    {method:<35} {score:>4}")

    (base_dir / "all_results.json").write_text(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
