#!/usr/bin/env python3
"""
Autoreason v2 experiment runner.

Key changes from v1:
- Iterative loop: passes repeat until incumbent (A) wins 3 consecutive times
- Fresh isolated agents per role (no shared context between critic, author B, synthesizer)
- 3-judge panel with ranked choice evaluation
- Original prompt as anchor for judges (not a rubric — the task defines "better")
- Reasoning required before ranking
- Conservative tiebreak: incumbent survives ties

Usage:
    python run_v2.py --task 1              # run task 1
    python run_v2.py --task 1 --max-passes 20  # cap at 20 passes
    python run_v2.py --dry-run             # print plan without calling LLM
"""

import argparse
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Load env
# ---------------------------------------------------------------------------
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

import yaml

# ---------------------------------------------------------------------------
# System prompts — each role gets its own, no bleed
# ---------------------------------------------------------------------------

CRITIC_SYSTEM = (
    "You are a critical reviewer. Your only job is to find real problems "
    "with the proposal you are given. Be specific and concrete. Do not "
    "suggest fixes or improvements — only identify weaknesses."
)

AUTHOR_B_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "You are revising a proposal based on specific criticisms. Address "
    "each valid criticism directly. Do not make changes that aren't "
    "motivated by an identified problem."
)

SYNTHESIZER_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "You are given two versions of a proposal as equal inputs. You have "
    "no preference between them. Take the strongest elements from each "
    "and produce a coherent synthesis. This is not a compromise — pick "
    "the best answer per dimension."
)

AUTHOR_A_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Avoid generic advice. "
    "Tailor everything to the constraints stated in the task."
)

JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no authorship stake in any "
    "version. You have never seen these proposals before. Your job is to "
    "determine which version best accomplishes the original task as described."
)

# ---------------------------------------------------------------------------
# User prompts
# ---------------------------------------------------------------------------

GENERATE_A = "{task_prompt}\n\nProduce a complete, detailed proposal."

CRITIC_PROMPT = """Here is a proposal:

---
{version_a}
---

Find real problems with this proposal. Focus on:
- Things that won't work as described
- Complexity that doesn't pay for itself
- Assumptions that are wrong
- Missing pieces that block the design

Do NOT propose fixes. Just the problems."""

AUTHOR_B_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Here is a proposal and the problems identified with it.

CURRENT PROPOSAL:
---
{version_a}
---

PROBLEMS FOUND:
---
{critic}
---

Revise the proposal to address these problems.
For each change, state which problem it fixes.
Do not make changes that aren't motivated by an identified problem."""

SYNTHESIZER_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Here are two versions of a proposal. You have no information about which came first or how they were produced. Treat them as equal inputs.

VERSION X:
---
{version_x}
---

VERSION Y:
---
{version_y}
---

Produce a synthesis that keeps the strongest elements from both.
This is not a compromise or average. Take the best answer per dimension and make them cohere."""

JUDGE_PROMPT = """ORIGINAL TASK:
---
{task_prompt}
---

Three proposals have been produced independently to accomplish this task. Evaluate how well each one accomplishes what the task asks for.

{judge_proposals}

For each proposal, state specifically:
1. Which aspects of the original task it handles well
2. Which aspects of the original task it handles poorly or misses
3. Any issues with feasibility or coherence

Then rank all three from best to worst. Respond with your ranking in this exact format at the end:

RANKING: [best], [second], [worst]

Where each slot is 1, 2, or 3 corresponding to the proposal numbers above."""


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
            if "rate" in err or "429" in err or "overloaded" in err:
                wait = (2 ** attempt) * 5
                print(f"    [Rate limited, retrying in {wait}s...]")
                await asyncio.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Failed after {max_retries} retries")


# ---------------------------------------------------------------------------
# Judge helpers
# ---------------------------------------------------------------------------

def randomize_for_judge(version_a, version_b, version_ab):
    """Randomize order, return (formatted_text, order_map).
    order_map: position (1,2,3) -> original label (A, B, AB)
    """
    versions = [("A", version_a), ("B", version_b), ("AB", version_ab)]
    random.shuffle(versions)
    order_map = {}
    parts = []
    for i, (label, content) in enumerate(versions, 1):
        order_map[str(i)] = label
        parts.append(f"PROPOSAL {i}:\n---\n{content}\n---")
    return "\n\n".join(parts), order_map


def parse_ranking(text, order_map):
    """Extract RANKING from judge response, return list of original labels in rank order."""
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            nums = [c for c in raw if c in ("1", "2", "3")]
            if len(nums) >= 2:
                return [order_map.get(n, n) for n in nums]
    return None


def aggregate_rankings(rankings):
    """Borda count over ranked lists. Returns (winner, scores, details).
    
    3 points for 1st, 2 for 2nd, 1 for 3rd.
    On tie, incumbent (A) wins (conservative tiebreak).
    """
    scores = {"A": 0, "B": 0, "AB": 0}
    points = [3, 2, 1]
    
    valid_rankings = [r for r in rankings if r is not None]
    
    for ranking in valid_rankings:
        for pos, label in enumerate(ranking):
            if label in scores and pos < len(points):
                scores[label] += points[pos]
    
    # Sort by score descending, with A winning ties
    priority = {"A": 0, "B": 1, "AB": 2}  # lower = wins ties
    ranked = sorted(scores.keys(), key=lambda k: (-scores[k], priority[k]))
    winner = ranked[0]
    
    return winner, scores, valid_rankings


# ---------------------------------------------------------------------------
# Single pass
# ---------------------------------------------------------------------------

async def run_pass(task_prompt, current_a, pass_num, pass_dir, config, dry_run=False):
    """Run one autoreason pass. Returns (winner_label, winner_text, pass_result)."""
    model = config["author_model"]
    temp = config["author_temperature"]
    jmodel = config["judge_model"]
    jtemp = config["judge_temperature"]
    max_tok = config["max_tokens"]
    num_judges = config.get("num_judges", 3)
    
    pass_dir.mkdir(parents=True, exist_ok=True)
    
    # Check for existing results (resume)
    result_file = pass_dir / "result.json"
    if result_file.exists():
        existing = json.loads(result_file.read_text())
        if existing.get("winner"):
            print(f"    ↳ Skipping (already complete: {existing['winner']})")
            winner = existing["winner"]
            winner_text_file = pass_dir / f"version_{winner.lower()}.md"
            if winner == "A":
                winner_text = current_a
            elif winner_text_file.exists():
                winner_text = winner_text_file.read_text()
            else:
                winner_text = current_a
            return winner, winner_text, existing
    
    if dry_run:
        print(f"    ↳ [DRY RUN] Would run: 1 critic + 1 author_b + 1 synthesizer + {num_judges} judges = {3 + num_judges} LLM calls")
        return "DRY", current_a, {}
    
    t0 = time.time()
    
    # Save current A
    (pass_dir / "version_a.md").write_text(current_a)
    
    # Step 1: Critic (fresh agent, only sees version A)
    print(f"    → Critic...")
    critic = await call_llm(
        CRITIC_SYSTEM,
        CRITIC_PROMPT.format(version_a=current_a),
        model, temp, max_tok
    )
    (pass_dir / "critic.md").write_text(critic)
    
    # Step 2: Author B (fresh agent, sees task + A + critic, no drafting history)
    print(f"    → Author B...")
    version_b = await call_llm(
        AUTHOR_B_SYSTEM,
        AUTHOR_B_PROMPT.format(task_prompt=task_prompt, version_a=current_a, critic=critic),
        model, temp, max_tok
    )
    (pass_dir / "version_b.md").write_text(version_b)
    
    # Step 3: Synthesizer (fresh agent, sees task + both versions as equal inputs, randomized)
    # Randomize which is X and which is Y so synthesizer has no positional bias
    print(f"    → Synthesizer...")
    if random.random() < 0.5:
        vx, vy = current_a, version_b
    else:
        vx, vy = version_b, current_a
    
    version_ab = await call_llm(
        SYNTHESIZER_SYSTEM,
        SYNTHESIZER_PROMPT.format(task_prompt=task_prompt, version_x=vx, version_y=vy),
        model, temp, max_tok
    )
    (pass_dir / "version_ab.md").write_text(version_ab)
    
    # Step 4: Judge panel (N fresh agents, each sees task + 3 versions randomized)
    print(f"    → Judge panel ({num_judges} judges)...")
    judge_tasks = []
    judge_orders = []
    
    for j in range(num_judges):
        proposals, order_map = randomize_for_judge(current_a, version_b, version_ab)
        judge_orders.append(order_map)
        judge_tasks.append(
            call_llm(
                JUDGE_SYSTEM,
                JUDGE_PROMPT.format(task_prompt=task_prompt, judge_proposals=proposals),
                jmodel, jtemp, max_tok
            )
        )
    
    judge_responses = await asyncio.gather(*judge_tasks, return_exceptions=True)
    
    # Parse rankings
    rankings = []
    judge_details = []
    for j, (response, order_map) in enumerate(zip(judge_responses, judge_orders)):
        if isinstance(response, Exception):
            print(f"      Judge {j+1}: ERROR - {response}")
            rankings.append(None)
            judge_details.append({"error": str(response)})
        else:
            ranking = parse_ranking(response, order_map)
            rankings.append(ranking)
            judge_details.append({
                "ranking": ranking,
                "presentation_order": order_map,
                "raw_response": response,
            })
            rank_str = " > ".join(ranking) if ranking else "PARSE_ERROR"
            print(f"      Judge {j+1}: {rank_str}")
    
    # Aggregate
    winner, scores, valid_rankings = aggregate_rankings(rankings)
    elapsed = time.time() - t0
    
    # Determine winner text
    version_map = {"A": current_a, "B": version_b, "AB": version_ab}
    winner_text = version_map[winner]
    
    result = {
        "pass": pass_num,
        "winner": winner,
        "scores": scores,
        "num_judges": num_judges,
        "num_valid": len(valid_rankings),
        "individual_rankings": [r for r in rankings if r is not None],
        "judge_details": judge_details,
        "elapsed_seconds": round(elapsed, 1),
        "author_model": model,
        "judge_model": jmodel,
    }
    (pass_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    
    print(f"    ↳ Winner: {winner} (scores: A={scores['A']}, B={scores['B']}, AB={scores['AB']}) [{elapsed:.0f}s]")
    
    return winner, winner_text, result


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run_autoreason_loop(task_prompt, task_dir, config, dry_run=False):
    """Run autoreason passes until convergence (3 consecutive A wins) or max passes."""
    model = config["author_model"]
    temp = config["author_temperature"]
    max_tok = config["max_tokens"]
    max_passes = config.get("max_passes", 50)
    convergence_threshold = config.get("convergence_threshold", 3)
    
    task_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 0: Generate initial Version A
    init_file = task_dir / "initial_a.md"
    if init_file.exists():
        print("  Using existing initial A")
        current_a = init_file.read_text()
    elif dry_run:
        print("  [DRY RUN] Would generate initial A")
        current_a = "DRY RUN"
    else:
        print("  Generating initial A...")
        current_a = await call_llm(
            AUTHOR_A_SYSTEM,
            GENERATE_A.format(task_prompt=task_prompt),
            model, temp, max_tok
        )
        init_file.write_text(current_a)
    
    consecutive_a_wins = 0
    history = []
    
    for pass_num in range(1, max_passes + 1):
        print(f"\n  ━━━ Pass {pass_num} (A wins streak: {consecutive_a_wins}/{convergence_threshold}) ━━━")
        
        pass_dir = task_dir / f"pass_{pass_num:02d}"
        winner, winner_text, result = await run_pass(
            task_prompt, current_a, pass_num, pass_dir, config, dry_run
        )
        
        if dry_run:
            history.append({"pass": pass_num, "winner": "DRY"})
            continue
        
        history.append({
            "pass": pass_num,
            "winner": winner,
            "scores": result.get("scores", {}),
        })
        
        if winner == "A":
            consecutive_a_wins += 1
            # A survives — don't update current_a, it's already the incumbent
        else:
            consecutive_a_wins = 0
            current_a = winner_text
            # Save the new incumbent
            (task_dir / f"incumbent_after_pass_{pass_num:02d}.md").write_text(current_a)
        
        if consecutive_a_wins >= convergence_threshold:
            print(f"\n  ✔ Converged after {pass_num} passes (A won {convergence_threshold} consecutive times)")
            break
    else:
        if not dry_run:
            print(f"\n  ◐ Max passes ({max_passes}) reached without convergence")
    
    # Save final output and history
    if not dry_run:
        (task_dir / "final_output.md").write_text(current_a)
        (task_dir / "history.json").write_text(json.dumps(history, indent=2))
        
        print(f"\n  History: {' → '.join(h['winner'] for h in history)}")
    
    return history


async def main():
    parser = argparse.ArgumentParser(description="Autoreason v2 experiment runner")
    parser.add_argument("--task", type=int, help="Run only this task number (1-indexed)")
    parser.add_argument("--max-passes", type=int, help="Override max passes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).parent
    config = yaml.safe_load((root / "config_v2.yaml").read_text())

    if args.max_passes:
        config["max_passes"] = args.max_passes

    tasks = []
    tasks_dir = root / "tasks"
    if not tasks_dir.exists():
        tasks_dir = root.parent.parent / "tasks"
    for f in sorted(tasks_dir.glob("task_*.md")):
        tasks.append((f.stem, f.read_text().strip()))

    if not tasks:
        print("No tasks found in tasks/")
        sys.exit(1)

    if args.task:
        if args.task < 1 or args.task > len(tasks):
            print(f"Task {args.task} out of range (1-{len(tasks)})")
            sys.exit(1)
        tasks = [tasks[args.task - 1]]

    print(f"Autoreason v2: {len(tasks)} task(s)")
    print(f"Author:  {config['author_model']} (temp={config['author_temperature']})")
    print(f"Judge:   {config['judge_model']} (temp={config['judge_temperature']}) × {config.get('num_judges', 3)}")
    print(f"Max passes: {config.get('max_passes', 50)}, convergence: {config.get('convergence_threshold', 3)} consecutive A wins")
    print()

    results_dir = root / "results_v2"

    for task_name, task_prompt in tasks:
        task_num = task_name.replace("task_", "")
        print(f"{'━' * 60}")
        print(f"Task {task_num}: {task_prompt[:80]}...")
        print(f"{'━' * 60}")

        task_dir = results_dir / task_name
        history = await run_autoreason_loop(task_prompt, task_dir, config, args.dry_run)
        print()


if __name__ == "__main__":
    asyncio.run(main())
