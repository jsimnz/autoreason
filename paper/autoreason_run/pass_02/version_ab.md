# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We introduce autoreason, a method for iterative LLM refinement in subjective domains where no objective metric exists. Autoreason addresses systematic failures of LLMs when iterating on subjective work: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our approach uses fresh isolated agents per iteration, blind evaluation panels with ranked choice voting and Borda count aggregation, and conservative tiebreaking. In experiments on go-to-market strategy generation, autoreason achieved unanimous preference (35/35 Borda score, 7/7 first place votes) over four prompting baselines. The method revealed three distinct phases over 26 passes before manual termination: rapid improvement, quality plateau, and bloat/prune oscillation. While demonstrating promise, convergence remains challenging—the system achieved two consecutive incumbent wins twice but never reached our threshold of three.

## 1. Introduction

Large language models exhibit systematic failures when iterating on subjective work. Given a document and instructions to improve it, LLMs demonstrate sycophancy (agreeing with any critique), overcriticism (finding flaws where none exist), overcompromise (attempting to satisfy contradictory feedback), authorship bias (preferring their own outputs), scope drift (expanding beyond original intent), and context collapse (losing track of quality through extended interaction).

These failures persist despite sophisticated prompting strategies. The problem is particularly acute in subjective domains where no ground truth exists to anchor evaluation. Current approaches fail because they violate fundamental requirements for unbiased evaluation: shared context between author and judge contaminates assessment, sequential refinement accumulates biases, and single judges introduce noise.

We present autoreason, a method that constructs a subjective fitness function through systematic isolation of roles and aggregation of independent judgments. By treating each iteration as a fresh competition between three framings—conservative (A), adversarial (B), and synthetic (AB)—with blind evaluation, autoreason shows potential for quality improvement in subjective tasks.

## 2. Method

Autoreason implements a three-way competition each iteration (or "pass"):

**Critique Phase**: A fresh LLM agent receives the current best document (A) and task description, then identifies potential problems or areas for improvement.

**Response Phase**: Three separate fresh agents receive the critique and produce responses:
- **A (Conservative)**: Argues the current version is fine and the proposed changes would make things worse
- **B (Adversarial)**: Accepts the critique and revises to fix the identified problems  
- **AB (Synthesis)**: Attempts to combine the best aspects of both perspectives

**Judge Phase**: A panel of fresh judge agents performs blind evaluation. Each judge receives all three documents (A, B, AB) in randomized order with no authorship information. Judges use ranked choice voting to order the documents. Rankings are aggregated using Borda count (3 points for first place, 2 for second, 1 for third).

This architecture addresses each failure mode through isolation. Fresh agents prevent context collapse and authorship bias. Blind evaluation eliminates sycophancy. The three-way competition handles both overcriticism (A can win) and overcompromise (B can beat AB). Multiple judges reduce noise.

The conservative tiebreak rule preserves stability: when documents receive equal Borda scores, the incumbent (A) wins. This prevents oscillation between equally valid alternatives and ensures changes represent genuine improvements.

Convergence occurs after a specified number of consecutive incumbent victories. Our experiment used a threshold of 3 consecutive A wins. The system was manually terminated after 26 passes without reaching this threshold, though it achieved 2 consecutive wins twice.

## 3. Experiments

We evaluated autoreason on a single task: go-to-market strategy generation for an open-source Kubernetes CLI tool with 5k GitHub stars, no revenue, and a 3-person team. All experiments used claude-sonnet-4-20250514 with temperature 0.8 for authors and 0.3 for judges.

Our v2 architecture implemented the complete isolation protocol: fresh agents per role per pass, 3-judge panels with Borda count aggregation, conservative tiebreaking, and convergence threshold of 3 consecutive incumbent wins.

The primary experiment ran 26 passes over approximately 65 minutes (~2.5 min/pass, ~160 LLM calls) before manual termination. The system achieved 2 consecutive incumbent wins twice (passes 14-15 and 24-25) but never reached the 3-consecutive threshold.

For comparison, we tested four alternative prompting strategies on the same task:
- **Conservative**: Single-pass improvement with explicit instruction to preserve strengths  
- **Improve_this**: Direct instruction to improve the document
- **Harsh_critic**: Aggressive critique followed by revision
- **Critique_and_revise**: Structured critique generation then addressing it

A 7-judge blind panel (compared to 3 judges in the main experiment) evaluated all five outputs using ranked choice voting.

To assess quality trajectory, we compared outputs from pass 15 versus pass 25 with another 7-judge panel.

## 4. Results

### 4.1 Comparison Against Baselines

Autoreason achieved unanimous preference across all judges (Table 1). With 35/35 possible Borda points and 7/7 first place votes, it dominated all prompting alternatives. Notably, all baseline methods received 0 first place votes.

| Method | Borda Score | First Place | Final Words |
|--------|-------------|-------------|-------------|
| Autoreason | 35 | 7 | 1800 |
| Conservative | 21 | 0 | 862 |
| Improve_this | 18 | 0 | 2116 |
| Harsh_critic | 18 | 0 | 1961 |
| Critique_and_revise | 13 | 0 | 2507 |

The conservative baseline outperformed all iterative approaches except autoreason, confirming that naive iteration degrades quality. Critique_and_revise performed worst despite its structured approach.

### 4.2 Trajectory Analysis

The 26-pass experiment revealed three distinct phases:

**Phase 1 - Rapid Improvement (Passes 1-5)**: B and AB won with strong margins. The initial document improved substantially, with word count growing from 847 to 1246 (+47%).

**Phase 2 - Quality Plateau (Passes 6-16)**: A began surviving through close calls and tiebreaks. The system reached its first 2-consecutive A win streak at passes 14-15, with the document stabilized at 1800 words.

**Phase 3 - Bloat/Prune Oscillation (Passes 17-26)**: B re-emerged as a frequent winner after 15-pass absence, winning 4 of 5 passes (17-21). Word count oscillated between 1644 and 2037 as AB added complexity and B pruned it back. A second 2-consecutive streak occurred at passes 24-25.

Winner distribution across all passes: A: 8 wins (31%), B: 5 wins (19%), AB: 13 wins (50%).

Pass 15 defeated pass 25 by 6-1 votes, suggesting the additional 10 passes did not improve quality. This aligns with our phase analysis showing quality plateau was reached by pass 15.

### 4.3 Qualitative Improvements

The initial strategy proposed generic targets, $49/user pricing, and projected $100K MRR without justification. The converged output quantified customer pain ($15K per incident × 6 incidents/year), proposed team-based pricing ($1499/month), and grounded projections in validation data (50+ customer interviews, 75% pilot success rate, CAC $2K, LTV $54K).

In a separate experiment testing the importance of baseline context, autoreason competed against an adversarial approach with judges shown the original baseline, winning 7-0 unanimously. Without the baseline shown, the margin was only 3-2, demonstrating the importance of anchoring for drift detection.

## 5. Discussion

The bloat/prune oscillation observed in Phase 3 represents a key finding about underdetermined task specifications. When B wins multiple consecutive passes after long absence, it signals the system is oscillating between "comprehensive" and "focused" attractors. This pattern suggests the task itself lacks clear scope boundaries, causing instability between equally valid interpretations.

Our convergence threshold of 3 consecutive wins proved difficult to achieve—the system reached 2 consecutive wins twice but could not maintain dominance for a third pass. This raises questions about appropriate convergence criteria for subjective domains where multiple valid solutions may exist.

The unanimous preference for autoreason over baseline prompting strategies, combined with the conservative baseline outperforming other iterative approaches, suggests that isolation and structured competition provide value. However, with only a single task tested, generalization remains an open question.

While our evaluation focused on subjective preference aggregation, the method's architectural choices directly address the stated failure modes: fresh agents prevent context collapse and authorship bias, blind evaluation reduces sycophancy, and the three-way competition structure handles both overcriticism and overcompromise.

## 6. Related Work

This work builds on foundations in automated research and LLM evaluation. While specific implementations vary, the core challenge of iterative refinement in subjective domains has received limited attention. Our approach differs from existing multi-agent systems by enforcing complete isolation between roles and iterations.

## 7. Conclusion

Autoreason demonstrates a structured approach to iterative LLM refinement in subjective domains through systematic isolation and aggregation. In our go-to-market strategy experiment, it achieved unanimous preference over standard prompting approaches while revealing important patterns in LLM iteration behavior.

The three-phase trajectory—rapid improvement, quality plateau, and bloat/prune oscillation—suggests both the promise and limitations of automated refinement. While initial passes show clear improvement, convergence remains elusive, with the system oscillating between competing interpretations of task scope.

Future work should explore whether these patterns generalize across different subjective tasks, investigate alternative convergence criteria, and develop methods to better specify scope constraints. The success of autoreason on this single task suggests that proper experimental design, rather than sophisticated prompting alone, may be key to unlocking LLM self-improvement capabilities.