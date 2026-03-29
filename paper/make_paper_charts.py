#!/usr/bin/env python3
"""Generate all charts for the paper, including meta-section."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# =========================================================================
# Fig 1: v2 trajectory (26 passes) — existing
# =========================================================================
# Already generated at fig_trajectory.png, skip regeneration

# =========================================================================
# Fig 2: Baseline comparison — existing  
# =========================================================================
# Already generated at fig_baseline.png, skip regeneration

# =========================================================================
# Fig 3: Word count trajectories — existing
# =========================================================================
# Already generated at fig_wordcount.png, skip regeneration

# =========================================================================
# Fig 4: Pass 15 vs 25 — existing
# =========================================================================
# Already generated at fig_convergence.png, skip regeneration

# =========================================================================
# Fig 5: Paper run trajectory (9 passes, all Opus)
# =========================================================================

passes = list(range(0, 10))  # 0=initial, 1-9=passes
winners = ['init', 'AB', 'A', 'AB', 'AB', 'AB', 'AB', 'AB', 'A', 'A']
scores_a =  [0, 3, 9, 7, 4, 6, 6, 3, 9, 8]
scores_b =  [0, 6, 3, 3, 5, 3, 4, 6, 3, 5]
scores_ab = [0, 9, 6, 8, 9, 9, 8, 9, 6, 5]

colors = {'A': '#4A90D9', 'B': '#E85D75', 'AB': '#7B68AE', 'init': '#CCCCCC'}

fig, (ax_scores, ax_bars) = plt.subplots(2, 1, figsize=(10, 5), height_ratios=[3, 0.8], sharex=True)
fig.suptitle('Paper Autoreason Run — All Opus, Ground Truth Context (9 passes)', fontsize=13, fontweight='bold', y=0.98)

# Scores
ax_scores.plot(passes[1:], scores_a[1:], color=colors['A'], linewidth=2, marker='o', markersize=6, label='A (incumbent)', zorder=5)
ax_scores.plot(passes[1:], scores_b[1:], color=colors['B'], linewidth=2, marker='s', markersize=6, label='B (revision)', zorder=5)
ax_scores.plot(passes[1:], scores_ab[1:], color=colors['AB'], linewidth=2, marker='^', markersize=6, label='AB (synthesis)', zorder=5)

ax_scores.set_ylabel('Borda score (max 9)', fontsize=11)
ax_scores.set_ylim(1, 10)
ax_scores.set_yticks([3, 5, 6, 7, 8, 9])
ax_scores.grid(axis='y', alpha=0.2)
ax_scores.legend(loc='center left', fontsize=9, framealpha=0.9)

# Convergence markers
for p in [8, 9]:
    ax_scores.axvline(x=p, color='#4A90D9', linewidth=1, linestyle='--', alpha=0.4)
ax_scores.annotate('✔ converged', xy=(9, 8), xytext=(7.5, 9.5),
                    fontsize=9, color='#4A90D9', fontweight='bold',
                    arrowprops=dict(arrowstyle='->', color='#4A90D9', lw=1.2))

# Winner bars
winner_colors = [colors.get(w, '#CCC') for w in winners]
ax_bars.bar(passes, [1]*len(passes), color=winner_colors, width=0.7, alpha=0.9)
ax_bars.set_ylim(0, 1)
ax_bars.set_yticks([])
ax_bars.set_ylabel('Winner', fontsize=10)
ax_bars.set_xlabel('Pass', fontsize=11)
ax_bars.set_xticks(passes)
ax_bars.set_xticklabels(['init'] + [str(i) for i in range(1, 10)])

for i, w in enumerate(winners):
    if w != 'init':
        ax_bars.text(passes[i], 0.5, w, ha='center', va='center', fontsize=8,
                     fontweight='bold', color='white')

plt.tight_layout()
plt.subplots_adjust(hspace=0.08)
plt.savefig('/root/autoreason-experiment/paper/fig_paper_run.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved fig_paper_run.png")


# =========================================================================
# Fig 6: Hallucination detection — before/after ground truth critic
# =========================================================================

fig, ax = plt.subplots(figsize=(8, 3.5))

categories = ['Without\nground truth', 'With\nground truth']
hallucinations = [4, 0]  # fabricated ablation, CIs, wrong models, wrong roles
bar_colors = ['#E85D75', '#4A90D9']

bars = ax.bar(categories, hallucinations, color=bar_colors, width=0.45, alpha=0.85, edgecolor='white')
ax.set_ylabel('Hallucinated claims in initial draft', fontsize=11)
ax.set_title('Ground-Truth Critic Eliminates Hallucination', fontsize=13, fontweight='bold')
ax.set_ylim(0, 5.5)
ax.set_yticks(range(0, 6))

for bar, h in zip(bars, hallucinations):
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.15, str(h),
            ha='center', fontsize=14, fontweight='bold')

# Annotate what was hallucinated
ax.text(0, 3.5, 'fabricated ablation study\nfake confidence intervals\nwrong model names\nincorrect role descriptions',
        ha='center', fontsize=8, color='#666666', style='italic')

ax.text(1, 0.8, 'all claims verified\nagainst actual data',
        ha='center', fontsize=8, color='#666666', style='italic')

plt.tight_layout()
plt.savefig('/root/autoreason-experiment/paper/fig_hallucination.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved fig_hallucination.png")


# =========================================================================  
# Fig 7: Judge panel integrity — 2 vs 3 working judges
# =========================================================================

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.5))

# Left: broken panel (11 passes, no convergence)
ax1.bar(['Passes to\nconverge'], [11], color='#E85D75', width=0.4, alpha=0.85)
ax1.text(0, 11.5, '>11', ha='center', fontsize=14, fontweight='bold', color='#E85D75')
ax1.text(0, 9, '(did not\nconverge)', ha='center', fontsize=9, color='#666666', style='italic')
ax1.set_ylim(0, 15)
ax1.set_title('2 working judges\n(Gemini parser broken)', fontsize=11, fontweight='bold')
ax1.set_ylabel('Passes', fontsize=11)

# Right: fixed panel (2 passes to converge)
ax2.bar(['Passes to\nconverge'], [2], color='#4A90D9', width=0.4, alpha=0.85)
ax2.text(0, 2.5, '2', ha='center', fontsize=14, fontweight='bold', color='#4A90D9')
ax2.set_ylim(0, 15)
ax2.set_title('3 working judges\n(all Opus)', fontsize=11, fontweight='bold')

fig.suptitle('Judge Panel Integrity Affects Convergence', fontsize=13, fontweight='bold', y=1.02)

plt.tight_layout()
plt.savefig('/root/autoreason-experiment/paper/fig_judge_integrity.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved fig_judge_integrity.png")
