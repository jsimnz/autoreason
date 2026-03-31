#!/usr/bin/env python3
"""
Autoreason v3 scaling remedies: target the root cause (synthesis drift + local-only judges).

Usage:
  python run_46_v3_remedies.py --experiment anchored
  python run_46_v3_remedies.py --experiment subtractive
  python run_46_v3_remedies.py --experiment anchored_subtractive
  python run_46_v3_remedies.py --experiment constrained
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

# ── Config ──────────────────────────────────────────────────────────
MODEL = "anthropic/claude-sonnet-4-6"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
MAX_PASSES = 50
CONVERGENCE = 2

# ── Prompts ─────────────────────────────────────────────────────────
AUTHOR_SYSTEM = "You are a senior consultant producing professional deliverables. Be specific, concrete, and practical."
CRITIC_SYSTEM = "You are a critical reviewer. Find real problems. Be specific. Do not suggest fixes."
AUTHOR_B_SYSTEM = "You are a senior consultant revising a proposal based on criticisms. Address each valid criticism directly."

# Default synthesizer (additive)
SYNTH_SYSTEM_DEFAULT = "You are a senior consultant. Take the strongest elements from two versions and produce a coherent synthesis."
SYNTH_PROMPT_DEFAULT = "TASK:\n---\n{task_prompt}\n---\n\nVERSION X:\n---\n{vx}\n---\n\nVERSION Y:\n---\n{vy}\n---\n\nSynthesize the strongest elements."

# Subtractive synthesizer
SYNTH_SYSTEM_SUBTRACTIVE = "You are a senior consultant performing a disciplined review of two proposal versions."
SYNTH_PROMPT_SUBTRACTIVE = """TASK:
---
{task_prompt}
---

VERSION X:
---
{vx}
---

VERSION Y:
---
{vy}
---

Compare the two versions carefully. Your goal is the MINIMAL good revision, not the maximal combination.

Rules:
- If Y's changes are genuine improvements over X, adopt them.
- If Y's changes are lateral moves, rewordings, or additions that don't clearly earn their place, keep X's version for those sections.
- Do NOT combine content from both just because both have something to say. Pick the better version of each section.
- If in doubt, prefer the shorter/simpler version. Additions must justify themselves.
- The output should be roughly the same length as the shorter input, not longer than the longer one.

Produce the result."""

COT_JUDGE_SYSTEM = "You are an independent evaluator. You have no authorship stake. Think carefully before deciding."

GENERATE_A = "{task_prompt}\n\nProduce a complete, detailed proposal."
CRITIC_PROMPT = "Find real problems with this proposal. No fixes.\n\n---\n{version_a}\n---"
AUTHOR_B_PROMPT = "TASK:\n---\n{task_prompt}\n---\n\nCURRENT VERSION:\n---\n{version_a}\n---\n\nCRITIC FINDINGS:\n---\n{critic}\n---\n\nRevise to address these problems."

# Standard judge (no anchor)
COT_JUDGE_3WAY = """ORIGINAL TASK:
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

After reasoning through each, rank all three from best to worst.

RANKING: [best], [second], [worst]"""

# Anchored judge (sees initial version)
COT_JUDGE_3WAY_ANCHORED = """ORIGINAL TASK:
---
{task_prompt}
---

INITIAL VERSION (the starting point — for reference, not as a candidate):
---
{initial_version}
---

Three teams have each produced a revised version. Your job is to determine which revision best accomplishes the original task.

{proposals}

For each proposal, think step by step:
1. How well does it accomplish the original task?
2. Has it genuinely improved on the initial version, or just changed it?
3. Are numbers and claims more defensible than before, or has it introduced new unsupported claims?
4. Is the detail level appropriate, or has it drifted toward unnecessary complexity?
5. Would someone actually USE this document as-is? Is it actionable?

Be skeptical of additions that don't clearly earn their place. Longer is not better. Different is not better. BETTER is better.

After reasoning, rank all three from best to worst.

RANKING: [best], [second], [worst]"""

# Constrained task
CONSTRAINED_TASK = """You are pitching a developer notification infrastructure startup to YC partners. You have 2 minutes (approximately 500 words).

Base facts (use ALL of these, add nothing that isn't derivable from them):
- Product: API-first notification service handling push, email, SMS, in-app for apps with 1M-50M MAU
- Current traction: 47 paying customers, $38K MRR, 180M notifications/month delivered
- Team: 3 engineers (ex-Twilio, ex-AWS SNS), founded 8 months ago
- Key metric: 99.97% delivery rate vs industry avg 94%
- Pricing: usage-based, $0.001/notification after 100K free tier
- Problem: engineering teams spend 3-6 months building notification infrastructure that isn't their core product
- Competition: AWS SNS (low-level), OneSignal (marketing-focused), custom builds
- Ask: $2M seed for hiring 2 more engineers and SOC2 certification

Constraints:
- Maximum 500 words
- Must be a compelling narrative, not a feature list
- Every sentence must earn its place

Write the pitch."""


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


async def run_pass(task_prompt, current_a, initial_a, pass_num, pass_dir, config):
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

    # Synthesizer
    if random.random() < 0.5:
        vx, vy = current_a, vb
    else:
        vx, vy = vb, current_a

    if config["subtractive"]:
        vab = await call_llm(SYNTH_SYSTEM_SUBTRACTIVE, SYNTH_PROMPT_SUBTRACTIVE.format(task_prompt=task_prompt, vx=vx, vy=vy), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    else:
        vab = await call_llm(SYNTH_SYSTEM_DEFAULT, SYNTH_PROMPT_DEFAULT.format(task_prompt=task_prompt, vx=vx, vy=vy), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_ab.md").write_text(vab)

    # Judge panel
    if config["anchored"]:
        judge_template = COT_JUDGE_3WAY_ANCHORED
    else:
        judge_template = COT_JUDGE_3WAY

    rankings, order_maps = [], []
    for _ in range(3):
        proposals, om = randomize_proposals(current_a, vab, vb)
        order_maps.append(om)

        if config["anchored"]:
            prompt = judge_template.format(task_prompt=task_prompt, proposals=proposals, initial_version=initial_a)
        else:
            prompt = judge_template.format(task_prompt=task_prompt, proposals=proposals)

        resp = await call_llm(COT_JUDGE_SYSTEM, prompt, MODEL, JUDGE_TEMP, MAX_TOKENS)
        raw = parse_ranking(resp)
        rankings.append([om.get(r, r) for r in raw] if raw else None)

    scores = {"A": 0, "AB": 0, "B": 0}
    points = [3, 2, 1]
    valid = 0
    for r in rankings:
        if not r:
            continue
        valid += 1
        for pos, label in enumerate(r):
            if label in scores and pos < 3:
                scores[label] += points[pos]

    priority = {"A": 0, "AB": 1, "B": 2}
    winner = sorted(scores.keys(), key=lambda k: (-scores[k], priority[k]))[0]
    elapsed = time.time() - t0

    vmap = {"A": current_a, "AB": vab, "B": vb}
    result = {
        "pass": pass_num, "winner": winner,
        "scores": scores, "valid": valid, "elapsed": round(elapsed, 1),
        "words_a": len(current_a.split()), "words_ab": len(vab.split()), "words_b": len(vb.split()),
    }
    (pass_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return winner, vmap[winner], result


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True,
                        choices=["anchored", "subtractive", "anchored_subtractive", "constrained"])
    args = parser.parse_args()

    exp = args.experiment
    config = {
        "anchored": exp in ("anchored", "anchored_subtractive"),
        "subtractive": exp in ("subtractive", "anchored_subtractive"),
        "constrained": exp == "constrained",
    }

    # Task prompt
    if config["constrained"]:
        task_prompt = CONSTRAINED_TASK
    else:
        task_prompt = Path("/root/autoreason-experiment/tasks/task_02.md").read_text().strip()

    root = Path(__file__).parent
    out_dir = root / f"results_46_v3_{exp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    ar_dir = out_dir / "autoreason"
    ar_dir.mkdir(parents=True, exist_ok=True)

    mods = []
    if config["anchored"]:
        mods.append("anchored judges")
    if config["subtractive"]:
        mods.append("subtractive synthesis")
    if config["constrained"]:
        mods.append("constrained task (500w pitch)")
    mod_str = " + ".join(mods) if mods else "none"

    print(f"{'='*70}")
    print(f"Sonnet 4.6 — v3 Remedy: {exp}")
    print(f"Modifications: {mod_str}")
    print(f"Model: {MODEL}")
    print(f"Max passes: {MAX_PASSES}, Convergence: {CONVERGENCE}")
    print(f"{'='*70}\n")

    # Generate or load initial A
    init_file = ar_dir / "initial_a.md"
    if not config["constrained"]:
        baseline_init = root / "results_46_task02" / "autoreason" / "initial_a.md"
        if init_file.exists():
            current_a = init_file.read_text()
        elif baseline_init.exists():
            current_a = baseline_init.read_text()
            init_file.write_text(current_a)
        else:
            current_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
            init_file.write_text(current_a)
    else:
        if init_file.exists():
            current_a = init_file.read_text()
        else:
            current_a = await call_llm(AUTHOR_SYSTEM, task_prompt, MODEL, AUTHOR_TEMP, MAX_TOKENS)
            init_file.write_text(current_a)

    initial_a = current_a
    print(f"  Initial A: {len(current_a.split())} words\n")

    streak, history = 0, []
    converge_reason = None

    for p in range(1, MAX_PASSES + 1):
        winner, winner_text, result = await run_pass(task_prompt, current_a, initial_a, p, ar_dir / f"pass_{p:02d}", config)
        history.append({"pass": p, "winner": winner, "scores": result.get("scores", {})})

        words_a = result.get("words_a", 0)
        words_ab = result.get("words_ab", 0)
        words_b = result.get("words_b", 0)
        print(f"  Pass {p:2d}: {winner:2s} (A={result['scores']['A']}, AB={result['scores']['AB']}, B={result['scores']['B']}) "
              f"[{result['elapsed']:.0f}s] A:{words_a}w AB:{words_ab}w B:{words_b}w", flush=True)

        if winner == "A":
            streak += 1
        else:
            streak = 0
            current_a = winner_text
            (ar_dir / f"incumbent_after_{p:02d}.md").write_text(current_a)

        if streak >= CONVERGENCE:
            converge_reason = f"consecutive A wins ({CONVERGENCE})"
            print(f"\n  >>> Converged at pass {p}: {converge_reason}")
            break

    if not converge_reason:
        print(f"\n  >>> Did not converge after {MAX_PASSES} passes")

    ar_output = current_a
    (ar_dir / "final_output.md").write_text(ar_output)

    summary = {
        "experiment": exp,
        "modifications": mod_str,
        "model": MODEL,
        "total_passes": len(history),
        "converged": converge_reason is not None,
        "converge_reason": converge_reason,
        "final_words": len(ar_output.split()),
        "a_wins": sum(1 for h in history if h["winner"] == "A"),
        "ab_wins": sum(1 for h in history if h["winner"] == "AB"),
        "b_wins": sum(1 for h in history if h["winner"] == "B"),
        "trajectory": " -> ".join(h["winner"] for h in history),
        "history": history,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (ar_dir / "history.json").write_text(json.dumps(history, indent=2))

    print(f"\n  Summary:")
    print(f"    Passes: {summary['total_passes']}")
    print(f"    Converged: {summary['converged']} ({converge_reason or 'N/A'})")
    print(f"    A: {summary['a_wins']}, AB: {summary['ab_wins']}, B: {summary['b_wins']}")
    print(f"    Final words: {summary['final_words']}")
    print(f"    Trajectory: {summary['trajectory']}")


if __name__ == "__main__":
    asyncio.run(main())
