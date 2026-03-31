#!/usr/bin/env python3
"""
Test Verdict hierarchical judges on the Sonnet 4.6 scaling problem.
Replaces our 3-judge Borda panel with a Verdict pipeline:
  Judge (rank with explanation) → Verify (check the reasoning) → repeat 3x → MaxPool

Runs 15 passes on Task 2 with Sonnet 4.6. Compares A win rate against baseline.
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

MODEL = "anthropic/claude-sonnet-4-6"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
MAX_PASSES = 15
CONVERGENCE = 2

AUTHOR_SYSTEM = "You are a senior consultant producing professional deliverables. Be specific, concrete, and practical."
CRITIC_SYSTEM = "You are a critical reviewer. Find real problems. Be specific. Do not suggest fixes."
AUTHOR_B_SYSTEM = "You are a senior consultant revising a proposal based on criticisms. Address each valid criticism directly."
SYNTH_SYSTEM = "You are a senior consultant. Take the strongest elements from two versions and produce a coherent synthesis."

GENERATE_A = "{task_prompt}\n\nProduce a complete, detailed proposal."
CRITIC_PROMPT = "Find real problems with this proposal. No fixes.\n\n---\n{version_a}\n---"
AUTHOR_B_PROMPT = "TASK:\n---\n{task_prompt}\n---\n\nCURRENT VERSION:\n---\n{version_a}\n---\n\nCRITIC FINDINGS:\n---\n{critic}\n---\n\nRevise to address these problems."
SYNTH_PROMPT = "TASK:\n---\n{task_prompt}\n---\n\nVERSION X:\n---\n{vx}\n---\n\nVERSION Y:\n---\n{vy}\n---\n\nSynthesize the strongest elements."

# Verdict-style hierarchical judge: rank with explanation, then verify
JUDGE_RANK_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Three proposals:

{proposals}

For each proposal, think step by step:
1. What does it get right about the task?
2. What does it get wrong or miss?
3. Are the numbers and claims defensible?
4. Is the detail level appropriate or bloated?
5. Is this genuinely better, or just different/longer?

After reasoning through each, rank all three from best to worst.
Explain your ranking in 2-3 sentences.

RANKING: [best], [second], [worst]"""

JUDGE_VERIFY_PROMPT = """A judge ranked three proposals for a task. Review their reasoning and ranking.

ORIGINAL TASK:
---
{task_prompt}
---

The three proposals were labeled 1, 2, 3 (randomized).

JUDGE'S REASONING AND RANKING:
---
{judge_output}
---

Verify the judge's reasoning:
1. Did the judge actually evaluate substance, or just prefer the longest/most detailed version?
2. Did the judge identify real quality differences, or just superficial ones?
3. Is the ranking consistent with the stated reasoning?
4. Would you change the ranking? If so, why?

If you agree with the ranking, repeat it. If you disagree, provide your corrected ranking.

RANKING: [best], [second], [worst]"""


async def call_llm(system, user, model=MODEL, temperature=AUTHOR_TEMP, max_tokens=MAX_TOKENS, max_retries=8):
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


def randomize_proposals(va, vab, vb):
    versions = [("A", va), ("AB", vab), ("B", vb)]
    random.shuffle(versions)
    order = {str(i+1): label for i, (label, _) in enumerate(versions)}
    parts = [f"PROPOSAL {i+1}:\n---\n{content}\n---" for i, (_, content) in enumerate(versions)]
    return "\n\n".join(parts), order


def parse_ranking(text, valid_chars="123"):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            items = [c for c in raw if c in valid_chars]
            if len(items) >= 2:
                return items
    return None


async def verdict_judge_panel(task_prompt, va, vab, vb, num_reps=3):
    """
    Verdict-style hierarchical judge:
    For each of N repetitions:
      1. Judge ranks A/AB/B with explanation (CoT)
      2. Verifier reviews the judge's reasoning and confirms or corrects
    Then aggregate via Borda across all verified rankings.
    """
    all_rankings = []

    for rep in range(num_reps):
        proposals, order_map = randomize_proposals(va, vab, vb)

        # Step 1: Judge with explanation
        judge_system = "You are an independent evaluator. Think carefully before deciding."
        judge_output = await call_llm(judge_system,
            JUDGE_RANK_PROMPT.format(task_prompt=task_prompt, proposals=proposals),
            temperature=JUDGE_TEMP)

        # Step 2: Verifier checks the reasoning
        verify_system = "You are a meta-evaluator. Your job is to check if the judge's reasoning is sound and unbiased."
        verify_output = await call_llm(verify_system,
            JUDGE_VERIFY_PROMPT.format(task_prompt=task_prompt, judge_output=judge_output),
            temperature=0.1)  # Low temp for verification

        # Parse the verifier's ranking (which may confirm or override)
        ranking = parse_ranking(verify_output)
        if ranking:
            mapped = [order_map.get(r, r) for r in ranking]
            all_rankings.append(mapped)

    # Borda aggregation across all verified rankings
    scores = {"A": 0, "AB": 0, "B": 0}
    points = [3, 2, 1]
    for r in all_rankings:
        for pos, label in enumerate(r):
            if label in scores and pos < 3:
                scores[label] += points[pos]

    priority = {"A": 0, "AB": 1, "B": 2}
    winner = sorted(scores.keys(), key=lambda k: (-scores[k], priority[k]))[0]

    return winner, scores, len(all_rankings)


async def run_pass(task_prompt, current_a, pass_num, pass_dir):
    pass_dir.mkdir(parents=True, exist_ok=True)
    result_file = pass_dir / "result.json"
    if result_file.exists():
        ex = json.loads(result_file.read_text())
        if ex.get("winner"):
            w = ex["winner"]
            if w == "A": return w, current_a, ex
            wf = pass_dir / f"version_{w.lower()}.md"
            return w, wf.read_text() if wf.exists() else current_a, ex

    t0 = time.time()
    (pass_dir / "version_a.md").write_text(current_a)

    critic = await call_llm(CRITIC_SYSTEM, CRITIC_PROMPT.format(version_a=current_a))
    (pass_dir / "critic.md").write_text(critic)

    vb = await call_llm(AUTHOR_B_SYSTEM, AUTHOR_B_PROMPT.format(
        task_prompt=task_prompt, version_a=current_a, critic=critic))
    (pass_dir / "version_b.md").write_text(vb)

    if random.random() < 0.5:
        vx, vy = current_a, vb
    else:
        vx, vy = vb, current_a
    vab = await call_llm(SYNTH_SYSTEM, SYNTH_PROMPT.format(task_prompt=task_prompt, vx=vx, vy=vy))
    (pass_dir / "version_ab.md").write_text(vab)

    # Verdict-style hierarchical judge panel
    winner, scores, valid = await verdict_judge_panel(task_prompt, current_a, vab, vb)
    elapsed = time.time() - t0

    vmap = {"A": current_a, "AB": vab, "B": vb}
    result = {
        "pass": pass_num, "winner": winner, "scores": scores, "valid": valid,
        "elapsed": round(elapsed, 1),
        "words_a": len(current_a.split()), "words_ab": len(vab.split()), "words_b": len(vb.split()),
        "judge_type": "verdict_hierarchical"
    }
    (pass_dir / "result.json").write_text(json.dumps(result, indent=2))
    return winner, vmap[winner], result


async def main():
    task_prompt = Path("/root/autoreason-experiment/tasks/task_02.md").read_text().strip()
    root = Path(__file__).parent
    out_dir = root / "results_46_verdict"
    out_dir.mkdir(parents=True, exist_ok=True)
    ar_dir = out_dir / "autoreason"
    ar_dir.mkdir(parents=True, exist_ok=True)

    print(f"{'='*60}")
    print(f"Verdict Hierarchical Judges — Sonnet 4.6, Task 2")
    print(f"Judge pipeline: Rank(CoT) → Verify → repeat 3x → Borda")
    print(f"Max passes: {MAX_PASSES}, Convergence: {CONVERGENCE}")
    print(f"{'='*60}\n")

    # Use same initial A as other 4.6 experiments
    baseline_init = root / "results_46_task02" / "autoreason" / "initial_a.md"
    init_file = ar_dir / "initial_a.md"
    if init_file.exists():
        current_a = init_file.read_text()
    elif baseline_init.exists():
        current_a = baseline_init.read_text()
        init_file.write_text(current_a)
    else:
        current_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt))
        init_file.write_text(current_a)

    print(f"  Initial A: {len(current_a.split())} words\n")

    streak, history = 0, []
    for p in range(1, MAX_PASSES + 1):
        winner, winner_text, result = await run_pass(task_prompt, current_a, p, ar_dir / f"pass_{p:02d}")
        history.append({"pass": p, "winner": winner, "scores": result["scores"]})

        print(f"  Pass {p:2d}: {winner:2s} (A={result['scores']['A']}, AB={result['scores']['AB']}, B={result['scores']['B']}) "
              f"[{result['elapsed']:.0f}s] {result['words_a']}w", flush=True)

        if winner == "A":
            streak += 1
        else:
            streak = 0
            current_a = winner_text
            (ar_dir / f"incumbent_after_{p:02d}.md").write_text(current_a)

        if streak >= CONVERGENCE:
            print(f"\n  >>> Converged at pass {p}")
            break

    if streak < CONVERGENCE:
        print(f"\n  >>> Did not converge after {MAX_PASSES} passes")

    (ar_dir / "final_output.md").write_text(current_a)
    (ar_dir / "history.json").write_text(json.dumps(history, indent=2))

    a_wins = sum(1 for h in history if h["winner"] == "A")
    ab_wins = sum(1 for h in history if h["winner"] == "AB")
    b_wins = sum(1 for h in history if h["winner"] == "B")
    traj = " -> ".join(h["winner"] for h in history)

    summary = {
        "total_passes": len(history), "a_wins": a_wins, "ab_wins": ab_wins, "b_wins": b_wins,
        "converged": streak >= CONVERGENCE, "trajectory": traj,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n  Summary: {len(history)} passes (A={a_wins} AB={ab_wins} B={b_wins})")
    print(f"  Trajectory: {traj}")
    print(f"\n  Baseline comparison (same setup, standard 3-judge CoT):")
    print(f"    Baseline: 50 passes, A=6, AB=30+, B=rest, no convergence")


if __name__ == "__main__":
    asyncio.run(main())
