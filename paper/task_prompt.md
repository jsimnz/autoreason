Write a 2-page research paper (two-column, ~3000 words) titled "Autoreason: Autoresearch for Subjective Domains" for Nous Research.

The paper introduces autoreason, a method for iterative LLM refinement that constructs a subjective fitness function through independent blind evaluation. It extends Karpathy's autoresearch paradigm to domains where no objective metric exists.

Required sections:
1. Abstract (150 words max)
2. Introduction — the problem: LLMs exhibit sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse when iterating on subjective work. Prompting strategies don't fix this (cite SlopCodeBench showing this for code too).
3. Method — the A/B/AB loop with fresh isolated agents per role, blind judge panel with ranked choice and Borda count, conservative tiebreak, convergence at 2 consecutive incumbent wins. Explain what A, B, and AB represent and why each design choice exists.
4. Experiments — Task: go-to-market strategy for an open-source K8s CLI tool. v2 run over 26 passes showing convergence trajectory, bloat/prune oscillation, and quality plateau. 5-way baseline comparison (autoreason vs conservative, improve_this, harsh_critic, critique_and_revise) with 7-judge blind panel. Pass 15 vs pass 25 convergence comparison.
5. Results — autoreason: 35/35 Borda, 7/7 first place unanimous. Conservative beat all iterative baselines. Critique-and-revise came last. Pass 15 beat pass 25 6-1. Qualitative comparison showing initial generic playbook vs converged output with real validation data.
6. Related work — autoresearch, SlopCodeBench (Orlanski et al. 2026), ACE context collapse (Zhang et al. ICLR 2026), LLM Council.
7. Discussion — bloat/prune oscillation as signal of underdetermined tasks, convergence threshold sensitivity, judges need baseline to detect drift, potential for objective domains where metrics are insufficient.
8. Conclusion

Key facts from actual experiments (use these exact numbers):
- All experiments used claude-sonnet-4-20250514 (temp=0.8 author, temp=0.3 judge)
- v2 architecture: fresh isolated agents per role per pass, 3-judge panel with Borda count, conservative tiebreak, convergence at 2 consecutive A wins
- v2 task 01 ran 26 passes before being stopped (never hit 3-consecutive threshold, but hit 2-consecutive twice at passes 14-15 and 24-25)
- 5-way baseline comparison (7-judge blind panel): autoreason 35/35 Borda 7/7 first place, conservative 21, improve_this 18, harsh_critic 18, critique_and_revise 13
- Word counts: initial 847, autoreason converged at 1800, conservative 862, improve_this 2116, harsh_critic 1961, critique_and_revise 2507
- Pass 15 vs pass 25 (7-judge panel): pass 15 won 6-1
- Autoreason vs adversarial with baseline shown: 7-0 unanimous. Without baseline: 3-2.
- v1 experiments (~1800 LLM calls) found positional bias, single judge noise, shared context contamination
- Qualitative: initial output had generic targets, $49/user pricing, $100K MRR fantasy. Converged output had quantified pain ($15K/incident x 6/yr), team pricing ($1499/mo), customer validation (50+ interviews, 75% pilot success), unit economics (CAC $2K, LTV $54K)

Constraints:
- Write for a technical ML audience familiar with LLMs but not necessarily this specific problem
- Be concrete and specific, not hand-wavy. Use the actual numbers from experiments.
- Do NOT fabricate experiments, ablation studies, confidence intervals, or any data not listed above
- Do not pad with filler. Every sentence should earn its place.
- Figures will be added separately — reference them by number but don't describe what they look like
- The tone should be direct and confident, not hedging
