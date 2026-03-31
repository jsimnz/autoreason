#!/usr/bin/env python3
"""Generate the scaling story figure: unconstrained failure vs constrained success."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Palatino', 'Palatino Linotype', 'URW Palladio L', 'DejaVu Serif'],
    'font.size': 11,
    'axes.titlesize': 12,
    'axes.labelsize': 11,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'axes.linewidth': 0.8,
})

out = '/root/autoreason-experiment/paper'

# ── Data ────────────────────────────────────────────────────────────
# Unconstrained (Task 2, Sonnet 4.6): autoreason loses
unconstrained = {
    'Autoreason': 7,
    'Critique &\nrevise': 31,
    'Improve\nthis': 30,
    'Harsh\ncritic': 23,
    'Conservative': 14,
}

# Constrained (500w pitch, Sonnet 4.6): autoreason wins
constrained = {
    'Autoreason': 30,
    'Critique &\nrevise': 10,
    'Improve\nthis': 27,
    'Harsh\ncritic': 13,
    'Conservative': 25,
}

methods = list(unconstrained.keys())
unc_scores = [unconstrained[m] for m in methods]
con_scores = [constrained[m] for m in methods]

# Color autoreason differently
colors_unc = ['#E85D75' if m == 'Autoreason' else '#BBBBBB' for m in methods]
colors_con = ['#4A90D9' if m == 'Autoreason' else '#BBBBBB' for m in methods]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4), sharey=True)

# Left: unconstrained (autoreason loses)
y = np.arange(len(methods))
bars1 = ax1.barh(y, unc_scores, color=colors_unc, alpha=0.88, height=0.55)
ax1.set_yticks(y)
ax1.set_yticklabels(methods)
ax1.set_xlabel('Borda Score')
ax1.set_xlim(0, 38)
ax1.set_title('Unconstrained Task\n(Sonnet 4.6, Task 2)', fontweight='bold')
ax1.grid(axis='x', alpha=0.15)
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)
for bar, score in zip(bars1, unc_scores):
    ax1.text(score + 0.5, bar.get_y() + bar.get_height()/2, str(score),
             ha='left', va='center', fontsize=10, fontweight='bold')
ax1.text(0.95, 0.05, 'autoreason: last place',
         transform=ax1.transAxes, ha='right', va='bottom',
         fontsize=9, fontstyle='italic', color='#E85D75')

# Right: constrained (autoreason wins)
bars2 = ax2.barh(y, con_scores, color=colors_con, alpha=0.88, height=0.55)
ax2.set_xlabel('Borda Score')
ax2.set_xlim(0, 38)
ax2.set_title('Scope-Constrained Task\n(Sonnet 4.6, 500w pitch)', fontweight='bold')
ax2.grid(axis='x', alpha=0.15)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)
for bar, score in zip(bars2, con_scores):
    ax2.text(score + 0.5, bar.get_y() + bar.get_height()/2, str(score),
             ha='left', va='center', fontsize=10, fontweight='bold')
ax2.text(0.95, 0.05, 'autoreason: first place',
         transform=ax2.transAxes, ha='right', va='bottom',
         fontsize=9, fontstyle='italic', color='#4A90D9')

plt.tight_layout()
plt.savefig(f'{out}/fig_scaling_story.pdf', dpi=300, bbox_inches='tight', facecolor='white')
print("Saved fig_scaling_story.pdf")
