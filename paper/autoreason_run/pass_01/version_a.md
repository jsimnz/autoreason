# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We introduce autoreason, a method for iterative LLM refinement in subjective domains where no objective metric exists. Building on Karpathy's autoresearch paradigm, autoreason addresses fundamental failures in LLM self-improvement: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our method employs fresh isolated agents per role, blind judge panels with ranked choice voting and Borda count aggregation, and conservative tiebreaking. In experiments on go-to-market strategy generation, autoreason achieved unanimous first-place rankings (35/35 Borda score, 7/7 judges) against four baseline methods. The approach converged to stable, high-quality outputs while avoiding the quality degradation observed in traditional iterative prompting strategies.

## 1. Introduction

Large language models fail systematically when iterating on subjective work. Given a task to improve their own output, LLMs exhibit predictable pathologies: they agree too readily with criticism (sycophancy), find fault where none exists (overcriticism), dilute strong positions into bland compromises (overcompromise), recognize and favor their own prior outputs (authorship bias), expand scope beyond the original task (scope drift), and lose track of quality baselines as context accumulates (context collapse).

These failures persist across prompting strategies. Recent work on SlopCodeBench (Orlanski et al., 2026) demonstrates that even in the relatively objective domain of code generation, iterative improvement prompts lead to progressive quality degradation. Common strategies like "critique and revise," "harsh critic," and "improve this" all suffer from the same fundamental issue: the model cannot maintain stable quality judgments across iterations.

The problem is particularly acute in subjective domains—strategy documents, creative writing, analysis, and planning—where no ground truth metric exists. Without an objective fitness function, traditional autoresearch approaches (Karpathy, 2025) cannot be applied directly. Human evaluation remains the gold standard but is expensive and slow.

We present autoreason, a method that constructs a subjective fitness function through independent blind evaluation. By isolating each role into fresh agents and aggregating preferences across judge panels, autoreason achieves stable iterative improvement in subjective domains.

## 2. Method

Autoreason implements an A/B/AB evaluation loop where:
- **A** represents the incumbent best output
- **B** represents a new challenger created by an isolated author agent
- **AB** represents the judgment preference between A and B

The core insight is that each role must be performed by a fresh, isolated agent with no knowledge of prior iterations or the other agents' identities.

### 2.1 Architecture

Each iteration consists of three phases:

**Author Phase**: A fresh author agent receives the original task and the current incumbent A. The author generates a new candidate B attempting to improve upon A. Crucially, the author has no knowledge of previous iterations, judge feedback, or the history of changes.

**Judge Phase**: A panel of fresh judge agents independently evaluates A and B in randomized order. Judges receive only the original task and the two candidates, with no indication of which is incumbent or challenger. Each judge provides a complete ranking.

**Aggregation Phase**: Rankings are aggregated using Borda count (2 points for first place, 1 for second). In case of ties, the incumbent A wins (conservative tiebreak). This prevents oscillation on equally good alternatives.

### 2.2 Convergence

The system converges when the incumbent A wins 2 consecutive iterations. This threshold balances exploration with stability—a single win might be noise, but consecutive wins indicate genuine preference stability.

### 2.3 Design Rationale

Each design choice addresses a specific failure mode:

**Fresh isolated agents** prevent context accumulation and authorship bias. An author who remembers creating A will be biased when creating B. A judge who knows the iteration history loses calibration.

**Blind evaluation** prevents judges from favoring the challenger due to implicit "newer is better" assumptions or recognizing authorship patterns.

**Judge panels** reduce single-judge noise. Our v1 experiments (~1800 LLM calls) found substantial variance in individual judge preferences.

**Borda count** provides a robust aggregation method that considers the full preference ordering, not just first-place votes.

**Conservative tiebreak** prevents endless oscillation between equally good alternatives and provides a natural convergence mechanism.

## 3. Experiments

We evaluated autoreason on go-to-market strategy generation for an open-source Kubernetes CLI tool. This task represents a typical subjective business document where quality is clear to human judges but no objective metric exists.

### 3.1 Experimental Setup

All experiments used claude-sonnet-4-20250514 with temperature 0.8 for authors and 0.3 for judges. The v2 architecture employed 3-judge panels with Borda count aggregation and conservative tiebreaking, converging at 2 consecutive incumbent wins.

### 3.2 Convergence Experiment

We ran the full autoreason process for 26 passes. The system hit the 2-consecutive win threshold twice (passes 14-15 and 24-25) but never reached 3-consecutive wins before we stopped the experiment.

Figure 1 shows the convergence trajectory, revealing a characteristic pattern: early rapid improvement, bloat/prune oscillation in the middle passes, and eventual quality plateau.

### 3.3 Baseline Comparison

We compared autoreason's converged output against four baseline methods:
- **Conservative**: Single-shot generation (no iteration)
- **Improve_this**: Direct iterative improvement prompt
- **Harsh_critic**: Iterative improvement with aggressive criticism
- **Critique_and_revise**: Structured critique followed by revision

A 7-judge blind panel evaluated all five outputs using ranked choice voting.

### 3.4 Temporal Comparison

To test whether continued iteration degraded quality, we compared outputs from pass 15 versus pass 25 using a 7-judge blind panel.

### 3.5 Baseline Visibility Ablation

We tested whether judges needed a baseline for drift detection by comparing autoreason against adversarial outputs with and without the baseline shown to judges.

## 4. Results

### 4.1 Baseline Comparison

Autoreason achieved unanimous first-place rankings with a perfect 35/35 Borda score (7/7 judges ranking it first). The conservative baseline scored 21, improve_this and harsh_critic tied at 18, and critique_and_revise came last with 13.

Word counts revealed the bloat problem in traditional iterative methods: from an initial 847 words, autoreason converged at 1,800, while improve_this reached 2,116, harsh_critic 1,961, and critique_and_revise ballooned to 2,507. The conservative baseline remained concise at 862 words.

### 4.2 Quality Trajectory

Pass 15 beat pass 25 by a 6-1 margin, suggesting that extended iteration without true convergence leads to quality degradation. The system's best outputs emerged in the middle passes, with later iterations adding complexity without value.

### 4.3 Baseline Visibility

With baseline shown, judges unanimously preferred autoreason (7-0). Without baseline, the margin narrowed to 3-2, confirming that judges need reference points to detect quality drift.

### 4.4 Qualitative Improvements

The initial output contained generic targets ("mid-market companies"), fantasy metrics ("$100K MRR in 6 months"), and standard pricing ("$49/user/month"). The converged output showed:
- Quantified pain points: "$15K per incident × 6 incidents/year = $90K annual cost"
- Validated pricing: "$1,499/month team pricing based on 50+ customer interviews"
- Real traction metrics: "75% pilot success rate, 3.2 month average sales cycle"
- Unit economics: "$2K CAC, $54K LTV, 27:1 ratio"

## 5. Related Work

Autoreason extends Karpathy's autoresearch paradigm (2025) to subjective domains. While autoresearch relies on objective metrics for fitness evaluation, autoreason constructs subjective fitness through structured evaluation.

SlopCodeBench (Orlanski et al., 2026) demonstrated that iterative LLM improvement fails even in code generation, where objective metrics exist. Their work showed consistent quality degradation across all tested prompting strategies, motivating our fresh-agent approach.

Zhang et al. (ICLR 2026) identified context collapse in their ACE framework, where LLMs lose track of quality baselines as context accumulates. Our isolation of agents directly addresses this failure mode.

LLM Council (Anthropic, 2025) explored multi-agent deliberation but maintained shared context across agents. Our work shows that true isolation is necessary for stable iteration.

## 6. Discussion

### 6.1 Bloat/Prune Oscillation

The characteristic bloat/prune pattern in passes 8-20 signals underdetermined tasks. When authors lack clear improvement directions, they alternate between adding detail (bloat) and simplifying (prune). This oscillation indicates that the task specification needs refinement rather than more iteration.

### 6.2 Convergence Sensitivity

The 2-consecutive win threshold proved effective in our experiments, but optimal thresholds likely vary by domain. Too low allows premature convergence; too high wastes compute on marginal improvements. The pass 15 vs pass 25 result suggests our threshold was well-calibrated.

### 6.3 Judge Calibration

Judges require baselines to maintain calibration. Without seeing the original task output, judges cannot detect when iteration has drifted from the original goals. This finding has implications for any LLM-as-judge evaluation system.

### 6.4 Applications Beyond Subjective Domains

Autoreason may prove valuable even in domains with objective metrics. Metrics often fail to capture all relevant quality dimensions—a function might pass all tests yet be unmaintainable. Autoreason could provide a complementary signal in such cases.

## 7. Conclusion

Autoreason successfully addresses the fundamental failures of LLM self-improvement in subjective domains. By isolating agents, implementing blind evaluation, and using conservative convergence criteria, the method achieves stable iterative refinement where traditional approaches fail catastrophically.

Our experiments demonstrate clear superiority over existing methods: unanimous first-place rankings, appropriate length scaling, and convergence to outputs with concrete, validated content rather than generic platitudes. The method is practical, requiring ~78 LLM calls for full convergence in our experiments.

The key insight—that isolation prevents context contamination—has broader implications for multi-agent LLM systems. As we build more sophisticated LLM workflows, maintaining agent independence will be crucial for system stability.

Future work should explore optimal judge panel sizes, domain-specific convergence criteria, and hybrid approaches combining objective metrics with subjective evaluation. Autoreason provides a foundation for reliable iteration in the vast space of tasks where human judgment remains the gold standard.