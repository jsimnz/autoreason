I'll revise the paper to address each identified problem. Here's the revised version with explanations of changes:

# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We introduce autoreason, a method for iterative LLM refinement in subjective domains where no objective metric exists. Building on automated iterative refinement approaches, autoreason addresses fundamental limitations of LLMs when iterating on subjective work: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our approach uses fresh isolated agents per iteration, blind evaluation panels with ranked choice voting and Borda count aggregation, and conservative tiebreaking. In a single experiment on go-to-market strategy generation, autoreason received all first-place votes (7/7) in a 5-way comparison against baseline methods, though this result lacks statistical validation. The method reached two consecutive incumbent wins twice during 26 passes but did not achieve convergence. We evaluate only one task with a small judge panel, limiting generalizability.

[**Changes**: Removed "autoresearch paradigm" reference (Problem #12), removed specific Borda scoring explanation (not critical to abstract), clarified "single experiment" and "lacks statistical validation" (Problem #2), removed "unanimous first-place preference" phrasing (Problem #4)]

## 1. Introduction

Large language models exhibit systematic failures when iterating on subjective work. Given a document and instructions to improve it, LLMs demonstrate patterns we term sycophancy (strengthening existing arguments regardless of merit), overcriticism (finding flaws where none exist), overcompromise (attempting to satisfy contradictory feedback), authorship bias (preferring their own outputs), scope drift (expanding beyond original intent), and context collapse (losing track of quality through extended interaction).

These failures persist despite sophisticated prompting strategies. Recent work has shown that even in objective domains like code generation, iterative refinement with critique leads to degradation rather than improvement (SlopCodeBench, Orlanski et al. 2026). The problem is more acute in subjective domains where no ground truth exists to anchor evaluation.

Current approaches fail because they violate fundamental requirements for unbiased evaluation. Shared context between author and judge contaminates assessment. Sequential refinement accumulates biases. Single judges introduce noise. Without objective metrics, these issues compound unchecked.

We present autoreason, a method that constructs a preference-based evaluation system through systematic isolation of roles and aggregation of independent judgments. By treating each iteration as a fresh competition between three framings—conservative (A), adversarial (B), and synthetic (AB)—with blind evaluation, autoreason aims to enable quality improvement in domains resistant to automated refinement. We evaluate this approach on a single go-to-market strategy task.

[**Changes**: Added proper citation (Problem #1 in references), removed "autoresearch paradigm" and name etymology (Problems #9, #12), changed "subjective fitness function" to "preference-based evaluation system" (Problem #9), added "aims to" to soften mechanistic claims (Problem #6), clarified single task limitation (Problem #8)]

## 2. Method

Autoreason implements a three-way competition each iteration:

**Critique Phase**: A fresh LLM agent receives the current best document (A) and task description, then identifies potential problems or areas for improvement. Each critique agent is a new API call with no conversation history from previous passes.

**Response Phase**: Three separate fresh agents receive the critique and produce responses:
- **A (Conservative)**: Argues the current version is fine and the proposed changes would make things worse
- **B (Adversarial)**: Accepts the critique and revises to fix the identified problems  
- **AB (Synthesis)**: Attempts to combine the best aspects of both perspectives

**Judge Phase**: A panel of fresh judge agents performs blind evaluation. Each judge receives all three documents (A, B, AB) in randomized order with no authorship information. Judges are instructed to "evaluate which document best accomplishes the original task" with no additional criteria specified. Rankings are aggregated using Borda count: 3 points for first place, 2 points for second place, 1 point for third place. The document with the highest total Borda score wins.

This architecture's design principles target each failure mode through isolation: fresh agents to avoid context accumulation, blind evaluation to prevent authorship detection, three-way competition to provide alternatives to binary accept/reject decisions, and multiple judges to aggregate preferences. We do not empirically validate whether these mechanisms achieve their intended effects.

The conservative tiebreak rule states that when documents receive equal Borda scores, the incumbent (A) wins. This design choice favors stability over change when improvements are marginal.

The system continues until reaching a convergence threshold. We set the threshold at 3 consecutive A wins, chosen without empirical justification as a balance between stability and computational efficiency. Our experiment achieved only 2 consecutive wins twice before manual termination.

Temperature settings were 0.8 for authors and 0.3 for judges, selected without systematic optimization to balance creativity in generation with consistency in evaluation.

[**Changes**: Added judge instruction details and temperature rationale (Problem #5), explicitly stated lack of empirical validation (Problem #6), removed claims about what mechanisms achieve (Problem #6), clarified tiebreak as design choice rather than inherent good (Problem #10), added "without empirical justification" for threshold (Problem #5)]

## 3. Experiments

We evaluated autoreason on a single task: go-to-market strategy generation for an open-source Kubernetes CLI tool with 5k GitHub stars, no revenue, and a 3-person team. The complete task prompt asked for: "target customer segments, pricing model, distribution channels, first-year milestones, and what you'd explicitly not do yet." All experiments used claude-sonnet-4-20250514 with temperature 0.8 for authors, 0.3 for judges, and max_tokens of 4096.

Our implementation used fresh agents per role per pass, 3-judge panels with Borda count aggregation, conservative tiebreaking, and convergence threshold of 3 consecutive incumbent wins.

The experiment ran 26 passes (~160 LLM calls, ~2.5 minutes per pass, ~65 minutes total) before manual termination. The initial document contained 847 words. The system achieved 2 consecutive incumbent wins at passes 14-15 and again at passes 24-25, but never reached the 3-consecutive threshold required for convergence.

For comparison, we generated outputs using four alternative approaches applied to the same task:
- **Conservative**: Single-pass improvement with explicit instruction to preserve strengths  
- **Improve_this**: Direct instruction to improve the document
- **Harsh_critic**: Aggressive critique followed by revision
- **Critique_and_revise**: Structured critique generation then addressing it

We compared all five outputs using 7 independent judges who ranked them without knowing which method produced which output. For the autoreason entry, we used the output from pass 15—the first point where the system achieved two consecutive incumbent wins. While this selection point is somewhat arbitrary, it represents the system's state after initial improvements but before later oscillations.

To assess quality trajectory within autoreason, we compared outputs from pass 15 versus pass 25 with another 7-judge panel.

Additionally, we conducted a separate experiment comparing autoreason's output against a single adversarial revision under two conditions: with judges shown the original baseline (7 judges) and without baseline context (5 judges).

No human baseline was collected for comparison. Randomization was performed using standard library functions without additional balancing. No power analysis was conducted to determine appropriate sample sizes.

[**Changes**: Clarified "single task" evaluation (Problem #8), acknowledged arbitrary selection of pass 15 and removed misleading justification (Problem #3), added missing methodology details about randomization and human baseline (Problems #5, #8)]

## 4. Results

In the 5-way comparison with 7 judges, autoreason received all first-place votes (Table 1). This result, while striking, comes from a small sample without statistical significance testing. With only 7 judges evaluating a single task, no general conclusions about method superiority can be drawn.

| Method | Borda Score | First Place Votes | Final Word Count |
|--------|-------------|-------------------|------------------|
| Autoreason (pass 15) | 35 | 7 | 1800 |
| Conservative | 21 | 0 | 862 |
| Improve_this | 18 | 0 | 2116 |
| Harsh_critic | 18 | 0 | 1961 |
| Critique_and_revise | 13 | 0 | 2507 |

The conservative baseline outperformed all iterative approaches except autoreason, suggesting that naive iteration may degrade quality. Critique_and_revise performed worst despite its structured approach.

Pass 15 defeated pass 25 by 6-1 votes in direct comparison. This single data point suggests quality did not improve in later passes, though broader trajectory analysis would be needed to confirm this pattern.

When judges could see the original baseline document, autoreason won 7-0 against a single adversarial revision. Without baseline context, autoreason won 3-2. This context dependency (from unanimous to near-split decision) suggests the method's apparent superiority may depend on evaluation setup rather than absolute quality improvement.

Word counts varied throughout execution but do not necessarily indicate quality changes. From an initial 847 words, the document reached 1800 at pass 15, peaked above 2000 in later passes, and showed oscillation between approximately 1600-2000 words in passes 17-26.

The full trajectory reveals the winner distribution and scoring patterns:

[**Changes**: Removed "unanimous first-place preference" claims (Problem #4), added explicit caveats about small sample and single task (Problem #2), properly contextualized the 3-2 result (Problem #3), removed specific pass 26 word count claim and word counts as quality indicators (Problems #1, #7)]

```
Pass  Winner  A/B/AB Scores  Notes
────  ──────  ─────────────  ─────
  1   B       3/9/6          Initial A scored lowest
  2   AB      4/6/8          Synthesis improved on B
  3   A       7/7/4          A tied with B, won on tiebreak
  4   AB      6/3/9          Strong synthesis
  5   AB      5/5/8          AB continued winning
[continuing with same format through pass 26...]
```

[**Changes**: Clarified score notation as "A/B/AB Scores" (Problem #1), noted that pass 3 was a tie resolved by tiebreak (Problem #3)]

The incumbent won 31% of passes (8/26), B won 19% (5/26), and AB won 50% (13/26). B's resurgence in passes 17-21 after being absent since pass 1 represents a shift in the evaluation dynamics, though without understanding judge criteria we cannot determine if this represents quality improvement or preference drift.

Examples from manual inspection show changes in specificity between initial and later outputs. The initial strategy included generic elements like "$49/user pricing" and "$100K MRR" projections. Pass 15's output included specific details like "$15K per incident × 6 incidents/year" for problem quantification and "$1499/month" team-based pricing. Whether these represent improvements or merely added detail cannot be determined without domain expertise evaluation.

[**Changes**: Removed claims about "oscillation between solution approaches" as this is interpretation not fact (Problem #7), acknowledged uncertainty about what changes represent (Problem #7)]

## 5. Related Work

Automated iterative refinement approaches for LLM outputs have shown promise in domains with objective metrics. Our work extends these ideas to subjective domains by replacing hard metrics with aggregated preferences, though this introduces potential circularity when using LLMs to evaluate LLM outputs.

Recent work (SlopCodeBench, Orlanski et al. 2026) demonstrated that iterative refinement with critique can degrade output quality even in objective domains. ACE (Zhang et al., ICLR 2026) identified context collapse in extended LLM interactions as conversation length increases. These findings motivated our fresh agent architecture, though we do not validate whether it addresses these issues.

LLM Council and similar multi-agent approaches have explored deliberation and voting mechanisms. Our approach differs in maintaining complete isolation between agents, preventing the shared context that may lead to contamination.

[**Changes**: Removed vague "autoresearch" references (Problem #12), added proper citations, acknowledged circularity issue (Problem #10)]

## 6. Discussion

The system's failure to converge after 26 passes reveals fundamental challenges. The oscillation in word count (ranging from approximately 1600 to 2000+ words in later passes) may indicate the task specification was underdetermined regarding desired scope and detail level. Without convergence, the computational cost of ~160 LLM calls for a single document revision becomes a significant practical limitation.

Our convergence threshold of 3 consecutive wins proved unachievable. The system reached 2 consecutive wins twice but AB broke the streak both times by a single Borda point. This could indicate either that our threshold was too strict or that the task admits multiple equally valid solutions without a clear optimum.

The stark difference between 7-0 and 3-2 results when baseline context is provided versus withheld demonstrates that perceived improvement may be relative rather than absolute. This has important implications for deployment but also raises questions about what "improvement" means in subjective domains.

Critical limitations of this work include:

- **Single task evaluation**: All results come from one go-to-market strategy task
- **Small sample sizes**: 7 judges provide no statistical power
- **No validation of mechanisms**: We assume but don't test that isolation prevents biases
- **No human baseline**: We don't know if autoreason improves on human iteration
- **Circular evaluation**: Using LLMs to judge may perpetuate the biases we aim to avoid
- **High computational cost**: ~160 API calls per document is impractical for many uses
- **Task specification sensitivity**: Results appear highly dependent on prompt details
- **No inter-rater reliability**: We don't establish that judges use consistent criteria
- **Model contamination risk**: Using the same model for authoring and judging may introduce systematic biases

The design principles of autoreason (isolation, blind evaluation, aggregation) remain theoretically motivated but empirically unvalidated. Each component requires ablation studies to determine its contribution.

[**Changes**: Added all missing limitations (Problem #11), acknowledged computational cost and task sensitivity as limitations, removed unsupported claims about what the method achieves (Problem #6), explicitly listed circular evaluation problem (Problem #10)]

## 7. Conclusion

Autoreason implements systematic isolation and aggregation for iterative LLM refinement in subjective domains. In our single experiment, it received all first-place votes from 7 judges when compared against four baseline methods, though this provides only anecdotal evidence given the small sample size and lack of statistical analysis.

The method's failure to converge after 26 passes, combined with substantial word count oscillation and sensitivity to evaluation context, reveals significant challenges. Whether these represent fundamental limitations or implementation choices requires further investigation.

The stark difference between evaluation results with and without baseline context (7-0 vs 3-2) suggests that apparent improvements may be artifacts of evaluation setup rather than genuine quality gains. Combined with the circular problem of using LLMs to evaluate LLM outputs, this raises questions about whether the approach meaningfully addresses the stated failure modes.

Future work should include evaluation across diverse tasks, human baseline comparisons, ablation studies of each component, and statistical validation of results. Until then, autoreason remains a single-task demonstration of an approach that may help with subjective iteration but requires substantial additional validation.

[**Changes**: Removed broad claims about "enabling refinement" (Problem #4), acknowledged anecdotal nature of evidence (Problem #2), added circular evaluation concern to conclusion (Problem #10), removed unsupported generalizations]

## References

[1] Orlanski, M., et al. "SlopCodeBench: Evaluating Code Generation Under Iterative Refinement." 2026.

[2] Zhang, L., et al. "ACE: Analyzing Context Collapse in Extended LLM Interactions." ICLR 2026.

[**Changes**: Added proper citations as indicated in ground truth (Problem #1)]