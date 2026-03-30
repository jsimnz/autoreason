#!/usr/bin/env python3
"""
Autoreason scaling remedies: test modifications to recover convergence with Sonnet 4.6.

Usage:
  python run_46_remedies.py --experiment margin
  python run_46_remedies.py --experiment scope
  python run_46_remedies.py --experiment plateau
  python run_46_remedies.py --experiment combined
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

# ── Config ──────────────────────────────────────────────────────────
MODEL = "anthropic/claude-sonnet-4-6"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
MAX_PASSES = 50
CONVERGENCE = 2  # consecutive A wins (used when plateau detection is off)
MARGIN_THRESHOLD = 2  # AB/B must beat A by this many Borda points
PLATEAU_WINDOW = 5  # rolling window for plateau detection
PLATEAU_SCORE_THRESHOLD = 6  # avg A score above this = converged

# ── Prompts ─────────────────────────────────────────────────────────
AUTHOR_SYSTEM = "You are a senior consultant producing professional deliverables. Be specific, concrete, and practical."
CRITIC_SYSTEM = "You are a critical reviewer. Find real problems. Be specific. Do not suggest fixes."
AUTHOR_B_SYSTEM = "You are a senior consultant revising a proposal based on criticisms. Address each valid criticism directly."
SYNTH_SYSTEM = "You are a senior consultant. Take the strongest elements from two versions and produce a coherent synthesis."

COT_JUDGE_SYSTEM_BASE = "You are an independent evaluator. You have no authorship stake. Think carefully before deciding."

# Scope-aware judge addition
SCOPE_INSTRUCTION = """
IMPORTANT: The initial version of this proposal was approximately {initial_words} words.
Evaluate whether each version's length is appropriate for the task. Significant expansion
beyond the initial scope should be justified by genuine additional value, not padding.
Prefer focused, concrete proposals over comprehensive but bloated ones."""

GENERATE_A = "{task_prompt}\n\nProduce a complete, detailed proposal."
CRITIC_PROMPT = "Find real problems with this proposal. No fixes.\n\n---\n{version_a}\n---"
AUTHOR_B_PROMPT = "TASK:\n---\n{task_prompt}\n---\n\nCURRENT VERSION:\n---\n{version_a}\n---\n\nCRITIC FINDINGS:\n---\n{critic}\n---\n\nRevise to address these problems."
SYNTH_PROMPT = "TASK:\n---\n{task_prompt}\n---\n\nVERSION X:\n---\n{vx}\n---\n\nVERSION Y:\n---\n{vy}\n---\n\nSynthesize the strongest elements."

COT_JUDGE_3WAY = """ORIGINAL TASK:
---
{task_prompt}
---
{scope_note}
Three proposals:

{proposals}

For each proposal, think step by step:
1. What does it get right about the task?
2. What does it get wrong or miss?
3. Are the numbers and claims defensible?
4. Is the detail level appropriate or bloated?

After reasoning through each, rank all three from best to worst.

RANKING: [best], [second], [worst]"""


async def call_llm(system, user, model, temperature, max_tokens, max_retries=8):
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


def randomize_proposals(va, vb, vab):
    versions = [("A", va), ("AB", vab), ("B", vb)]  # A, AB, B order
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


async def run_pass(task_prompt, current_a, pass_num, pass_dir, config):
    pass_dir.mkdir(parents=True, exist_ok=True)
    result_file = pass_dir / "result.json"
    if result_file.exists():
        ex = json.loads(result_file.read_text())
        if ex.get("winner"):
            w = ex["winner"]
            if w == "A":
                return w, current_a, ex
            wf = pass_dir / f"version_{w.lower()}.md"
            return w, wf.read_text() if wf.exists() else current_a, ex

    t0 = time.time()
    (pass_dir / "version_a.md").write_text(current_a)

    # Critic
    critic = await call_llm(CRITIC_SYSTEM, CRITIC_PROMPT.format(version_a=current_a), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "critic.md").write_text(critic)

    # Author B
    vb = await call_llm(AUTHOR_B_SYSTEM, AUTHOR_B_PROMPT.format(task_prompt=task_prompt, version_a=current_a, critic=critic), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_b.md").write_text(vb)

    # Synthesizer (randomized A/B order)
    if random.random() < 0.5:
        vx, vy = current_a, vb
    else:
        vx, vy = vb, current_a
    vab = await call_llm(SYNTH_SYSTEM, SYNTH_PROMPT.format(task_prompt=task_prompt, vx=vx, vy=vy), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_ab.md").write_text(vab)

    # Build scope note for judges
    scope_note = ""
    if config["scope"]:
        scope_note = SCOPE_INSTRUCTION.format(initial_words=config["initial_words"])

    # Judge panel (3 CoT judges)
    rankings, order_maps = [], []
    for _ in range(3):
        proposals, om = randomize_proposals(current_a, vb, vab)
        order_maps.append(om)
        resp = await call_llm(COT_JUDGE_SYSTEM_BASE, COT_JUDGE_3WAY.format(
            task_prompt=task_prompt, proposals=proposals, scope_note=scope_note
        ), MODEL, JUDGE_TEMP, MAX_TOKENS)
        raw = parse_ranking(resp)
        rankings.append([om.get(r, r) for r in raw] if raw else None)

    scores = {"A": 0, "B": 0, "AB": 0}
    points = [3, 2, 1]
    valid = 0
    for r in rankings:
        if not r:
            continue
        valid += 1
        for pos, label in enumerate(r):
            if label in scores and pos < 3:
                scores[label] += points[pos]

    # ── Winner determination with margin logic ──
    raw_priority = {"A": 0, "AB": 1, "B": 2}
    raw_winner = sorted(scores.keys(), key=lambda k: (-scores[k], raw_priority[k]))[0]

    if config["margin"] and raw_winner != "A":
        # AB/B must beat A by margin threshold
        if scores[raw_winner] - scores["A"] < MARGIN_THRESHOLD:
            winner = "A"  # margin not met, incumbent survives
        else:
            winner = raw_winner
    else:
        winner = raw_winner

    elapsed = time.time() - t0
    vmap = {"A": current_a, "B": vb, "AB": vab}
    result = {
        "pass": pass_num, "winner": winner, "raw_winner": raw_winner,
        "scores": scores, "valid": valid, "elapsed": round(elapsed, 1),
        "margin_applied": config["margin"] and raw_winner != winner,
        "words_a": len(current_a.split()), "words_b": len(vb.split()), "words_ab": len(vab.split()),
    }
    (pass_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return winner, vmap[winner], result


def check_plateau(history, window=PLATEAU_WINDOW, threshold=PLATEAU_SCORE_THRESHOLD):
    """Check if A's average Borda score over last N passes exceeds threshold."""
    if len(history) < window:
        return False
    recent = history[-window:]
    avg_a = sum(h["scores"].get("A", 0) for h in recent) / window
    return avg_a >= threshold


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True, choices=["margin", "scope", "plateau", "combined"])
    args = parser.parse_args()

    exp = args.experiment
    config = {
        "margin": exp in ("margin", "combined"),
        "scope": exp in ("scope", "combined"),
        "plateau": exp in ("plateau", "combined"),
        "initial_words": 0,
    }

    task_prompt = Path("/root/autoreason-experiment/tasks/task_02.md").read_text().strip()
    root = Path(__file__).parent
    out_dir = root / f"results_46_remedy_{exp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    ar_dir = out_dir / "autoreason"
    ar_dir.mkdir(parents=True, exist_ok=True)

    label = f"Remedy: {exp}"
    mods = []
    if config["margin"]:
        mods.append(f"margin={MARGIN_THRESHOLD}")
    if config["scope"]:
        mods.append("scope-aware judges")
    if config["plateau"]:
        mods.append(f"plateau(window={PLATEAU_WINDOW}, threshold={PLATEAU_SCORE_THRESHOLD})")
    mod_str = " + ".join(mods)

    print(f"{'='*70}")
    print(f"Sonnet 4.6 — Task 2 — {label}")
    print(f"Modifications: {mod_str}")
    print(f"Model: {MODEL}")
    print(f"Max passes: {MAX_PASSES}, Convergence: {CONVERGENCE} consecutive A wins")
    print(f"{'='*70}\n")

    # Generate or load initial A
    init_file = ar_dir / "initial_a.md"
    # Use same initial A as baseline for fair comparison
    baseline_init = root / "results_46_task02" / "autoreason" / "initial_a.md"
    if init_file.exists():
        current_a = init_file.read_text()
    elif baseline_init.exists():
        current_a = baseline_init.read_text()
        init_file.write_text(current_a)
    else:
        current_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
        init_file.write_text(current_a)

    config["initial_words"] = len(current_a.split())
    print(f"  Initial A: {config['initial_words']} words\n")

    initial_a = current_a
    streak, history = 0, []
    converge_reason = None

    for p in range(1, MAX_PASSES + 1):
        winner, winner_text, result = await run_pass(task_prompt, current_a, p, ar_dir / f"pass_{p:02d}", config)
        history.append({"pass": p, "winner": winner, "scores": result.get("scores", {}),
                        "raw_winner": result.get("raw_winner", winner),
                        "margin_applied": result.get("margin_applied", False)})

        margin_note = " [margin->A]" if result.get("margin_applied") else ""
        words = result.get("words_a", len(current_a.split()))
        print(f"  Pass {p:2d}: {winner:2s} (A={result['scores']['A']}, AB={result['scores']['AB']}, B={result['scores']['B']}) "
              f"[{result['elapsed']:.0f}s] {words}w{margin_note}", flush=True)

        if winner == "A":
            streak += 1
        else:
            streak = 0
            current_a = winner_text
            (ar_dir / f"incumbent_after_{p:02d}.md").write_text(current_a)

        # Check convergence: consecutive wins
        if streak >= CONVERGENCE:
            converge_reason = f"consecutive A wins ({CONVERGENCE})"
            print(f"\n  >>> Converged at pass {p}: {converge_reason}")
            break

        # Check convergence: plateau detection
        if config["plateau"] and check_plateau(history):
            converge_reason = f"plateau detected (avg A score >= {PLATEAU_SCORE_THRESHOLD} over last {PLATEAU_WINDOW} passes)"
            print(f"\n  >>> Converged at pass {p}: {converge_reason}")
            break

    if not converge_reason:
        print(f"\n  >>> Did not converge after {MAX_PASSES} passes")

    # Save results
    ar_output = current_a
    (ar_dir / "final_output.md").write_text(ar_output)

    summary = {
        "experiment": exp,
        "modifications": mod_str,
        "model": MODEL,
        "task": "task_02",
        "total_passes": len(history),
        "converged": converge_reason is not None,
        "converge_reason": converge_reason,
        "final_words": len(ar_output.split()),
        "a_wins": sum(1 for h in history if h["winner"] == "A"),
        "ab_wins": sum(1 for h in history if h["winner"] == "AB"),
        "b_wins": sum(1 for h in history if h["winner"] == "B"),
        "margin_overrides": sum(1 for h in history if h.get("margin_applied", False)),
        "trajectory": " -> ".join(h["winner"] for h in history),
        "history": history,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (ar_dir / "history.json").write_text(json.dumps(history, indent=2))

    print(f"\n  Summary:")
    print(f"    Passes: {summary['total_passes']}")
    print(f"    Converged: {summary['converged']} ({converge_reason or 'N/A'})")
    print(f"    A wins: {summary['a_wins']}, AB wins: {summary['ab_wins']}, B wins: {summary['b_wins']}")
    if config["margin"]:
        print(f"    Margin overrides: {summary['margin_overrides']} (AB/B win reversed to A)")
    print(f"    Final words: {summary['final_words']}")
    print(f"    Trajectory: {summary['trajectory']}")


if __name__ == "__main__":
    asyncio.run(main())
