#!/usr/bin/env python3
"""Generate remedy experiment figure as vector PDF."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

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
})

out = '/root/autoreason-experiment/paper'

# ── Data ────────────────────────────────────────────────────────────
# Trajectories from logs
trajectories = {
    'Baseline\n(no fix)': {
        'winners': ['AB','AB','AB','AB','AB','B','AB','AB','AB','AB','B','AB','AB','B','B','AB','B','AB','AB','AB',
                     'B','AB','AB','A','AB','AB','A','AB','A','B','B','AB','AB','AB','AB','A','AB','AB','AB','AB',
                     'AB','AB','AB','AB','B','B','A','AB','AB','A'],
        'converged': None,
        'color': '#999999',
    },
    'Margin': {
        'winners': ['AB','AB','AB','B','AB','B','AB','AB','B','AB','A','AB','B','A','A'],
        'converged': 15,
        'color': '#4A90D9',
    },
    'Scope-aware': {
        'winners': ['AB','AB','AB','AB','AB','AB','AB','AB','AB','AB','AB','AB','AB','AB','AB','AB','AB','AB','AB',
                     'AB','A','AB','B','AB','AB','AB','AB','AB','AB','AB','AB','AB','AB','A','AB'],
        'converged': None,
        'color': '#E8A838',
    },
    'Plateau': {
        'winners': ['AB','AB','AB','AB','B','AB','AB','AB','AB','B','B','AB','B','AB','B','AB','B','B','B','AB',
                     'A','AB','B','AB','B','AB','AB','AB','AB','AB','AB','AB','AB','AB','AB'],
        'converged': None,
        'color': '#E85D75',
    },
    'Combined': {
        'winners': ['B','AB','AB','AB','AB','B','AB','AB','AB','AB','AB','AB','A','AB','AB','A','A'],
        'converged': 17,
        'color': '#7B68AE',
    },
}

# ── Figure: A's cumulative win rate over passes ─────────────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4), gridspec_kw={'width_ratios': [2, 1]})

# Left: A's score trajectory
for name, data in trajectories.items():
    winners = data['winners']
    passes = list(range(1, len(winners) + 1))
    # Rolling A win fraction (cumulative)
    a_cumulative = [sum(1 for w in winners[:i+1] if w == 'A') / (i+1) for i in range(len(winners))]
    style = '-' if data['converged'] else '--'
    lw = 2.5 if data['converged'] else 1.5
    alpha = 1.0 if data['converged'] else 0.6
    ax1.plot(passes, a_cumulative, color=data['color'], linewidth=lw, linestyle=style,
             alpha=alpha, label=name.replace('\n', ' '))
    if data['converged']:
        ax1.axvline(x=data['converged'], color=data['color'], linewidth=0.8, linestyle=':', alpha=0.5)
        ax1.plot(data['converged'], a_cumulative[data['converged']-1], 'o',
                 color=data['color'], markersize=8, zorder=10)

ax1.set_xlabel('Pass')
ax1.set_ylabel('Cumulative A win rate')
ax1.set_xlim(0, 52)
ax1.set_ylim(0, 0.35)
ax1.grid(axis='y', alpha=0.15)
ax1.legend(loc='upper right', fontsize=9, framealpha=0.9)
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)

# Right: passes to converge (bar chart)
remedies = ['Margin', 'Combined', 'Scope-\naware', 'Plateau', 'Baseline\n(no fix)']
passes_to_conv = [15, 17, 35, 35, 50]
bar_colors = ['#4A90D9', '#7B68AE', '#E8A838', '#E85D75', '#999999']
converged = [True, True, False, False, False]

bars = ax2.barh(remedies, passes_to_conv, color=bar_colors, alpha=0.88, height=0.55)

for bar, p, conv in zip(bars, passes_to_conv, converged):
    label = str(p) if conv else f'{p}*'
    ax2.text(p + 0.8, bar.get_y() + bar.get_height()/2, label,
             ha='left', va='center', fontsize=10, fontweight='bold')

ax2.set_xlabel('Passes')
ax2.set_xlim(0, 58)
ax2.grid(axis='x', alpha=0.15)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)
ax2.text(0.95, 0.02, '* did not converge', transform=ax2.transAxes,
         ha='right', va='bottom', fontsize=8, fontstyle='italic', color='#888888')

plt.tight_layout()
plt.savefig(f'{out}/fig_remedies.pdf', dpi=300, bbox_inches='tight', facecolor='white')
print("Saved fig_remedies.pdf")
