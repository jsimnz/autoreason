#!/usr/bin/env python3
"""Generate charts for baseline comparison and pass15 vs pass25."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# =========================================================================
# Chart 1: Word count trajectories for all methods
# =========================================================================

trajectories = {
    "conservative": [847,847,856,862,865,865,865,862,869,863,862,859,859,858,858,862],
    "autoreason": [847,1079,1172,1172,1246,1340,1340,1574,1705,1705,1752,1622,1622,1800,1800,1800],
    "improve_this": [847,2196,2015,2098,2138,2048,2114,2137,2219,2082,2011,2057,2013,1999,1985,2116],
    "harsh_critic": [847,1352,1623,1765,2042,2391,2386,2367,2399,2078,2162,2395,2387,2353,2197,1961],
    "critique_and_revise": [847,1130,1561,1916,2060,2312,2437,2302,2502,2471,2435,2495,2510,2581,2524,2507],
}

colors = {
    "autoreason": "#4A90D9",
    "conservative": "#7B9E6B",
    "improve_this": "#E8A838",
    "harsh_critic": "#E85D75",
    "critique_and_revise": "#7B68AE",
}

fig, ax = plt.subplots(figsize=(14, 6))

passes = list(range(0, 16))
for name, traj in trajectories.items():
    style = '-' if name == 'autoreason' else '--'
    width = 2.5 if name == 'autoreason' else 1.5
    ax.plot(passes, traj, color=colors[name], linewidth=width, linestyle=style,
            marker='o', markersize=4, label=name, zorder=5 if name == 'autoreason' else 3)

ax.set_xlabel('Pass', fontsize=11)
ax.set_ylabel('Word count', fontsize=11)
ax.set_title('Word Count Trajectories: Autoreason vs Baselines (15 passes, same starting point)', fontsize=13, fontweight='bold')
ax.set_xticks(passes)
ax.set_ylim(700, 2700)
ax.grid(axis='y', alpha=0.2)
ax.legend(loc='upper left', fontsize=10, framealpha=0.9)

plt.tight_layout()
plt.savefig('/root/autoreason-experiment/experiments/v2/word_count_trajectories.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved word_count_trajectories.png")


# =========================================================================
# Chart 2: 5-way Borda scores
# =========================================================================

methods = ['autoreason', 'conservative', 'improve_this', 'harsh_critic', 'critique_and_revise']
scores = [35, 21, 18, 18, 13]
first_places = [7, 0, 0, 0, 0]
bar_colors = [colors[m] for m in methods]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

# Borda scores
bars = ax1.barh(methods, scores, color=bar_colors, alpha=0.85, edgecolor='white', linewidth=0.5)
ax1.set_xlabel('Borda Score (max 35)', fontsize=11)
ax1.set_title('7-Judge Blind Panel: Borda Scores', fontsize=13, fontweight='bold')
ax1.set_xlim(0, 38)
ax1.invert_yaxis()
for bar, score in zip(bars, scores):
    ax1.text(score + 0.5, bar.get_y() + bar.get_height()/2, str(score),
             va='center', fontsize=11, fontweight='bold')

# Word counts with final ranking
final_words = [1800, 862, 2116, 1961, 2507]
bars2 = ax2.barh(methods, final_words, color=bar_colors, alpha=0.85, edgecolor='white', linewidth=0.5)
ax2.set_xlabel('Final Word Count', fontsize=11)
ax2.set_title('Output Length After 15 Passes', fontsize=13, fontweight='bold')
ax2.set_xlim(0, 2800)
ax2.invert_yaxis()
for bar, wc in zip(bars2, final_words):
    ax2.text(wc + 30, bar.get_y() + bar.get_height()/2, str(wc),
             va='center', fontsize=10)

# Mark initial word count
ax2.axvline(x=847, color='#333333', linewidth=1, linestyle='--', alpha=0.5)
ax2.text(855, 4.7, 'initial (847)', fontsize=8, color='#555555')

plt.tight_layout()
plt.savefig('/root/autoreason-experiment/experiments/v2/baseline_comparison.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved baseline_comparison.png")


# =========================================================================
# Chart 3: Pass 15 vs Pass 25 judge results
# =========================================================================

fig, ax = plt.subplots(figsize=(8, 4))

categories = ['Pass 15\n(first convergence)', 'Pass 25\n(second convergence)']
wins = [6, 1]
bar_colors_conv = ['#4A90D9', '#AAAAAA']

bars = ax.bar(categories, wins, color=bar_colors_conv, width=0.5, alpha=0.85, edgecolor='white')
ax.set_ylabel('Judge Votes (out of 7)', fontsize=11)
ax.set_title('Does Continuing Past First Convergence Help?', fontsize=13, fontweight='bold')
ax.set_ylim(0, 8)
ax.set_yticks(range(0, 8))

for bar, w in zip(bars, wins):
    ax.text(bar.get_x() + bar.get_width()/2, w + 0.15, str(w),
            ha='center', fontsize=14, fontweight='bold')

ax.text(0.5, -0.15, 'Pass 15: 1800 words  |  Pass 25: 1758 words  |  10 extra passes, no improvement',
        transform=ax.transAxes, ha='center', fontsize=9, color='#666666', style='italic')

plt.tight_layout()
plt.savefig('/root/autoreason-experiment/experiments/v2/pass15_vs_pass25.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved pass15_vs_pass25.png")
