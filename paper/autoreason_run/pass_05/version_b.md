I'll revise the paper to address each identified problem while maintaining the original voice and structure.

# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We introduce autoreason, a method for iterative LLM refinement in subjective domains where no objective metric exists. Building on the autoresearch paradigm of iterative refinement, autoreason addresses fundamental limitations of LLMs when iterating on subjective work: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our approach uses fresh isolated agents per iteration, blind evaluation panels with ranked choice voting and Borda count aggregation, and conservative tiebreaking (incumbent wins ties). In experiments on go-to-market strategy generation, autoreason achieved unanimous first-place preference (7/7 first place votes) over four baseline methods. The method achieved two consecutive incumbent wins twice during 26 passes before manual termination, but did not reach the convergence threshold of three consecutive wins.

**[Fix for Problem 9: Removed misleading "35/35 Borda score" from abstract, focusing on the more meaningful 7/7 first place votes]**

## 1. Introduction

Large language models exhibit systematic failures when iterating on subjective work. Given a document and instructions to improve it, LLMs demonstrate sycophancy (agreeing with any critique), overcriticism (finding flaws where none exist), overcompromise (attempting to satisfy contradictory feedback), authorship bias (preferring their own outputs), scope drift (expanding beyond original intent), and context collapse (losing track of quality through extended interaction).

These failures persist despite sophisticated prompting strategies. Recent work has shown that even in objective domains like code generation, iterative refinement with critique leads to degradation rather than improvement—a phenomenon termed "slop" generation where outputs become verbose and overcomplicated [1]. The problem is more acute in subjective domains where no ground truth exists to anchor evaluation.

Current approaches fail because they violate fundamental requirements for unbiased evaluation. Shared context between author and judge contaminates assessment. Sequential refinement accumulates biases. Single judges introduce noise. Without objective metrics, these issues compound unchecked.

We present autoreason, a method that constructs a subjective fitness function through systematic isolation of roles and aggregation of independent judgments. By treating each iteration as a fresh competition between three framings—conservative (A), adversarial (B), and synthetic (AB)—with blind evaluation, autoreason enables genuine quality improvement in domains previously resistant to automated refinement.

## 2. Method

Autoreason implements a three-way competition each iteration:

**Critique Phase**: A fresh LLM agent receives the current best document (A) and task description, then identifies potential problems or areas for improvement. Each critique agent is a new API call with no conversation history from previous passes.

**[Fix for Problem 3: Added explicit detail about how "freshness" is implemented]**

**Response Phase**: Three separate fresh agents receive the critique and produce responses:
- **A (Conservative)**: Argues the current version is fine and the proposed changes would make things worse
- **B (Adversarial)**: Accepts the critique and revises to fix the identified problems  
- **AB (Synthesis)**: Attempts to combine the best aspects of both perspectives

**Judge Phase**: A panel of fresh judge agents performs blind evaluation. Each judge receives all three documents (A, B, AB) in randomized order with no authorship information. Judges rank the documents from best to worst. Rankings are aggregated using Borda count (3 points for first place, 2 for second, 1 for third). The document with the highest total Borda score wins.

**[Fix for Problem 3: Added explicit Borda scoring details]**

This architecture is designed to address each failure mode through isolation. Fresh agents prevent context accumulation across passes. Blind evaluation removes authorship signals. The three-way competition provides alternatives to both accepting and rejecting critiques. Multiple judges reduce individual bias. However, we note these are design principles rather than empirically validated claims.

**[Fix for Problem 6: Removed unsupported causal claims, reframed as design principles]**

The conservative tiebreak rule preserves stability: when documents receive equal Borda scores, the incumbent (A) wins. This prevents oscillation between equally valid alternatives and ensures changes represent genuine improvements.

The system continues until reaching a convergence threshold of consecutive incumbent victories. Our experiments used a threshold of 3 consecutive A wins. The experiment ran for 26 passes, achieving 2 consecutive wins twice (passes 14-15 and 24-25) before manual termination.

## 3. Experiments

We evaluated autoreason on go-to-market strategy generation for an open-source Kubernetes CLI tool with 5k GitHub stars, no revenue, and a 3-person team. All experiments used anthropic/claude-sonnet-4-20250514 with temperature 0.8 for authors, 0.3 for judges, and max_tokens of 4096.

Our v2 architecture implemented the complete isolation protocol: fresh agents per role per pass, 3-judge panels with Borda count aggregation, conservative tiebreaking, and convergence threshold of 3 consecutive incumbent wins.

The primary experiment ran 26 passes (~160 LLM calls) before manual termination. The initial document contained 847 words. The system achieved 2 consecutive incumbent wins twice (passes 14-15 and 24-25) but never reached the 3-consecutive threshold required for convergence. We manually terminated the experiment after 26 passes rather than allowing it to continue indefinitely.

**[Fix for Problem 8: Clarified that manual termination was a choice, not because convergence was proven unattainable]**

For comparison, we generated outputs using four alternative approaches applied to the same task:
- **Conservative**: Single-pass improvement with explicit instruction to preserve strengths  
- **Improve_this**: Direct instruction to improve the document
- **Harsh_critic**: Aggressive critique followed by revision
- **Critique_and_revise**: Structured critique generation then addressing it

We then compared all five outputs (autoreason's output from pass 15, plus the four alternatives) using 7 independent judges who ranked them without knowing which method produced which output.

**[Fix for Problem 1: Accurately described the evaluation as a comparison of outputs, not claiming a formal "blind panel" protocol]**

To assess quality trajectory within autoreason, we compared outputs from pass 15 versus pass 25 with another 7-judge evaluation. We selected pass 15 as it marked the end of the first 2-consecutive win streak, and pass 25 as the end of the second streak.

**[Fix for Problem 5: Explained why these specific passes were selected]**

## 4. Results

In the 5-way comparison, autoreason achieved unanimous first-place preference across all judges (Table 1). With 7 judges each ranking 5 outputs, autoreason received all 7 first-place votes and a total Borda score of 35 (7 judges × 5 points for ranking first).

**[Fix for Problem 9: Clarified what the Borda score means rather than presenting it as a percentage]**

| Method | Borda Score | First Place Votes | Final Word Count |
|--------|-------------|-------------------|------------------|
| Autoreason (pass 15) | 35 | 7 | 1800 |
| Conservative | 21 | 0 | 862 |
| Improve_this | 18 | 0 | 2116 |
| Harsh_critic | 18 | 0 | 1961 |
| Critique_and_revise | 13 | 0 | 2507 |

**[Fix for Problem 1: Clarified that autoreason entry is from pass 15]**

The conservative baseline outperformed all iterative approaches except autoreason, confirming that naive iteration degrades quality. Critique_and_revise performed worst despite its structured approach.

Pass 15 defeated pass 25 by 6-1 votes. While this comparison is limited to two specific points, it suggests quality did not improve in the latter passes.

**[Fix for Problem 5: Acknowledged limitation of comparing only two points]**

Word counts reveal scope expansion in traditional methods. From an initial 847 words, improve_this expanded to 2116 and critique_and_revise to 2507. The conservative baseline remained concise at 862 words. Autoreason's word count varied significantly throughout the experiment, reaching 1800 at pass 15, peaking at 2037 at pass 18, dropping to 1707 at pass 19, spiking again to 2008 at pass 21, and ending around 1617 at pass 26. This oscillation between ~1600-2000 words in later passes indicates the system did not stabilize on a consistent scope.

**[Fix for Problem 4: Accurately described word count oscillation rather than claiming stabilization]**

The trajectory analysis reveals important patterns. The incumbent won 31% of passes (8/26), with B winning 19% (5/26) and AB winning 50% (13/26). This distribution shows that the synthesis approach dominated throughout the experiment, though the incumbent did achieve two separate 2-consecutive win streaks.

Notably, B re-emerged as a winner in passes 17-21 after being absent since pass 1, winning 4 of 5 consecutive passes. This resurgence of the adversarial approach late in the experiment suggests the system was oscillating between different solution approaches rather than converging.

**[Fix for Problem 2: Added important detail about B's resurgence that undermines stability claims]**

Qualitative analysis shows dramatic improvement in specificity. The initial strategy proposed generic targets, $49/user pricing, and projected $100K MRR without justification. The converged output quantified customer pain ($15K per incident × 6 incidents/year), proposed team-based pricing ($1499/month), and grounded projections in validation data (50+ customer interviews, 75% pilot success rate, CAC $2K, LTV $54K).

In a separate comparison where judges could see the original baseline, autoreason's output won unanimously (7-0) against an output generated using only adversarial revision. Without baseline context, the margin was narrower (3-2), demonstrating the importance of anchoring for drift detection.

**[Fix for Problem 7: Clarified what "adversarial approach" means]**

## 5. Related Work

The concept of autoresearch—iterative LLM refinement for objective domains—inspired our extension to subjective domains [2]. By replacing hard metrics with systematic human preference simulation, we address domains where ground truth is unavailable.

Recent work has demonstrated that iterative refinement with critique can degrade output quality, producing verbose, overcomplicated results even in domains with objective correctness metrics [1]. These findings parallel our observations in subjective domains.

The problem of context collapse in extended LLM interactions, where performance degrades as conversation length increases, motivated our fresh agent architecture [3]. Prior multi-agent deliberation approaches maintained shared context between agents [4], leading to contamination in extended deliberation that our isolation protocol prevents.

## 6. Discussion

The bloat/prune oscillation observed in passes 17-26 represents a fundamental challenge: the system oscillates between "comprehensive" and "focused" attractors without reaching equilibrium. When B wins multiple consecutive passes (17, 19-21) after being absent since pass 1, it signals that the task specification itself may be underdetermined regarding desired scope and detail level. This oscillation prevented convergence and led to manual termination after 26 passes.

Our convergence threshold of 3 consecutive wins was not achieved in 26 passes—the system achieved 2 consecutive wins twice but could not maintain dominance for a third pass. Whether this threshold is too high or the task admits multiple equally valid solutions remains an open question.

**[Fix for Problem 8: Removed claim that threshold was "unattainable"]**

The 7-0 result when judges could compare against baseline demonstrates that drift detection benefits from anchoring. This has implications for deployment where maintaining alignment with original intent matters.

While our evaluation focused on subjective preference aggregated across multiple judges, we acknowledge limitations in our analysis. We did not assess inter-rater reliability, statistical significance of preferences, or confidence intervals on the results. The unanimous preference for autoreason is striking but based on a single task with 7 judges.

**[Fix for Problem 10: Acknowledged lack of statistical analysis as a limitation]**

While the method's design aims to address the stated failure modes—fresh agents to prevent context collapse, blind evaluation to reduce bias, three-way competition to handle different critique responses—we have not empirically validated that these mechanisms achieve their intended effects. Future work should isolate and test each component.

**[Fix for Problem 6: Acknowledged lack of empirical validation for claimed mechanisms]**

Autoreason may extend to objective domains where metrics prove insufficient. Code readability, documentation quality, and API design have objective constraints but ultimately require subjective judgment. The method could complement hard metrics in these domains.

## 7. Conclusion

Autoreason enables iterative LLM refinement in subjective domains through systematic isolation and aggregation. By treating each iteration as a fresh three-way competition with blind evaluation, it avoids some failure modes that plague traditional approaches.

Our experiments demonstrate strong preference over existing methods, achieving unanimous first-place votes in head-to-head comparison. However, the method's inability to reach convergence after 26 passes, combined with significant word count oscillation in later passes, reveals fundamental challenges in defining stable equilibria for underdetermined tasks.

**[Fix for Problem 4: Added word count oscillation to conclusion]**

The success of autoreason suggests that the key to LLM self-improvement lies not in sophisticated prompting but in proper experimental design. Fresh perspectives, blind evaluation, and systematic aggregation unlock capabilities that shared context obscures.

## References

[1] Orlanski et al. "SlopCodeBench: Evaluating Code Generation Quality Degradation in Iterative LLM Refinement." 2026.

[2] Karpathy, A. "Autoresearch: Automated Scientific Discovery through Iterative Refinement." 2025.

[3] Zhang et al. "ACE: Analyzing Context Effects in Extended LLM Interactions." ICLR 2026.

[4] LLM Council Contributors. "Multi-Agent Deliberation for Complex Reasoning Tasks." 2025.