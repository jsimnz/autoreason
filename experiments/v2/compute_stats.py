#!/usr/bin/env python3
"""
Compute confidence intervals and statistical tests for all code experiments.
Critic items #3 and #9.
"""
import json, glob, os
import numpy as np
from pathlib import Path
from scipy import stats

def bootstrap_ci(data, n_boot=2000, ci=0.95):
    """Bootstrap confidence interval for a proportion."""
    data = np.array(data, dtype=float)
    n = len(data)
    boots = np.array([np.mean(np.random.choice(data, n, replace=True)) for _ in range(n_boot)])
    lo = np.percentile(boots, (1-ci)/2 * 100)
    hi = np.percentile(boots, (1+ci)/2 * 100)
    return np.mean(data), lo, hi

def mcnemar_test(a_results, b_results):
    """McNemar's test on paired binary outcomes."""
    a = np.array(a_results, dtype=bool)
    b = np.array(b_results, dtype=bool)
    # Discordant pairs
    a_only = np.sum(a & ~b)  # a passes, b fails
    b_only = np.sum(~a & b)  # b passes, a fails
    # McNemar's with continuity correction
    if a_only + b_only == 0:
        return 1.0, 0, 0
    chi2 = (abs(a_only - b_only) - 1)**2 / (a_only + b_only)
    p = 1 - stats.chi2.cdf(chi2, 1)
    return p, int(a_only), int(b_only)

def load_results(results_dir, strategy):
    """Load results for a strategy, return list of (problem_id, tier, pass_private)."""
    results = []
    for f in sorted(glob.glob(f"{results_dir}/*_{strategy}.json")):
        with open(f) as fh:
            d = json.load(fh)
        if 'error' in d:
            continue
        results.append({
            'pid': d['problem_id'],
            'tier': d.get('tier', '?'),
            'pass_pub': d.get('pass_public', False),
            'pass_priv': d.get('pass_private', False),
        })
    return results

def analyze_experiment(name, results_dir, strategies):
    print(f"\n{'='*70}")
    print(f"  {name}")
    print(f"{'='*70}")
    
    all_results = {}
    for s in strategies:
        all_results[s] = load_results(results_dir, s)
    
    # Per-strategy stats with CIs
    print(f"\n  Strategy             N    Private    95% CI         Public     95% CI")
    print(f"  {'─'*65}")
    for s in strategies:
        r = all_results[s]
        if not r:
            print(f"  {s:<20} 0    ---")
            continue
        priv = [x['pass_priv'] or False for x in r]
        pub = [x['pass_pub'] or False for x in r]
        priv_mean, priv_lo, priv_hi = bootstrap_ci(priv)
        pub_mean, pub_lo, pub_hi = bootstrap_ci(pub)
        print(f"  {s:<20} {len(r):<4} {priv_mean:.1%}     [{priv_lo:.1%}, {priv_hi:.1%}]    {pub_mean:.1%}     [{pub_lo:.1%}, {pub_hi:.1%}]")
    
    # Per-tier breakdown with CIs
    for tier in ['easy', 'medium', 'hard']:
        print(f"\n  {tier.upper()}")
        for s in strategies:
            r = [x for x in all_results[s] if x['tier'] == tier]
            if not r:
                continue
            priv = [x['pass_priv'] or False for x in r]
            priv_mean, priv_lo, priv_hi = bootstrap_ci(priv)
            print(f"    {s:<20} {len(r):<4} {priv_mean:.1%}  [{priv_lo:.1%}, {priv_hi:.1%}]")
    
    # Pairwise McNemar tests
    print(f"\n  Pairwise McNemar (private-test):")
    for i, s1 in enumerate(strategies):
        for s2 in strategies[i+1:]:
            # Align on shared problems
            r1 = {x['pid']: x for x in all_results[s1]}
            r2 = {x['pid']: x for x in all_results[s2]}
            shared = sorted(set(r1.keys()) & set(r2.keys()))
            if not shared:
                continue
            a = [r1[pid]['pass_priv'] or False for pid in shared]
            b = [r2[pid]['pass_priv'] or False for pid in shared]
            p, a_only, b_only = mcnemar_test(a, b)
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
            print(f"    {s1} vs {s2}: p={p:.4f}{sig}  ({s1}-only={a_only}, {s2}-only={b_only}, n={len(shared)})")

base = Path("/workspace/autoreason/experiments/v2")

analyze_experiment(
    "Sonnet 4.6 Code (150 problems)",
    base / "results_code_s46",
    ["s46_autoreason", "s46_critique", "s46_single"]
)

# Only run these if enough data
haiku_dir = base / "results_code_haiku"
haiku_count = len([f for f in glob.glob(str(haiku_dir / "*_haiku_single.json"))
                   if 'error' not in json.load(open(f))])
if haiku_count >= 100:
    analyze_experiment(
        f"Haiku 3.5 Code ({haiku_count} problems so far)",
        haiku_dir,
        ["haiku_autoreason", "haiku_critique", "haiku_single", "sonnet_single"]
    )
else:
    print(f"\nHaiku: only {haiku_count}/150 done, skipping stats")

bon_dir = base / "results_code_best_of_n"
bon_count = len([f for f in glob.glob(str(bon_dir / "*_haiku_best6.json"))
                 if 'error' not in json.load(open(f))])
if bon_count >= 100:
    analyze_experiment(
        f"Best-of-N ({bon_count} problems so far)",
        bon_dir,
        ["haiku_best6", "haiku_autoreason", "sonnet_single"]
    )
else:
    print(f"\nBest-of-N: only {bon_count}/150 done, skipping stats")
