#!/usr/bin/env python3
"""Generate additional paper figures as vector PDFs."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# ── Match paper typography ──────────────────────────────────────────
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Palatino', 'Palatino Linotype', 'URW Palladio L', 'DejaVu Serif'],
    'font.size': 11,
    'axes.titlesize': 13,
    'axes.labelsize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'axes.linewidth': 0.8,
    'lines.linewidth': 2.0,
    'lines.markersize': 5,
})

out = '/root/autoreason-experiment/paper'

# =========================================================================
# Fig: Word count trajectories
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

labels = {
    "autoreason": "Autoreason",
    "conservative": "Conservative",
    "improve_this": "Improve this",
    "harsh_critic": "Harsh critic",
    "critique_and_revise": "Critique & revise",
}

fig, ax = plt.subplots(figsize=(10, 4.5))

passes = list(range(0, 16))
for name, traj in trajectories.items():
    style = '-' if name == 'autoreason' else '--'
    width = 2.5 if name == 'autoreason' else 1.5
    alpha = 1.0 if name == 'autoreason' else 0.75
    ax.plot(passes, traj, color=colors[name], linewidth=width, linestyle=style,
            marker='o', markersize=4 if name != 'autoreason' else 6,
            label=labels[name], zorder=5 if name == 'autoreason' else 3, alpha=alpha)

ax.set_xlabel('Pass')
ax.set_ylabel('Word count')
ax.set_xticks(passes)
ax.set_ylim(700, 2700)
ax.grid(axis='y', alpha=0.15)
ax.legend(loc='upper left', framealpha=0.9)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig(f'{out}/fig_wordcount.pdf', dpi=300, bbox_inches='tight', facecolor='white')
print("Saved fig_wordcount.pdf")


# =========================================================================
# Fig: Hallucination — before/after ground truth critic
# =========================================================================

fig, ax = plt.subplots(figsize=(6, 3.2))

categories = ['Without\nground truth', 'With\nground truth']
hallucinations = [4, 0]
bar_colors = ['#E85D75', '#4A90D9']

bars = ax.bar(categories, hallucinations, color=bar_colors, width=0.4, alpha=0.88)
ax.set_ylabel('Hallucinated claims')
ax.set_ylim(0, 5.5)
ax.set_yticks(range(0, 6))
ax.grid(axis='y', alpha=0.15)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

for bar, h in zip(bars, hallucinations):
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.18, str(h),
            ha='center', fontsize=14, fontweight='bold')

# Annotate what was hallucinated
ax.text(0, 2.8,
        'fabricated ablation\nfake confidence intervals\nwrong model names\nincorrect role descriptions',
        ha='center', fontsize=8, color='white', fontstyle='italic')

ax.text(1, 0.6, 'all claims verified\nagainst actual data',
        ha='center', fontsize=8, color='#666666', fontstyle='italic')

plt.tight_layout()
plt.savefig(f'{out}/fig_hallucination.pdf', dpi=300, bbox_inches='tight', facecolor='white')
print("Saved fig_hallucination.pdf")


# =========================================================================
# Fig: Judge panel integrity — 2 vs 3 working judges
# =========================================================================

fig, ax = plt.subplots(figsize=(6, 3.2))

labels_ji = ['2 judges\n(Gemini broken)', '3 judges\n(all Opus)']
passes_ji = [11, 2]
bar_colors_ji = ['#E85D75', '#4A90D9']

bars = ax.bar(labels_ji, passes_ji, color=bar_colors_ji, width=0.4, alpha=0.88)

ax.text(0, 11.8, '>11 (no convergence)', ha='center', fontsize=10, fontweight='bold', color='#E85D75')
ax.text(1, 2.8, '2', ha='center', fontsize=12, fontweight='bold', color='#4A90D9')

ax.set_ylabel('Passes to converge')
ax.set_ylim(0, 15)
ax.grid(axis='y', alpha=0.15)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig(f'{out}/fig_judge_integrity.pdf', dpi=300, bbox_inches='tight', facecolor='white')
print("Saved fig_judge_integrity.pdf")
