

## Problems Identified

### Overstated or Insufficiently Qualified Claims

1. **Abstract**: "autoreason ranked first or second in every 7-judge blind comparison, winning 3/5 outright" — This is stated as a headline result but applies only to Sonnet 4 on 5 tasks. The abstract then immediately notes the method *fails* with a stronger model on open-ended tasks. The juxtaposition buries the failure and leads with the success, creating an misleading first impression.

2. **Abstract**: "game-theoretic analysis suggests near-transitive preferences" — The near-transitivity is measured by same-model judges evaluating same-model outputs. The paper acknowledges this circularity in Section 5.2 but the abstract presents it without qualification.

3. **Section 4.2 (Qualitative Improvement)**: "The adversarial process replaced vague aspirational claims with internally consistent specifics." This is presented as a general characterization of what the process does, but it's based on a single qualitative example (Task 1). The hedge at the end ("These details are LLM-generated...") partially addresses this but the framing sentence is still causal and general.

4. **Section 7 Discussion**: "The broader observation: the obstacle to iterative LLM self-improvement may not be model capability but the interaction between evaluation methodology and task specification." This is presented as a key takeaway but is supported by exactly one constrained task with one model. The paper hedges elsewhere but the conclusion section elevates this to a "broader observation."

### Methodological Issues Still Unresolved

5. **No human evaluation**: The limitations section acknowledges this extensively, but the paper still makes quality claims throughout (e.g., "autoreason's value emerges from iteration," "Post-convergence passes are noise," winning/losing language). Every comparative result is LLM-judged, and the paper never quantifies or bounds the gap between LLM preference and human preference. A reviewer who asked for human evaluation would find this unaddressed.

6. **Confounded constrained-task comparison (Section 5.2)**: The paper acknowledges "The constrained task differs from Task 2 in both scope constraints and content" but then proceeds to draw conclusions about scope being the root cause. This is a confound the paper identifies but does not resolve. The sentence "so this comparison isolates the effect of bounded scope only in combination with a task change" is self-contradictory — it explicitly says it *doesn't* isolate the effect.

7. **Single runs for remedy experiments**: Section 7 notes "Scaling remedy experiments each ran once" but Tables 6, 7, 8, and 9 present these single-run results as definitive evidence. The Round 1 and Round 2 remedy conclusions ("Only the constrained task converges") are drawn from n=1 per condition.

8. **Temperature choices not ablated**: Section 2 acknowledges "these values were chosen based on preliminary runs and not formally ablated." This is fine as a disclosure, but temperature could plausibly explain some of the convergence behavior differences, especially the CoT judge results, and no reviewer concern about this is addressed beyond the disclosure.

### Structural and Presentation Issues

9. **Section 3 (Experiments)** mixes experimental setup with method description. The baselines are described here but the method is in Section 2. The compute budget paragraph belongs in the method or a dedicated subsection, not embedded in the experiment description.

10. **Table 1 vs. Table 2 comparison is awkward**: Table 1 shows single-pass results where autoreason uses 5 calls vs. 1 call for baselines. Table 2 shows iterative results at 15 passes. But autoreason at 15 passes uses ~90 calls while baselines use ~15. The compute budget paragraph addresses this but the tables don't make the cost difference visible, and the "max 35" scoring makes results look directly comparable when the compute is 6× different.

11. **The paper-writing experiment (Section 6)** uses a different model (Opus) than all other experiments (Sonnet 4), making it non-comparable. It's presented as evidence for the method but serves more as an anecdote. The ground-truth critic finding is interesting but disconnected from the main experimental narrative.

12. **Figure references are dense and sometimes redundant**: Section 4.1 references Figure 2, Figure 3, and Figure 4 within a few paragraphs. Figure 3 (summary) largely duplicates Table 2's information in visual form.

### Missing or Incomplete Responses to Likely Reviewer Concerns

13. **No statistical significance testing**: With 7 judges producing Borda scores, the differences between methods (e.g., 27 vs. 25 in Table 2, Task 4) could easily be within noise. No confidence intervals, no significance tests, no bootstrap analysis. The Monte Carlo section (n=5) is acknowledged as limited but no power analysis is offered.

14. **Borda count choice not justified**: Why Borda over other aggregation methods (Kemeny-Young, Copeland, majority rule)? Arrow's impossibility theorem is cited in the bibliography but never discussed in the text. The choice of 3/2/1 scoring is presented without alternatives or sensitivity analysis.

15. **The PSRO connection is vague and acknowledged as such** ("loosely analogous rather than a direct equivalence") but it's still in the formal framing section and the related work. If it's only loosely analogous, its presence in the formal framing section is misleading about the theoretical grounding of the method.

### Prose Issues

16. **Section 1**: "LLMs exhibit systematic failures when iterating on subjective work: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse." This is a list of six failure modes with only two citations supporting any of them. Sycophancy, overcriticism, overcompromise, and authorship bias are not cited.

17. **Section 2**: "Every role is a fresh, isolated agent with no shared context" is stated twice — once in the method description and once in the paragraph after the formal framing. 

18. **Section 4.3**: "Post-convergence passes are noise" is stated as fact based on a single 7-judge comparison (pass 15 vs. pass 25 on Task 1). This is one comparison on one task.

19. **Bibliography**: Reference [9] (LLM Council) is attributed to "A. Karpathy" but LLM Council is not a Karpathy work. Reference [11] (Arrow) has a footnote about 2026 dates that applies to references [2] and [3], not [11] — the footnote is attached to the wrong reference.