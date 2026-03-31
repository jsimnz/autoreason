# Review: Sonnet 4.6

## Summary

This paper introduces "autoreason," an iterative LLM refinement method for subjective domains (e.g., strategy documents, policies) where no objective metric exists. Each iteration generates three candidates—the incumbent (A), an adversarial revision (B), and a synthesis (AB)—evaluated by a blind judge panel using Borda count aggregation. The paper reports results on five business-writing tasks using Claude Sonnet-4, showing autoreason ranks 1st or 2nd in blind comparisons after iteration. A secondary finding is that with a stronger model (Sonnet 4.6), the method fails on open-ended tasks due to unbounded scope, but succeeds on a scope-constrained task. The paper also applies the method to write itself and discusses chain-of-thought judging, convergence properties, and game-theoretic validation.

---

## Strengths (be specific, cite sections)

**1. Honest reporting of failures (Section 5, Tables 3–6).** The authors do not hide the Sonnet 4.6 failure. They report autoreason finishing last (Borda 7/35, Table 3), run eight remedy experiments, and trace the root cause to task scope rather than evaluation design. This kind of negative result reporting is genuinely valuable and relatively rare.

**2. Practical design choices are well-motivated (Section 2).** The use of fresh isolated agents, randomized labels, conservative tiebreaking, and Borda count aggregation are each individually justified with reference to known LLM failure modes (sycophancy, verbosity bias, authorship bias). The connection to Condorcet jury theorem is appropriate, and the caveat about shared systematic biases bounding effective independence is honest.

**3. Chain-of-thought judging ablation (Section 4.4, Table 4).** The finding that adding "think step by step" to judge prompts reduces convergence passes by ~3× is a clean, actionable result with a plausible mechanism (forcing articulation of specific strengths prevents verbosity bias). This is the most reproducible and practically useful finding in the paper.

**4. The scope hypothesis is well-supported within its experiments (Section 5.2, Tables 6–7).** The contrast between unconstrained (no convergence, last place) and constrained (10-pass convergence, first place) with the same model is striking. The word-count data (480–694 vs. 1895–2700) provides a concrete mechanistic explanation. The inversion of the baseline ranking (critique-and-revise drops from 1st to last) is a strong falsifiable prediction that was confirmed.

**5. Self-application experiment (Section 6).** Using autoreason to write the paper itself, with ground-truth context for fact-checking, is a creative demonstration. The hallucination-catching result (4 hallucinations without ground truth, 0 with) is a concrete, memorable illustration of the critic's role.

---

## Weaknesses (be specific, cite sections)

**1. No human evaluation anywhere in the paper.** All quality assessments rely on LLM judges evaluating LLM outputs. The paper's central claim—that autoreason produces better documents—is entirely circular: the same model family (Anthropic) generates and evaluates all content. Section 7 acknowledges this but treats it as a limitation rather than a fundamental validity threat. The Borda scores in Tables 2, 5, 7 are meaningless if LLM judges systematically prefer certain artifacts (e.g., longer, more detailed, more confident-sounding text) regardless of actual quality. **Impact:** The core empirical claims cannot be trusted without at least one human evaluation study. **Fix:** Even a small crowdsourced study (e.g., 20 human raters on Task 1 comparing autoreason vs. critique-and-revise) would substantially strengthen the paper.

**2. Single-task generalization for the key positive result (Section 5.2).** The constrained-task finding—the paper's resolution of the Sonnet 4.6 failure—is based on a single task (500-word startup pitch). Section 7 acknowledges this, but the abstract and conclusion present it as a general solution. Table 7 shows autoreason winning with Borda 30/35, but this is one data point. The five original tasks (Section 3) were not re-run with scope constraints and Sonnet 4.6. **Impact:** The claim that "scope constraints restore convergence and quality" is not established beyond a single instance. **Fix:** Run the constrained-task experiment on at least 3 of the original 5 tasks with explicit word/section constraints.

**3. Baseline comparisons are not equalized for compute (Sections 4.1–4.2, Tables 1–2).** Autoreason uses 5 LLM calls per pass and runs to convergence (9–28 passes), while baselines run for a fixed 15 passes with 1–2 calls each. The comparison in Table 2 is autoreason at convergence vs. baselines at 15 passes, but the compute budgets are wildly different. Autoreason on Task 1 ran 26 passes × 5 calls = 130 calls; critique-and-revise ran 15 × 2 = 30 calls. **Impact:** The performance advantage may simply reflect more compute, not architectural superiority. **Fix:** Report total LLM calls per method and include a compute-matched comparison (e.g., run critique-and-revise for 65 passes to match autoreason's call budget).

**4. Monte Carlo analysis is underpowered (Section 4.5).** Five runs is not sufficient to claim "80% convergence" with any statistical confidence. The confidence interval on a binomial proportion with n=5, k=4 is approximately [28%, 99%] at 95% confidence. The claim "Monte Carlo analysis confirms 80% convergence with consistent quality" in the abstract overstates what 5 runs can establish. **Impact:** The robustness claim is not credible. **Fix:** Run at least 20–30 independent trials, or report the confidence interval honestly.

**5. The "game-theoretic validation" is superficial (Section 4.5).** The claim of "fully transitive preferences" based on 1.1% Condorcet cycle rate across 91 passes is presented as validating the PSRO framing, but 91 passes across 5 tasks is a small sample. More importantly, the Condorcet cycle rate measures transitivity of judge preferences within a run, not the correctness of those preferences. The connection to PSRO (Section 2) is asserted but never formally developed—there is no empirical game matrix, no Nash equilibrium computation, and no actual PSRO algorithm being run. **Impact:** The game-theoretic framing is decorative rather than substantive. **Fix:** Either develop the PSRO connection formally (show the empirical game matrix, compute Nash strategies) or remove the PSRO framing and replace with a simpler claim about preference transitivity.

**6. Qualitative improvement claims lack grounding (Section 4.2).** The comparison between initial and converged Task 1 outputs (generic playbook → specific metrics) is presented as evidence of quality improvement, but these specific numbers ($15K/incident, $1,499/mo, CAC $2K, LTV $54K) were generated by the LLM. There is no verification that these figures are realistic or correct. The paper presents LLM-generated specificity as genuine improvement without any external validation. **Impact:** The qualitative improvement section may be illustrating confident hallucination rather than quality improvement. **Fix:** Note explicitly that the specificity is LLM-generated and unverified, or use a task where ground truth can be checked.

**7. Experimental design confounds model and task (Section 5).** The paper uses Sonnet 4 for the main experiments (Section 3) and Sonnet 4.6 for the scaling experiments (Section 5), but these are different model versions with different capabilities. The failure with 4.6 is attributed to "scope," but it could also reflect differences in how 4.6 responds to the synthesis prompt, judge prompt, or critic prompt. No ablation isolates which component changed behavior. **Impact:** The scope hypothesis, while plausible, is not the only explanation for the 4.6 failure. **Fix:** Run the original 5 tasks with Sonnet 4.6 (unconstrained) to confirm the failure generalizes, and test whether the same scope constraints work on tasks other than the startup pitch.

**8. References contain apparent errors (Bibliography).** SlopCodeBench is cited as "arXiv:2603.24755, 2026"—a 2026 date and a March 2026 arXiv ID are suspicious for a paper submitted to a current venue. ACE is cited as "ICLR 2026." LLM Council is cited as "A. Karpathy, 2025" with no URL or arXiv ID. These suggest the bibliography was partially AI-generated or contains placeholder citations. **Impact:** Undermines credibility; a reviewer cannot verify these claims. **Fix:** Verify all citations against actual published sources.

---

## Questions for Authors

1. **On human evaluation:** Have you conducted any human evaluation of the outputs? Even informal feedback from domain experts (e.g., showing the Task 1 go-to-market strategy to a startup founder) would substantially strengthen the quality claims. If not, why not?

2. **On compute fairness:** What is the total LLM call count for autoreason vs. each baseline in Tables 1–2? If you ran critique-and-revise for the same number of total calls as autoreason, does it still lose?

3. **On the scope hypothesis:** You claim scope is the root cause of the Sonnet 4.6 failure. But did you test whether adding explicit scope constraints to the original 5 tasks (with Sonnet 4) changes the results? If scope constraints always help, why not recommend them universally?

4. **On judge reliability:** The paper uses 3 judges for the main experiments and 7 judges for the final blind comparisons. Why the inconsistency? Have you measured inter-judge agreement (e.g., Krippendorff's alpha) to validate that the panel is producing reliable rankings?

5. **On the self-referential experiment (Section 6):** The paper was written using autoreason. Does this mean the experimental results reported in the paper were also revised by the method? If so, how do you ensure the reported numbers were not altered during the autoreason passes?

6. **On the SlopCodeBench and ACE citations:** Can you provide verified arXiv IDs or DOIs for these references? The 2026 dates are unusual.

---

## Minor Issues

1. **Abstract overstates Monte Carlo result:** "Monte Carlo analysis confirms 80% convergence" from n=5 runs should be "suggests" or include a confidence interval.

2. **Figure 1 self-reference:** The caption reads "The autoreason loop (Figure 1)" inside Figure 1's own caption—this is a self-referential citation that should be removed.

3. **Table 4 (CoT):** The "Decomposed (3 specialists)" row has "---" for Task 2 with no explanation. Was this experiment not run? Why?

4. **Section 4.3, Figure 3:** "At pass 15, A had won twice consecutively. Eleven more passes followed." This implies the convergence criterion was met at pass 15 but the experiment continued—why? This should be explained more clearly.

5. **Inconsistent judge counts:** Main experiments use 3 judges; final blind comparisons use 7 judges (mentioned in Section 3 but not explained). The rationale for 7 in blind comparisons vs. 3 in the loop should be stated.

6. **"shl0ms" as author name:** This appears to be a pseudonym. Top venues require real author names for the review process; this should be clarified.

7. **Temperature settings:** Authors use temp=0.8, judges use temp=0.3. The rationale for these specific values is not given. Sensitivity to temperature is not tested.

8. **Figure 7 (word count):** The caption says "Autoreason (solid) grows controllably; baselines stagnate or bloat" but the figure is not included in the LaTeX source (only referenced). The claim that autoreason "grows controllably" while baselines "bloat" seems to contradict the Sonnet 4.6 finding where autoreason drifted to 1895–2700 words.

---

## Overall Assessment

**Recommendation: Weak Reject**

The paper addresses a real and important problem (iterative LLM refinement for subjective tasks), proposes a reasonable method with well-motivated design choices, and reports failures honestly. The CoT judging finding and the scope hypothesis are genuinely interesting. However, the paper has critical validity problems that prevent acceptance at a top venue in its current form:

The **most important issue** is the complete absence of human evaluation. Every quality claim in the paper rests on LLM judges evaluating LLM outputs from the same model family. This is not a minor limitation—it is a fundamental methodological problem that makes it impossible to know whether autoreason actually produces better documents or merely produces documents that Anthropic models prefer. A paper claiming to solve iterative improvement for subjective domains must demonstrate improvement on at least one task where "better" can be verified by humans or by an external standard.

Secondary issues—the underpowered Monte Carlo (n=5), the single constrained-task result, the compute-imbalanced comparisons, and the suspicious bibliography entries—collectively suggest the paper needs substantially more experimental work before it is ready for a top venue. The writing is clear and the ideas are interesting; the experimental foundation needs to be rebuilt on more solid ground.
