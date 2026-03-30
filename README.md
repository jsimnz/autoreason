# Autoreason

**Autoresearch for subjective domains.**

Autoreason is an iterative refinement method for LLM-generated content where no objective metric exists. It constructs a subjective fitness function through independent blind evaluation — the same way science uses peer review where math can use proofs.

## The Core Idea

```
                      ┌─────┐
                      │  A  │  the original
                      └──┬──┘
                         │
                    ┌────┴────┐
                    │ critic  │  find problems
                    └────┬────┘
            ┌────────────┼──────────────┐
            ▼            ▼              ▼
         ┌──────┐    ┌────────┐    ┌──────────┐
         │  A   │    │   B    │    │    AB    │
         │ keep │    │ change │    │synthesize│
         └──┬───┘    └───┬────┘    └────┬─────┘
            └────────────┼──────────────┘
                         ▼
                   ┌───────────┐
                   │blind judge│  which best
                   │  panel    │  accomplishes
                   └─────┬─────┘  the task?
                         │
                         ▼
                   winner → new A
                   repeat until A survives
```

**A** is conservatism: the current version is fine, the changes made things worse. **B** is adversarial editing: the critique found real problems and the revision fixes them. **AB** is what happens when you ask an agent to be objective: both versions got some things right, here's a synthesis that keeps the best of each. The judge decides which of these three framings actually produced the best result, with no knowledge of which is which.

## The Problem This Solves

LLMs exhibit compounding failure modes when used for iterative refinement on subjective work:

| Failure Mode | What Happens | Why It Happens |
|---|---|---|
| **Sycophancy** | Ask it to improve something and it strengthens whatever you hand it, regardless of whether the argument is actually sound | The model follows the implied instruction: "make this better" becomes "make this more of what it already is" |
| **Overcriticism** | Ask it to find problems and it always finds something, even when the work is sound | The instruction to critique is interpreted as an instruction to change — saying "this is fine" feels like task failure |
| **Overcompromise** | Ask it to synthesize two perspectives and it hedges everything, producing a mushy average instead of selecting the best answer per dimension | The model treats both inputs as equally valid and tries to include something from each, losing the sharpness of either |
| **Authorship bias** | An agent that wrote version A will defend it even while "incorporating feedback" from a critique | The drafting history in the context window creates a completion bias toward continuing the established pattern |
| **Scope drift** | Each iteration adds hedging, caveats, and complexity — the output bloats away from what was asked for | No anchor back to the original task; the model optimizes for "impressiveness" rather than "accomplishes the task" |
| **Context collapse** | After several review cycles, the output diverges from the original intent with no mechanism to detect or reverse the drift | Each round takes the previous round's output as input — by round 3, the original signal has decayed through layers of revision |

The output is shaped more by how you prompt than by what's actually better. There is no independent evaluation happening — just a mirror.

## How Autoreason Addresses Each Failure Mode

| Failure Mode | Architectural Fix |
|---|---|
| **Sycophancy** | The incumbent (A) competes against adversarial alternatives — the judge picks the best version, not the most polished one |
| **Overcriticism** | The critic only finds problems. A separate Author B decides which criticisms are valid enough to act on. If the critique was wrong, the judge picks A and the criticism is discarded |
| **Overcompromise** | The synthesizer (AB) is one of three options, not the default. If the synthesis hedged too much, the judge picks A or B instead |
| **Authorship bias** | Every role is a fresh agent with no shared context. Author B never saw Author A's drafting process. The synthesizer doesn't know which version came first |
| **Scope drift** | Judges evaluate against the original task prompt — "which version best accomplishes what was asked for" — not "which is most thorough" |
| **Context collapse** | The original task prompt is the anchor throughout all passes. The incumbent (A) is always a candidate, so the loop can revert to stability at any point |

## v2 Architecture

Every role is a fresh, isolated agent with no shared context. The artifact is the thread of continuity, not the agent's memory.

```
ORIGINAL TASK PROMPT (anchor — seen by all roles)
        │
        ▼
   ┌──────────┐
   │ Author A │   generate initial version
   └────┬─────┘
        │
        ▼ ══════════════════ LOOP ══════════════════
        │
   ┌────┴──────┐
   │ Critic    │   fresh agent, sees current A
   └────┬──────┘   finds problems — no fixes
                   (optional: ground-truth data for fact-checking)
        │
   ┌────┴──────┐
   │ Author B  │   fresh agent, sees task + A + critique
   └────┬──────┘   revises A to address valid criticisms
        │
   ┌────┴───────────┐
   │  Synthesizer   │   fresh agent, sees task + A + B (randomized)
   └────┬───────────┘   merges the strongest elements of each -> AB
        │
        ▼
   ┌───────────────────────────────────────────┐
   │            Judge Panel (3 judges)         │
   │  fresh agents, blind evaluation           │
   │  ranked choice + Borda count              │
   │                                           │
   │  chooses best of:                         │
   │    A  — the incumbent (unchanged)         │
   │    B  — the adversarial revision          │
   │    AB — the synthesis (best of both)      │
   └────┬──────────────────────────────────────┘
        │
        ├── Winner = A → streak++
        └── Winner = B or AB → streak = 0, winner becomes new A
        │
        ▼ ══════════════════ /LOOP ══════════════════
          repeat until A streak = 2 (converged)
```

### Why It Works

| | Autoresearch | Autoreason |
|---|---|---|
| **Generate** | Mutate code | Produce A, B, AB |
| **Test** | Run experiment, check val_bpb | Independent judge panel evaluates |
| **Keep/revert** | Better metric → keep | Judges pick best → advance |
| **Anchor** | Last known good commit | Original task prompt |
| **Drift prevention** | Objective metric | Blind judges + incumbent always a candidate |

## Key Results

Tested across 5 tasks (go-to-market strategy, notification system design, remote work policy, competitive positioning, incident response) with claude-sonnet-4. Each task ran autoreason to convergence plus four baselines at 15 iterative passes each, evaluated by a 7-judge blind panel.

### Iteration Is Where the Value Lives

A single autoreason pass (5 LLM calls) loses to simpler methods. Harsh critic and critique-and-revise both outperform it at 1/5th the cost. But with iteration, the picture reverses:

| Method | Avg Borda (max 35) | Avg Rank | Tasks Won |
|---|---|---|---|
| **autoreason** | **27.8** | **1.4** | **3/5** |
| critique & revise | 22.4 | 2.0 | 2/5 |
| harsh critic | 22.0 | 2.6 | 0/5 |
| conservative | 17.6 | 3.6 | 0/5 |
| improve this | 12.2 | 4.4 | 0/5 |

Autoreason won tasks 1, 3, 5 and placed second on 2 and 4 — never below 2nd. It excels on tasks with genuine tradeoffs (strategy, policy, cross-timezone incident response). Critique-and-revise wins on tasks with concrete technical requirements (system design, competitive positioning) where a direct find-and-fix loop is more efficient.

### Qualitative Improvement

The initial Task 1 output was a generic startup playbook. After 14 passes:

| Dimension | Initial (pass 0) | Converged (pass 14) |
|---|---|---|
| Target | "Mid-market engineering teams (50-500 employees)" | Platform engineering at 200-1000 employee companies, quantified pain (6 incidents/year × $15K = $90K cost) |
| Pricing | $49/user/month (generic SaaS) | $1,499/month per team up to 50 devs (matches actual buying motion) |
| Revenue target | $100K MRR by Q4 with 3 people | $25K MRR by Q4, growing to 8 people with quarterly hires |
| Validation | None | 50+ customer interviews, pilot results, 75% incident reduction in 30 days |
| Unit economics | Not mentioned | CAC $2K, LTV $54K, LTV:CAC 27:1, 90% gross margin |

The adversarial process didn't just polish the prose — it forced the proposal to get concrete. The most telling change: the adversarial process killed the unrealistic revenue numbers.

### Chain-of-Thought Judges (3x Faster Convergence)

Adding "think step by step about each version" to the judge prompt — no architecture changes — reduced convergence from 14 passes to 5 on Task 1. CoT judges produce more decisive scores (A winning at 8–9 vs baseline's 6–7). The reasoning step acts as a debiasing mechanism: judges must articulate specific strengths before committing to a ranking.

### Convergence and Stopping

All 5 tasks converged at threshold k=2, requiring 9–28 passes. Continuing past convergence hurts: a 7-judge panel preferred the pass 15 output over pass 25 by 6–1. The first convergence point is the quality ceiling.

Monte Carlo analysis (5 independent runs, same task): 80% convergence rate. Final word counts clustered tightly (1451–1660) despite variable path lengths — the loop reaches a similar quality ceiling regardless of the path taken.

### Game-Theoretic Validation

Retroactive analysis across 91 passes: only 1 Condorcet cycle (1.1% — nearly perfect transitivity). ELO ratings plateau by pass 5–10. Pairwise dominance is fully transitive: autoreason > critique-and-revise > harsh_critic > conservative > improve_this. No rock-paper-scissors dynamics.

### Model Scaling: A Failure Mode

Running autoreason with a stronger model (claude-sonnet-4-6) on Task 2 produced a complete reversal: **autoreason came dead last** (Borda 7/35, zero first-place votes). Over 50 passes, A won only 6 times (12%). The stronger model produced AB syntheses so consistently preferred by judges that the incumbent could never survive a challenge.

This is structurally different from the bloat/prune oscillation. With Sonnet 4, A occasionally won on close calls and tiebreaks, creating windows for convergence. With 4.6, judges were decisive enough (scores of 8–9 for AB) to never let A through.

The implication: the convergence mechanism assumes the incumbent can eventually become good enough that fresh challengers cannot improve on it. When the model is capable enough that synthesis reliably produces a better version, this assumption breaks. Potential remedies: score-based plateau detection, requiring AB to win by a margin, tiered model configs (stronger judge, weaker author). Open question.

### Constrained Tasks

Adding a 1000-word limit and 6 required sections eliminated word count oscillation but made convergence harder — specific constraints give the critic a verifiable checklist that always finds violations. B won 18 of 25 passes (72%). Whether the loop would have converged given more passes is unknown.

## Ground-Truth Critic

When the domain has reference material — experimental data, source documents, specs, a codebase — the critic should receive it. This turns the critic from "find things that sound wrong" into "verify every claim against the actual data."

We discovered this while running autoreason on the paper itself. Without ground-truth access, the initial Opus generation hallucinated a fabricated ablation study, fake confidence intervals, wrong model names, and incorrect role descriptions. With ground-truth access (the actual experiment results), the critic caught all four on the first pass.

The pattern:
- **Critic** gets the artifact AND the ground-truth data. Verifies claims against reality.
- **Author B and Synthesizer** also get ground-truth data to ensure revisions stay accurate.
- **Author A** (initial generation) works from the task prompt only — the first draft represents what the model "thinks" it knows. The critic corrects it against what's actually true.
- **Judges** see the task prompt and the versions only. They evaluate quality, not accuracy — accuracy is the critic's job.

## Design Decisions

| Decision | What We Chose | Why |
|---|---|---|
| Agent isolation | Fresh per role per pass | Prevents authorship bias. B re-emerged at passes 17-21 after 15 passes of irrelevance — a persistent agent would have learned to defer |
| Judge panel | 3 same-model judges | Averages out individual biases. Correlated biases remain (all sonnet) — mixed-model panels untested |
| Evaluation | Ranked choice + Borda count | No rubric injection. The task prompt is the rubric |
| Tiebreak | Conservative (incumbent wins) | Removed 3 unnecessary churn events in 26 passes |
| Convergence | 2 consecutive A wins | Threshold of 3 was too strict (never reached in 26 passes). 2 converges at the quality plateau |
| Judge prompting | Chain-of-thought | 3x faster convergence, more decisive scores, no architecture changes |

## Paper

The 6-page paper (`paper/autoreason.tex`) covers all experiments and was itself written using autoreason with claude-opus-4. See `paper/autoreason.pdf`.

## Repository Structure

```
├── README.md              ← you are here
├── OVERVIEW.md            ← shareable intro (starts with Karpathy hook)
├── RESULTS.md             ← full findings, trajectory data, design space matrix
├── paper/                 ← LaTeX paper + charts
├── tasks/                 ← task prompts used across all experiments
├── experiments/
│   ├── v2/                ← current: iterative loop, judge panel, fresh agents
│   │   ├── run_v2.py
│   │   ├── config_v2.yaml
│   │   ├── results_v2/          ← 5-task results
│   │   ├── results_multi_task/  ← multi-task comparison
│   │   ├── results_46_task02/   ← sonnet 4.6 scaling experiment
│   │   └── ...
│   ├── v1/                ← original: single-pass, single judge, Monte Carlo
│   └── prior/             ← exploratory experiments (blind eval, comparison, matrix)
```

## Running

```bash
pip install litellm pyyaml

# Dry run
python experiments/v2/run_v2.py --task 1 --dry-run

# Single task, unlimited passes
python experiments/v2/run_v2.py --task 1

# Cap at 20 passes
python experiments/v2/run_v2.py --task 1 --max-passes 20
```

Uses [litellm](https://docs.litellm.ai/) for model routing — any supported provider works. Set the model in `config_v2.yaml` and the corresponding API key in your environment:

| Provider | Model format | Environment variable |
|---|---|---|
| Anthropic | `anthropic/claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` |
| OpenRouter | `openrouter/anthropic/claude-sonnet-4` | `OPENROUTER_API_KEY` |
| Google | `gemini/gemini-2.5-pro` | `GEMINI_API_KEY` |
| Any OpenAI-compatible | `openai/model-name` + `api_base` | `OPENAI_API_KEY` |

## Open Questions

1. **Mixed-model judge panel** (sonnet + gpt-4o + gemini) — would decorrelated biases change convergence behavior?
2. **Model scaling** — can architectural modifications (score-based plateau detection, asymmetric evaluation, tiered models) recover autoreason's advantage with stronger models?
3. **Human evaluation** — do human judges agree with LLM judges on which outputs are better?
4. **Other model families** — all current results are Anthropic. Does the method generalize to GPT-4o, Gemini, open-weight models?

## License

MIT
