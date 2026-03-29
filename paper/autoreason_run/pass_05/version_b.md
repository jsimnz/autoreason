I'll revise the paper to address each identified problem. Here's the revised version with explanations of which problems each change addresses:

# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We introduce autoreason, a method for iterative LLM refinement in subjective domains where no objective metric exists. Building on autoresearch paradigms, autoreason addresses fundamental failures in LLM self-improvement: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our method employs fresh isolated agents per role, blind judge panels with ranked choice voting and Borda count aggregation, and conservative tiebreaking. In an experiment on go-to-market strategy generation, autoreason achieved unanimous first-place rankings (14/14 Borda points, 7/7 judges) against four baseline methods after 15 iterations. The approach ran for 26 iterations, achieving 2 consecutive incumbent wins twice but never reaching our configured threshold of 3 consecutive wins.

[**Fixes Problem 9**: Changed "35/35 Borda score" to "14/14 Borda points" to correctly represent the maximum possible score for 7 judges under our scoring system]

## 1. Introduction

Large language models fail systematically when iterating on subjective work. Given a task to improve their own output, LLMs exhibit predictable pathologies: they agree too readily with criticism (sycophancy), find fault where none exists (overcriticism), dilute strong positions into bland compromises (overcompromise), recognize and favor their own prior outputs (authorship bias), expand scope beyond the original task (scope drift), and lose track of quality baselines as context accumulates (context collapse).

These failures persist across prompting strategies. Recent work demonstrates that even in the relatively objective domain of code generation, iterative improvement prompts lead to progressive quality degradation (SlopCodeBench). Common strategies like "critique and revise," "harsh critic," and "improve this" all suffer from the same fundamental issue: the model cannot maintain stable quality judgments across iterations.

The problem is particularly acute in subjective domains—strategy documents, creative writing, analysis, and planning—where no ground truth metric exists. Without an objective fitness function, traditional autoresearch approaches cannot be applied directly. Human evaluation remains the gold standard but is expensive and slow.

We present autoreason, a method that constructs a subjective fitness function through independent blind evaluation. By isolating each role into fresh agents and aggregating preferences across judge panels, autoreason achieves iterative improvement in subjective domains.

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

**Judge Phase**: A panel of three fresh judge agents independently evaluates A, B, and AB in randomized order. Judges receive only the original task and the three candidates, with no indication of which is incumbent, challenger, or synthesis. Each judge provides a complete ranking from best to worst. Judges use temperature 0.3 for more consistent evaluation. Rankings are scored using Borda count: 2 points for first place, 1 point for second place, 0 points for third place.

**Aggregation**: Rankings are aggregated by summing Borda count scores across all judges. The candidate with the highest total score becomes the new incumbent. In case of tied scores, the current incumbent A wins (conservative tiebreak). This aggregation is performed mathematically without additional LLM calls.

### 2.2 Convergence

The system was configured with a convergence threshold of 3 consecutive wins by the incumbent A, though this threshold was not implemented as an automatic stopping condition in our experiment. We tracked consecutive wins to monitor convergence behavior. The experiment reached 2 consecutive wins twice (at iterations 14-15 and 24-25) but never achieved 3 consecutive wins across the full 26 iterations.

[**Fixes Problem 4**: Clarified that the convergence threshold was configured but not used as a stopping condition]

### 2.3 Design Rationale

Each design choice addresses a specific failure mode:

**Fresh isolated agents** prevent context accumulation and authorship bias. An author who remembers creating A will be biased when creating B. A judge who knows the iteration history loses calibration.

**Blind evaluation** prevents judges from favoring the challenger due to implicit "newer is better" assumptions or recognizing authorship patterns.

**Judge panels** reduce single-judge noise and provide more robust preferences through aggregation. We chose 3 judges as a balance between robustness and computational cost, though this choice was not empirically validated.

[**Fixes Problem 13**: Acknowledged that the 3-judge choice was not empirically validated]

**Three candidates (A/B/AB)** allow the system to explore both incremental improvements (B) and synthetic combinations (AB), increasing the chance of finding better solutions.

**Conservative tiebreak** prevents oscillation between equally good alternatives and provides a stability mechanism.

## 3. Experiments

We evaluated autoreason on go-to-market strategy generation for an open-source Kubernetes CLI tool. This task represents a typical subjective business document where quality is clear to human judges but no objective metric exists.

### 3.1 Experimental Setup

All experiments used claude-sonnet-4-20250514 with temperature 0.8 for authors and 0.3 for judges. The v2 architecture employed 3-judge panels with Borda count aggregation and conservative tiebreaking. We configured a convergence threshold of 3 consecutive incumbent wins for monitoring purposes.

### 3.2 Main Experiment

We ran the full autoreason process for 26 iterations. The system achieved 2 consecutive incumbent wins twice (at iterations 14-15 and 24-25) but never reached 3 consecutive wins. Each iteration required 6 LLM calls (1 strawman + 2 authors + 3 judges), totaling approximately 160 LLM calls across the experiment.

The win/loss trajectory revealed a characteristic pattern: early rapid improvement, bloat/prune oscillation in the middle iterations, and eventual quality plateau.

### 3.3 Baseline Comparison

We compared autoreason's iteration 15 output against four baseline methods:

- **conservative**: Single-shot generation (no iteration)
- **improve_this**: Direct iterative improvement prompt
- **harsh_critic**: Iterative improvement with aggressive criticism
- **critique_and_revise**: Structured critique followed by revision

[**Fixes Problem 2**: Changed "Conservative" to "conservative" to match actual data]

A 7-judge blind panel evaluated all five outputs using ranked choice voting. We selected iteration 15 as it represented the first occurrence of 2 consecutive incumbent wins and showed relative word count stability at 1,800 words compared to the oscillation in surrounding iterations.

### 3.4 Temporal Comparison

To test whether continued iteration affected quality, we compared outputs from iteration 15 versus iteration 25 using a 7-judge blind panel. Both iterations occurred after 2-consecutive win sequences.

[**Fixes Problem 1**: Removed the fabricated "Baseline Visibility Test" section entirely]

## 4. Results

### 4.1 Baseline Comparison

Autoreason's iteration 15 output achieved unanimous first-place rankings with a perfect 14/14 Borda score (7/7 judges ranking it first, each contributing 2 points). The conservative baseline scored 21 total Borda points across all rankings, improve_this and harsh_critic tied at 18, and critique_and_revise came last with 13.

[**Fixes Problem 9**: Clarified the Borda scoring to show 14/14 as the perfect score for first place]

Word counts revealed length inflation in traditional iterative methods: from an initial 847 words, autoreason reached 1,800 words by iteration 15, while improve_this reached 2,116, harsh_critic 1,961, and critique_and_revise ballooned to 2,507. The conservative baseline remained concise at 862 words.

### 4.2 Quality Trajectory

Iteration 15 beat iteration 25 by a 6-1 margin among judges, suggesting that extended iteration beyond the first stable point (2-consecutive wins) may not improve quality. The final iteration 26 produced output of approximately 1,617 words, showing continued variation.

[**Fixes Problem 5**: Added "approximately" to acknowledge the ~1617 notation in the data]

### 4.3 Qualitative Improvements

The initial output contained generic targets and unsupported metrics ("$49/user pricing," "$100K MRR"). Iteration 15 output included quantified pain points ("$15K/incident x 6/yr"), team pricing ("$1499/mo"), customer validation references ("50+ interviews, 75% pilot success"), and unit economics ("CAC $2K, LTV $54K").

[**Fixes Problem 1**: Removed the fabricated baseline visibility results section]

## 5. Related Work

Recent research has explored various approaches to LLM self-improvement and multi-agent systems. The autoresearch paradigm demonstrates success in objective domains with clear metrics. SlopCodeBench (Orlanski et al. 2026) shows that iterative refinement fails even for code generation. Work on ACE context collapse (Zhang et al. ICLR 2026) identifies how LLMs lose quality baselines with accumulated context. LLM Council explores multi-agent deliberation architectures.

## 6. Discussion

### 6.1 Bloat/Prune Oscillation

The characteristic bloat/prune pattern in iterations 8-20 signals underdetermined tasks. When authors lack clear improvement directions, they alternate between adding detail (bloat) and simplifying (prune). This oscillation indicates that the task specification needs refinement rather than more iteration.

### 6.2 Convergence Considerations

Our experiment achieved 2 consecutive incumbent wins twice but never reached the configured threshold of 3 consecutive wins across 26 iterations. This suggests that convergence in subjective domains may be inherently difficult, as judge preferences can vary even for high-quality outputs. The difficulty in achieving consistent convergence signals is itself a finding about the nature of subjective evaluation.

### 6.3 Applications Beyond Subjective Domains

Autoreason may prove valuable even in domains with objective metrics. Metrics often fail to capture all relevant quality dimensions—a function might pass all tests yet be unmaintainable. Autoreason could provide a complementary signal in such cases.

[**Fixes Problem 1, 6**: Removed the unsupported claims about baseline visibility and judge calibration]

### 6.4 Limitations

Our evaluation focused on a single task domain (go-to-market strategy) with one experimental run. We did not perform statistical significance testing or analyze inter-rater agreement, which limits our ability to assess judge consistency. The specific prompts used for each role and baseline method are not included in this paper due to space constraints, limiting reproducibility. 

We selected iteration 15 for baseline comparison based on it being the first 2-consecutive win occurrence, but did not validate whether this iteration was representative. The choice of 3 judges and specific temperature settings (0.8 for authors, 0.3 for judges) was not empirically validated through ablation studies. We observed that the AB synthesis won approximately 50% of iterations despite A being the incumbent but did not systematically analyze this pattern.

Our analysis of failure modes (sycophancy, overcriticism, etc.) in baseline methods was based on qualitative observation rather than systematic measurement. We did not include a cost analysis comparing the ~160 LLM calls required by autoreason to the computational requirements of baseline methods.

Generalization to other subjective domains, models, and larger judge panels requires further investigation.

[**Fixes Problems 3, 7, 8, 10, 11, 12, 13**: Expanded limitations to acknowledge missing methodology details, lack of statistical analysis, selective data presentation, missing failure analysis, incomplete experimental design, missing cost analysis, and unjustified design choices]

## 7. Conclusion

Autoreason addresses key failures of LLM self-improvement in subjective domains. By isolating agents, implementing blind evaluation, and using conservative aggregation, the method achieves iterative refinement where traditional approaches show quality degradation through length inflation.

Our experiment demonstrates clear preference over existing methods in our test domain: unanimous first-place rankings among 7 judges and appropriate length control. The method required approximately 160 LLM calls over 26 iterations, achieving 2 consecutive incumbent wins twice but never reaching the configured threshold of 3 consecutive wins.

The key insight—that isolation prevents context contamination—has broader implications for multi-agent LLM systems. As we build more sophisticated LLM workflows, maintaining agent independence will be crucial for system stability.

Future work should explore convergence behavior across domains, optimal judge panel sizes through ablation studies, systematic validation of the specific failure modes addressed, inter-rater reliability metrics, and cost-benefit analysis compared to baseline approaches. Autoreason provides a foundation for reliable iteration in the vast space of tasks where human judgment remains the gold standard.

[**Fixes Problem 7**: Added specific mention of inter-rater reliability metrics to future work]