#!/usr/bin/env python3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

passes = list(range(1, 27))
winners = ['B','AB','A','AB','AB','A','AB','AB','A','AB','AB','A','AB','A','A','AB','B','AB','B','B','B','AB','AB','A','A','AB']
word_counts = [847,1079,1172,1172,1246,1340,1340,1574,1705,1705,1752,1622,1622,1800,1800,1800,1839,2037,1707,1644,2008,1702,1639,1758,1758,1617]

scores_a =  [3,4,7,6,5,6,4,5,7,5,5,7,7,8,7,7,6,5,4,4,4,5,5,9,7,4]
scores_b =  [9,6,7,3,5,6,6,5,6,5,6,4,3,6,4,3,7,5,8,8,9,6,5,5,5,6]
scores_ab = [6,8,4,9,8,6,8,8,5,8,7,7,8,4,7,8,5,8,6,6,5,7,8,4,6,8]

colors = {'A': '#4A90D9', 'B': '#E85D75', 'AB': '#7B68AE'}
winner_colors = [colors[w] for w in winners]

fig, (ax_scores, ax_wc, ax_bars) = plt.subplots(3, 1, figsize=(14, 9), height_ratios=[3, 2, 0.8], sharex=True)
fig.suptitle('Autoreason v2 — Task 01 Trajectory (26 passes)', fontsize=14, fontweight='bold', y=0.98)

# Phase shading on all panels
for ax in [ax_scores, ax_wc, ax_bars]:
    ax.axvspan(0.5, 5.5, alpha=0.05, color='green', zorder=0)
    ax.axvspan(5.5, 16.5, alpha=0.05, color='orange', zorder=0)
    ax.axvspan(16.5, 26.5, alpha=0.05, color='red', zorder=0)

# Near-convergence markers on all panels
for ax in [ax_scores, ax_wc, ax_bars]:
    for p in [14, 15]:
        ax.axvline(x=p, color='#4A90D9', linewidth=1, linestyle='--', alpha=0.35, zorder=1)
    for p in [24, 25]:
        ax.axvline(x=p, color='#4A90D9', linewidth=1, linestyle='--', alpha=0.35, zorder=1)

# --- TOP: Judge scores ---
ax_scores.plot(passes, scores_a, color=colors['A'], linewidth=2, marker='o', markersize=5, label='A', zorder=5)
ax_scores.plot(passes, scores_b, color=colors['B'], linewidth=2, marker='s', markersize=5, label='B', zorder=5)
ax_scores.plot(passes, scores_ab, color=colors['AB'], linewidth=2, marker='^', markersize=5, label='AB', zorder=5)
ax_scores.set_ylabel('Borda score (max 9)', fontsize=10)
ax_scores.set_ylim(2, 10)
ax_scores.set_yticks([3, 4, 5, 6, 7, 8, 9])
ax_scores.grid(axis='y', alpha=0.2)
ax_scores.legend(loc='upper right', fontsize=9, framealpha=0.9, ncol=3)

# Phase labels
ax_scores.text(3, 9.7, 'Rapid improvement', ha='center', fontsize=9, color='#2d7d2d', fontweight='bold')
ax_scores.text(11, 9.7, 'Quality plateau', ha='center', fontsize=9, color='#b37700', fontweight='bold')
ax_scores.text(21.5, 9.7, 'Bloat/prune oscillation', ha='center', fontsize=9, color='#b33030', fontweight='bold')

# Convergence annotations
ax_scores.annotate('★ 2/3', xy=(15, scores_a[14]), xytext=(16.2, 9.2),
            fontsize=8, ha='left', color='#4A90D9', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='#4A90D9', lw=1.2))
ax_scores.annotate('★ 2/3', xy=(25, scores_a[24]), xytext=(23, 9.2),
            fontsize=8, ha='right', color='#4A90D9', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='#4A90D9', lw=1.2))

# --- MIDDLE: Word count ---
ax_wc.fill_between(passes, word_counts, alpha=0.08, color='#555555')
ax_wc.plot(passes, word_counts, color='#333333', linewidth=2, zorder=5, marker='o', markersize=4)
ax_wc.set_ylabel('Word count', fontsize=10)
ax_wc.set_ylim(700, 2200)
ax_wc.grid(axis='y', alpha=0.2)

# --- BOTTOM: Winner bars ---
ax_bars.bar(passes, [1]*len(passes), color=winner_colors, width=0.75, alpha=0.9)
ax_bars.set_ylim(0, 1)
ax_bars.set_yticks([])
ax_bars.set_ylabel('Winner', fontsize=10)
ax_bars.set_xlabel('Pass', fontsize=11)
ax_bars.set_xticks(passes)
ax_bars.set_xlim(0.3, 26.7)

for i, w in enumerate(winners):
    ax_bars.text(passes[i], 0.5, w, ha='center', va='center', fontsize=7,
                fontweight='bold', color='white')

# Legend below chart
legend_patches = [
    mpatches.Patch(color=colors['A'], label='A (incumbent survives)', alpha=0.9),
    mpatches.Patch(color=colors['B'], label='B (revision displaces)', alpha=0.9),
    mpatches.Patch(color=colors['AB'], label='AB (synthesis displaces)', alpha=0.9),
]
fig.legend(handles=legend_patches, loc='lower center', ncol=3, fontsize=10,
           framealpha=0.9, bbox_to_anchor=(0.5, -0.01))

plt.tight_layout()
plt.subplots_adjust(bottom=0.08, hspace=0.1)
plt.savefig('/root/autoreason-experiment/trajectory_chart.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved")
