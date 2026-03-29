#!/usr/bin/env python3
"""
Run autoreason on the paper itself.

Opus author / mixed judge panel (Opus + Sonnet + Gemini 2.5 Pro via OpenRouter).
Fresh agents per role, convergence at 2 consecutive A wins.
"""

import argparse
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

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

AUTHOR_MODEL = "anthropic/claude-opus-4-20250514"
JUDGE_MODELS = [
    "anthropic/claude-opus-4-20250514",
    "anthropic/claude-sonnet-4-20250514",
    "openrouter/google/gemini-2.5-pro",
]
AUTHOR_TEMP = 0.7
JUDGE_TEMP = 0.3
MAX_TOKENS = 16384
MAX_PASSES = 15
CONVERGENCE_THRESHOLD = 2

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

AUTHOR_A_SYSTEM = (
    "You are a senior ML researcher writing a concise, rigorous research paper. "
    "Write clearly and directly for a technical audience. Every sentence must earn its place. "
    "Use actual numbers from experiments. Do not hedge or pad."
)

STRAWMAN_SYSTEM = (
    "You are a critical peer reviewer for a top ML venue. You have access to the actual "
    "experimental data and methodology. Your job is to find real problems with this paper — "
    "hallucinated or incorrect numbers, wrong methodology descriptions, weak arguments, "
    "missing context, unsupported claims, fabricated results, structural issues. "
    "Check every claim against the provided ground truth data. Be specific and concrete. "
    "Do not suggest fixes."
)

AUTHOR_B_SYSTEM = (
    "You are a senior ML researcher revising a paper based on peer review feedback. "
    "Address each valid criticism directly. Do not make changes that aren't motivated "
    "by an identified problem. Maintain the paper's voice and structure."
)

SYNTHESIZER_SYSTEM = (
    "You are a senior ML researcher. You are given two versions of a paper as equal inputs. "
    "You have no preference between them. Take the strongest elements from each "
    "and produce a coherent synthesis. This is not a compromise — pick the best "
    "answer per section and make them cohere."
)

JUDGE_SYSTEM = (
    "You are an independent reviewer evaluating paper submissions. You have no authorship "
    "stake in any version. Evaluate which version best accomplishes the stated task."
)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

GENERATE_A = "{task_prompt}\n\nWrite the complete paper now."

STRAWMAN_PROMPT = """Here is a research paper draft:

---
{version_a}
---

Here is the actual experimental data and methodology from the repository. Use this as ground truth to fact-check every claim in the paper:

---
{experiment_context}
---

Find real problems with this paper. Focus on:
- Hallucinated or incorrect numbers (check against the ground truth above)
- Wrong descriptions of the methodology (the ground truth shows exactly how it works)
- Fabricated experiments or results not present in the actual data
- Claims not supported by the data presented
- Missing methodology details
- Structural or flow issues
- Anything a reviewer at a top venue would flag

Do NOT propose fixes. Just the problems."""

AUTHOR_B_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Here is a paper draft and the problems identified by a reviewer.

CURRENT DRAFT:
---
{version_a}
---

REVIEWER PROBLEMS:
---
{strawman}
---

Revise the paper to address these problems.
For each change, state which problem it fixes.
Do not make changes that aren't motivated by an identified problem."""

SYNTHESIZER_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Here are two versions of a research paper. Treat them as equal inputs.

VERSION X:
---
{version_x}
---

VERSION Y:
---
{version_y}
---

Produce a synthesis that keeps the strongest elements from both.
Pick the best version of each section and make them cohere."""

JUDGE_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Three paper drafts have been produced independently. Evaluate how well each accomplishes the stated task.

{judge_proposals}

For each draft, evaluate:
1. Which aspects of the task it handles well
2. Which aspects it handles poorly or misses
3. Quality of writing, argumentation, and use of experimental evidence

Then rank all three from best to worst:

RANKING: [best], [second], [worst]

Where each slot is 1, 2, or 3 corresponding to the draft numbers above."""


# ---------------------------------------------------------------------------
# LLM call wrapper
# ---------------------------------------------------------------------------

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
            if "rate" in err or "429" in err or "overloaded" in err or "529" in err:
                wait = (2 ** attempt) * 10
                print(f"    [Rate limited, retrying in {wait}s...]")
                await asyncio.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Failed after {max_retries} retries")


# ---------------------------------------------------------------------------
# Judge helpers
# ---------------------------------------------------------------------------

def randomize_for_judge(version_a, version_b, version_ab):
    versions = [("A", version_a), ("B", version_b), ("AB", version_ab)]
    random.shuffle(versions)
    order_map = {}
    parts = []
    for i, (label, content) in enumerate(versions, 1):
        order_map[str(i)] = label
        parts.append(f"DRAFT {i}:\n---\n{content}\n---")
    return "\n\n".join(parts), order_map


def parse_ranking(text, order_map):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            nums = [c for c in raw if c in ("1", "2", "3")]
            if len(nums) >= 2:
                return [order_map.get(n, n) for n in nums]
    return None


def aggregate_rankings(rankings):
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


# ---------------------------------------------------------------------------
# Single pass
# ---------------------------------------------------------------------------

async def run_pass(task_prompt, current_a, pass_num, pass_dir):
    pass_dir.mkdir(parents=True, exist_ok=True)

    # Check resume
    result_file = pass_dir / "result.json"
    if result_file.exists():
        existing = json.loads(result_file.read_text())
        if existing.get("winner"):
            print(f"    ↳ Skipping (already complete: {existing['winner']})")
            winner = existing["winner"]
            if winner == "A":
                return winner, current_a, existing
            wf = pass_dir / f"version_{winner.lower()}.md"
            return winner, wf.read_text() if wf.exists() else current_a, existing

    t0 = time.time()
    (pass_dir / "version_a.md").write_text(current_a)

    # Load experiment context for strawman fact-checking
    context_path = Path(__file__).parent / "experiment_context.md"
    experiment_context = context_path.read_text() if context_path.exists() else ""

    # Strawman (with ground truth access)
    print(f"    → Strawman (Opus, with ground truth)...")
    strawman = await call_llm(STRAWMAN_SYSTEM,
                               STRAWMAN_PROMPT.format(version_a=current_a, experiment_context=experiment_context),
                               AUTHOR_MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "strawman.md").write_text(strawman)

    # Author B
    print(f"    → Author B (Opus)...")
    version_b = await call_llm(AUTHOR_B_SYSTEM,
                                AUTHOR_B_PROMPT.format(task_prompt=task_prompt, version_a=current_a, strawman=strawman),
                                AUTHOR_MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_b.md").write_text(version_b)

    # Synthesizer
    print(f"    → Synthesizer (Opus)...")
    if random.random() < 0.5:
        vx, vy = current_a, version_b
    else:
        vx, vy = version_b, current_a
    version_ab = await call_llm(SYNTHESIZER_SYSTEM,
                                 SYNTHESIZER_PROMPT.format(task_prompt=task_prompt, version_x=vx, version_y=vy),
                                 AUTHOR_MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_ab.md").write_text(version_ab)

    # Judge panel (mixed models)
    print(f"    → Judge panel ({len(JUDGE_MODELS)} judges: {', '.join(m.split('/')[-1] for m in JUDGE_MODELS)})...")
    judge_tasks = []
    judge_orders = []

    for jmodel in JUDGE_MODELS:
        proposals, order_map = randomize_for_judge(current_a, version_b, version_ab)
        judge_orders.append(order_map)
        judge_tasks.append(
            call_llm(JUDGE_SYSTEM,
                      JUDGE_PROMPT.format(task_prompt=task_prompt, judge_proposals=proposals),
                      jmodel, JUDGE_TEMP, MAX_TOKENS)
        )

    judge_responses = await asyncio.gather(*judge_tasks, return_exceptions=True)

    rankings = []
    judge_details = []
    for j, (response, order_map, jmodel) in enumerate(zip(judge_responses, judge_orders, JUDGE_MODELS)):
        model_short = jmodel.split("/")[-1]
        if isinstance(response, Exception):
            print(f"      {model_short}: ERROR - {response}")
            rankings.append(None)
            judge_details.append({"error": str(response), "model": jmodel})
        else:
            ranking = parse_ranking(response, order_map)
            rankings.append(ranking)
            judge_details.append({
                "ranking": ranking,
                "model": jmodel,
                "presentation_order": order_map,
                "raw_response": response,
            })
            rank_str = " > ".join(ranking) if ranking else "PARSE_ERROR"
            print(f"      {model_short}: {rank_str}")

    winner, scores, valid = aggregate_rankings(rankings)
    elapsed = time.time() - t0

    version_map = {"A": current_a, "B": version_b, "AB": version_ab}
    winner_text = version_map[winner]

    result = {
        "pass": pass_num,
        "winner": winner,
        "scores": scores,
        "judge_details": judge_details,
        "elapsed_seconds": round(elapsed, 1),
    }
    (pass_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"    ↳ Winner: {winner} (A={scores['A']}, B={scores['B']}, AB={scores['AB']}) [{elapsed:.0f}s]")
    return winner, winner_text, result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-passes", type=int, default=MAX_PASSES)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).parent
    task_prompt = (root / "task_prompt.md").read_text().strip()
    out_dir = root / "autoreason_run"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Autoreason paper generation")
    print(f"Author: {AUTHOR_MODEL} (temp={AUTHOR_TEMP})")
    print(f"Judges: {', '.join(m.split('/')[-1] for m in JUDGE_MODELS)} (temp={JUDGE_TEMP})")
    print(f"Max passes: {args.max_passes}, convergence: {CONVERGENCE_THRESHOLD}")
    print()

    # Initial A
    init_file = out_dir / "initial_a.md"
    if init_file.exists():
        print("  Using existing initial A")
        current_a = init_file.read_text()
    elif args.dry_run:
        print("  [DRY RUN]")
        return
    else:
        print("  Generating initial A (Opus)...")
        current_a = await call_llm(AUTHOR_A_SYSTEM, GENERATE_A.format(task_prompt=task_prompt),
                                    AUTHOR_MODEL, AUTHOR_TEMP, MAX_TOKENS)
        init_file.write_text(current_a)
        print(f"  Initial A: {len(current_a.split())} words")

    consecutive_a = 0
    history = []

    for pass_num in range(1, args.max_passes + 1):
        print(f"\n  ━━━ Pass {pass_num} (streak: {consecutive_a}/{CONVERGENCE_THRESHOLD}) ━━━")

        winner, winner_text, result = await run_pass(
            task_prompt, current_a, pass_num, out_dir / f"pass_{pass_num:02d}"
        )

        history.append({"pass": pass_num, "winner": winner, "scores": result.get("scores", {})})

        if winner == "A":
            consecutive_a += 1
        else:
            consecutive_a = 0
            current_a = winner_text
            (out_dir / f"incumbent_after_pass_{pass_num:02d}.md").write_text(current_a)

        if consecutive_a >= CONVERGENCE_THRESHOLD:
            print(f"\n  ✔ Converged after {pass_num} passes")
            break

    (out_dir / "final_paper.md").write_text(current_a)
    (out_dir / "history.json").write_text(json.dumps(history, indent=2))
    print(f"\n  Final: {len(current_a.split())} words")
    print(f"  History: {' → '.join(h['winner'] for h in history)}")


if __name__ == "__main__":
    asyncio.run(main())
