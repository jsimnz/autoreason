#!/usr/bin/env python3
"""
Run autoreason on the paper itself using Opus 4.6, incorporating reviewer feedback.
Ground-truth context: actual experimental data + reviewer feedback.
Scope constraint: must stay within +-10% of current length (~3800 words / ~35K chars).
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

MODEL = "anthropic/claude-opus-4-6"
AUTHOR_TEMP = 0.7
JUDGE_TEMP = 0.2
MAX_TOKENS = 16384
MAX_PASSES = 15
CONVERGENCE = 2

# Load all context
PAPER_TEX = Path("/root/autoreason-experiment/paper/autoreason.tex").read_text()
RESULTS_MD = Path("/root/autoreason-experiment/RESULTS.md").read_text()

reviews_dir = Path("/root/autoreason-experiment/paper/reviews")
REVIEWS = ""
for rf in sorted(reviews_dir.glob("review_*.md")):
    REVIEWS += f"\n{'='*60}\n{rf.name}\n{'='*60}\n{rf.read_text()}\n"

current_words = len(PAPER_TEX.split())
min_words = int(current_words * 0.85)
max_words = int(current_words * 1.15)

TASK_PROMPT = f"""Improve this LaTeX paper based on the reviewer feedback below. 

SCOPE CONSTRAINTS (critical, do not violate):
- The output must be a complete, compilable LaTeX document
- Do NOT add new experiments or fabricate results
- Do NOT change any numbers, Borda scores, pass counts, or experimental outcomes
- You may reorganize, rewrite prose, fix issues, clarify, tighten, or restructure
- Preserve all figures, tables, TikZ diagram, and appendix content
- Keep maximum 3 em-dashes in the entire document
- Preserve the existing section structure: Introduction, Method, Experiments, Results, Model Scaling, Writing This Paper, Related Work, Discussion, Conclusion, Appendix
- Do NOT add new sections or remove existing ones
- Do NOT add new figures or tables

EXACTLY THESE 10 REVIEWER ITEMS TO ADDRESS (do all 10, nothing else):
1. Baselines are undefined. Add a short paragraph in Section 3 (Experiments) describing the 4 baseline methods and their prompts.
2. Acknowledge LLM-only evaluation more prominently in Discussion limitations.
3. Temper the constrained-task claim: acknowledge it is one task, not a general result.
4. Fix Figure 1 caption self-reference (remove "Figure 1" from inside its own caption).
5. Add one sentence in Section 3 noting the compute budget difference (autoreason: ~90 calls/task vs baselines: ~15 calls/task).
6. Add one sentence in the bibliography section or a footnote acknowledging that the 2026 dates are correct (recent preprints).
7. Change "confirms" to "suggests" for the Monte Carlo result in the abstract and Section 4.5.
8. Soften the PSRO claim in Section 2.1: say "loosely analogous" rather than "direct connection."
9. Add one sentence explaining 3 judges in-loop (cost) vs 7 in final eval (statistical power).
10. Add one sentence justifying k=2 and temperature choices (e.g., in Method or Experiments).

WHAT NOT TO CHANGE:
- The core narrative arc (works -> fails -> diagnosis -> scope fix)
- Any experimental numbers or results
- The TikZ method diagram
- The appendix prompts
- The bibliography entries (the 2026 dates are correct)
- The section structure and ordering

GROUND-TRUTH DATA (reference, do not fabricate beyond this):
{RESULTS_MD[:8000]}

REVIEWER FEEDBACK:
{REVIEWS[:12000]}
"""

LENGTH_NOTE = f"HARD CONSTRAINT: The output MUST be between {min_words} and {max_words} words. The current version is {current_words} words. If you add content anywhere, you MUST cut an equal amount elsewhere. Exceeding the limit means your revision will be rejected."

AUTHOR_SYSTEM = f"You are an expert ML paper author. Produce complete, compilable LaTeX. Be precise with experimental claims. {LENGTH_NOTE}"
CRITIC_SYSTEM = "You are a senior ML reviewer. Find real problems with this paper revision. Be specific about what's wrong and cite sections. Do not suggest fixes."
AUTHOR_B_SYSTEM = f"You are an expert ML paper author revising based on specific criticisms. Address each valid criticism. Do not change experimental numbers. {LENGTH_NOTE}"
SYNTH_SYSTEM = f"You are an expert ML paper editor. Merge the best elements of two paper versions into one coherent, complete LaTeX document. {LENGTH_NOTE}"
COT_JUDGE_SYSTEM = "You are a senior ML reviewer evaluating paper revisions. Think carefully before deciding."

CRITIC_PROMPT = """Review this paper revision. The revision was supposed to address reviewer feedback while staying within scope constraints.

Find problems: claims that are still overstated, reviewer feedback that wasn't addressed, prose that could be tighter, structural issues, anything that would still bother a reviewer.

Do NOT suggest fixes. Just identify the problems.

PAPER:
---
{version_a}
---"""

AUTHOR_B_PROMPT = """TASK:
---
{task_prompt}
---

CURRENT PAPER VERSION:
---
{version_a}
---

CRITIC FINDINGS:
---
{critic}
---

Revise the paper to address these problems. Output the complete LaTeX document."""

SYNTH_PROMPT = """TASK:
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

Merge the strongest elements of both into one complete, compilable LaTeX document. Stay within the scope constraints."""

COT_JUDGE_3WAY = """You are evaluating three revisions of an ML paper. All were revised based on the same reviewer feedback.

ORIGINAL TASK AND CONSTRAINTS:
---
{task_prompt}
---

Three revised versions:

{proposals}

For each version, think step by step:
1. How well does it address the reviewer feedback?
2. Does it stay within scope constraints (length, no fabricated results)?
3. Is the prose clear and precise?
4. Would this version satisfy the reviewers better than the others?
5. Are there any new problems introduced?

After reasoning, rank all three from best to worst.

RANKING: [best], [second], [worst]"""


async def call_llm(system, user, model=MODEL, temperature=AUTHOR_TEMP, max_tokens=MAX_TOKENS, max_retries=5):
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
                wait = min((2 ** attempt) * 10, 120)
                print(f"    Rate limited, waiting {wait}s...")
                await asyncio.sleep(wait)
            else:
                if attempt < max_retries - 1:
                    print(f"    Error: {e}, retrying...")
                    await asyncio.sleep(15)
                else:
                    raise


def randomize_proposals(va, vab, vb):
    versions = [("A", va), ("AB", vab), ("B", vb)]
    random.shuffle(versions)
    order = {str(i+1): label for i, (label, _) in enumerate(versions)}
    parts = [f"VERSION {i+1}:\n---\n{content}\n---" for i, (_, content) in enumerate(versions)]
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


def extract_latex(text):
    """Extract the LaTeX document from a response that might have explanation around it."""
    if "\\documentclass" in text:
        start = text.index("\\documentclass")
        if "\\end{document}" in text:
            end = text.index("\\end{document}") + len("\\end{document}")
            return text[start:end]
        return text[start:]
    return text


async def run_pass(current_a, pass_num, pass_dir):
    pass_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    (pass_dir / "version_a.tex").write_text(current_a)

    # Critic
    critic = await call_llm(CRITIC_SYSTEM, CRITIC_PROMPT.format(version_a=current_a))
    (pass_dir / "critic.md").write_text(critic)

    # Author B
    vb_raw = await call_llm(AUTHOR_B_SYSTEM, AUTHOR_B_PROMPT.format(
        task_prompt=TASK_PROMPT, version_a=current_a, critic=critic))
    vb = extract_latex(vb_raw)
    (pass_dir / "version_b.tex").write_text(vb)

    # Synthesizer
    if random.random() < 0.5:
        vx, vy = current_a, vb
    else:
        vx, vy = vb, current_a
    vab_raw = await call_llm(SYNTH_SYSTEM, SYNTH_PROMPT.format(
        task_prompt=TASK_PROMPT, vx=vx, vy=vy))
    vab = extract_latex(vab_raw)
    (pass_dir / "version_ab.tex").write_text(vab)

    # 3 judges
    rankings = []
    for _ in range(3):
        proposals, om = randomize_proposals(current_a, vab, vb)
        resp = await call_llm(COT_JUDGE_SYSTEM,
            COT_JUDGE_3WAY.format(task_prompt=TASK_PROMPT, proposals=proposals),
            temperature=JUDGE_TEMP)
        raw = parse_ranking(resp)
        rankings.append([om.get(r, r) for r in raw] if raw else None)

    scores = {"A": 0, "AB": 0, "B": 0}
    for r in rankings:
        if not r: continue
        for pos, label in enumerate(r):
            if label in scores and pos < 3:
                scores[label] += [3, 2, 1][pos]

    priority = {"A": 0, "AB": 1, "B": 2}
    winner = sorted(scores.keys(), key=lambda k: (-scores[k], priority[k]))[0]
    elapsed = time.time() - t0

    vmap = {"A": current_a, "AB": vab, "B": vb}
    result = {
        "pass": pass_num, "winner": winner, "scores": scores,
        "elapsed": round(elapsed, 1),
        "words_a": len(current_a.split()),
        "words_ab": len(vab.split()),
        "words_b": len(vb.split()),
    }
    (pass_dir / "result.json").write_text(json.dumps(result, indent=2))
    return winner, vmap[winner], result


async def main():
    out_dir = Path("/root/autoreason-experiment/paper/autoreason_run_v2")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Autoreason on Paper v2 (Opus 4.6)")
    print(f"Current paper: {current_words} words")
    print(f"Target range: {min_words}–{max_words} words")
    print(f"Max passes: {MAX_PASSES}, Convergence: {CONVERGENCE}")
    print(f"{'='*60}\n")

    # Generate initial revision (Author A)
    init_file = out_dir / "initial_a.tex"
    if init_file.exists():
        current_a = init_file.read_text()
        print(f"  Loaded existing initial A: {len(current_a.split())} words")
    else:
        print("  Generating initial revision...")
        raw = await call_llm(AUTHOR_SYSTEM,
            TASK_PROMPT + "\n\nCURRENT PAPER:\n---\n" + PAPER_TEX + "\n---\n\nProduce the complete revised LaTeX document.")
        current_a = extract_latex(raw)
        init_file.write_text(current_a)
        print(f"  Initial A: {len(current_a.split())} words")

    streak, history = 0, []
    for p in range(1, MAX_PASSES + 1):
        winner, winner_text, result = await run_pass(current_a, p, out_dir / f"pass_{p:02d}")
        history.append({"pass": p, "winner": winner, "scores": result["scores"]})

        print(f"  Pass {p:2d}: {winner:2s} (A={result['scores']['A']}, AB={result['scores']['AB']}, B={result['scores']['B']}) "
              f"[{result['elapsed']:.0f}s] A:{result['words_a']}w AB:{result['words_ab']}w B:{result['words_b']}w",
              flush=True)

        if winner == "A":
            streak += 1
        else:
            streak = 0
            current_a = winner_text
            (out_dir / f"incumbent_after_{p:02d}.tex").write_text(current_a)

        if streak >= CONVERGENCE:
            print(f"\n  >>> Converged at pass {p}")
            break

    if streak < CONVERGENCE:
        print(f"\n  >>> Did not converge after {MAX_PASSES} passes")

    (out_dir / "final.tex").write_text(current_a)
    (out_dir / "history.json").write_text(json.dumps(history, indent=2))

    traj = " -> ".join(h["winner"] for h in history)
    print(f"\n  Final: {len(current_a.split())} words")
    print(f"  Trajectory: {traj}")


if __name__ == "__main__":
    asyncio.run(main())
