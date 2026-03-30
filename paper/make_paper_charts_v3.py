#!/usr/bin/env python3
"""Generate final charts including summary and appendix trajectories."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import json
from pathlib import Path

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
    'lines.markersize': 8,
})

out = '/root/autoreason-experiment/paper'
colors = {'A': '#4A90D9', 'B': '#E85D75', 'AB': '#7B68AE'}

# =========================================================================
# Fig: Average rank summary
# =========================================================================

methods = ['Autoreason', 'Critique &\nRevise', 'Harsh\nCritic', 'Conservative', 'Improve\nThis']
avg_borda = [
    np.mean([35, 19, 29, 25, 31]),
    np.mean([13, 22, 26, 32, 19]),
    np.mean([18, 19, 27, 20, 26]),
    np.mean([21, 19, 15, 18, 15]),
    np.mean([18, 11, 8, 10, 14]),
]
# Compute average rank per task
all_scores = {
    'Autoreason': [35, 19, 29, 25, 31],
    'C&R': [13, 22, 26, 32, 19],
    'Harsh': [18, 19, 27, 20, 26],
    'Conservative': [21, 19, 15, 18, 15],
    'Improve': [18, 11, 8, 10, 14],
}
method_keys = list(all_scores.keys())
avg_ranks = []
for mk in method_keys:
    ranks = []
    for t in range(5):
        task_scores = [(all_scores[m][t], m) for m in method_keys]
        task_scores.sort(reverse=True)
        for rank, (score, m) in enumerate(task_scores, 1):
            if m == mk:
                ranks.append(rank)
                break
    avg_ranks.append(np.mean(ranks))

bar_colors = ['#4A90D9', '#7B68AE', '#E85D75', '#7B9E6B', '#E8A838']

# Sort by score descending for clean visual
method_labels_clean = ['Autoreason', 'Critique &\nRevise', 'Harsh\nCritic', 'Conservative', 'Improve\nThis']
order = np.argsort(avg_borda)  # ascending
labels_sorted = [method_labels_clean[i] for i in order]
scores_sorted = [avg_borda[i] for i in order]
ranks_sorted = [avg_ranks[i] for i in order]
colors_sorted = [bar_colors[i] for i in order]

fig, ax = plt.subplots(figsize=(8, 3.5))

bars = ax.barh(labels_sorted, scores_sorted, color=colors_sorted, alpha=0.88, height=0.55)

for bar, score, rank in zip(bars, scores_sorted, ranks_sorted):
    # Score label at end of bar
    ax.text(score + 0.4, bar.get_y() + bar.get_height()/2,
            f'{score:.1f}',
            ha='left', va='center', fontsize=11, fontweight='bold')
    # Rank label inside bar
    ax.text(1.5, bar.get_y() + bar.get_height()/2,
            f'rank {rank:.1f}',
            ha='left', va='center', fontsize=9, color='white', fontstyle='italic')

ax.set_xlabel('Average Borda Score (max 35)', fontsize=12)
ax.set_xlim(0, 36)
ax.grid(axis='x', alpha=0.15)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig(f'{out}/fig_summary.pdf', dpi=300, bbox_inches='tight', facecolor='white')
print("Saved fig_summary.pdf")


# =========================================================================
# Appendix: All trajectory trees (compact, stacked)
# =========================================================================

root = Path('/root/autoreason-experiment/experiments/v2')

trajectories = {}

# Task 1 (26 passes, original)
trajectories['Task 1: GTM Strategy (26 passes)'] = \
    ['B','AB','A','AB','AB','A','AB','AB','A','AB','AB','A','AB','A','A','AB','B','AB','B','B','B','AB','AB','A','A','AB']

# Tasks 2-5
task_names = {2: 'Notification System', 3: 'Remote Work Policy', 4: 'Code Review Positioning', 5: 'Incident Response'}
for t in range(2, 6):
    hist_file = root / "results_multi_task" / f"task_{t:02d}" / "autoreason" / "history.json"
    if hist_file.exists():
        history = json.loads(hist_file.read_text())
        traj = [h['winner'] for h in history]
        trajectories[f'Task {t}: {task_names[t]} ({len(traj)} passes)'] = traj

# MC runs
mc_dir = root / "results_monte_carlo" / "task_01"
for i in range(1, 6):
    hist_file = mc_dir / f"run_{i:02d}" / "history.json"
    if hist_file.exists():
        history = json.loads(hist_file.read_text())
        traj = [h['winner'] for h in history]
        conv = 'Y' if traj[-1] == 'A' and len(traj) >= 2 and traj[-2] == 'A' else 'N'
        trajectories[f'MC Run {i} ({len(traj)} passes, {conv})'] = traj

def draw_tree(ax, winners, title):
    n = len(winners)
    y = [0]
    for w in winners:
        if w == 'A': y.append(y[-1])
        elif w == 'AB': y.append(y[-1] + 0.5)
        elif w == 'B': y.append(y[-1] + 1)

    for i in range(n):
        base_y = y[i]
        winner = winners[i]
        dest = {'A': base_y, 'AB': base_y + 0.5, 'B': base_y + 1}
        for option, d in dest.items():
            if option == winner: continue
            ax.plot([i, i+1], [base_y, d], color=colors[option], linewidth=0.8, linestyle=':', alpha=0.35, zorder=2)
            ax.plot(i+1, d, 'o', color=colors[option], markersize=5, alpha=0.35, zorder=3,
                    markerfacecolor='white', markeredgewidth=1)

    for i in range(n):
        ax.plot([i, i+1], [y[i], y[i+1]], color=colors[winners[i]], linewidth=2, alpha=0.8, zorder=5)

    ax.plot(0, 0, 'o', color='#888', markersize=7, zorder=6)
    for i, w in enumerate(winners):
        ax.plot(i+1, y[i+1], 'o', color=colors[w], markersize=7, zorder=6)

    ax.set_xlim(-0.5, max(n, 5) + 0.5)
    ax.set_xticks(range(0, n+1, 5))
    ax.set_yticks([])
    ax.set_title(title, fontsize=9, fontweight='bold', pad=4)
    ax.grid(axis='x', alpha=0.1)

    a_wins = winners.count('A')
    b_wins = winners.count('B')
    ab_wins = winners.count('AB')
    ax.text(0.98, 0.85, f'A:{a_wins} B:{b_wins} AB:{ab_wins}',
            transform=ax.transAxes, ha='right', va='top', fontsize=7,
            family='monospace', bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8, edgecolor='#ddd'))


n_plots = len(trajectories)
fig, axes = plt.subplots(n_plots, 1, figsize=(14, n_plots * 1.6 + 1))
if n_plots == 1: axes = [axes]

fig.suptitle('Appendix: All Autoreason Trajectories', fontsize=14, fontweight='bold', y=0.99)

for ax, (title, traj) in zip(axes, trajectories.items()):
    draw_tree(ax, traj, title)

legend_patches = [
    mpatches.Patch(color=colors['A'], label='A (incumbent survives)'),
    mpatches.Patch(color=colors['B'], label='B (revision displaces)'),
    mpatches.Patch(color=colors['AB'], label='AB (synthesis displaces)'),
]
fig.legend(handles=legend_patches, loc='lower center', ncol=3, fontsize=9,
           framealpha=0.9, bbox_to_anchor=(0.5, 0.0))

plt.tight_layout()
plt.subplots_adjust(bottom=0.05, top=0.95, hspace=0.55)
plt.savefig(f'{out}/fig_appendix_trajectories.pdf', dpi=300, bbox_inches='tight', facecolor='white')
print("Saved fig_appendix_trajectories.png")
