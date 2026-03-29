# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We introduce autoreason, a method for iterative LLM refinement in subjective domains where no objective metric exists. Building on the autoresearch paradigm of iterative refinement, autoreason addresses fundamental limitations of LLMs when iterating on subjective work: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our approach uses fresh isolated agents per iteration, blind evaluation panels with ranked choice voting and Borda count aggregation, and conservative tiebreaking. In experiments on go-to-market strategy generation, autoreason achieved unanimous first-place preference (35/35 Borda score, 7/7 first place votes) in a 5-way comparison against conservative, improve_this, harsh_critic, and critique_and_revise baselines. The method achieved two consecutive incumbent wins twice during 26 passes before manual termination. While promising, we evaluate only a single task with claude-sonnet-4-20250514 and acknowledge the statistical limitations of our 7-judge panel.

## 1. Introduction

Large language models exhibit systematic failures when iterating on subjective work. Given a document and instructions to improve it, LLMs demonstrate problematic patterns: strengthening existing arguments regardless of merit when asked to improve (sycophancy), finding flaws where none exist when asked to critique (overcriticism), attempting to satisfy contradictory feedback through excessive hedging (overcompromise), preferring their own prior outputs (authorship bias), expanding beyond original intent (scope drift), and degrading quality through extended interaction (context collapse).

These failures persist despite sophisticated prompting strategies. Recent work (SlopCodeBench, Orlanski et al. 2026) has shown that even in objective domains like code generation, iterative refinement with critique leads to degradation rather than improvement. The problem is more acute in subjective domains where no ground truth exists to anchor evaluation.

Current approaches fail because they violate fundamental requirements for unbiased evaluation. Shared context between author and judge contaminates assessment. Sequential refinement accumulates biases. Single judges introduce noise. Without objective metrics, these issues compound unchecked.

We present autoreason, a method that constructs a subjective fitness function through systematic isolation of roles and aggregation of independent judgments. By treating each iteration as a fresh competition between three framings—conservative (A), adversarial (B), and synthetic (AB)—with blind evaluation, autoreason shows promise for quality improvement in subjective domains, though our evaluation is limited to a single task and model.

## 2. Method

Autoreason implements a three-way competition each iteration:

**Critique Phase**: A fresh LLM agent (new API call with no conversation history) receives the current best document (A) and task description, then identifies potential problems or areas for improvement.

**Response Phase**: Three separate fresh agents produce responses:
- **A (Conservative)**: Argues the current version is fine and the proposed changes would make things worse
- **B (Adversarial)**: Accepts the critique and revises to fix the identified problems  
- **AB (Synthesis)**: Attempts to combine the best aspects of both perspectives

**Judge Phase**: A panel of fresh judge agents performs blind evaluation. Each judge receives all three documents (A, B, AB) in randomized order with no authorship information. Judges rank the documents from best to worst. Rankings are aggregated using Borda count: 3 points for first place, 2 points for second place, 1 point for third place. The document with the highest total Borda score wins.

The conservative tiebreak rule preserves stability: when documents receive equal Borda scores, the incumbent (A) wins. This prevents oscillation between equally valid alternatives.

The system continues until reaching a convergence threshold. We used 3 consecutive A wins as our threshold. Our experiments achieved 2 consecutive wins twice (passes 14-15 and 24-25) before manual termination at 26 passes.

## 3. Experiments

We evaluated autoreason on go-to-market strategy generation for an open-source Kubernetes CLI tool with 5k GitHub stars, no revenue, and a 3-person team. The task prompt asked for: "target customer segments, pricing model, distribution channels, first-year milestones, and what you'd explicitly not do yet." All experiments used claude-sonnet-4-20250514 with temperature 0.8 for authors and 0.3 for judges.

Our v2 architecture implemented: fresh agents per role per pass, 3-judge panels with Borda count aggregation, conservative tiebreaking, and convergence threshold of 3 consecutive incumbent wins.

The primary experiment ran 26 passes (~160 LLM calls, ~2.5 minutes per pass, ~65 minutes total) before manual termination. The initial document contained 847 words. The system achieved 2 consecutive incumbent wins at passes 14-15 and again at passes 24-25, but never reached the 3-consecutive threshold.

For comparison, we generated outputs using four alternative approaches:
- **Conservative**: Single-pass improvement with explicit instruction to preserve strengths  
- **Improve_this**: Direct instruction to improve the document
- **Harsh_critic**: Aggressive critique followed by revision
- **Critique_and_revise**: Structured critique generation then addressing it

We compared all five outputs using 7 independent judges. For autoreason, we used the output from pass 15 (1800 words), which was the incumbent at the end of the first 2-consecutive win streak.

Additionally, we compared autoreason's output against a single adversarial revision under two conditions: with judges shown the original baseline (7 judges) and without baseline context (5 judges).

## 4. Results

In the 5-way comparison with 7 judges, autoreason achieved unanimous first-place preference (Table 1). All 7 judges ranked autoreason first, yielding a perfect Borda score of 35/35. The conservative baseline outperformed all other iterative approaches.

| Method | Borda Score | First Place Votes | Final Word Count |
|--------|-------------|-------------------|------------------|
| Autoreason (pass 15) | 35 | 7 | 1800 |
| Conservative | 21 | 0 | 862 |
| Improve_this | 18 | 0 | 2116 |
| Harsh_critic | 18 | 0 | 1961 |
| Critique_and_revise | 13 | 0 | 2507 |

**Table 1: 5-way comparison results (7 judges). Borda scoring: 3 points for 1st place, 2 for 2nd, 1 for 3rd.**

Pass 15 defeated pass 25 by 6-1 votes in direct comparison.

When comparing autoreason versus a single adversarial revision, results varied by condition: with baseline context, autoreason won 7-0; without baseline context, autoreason won 3-2. This demonstrates the importance of anchoring for drift detection.

The full trajectory (Figure 1) reveals three phases:

```
Pass  Winner  Scores (A/B/AB)  Words   Phase
────  ──────  ───────────────  ─────   ─────
  1   B       3 / 9 / 6        847     Improvement
  2   AB      4 / 6 / 8        1079    
  3   A       7 / 7 / 4        1172    
  4   AB      6 / 3 / 9        1172    
  5   AB      5 / 5 / 8        1246    
  6   A       6 / 6 / 6        1340    Plateau
  7   AB      4 / 6 / 8        1340    
  8   AB      5 / 5 / 8        1574    
  9   A       7 / 6 / 5        1705    
 10   AB      5 / 5 / 8        1705    
 11   AB      5 / 6 / 7        1752    
 12   A       7 / 4 / 7        1622    
 13   AB      7 / 3 / 8        1622    
 14   A       8 / 6 / 4        1800    
 15   A       7 / 4 / 7        1800    (2 consecutive)
 16   AB      7 / 3 / 8        1800    
 17   B       6 / 7 / 5        1839    Oscillation
 18   AB      5 / 5 / 8        2037    
 19   B       4 / 8 / 6        1707    
 20   B       4 / 8 / 6        1644    
 21   B       4 / 9 / 5        2008    
 22   AB      5 / 6 / 7        1702    
 23   AB      5 / 5 / 8        1639    
 24   A       9 / 5 / 4        1758    
 25   A       7 / 5 / 6        1758    (2 consecutive)
 26   AB      4 / 6 / 8        ~1617   
```

Phase 1 (passes 1-5): Rapid improvement with B and AB winning decisively.
Phase 2 (passes 6-16): Quality plateau with tighter margins and first consecutive A wins.
Phase 3 (passes 17-26): Oscillation between approaches, with B winning 4/10 passes after being absent since pass 1.

The incumbent won 31% of passes (8/26), B won 19% (5/26), and AB won 50% (13/26).

Qualitative comparison of initial versus pass 15 outputs shows increased specificity. The initial output proposed generic customer segments and "$49/user" pricing with "$100K MRR" projections. The pass 15 output included quantified pain points ("$15K/incident x 6/yr"), team-based pricing ("$1499/mo"), and validation metrics ("50+ interviews, 75% pilot success"). However, we did not systematically analyze which specific changes drove judge preferences.

## 5. Related Work

Autoresearch introduced iterative LLM refinement for objective domains. Our work extends this to subjective domains by replacing hard metrics with aggregated preference judgments.

SlopCodeBench (Orlanski et al. 2026) demonstrated that iterative refinement with critique can degrade output quality even in objective domains, producing verbose and overcomplicated code. These findings parallel our observations of bloat/prune oscillation.

Work on ACE context collapse (Zhang et al. ICLR 2026) showed performance degradation in extended LLM interactions as conversation length increases. This motivated our use of fresh agents per iteration, though we do not empirically validate whether this prevents the degradation.

LLM Council and related multi-agent approaches maintain shared context between agents. Our approach differs by isolating each agent to prevent cross-contamination.

## 6. Discussion

The bloat/prune oscillation in passes 17-26 suggests the task specification was underdetermined regarding desired scope. When AB adds detail and B removes it cyclically, this indicates multiple valid equilibria rather than a single optimum.

Our convergence threshold of 3 consecutive wins proved difficult to achieve—the system reached 2 consecutive wins twice but AB broke the streak both times by a single Borda point. With only 3 judges, one judge preferring AB suffices to prevent convergence.

The 7-0 versus 3-2 results (with and without baseline) demonstrate that judge preferences depend strongly on whether they can compare against the original. This has implications for deployment where drift from original intent matters.

Critical limitations:
- Single task evaluation: All results come from one go-to-market strategy task
- Single model: Only tested with claude-sonnet-4-20250514  
- Small sample: 7 judges provide limited statistical power
- No ablation studies: We did not test whether individual components (blind evaluation, three-way competition) achieve their intended effects
- No inter-rater reliability metrics

The method's failure to converge after 26 passes raises questions about whether the approach is fundamentally unstable or whether this specific task admits multiple equally valid solutions.

## 7. Conclusion

Autoreason demonstrates a structured approach to iterative refinement in subjective domains. In our single-task evaluation, it achieved unanimous preference over four baseline methods, though with only 7 judges this provides limited evidence of superiority.

The method's inability to converge after 26 passes and the observed oscillation patterns reveal challenges in defining stable solutions for underdetermined tasks. Whether this represents a fundamental limitation or a feature revealing task ambiguity remains unclear.

The strong performance difference when judges have baseline context (7-0) versus without (3-2) suggests the method may be most valuable when maintaining alignment with original intent matters. However, evaluation on diverse tasks with larger judge panels is essential before drawing general conclusions.

## References

[1] Orlanski et al. 2026. SlopCodeBench: Evaluating Code Generation Under Iterative Refinement. 

[2] Zhang et al. ICLR 2026. ACE: Analyzing Context Extension in Large Language Models.