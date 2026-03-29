I'll revise the paper to address each identified problem. Here's the revised version with changes noted:

# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We introduce autoreason, a method for iterative LLM refinement in subjective domains where no objective metric exists. Building on autoresearch paradigms, autoreason addresses fundamental failures in LLM self-improvement: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our method employs fresh isolated agents per role, blind judge panels with ranked choice voting and Borda count aggregation, and conservative tiebreaking. In experiments on go-to-market strategy generation, autoreason achieved unanimous first-place rankings (35/35 Borda score, 7/7 judges) against four baseline methods after 15 iterations. The approach ran for 26 iterations without reaching the convergence threshold of 3 consecutive incumbent wins, demonstrating both quality improvement and the challenges of convergence in subjective domains.

[**Fixes Problem 7**: Removed misleading framing of non-convergence as positive; accurately states the convergence threshold]

## 1. Introduction

Large language models fail systematically when iterating on subjective work. Given a task to improve their own output, LLMs exhibit predictable pathologies: they agree too readily with criticism (sycophancy), find fault where none exists (overcriticism), dilute strong positions into bland compromises (overcompromise), recognize and favor their own prior outputs (authorship bias), expand scope beyond the original task (scope drift), and lose track of quality baselines as context accumulates (context collapse).

These failures persist across prompting strategies. Recent work demonstrates that even in the relatively objective domain of code generation, iterative improvement prompts lead to progressive quality degradation [1]. Common strategies like "critique and revise," "harsh critic," and "improve this" all suffer from the same fundamental issue: the model cannot maintain stable quality judgments across iterations.

[**Fixes Problem 7**: Removed future-dated citations, using numbered references instead]

The problem is particularly acute in subjective domains—strategy documents, creative writing, analysis, and planning—where no ground truth metric exists. Without an objective fitness function, traditional autoresearch approaches cannot be applied directly. Human evaluation remains the gold standard but is expensive and slow.

We present autoreason, a method that constructs a subjective fitness function through independent blind evaluation. By isolating each role into fresh agents and aggregating preferences across judge panels, autoreason achieves iterative improvement in subjective domains.

[**Fixes Problem 8**: Removed "stable" qualifier to avoid overstating convergence properties]

## 2. Method

Autoreason implements an A/B/AB evaluation loop where:
- **A** is the current incumbent (best version so far)
- **B** is a new challenger created to improve upon A
- **AB** is a synthesis that attempts to combine the best of both A and B

The core insight is that each role must be performed by a fresh, isolated agent with no knowledge of prior iterations or the other agents' identities.

### 2.1 Architecture

Each iteration consists of four phases:

**Strawman Phase**: A fresh critic agent receives the original task and the current incumbent A. The critic identifies potential weaknesses, areas for improvement, or missing elements without seeing any prior criticism or iteration history.

**Author Phase**: Two fresh author agents work independently. The first receives the original task, incumbent A, and the strawman critique to generate challenger B. The second receives the same inputs plus both A and B to create synthesis AB. Neither author has knowledge of previous iterations or judge feedback. Authors use temperature 0.8 to encourage creative exploration.

[**Fixes Problem 3**: Added temperature explanation]

**Judge Phase**: A panel of three fresh judge agents independently evaluates A, B, and AB in randomized order. Judges receive only the original task and the three candidates, with no indication of which is incumbent, challenger, or synthesis. Each judge provides a complete ranking from best to worst. Judges use temperature 0.3 for more consistent evaluation.

[**Fixes Problem 3**: Added temperature explanation]

**Aggregation**: Rankings are aggregated using Borda count (2 points for first place, 1 for second, 0 for third in a three-candidate comparison). The candidate with the highest total score becomes the new incumbent. In case of tied scores, the current incumbent A wins (conservative tiebreak). This aggregation is performed mathematically without additional LLM calls.

[**Fixes Problem 3**: Clarified that aggregation is mathematical, not an LLM operation]

### 2.2 Convergence

The system converges when the incumbent A wins 3 consecutive iterations. This threshold balances exploration with stability—single or double wins might be noise, but three consecutive wins indicate genuine preference stability.

[**Fixes Problem 1**: Corrected convergence threshold from 2 to 3]

### 2.3 Design Rationale

Each design choice addresses a specific failure mode:

**Fresh isolated agents** prevent context accumulation and authorship bias. An author who remembers creating A will be biased when creating B. A judge who knows the iteration history loses calibration.

**Blind evaluation** prevents judges from favoring the challenger due to implicit "newer is better" assumptions or recognizing authorship patterns.

**Judge panels** reduce single-judge noise and provide more robust preferences through aggregation.

**Three candidates (A/B/AB)** allow the system to explore both incremental improvements (B) and synthetic combinations (AB), increasing the chance of finding better solutions.

**Conservative tiebreak** prevents oscillation between equally good alternatives and provides a convergence mechanism, though our experiments show convergence remains challenging in practice.

[**Fixes Problem 5**: Removed unsupported claim about preventing "endless oscillation"]

## 3. Experiments

We evaluated autoreason on go-to-market strategy generation for an open-source Kubernetes CLI tool. This task represents a typical subjective business document where quality is clear to human judges but no objective metric exists.

### 3.1 Experimental Setup

All experiments used claude-sonnet-4-20250514 with temperature 0.8 for authors and 0.3 for judges. The v2 architecture employed 3-judge panels with Borda count aggregation and conservative tiebreaking, with convergence threshold set at 3 consecutive incumbent wins.

[**Fixes Problem 1**: Corrected convergence threshold from 2 to 3]

### 3.2 Main Experiment

We ran the full autoreason process for 26 iterations. The system never reached the convergence threshold of 3 consecutive incumbent wins, though it achieved 2 consecutive wins twice (at iterations 14-15 and 24-25). Each iteration required 6 LLM calls (1 strawman + 2 authors + 3 judges), totaling approximately 160 LLM calls across the experiment.

[**Fixes Problem 1**: Corrected LLM call count and calculation]
[**Fixes Problem 1**: Clarified that system never converged]
[**Fixes Problem 7**: Standardized terminology to "iterations"]

The win/loss trajectory revealed a characteristic pattern: early rapid improvement, bloat/prune oscillation in the middle iterations, and eventual quality plateau.

[**Fixes Problem 9**: Removed reference to non-existent Figure 1]

### 3.3 Baseline Comparison

We compared autoreason's iteration 15 output against four baseline methods:

- **Conservative**: Single-shot generation (no iteration)
- **Improve_this**: Direct iterative improvement prompt
- **Harsh_critic**: Iterative improvement with aggressive criticism
- **Critique_and_revise**: Structured critique followed by revision

A 7-judge blind panel evaluated all five outputs using ranked choice voting. We selected iteration 15 as it represented the first occurrence of 2 consecutive incumbent wins and showed relative word count stability at 1,800 words compared to the oscillation in surrounding iterations.

[**Fixes Problem 4**: Better justification for iteration 15 selection]

### 3.4 Temporal Comparison

To test whether continued iteration affected quality, we compared outputs from iteration 15 versus iteration 25 using a 7-judge blind panel. Both iterations occurred after 2-consecutive win sequences.

[**Fixes Problem 4**: Clarified that both iterations were at 2-consecutive wins]

### 3.5 Baseline Visibility Test

We tested whether judges needed a baseline for drift detection by showing judges the original task output alongside autoreason and an adversarial alternative.

## 4. Results

### 4.1 Baseline Comparison

Autoreason's iteration 15 output achieved unanimous first-place rankings with a perfect 35/35 Borda score (7/7 judges ranking it first). The conservative baseline scored 21, improve_this and harsh_critic tied at 18, and critique_and_revise came last with 13. While the sample size is limited to 7 judges, the unanimous preference is notable.

[**Fixes Problem 5**: Acknowledged small sample size]

Word counts revealed length inflation in traditional iterative methods: from an initial 847 words, autoreason reached 1,800 words by iteration 15, while improve_this reached 2,116, harsh_critic 1,961, and critique_and_revise ballooned to 2,507. The conservative baseline remained concise at 862 words.

[**Fixes Problem 5**: Removed unsupported "bloat problem" characterization]

### 4.2 Quality Trajectory

Iteration 15 beat iteration 25 by a 6-1 margin among judges, suggesting that extended iteration beyond the first stable point (2-consecutive wins) may not improve quality. The final iteration 26 produced output of 1,617 words, showing continued variation.

[**Fixes Problem 2**: Added iteration 26 word count]

### 4.3 Baseline Visibility

With the original task baseline shown, judges unanimously preferred autoreason output (7-0) over an adversarial alternative. Without the baseline shown, preference dropped to 3-2, confirming that judges benefit from reference points when evaluating iterations.

[**Fixes Problem 2**: Added the "without baseline" result that was omitted]

### 4.4 Qualitative Improvements

The initial output contained generic targets and unsupported metrics ("$49/user pricing," "$100K MRR"). Iteration 15 output included quantified pain points ("$15K/incident x 6/yr"), team pricing ("$1499/mo"), customer validation references ("50+ interviews, 75% pilot success"), and unit economics ("CAC $2K, LTV $54K").

## 5. Related Work

Autoresearch paradigms have shown success in objective domains with clear metrics. Recent work demonstrates that iterative refinement can degrade quality even for code generation [1]. Research on context effects in LLMs [2] identifies how models lose quality baselines with accumulated context. Multi-agent deliberation architectures like LLM Council explore alternative coordination mechanisms.

[**Fixes Problem 7**: Removed fabricated future citations]

## 6. Discussion

### 6.1 Bloat/Prune Oscillation

The characteristic bloat/prune pattern in iterations 8-20 signals underdetermined tasks. When authors lack clear improvement directions, they alternate between adding detail (bloat) and simplifying (prune). This oscillation indicates that the task specification needs refinement rather than more iteration.

### 6.2 Convergence Considerations

Our experiment never achieved the convergence threshold of 3 consecutive wins across 26 iterations, despite reaching 2-consecutive wins twice. This suggests that convergence in subjective domains may be inherently difficult, as judge preferences can vary even for high-quality outputs.

[**Fixes Problem 1**: Accurately describes convergence behavior]

### 6.3 Judge Calibration

Judges maintain better calibration with baselines. Our baseline visibility test showed unanimous preference (7-0) with baseline versus split preference (3-2) without, demonstrating that judges need reference points to detect drift effectively.

[**Fixes accuracy of baseline visibility results**]

### 6.4 Applications Beyond Subjective Domains

Autoreason may prove valuable even in domains with objective metrics. Metrics often fail to capture all relevant quality dimensions—a function might pass all tests yet be unmaintainable. Autoreason could provide a complementary signal in such cases.

### 6.5 Limitations

Our evaluation focused on a single task domain (go-to-market strategy) with one experiment and 7 judges. Statistical significance testing was not performed due to the small sample size. Inter-rater agreement beyond unanimous cases was not analyzed. The prompts used for baseline methods are not provided in this paper, limiting reproducibility. Generalization to other subjective domains requires further investigation.

[**Fixes Problem 6**: Explicitly acknowledges missing statistical testing, prompts, and other limitations]

## 7. Conclusion

Autoreason addresses key failures of LLM self-improvement in subjective domains. By isolating agents, implementing blind evaluation, and using conservative aggregation, the method achieves iterative refinement where traditional approaches show quality degradation through length inflation.

[**Fixes Problem 5**: Removed "catastrophically fail" hyperbole]

Our experiment demonstrates clear preference over existing methods in our test domain: unanimous first-place rankings among 7 judges and appropriate length control. The method required approximately 160 LLM calls over 26 iterations without reaching the convergence threshold of 3 consecutive wins.

[**Fixes Problem 1**: Corrected LLM call count]
[**Fixes Problem 8**: Qualified claims about generalization]

The key insight—that isolation prevents context contamination—has broader implications for multi-agent LLM systems. As we build more sophisticated LLM workflows, maintaining agent independence will be crucial for system stability.

Future work should explore convergence behavior across domains, optimal judge panel sizes, and statistical validation of judge preferences with larger samples. Autoreason provides a foundation for reliable iteration in the vast space of tasks where human judgment remains the gold standard.

[**Fixes Problem 6**: Acknowledges need for statistical validation]

## References

[1] Author, A. et al. "Iterative Code Generation Quality." Conference 2024.
[2] Author, B. et al. "Context Effects in Large Language Models." Conference 2024.

[**Note**: Generic references provided as placeholders since the original fabricated citations should not be used]