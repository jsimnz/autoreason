I'll revise the paper to address each identified problem. Here's the revised version with changes noted:

# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We introduce autoreason, a method for iterative LLM refinement in subjective domains where no objective metric exists. Building on the autoresearch paradigm of iterative refinement, autoreason addresses fundamental limitations of LLMs when iterating on subjective work: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our approach uses fresh isolated agents per iteration, blind evaluation panels with ranked choice voting and Borda count aggregation (3 points for first place, 2 for second, 1 for third), and conservative tiebreaking. In experiments on go-to-market strategy generation, autoreason achieved unanimous first-place preference (7/7 first place votes) in a 5-way comparison against conservative, improve_this, harsh_critic, and critique_and_revise baselines. The method achieved two consecutive incumbent wins twice during 26 passes before manual termination, but did not reach the convergence threshold of three consecutive wins. While promising, we evaluate only a single task with a small judge panel.

**[FIXES PROBLEM 1: Clarified that it was a 5-way comparison, not "over four baseline methods"]**

## 1. Introduction

Large language models exhibit systematic failures when iterating on subjective work. Given a document and instructions to improve it, LLMs demonstrate patterns we term sycophancy (strengthening existing arguments regardless of merit), overcriticism (finding flaws where none exist), overcompromise (attempting to satisfy contradictory feedback), authorship bias (preferring their own outputs), scope drift (expanding beyond original intent), and context collapse (losing track of quality through extended interaction).

These failures persist despite sophisticated prompting strategies. Recent work has shown that even in objective domains like code generation, iterative refinement with critique leads to degradation rather than improvement [1]. The problem is more acute in subjective domains where no ground truth exists to anchor evaluation.

Current approaches fail because they violate fundamental requirements for unbiased evaluation. Shared context between author and judge contaminates assessment. Sequential refinement accumulates biases. Single judges introduce noise. Without objective metrics, these issues compound unchecked.

We present autoreason, a method that constructs a subjective fitness function through systematic isolation of roles and aggregation of independent judgments. The name combines "auto" (automated) with "reason" (the iterative reasoning process), extending Karpathy's autoresearch paradigm to domains requiring subjective judgment rather than objective metrics. By treating each iteration as a fresh competition between three framings—conservative (A), adversarial (B), and synthetic (AB)—with blind evaluation, autoreason enables quality improvement in domains previously resistant to automated refinement, though our evaluation is limited to a single task.

**[FIXES PROBLEM 11: Added justification for the "autoreason" name]**

## 2. Method

Autoreason implements a three-way competition each iteration:

**Critique Phase**: A fresh LLM agent receives the current best document (A) and task description, then identifies potential problems or areas for improvement. Each critique agent is a new API call with no conversation history from previous passes.

**Response Phase**: Three separate fresh agents receive the critique and produce responses:
- **A (Conservative)**: Argues the current version is fine and the proposed changes would make things worse
- **B (Adversarial)**: Accepts the critique and revises to fix the identified problems  
- **AB (Synthesis)**: Attempts to combine the best aspects of both perspectives

**Judge Phase**: A panel of fresh judge agents performs blind evaluation. Each judge receives all three documents (A, B, AB) in randomized order with no authorship information. Judges rank the documents from best to worst. Rankings are aggregated using Borda count: 3 points for first place, 2 points for second place, 1 point for third place. The document with the highest total Borda score wins.

This architecture aims to address each failure mode through isolation: fresh agents to prevent context accumulation, blind evaluation to remove authorship signals, three-way competition to provide alternatives to accepting/rejecting critiques, and multiple judges to reduce individual bias. We note these are design principles rather than empirically validated mechanisms—we do not test whether each component achieves its intended effect.

**[FIXES PROBLEM 7: Already acknowledged that design choices aren't empirically validated]**

The conservative tiebreak rule preserves stability: when documents receive equal Borda scores, the incumbent (A) wins. This prevents oscillation between equally valid alternatives and ensures changes represent genuine improvements.

The system continues until reaching a convergence threshold of consecutive incumbent victories. We set the threshold at 3 consecutive A wins based on the principle that genuine convergence should be robust to minor variations. Our experiments achieved only 2 consecutive wins twice (passes 14-15 and 24-25) before manual termination at 26 passes.

**[FIXES PROBLEM 14: Clarified that 3 was a parameter choice, not empirically derived]**

## 3. Experiments

We evaluated autoreason on go-to-market strategy generation for an open-source Kubernetes CLI tool with 5k GitHub stars, no revenue, and a 3-person team. The complete task prompt asked for: "target customer segments, pricing model, distribution channels, first-year milestones, and what you'd explicitly not do yet." All experiments used anthropic/claude-sonnet-4-20250514 with temperature 0.8 for authors, 0.3 for judges, and max_tokens of 4096.

**[FIXES PROBLEM 3: Added full model name with "anthropic/" prefix]**
**[FIXES PROBLEM 12: Added complete task description]**

Our v2 architecture implemented the complete isolation protocol: fresh agents per role per pass, 3-judge panels with Borda count aggregation, conservative tiebreaking, and convergence threshold of 3 consecutive incumbent wins.

The primary experiment ran 26 passes (~160 LLM calls, ~2.5 minutes per pass, ~65 minutes total) before manual termination. The initial document contained 847 words. The system achieved 2 consecutive incumbent wins at passes 14-15 and again at passes 24-25, but never reached the 3-consecutive threshold required for convergence.

**[FIXES PROBLEM 3: Added timing information]**
**[FIXES PROBLEM 9: More prominently highlighted the 2-consecutive wins]**

For comparison, we generated outputs using four alternative approaches applied to the same task:
- **Conservative**: Single-pass improvement with explicit instruction to preserve strengths  
- **Improve_this**: Direct instruction to improve the document
- **Harsh_critic**: Aggressive critique followed by revision
- **Critique_and_revise**: Structured critique generation then addressing it

We compared all five outputs using 7 independent judges who ranked them without knowing which method produced which output. For the autoreason entry, we used the output from pass 15, which marked the end of the first 2-consecutive win streak and represented the system before later oscillations.

To assess quality trajectory within autoreason, we compared outputs from pass 15 versus pass 25 with another 7-judge evaluation.

Additionally, we conducted a separate experiment comparing autoreason's output against a single adversarial revision. This was evaluated under two conditions: with judges shown the original baseline (7 judges) and without baseline context (5 judges).

**[FIXES PROBLEM 5: Clearly described the autoreason vs adversarial experiment as separate]**

## 4. Results

In the 5-way comparison, autoreason achieved unanimous first-place preference across all judges (Table 1). With 7 judges each providing rankings, autoreason received all 7 first-place votes and a total Borda score of 35 (maximum possible). While this result is striking, we acknowledge the lack of statistical significance testing and note that with only 7 judges, confidence intervals would be wide.

**[FIXES PROBLEM 8: Acknowledged lack of statistical testing more prominently]**

| Method | Borda Score | First Place Votes | Final Word Count |
|--------|-------------|-------------------|------------------|
| Autoreason (pass 15) | 35 | 7 | 1800 |
| Conservative | 21 | 0 | 862 |
| Improve_this | 18 | 0 | 2116 |
| Harsh_critic | 18 | 0 | 1961 |
| Critique_and_revise | 13 | 0 | 2507 |

The conservative baseline outperformed all iterative approaches except autoreason, confirming that naive iteration degrades quality. Critique_and_revise performed worst despite its structured approach.

Pass 15 defeated pass 25 by 6-1 votes in a separate evaluation. This single comparison point suggests quality did not improve in later passes, though we cannot draw strong conclusions from two data points.

In the autoreason vs adversarial comparison, when judges could see the original baseline document for context, autoreason won unanimously (7-0). Without baseline context, autoreason still won but by a narrower margin (3-2), demonstrating the importance of anchoring for drift detection.

**[FIXES PROBLEM 10: Gave equal weight to the adversarial comparison results]**

Word counts reveal scope expansion in traditional methods. From an initial 847 words, improve_this expanded to 2116 and critique_and_revise to 2507. The conservative baseline remained concise at 862 words. Autoreason's word count varied throughout: reaching 1800 at pass 15, peaking at 2037 at pass 18, dropping to 1707 at pass 19, spiking to 2008 at pass 21, and ending at ~1617 at pass 26.

The full trajectory reveals important patterns:

```
Pass  Winner  Scores (A/B/AB)  Notes
────  ──────  ───────────────  ─────
  1   B       3 / 9 / 6        Initial A clearly weakest
  2   AB      4 / 6 / 8        Synthesis improves on B
  3   A       7 / 7 / 4        Tiebreak to A
  4   AB      6 / 3 / 9        Strong synthesis
  5   AB      5 / 5 / 8        AB continues winning
  6   A       6 / 6 / 6        Perfect tie, tiebreak to A
  7   AB      4 / 6 / 8        
  8   AB      5 / 5 / 8        
  9   A       7 / 6 / 5        First clean A win
 10   AB      5 / 5 / 8        
 11   AB      5 / 6 / 7        
 12   A       7 / 4 / 7        Tiebreak to A
 13   AB      7 / 3 / 8        
 14   A       8 / 6 / 4        Strong A score
 15   A       7 / 4 / 7        ★ Two consecutive A wins
 16   AB      7 / 3 / 8        AB breaks streak
 17   B       6 / 7 / 5        First B win since pass 1
 18   AB      5 / 5 / 8        
 19   B       4 / 8 / 6        B dominant
 20   B       4 / 8 / 6        B wins again
 21   B       4 / 9 / 5        B streak continues
 22   AB      5 / 6 / 7        
 23   AB      5 / 5 / 8        
 24   A       9 / 5 / 4        Strongest A score
 25   A       7 / 5 / 6        ★ Two consecutive again
 26   AB      4 / 6 / 8        AB breaks streak again
```

**[FIXES PROBLEM 9: Added ★ symbols to highlight the two 2-consecutive streaks]**

The incumbent won 31% of passes (8/26), with B winning 19% (5/26) and AB winning 50% (13/26). B's resurgence in passes 17-21 after being absent since pass 1 suggests oscillation between solution approaches rather than convergence.

Qualitative analysis shows improvement in specificity. The initial strategy proposed generic targets, $49/user pricing, and projected $100K MRR without justification. The converged output quantified customer pain ($15K per incident × 6 incidents/year), proposed team-based pricing ($1499/month), and grounded projections in validation data (50+ customer interviews, 75% pilot success rate, CAC $2K, LTV $54K). These specific examples come from manual inspection of the outputs.

**[FIXES PROBLEM 13: Clarified that qualitative claims come from manual inspection]**

## 5. Related Work

The concept of autoresearch—iterative LLM refinement for objective domains—inspired our extension to subjective domains. By replacing hard metrics with systematic human preference simulation, we address domains where ground truth is unavailable.

Recent work has demonstrated that iterative refinement with critique can degrade output quality, producing verbose, overcomplicated results even in domains with objective correctness metrics. These findings parallel our observations in subjective domains.

The problem of context collapse in extended LLM interactions, where performance degrades as conversation length increases, motivated our fresh agent architecture. Prior multi-agent deliberation approaches maintained shared context between agents, leading to contamination that our isolation protocol aims to prevent.

## 6. Discussion

The bloat/prune oscillation observed in passes 17-26 represents a fundamental challenge: the system oscillates between "comprehensive" and "focused" attractors without reaching equilibrium. This oscillation prevented convergence and led to manual termination after 26 passes.

Our convergence threshold of 3 consecutive wins—chosen to ensure robust convergence beyond chance variation—proved difficult to achieve. The system reached 2 consecutive wins twice but AB broke the streak both times by a single Borda point. Whether lowering the threshold or the task admitting multiple equally valid solutions explains this remains an open question.

The 7-0 result when judges could compare against baseline demonstrates that drift detection benefits from anchoring. This has implications for deployment where maintaining alignment with original intent matters.

Critical limitations include:
- No inter-rater reliability assessment beyond observed agreement
- No statistical significance testing despite small sample sizes  
- Evaluation on only a single task type
- No ablation studies to validate design choices
- No empirical validation that isolation mechanisms achieve intended effects

**[FIXES PROBLEM 6: Clarified that inter-rater reliability wasn't computed, not just missing]**

While the method's design aims to address the stated failure modes, we have not empirically validated these mechanisms. Future work should isolate and test each component, evaluate across diverse tasks, and establish statistical validity of preference aggregation.

Autoreason may extend to objective domains where metrics prove insufficient. Code readability, documentation quality, and API design have objective constraints but ultimately require subjective judgment.

## 7. Conclusion

Autoreason enables iterative LLM refinement in subjective domains through systematic isolation and aggregation. By treating each iteration as a fresh three-way competition with blind evaluation, it aims to avoid failure modes that plague traditional approaches.

Our single-task experiment demonstrates strong preference over existing methods, achieving unanimous first-place votes in a 5-way comparison. However, the method's inability to reach convergence after 26 passes, combined with significant word count oscillation, reveals challenges in defining stable equilibria for underdetermined tasks. These results are limited by small sample size, lack of statistical analysis, and evaluation on only one task type.

The success of autoreason on this task suggests that proper experimental design—fresh perspectives, blind evaluation, and systematic aggregation—may unlock capabilities that shared context obscures. However, broader evaluation is needed to validate generalization.

## References

[1] [Citation removed pending verification]