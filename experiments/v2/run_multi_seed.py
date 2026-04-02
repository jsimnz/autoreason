#!/usr/bin/env python3
"""
Multi-seed replication: Run autoreason 3 times on each of the 5 writing tasks.
After all runs, 7-judge cross-evaluation measures variance.

Usage:
    python run_multi_seed.py                  # run everything
    python run_multi_seed.py --task 1         # just task 1
    python run_multi_seed.py --eval-only      # skip runs, just evaluate
"""
import argparse, asyncio, json, os, random, time
from pathlib import Path

def load_dotenv(path):
    if not Path(path).exists(): return
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())

load_dotenv(os.path.expanduser("~/.hermes/.env"))

import litellm
litellm.suppress_debug_info = True

MODEL = "anthropic/claude-sonnet-4-20250514"
AUTHOR_TEMP = 0.8
JUDGE_TEMP = 0.3
MAX_TOKENS = 4096
NUM_JUDGES = 3
MAX_PASSES = 25
CONVERGENCE_K = 2
NUM_SEEDS = 3

ROOT = Path(__file__).parent
TASKS_DIR = ROOT.parent.parent / "tasks"
OUT_DIR = ROOT / "results_multi_seed"

# --- Prompts (same as run_overnight.py) ---
AUTHOR_SYSTEM = (
    "You are a senior consultant producing professional deliverables. "
    "Be specific, concrete, and practical. Avoid generic advice."
)
CRITIC_SYSTEM = (
    "You are a critical reviewer. Your only job is to find real problems. "
    "Be specific and concrete. Do not suggest fixes."
)
AUTHOR_B_SYSTEM = (
    "You are a senior consultant revising a proposal based on specific criticisms. "
    "Address each valid criticism directly. Do not make changes not motivated by an identified problem."
)
SYNTHESIZER_SYSTEM = (
    "You are given two versions as equal inputs. Take the strongest elements "
    "from each and produce a coherent synthesis. This is not a compromise."
)
COT_JUDGE_SYSTEM = (
    "You are an independent evaluator. You have no authorship stake. "
    "Think carefully before deciding."
)

async def call_llm(system, user, temp=AUTHOR_TEMP):
    resp = await litellm.acompletion(
        model=MODEL, temperature=temp, max_tokens=MAX_TOKENS,
        messages=[{"role":"system","content":system},{"role":"user","content":user}]
    )
    return resp.choices[0].message.content

def parse_ranking(text):
    import re
    m = re.search(r'RANKING:\s*(\w+)\s*[,>]\s*(\w+)\s*[,>]\s*(\w+)', text)
    if m:
        return [m.group(1).strip(), m.group(2).strip(), m.group(3).strip()]
    return None

async def judge_3way(task, a_text, b_text, ab_text, n_judges=NUM_JUDGES):
    labels = ["X","Y","Z"]
    candidates = [("A", a_text), ("B", b_text), ("AB", ab_text)]
    random.shuffle(candidates)
    label_map = {labels[i]: candidates[i][0] for i in range(3)}
    
    parts = "\n\n".join(f"=== VERSION {labels[i]} ===\n{candidates[i][1]}" for i in range(3))
    prompt = f"ORIGINAL TASK:\n---\n{task}\n---\n\n{parts}\n\nFor each version, think step by step:\n1. What does it get right?\n2. What does it get wrong?\n3. Is detail appropriate or bloated?\n\nThen rank all three.\nRANKING: [best], [second], [worst]"
    
    scores = {"A":0, "B":0, "AB":0}
    for _ in range(n_judges):
        resp = await call_llm(COT_JUDGE_SYSTEM, prompt, JUDGE_TEMP)
        ranking = parse_ranking(resp)
        if ranking and len(ranking) == 3:
            for rank_pos, label in enumerate(ranking):
                label = label.strip()
                if label in label_map:
                    scores[label_map[label]] += (3 - rank_pos)
    return scores

async def run_autoreason(task_prompt, out_dir, label=""):
    out_dir.mkdir(parents=True, exist_ok=True)
    hist_file = out_dir / "history.json"
    if hist_file.exists():
        print(f"    {label} cached")
        return json.loads(hist_file.read_text())
    
    # Generate initial A
    a_text = await call_llm(AUTHOR_SYSTEM, f"{task_prompt}\n\nProduce a complete, detailed proposal.")
    history = [{"pass":0, "winner":"A", "a_words":len(a_text.split())}]
    consec_a = 0
    
    for p in range(1, MAX_PASSES+1):
        # Critic
        critique = await call_llm(CRITIC_SYSTEM, 
            f"Here is a proposal:\n---\n{a_text}\n---\n\nORIGINAL TASK:\n{task_prompt}\n\nFind real problems.")
        # Author B
        b_text = await call_llm(AUTHOR_B_SYSTEM,
            f"ORIGINAL TASK:\n---\n{task_prompt}\n---\n\nCURRENT VERSION:\n---\n{a_text}\n---\n\nCRITIQUE:\n---\n{critique}\n---\n\nRevise to address these problems.")
        # Synthesizer
        versions = [(a_text, "X"), (b_text, "Y")]
        random.shuffle(versions)
        ab_text = await call_llm(SYNTHESIZER_SYSTEM,
            f"ORIGINAL TASK:\n---\n{task_prompt}\n---\n\nVERSION {versions[0][1]}:\n---\n{versions[0][0]}\n---\n\nVERSION {versions[1][1]}:\n---\n{versions[1][0]}\n---\n\nProduce a synthesis.")
        
        # Judge
        scores = await judge_3way(task_prompt, a_text, b_text, ab_text)
        winner = max(scores, key=lambda k: (scores[k], k == "A"))  # A wins ties
        if scores["A"] >= max(scores["B"], scores["AB"]):
            winner = "A"
        
        entry = {"pass": p, "winner": winner, "scores": scores,
                 "a_words": len(a_text.split()), "b_words": len(b_text.split()), "ab_words": len(ab_text.split())}
        history.append(entry)
        
        if winner == "A":
            consec_a += 1
        else:
            consec_a = 0
            a_text = b_text if winner == "B" else ab_text
        
        print(f"    {label} pass {p}: {winner} (A={scores['A']}, B={scores['B']}, AB={scores['AB']})")
        
        if consec_a >= CONVERGENCE_K:
            print(f"    {label} converged at pass {p}")
            break
    
    # Save
    (out_dir / "final_output.md").write_text(a_text)
    hist_file.write_text(json.dumps(history, indent=2))
    return history

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=int, help="Run specific task (1-5)")
    parser.add_argument("--eval-only", action="store_true")
    args = parser.parse_args()
    
    tasks = range(1, 6) if not args.task else [args.task]
    
    for task_num in tasks:
        task_file = TASKS_DIR / f"task_{task_num:02d}.md"
        if not task_file.exists():
            print(f"Task {task_num}: file not found, skipping")
            continue
        task_prompt = task_file.read_text().strip()
        
        print(f"\n{'='*60}")
        print(f"  Task {task_num}: {NUM_SEEDS} seeds")
        print(f"{'='*60}")
        
        if not args.eval_only:
            for seed in range(1, NUM_SEEDS+1):
                run_dir = OUT_DIR / f"task_{task_num:02d}" / f"seed_{seed:02d}"
                print(f"\n  Seed {seed}/{NUM_SEEDS}:")
                await run_autoreason(task_prompt, run_dir, label=f"T{task_num}S{seed}")
                await asyncio.sleep(2)
        
        # Summarize
        print(f"\n  Summary for Task {task_num}:")
        for seed in range(1, NUM_SEEDS+1):
            hist_file = OUT_DIR / f"task_{task_num:02d}" / f"seed_{seed:02d}" / "history.json"
            if hist_file.exists():
                hist = json.loads(hist_file.read_text())
                passes = len(hist) - 1
                converged = hist[-1].get("winner") == "A" and passes > 0
                words = hist[-1].get("a_words", "?")
                print(f"    Seed {seed}: {passes} passes, converged={converged}, words={words}")

if __name__ == "__main__":
    asyncio.run(main())
