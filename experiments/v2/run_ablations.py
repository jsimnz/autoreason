#!/usr/bin/env python3
"""
Component ablation experiments for autoreason.
Tests: judge count (1v3v7), Borda vs majority, synthesis-only, revision-only.

Uses Task 1 (GTM strategy) with Sonnet 4, running each ablation to convergence.
Also runs length-controlled evaluation: truncate all outputs to median length before judging.

Usage:
    python run_ablations.py                    # run all
    python run_ablations.py --ablation judges  # just judge count
    python run_ablations.py --eval-only        # skip runs, evaluate
"""
import argparse, asyncio, json, os, random, time, re
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
MAX_PASSES = 25
CONVERGENCE_K = 2

ROOT = Path(__file__).parent
TASKS_DIR = ROOT.parent.parent / "tasks"
OUT_DIR = ROOT / "results_ablations"

# --- Prompts (same as main experiments) ---
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
    for attempt in range(6):
        try:
            resp = await litellm.acompletion(
                model=MODEL, temperature=temp, max_tokens=MAX_TOKENS,
                messages=[{"role":"system","content":system},{"role":"user","content":user}]
            )
            return resp.choices[0].message.content
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e) or "529" in str(e):
                wait = min((2 ** attempt) * 5, 120)
                print(f"      [Rate limited, retry {attempt+1} in {wait}s]")
                await asyncio.sleep(wait)
            elif attempt < 5:
                await asyncio.sleep(10)
            else:
                raise

def parse_ranking(text):
    for line in reversed(text.split("\n")):
        line = line.strip().strip("*").strip()
        if line.upper().startswith("RANKING:"):
            raw = line.split(":", 1)[1].strip()
            items = [c for c in raw if c in "123"]
            if len(items) >= 2:
                return items
    return None

def aggregate_borda(rankings, labels, tiebreak=None):
    scores = {l: 0 for l in labels}
    n = len(labels)
    valid = [r for r in rankings if r is not None]
    for ranking in valid:
        for pos, label in enumerate(ranking):
            if label in scores and pos < n:
                scores[label] += (n - pos)
    if tiebreak:
        ranked = sorted(scores.keys(), key=lambda k: (-scores[k], 0 if k == tiebreak else 1))
    else:
        ranked = sorted(scores.keys(), key=lambda k: -scores[k])
    return ranked[0], scores, valid

def aggregate_majority(rankings, labels, tiebreak=None):
    """Majority vote: count first-place votes only."""
    votes = {l: 0 for l in labels}
    valid = [r for r in rankings if r is not None]
    for ranking in valid:
        if ranking:
            first = ranking[0]
            if first in votes:
                votes[first] += 1
    if tiebreak:
        ranked = sorted(votes.keys(), key=lambda k: (-votes[k], 0 if k == tiebreak else 1))
    else:
        ranked = sorted(votes.keys(), key=lambda k: -votes[k])
    return ranked[0], votes, valid

async def judge_3way(task, a_text, b_text, ab_text, n_judges=3, aggregation="borda"):
    labels_map = {}
    candidates = [("A", a_text), ("B", b_text), ("AB", ab_text)]
    random.shuffle(candidates)
    
    for i, (real_label, _) in enumerate(candidates, 1):
        labels_map[str(i)] = real_label
    
    parts = "\n\n".join(f"PROPOSAL {i+1}:\n---\n{candidates[i][1]}\n---" for i in range(3))
    prompt = (f"ORIGINAL TASK:\n---\n{task}\n---\n\n{parts}\n\n"
              "For each proposal, think step by step about what it gets right and wrong.\n"
              "Then rank all three:\nRANKING: [best], [second], [worst]\nWhere each slot is 1, 2, or 3.")
    
    tasks = [call_llm(COT_JUDGE_SYSTEM, prompt, JUDGE_TEMP) for _ in range(n_judges)]
    resps = await asyncio.gather(*tasks, return_exceptions=True)
    
    rankings = []
    for resp in resps:
        if isinstance(resp, Exception):
            rankings.append(None)
        else:
            raw = parse_ranking(resp)
            mapped = [labels_map.get(r, r) for r in raw] if raw else None
            rankings.append(mapped)
    
    if aggregation == "borda":
        return aggregate_borda(rankings, ["A", "B", "AB"], tiebreak="A")
    else:
        return aggregate_majority(rankings, ["A", "B", "AB"], tiebreak="A")

async def run_autoreason_ablation(task_prompt, out_dir, label="",
                                   n_judges=3, aggregation="borda",
                                   include_synthesis=True, include_revision=True):
    out_dir.mkdir(parents=True, exist_ok=True)
    hist_file = out_dir / "history.json"
    if hist_file.exists():
        print(f"    {label} cached")
        return json.loads(hist_file.read_text())
    
    a_text = await call_llm(AUTHOR_SYSTEM, f"{task_prompt}\n\nProduce a complete, detailed proposal.")
    (out_dir / "initial_a.md").write_text(a_text)
    history = [{"pass": 0, "winner": "A", "a_words": len(a_text.split())}]
    consec_a = 0
    
    for p in range(1, MAX_PASSES + 1):
        # Critic
        critique = await call_llm(CRITIC_SYSTEM,
            f"Here is a proposal:\n---\n{a_text}\n---\n\nORIGINAL TASK:\n{task_prompt}\n\nFind real problems.")
        
        # Author B (revision)
        if include_revision:
            b_text = await call_llm(AUTHOR_B_SYSTEM,
                f"ORIGINAL TASK:\n---\n{task_prompt}\n---\n\nCURRENT VERSION:\n---\n{a_text}\n---\n\n"
                f"CRITIQUE:\n---\n{critique}\n---\n\nRevise to address these problems.")
        else:
            b_text = a_text  # no revision, B = A
        
        # Synthesizer
        if include_synthesis:
            versions = [(a_text, "X"), (b_text, "Y")]
            random.shuffle(versions)
            ab_text = await call_llm(SYNTHESIZER_SYSTEM,
                f"ORIGINAL TASK:\n---\n{task_prompt}\n---\n\nVERSION {versions[0][1]}:\n---\n{versions[0][0]}\n---\n\n"
                f"VERSION {versions[1][1]}:\n---\n{versions[1][0]}\n---\n\nProduce a synthesis.")
        else:
            ab_text = b_text  # no synthesis, AB = B
        
        # Judge
        winner, scores, valid = await judge_3way(task_prompt, a_text, b_text, ab_text,
                                                  n_judges=n_judges, aggregation=aggregation)
        
        # Conservative tiebreak
        if scores.get("A", 0) >= max(scores.get("B", 0), scores.get("AB", 0)):
            winner = "A"
        
        entry = {"pass": p, "winner": winner, "scores": scores,
                 "a_words": len(a_text.split()), "b_words": len(b_text.split()),
                 "ab_words": len(ab_text.split()), "valid_judges": len(valid)}
        history.append(entry)
        
        if winner == "A":
            consec_a += 1
        else:
            consec_a = 0
            a_text = b_text if winner == "B" else ab_text
        
        print(f"    {label} pass {p}: {winner} (A={scores.get('A',0)}, B={scores.get('B',0)}, AB={scores.get('AB',0)})")
        
        if consec_a >= CONVERGENCE_K:
            print(f"    {label} converged at pass {p}")
            break
    
    (out_dir / "final_output.md").write_text(a_text)
    hist_file.write_text(json.dumps(history, indent=2))
    return history


async def run_length_controlled_eval(task_prompt, out_dir):
    """Re-evaluate existing outputs with length normalization."""
    # Load final outputs - Task 1 is split across different result dirs
    ar_out = (ROOT / "results_multi_seed" / "task_01" / "seed_01" / "final_output.md").read_text()
    
    baselines = {}
    bl_dir = ROOT / "results_baselines" / "task_01"
    for name in ["harsh_critic", "improve_this", "conservative"]:
        f = bl_dir / name / "final_output.md"
        if f.exists():
            baselines[name] = f.read_text()
    # Also check multi_task for tasks 2-5 baselines that have critique_and_revise
    mt_dir = ROOT / "results_multi_task" / "task_02"
    if (mt_dir / "baselines" / "critique_and_revise" / "final_output.md").exists():
        baselines["critique_and_revise"] = (mt_dir / "baselines" / "critique_and_revise" / "final_output.md").read_text()
    
    # Find median word count
    all_outputs = [ar_out] + list(baselines.values())
    word_counts = [len(o.split()) for o in all_outputs]
    median_wc = sorted(word_counts)[len(word_counts) // 2]
    print(f"  Word counts: {word_counts}, median: {median_wc}")
    
    # Truncate all to median
    def truncate(text, max_words):
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + "\n\n[truncated to " + str(max_words) + " words]"
    
    ar_trunc = truncate(ar_out, median_wc)
    baselines_trunc = {k: truncate(v, median_wc) for k, v in baselines.items()}
    
    # Run 7-judge evaluation: autoreason vs each baseline
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    
    for bname, btext in baselines_trunc.items():
        print(f"  Evaluating AR vs {bname} (truncated to {median_wc} words)...")
        # Use pairwise comparison
        wins = {"AR": 0, bname: 0, "tie": 0}
        for _ in range(7):
            if random.random() < 0.5:
                order = [("X", ar_trunc), ("Y", btext)]
                x_is = "AR"
            else:
                order = [("X", btext), ("Y", ar_trunc)]
                x_is = bname
            
            prompt = (f"ORIGINAL TASK:\n---\n{task_prompt}\n---\n\n"
                      f"VERSION X:\n---\n{order[0][1]}\n---\n\n"
                      f"VERSION Y:\n---\n{order[1][1]}\n---\n\n"
                      "Which version better accomplishes the task? Think step by step, then answer:\n"
                      "WINNER: X or Y")
            
            resp = await call_llm(COT_JUDGE_SYSTEM, prompt, JUDGE_TEMP)
            if "WINNER: X" in resp.upper() or "WINNER:X" in resp.upper():
                wins[x_is] += 1
            elif "WINNER: Y" in resp.upper() or "WINNER:Y" in resp.upper():
                wins["AR" if x_is == bname else bname] += 1
            else:
                wins["tie"] += 1
        
        results[bname] = wins
        print(f"    {wins}")
    
    (out_dir / "length_controlled_results.json").write_text(json.dumps(results, indent=2))
    return results


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ablation", choices=["judges", "aggregation", "components", "length", "all"], default="all")
    parser.add_argument("--eval-only", action="store_true")
    args = parser.parse_args()
    
    task_prompt = (TASKS_DIR / "task_01.md").read_text().strip()
    
    ablations = {
        "judges": [
            ("1_judge_borda", {"n_judges": 1, "aggregation": "borda"}),
            ("3_judge_borda", {"n_judges": 3, "aggregation": "borda"}),
            ("7_judge_borda", {"n_judges": 7, "aggregation": "borda"}),
        ],
        "aggregation": [
            ("3_judge_borda", {"n_judges": 3, "aggregation": "borda"}),
            ("3_judge_majority", {"n_judges": 3, "aggregation": "majority"}),
        ],
        "components": [
            ("full_autoreason", {"include_synthesis": True, "include_revision": True}),
            ("no_synthesis", {"include_synthesis": False, "include_revision": True}),
            ("no_revision", {"include_synthesis": True, "include_revision": False}),
        ],
    }
    
    to_run = list(ablations.keys()) if args.ablation == "all" else [args.ablation]
    if args.ablation == "all":
        to_run.append("length")
    
    for group in to_run:
        if group == "length":
            print(f"\n{'='*60}")
            print(f"  Length-Controlled Evaluation")
            print(f"{'='*60}")
            if not args.eval_only:
                await run_length_controlled_eval(task_prompt, OUT_DIR / "length_controlled")
            continue
            
        print(f"\n{'='*60}")
        print(f"  Ablation: {group}")
        print(f"{'='*60}")
        
        if args.eval_only:
            continue
            
        for name, params in ablations[group]:
            print(f"\n  {name}:")
            run_dir = OUT_DIR / group / name
            await run_autoreason_ablation(
                task_prompt, run_dir, label=name,
                n_judges=params.get("n_judges", 3),
                aggregation=params.get("aggregation", "borda"),
                include_synthesis=params.get("include_synthesis", True),
                include_revision=params.get("include_revision", True),
            )
            await asyncio.sleep(2)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    for group_name in ["judges", "aggregation", "components"]:
        group_dir = OUT_DIR / group_name
        if not group_dir.exists():
            continue
        print(f"\n  {group_name}:")
        for run_dir in sorted(group_dir.iterdir()):
            hist_file = run_dir / "history.json"
            if hist_file.exists():
                hist = json.loads(hist_file.read_text())
                passes = len(hist) - 1
                converged = passes > 0 and hist[-1].get("winner") == "A"
                words = hist[-1].get("a_words", "?")
                a_wins = sum(1 for h in hist[1:] if h.get("winner") == "A")
                print(f"    {run_dir.name}: {passes} passes, conv={converged}, "
                      f"words={words}, A_wins={a_wins}/{passes}")
    
    # Length controlled
    lc_file = OUT_DIR / "length_controlled" / "length_controlled_results.json"
    if lc_file.exists():
        lc = json.loads(lc_file.read_text())
        print(f"\n  Length-controlled (7 judges each):")
        for bname, wins in lc.items():
            print(f"    AR vs {bname}: AR={wins.get('AR',0)}, {bname}={wins.get(bname,0)}, tie={wins.get('tie',0)}")

if __name__ == "__main__":
    asyncio.run(main())
