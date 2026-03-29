#!/usr/bin/env python3
"""Single trajectory tree — Task 1 unconstrained (26 passes)."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

colors = {
    'A': '#4A90D9',
    'B': '#E85D75',
    'AB': '#7B68AE',
}

winners = ['B','AB','A','AB','AB','A','AB','AB','A','AB','AB','A','AB','A','A','AB','B','AB','B','B','B','AB','AB','A','A','AB']
n = len(winners)

# Calculate y positions: A=stay, AB=+1, B=+2
y = [0]
for w in winners:
    if w == 'A':
        y.append(y[-1])
    elif w == 'AB':
        y.append(y[-1] + 0.5)
    elif w == 'B':
        y.append(y[-1] + 1)

fig, ax = plt.subplots(figsize=(16, 10))

# Draw unchosen branches at each pass
for i in range(n):
    base_y = y[i]
    winner = winners[i]
    
    # The 3 possible destinations from this point
    dest_a = base_y       # A = no change
    dest_ab = base_y + 0.5  # AB = +0.5
    dest_b = base_y + 1   # B = +1
    
    destinations = {'A': dest_a, 'AB': dest_ab, 'B': dest_b}
    
    for option, dest in destinations.items():
        if option == winner:
            continue
        # Unchosen branch: dashed line + hollow circle
        ax.plot([i, i+1], [base_y, dest], color=colors[option], 
                linewidth=1, linestyle=':', alpha=0.4, zorder=2)
        ax.plot(i+1, dest, 'o', color=colors[option], markersize=8, 
                alpha=0.4, zorder=3, markerfacecolor='white', markeredgewidth=1.5)
        ax.text(i+1, dest, option.replace('AB', 'AB'), ha='center', va='center',
                fontsize=5, color=colors[option], alpha=0.5, fontweight='bold', zorder=4)

# Draw winning path
for i in range(n):
    c = colors[winners[i]]
    ax.plot([i, i+1], [y[i], y[i+1]], color=c, linewidth=2.5, alpha=0.8, zorder=5)

# Draw winner nodes
ax.plot(0, 0, 'o', color='#888888', markersize=12, zorder=6)
ax.text(0, 0, 'init', ha='center', va='center', fontsize=5, color='white', fontweight='bold', zorder=7)

for i, w in enumerate(winners):
    ax.plot(i+1, y[i+1], 'o', color=colors[w], markersize=12, zorder=6)
    ax.text(i+1, y[i+1], w, ha='center', va='center', 
            fontsize=6, color='white', fontweight='bold', zorder=7)

# Convergence markers
for p in [15, 25]:
    if p <= n:
        ax.axvline(x=p, color='#4A90D9', linewidth=1, linestyle='--', alpha=0.3, zorder=1)

ax.annotate('★ 2/2', xy=(15, y[15]), xytext=(15, y[15]-2),
            fontsize=9, ha='center', color='#4A90D9', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='#4A90D9', lw=1.2, alpha=0.6))
ax.annotate('★ 2/2', xy=(25, y[25]), xytext=(25, y[25]-2),
            fontsize=9, ha='center', color='#4A90D9', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='#4A90D9', lw=1.2, alpha=0.6))

# Axis
ax.set_xlim(-0.5, n + 0.5)
ax.set_xticks(range(0, n+1))
ax.set_xlabel('Pass', fontsize=12)
ax.set_ylabel('Cumulative drift from initial version', fontsize=12)
ax.set_yticks(np.arange(0, max(y)+1, 2))
ax.grid(axis='both', alpha=0.1)

ax.set_title('Autoreason Trajectory — Task 1: GTM Strategy (26 passes)\nVertical position = cumulative distance from initial version', 
             fontsize=13, fontweight='bold')

# Legend
legend_patches = [
    mpatches.Patch(color=colors['A'], label='A wins — incumbent survives (no drift)'),
    mpatches.Patch(color=colors['B'], label='B wins — revision displaces (+1 drift)'),
    mpatches.Patch(color=colors['AB'], label='AB wins — synthesis displaces (+0.5 drift)'),
]
ax.legend(handles=legend_patches, loc='upper left', fontsize=10, framealpha=0.9)

# Stats box
a_wins = winners.count('A')
b_wins = winners.count('B')
ab_wins = winners.count('AB')
stats = f'A: {a_wins} wins ({a_wins/n*100:.0f}%)\nB: {b_wins} wins ({b_wins/n*100:.0f}%)\nAB: {ab_wins} wins ({ab_wins/n*100:.0f}%)'
ax.text(0.98, 0.05, stats, transform=ax.transAxes, ha='right', va='bottom',
        fontsize=10, family='monospace',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.9, edgecolor='#ccc'))

plt.tight_layout()
plt.savefig('/root/autoreason-experiment/experiments/v2/trajectory_tree_task1.png', 
            dpi=150, bbox_inches='tight', facecolor='white')
print("Saved trajectory_tree_task1.png")
