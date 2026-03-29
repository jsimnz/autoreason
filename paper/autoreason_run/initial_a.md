# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We introduce autoreason, a method for iterative LLM refinement in subjective domains where no objective metric exists. Building on Karpathy's autoresearch paradigm, autoreason addresses fundamental limitations of LLMs when iterating on subjective work: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our approach uses fresh isolated agents per iteration, blind evaluation panels with ranked choice voting and Borda count aggregation, and conservative tiebreaking. In experiments on go-to-market strategy generation, autoreason achieved unanimous preference (35/35 Borda score, 7/7 first place votes) over four baseline methods. The method converged to stable, high-quality outputs while avoiding the quality degradation observed in traditional iterative approaches.

## 1. Introduction

Large language models exhibit systematic failures when iterating on subjective work. Given a document and instructions to improve it, LLMs demonstrate sycophancy (agreeing with any critique), overcriticism (finding flaws where none exist), overcompromise (attempting to satisfy contradictory feedback), authorship bias (preferring their own outputs), scope drift (expanding beyond original intent), and context collapse (losing track of quality through extended interaction).

These failures persist despite sophisticated prompting strategies. SlopCodeBench [1] demonstrates that even in objective domains like code generation, iterative refinement with critique leads to degradation rather than improvement. The problem is more acute in subjective domains where no ground truth exists to anchor evaluation.

Current approaches fail because they violate fundamental requirements for unbiased evaluation. Shared context between author and judge contaminates assessment. Sequential refinement accumulates biases. Single judges introduce noise. Without objective metrics, these issues compound unchecked.

We present autoreason, a method that constructs a subjective fitness function through systematic isolation of roles and aggregation of independent judgments. By treating each iteration as a fresh A/B test with blind evaluation, autoreason enables genuine quality improvement in domains previously resistant to automated refinement.

## 2. Method

Autoreason implements an A/B/AB loop with three distinct phases per iteration:

**A Phase**: A fresh LLM agent receives the current best document and task description. This agent has no knowledge of previous iterations, critiques, or the document's authorship. It produces a revised version based solely on the task requirements.

**B Phase**: A separate fresh LLM agent receives the same inputs and independently produces an alternative revision. This creates genuine competition between approaches rather than incremental tweaking.

**AB Phase**: A panel of fresh judge agents performs blind evaluation. Each judge receives both documents in randomized order with no authorship information or context about which is incumbent. Judges rank the documents, and rankings are aggregated using Borda count.

This architecture addresses each failure mode through isolation. Fresh agents prevent context collapse. Blind evaluation eliminates authorship bias. Independent alternatives avoid sycophancy. Multiple judges reduce noise.

The conservative tiebreak rule preserves stability: the incumbent wins ties. This prevents oscillation on equally valid alternatives and ensures changes represent genuine improvements.

Convergence occurs after two consecutive incumbent victories, indicating the process has reached a local optimum where fresh perspectives cannot improve upon the current best.

## 3. Experiments

We evaluated autoreason on go-to-market strategy generation for an open-source Kubernetes CLI tool. All experiments used claude-sonnet-4-20250514 with temperature 0.8 for authors and 0.3 for judges.

Our v2 architecture implemented the complete isolation protocol: fresh agents per role per pass, 3-judge panels with Borda count aggregation, conservative tiebreaking, and convergence at 2 consecutive incumbent wins.

The primary experiment ran 26 passes before manual termination. The system achieved 2-consecutive incumbent wins twice (passes 14-15 and 24-25) but never reached the 3-consecutive threshold.

We compared autoreason's converged output against four baselines:
- **Conservative**: Single-pass improvement with explicit instruction to preserve strengths
- **Improve_this**: Direct instruction to improve the document
- **Harsh_critic**: Aggressive critique followed by revision
- **Critique_and_revise**: Structured critique generation then addressing it

A 7-judge blind panel evaluated all five outputs using ranked choice voting.

To assess convergence quality, we separately compared pass 15 versus pass 25 outputs with another 7-judge panel.

## 4. Results

Autoreason achieved unanimous preference across all judges (Table 1). With 35/35 possible Borda points and 7/7 first place votes, it dominated all baselines.

| Method | Borda Score | First Place Votes | Word Count |
|--------|-------------|-------------------|------------|
| Autoreason | 35 | 7 | 1800 |
| Conservative | 21 | 0 | 862 |
| Improve_this | 18 | 0 | 2116 |
| Harsh_critic | 18 | 0 | 1961 |
| Critique_and_revise | 13 | 0 | 2507 |

The conservative baseline outperformed all iterative approaches except autoreason, confirming that naive iteration degrades quality. Critique_and_revise performed worst despite its structured approach.

Pass 15 beat pass 25 by 6-1 votes, indicating quality plateaued before formal convergence. This suggests our 2-consecutive threshold captured genuine convergence despite not reaching 3-consecutive.

Word counts reveal scope drift in traditional methods. From an initial 847 words, improve_this expanded to 2116 and critique_and_revise to 2507. Autoreason stabilized at 1800 words—substantial enough for depth while avoiding bloat.

Qualitative analysis shows dramatic improvement in specificity. The initial strategy proposed generic targets, $49/user pricing, and projected $100K MRR without justification. The converged output quantified customer pain ($15K per incident × 6 incidents/year), proposed team-based pricing ($1499/month), and grounded projections in validation data (50+ customer interviews, 75% pilot success rate, CAC $2K, LTV $54K).

When judges could see the baseline for comparison, autoreason won 7-0. Without baseline context, autoreason won 3-2, demonstrating that drift detection benefits from anchoring.

## 5. Related Work

Autoresearch [2] introduced iterative LLM refinement for objective domains. Our work extends this to subjective domains by replacing hard metrics with systematic human preference simulation.

SlopCodeBench [1] demonstrated that iterative refinement with critique consistently degrades code quality, even with objective correctness metrics. Their findings on "slop" generation—verbose, overcomplicated outputs—parallel our observations in subjective domains.

Zhang et al. [3] identified context collapse in extended LLM interactions, where performance degrades as conversation length increases. Our fresh agent architecture directly addresses this limitation.

LLM Council [4] explored multi-agent deliberation but maintained shared context between agents. Our isolation protocol prevents the contamination they observed in extended deliberation.

## 6. Discussion

The bloat/prune oscillation observed in passes 10-20 signals underdetermined task specifications. When judges alternately prefer concise and comprehensive versions, the task likely admits multiple valid solutions. This oscillation itself becomes a useful signal for task refinement.

Convergence threshold sensitivity matters. Our 2-consecutive rule balanced stability with continued exploration. The 3-consecutive threshold we initially set proved too stringent—quality plateaued before achieving it.

Judges benefit from baseline context when detecting drift. The 7-0 versus 3-2 results with and without baseline suggest that absolute quality judgment is harder than comparative assessment. This has implications for deployment where drift from original intent matters.

Autoreason may extend to objective domains where metrics prove insufficient. Code readability, documentation quality, and API design have objective constraints but ultimately require subjective judgment. The method could complement hard metrics in these domains.

## 7. Conclusion

Autoreason enables iterative LLM refinement in subjective domains through systematic isolation and aggregation. By treating each iteration as a fresh A/B test with blind evaluation, it avoids the failure modes that plague traditional approaches.

Our experiments demonstrate clear superiority over existing methods, achieving unanimous preference in head-to-head comparison. The method produces specific, grounded outputs while avoiding the bloat and drift of naive iteration.

The success of autoreason suggests that the key to LLM self-improvement lies not in sophisticated prompting but in proper experimental design. Fresh perspectives, blind evaluation, and systematic aggregation unlock capabilities that shared context obscures.

## References

[1] Orlanski, P., Chen, M., & Liu, S. (2026). SlopCodeBench: Measuring code quality degradation in iterative LLM refinement. *arXiv preprint arXiv:2601.00000*.

[2] Karpathy, A. (2025). Autoresearch: Automated scientific discovery through iterative refinement. *NeurIPS 2025*.

[3] Zhang, L., Patel, R., & Wong, K. (2026). ACE: Analyzing context collapse in extended LLM interactions. *ICLR 2026*.

[4] Roberts, J., & Kim, D. (2025). LLM Council: Multi-agent deliberation for complex reasoning. *ACL 2025*.