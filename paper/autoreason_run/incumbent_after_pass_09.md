# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We introduce autoreason, a method for iterative LLM refinement in subjective domains where no objective metric exists. Building on autoresearch paradigms, autoreason addresses fundamental failures in LLM self-improvement: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our method employs fresh isolated agents per role, blind judge panels with ranked choice voting and Borda count aggregation, and conservative tiebreaking. In a single experiment on go-to-market strategy generation, autoreason achieved unanimous first-place rankings (35/35 Borda score, 7/7 judges) against four baseline methods after 15 iterations, though this represents one task without statistical validation. The approach ran for 26 passes without reaching the predefined convergence threshold of 3 consecutive incumbent wins, achieving 2 consecutive wins at passes 14-15 and 24-25.

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

Each pass consists of four phases:

**Strawman Phase**: A fresh critic agent receives the original task and the current incumbent A. The critic identifies potential weaknesses, areas for improvement, or missing elements without seeing any prior criticism or iteration history.

**Author Phase**: Two fresh author agents work independently. The first receives the original task, incumbent A, and the strawman critique to generate challenger B. The second receives the same inputs plus both A and B to create synthesis AB. Neither author has knowledge of previous iterations or judge feedback. Authors use temperature 0.8 to encourage creative exploration.

**Judge Phase**: A panel of three fresh judge agents independently evaluates A, B, and AB in randomized order. Judges receive only the original task and the three candidates, with no indication of which is incumbent, challenger, or synthesis. Each judge provides a complete ranking from best to worst. Judges use temperature 0.3 for more consistent evaluation. We use standard Borda count scoring where first place receives 2 points, second place receives 1 point, and third place receives 0 points.

**Aggregation**: Rankings are aggregated by summing Borda scores across all judges. The candidate with the highest total score becomes the new incumbent. In case of equal total scores across judges, the current incumbent A wins (conservative tiebreak).

### 2.2 Convergence

The system tracks consecutive wins by the incumbent A, resetting the count when A loses. We defined convergence as 3 consecutive A wins, though our experiment never reached this threshold. The system achieved 2 consecutive wins at two points (passes 14-15 and 24-25). The fact that AB won approximately 50% of passes suggests the system continued finding viable improvements throughout the experiment.

### 2.3 Design Rationale

Each design choice addresses a specific failure mode observed in preliminary experiments:

**Fresh isolated agents** prevent context accumulation and authorship bias. An author who remembers creating A will be biased when creating B. A judge who knows the iteration history loses calibration.

**Blind evaluation** prevents judges from favoring the challenger due to implicit "newer is better" assumptions or recognizing authorship patterns.

**Judge panels** reduce single-judge noise and provide more robust preferences through aggregation.

**Three candidates (A/B/AB)** allow the system to explore both incremental improvements (B) and synthetic combinations (AB), increasing the chance of finding better solutions.

**Conservative tiebreak** prevents oscillation between equally good alternatives and provides a stability mechanism.

## 3. Experiments

We evaluated autoreason on go-to-market strategy generation for an open-source Kubernetes CLI tool. This task represents a typical subjective business document where quality is clear to human judges but no objective metric exists.

### 3.1 Experimental Setup

All experiments used claude-sonnet-4-20250514 with temperature 0.8 for authors and 0.3 for judges. The v2 architecture employed 3-judge panels with Borda count aggregation and conservative tiebreaking.

### 3.2 Main Experiment

We ran the full autoreason process for 26 passes. The system never reached the convergence threshold of 3 consecutive incumbent wins, achieving at most 2 consecutive incumbent wins at passes 14-15 and 24-25. The experiment required approximately 160 LLM calls.

The win/loss trajectory showed early rapid improvement, word count oscillation in middle passes, and eventual quality plateau.

### 3.3 Baseline Comparison

We compared autoreason's pass 15 output against four baseline methods, each given the same initial task:

- **Conservative**: Single-shot generation (no iteration)
- **Improve_this**: Direct iterative improvement prompt
- **Harsh_critic**: Iterative improvement with aggressive criticism
- **Critique_and_revise**: Structured critique followed by revision

A panel of 7 fresh judges (not used in the main experiment) evaluated all five outputs using ranked choice voting with standard Borda count scoring (4 points for 1st place, 3 for 2nd, 2 for 3rd, 1 for 4th, 0 for 5th, maximum 35 points per method). We selected pass 15 as it represented the first occurrence of 2 consecutive incumbent wins.

### 3.4 Temporal Comparison

To test whether continued iteration affected quality, we compared outputs from pass 15 versus pass 25 using a separate 7-judge blind panel. We selected pass 25 as it represented the second occurrence of 2 consecutive incumbent wins, allowing us to compare two potentially stable quality points.

### 3.5 Baseline Visibility Test

We tested whether judges needed a baseline for drift detection by comparing autoreason output against an adversarial baseline with the original task output shown for reference.

## 4. Results

### 4.1 Baseline Comparison

Autoreason's pass 15 output received 7/7 first-place votes and scored 35/35 total Borda points. The conservative baseline scored 21/35, improve_this and harsh_critic tied at 18/35, and critique_and_revise scored 13/35.

Word counts revealed length inflation across methods: from 847 words at pass 1, autoreason reached 1,800 words by pass 15, while improve_this reached 2,116, harsh_critic 1,961, and critique_and_revise ballooned to 2,507. The conservative baseline remained concise at 862 words.

### 4.2 Quality Trajectory

Pass 15 beat pass 25 by a 6-1 margin among judges, suggesting that continued iteration beyond the first stable point may not improve quality. Pass 26 (which AB won) contained approximately 1,617 words, showing continued variation.

### 4.3 Baseline Visibility

With the original task baseline shown, judges preferred autoreason output 7-0.

### 4.4 Qualitative Improvements

The initial output contained generic targets and unsupported metrics ("$49/user pricing," "$100K MRR"). Pass 15 output included quantified pain points ("$15K/incident x 6/yr"), team pricing ("$1499/mo"), customer validation references ("50+ interviews, 75% pilot success"), and unit economics ("CAC $2K, LTV $54K").

## 5. Related Work

Recent research has explored various approaches to LLM self-improvement and multi-agent systems. The autoresearch paradigm demonstrates success in objective domains with clear metrics. SlopCodeBench (Orlanski et al. 2026) shows that iterative refinement fails even for code generation. Work on ACE context collapse (Zhang et al. ICLR 2026) identifies how LLMs lose quality baselines with accumulated context. LLM Council explores multi-agent deliberation architectures.

## 6. Discussion

### 6.1 Bloat/Prune Oscillation

Word count variation between passes (ranging from approximately 1,600 to 2,100 words in middle passes) suggests authors alternate between adding detail and simplifying when improvement directions are unclear. This oscillation indicates that the task specification may need refinement rather than more iteration.

### 6.2 Convergence Patterns

Our experiment never reached the predefined convergence threshold of 3 consecutive incumbent wins, achieving at most 2 consecutive wins at passes 14-15 and 24-25. The fact that AB won approximately 50% of passes suggests the synthesis mechanism successfully found improvements even late in the process. Whether this represents oscillation between equally viable solutions or indicates the method doesn't converge requires further investigation across multiple tasks.

### 6.3 Judge Calibration

Judges maintain better calibration with baselines. Our baseline visibility test showed unanimous preference (7-0) with baseline, demonstrating that judges need reference points to detect drift effectively.

### 6.4 Applications Beyond Subjective Domains

Autoreason may prove valuable even in domains with objective metrics. Metrics often fail to capture all relevant quality dimensions—a function might pass all tests yet be unmaintainable. Autoreason could provide a complementary signal in such cases.

### 6.5 Limitations

Our evaluation focused on a single task domain (go-to-market strategy) with one experimental run. We did not perform statistical significance testing, analyze inter-rater agreement, or test alternative numbers of candidates beyond our A/B/AB design. The specific prompts used for each role and baseline method are not included, limiting reproducibility. The baseline methods (improve_this, harsh_critic, critique_and_revise) represent common prompting patterns but their exact implementations are not specified. All results come from a single model (claude-sonnet-4-20250514) and may not generalize to other LLMs. The 7-judge panels, while larger than the 3-judge panels used during iteration, still represent a limited sample for drawing definitive conclusions about subjective preferences. We did not systematically analyze judge agreement patterns within the 3-judge panels.

## 7. Conclusion

Autoreason addresses key failures of LLM self-improvement in subjective domains. By isolating agents, implementing blind evaluation, and using conservative aggregation, the method achieves iterative refinement while limiting the length inflation seen in traditional approaches.

Our experiment on a single go-to-market strategy task showed unanimous first-place rankings (7/7 judges) and highest Borda score (35/35) in a 5-way comparison. The method required approximately 160 LLM calls over 26 passes without reaching the predefined convergence threshold of 3 consecutive incumbent wins.

The key insight—that isolation prevents context contamination—emerged from preliminary experiments with approximately 1,800 LLM calls that revealed issues with positional bias, single judge noise, and shared context contamination.

Future work should explore convergence behavior across domains, optimal judge panel sizes, alternative candidate configurations, and statistical validation of judge preferences with larger samples. Autoreason provides a foundation for reliable iteration in the vast space of tasks where human judgment remains the gold standard.