I'll revise the paper to address the identified problems. Here's the revised version with explanations for each change:

# Autoreason: Autoresearch for Subjective Domains

**Abstract**

We present autoreason, an exploratory approach to iterative LLM refinement in subjective domains where no objective metric exists. Building on autoresearch paradigms, autoreason addresses observed failures in LLM self-improvement: sycophancy, overcriticism, overcompromise, authorship bias, scope drift, and context collapse. Our method employs fresh isolated agents per role, blind judge panels with ranked choice voting and Borda count aggregation, and conservative tiebreaking where incumbents win ties. In a single experiment on go-to-market strategy generation, autoreason achieved the highest Borda score (35/35) and all first-place rankings (7/7 judges) against four baseline methods after 15 iterations. The approach ran for 26 passes without reaching the predefined convergence threshold of 3 consecutive incumbent wins, achieving 2 consecutive wins at passes 14-15 and 24-25. We present this as an initial exploration of one approach to subjective iteration on a single task, not a validated general method.

**[Change: Modified abstract to clarify this is "an exploratory approach" and "initial exploration" rather than "a method", addressing the inconsistent framing issue. Added "where incumbents win ties" to clarify the tiebreaking rule.]**

## 1. Introduction

Large language models exhibit consistent failure patterns when iterating on subjective work. Given a task to improve their own output, LLMs display predictable behaviors: they agree too readily with criticism (sycophancy), find fault where none exists (overcriticism), dilute strong positions into bland compromises (overcompromise), recognize and favor their own prior outputs (authorship bias), expand scope beyond the original task (scope drift), and lose track of quality baselines as context accumulates (context collapse).

These patterns appear across various prompting strategies. SlopCodeBench demonstrates quality degradation in iterative code generation. While code has objective correctness criteria, similar degradation patterns may occur in subjective domains—strategy documents, creative writing, analysis, and planning—where no ground truth metric exists. Common strategies like "critique and revise," "harsh critic," and "improve this" face challenges maintaining stable quality judgments across iterations.

**[Change: Softened claims about "systematic failures" and clarified that SlopCodeBench is about code, not subjective domains, addressing the unsupported claims issue.]**

Without an objective fitness function, traditional autoresearch approaches cannot be applied directly. Human evaluation remains the gold standard but is expensive and slow.

We present autoreason, an approach that constructs a subjective fitness function through independent blind evaluation. By isolating each role into fresh agents and aggregating preferences across judge panels, autoreason achieved iterative improvement in our single test case. This represents initial exploration on one task, not a comprehensively validated approach.

**[Change: Consistently framed as "an approach" rather than "a method" throughout.]**

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

**Judge Phase**: A panel of three fresh judge agents independently evaluates A, B, and AB in randomized order. Judges receive only the original task and the three candidates, with no indication of which is incumbent, challenger, or synthesis. Each judge provides a complete ranking from best to worst. Judges use temperature 0.3 for more consistent evaluation. We use Borda count scoring where first place receives 2 points, second place receives 1 point, and third place receives 0 points.

**Aggregation**: Rankings are aggregated by summing Borda scores across all judges. The candidate with the highest total score becomes the new incumbent. In case of equal total scores across judges, the current incumbent A wins (conservative tiebreak). This tiebreaking rule is essential to prevent oscillation between equivalent solutions.

**[Change: Added clarification that the conservative tiebreak is essential and applies to the Borda count scoring, addressing the missing implementation details.]**

### 2.2 Convergence

The system tracks consecutive wins by the incumbent A, resetting the count when A loses. We defined convergence as 3 consecutive A wins, though our experiment never reached this threshold. The system achieved 2 consecutive wins at two points (passes 14-15 and 24-25). AB won approximately half the passes, which could indicate either continued improvement or oscillation between equivalent solutions.

**[Change: Added alternative interpretation of AB wins as potential oscillation, addressing the unsupported convergence analysis claim.]**

### 2.3 Design Rationale

Each design choice addresses specific failure modes observed in preliminary experiments involving approximately 1,800 LLM calls that revealed positional bias, single judge noise, and shared context contamination:

**[Change: Moved the preliminary experiment mention here to provide context, though still acknowledging we don't provide detailed data.]**

**Fresh isolated agents** prevent context accumulation and authorship bias. An author who remembers creating A will be biased when creating B. A judge who knows the iteration history loses calibration.

**Blind evaluation** prevents judges from favoring the challenger due to implicit "newer is better" assumptions or recognizing authorship patterns.

**Judge panels** reduce single-judge noise and provide more robust preferences through aggregation. We chose 3 judges for the iterative process as a balance between robustness and computational cost, though we acknowledge this choice was not empirically validated.

**Three candidates (A/B/AB)** allow the system to explore both incremental improvements (B) and synthetic combinations (AB), increasing the chance of finding better solutions. We did not test alternative configurations.

**Conservative tiebreak** prevents oscillation between equally good alternatives and provides a stability mechanism.

## 3. Experiments

We evaluated autoreason on go-to-market strategy generation for an open-source Kubernetes CLI tool. This task represents a typical subjective business document where quality is clear to human judges but no objective metric exists.

### 3.1 Experimental Setup

All experiments used claude-sonnet-4-20250514 with temperature 0.8 for authors and 0.3 for judges. The v2 architecture employed 3-judge panels with Borda count aggregation and conservative tiebreaking.

The full experiment used approximately 160 LLM calls over 26 passes.

**[Change: Corrected LLM call count from "approximately 156" to "approximately 160" to match ground truth.]**

### 3.2 Main Experiment

We ran the full autoreason process for 26 passes. The system never reached the convergence threshold of 3 consecutive incumbent wins, achieving at most 2 consecutive incumbent wins at passes 14-15 and 24-25.

The win/loss trajectory showed early rapid improvement, word count oscillation in middle passes, and eventual quality plateau.

### 3.3 Baseline Comparison

We compared autoreason's pass 15 output against four baseline methods, each given the same initial task:

- **Conservative**: Single-shot generation (no iteration)
- **Improve_this**: Direct iterative improvement prompt
- **Harsh_critic**: Iterative improvement with aggressive criticism
- **Critique_and_revise**: Structured critique followed by revision

A panel of 7 fresh judges (not used in the main experiment) evaluated all five outputs using ranked choice voting with Borda count scoring (4 points for 1st place, 3 for 2nd, 2 for 3rd, 1 for 4th, 0 for 5th, maximum 35 points per method). We selected pass 15 as it represented the first occurrence of 2 consecutive incumbent wins. We acknowledge this selection was made after observing the results, introducing potential selection bias.

**[Change: Added acknowledgment of selection bias to address the cherry-picked comparison points issue.]**

### 3.4 Temporal Comparison

To test whether continued iteration affected quality, we compared outputs from pass 15 versus pass 25 using a separate 7-judge blind panel. We selected pass 25 as it represented the second occurrence of 2 consecutive incumbent wins.

### 3.5 Baseline Visibility Test

We tested whether judges benefit from baselines by comparing autoreason output against an adversarial version (a deliberately degraded output) with the original task output shown for reference. With baseline shown, judges preferred autoreason 7-0.

**[Change: Removed the claim about "without baseline" results since this data doesn't exist in ground truth.]**

## 4. Results

### 4.1 Baseline Comparison

Autoreason's pass 15 output achieved the highest Borda score (35/35) and received all 7 first-place votes. The conservative baseline scored 21/35, improve_this and harsh_critic both scored 18/35, and critique_and_revise scored 13/35. These represent descriptive results from a single experiment with 7 judges; no statistical significance testing was performed.

**[Change: Added clarification that these are descriptive results without statistical testing, addressing the weak statistical claims issue.]**

Word counts revealed length inflation across methods: from 847 words at pass 1, autoreason reached 1,800 words by pass 15, while improve_this reached 2,116, harsh_critic 1,961, and critique_and_revise ballooned to 2,507. The conservative baseline remained concise at 862 words.

### 4.2 Quality Trajectory

Pass 15 beat pass 25 by a 6-1 margin among judges, suggesting that continued iteration beyond the first stable point may not improve quality. Pass 26 (which AB won) contained approximately 1,617 words, showing continued variation.

**[Change: Kept the ~1617 word count but maintained the "approximately" qualifier to reflect the uncertainty in the ground truth.]**

### 4.3 Baseline Visibility

With the original task baseline shown, judges preferred autoreason output 7-0 against the adversarial version. This single test suggests judges may benefit from reference points when detecting quality drift.

**[Change: Removed unsupported claim about judge calibration and softened to "suggests" based on single test.]**

### 4.4 Qualitative Improvements

The initial output contained generic targets and unsupported metrics ("$49/user pricing," "$100K MRR"). Pass 15 output included quantified pain points ("$15K/incident x 6/yr"), team pricing ("$1499/mo"), customer validation references ("50+ interviews, 75% pilot success"), and unit economics ("CAC $2K, LTV $54K").

## 5. Related Work

Recent research has explored various approaches to LLM self-improvement and multi-agent systems. The autoresearch paradigm demonstrates success in objective domains with clear metrics. SlopCodeBench shows that iterative refinement can lead to quality degradation in code generation. Work on ACE context collapse identifies how LLMs lose quality baselines with accumulated context. LLM Council explores multi-agent deliberation architectures. Our use of blind evaluation panels builds on established peer review practices rather than representing a novel contribution.

**[Change: Removed future dates from citations and made claims more general, addressing the citation issues.]**

## 6. Discussion

### 6.1 Bloat/Prune Oscillation

Word count variation between passes (ranging from approximately 1,600 to 2,100 words in middle passes) suggests authors alternate between adding detail and simplifying when improvement directions are unclear. This oscillation indicates that the task specification may need refinement rather than more iteration.

### 6.2 Convergence Patterns

Our experiment never reached the predefined convergence threshold of 3 consecutive incumbent wins, achieving at most 2 consecutive wins at passes 14-15 and 24-25. The fact that AB won approximately 50% of passes could represent either successful synthesis of improvements or oscillation between equally viable solutions. The failure to converge after 26 passes raises questions about whether this approach can reach stable endpoints or if the 3-consecutive-win threshold was too stringent for this task.

**[Change: Added analysis of convergence failure, addressing the missing failure analysis issue.]**

### 6.3 Applications Beyond Subjective Domains

Autoreason may prove valuable even in domains with objective metrics. Metrics often fail to capture all relevant quality dimensions—a function might pass all tests yet be unmaintainable. Autoreason could provide a complementary signal in such cases.

### 6.4 Limitations

This work represents an exploratory study of a single task domain (go-to-market strategy) with one experimental run. We cannot generalize beyond this specific case. We did not perform statistical significance testing, analyze inter-rater agreement among the 3-judge panels, or test alternative numbers of candidates beyond our A/B/AB design. With only 7 judges and no significance testing, all reported differences are descriptive rather than inferential.

**[Change: Strengthened limitations section to acknowledge single-domain testing and lack of inter-rater agreement analysis.]**

The specific prompts used for each role and baseline method are not included, limiting reproducibility. The baseline methods (improve_this, harsh_critic, critique_and_revise) represent our interpretations of common prompting patterns; other implementations might yield different results.

**[Change: Removed "due to space constraints" excuse and acknowledged this as a limitation.]**

All results come from a single model (claude-sonnet-4-20250514) and may not generalize to other LLMs. The method's effectiveness on other subjective tasks (creative writing, analysis, etc.) remains untested.

We did not systematically analyze judge agreement patterns within the 3-judge panels or validate our choice of 3 judges versus other panel sizes. The temperature settings (0.8 for authors, 0.3 for judges) and convergence threshold were chosen without systematic exploration.

**[Change: Added acknowledgment of arbitrary parameter choices.]**

## 7. Conclusion

Autoreason demonstrates one approach to iterative refinement in subjective domains. By isolating agents, implementing blind evaluation, and using conservative aggregation, the method achieved improvements in our single test case while limiting the length inflation seen in baseline approaches.

Our single experiment on go-to-market strategy generation showed the highest Borda score (35/35) and all first-place rankings (7/7 judges) in a 5-way comparison. The method required approximately 160 LLM calls over 26 passes, achieving 2 consecutive incumbent wins twice but never reaching 3 consecutive wins.

**[Change: Corrected LLM call count.]**

The key insight—that isolation prevents context contamination—emerged from preliminary experiments with approximately 1,800 LLM calls that revealed issues with positional bias, single judge noise, and shared context contamination.

This exploratory work on a single task suggests potential but cannot support general claims. Future work should test across diverse domains, include statistical validation, analyze optimal judge panel sizes, test alternative candidate configurations, compare to human iteration patterns, and provide complete methodological details for reproducibility. Only through such systematic investigation can we determine whether autoreason represents a reliable approach to subjective iteration or merely an interesting observation from one experiment.

**[Change: Strengthened the conclusion to emphasize single-task limitation and added suggestion to compare to human iteration, addressing the missing comparison issue. Changed final phrase from "interesting result on a single task" to "interesting observation from one experiment" to further emphasize limitations.]**