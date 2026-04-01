#!/usr/bin/env python3
"""
Monte Carlo: 5 independent runs of autoreason on constrained task 3 (AI policy memo)
with Sonnet 4.6. Tests whether different random paths converge to similar quality.

After all runs complete, a 7-judge panel compares all 5 final outputs pairwise
to measure how tightly they cluster.

Usage:
    python run_monte_carlo_constrained.py              # run all 5
    python run_monte_carlo_constrained.py --run 3      # run only run 3
    python run_monte_carlo_constrained.py --eval-only   # skip runs, just evaluate
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

MODEL = "anthropic/claude-sonnet-4-6"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
NUM_JUDGES_INLOOP = 3
NUM_JUDGES_EVAL = 7
MAX_PASSES = 25
CONVERGENCE = 2
NUM_RUNS = 5

AUTHOR_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Avoid generic advice. "
    "Follow all constraints exactly as stated in the task."
)
CRITIC_SYSTEM = (
    "You are a critical reviewer. Your only job is to find real problems "
    "with the document you are given. Be specific and concrete. Do not "
    "suggest fixes or improvements — only identify weaknesses. "
    "Pay special attention to whether the output follows the stated constraints."
)
AUTHOR_B_SYSTEM = (
    "You are a senior consultant revising a document based on specific criticisms. "
    "Address each valid criticism directly. Do not make changes that aren't "
    "motivated by an identified problem. Follow all constraints exactly."
)
SYNTHESIZER_SYSTEM = (
    "You are a senior consultant. You are given two versions of a document as equal inputs. "
    "Take the strongest elements from each and produce a coherent synthesis. "
    "This is not a compromise — pick the best answer per dimension. "
    "Follow all constraints exactly."
)
COT_JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no authorship stake. "
    "Think carefully before deciding."
)

GENERATE_A = "{task_prompt}\n\nProduce your response now."

CRITIC_PROMPT = """Here is a document produced for the following task:

ORIGINAL TASK AND CONSTRAINTS:
---
{task_prompt}
---

DOCUMENT TO REVIEW:
---
{version_a}
---

Find real problems. Focus on constraint violations, wrong assumptions, missing required elements, unnecessary filler.
Do NOT propose fixes. Just the problems."""

AUTHOR_B_PROMPT = """ORIGINAL TASK AND CONSTRAINTS:
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

Revise the document to address these problems. For each change, state which problem it fixes."""

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

Produce a synthesis that keeps the strongest elements from both."""

JUDGE_3WAY = """ORIGINAL TASK:
---
{task_prompt}
---

{judge_proposals}

For each version, think step by step about constraint adherence, specificity, and quality.
Rank all three from best to worst:

RANKING: [best], [second], [worst]

Where each slot is 1, 2, or 3."""

JUDGE_5WAY = """ORIGINAL TASK:
---
{task_prompt}
---

Five independent teams produced documents for this task using the same method but different random seeds. 
Evaluate which outputs best accomplish the task.

{proposals}

For each version, think step by step:
1. Does it follow all stated constraints?
2. Is the content specific and well-justified?
3. Which items are most actionable?

Rank all five from best to worst:

RANKING: [best], [second], [third], [fourth], [worst]

Where each slot is A, B, C, D, or E."""


async def call_llm(system, user, model=MODEL, temperature=0.7, max_tokens=MAX_TOKENS, max_retries=8):
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


def randomize_for_judge(va, vb, vab):
    versions = [("A", va), ("B", vb), ("AB", vab)]
    random.shuffle(versions)
    order = {}
    parts = []
    for i, (label, content) in enumerate(versions, 1):
        order[str(i)] = label
        parts.append(f"PROPOSAL {i}:\n---\n{content}\n---")
    return "\n\n".join(parts), order


def parse_ranking_3way(text):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            nums = [c for c in raw if c in ("1", "2", "3")]
            if len(nums) >= 2:
                return nums
    return None


def parse_ranking_5way(text, valid_chars="ABCDE"):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            items = [c for c in raw.upper() if c in valid_chars]
            if len(items) >= 3:
                return items
    return None


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
    critic = await call_llm(CRITIC_SYSTEM, CRITIC_PROMPT.format(
        version_a=current_a, task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "critic.md").write_text(critic)

    print(f"    → Author B...")
    vb = await call_llm(AUTHOR_B_SYSTEM, AUTHOR_B_PROMPT.format(
        task_prompt=task_prompt, version_a=current_a, critic=critic), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_b.md").write_text(vb)

    print(f"    → Synthesizer...")
    if random.random() < 0.5:
        vx, vy = current_a, vb
    else:
        vx, vy = vb, current_a
    vab = await call_llm(SYNTHESIZER_SYSTEM, SYNTHESIZER_PROMPT.format(
        task_prompt=task_prompt, version_x=vx, version_y=vy), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_ab.md").write_text(vab)

    print(f"    → Judges ({NUM_JUDGES_INLOOP})...")
    jtasks, jorders = [], []
    for _ in range(NUM_JUDGES_INLOOP):
        proposals, order = randomize_for_judge(current_a, vb, vab)
        jorders.append(order)
        jtasks.append(call_llm(COT_JUDGE_SYSTEM, JUDGE_3WAY.format(
            task_prompt=task_prompt, judge_proposals=proposals), MODEL, JUDGE_TEMP, MAX_TOKENS))

    jresps = await asyncio.gather(*jtasks, return_exceptions=True)
    rankings, jdetails = [], []
    for j, (resp, order) in enumerate(zip(jresps, jorders)):
        if isinstance(resp, Exception):
            rankings.append(None)
            jdetails.append({"error": str(resp)})
        else:
            r = parse_ranking_3way(resp)
            if r:
                r = [order.get(n, n) for n in r]
            rankings.append(r)
            jdetails.append({"ranking": r, "order": order, "raw": resp})
            print(f"      J{j+1}: {' > '.join(r) if r else 'PARSE_ERROR'}")

    winner, scores, valid = aggregate_3way(rankings)
    elapsed = time.time() - t0
    vmap = {"A": current_a, "B": vb, "AB": vab}
    result = {"pass": pass_num, "winner": winner, "scores": scores,
              "num_valid": len(valid), "judge_details": jdetails, "elapsed": round(elapsed, 1)}
    (pass_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"    ↳ {winner} (A={scores['A']}, B={scores['B']}, AB={scores['AB']}) [{elapsed:.0f}s]")
    return winner, vmap[winner], result


async def run_single(task_prompt, run_dir, run_num):
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*50}")
    print(f"  Run {run_num}")
    print(f"{'='*50}")

    # Each run generates its own initial A (different random seed)
    init_file = run_dir / "initial_a.md"
    if init_file.exists():
        current_a = init_file.read_text()
        print(f"  Using existing initial A ({len(current_a.split())} words)")
    else:
        print("  Generating initial A...")
        current_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt),
                                    MODEL, AUTHOR_TEMP, MAX_TOKENS)
        init_file.write_text(current_a)
        print(f"  Initial A: {len(current_a.split())} words")

    streak, history = 0, []
    for p in range(1, MAX_PASSES + 1):
        print(f"\n  Pass {p} (streak: {streak}/{CONVERGENCE})")
        winner, winner_text, result = await run_pass(
            task_prompt, current_a, p, run_dir / f"pass_{p:02d}")
        history.append({"pass": p, "winner": winner, "scores": result.get("scores", {}),
                        "words": len(winner_text.split())})
        if winner == "A":
            streak += 1
        else:
            streak = 0
            current_a = winner_text
            (run_dir / f"incumbent_after_{p:02d}.md").write_text(current_a)
        if streak >= CONVERGENCE:
            print(f"\n  ✔ Converged after {p} passes")
            break

    (run_dir / "final_output.md").write_text(current_a)
    (run_dir / "history.json").write_text(json.dumps(history, indent=2))
    converged = streak >= CONVERGENCE
    print(f"  Final: {len(current_a.split())} words, {'converged' if converged else 'did NOT converge'}")
    return current_a, history, converged


async def run_cross_eval(task_prompt, outputs, out_dir):
    """7-judge panel comparing all 5 MC outputs to measure clustering."""
    out_dir.mkdir(parents=True, exist_ok=True)
    method_names = list(outputs.keys())
    labels = list("ABCDE")[:len(method_names)]

    print(f"\n{'='*50}")
    print(f"  Cross-Evaluation: {len(method_names)} MC outputs")
    print(f"{'='*50}")

    judge_tasks, judge_orders = [], []
    for _ in range(NUM_JUDGES_EVAL):
        shuffled = method_names.copy()
        random.shuffle(shuffled)
        order = {labels[i]: shuffled[i] for i in range(len(method_names))}
        judge_orders.append(order)
        parts = [f"VERSION {labels[i]}:\n---\n{outputs[order[labels[i]]]}\n---"
                 for i in range(len(method_names))]
        judge_tasks.append(call_llm(
            COT_JUDGE_SYSTEM,
            JUDGE_5WAY.format(task_prompt=task_prompt, proposals="\n\n".join(parts)),
            MODEL, JUDGE_TEMP, MAX_TOKENS))

    responses = await asyncio.gather(*judge_tasks, return_exceptions=True)
    borda = {n: 0 for n in method_names}
    first_place = {n: 0 for n in method_names}
    points = [5, 4, 3, 2, 1]
    valid = 0

    for j, (resp, order) in enumerate(zip(responses, judge_orders)):
        if isinstance(resp, Exception):
            print(f"  Judge {j+1}: ERROR")
            continue
        ranking = parse_ranking_5way(resp, "".join(labels))
        if not ranking:
            print(f"  Judge {j+1}: PARSE FAILED")
            (out_dir / f"judge_{j+1}_raw.txt").write_text(str(resp))
            continue
        valid += 1
        mapped = [order.get(l, l) for l in ranking[:len(method_names)]]
        for pos, method in enumerate(mapped):
            if method in borda and pos < len(points):
                borda[method] += points[pos]
        if mapped[0] in first_place:
            first_place[mapped[0]] += 1
        print(f"  Judge {j+1}: {' > '.join(mapped[:3])}...")
        (out_dir / f"judge_{j+1}_raw.txt").write_text(resp)

    max_borda = valid * 5
    sorted_methods = sorted(borda.items(), key=lambda x: -x[1])

    print(f"\n  {'Run':<12} {'Borda':>8}/{max_borda} {'1st':>5} {'Words':>7}")
    print(f"  {'-'*40}")
    for method, score in sorted_methods:
        wc = len(outputs[method].split())
        print(f"  {method:<12} {score:>8} {first_place[method]:>5} {wc:>7}")

    # Clustering metric: std dev of Borda scores (lower = tighter cluster)
    scores = list(borda.values())
    mean_score = sum(scores) / len(scores)
    std_dev = (sum((s - mean_score) ** 2 for s in scores) / len(scores)) ** 0.5
    print(f"\n  Borda mean: {mean_score:.1f}, std: {std_dev:.1f}")
    print(f"  Clustering: {'tight' if std_dev < 3 else 'moderate' if std_dev < 6 else 'spread'}")

    results = {
        "valid_judges": valid, "borda": borda, "first_place": first_place,
        "word_counts": {n: len(outputs[n].split()) for n in method_names},
        "borda_mean": round(mean_score, 1), "borda_std": round(std_dev, 1),
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    return results


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=int, help="Run only this run number (1-5)")
    parser.add_argument("--eval-only", action="store_true", help="Skip runs, just evaluate")
    args = parser.parse_args()

    root = Path(__file__).parent
    task_path = root.parent.parent / "tasks" / "task_03_constrained.md"
    task_prompt = task_path.read_text().strip()
    base_dir = root / "results_monte_carlo_constrained"
    base_dir.mkdir(parents=True, exist_ok=True)

    print(f"Monte Carlo: Constrained Task 3 (Policy Memo), Sonnet 4.6")
    print(f"Model: {MODEL}, {NUM_RUNS} runs, max {MAX_PASSES} passes, k={CONVERGENCE}")

    runs_to_do = [args.run] if args.run else list(range(1, NUM_RUNS + 1))

    if not args.eval_only:
        for run_num in runs_to_do:
            run_dir = base_dir / f"run_{run_num:02d}"
            await run_single(task_prompt, run_dir, run_num)

    # Cross-evaluation
    outputs = {}
    summaries = []
    for run_num in range(1, NUM_RUNS + 1):
        run_dir = base_dir / f"run_{run_num:02d}"
        final = run_dir / "final_output.md"
        hist = run_dir / "history.json"
        if final.exists():
            outputs[f"run_{run_num}"] = final.read_text()
            if hist.exists():
                h = json.loads(hist.read_text())
                winners = "".join(x["winner"][0] for x in h)
                words = [x["words"] for x in h]
                converged = any(
                    all(x["winner"] == "A" for x in h[i:i+CONVERGENCE])
                    for i in range(len(h) - CONVERGENCE + 1)
                )
                summaries.append({
                    "run": run_num, "passes": len(h), "converged": converged,
                    "final_words": words[-1] if words else 0, "trajectory": winners
                })

    if len(outputs) >= 2:
        print(f"\n\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"{'Run':>5} {'Passes':>7} {'Conv':>6} {'Words':>7} {'Trajectory'}")
        print(f"{'-'*55}")
        for s in summaries:
            print(f"  {s['run']:>3} {s['passes']:>7} {'Yes' if s['converged'] else 'No':>6} "
                  f"{s['final_words']:>7} {s['trajectory']}")

        word_counts = [s["final_words"] for s in summaries]
        if word_counts:
            wc_mean = sum(word_counts) / len(word_counts)
            wc_std = (sum((w - wc_mean) ** 2 for w in word_counts) / len(word_counts)) ** 0.5
            print(f"\n  Word count: mean={wc_mean:.0f}, std={wc_std:.0f}, "
                  f"range={min(word_counts)}-{max(word_counts)}")
            conv_rate = sum(1 for s in summaries if s["converged"]) / len(summaries)
            print(f"  Convergence rate: {conv_rate*100:.0f}%")

        await run_cross_eval(task_prompt, outputs, base_dir / "cross_eval")
    else:
        print(f"\n  Only {len(outputs)} runs completed, need at least 2 for cross-eval")

    (base_dir / "summary.json").write_text(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
