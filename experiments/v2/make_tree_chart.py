#!/usr/bin/env python3
"""Horizontal tree trajectory visualization."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import json
from pathlib import Path

colors = {
    'A': '#4A90D9',   # blue - incumbent survived
    'B': '#E85D75',   # red - adversarial revision won
    'AB': '#7B68AE',  # purple - synthesis won
    'init': '#888888', # gray - starting point
}

def draw_trajectory_tree(ax, winners, title, max_passes=None):
    """
    Draw horizontal tree where:
    - x axis = pass number
    - y position shifts: stays if A wins, +1 if AB wins, +2 if B wins
    - color of each node = what the current A is derived from
    - at each level, show 3 branches (A, B, AB) with winner highlighted
    """
    if max_passes:
        winners = winners[:max_passes]
    
    n = len(winners)
    
    # Calculate y positions based on cumulative drift
    y_positions = [0]
    for w in winners:
        if w == 'A':
            y_positions.append(y_positions[-1])  # no drift
        elif w == 'AB':
            y_positions.append(y_positions[-1] + 1)  # moderate drift
        elif w == 'B':
            y_positions.append(y_positions[-1] + 2)  # maximum drift
    
    # Normalize y positions to fit in plot
    max_y = max(y_positions) if y_positions else 1
    if max_y > 0:
        y_positions = [y / max_y for y in y_positions]
    
    # Draw the main trajectory line
    passes = list(range(len(y_positions)))
    
    # Draw branch options at each pass (faded)
    for i in range(1, len(winners) + 1):
        base_y = y_positions[i-1]
        # Show the 3 options as small dots
        offsets = {'A': 0, 'AB': 0.03, 'B': 0.06}
        for option, offset in offsets.items():
            opt_y = base_y + (offset / (max_y if max_y > 0 else 1)) if max_y > 0 else base_y + offset
            if option == winners[i-1]:
                # Winner: big filled dot
                ax.plot(i, y_positions[i], 'o', color=colors[option], markersize=10, zorder=5)
            else:
                # Non-winner: small faded dot
                dot_y = base_y + offset * 3
                ax.plot(i, dot_y, 'o', color=colors[option], markersize=4, alpha=0.2, zorder=3)
    
    # Draw connecting lines between winners
    for i in range(len(y_positions) - 1):
        c = colors[winners[i]] if i < len(winners) else colors['init']
        ax.plot([i, i+1], [y_positions[i], y_positions[i+1]], 
                color=c, linewidth=2, alpha=0.7, zorder=4)
    
    # Starting dot
    ax.plot(0, 0, 'o', color=colors['init'], markersize=10, zorder=5)
    
    # Winner labels inside dots
    ax.text(0, 0, '0', ha='center', va='center', fontsize=6, color='white', fontweight='bold', zorder=6)
    for i, w in enumerate(winners):
        ax.text(i+1, y_positions[i+1], w.replace('AB','S'), ha='center', va='center', 
                fontsize=5, color='white', fontweight='bold', zorder=6)
    
    ax.set_xlim(-0.5, n + 0.5)
    ax.set_xticks(range(0, n+1, 5))
    ax.set_yticks([])
    ax.set_xlabel('Pass', fontsize=9)
    ax.set_title(title, fontsize=10, fontweight='bold', pad=8)
    ax.grid(axis='x', alpha=0.15)
    
    # Add drift annotation
    total_drift = y_positions[-1]
    a_wins = winners.count('A')
    b_wins = winners.count('B')
    ab_wins = winners.count('AB')
    ax.text(0.98, 0.95, f'A:{a_wins}  B:{b_wins}  AB:{ab_wins}', 
            transform=ax.transAxes, ha='right', va='top', fontsize=7, 
            color='#666', family='monospace',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))


# ── Load all trajectories ──────────────────────────────────────────────

root = Path(__file__).parent

trajectories = {}

# Task 1 original (26 passes)
trajectories['Task 1: GTM Strategy\n(unconstrained, 26 passes)'] = \
    ['B','AB','A','AB','AB','A','AB','AB','A','AB','AB','A','AB','A','A','AB','B','AB','B','B','B','AB','AB','A','A','AB']

# Task 1 constrained (25 passes)
trajectories['Task 1: GTM Strategy\n(constrained, 25 passes)'] = \
    ['B','B','AB','A','B','B','B','A','B','A','B','AB','B','AB','AB','B','B','B','B','B','B','AB','B','B','B']

# Monte Carlo runs
mc_dir = root / "results_monte_carlo" / "task_01"
for i in range(1, 6):
    hist_file = mc_dir / f"run_{i:02d}" / "history.json"
    if hist_file.exists():
        history = json.loads(hist_file.read_text())
        traj = [h['winner'] for h in history]
        trajectories[f'MC Run {i} ({len(traj)} passes)'] = traj

# Tasks 2-5
task_names = {
    2: 'Notification System',
    3: 'Remote Work Policy',
    4: 'Code Review Positioning',
    5: 'Incident Response',
}
for t in range(2, 6):
    hist_file = root / "results_multi_task" / f"task_{t:02d}" / "autoreason" / "history.json"
    if hist_file.exists():
        history = json.loads(hist_file.read_text())
        traj = [h['winner'] for h in history]
        trajectories[f'Task {t}: {task_names[t]}\n({len(traj)} passes)'] = traj

# Paper run
paper_hist = root.parent.parent / "paper" / "autoreason_run" / "history.json"
if paper_hist.exists():
    history = json.loads(paper_hist.read_text())
    traj = [h['winner'] for h in history]
    trajectories[f'Paper (Opus, {len(traj)} passes)'] = traj


# ── Draw ──────────────────────────────────────────────────────────────

n_plots = len(trajectories)
fig, axes = plt.subplots(n_plots, 1, figsize=(14, n_plots * 1.4 + 1.5))
if n_plots == 1:
    axes = [axes]

fig.suptitle('Autoreason Trajectories — All Experiments', fontsize=14, fontweight='bold', y=0.98)

for ax, (title, traj) in zip(axes, trajectories.items()):
    draw_trajectory_tree(ax, traj, title)

# Legend at bottom
legend_patches = [
    mpatches.Patch(color=colors['A'], label='A wins (incumbent survives)'),
    mpatches.Patch(color=colors['B'], label='B wins (revision displaces)'),
    mpatches.Patch(color=colors['AB'], label='AB wins (synthesis displaces)'),
    mpatches.Patch(color=colors['init'], label='Initial generation'),
]
fig.legend(handles=legend_patches, loc='lower center', ncol=4, fontsize=9, 
           framealpha=0.9, bbox_to_anchor=(0.5, 0.0))

plt.tight_layout()
plt.subplots_adjust(bottom=0.06, top=0.94, hspace=0.6)
plt.savefig(root / 'trajectory_trees.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved trajectory_trees.png")
