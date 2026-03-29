#!/usr/bin/env python3
"""Generate all charts for the updated paper."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

out = '/root/autoreason-experiment/paper'

colors = {'A': '#4A90D9', 'B': '#E85D75', 'AB': '#7B68AE'}

# =========================================================================
# Fig 1: Multi-task 5-way comparison
# =========================================================================

tasks = ['Task 1\nGTM Strategy', 'Task 2\nNotifications', 'Task 3\nRemote Policy', 'Task 4\nCode Review', 'Task 5\nIncident Resp.']
methods = ['autoreason', 'critique_and_revise', 'harsh_critic', 'conservative', 'improve_this']
method_labels = ['Autoreason', 'Critique & Revise', 'Harsh Critic', 'Conservative', 'Improve This']
method_colors = ['#4A90D9', '#7B68AE', '#E85D75', '#7B9E6B', '#E8A838']

scores = {
    'autoreason':        [35, 19, 29, 25, 31],
    'critique_and_revise': [13, 22, 26, 32, 19],
    'harsh_critic':      [18, 19, 27, 20, 26],
    'conservative':      [21, 19, 15, 18, 15],
    'improve_this':      [18, 11,  8, 10, 14],
}

fig, ax = plt.subplots(figsize=(12, 6))
x = np.arange(len(tasks))
width = 0.15
for i, (method, label) in enumerate(zip(methods, method_labels)):
    offset = (i - 2) * width
    bars = ax.bar(x + offset, scores[method], width, label=label, color=method_colors[i], alpha=0.85)
    for bar, score in zip(bars, scores[method]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_y() + bar.get_height() + 0.3,
                str(score), ha='center', va='bottom', fontsize=7, fontweight='bold')

ax.set_ylabel('Borda Score (max 35)', fontsize=11)
ax.set_title('5-Way Blind Panel: Autoreason vs Baselines Across 5 Tasks', fontsize=13, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(tasks, fontsize=9)
ax.set_ylim(0, 40)
ax.legend(fontsize=9, loc='upper right')
ax.grid(axis='y', alpha=0.15)

plt.tight_layout()
plt.savefig(f'{out}/fig_multi_task.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved fig_multi_task.png")

# =========================================================================
# Fig 2: Monte Carlo convergence
# =========================================================================

mc_passes = [30, 6, 14, 17, 8]
mc_words = [1654, 1453, 1451, 1618, 1660]
mc_converged = [False, True, True, True, True]
mc_colors = ['#E85D75' if not c else '#4A90D9' for c in mc_converged]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

# Passes to converge
bars = ax1.bar(range(1, 6), mc_passes, color=mc_colors, alpha=0.85, width=0.6)
for bar, p, c in zip(bars, mc_passes, mc_converged):
    label = str(p) if c else f'{p}*'
    ax1.text(bar.get_x() + bar.get_width()/2, p + 0.5, label,
             ha='center', fontsize=11, fontweight='bold')
ax1.set_xlabel('Run', fontsize=11)
ax1.set_ylabel('Passes', fontsize=11)
ax1.set_title('Passes to Convergence', fontsize=12, fontweight='bold')
ax1.set_ylim(0, 35)
ax1.set_xticks(range(1, 6))
ax1.text(0.95, 0.95, '* = did not converge\n   (hit 30-pass cap)', transform=ax1.transAxes,
         ha='right', va='top', fontsize=8, color='#666', style='italic')

# Final word counts
ax2.bar(range(1, 6), mc_words, color='#4A90D9', alpha=0.85, width=0.6)
for i, w in enumerate(mc_words):
    ax2.text(i+1, w + 20, str(w), ha='center', fontsize=10, fontweight='bold')
ax2.set_xlabel('Run', fontsize=11)
ax2.set_ylabel('Words', fontsize=11)
ax2.set_title('Final Word Count', fontsize=12, fontweight='bold')
ax2.set_ylim(0, 1900)
ax2.set_xticks(range(1, 6))
ax2.axhline(y=np.mean(mc_words), color='#333', linewidth=1, linestyle='--', alpha=0.4)
ax2.text(5.3, np.mean(mc_words), f'mean: {int(np.mean(mc_words))}', fontsize=8, color='#666')

fig.suptitle('Monte Carlo: 5 Independent Runs of Task 1', fontsize=13, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig(f'{out}/fig_monte_carlo.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved fig_monte_carlo.png")

# =========================================================================
# Fig 3: Trajectory tree (Task 1, 26 passes)
# =========================================================================

winners = ['B','AB','A','AB','AB','A','AB','AB','A','AB','AB','A','AB','A','A','AB','B','AB','B','B','B','AB','AB','A','A','AB']
n = len(winners)

y = [0]
for w in winners:
    if w == 'A': y.append(y[-1])
    elif w == 'AB': y.append(y[-1] + 0.5)
    elif w == 'B': y.append(y[-1] + 1)

fig, ax = plt.subplots(figsize=(16, 8))

for i in range(n):
    base_y = y[i]
    winner = winners[i]
    dest = {'A': base_y, 'AB': base_y + 0.5, 'B': base_y + 1}
    for option, d in dest.items():
        if option == winner: continue
        ax.plot([i, i+1], [base_y, d], color=colors[option], linewidth=1, linestyle=':', alpha=0.4, zorder=2)
        ax.plot(i+1, d, 'o', color=colors[option], markersize=8, alpha=0.4, zorder=3,
                markerfacecolor='white', markeredgewidth=1.5)
        ax.text(i+1, d, option, ha='center', va='center', fontsize=5, color=colors[option],
                alpha=0.5, fontweight='bold', zorder=4)

for i in range(n):
    ax.plot([i, i+1], [y[i], y[i+1]], color=colors[winners[i]], linewidth=2.5, alpha=0.8, zorder=5)

ax.plot(0, 0, 'o', color='#888', markersize=12, zorder=6)
ax.text(0, 0, 'init', ha='center', va='center', fontsize=5, color='white', fontweight='bold', zorder=7)
for i, w in enumerate(winners):
    ax.plot(i+1, y[i+1], 'o', color=colors[w], markersize=12, zorder=6)
    ax.text(i+1, y[i+1], w, ha='center', va='center', fontsize=6, color='white', fontweight='bold', zorder=7)

for p in [15, 25]:
    ax.axvline(x=p, color='#4A90D9', linewidth=1, linestyle='--', alpha=0.3, zorder=1)
ax.annotate('★ 2/2', xy=(15, y[15]), xytext=(15, y[15]-1.5),
            fontsize=9, ha='center', color='#4A90D9', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='#4A90D9', lw=1.2, alpha=0.6))

ax.set_xlim(-0.5, n+0.5)
ax.set_xticks(range(0, n+1))
ax.set_xlabel('Pass', fontsize=12)
ax.set_ylabel('Cumulative drift from initial version', fontsize=12)
ax.grid(axis='both', alpha=0.1)
ax.set_title('Autoreason Trajectory Tree — Task 1 (26 passes)', fontsize=13, fontweight='bold')

legend_patches = [
    mpatches.Patch(color=colors['A'], label='A wins — incumbent survives (no drift)'),
    mpatches.Patch(color=colors['B'], label='B wins — revision displaces (+1 drift)'),
    mpatches.Patch(color=colors['AB'], label='AB wins — synthesis displaces (+0.5 drift)'),
]
ax.legend(handles=legend_patches, loc='upper left', fontsize=10, framealpha=0.9)

plt.tight_layout()
plt.savefig(f'{out}/fig_trajectory_tree.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved fig_trajectory_tree.png")

# =========================================================================
# Fig 4: Convergence across all tasks
# =========================================================================

all_tasks = ['Task 1', 'Task 2', 'Task 3', 'Task 4', 'Task 5', 'Paper']
all_passes = [15, 12, 10, 15, 28, 9]  # pass where first 2-consecutive happened or convergence
all_words = [1800, 1252, 1279, 2377, 2280, 2097]

fig, ax = plt.subplots(figsize=(10, 5))
bar_colors = ['#4A90D9'] * len(all_tasks)
bars = ax.bar(all_tasks, all_passes, color=bar_colors, alpha=0.85, width=0.5)
for bar, p, w in zip(bars, all_passes, all_words):
    ax.text(bar.get_x() + bar.get_width()/2, p + 0.5, f'{p} passes\n{w} words',
            ha='center', fontsize=9, fontweight='bold')
ax.set_ylabel('Passes to converge', fontsize=11)
ax.set_title('Convergence Speed Across Tasks (threshold = 2 consecutive A wins)', fontsize=13, fontweight='bold')
ax.set_ylim(0, 35)
ax.grid(axis='y', alpha=0.15)
plt.tight_layout()
plt.savefig(f'{out}/fig_convergence_all.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved fig_convergence_all.png")
