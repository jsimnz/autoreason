## Problems Identified

### Overstated or Insufficiently Hedged Claims

1. **Abstract**: "game-theoretic analysis suggests near-transitive preferences within the LLM-judge evaluation framework" — The 1.1% Condorcet cycle rate across 91 passes is reported as evidence of near-transitivity, but 91 passes with 3-way comparisons yields a small number of possible cycles. The statistical basis for calling this "near-transitive" is never formalized. What cycle rate would falsify this claim?

2. **Abstract**: "Monte Carlo analysis suggests 80% convergence with consistent quality (though n=5 limits precision)" — Reporting a point estimate of 80% from n=5 is misleading even with the parenthetical caveat. The 95% confidence interval for a 4/5 binomial proportion is roughly [28%, 99%]. Calling this "80% convergence" gives false precision.

3. **Section 4.1**: "The judge panel acts as a filter: revisions that score lower than the incumbent are rejected, while baselines lack this selective mechanism." This is stated as an explanation for why autoreason improves with iteration, but it's equally consistent with the method simply having more compute (6× per pass, more total passes). The filtering explanation is never disentangled from the compute advantage.

### Unaddressed Reviewer Concerns

4. **No human evaluation whatsoever.** The Limitations section acknowledges this extensively, but the paper still makes claims like "ranked first or second in every 7-judge blind comparison" (Abstract) and "wins 3/5 outright" (Abstract) without qualification in those specific sentences. The hedging is inconsistent — sometimes present, sometimes absent.

5. **Single model family.** All core experiments use Anthropic models. The paper acknowledges this in Limitations but the title and framing ("Autoresearch for Subjective Domains") imply generality that hasn't been demonstrated.

6. **No ablation of core design choices.** Temperature values (0.8/0.3) are acknowledged as not formally ablated (Section 2), but neither are: the number of candidates (3), the Borda scoring scheme (3/2/1), the choice of k=2, or the use of 3 in-loop judges. The paper defends k=2 informally but doesn't test alternatives systematically.

### Structural and Methodological Issues

7. **Confounded constrained-task comparison (Section 5.2).** The paper acknowledges "The constrained task differs from Task 2 in both scope constraints and content" but then still draws the conclusion that scope is the root cause. The eight remedy experiments that failed were all on Task 2; the one that succeeded was a different task entirely. This is a confound the paper cannot resolve, yet the Discussion and Conclusion treat scope as the identified root cause.

8. **Inconsistent baseline treatment.** Autoreason ran to convergence (variable passes) while baselines ran exactly 15 passes. Table~\ref{tab:multi} compares at 15 passes, but autoreason's convergence points vary (9–28). For tasks where autoreason converges before 15 passes, what happens in the remaining passes? The comparison is not at equal compute or equal passes.

9. **The PSRO analogy (Section 2.1)** is acknowledged as "loose" but still takes up a full paragraph and appears in Related Work. If it's loose enough to require a disclaimer, it's unclear what analytical value it adds.

10. **Reference quality.** Reference [9] ("LLM Council, 2025") lacks authors, venue, or any identifying information. References [2] and [3] have 2026 dates explained by a footnote, but a paper citing future-dated preprints raises credibility concerns regardless of the explanation.

### Prose Issues

11. **Section 1, paragraph 2**: "We present autoreason, extending Karpathy's autoresearch to subjective domains" — this framing overstates the connection. Autoresearch uses val_bpb as a fitness function for neural network training; autoreason is an iterative document refinement loop. The "extension" is metaphorical at best.

12. **Section 4.2** ("Qualitative Improvement") provides a single anecdotal example with no systematic analysis. The before/after description is vague ("quantified pain points," "competitive positioning against named tools") without showing actual text or measuring these properties.

13. **Section 6 (Writing This Paper)**: The self-referential experiment (running autoreason on the paper itself) creates an uncomfortable circularity. The paper's quality is partly a product of the method it evaluates, and the evaluation of that method is conducted by the same model family. This is acknowledged nowhere as a methodological concern.

### Statistical and Experimental Gaps

14. **No variance reporting on main results.** Tables 2 and 3 report single Borda scores with no confidence intervals or repeated trials (except the Monte Carlo on Task 1). The 7-judge panel scores have inherent variance that is never quantified.

15. **CoT judge results (Section 4.4)** are based on exactly two tasks. The claim "CoT reduces convergence 3× on Task 1 (1.5× on Task 2)" is presented as a finding but with n=1 per condition per task, these are anecdotes, not results.

16. **Table 7 (Remedy quality)** uses a /49 Borda scale without explanation — presumably 7 judges × 7 candidates × 1 point each, but this scoring differs from the /35 used elsewhere and is never explained.