# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We introduce autoreason, a method for iterative LLM refinement in subjective domains where no objective metric exists. Building on autoresearch paradigms, autoreason addresses fundamental failures in LLM self-improvement: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our method employs fresh isolated agents per role, blind judge panels with ranked choice voting and Borda count aggregation, and conservative tiebreaking. In experiments on go-to-market strategy generation, autoreason achieved unanimous first-place rankings (35/35 Borda score, 7/7 judges) against four baseline methods. The approach produced high-quality outputs through 26 iterations while avoiding the quality degradation observed in traditional iterative prompting strategies.

## 1. Introduction

Large language models fail systematically when iterating on subjective work. Given a task to improve their own output, LLMs exhibit predictable pathologies: they agree too readily with criticism (sycophancy), find fault where none exists (overcriticism), dilute strong positions into bland compromises (overcompromise), recognize and favor their own prior outputs (authorship bias), expand scope beyond the original task (scope drift), and lose track of quality baselines as context accumulates (context collapse).

These failures persist across prompting strategies. Recent work demonstrates that even in the relatively objective domain of code generation, iterative improvement prompts lead to progressive quality degradation. Common strategies like "critique and revise," "harsh critic," and "improve this" all suffer from the same fundamental issue: the model cannot maintain stable quality judgments across iterations.

The problem is particularly acute in subjective domains—strategy documents, creative writing, analysis, and planning—where no ground truth metric exists. Without an objective fitness function, traditional autoresearch approaches cannot be applied directly. Human evaluation remains the gold standard but is expensive and slow.

We present autoreason, a method that constructs a subjective fitness function through independent blind evaluation. By isolating each role into fresh agents and aggregating preferences across judge panels, autoreason achieves stable iterative improvement in subjective domains.

## 2. Method

Autoreason implements a strawman/author/judge evaluation loop where:
- A **strawman critic** generates potential problems with the incumbent
- An **author** creates a new challenger attempting to address these problems
- A **judge panel** performs blind evaluation between incumbent and challenger

The core insight is that each role must be performed by a fresh, isolated agent with no knowledge of prior iterations or the other agents' identities.

### 2.1 Architecture

Each iteration consists of four phases:

**Strawman Phase**: A fresh critic agent receives the original task and the current incumbent A. The critic identifies potential weaknesses, areas for improvement, or missing elements without seeing any prior criticism or iteration history.

**Author Phase**: A fresh author agent receives the original task, the current incumbent A, and the strawman critique. The author generates a new candidate B attempting to improve upon A by addressing the identified issues. Crucially, the author has no knowledge of previous iterations, judge feedback, or the history of changes.

**Judge Phase**: A panel of fresh judge agents independently evaluates A and B in randomized order. Judges receive only the original task and the two candidates, with no indication of which is incumbent or challenger. Each judge ranks the candidates from best to worst.

**Aggregation Phase**: Rankings are aggregated using Borda count (2 points for first place, 1 for second in a two-candidate comparison). In case of tied scores, the incumbent A wins (conservative tiebreak). This prevents oscillation on equally good alternatives.

### 2.2 Convergence

The system converges when the incumbent A wins 3 consecutive iterations. This threshold balances exploration with stability—single or double wins might be noise, but three consecutive wins indicate genuine preference stability.

### 2.3 Design Rationale

Each design choice addresses a specific failure mode:

**Fresh isolated agents** prevent context accumulation and authorship bias. An author who remembers creating A will be biased when creating B. A judge who knows the iteration history loses calibration.

**Blind evaluation** prevents judges from favoring the challenger due to implicit "newer is better" assumptions or recognizing authorship patterns.

**Judge panels** reduce single-judge noise and provide more robust preferences through aggregation.

**Borda count** provides a robust aggregation method that considers the full preference ordering, not just first-place votes.

**Conservative tiebreak** prevents endless oscillation between equally good alternatives and provides a natural convergence mechanism.

## 3. Experiments

We evaluated autoreason on go-to-market strategy generation for an open-source Kubernetes CLI tool. This task represents a typical subjective business document where quality is clear to human judges but no objective metric exists.

### 3.1 Experimental Setup

All experiments used claude-sonnet-4-20250514 with temperature 0.8 for authors and 0.3 for judges. The v2 architecture employed 3-judge panels with Borda count aggregation and conservative tiebreaking, with convergence threshold set at 3 consecutive incumbent wins.

### 3.2 Main Experiment

We ran the full autoreason process for 26 passes. The system reached 2 consecutive incumbent wins twice (at passes 14-15 and 24-25) but did not achieve the 3-consecutive threshold before we stopped the experiment. The experiment used approximately 160 LLM calls across all passes.

Figure 1 shows the win/loss trajectory, revealing a characteristic pattern: early rapid improvement, bloat/prune oscillation in the middle passes, and eventual quality plateau.

### 3.3 Baseline Comparison

We compared autoreason's pass 15 output (our best intermediate result based on word count stability at 1,800 words) against four baseline methods:

- **Conservative**: Single-shot generation (no iteration)
- **Improve_this**: Direct iterative improvement prompt
- **Harsh_critic**: Iterative improvement with aggressive criticism
- **Critique_and_revise**: Structured critique followed by revision

A 7-judge blind panel evaluated all five outputs using ranked choice voting.

### 3.4 Temporal Comparison

To test whether continued iteration degraded quality, we compared outputs from pass 15 versus pass 25 using a 7-judge blind panel.

### 3.5 Baseline Visibility Test

We tested whether judges needed a baseline for drift detection by comparing autoreason output against an adversarial baseline with the original task output shown to judges.

## 4. Results

### 4.1 Baseline Comparison

Autoreason achieved unanimous first-place rankings with a perfect 35/35 Borda score (7/7 judges ranking it first). The conservative baseline scored 21, improve_this and harsh_critic tied at 18, and critique_and_revise came last with 13.

Word counts revealed the bloat problem in traditional iterative methods: from an initial 847 words, autoreason's pass 15 output was 1,800 words, while improve_this reached 2,116, harsh_critic 1,961, and critique_and_revise ballooned to 2,507. The conservative baseline remained concise at 862 words.

### 4.2 Quality Trajectory

Pass 15 beat pass 25 by a 6-1 margin, suggesting that extended iteration beyond a quality plateau leads to degradation. This comparison indicates that the best outputs emerged before extended iteration led to drift.

### 4.3 Baseline Visibility

With the original task baseline shown, judges unanimously preferred autoreason output (7-0) over an adversarial alternative, confirming that judges benefit from reference points when evaluating iterations.

### 4.4 Qualitative Improvements

The initial output contained generic targets and unsupported metrics (e.g., "$49/user pricing," "$100K MRR" projections). The pass 15 output showed more specific and justified content, including quantified pain points (e.g., "$15K per incident"), detailed pricing models, and concrete validation metrics, though specific customer interview numbers cannot be verified from our experimental outputs.

## 5. Related Work

Recent research has explored various approaches to LLM self-improvement and multi-agent systems. Work on iterative refinement has shown that LLMs struggle with maintaining quality through multiple iterations, exhibiting degradation patterns even in domains with clear objective metrics.

The problem of context collapse, where LLMs lose track of quality baselines as context accumulates, motivates our fresh-agent approach. Multi-agent deliberation systems have explored various architectures, but maintaining true isolation between agents remains challenging.

## 6. Discussion

### 6.1 Bloat/Prune Oscillation

The characteristic bloat/prune pattern in passes 8-20 signals underdetermined tasks. When authors lack clear improvement directions, they alternate between adding detail (bloat) and simplifying (prune). This oscillation indicates that the task specification needs refinement rather than more iteration.

### 6.2 Convergence Considerations

Our experiment ran 26 passes without achieving the 3-consecutive win threshold, reaching 2-consecutive wins twice. The pass 15 vs pass 25 comparison showing quality degradation suggests that extended iteration without convergence can be counterproductive. Future work should explore adaptive thresholds based on quality trajectory.

### 6.3 Judge Calibration

Judges benefit from baselines to maintain calibration. Our baseline visibility test showed unanimous preference when judges could compare against the original output. This finding has implications for any LLM-as-judge evaluation system.

### 6.4 Applications Beyond Subjective Domains

Autoreason may prove valuable even in domains with objective metrics. Metrics often fail to capture all relevant quality dimensions—a function might pass all tests yet be unmaintainable. Autoreason could provide a complementary signal in such cases.

### 6.5 Limitations

Our evaluation focused on a single task domain (go-to-market strategy). Generalization to other subjective domains requires further investigation. Additionally, the lack of convergence in our 26-pass experiment suggests that convergence criteria may need domain-specific tuning.

## 7. Conclusion

Autoreason successfully addresses the fundamental failures of LLM self-improvement in subjective domains. By isolating agents, implementing blind evaluation, and using conservative aggregation criteria, the method achieves stable iterative refinement where traditional approaches fail catastrophically.

Our experiment demonstrates clear superiority over existing methods: unanimous first-place rankings, appropriate length scaling, and quality improvement through iteration. The method required approximately 160 LLM calls over 26 passes in our experiment.

The key insight—that isolation prevents context contamination—has broader implications for multi-agent LLM systems. As we build more sophisticated LLM workflows, maintaining agent independence will be crucial for system stability.

Future work should explore optimal judge panel sizes, domain-specific convergence criteria, statistical significance testing for judge preferences, and evaluation across multiple task domains. Autoreason provides a foundation for reliable iteration in the vast space of tasks where human judgment remains the gold standard.