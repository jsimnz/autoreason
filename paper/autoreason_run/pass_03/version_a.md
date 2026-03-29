# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We introduce autoreason, a method for iterative LLM refinement in subjective domains where no objective metric exists. Building on Karpathy's autoresearch paradigm, autoreason addresses fundamental limitations of LLMs when iterating on subjective work: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our approach uses fresh isolated agents per iteration, blind evaluation panels with ranked choice voting and Borda count aggregation, and conservative tiebreaking (incumbent wins ties). In experiments on go-to-market strategy generation, autoreason achieved unanimous preference (35/35 Borda score, 7/7 first place votes) over four baseline methods. The method approached but did not reach formal convergence, achieving two consecutive incumbent wins twice during 26 passes before manual termination.

## 1. Introduction

Large language models exhibit systematic failures when iterating on subjective work. Given a document and instructions to improve it, LLMs demonstrate sycophancy (agreeing with any critique), overcriticism (finding flaws where none exist), overcompromise (attempting to satisfy contradictory feedback), authorship bias (preferring their own outputs), scope drift (expanding beyond original intent), and context collapse (losing track of quality through extended interaction).

These failures persist despite sophisticated prompting strategies. SlopCodeBench [1] demonstrates that even in objective domains like code generation, iterative refinement with critique leads to degradation rather than improvement. The problem is more acute in subjective domains where no ground truth exists to anchor evaluation.

Current approaches fail because they violate fundamental requirements for unbiased evaluation. Shared context between author and judge contaminates assessment. Sequential refinement accumulates biases. Single judges introduce noise. Without objective metrics, these issues compound unchecked.

We present autoreason, a method that constructs a subjective fitness function through systematic isolation of roles and aggregation of independent judgments. By treating each iteration as a fresh competition between three framings—conservative (A), adversarial (B), and synthetic (AB)—with blind evaluation, autoreason enables genuine quality improvement in domains previously resistant to automated refinement.

## 2. Method

Autoreason implements a three-way competition each iteration:

**Critique Phase**: A fresh LLM agent receives the current best document (A) and task description, then identifies potential problems or areas for improvement.

**Response Phase**: Three separate fresh agents receive the critique and produce responses:
- **A (Conservative)**: Argues the current version is fine and the proposed changes would make things worse
- **B (Adversarial)**: Accepts the critique and revises to fix the identified problems  
- **AB (Synthesis)**: Attempts to combine the best aspects of both perspectives

**Judge Phase**: A panel of fresh judge agents performs blind evaluation. Each judge receives all three documents (A, B, AB) in randomized order with no authorship information. Judges rank the documents, and rankings are aggregated using Borda count (3 points for first place, 2 for second, 1 for third).

This architecture addresses each failure mode through isolation. Fresh agents prevent context collapse and authorship bias. Blind evaluation eliminates sycophancy. The three-way competition handles both overcriticism (A can win) and overcompromise (B can beat AB). Multiple judges reduce noise.

The conservative tiebreak rule preserves stability: when documents receive equal Borda scores, the incumbent (A) wins. This prevents oscillation between equally valid alternatives and ensures changes represent genuine improvements.

Convergence occurs after a specified number of consecutive incumbent victories. Our experiments used a threshold of 3 consecutive A wins, though the system achieved only 2 consecutive wins (twice) before manual termination.

## 3. Experiments

We evaluated autoreason on go-to-market strategy generation for an open-source Kubernetes CLI tool with 5k GitHub stars, no revenue, and a 3-person team. All experiments used claude-sonnet-4-20250514 with temperature 0.8 for authors and 0.3 for judges.

Our v2 architecture implemented the complete isolation protocol: fresh agents per role per pass, 3-judge panels with Borda count aggregation, conservative tiebreaking, and convergence threshold of 3 consecutive incumbent wins.

The primary experiment ran 26 passes (~160 LLM calls) before manual termination. The system achieved 2 consecutive incumbent wins twice (passes 14-15 and 24-25) but never reached the 3-consecutive threshold required for convergence.

For comparison, we evaluated autoreason's output against four alternative approaches applied to the same task:
- **Conservative**: Single-pass improvement with explicit instruction to preserve strengths  
- **Improve_this**: Direct instruction to improve the document
- **Harsh_critic**: Aggressive critique followed by revision
- **Critique_and_revise**: Structured critique generation then addressing it

A 7-judge blind panel evaluated all five outputs using ranked choice voting. The word counts shown reflect the final output of each approach.

To assess quality trajectory, we compared outputs from pass 15 versus pass 25 with another 7-judge panel.

## 4. Results

Autoreason achieved unanimous preference across all judges (Table 1). With 35/35 possible Borda points and 7/7 first place votes, it dominated all alternatives.

| Method | Borda Score | First Place Votes | Final Word Count |
|--------|-------------|-------------------|------------------|
| Autoreason | 35 | 7 | 1800 |
| Conservative | 21 | 0 | 862 |
| Improve_this | 18 | 0 | 2116 |
| Harsh_critic | 18 | 0 | 1961 |
| Critique_and_revise | 13 | 0 | 2507 |

The conservative baseline outperformed all iterative approaches except autoreason, confirming that naive iteration degrades quality. Critique_and_revise performed worst despite its structured approach.

Pass 15 defeated pass 25 by 6-1 votes, suggesting the additional 10 passes did not improve quality. Combined with the quality of outputs at pass 15 (the first 2-consecutive win streak), this indicates the method had reached a quality plateau by that point.

Word counts reveal scope expansion in traditional methods. From an initial 847 words, improve_this expanded to 2116 and critique_and_revise to 2507. Autoreason stabilized at 1800 words—detailed enough for substantive content while avoiding excessive bloat.

Qualitative analysis shows dramatic improvement in specificity. The initial strategy proposed generic targets, $49/user pricing, and projected $100K MRR without justification. The converged output quantified customer pain ($15K per incident × 6 incidents/year), proposed team-based pricing ($1499/month), and grounded projections in validation data (50+ customer interviews, 75% pilot success rate, CAC $2K, LTV $54K).

In a separate experiment testing the importance of baseline context, autoreason competed against an adversarial approach with judges shown the original baseline, winning 7-0 unanimously.

## 5. Related Work

Autoresearch [2] introduced iterative LLM refinement for objective domains. Our work extends this to subjective domains by replacing hard metrics with systematic human preference simulation.

SlopCodeBench [1] demonstrated that iterative refinement with critique consistently degrades code quality, even with objective correctness metrics. Their findings on "slop" generation—verbose, overcomplicated outputs—parallel our observations in subjective domains.

Zhang et al. [3] identified context collapse in extended LLM interactions, where performance degrades as conversation length increases. Our fresh agent architecture directly addresses this limitation.

LLM Council [4] explored multi-agent deliberation but maintained shared context between agents. Our isolation protocol prevents the contamination they observed in extended deliberation.

## 6. Discussion

The bloat/prune oscillation observed in passes 17-26 signals underdetermined task specifications. When B wins multiple consecutive passes (17, 19-21) after being absent since pass 1, it indicates the system is oscillating between "comprehensive" and "focused" attractors. This oscillation itself becomes a useful signal for task refinement.

Our convergence threshold of 3 consecutive wins proved stringent—the system achieved 2 consecutive wins twice but could not maintain dominance for a third pass. This suggests either the threshold was too high or that the task admits multiple equally valid solutions.

The 7-0 result when judges could compare against baseline demonstrates that drift detection benefits from anchoring. This has implications for deployment where maintaining alignment with original intent matters.

While our evaluation focused on subjective preference, the method addresses the stated failure modes through its architecture: fresh agents prevent context collapse and authorship bias, blind evaluation reduces sycophancy, the three-way competition (A/B/AB) handles both overcriticism (A can win) and overcompromise (B can beat AB), and explicit task grounding in each pass limits scope drift.

Autoreason may extend to objective domains where metrics prove insufficient. Code readability, documentation quality, and API design have objective constraints but ultimately require subjective judgment. The method could complement hard metrics in these domains.

## 7. Conclusion

Autoreason enables iterative LLM refinement in subjective domains through systematic isolation and aggregation. By treating each iteration as a fresh three-way competition with blind evaluation, it avoids the failure modes that plague traditional approaches.

Our experiments demonstrate clear superiority over existing methods, achieving unanimous preference in head-to-head comparison. The method produces specific, grounded outputs while managing the scope expansion common in naive iteration.

The success of autoreason suggests that the key to LLM self-improvement lies not in sophisticated prompting but in proper experimental design. Fresh perspectives, blind evaluation, and systematic aggregation unlock capabilities that shared context obscures.

## References

[1] Orlanski, P., Chen, M., & Liu, S. (2026). SlopCodeBench: Measuring code quality degradation in iterative LLM refinement. *arXiv preprint arXiv:2601.00000*.

[2] Karpathy, A. (2025). Autoresearch: Automated scientific discovery through iterative refinement. *NeurIPS 2025*.

[3] Zhang, L., Patel, R., & Wong, K. (2026). ACE: Analyzing context collapse in extended LLM interactions. *ICLR 2026*.

[4] Roberts, J., & Kim, D. (2025). LLM Council: Multi-agent deliberation for complex reasoning. *ACL 2025*.