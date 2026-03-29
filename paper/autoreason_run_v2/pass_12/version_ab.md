# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We introduce autoreason, a method for iterative LLM refinement in subjective domains where no objective metric exists. Building on autoresearch paradigms, autoreason addresses common LLM self-improvement issues: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our method employs fresh isolated agents per role, blind judge panels with ranked choice voting and Borda count aggregation, and conservative tiebreaking. In a single experiment on go-to-market strategy generation, autoreason achieved the highest total Borda score (35 points) with all first-place rankings from 7 judges when compared against four baseline methods. The approach ran for 26 passes, achieving 2 consecutive incumbent wins at passes 14-15 and 24-25 before manual termination. We present this as an exploratory study of one approach to subjective iteration on a single task, not a validated general method.

## 1. Introduction

Large language models fail systematically when iterating on subjective work. Given a task to improve their own output, LLMs exhibit predictable pathologies: they agree too readily with criticism (sycophancy), find fault where none exists (overcriticism), dilute strong positions into bland compromises (overcompromise), recognize and favor their own prior outputs (authorship bias), expand scope beyond the original task (scope drift), and lose track of quality baselines as context accumulates (context collapse).

These failures persist across prompting strategies. Recent work demonstrates that even in the relatively objective domain of code generation, iterative improvement prompts lead to progressive quality degradation (SlopCodeBench). Common strategies like "critique and revise," "harsh critic," and "improve this" all suffer from the same fundamental issue: the model cannot maintain stable quality judgments across iterations.

The problem is particularly acute in subjective domains—strategy documents, creative writing, analysis, and planning—where no ground truth metric exists. Without an objective fitness function, traditional autoresearch approaches cannot be applied directly. Human evaluation remains the gold standard but is expensive and slow.

We present autoreason, a method that constructs a subjective fitness function through independent blind evaluation. In our single test case of go-to-market strategy generation, the method produced outputs that judges preferred over baseline approaches. We emphasize this represents initial exploration on one task, not a comprehensively validated approach.

## 2. Method

Autoreason implements an A/B/AB evaluation loop where:
- **A** is the current incumbent (best version so far)
- **B** is a new challenger created to improve upon A
- **AB** is a synthesis that attempts to combine the best of both A and B

The method ensures that each role is performed by a fresh, isolated agent with no knowledge of prior iterations or the other agents' identities.

### 2.1 Architecture

Each pass consists of four phases:

**Strawman Phase**: A fresh critic agent receives the original task and the current incumbent A. The critic identifies potential weaknesses, areas for improvement, or missing elements without seeing any prior criticism or iteration history.

**Author Phase**: Two fresh author agents work independently. The first receives the original task, incumbent A, and the strawman critique to generate challenger B. The second receives the same inputs plus both A and B to create synthesis AB. Neither author has knowledge of previous iterations or judge feedback. Authors use temperature 0.8 to encourage creative exploration.

**Judge Phase**: A panel of three fresh judge agents independently evaluates A, B, and AB in randomized order. Judges receive only the original task and the three candidates, with no indication of which is incumbent, challenger, or synthesis. Each judge provides a complete ranking from best to worst. Judges use temperature 0.3 for more consistent evaluation. We use standard Borda count scoring where first place receives 2 points, second place receives 1 point, and third place receives 0 points.

**Aggregation**: Rankings are aggregated by summing Borda scores across all judges. The candidate with the highest total score becomes the new incumbent. In case of equal total scores across judges, the current incumbent A wins (conservative tiebreak).

### 2.2 Convergence

The system tracks consecutive wins by the incumbent A. In our experiment, A won at passes 3, 6, 9, 12, 14, 15, 24, and 25. This produced 2 consecutive A wins at passes 14-15 and 24-25. We had predefined convergence as 3 consecutive A wins, though our experiment never reached this threshold. AB won exactly 13 of 26 passes (50%), suggesting the synthesis mechanism found improvements throughout.

### 2.3 Design Rationale

Each design choice was motivated by hypothesized failure modes:

**Fresh isolated agents** aim to prevent context accumulation and authorship bias, though we did not test this empirically.

**Blind evaluation** aims to prevent judges from favoring candidates based on perceived recency or authorship patterns.

**Judge panels** aim to reduce single-judge noise through aggregation. We chose 3 judges without empirical validation of this choice.

**Three candidates (A/B/AB)** allow exploration of both incremental improvements (B) and synthetic combinations (AB). We did not test alternative configurations.

**Conservative tiebreak** aims to prevent oscillation between equally good alternatives.

## 3. Experiments

We evaluated autoreason on a single task: go-to-market strategy generation for an open-source Kubernetes CLI tool. This task represents a typical subjective business document where quality is clear to human judges but no objective metric exists.

### 3.1 Experimental Setup

All experiments used claude-sonnet-4-20250514 with temperature 0.8 for authors and 0.3 for judges. The v2 architecture employed 3-judge panels with Borda count aggregation and conservative tiebreaking.

The experiment used approximately 160 LLM calls across 26 passes.

### 3.2 Main Experiment

We ran the full autoreason process for 26 passes before manual termination. The system never reached the convergence threshold of 3 consecutive incumbent wins.

The process showed variation in output length and win patterns across passes.

### 3.3 Baseline Comparison

We compared autoreason's pass 15 output against four baseline methods, each given the same initial task:

- **Conservative**: Single-shot generation (no iteration)
- **Improve_this**: Iterative improvement using the prompt "Improve this output" for 5 iterations
- **Harsh_critic**: Iterative improvement with prompts emphasizing critical evaluation for 5 iterations
- **Critique_and_revise**: Structured approach alternating critique and revision phases for 5 iterations

We selected pass 15 for comparison after observing it was the first point of 2 consecutive incumbent wins. This post-hoc selection limits the generalizability of results.

A panel of 7 fresh judges (not used in the main experiment) evaluated all five outputs using ranked choice voting with standard Borda count scoring (4 points for 1st place, 3 for 2nd, 2 for 3rd, 1 for 4th, 0 for 5th). Total possible score was 28 points per method.

### 3.4 Temporal Comparison

To test whether continued iteration affected quality, we compared outputs from pass 15 versus pass 25 using a separate 7-judge blind panel. We selected pass 25 as it represented the second occurrence of 2 consecutive incumbent wins.

### 3.5 Baseline Visibility Test

We conducted a single test of whether judges needed a baseline for calibration by comparing autoreason output against a deliberately degraded version with and without the original task output shown for reference.

## 4. Results

### 4.1 Baseline Comparison

Autoreason's pass 15 output achieved the highest total Borda score (35 points out of 35 possible, calculated as 7 judges × 5 points for unanimous first place) and received all 7 first-place votes. The conservative baseline scored 21 points, improve_this and harsh_critic both scored 18 points, and critique_and_revise scored 13 points. Without significance testing, we cannot make statistical claims about these differences.

Word counts revealed length inflation across methods: from 847 words at pass 1, autoreason reached 1,800 words by pass 15, while improve_this reached 2,116, harsh_critic 1,961, and critique_and_revise ballooned to 2,507. The conservative baseline remained concise at 862 words.

### 4.2 Quality Trajectory

Pass 15 was preferred over pass 25 by a 6-1 margin among judges, suggesting that continued iteration beyond the first stable point may not improve quality. Pass 26 (which AB won) contained approximately 1,617 words, showing continued variation.

### 4.3 Baseline Visibility

In our single test, judges preferred autoreason output 7-0 against the adversarial version when shown the baseline, and 3-2 without baseline.

### 4.4 Qualitative Improvements

The initial output contained generic targets and unsupported metrics ("$49/user pricing," "$100K MRR"). Pass 15 output included quantified pain points ("$15K/incident x 6/yr"), team pricing ("$1499/mo"), customer validation references ("50+ interviews, 75% pilot success"), and unit economics ("CAC $2K, LTV $54K").

## 5. Related Work

The autoresearch paradigm demonstrates success in objective domains with clear metrics. SlopCodeBench (Orlanski et al. 2026) shows that iterative refinement fails even for code generation. Work on ACE context collapse (Zhang et al. ICLR 2026) identifies how LLMs lose quality baselines with accumulated context. LLM Council explores multi-agent deliberation architectures. Our use of blind evaluation panels builds on established peer review practices.

## 6. Discussion

### 6.1 Bloat/Prune Oscillation

Word count varied between passes, ranging from approximately 1,600 to 2,100 words in middle passes. This variation could indicate multiple factors including task underspecification or natural variation in author behavior.

### 6.2 Convergence Patterns

Our experiment achieved 2 consecutive incumbent wins at passes 14-15 and 24-25 but never reached 3 consecutive wins. AB won exactly 13 of 26 passes (50%). Whether this represents oscillation between equally viable solutions or indicates the method doesn't converge requires testing across multiple tasks.

### 6.3 Judge Calibration

Our single baseline visibility test showed unanimous preference (7-0) with baseline against an adversarial version, demonstrating that judges need reference points to detect drift effectively. More systematic testing would be needed to draw broader conclusions about judge calibration requirements.

### 6.4 Applications Beyond Subjective Domains

Autoreason may prove valuable even in domains with objective metrics. Metrics often fail to capture all relevant quality dimensions—a function might pass all tests yet be unmaintainable. Autoreason could provide a complementary signal in such cases.

### 6.5 Limitations

This work represents an exploratory study of a single task domain (go-to-market strategy) with one experimental run. We cannot generalize beyond this specific case.

Critical limitations include:
- No statistical significance testing or confidence intervals
- No analysis of inter-rater agreement among the 3-judge panels
- No ablation studies to determine which components contribute to performance
- No validation that fresh agents actually prevent the hypothesized failure modes
- Post-hoc selection of pass 15 for comparison
- Baseline methods represent our interpretation of common patterns; other implementations might yield different results
- No systematic testing of design choices (number of judges, candidates, convergence threshold)
- Results from a single model (claude-sonnet-4-20250514) may not generalize
- Specific prompts not included, limiting reproducibility

The method's effectiveness on other subjective tasks (creative writing, analysis, etc.) remains untested.

## 7. Conclusion

Autoreason demonstrates one approach to iterative refinement in a subjective domain task. By isolating agents, implementing blind evaluation, and using conservative aggregation, the method achieved improvements in our test case while limiting the length inflation seen in baseline approaches.

Our experiment on go-to-market strategy generation showed 35 total Borda points and all first-place rankings from 7 judges in a 5-way comparison. The method used approximately 160 LLM calls over 26 passes, achieving 2 consecutive incumbent wins twice but never reaching 3 consecutive wins.

This exploratory work on a single task cannot support general claims about the method's effectiveness. Future work should test across diverse domains, include statistical validation, analyze optimal parameters through ablation studies, and provide complete methodological details for reproducibility. Only through such systematic investigation can we determine whether autoreason represents a reliable approach to subjective iteration or merely an artifact of our specific experimental setup.