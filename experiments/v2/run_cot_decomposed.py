#!/usr/bin/env python3
"""
Test chain-of-thought judging + decomposed evaluation.

Two variants compared against baseline on task 1:
1. CoT judges: same holistic ranking but must reason before deciding
2. Decomposed: 3 specialized judges (structure, evidence, task adherence)
   each score their dimension, aggregated into final ranking

Both run the full autoreason loop to convergence (threshold 2).
Compare convergence speed and final quality against baseline run.
"""

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

MODEL = "anthropic/claude-sonnet-4-20250514"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
MAX_PASSES = 30
CONVERGENCE = 2

# ── Author prompts (same for all variants) ──────────────────────────────

AUTHOR_SYSTEM = "You are a senior consultant producing professional deliverables. Be specific, concrete, and practical."
CRITIC_SYSTEM = "You are a critical reviewer. Find real problems. Be specific. Do not suggest fixes."
AUTHOR_B_SYSTEM = "You are a senior consultant revising a proposal based on criticisms. Address each valid criticism directly."
SYNTH_SYSTEM = "You are a senior consultant. Take the strongest elements from two versions and produce a coherent synthesis."

GENERATE_A = "{task_prompt}\n\nProduce a complete, detailed proposal."
CRITIC_PROMPT = "Find real problems with this proposal. No fixes.\n\n---\n{version_a}\n---"
AUTHOR_B_PROMPT = "TASK:\n---\n{task_prompt}\n---\n\nPROPOSAL:\n---\n{version_a}\n---\n\nPROBLEMS:\n---\n{critic}\n---\n\nRevise to address these problems."
SYNTH_PROMPT = "TASK:\n---\n{task_prompt}\n---\n\nVERSION X:\n---\n{vx}\n---\n\nVERSION Y:\n---\n{vy}\n---\n\nSynthesize the strongest elements."

# ── Judge variants ──────────────────────────────────────────────────────

# Variant 1: Chain-of-thought holistic judge
COT_JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no authorship stake. "
    "Think carefully before deciding."
)

COT_JUDGE_PROMPT = """ORIGINAL TASK:
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

# Variant 2: Decomposed specialized judges
STRUCTURE_JUDGE_SYSTEM = (
    "You are an expert in document structure and logical flow. "
    "Evaluate ONLY structural quality: organization, logical progression, "
    "coherence between sections, whether the argument builds correctly."
)

EVIDENCE_JUDGE_SYSTEM = (
    "You are an expert in evidence and quantitative reasoning. "
    "Evaluate ONLY the quality of evidence: are claims supported? "
    "Are numbers justified? Are assumptions stated and defensible?"
)

ADHERENCE_JUDGE_SYSTEM = (
    "You are an expert in requirements analysis. "
    "Evaluate ONLY task adherence: does the output accomplish what "
    "the task asked for? Are all required elements covered? "
    "Is anything missing or off-topic?"
)

DECOMPOSED_JUDGE_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Three proposals:

{proposals}

Evaluate these proposals ONLY on your area of expertise. Score each 1-10 on your dimension, then rank them.

SCORES: [proposal 1 score], [proposal 2 score], [proposal 3 score]
RANKING: [best], [second], [worst]"""


async def call_llm(system, user, model, temperature, max_tokens, max_retries=8):
    for attempt in range(max_retries):
        try:
            response = await litellm.acompletion(
                model=model, messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ], temperature=temperature, max_tokens=max_tokens,
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
    versions = [("A", va), ("B", vb), ("AB", vab)]
    random.shuffle(versions)
    order = {str(i+1): label for i, (label, _) in enumerate(versions)}
    parts = [f"PROPOSAL {i+1}:\n---\n{content}\n---" for i, (_, content) in enumerate(versions)]
    return "\n\n".join(parts), order


def parse_ranking(text):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip().lstrip("#").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            nums = [c for c in raw if c in ("1", "2", "3")]
            if len(nums) >= 2:
                return nums
    return None


def aggregate(rankings, order_maps):
    scores = {"A": 0, "B": 0, "AB": 0}
    points = [3, 2, 1]
    valid = 0
    for ranking, om in zip(rankings, order_maps):
        if not ranking:
            continue
        valid += 1
        mapped = [om.get(r, r) for r in ranking]
        for pos, label in enumerate(mapped):
            if label in scores and pos < len(points):
                scores[label] += points[pos]
    priority = {"A": 0, "B": 1, "AB": 2}
    winner = sorted(scores.keys(), key=lambda k: (-scores[k], priority[k]))[0]
    return winner, scores, valid


async def run_pass(task_prompt, current_a, pass_num, pass_dir, judge_variant):
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

    critic = await call_llm(CRITIC_SYSTEM, CRITIC_PROMPT.format(version_a=current_a), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "critic.md").write_text(critic)

    vb = await call_llm(AUTHOR_B_SYSTEM, AUTHOR_B_PROMPT.format(task_prompt=task_prompt, version_a=current_a, critic=critic), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_b.md").write_text(vb)

    if random.random() < 0.5:
        vx, vy = current_a, vb
    else:
        vx, vy = vb, current_a
    vab = await call_llm(SYNTH_SYSTEM, SYNTH_PROMPT.format(task_prompt=task_prompt, vx=vx, vy=vy), MODEL, AUTHOR_TEMP, MAX_TOKENS)
    (pass_dir / "version_ab.md").write_text(vab)

    # Judge phase — varies by variant
    rankings = []
    order_maps = []

    if judge_variant == "cot":
        # 3 CoT holistic judges
        for _ in range(3):
            proposals, om = randomize_proposals(current_a, vb, vab)
            order_maps.append(om)
            resp = await call_llm(COT_JUDGE_SYSTEM, COT_JUDGE_PROMPT.format(task_prompt=task_prompt, proposals=proposals), MODEL, JUDGE_TEMP, MAX_TOKENS)
            rankings.append(parse_ranking(resp))

    elif judge_variant == "decomposed":
        # 3 specialized judges, one per dimension
        judges = [
            (STRUCTURE_JUDGE_SYSTEM, "structure"),
            (EVIDENCE_JUDGE_SYSTEM, "evidence"),
            (ADHERENCE_JUDGE_SYSTEM, "adherence"),
        ]
        for jsys, jname in judges:
            proposals, om = randomize_proposals(current_a, vb, vab)
            order_maps.append(om)
            resp = await call_llm(jsys, DECOMPOSED_JUDGE_PROMPT.format(task_prompt=task_prompt, proposals=proposals), MODEL, JUDGE_TEMP, MAX_TOKENS)
            rankings.append(parse_ranking(resp))

    winner, scores, valid = aggregate(rankings, order_maps)
    elapsed = time.time() - t0

    vmap = {"A": current_a, "B": vb, "AB": vab}
    result = {"pass": pass_num, "winner": winner, "scores": scores, "valid": valid,
              "variant": judge_variant, "elapsed": round(elapsed, 1)}
    (pass_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

    return winner, vmap[winner], result


async def run_variant(task_prompt, variant_name, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)

    init_file = out_dir / "initial_a.md"
    if init_file.exists():
        current_a = init_file.read_text()
    else:
        current_a = await call_llm(AUTHOR_SYSTEM, GENERATE_A.format(task_prompt=task_prompt), MODEL, AUTHOR_TEMP, MAX_TOKENS)
        init_file.write_text(current_a)
    print(f"  [{variant_name}] Initial A: {len(current_a.split())} words")

    streak, history = 0, []
    for p in range(1, MAX_PASSES + 1):
        winner, winner_text, result = await run_pass(task_prompt, current_a, p, out_dir / f"pass_{p:02d}", variant_name)
        history.append({"pass": p, "winner": winner, "scores": result.get("scores", {})})
        print(f"  [{variant_name}] Pass {p}: {winner} (A={result['scores'].get('A',0)}, B={result['scores'].get('B',0)}, AB={result['scores'].get('AB',0)}) [{result.get('elapsed',0):.0f}s]")

        if winner == "A":
            streak += 1
        else:
            streak = 0
            current_a = winner_text
            (out_dir / f"incumbent_after_{p:02d}.md").write_text(current_a)

        if streak >= CONVERGENCE:
            print(f"  [{variant_name}] ✔ Converged at pass {p}")
            break

    (out_dir / "final_output.md").write_text(current_a)
    (out_dir / "history.json").write_text(json.dumps(history, indent=2))
    traj = " → ".join(h["winner"] for h in history)
    print(f"  [{variant_name}] Final: {len(current_a.split())} words, {traj}")
    return current_a, history


async def main():
    task_prompt = Path("/root/autoreason-experiment/tasks/task_01.md").read_text().strip()
    root = Path(__file__).parent

    print(f"CoT + Decomposed Judge Evaluation")
    print(f"Model: {MODEL}")
    print(f"{'='*60}\n")

    for variant in ["cot", "decomposed"]:
        print(f"\n{'━'*60}")
        print(f"Variant: {variant}")
        print(f"{'━'*60}")
        out_dir = root / "results_judge_variants" / f"task_01_{variant}"
        await run_variant(task_prompt, variant, out_dir)
        await asyncio.sleep(5)

    print(f"\n{'='*60}")
    print(f"COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
