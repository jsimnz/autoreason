#!/usr/bin/env python3
"""
Batch 1: Free retroactive analysis on existing data.
1. Transitivity violations in judge rankings
2. ELO ratings for all versions across passes
3. Nash equilibrium analysis of incumbent pairwise matrix
"""

import json
import math
from pathlib import Path
from collections import defaultdict

root = Path(__file__).parent

# =========================================================================
# 1. Transitivity Analysis
# =========================================================================
print("=" * 60)
print("1. TRANSITIVITY ANALYSIS")
print("=" * 60)

def check_transitivity(ranking):
    """Check if a ranking has any transitive violations.
    A ranking [A, B, AB] means A > B > AB.
    No violations possible in a linear ranking from one judge.
    Violations occur across judges when aggregated preferences cycle."""
    return True  # Single rankings are always transitive

def check_panel_transitivity(rankings):
    """Check if majority preferences across a panel are transitive.
    Given multiple rankings, compute majority pairwise preferences
    and check for cycles (Condorcet paradox)."""
    candidates = set()
    for r in rankings:
        if r:
            candidates.update(r)
    candidates = sorted(candidates)
    
    # Count pairwise wins
    wins = defaultdict(lambda: defaultdict(int))
    for r in rankings:
        if not r:
            continue
        for i, a in enumerate(r):
            for b in r[i+1:]:
                wins[a][b] += 1
                
    # Check for cycles in majority preferences
    n = len(candidates)
    cycles = []
    for i, a in enumerate(candidates):
        for j, b in enumerate(candidates):
            if i >= j:
                continue
            for k, c in enumerate(candidates):
                if k <= j:
                    continue
                # Check A>B>C>A cycle
                ab = wins[a][b] > wins[b][a]
                bc = wins[b][c] > wins[c][b]
                ca = wins[c][a] > wins[a][c]
                if ab and bc and ca:
                    cycles.append((a, b, c, "A>B>C>A"))
                # Check A>C>B>A cycle
                ac = wins[a][c] > wins[c][a]
                cb = wins[c][b] > wins[b][c]
                ba = wins[b][a] > wins[a][b]
                if ac and cb and ba:
                    cycles.append((a, c, b, "A>C>B>A"))
    return cycles

# Analyze task 1 (26-pass run)
task1_dir = root / "results_v2" / "task_01"
total_passes = 0
cycle_count = 0

for pass_dir in sorted(task1_dir.glob("pass_*")):
    result_file = pass_dir / "result.json"
    if not result_file.exists():
        continue
    data = json.loads(result_file.read_text())
    rankings = []
    for jd in data.get("judge_details", []):
        r = jd.get("ranking")
        if r:
            rankings.append(r)
    
    if len(rankings) >= 2:
        total_passes += 1
        cycles = check_panel_transitivity(rankings)
        if cycles:
            cycle_count += 1
            pass_num = pass_dir.name
            print(f"  {pass_num}: CYCLE detected — {cycles[0]}")

print(f"\n  Task 1 (26 passes): {cycle_count} passes with Condorcet cycles out of {total_passes}")
print(f"  Cycle rate: {cycle_count/total_passes*100:.0f}%")

# Analyze all multi-task runs
print(f"\n  Multi-task analysis:")
for task_num in range(2, 6):
    task_dir = root / "results_multi_task" / f"task_{task_num:02d}" / "autoreason"
    tp = 0
    cc = 0
    for pass_dir in sorted(task_dir.glob("pass_*")):
        result_file = pass_dir / "result.json"
        if not result_file.exists():
            continue
        data = json.loads(result_file.read_text())
        rankings = [jd.get("ranking") for jd in data.get("judge_details", []) if jd.get("ranking")]
        if len(rankings) >= 2:
            tp += 1
            if check_panel_transitivity(rankings):
                cc += 1
    if tp > 0:
        print(f"  Task {task_num}: {cc}/{tp} passes with cycles ({cc/tp*100:.0f}%)")

# =========================================================================
# 2. ELO Rating Analysis
# =========================================================================
print(f"\n{'='*60}")
print("2. ELO RATING ANALYSIS")
print("=" * 60)

def update_elo(winner_elo, loser_elo, k=32):
    """Standard ELO update."""
    expected_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
    expected_loser = 1 - expected_winner
    new_winner = winner_elo + k * (1 - expected_winner)
    new_loser = loser_elo + k * (0 - expected_loser)
    return new_winner, new_loser

# Task 1: track ELO of each incumbent version
print(f"\n  Task 1 ELO progression:")

history_file = task1_dir / "history.json"
if not history_file.exists():
    # Build from pass results
    history = []
    for pass_dir in sorted(task1_dir.glob("pass_*")):
        rf = pass_dir / "result.json"
        if rf.exists():
            d = json.loads(rf.read_text())
            history.append(d)
else:
    history = json.loads(history_file.read_text())

# Each version starts at 1500
# When B or AB wins, new incumbent gets winner ELO, old gets loser ELO
incumbent_elo = 1500
elo_history = [1500]
version_elos = {"v0": 1500}  # initial version

for i, h in enumerate(history):
    winner = h.get("winner", "A")
    scores = h.get("scores", {})
    
    if winner == "A":
        # Incumbent defended — ELO goes up
        # Treat the best challenger score as the opponent
        challenger_score = max(scores.get("B", 0), scores.get("AB", 0))
        incumbent_score = scores.get("A", 0)
        if incumbent_score > challenger_score:
            incumbent_elo, _ = update_elo(incumbent_elo, 1500, k=32)
        elo_history.append(incumbent_elo)
    else:
        # Challenger won — new incumbent
        _, old_elo = update_elo(1500, incumbent_elo, k=32)
        incumbent_elo = 1500 + 32  # New version starts slightly above baseline
        elo_history.append(incumbent_elo)

print(f"  Initial ELO: 1500")
print(f"  Final ELO: {incumbent_elo:.0f}")
print(f"  Peak ELO: {max(elo_history):.0f} (pass {elo_history.index(max(elo_history))})")
print(f"  ELO at pass 15: {elo_history[15]:.0f}")
print(f"  ELO at pass 25: {elo_history[25]:.0f}")

# Check if ELO plateaued
window = 5
if len(elo_history) > window * 2:
    first_half_avg = sum(elo_history[window:window*2]) / window
    second_half_avg = sum(elo_history[-window:]) / window
    print(f"  Early avg (passes 5-10): {first_half_avg:.0f}")
    print(f"  Late avg (last 5): {second_half_avg:.0f}")
    print(f"  Plateau: {'Yes' if abs(first_half_avg - second_half_avg) < 50 else 'No'}")

# =========================================================================
# 3. Nash Equilibrium Analysis
# =========================================================================
print(f"\n{'='*60}")
print("3. NASH EQUILIBRIUM ANALYSIS")
print("=" * 60)

# Build pairwise comparison matrix from 5-way judge panels
# Use the overnight results
print(f"\n  Pairwise win rates from 5-way judge panels (all tasks):")

methods = ["autoreason", "critique_and_revise", "harsh_critic", "conservative", "improve_this"]
pairwise_wins = {m: {n: 0 for n in methods} for m in methods}
total_comparisons = 0

for task_num in range(2, 6):
    judge_file = root / "results_multi_task" / f"task_{task_num:02d}" / "comparison" / "5way_results.json"
    if not judge_file.exists():
        continue
    data = json.loads(judge_file.read_text())
    borda = data.get("borda", {})
    
    # From Borda scores, infer pairwise preferences
    # Higher Borda = more judges ranked it above others
    sorted_methods = sorted(borda.items(), key=lambda x: -x[1])
    for i, (m1, s1) in enumerate(sorted_methods):
        for j, (m2, s2) in enumerate(sorted_methods):
            if i < j and m1 in methods and m2 in methods:
                pairwise_wins[m1][m2] += 1
                total_comparisons += 1

# Add task 1 from original comparison
task1_borda = {"autoreason": 35, "conservative": 21, "improve_this": 18, "harsh_critic": 18, "critique_and_revise": 13}
sorted_t1 = sorted(task1_borda.items(), key=lambda x: -x[1])
for i, (m1, s1) in enumerate(sorted_t1):
    for j, (m2, s2) in enumerate(sorted_t1):
        if i < j and m1 in methods and m2 in methods:
            pairwise_wins[m1][m2] += 1

# Print pairwise matrix
print(f"\n  {'':25s}", end="")
for m in methods:
    print(f" {m[:6]:>6s}", end="")
print()

for m1 in methods:
    print(f"  {m1:25s}", end="")
    for m2 in methods:
        if m1 == m2:
            print(f"    ---", end="")
        else:
            w = pairwise_wins[m1][m2]
            l = pairwise_wins[m2][m1]
            total = w + l
            rate = w / total if total > 0 else 0.5
            print(f"  {rate:.2f}", end="")
    print()

# Compute dominance
print(f"\n  Dominance (wins across all pairwise matchups):")
for m in methods:
    total_wins = sum(pairwise_wins[m][n] for n in methods if n != m)
    total_losses = sum(pairwise_wins[n][m] for n in methods if n != m)
    total = total_wins + total_losses
    rate = total_wins / total if total > 0 else 0.5
    print(f"  {m:25s} {total_wins}W / {total_losses}L ({rate:.1%})")

# Check for non-transitive relationships
print(f"\n  Non-transitive triples (A beats B, B beats C, C beats A):")
found_cycles = False
for i, a in enumerate(methods):
    for j, b in enumerate(methods):
        if j <= i: continue
        for k, c in enumerate(methods):
            if k <= j: continue
            ab = pairwise_wins[a][b] > pairwise_wins[b][a]
            bc = pairwise_wins[b][c] > pairwise_wins[c][b]
            ca = pairwise_wins[c][a] > pairwise_wins[a][c]
            if ab and bc and ca:
                print(f"  {a} > {b} > {c} > {a}")
                found_cycles = True
            ac = pairwise_wins[a][c] > pairwise_wins[c][a]
            cb = pairwise_wins[c][b] > pairwise_wins[b][c]
            ba = pairwise_wins[b][a] > pairwise_wins[a][b]
            if ac and cb and ba:
                print(f"  {a} > {c} > {b} > {a}")
                found_cycles = True

if not found_cycles:
    print(f"  None — preferences are fully transitive across methods")

print(f"\n{'='*60}")
print("ANALYSIS COMPLETE")
print("=" * 60)
