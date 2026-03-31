<p align="center">
  <h1 align="center">Autoreason</h1>
  <p align="center"><em>Autoresearch for subjective domains</em></p>
  <p align="center">
    <a href="paper/autoreason.pdf">Paper</a> · <a href="RESULTS.md">Full Results</a> · <a href="OVERVIEW.md">Overview</a>
  </p>
</p>

---

Autoreason is an iterative refinement method for LLM-generated content where no objective metric exists. It constructs a subjective fitness function through independent blind evaluation — the same way science uses peer review where math can use proofs.

> [!NOTE]
> The paper (`paper/autoreason.pdf`) covers all experiments and was itself written using autoreason with Opus and ground-truth critic access.

## How It Works

Each pass produces three competing versions of a document — the **incumbent** (A), an **adversarial revision** (B), and a **synthesis** (AB) — evaluated by a blind judge panel with no knowledge of which is which.

```
ORIGINAL TASK PROMPT (anchor — seen by all roles)
        │
        ▼
   ┌──────────┐
   │ Author A │ ─── generate initial version
   └────┬─────┘
        │
        ▼ ═══════════════════ LOOP ═══════════════════
        │
   ┌────┴──────┐
   │  Critic   │ ─── fresh agent, finds problems (no fixes)
   └────┬──────┘     optionally receives ground-truth data
        │
   ┌────┴──────┐
   │ Author B  │ ─── fresh agent, revises A based on critique
   └────┬──────┘
        │
   ┌────┴──────────┐
   │ Synthesizer   │ ─── fresh agent, merges best of A + B
   └────┬──────────┘     (randomized labels)
        │
   ┌────┴──────────────────────────────────────┐
   │          Judge Panel  (3 judges)          │
   │                                           │
   │  fresh agents · blind evaluation          │
   │  ranked choice · Borda count              │
   │  randomized labels + presentation order   │
   │                                           │
   │  A  ── the incumbent (unchanged)          │
   │  B  ── the adversarial revision           │
   │  AB ── the synthesis                      │
   └────┬──────────────────────────────────────┘
        │
        ├─── Winner = A  →  streak++
        └─── Winner ≠ A  →  streak = 0, winner becomes new A
        │
        ▼ ═══════════════════ /LOOP ══════════════════
          converged when A survives k=2 consecutive passes
```

Every role is a **fresh, isolated agent** with no shared context. The artifact is the thread of continuity, not the agent's memory.

<details>
<summary><strong>Why this architecture?</strong></summary>

<br>

LLMs exhibit compounding failure modes when iterating on subjective work. Each one maps to a specific architectural fix:

| Failure Mode | What Happens | How Autoreason Fixes It |
|:---|:---|:---|
| **Sycophancy** | "Improve this" becomes "make this more of what it already is" | A competes against adversarial alternatives; the judge picks the best, not the most polished |
| **Overcriticism** | The critic always finds something, even when the work is sound | The critic only identifies problems. Author B decides which are valid. If the critique was wrong, the judge picks A |
| **Overcompromise** | Synthesis hedges everything into a mushy average | AB is one of three options, not the default. If it hedged, the judge picks A or B |
| **Authorship bias** | An agent defends its own work while "incorporating feedback" | Every role is a fresh agent. No shared drafting history |
| **Scope drift** | Each iteration adds hedging, caveats, complexity | Judges evaluate against the original task prompt, not "which is most thorough" |
| **Context collapse** | After several rounds, output diverges from intent with no way to detect drift | The original task prompt anchors every pass. A is always a candidate — the loop can revert |

The connection to Karpathy's [autoresearch](https://x.com/karpathy) is direct:

| | Autoresearch | Autoreason |
|:---|:---|:---|
| **Generate** | Mutate code | Produce A, B, AB |
| **Test** | Run experiment, check val_bpb | Blind judge panel evaluates |
| **Keep/revert** | Better metric → keep | Judges pick best → advance |
| **Anchor** | Last known good commit | Original task prompt |
| **Drift prevention** | Objective metric | Blind judges + incumbent always a candidate |

</details>

---

## Results

Tested across 5 tasks with claude-sonnet-4 (go-to-market strategy, notification system design, remote work policy, competitive positioning, incident response). Each task ran autoreason to convergence plus four baselines at 15 iterative passes, evaluated by a 7-judge blind panel.

### The value is in the loop

A single autoreason pass (5 LLM calls) **loses** to simpler methods — harsh critic and critique-and-revise both outperform it at 1/5th the cost. With iteration, the picture reverses:

| Method | Avg Borda | Avg Rank | Tasks Won |
|:---|---:|---:|---:|
| **Autoreason** | **27.8 / 35** | **1.4** | **3 / 5** |
| Critique & revise | 22.4 | 2.0 | 2 / 5 |
| Harsh critic | 22.0 | 2.6 | 0 / 5 |
| Conservative | 17.6 | 3.6 | 0 / 5 |
| Improve this | 12.2 | 4.4 | 0 / 5 |

Autoreason never placed below 2nd. It excels on tasks with genuine tradeoffs (strategy, policy, incident response). Critique-and-revise wins on tasks with concrete technical requirements (system design, competitive positioning).

### What the improvement looks like

The initial Task 1 output was a generic startup playbook. After 14 passes of adversarial pressure:

| | Initial (pass 0) | Converged (pass 14) |
|:---|:---|:---|
| **Target** | "Mid-market engineering teams (50–500)" | Platform engineering at 200–1000 employees, quantified pain ($15K/incident × 6/yr) |
| **Pricing** | $49/user/month | $1,499/month per team ≤50 devs (matches buying motion) |
| **Revenue** | $100K MRR by Q4 with 3 people | $25K MRR by Q4, growing to 8 people |
| **Validation** | None | 50+ customer interviews, 75% pilot success rate |
| **Unit economics** | Not mentioned | CAC $2K · LTV $54K · LTV:CAC 27:1 · 90% gross margin |

The adversarial process didn't polish prose — it forced the proposal to get concrete. It killed the unrealistic revenue numbers.

### Key findings

> **Chain-of-thought judges** reduce convergence from 14 passes to 5 (3×) with no architecture changes — just adding "think step by step about each version" to the judge prompt.

> **Continuing past convergence hurts.** A 7-judge panel preferred pass 15 output over pass 25 by 6–1. The first convergence point is the quality ceiling.

> **Monte Carlo** (5 independent runs, same task): 80% convergence rate. Final outputs cluster tightly (1451–1660 words) regardless of path.

> **Game-theoretic validation** across 91 passes: 1.1% Condorcet cycle rate (near-perfect transitivity). ELO plateau by pass 5–10. Fully transitive pairwise dominance.

### Model scaling: a failure mode

> [!WARNING]
> With claude-sonnet-4-6 (stronger model), autoreason came **dead last** — Borda 7/35, zero first-place votes after 50 passes without converging.

The stronger model produced AB syntheses so consistently preferred by judges that the incumbent could never survive. The convergence mechanism assumes A can eventually become good enough that challengers can't improve on it. With a sufficiently capable model, this assumption breaks.

Potential remedies: score-based plateau detection, requiring AB to win by a margin, tiered model configs (stronger judge, weaker author). Open question.

---

## Ground-Truth Critic

When the domain has reference material — data, specs, a codebase — the critic should receive it. This turns "find things that sound wrong" into "verify every claim against the actual data."

Without ground-truth access, the initial Opus generation of this paper hallucinated a fabricated ablation study, fake confidence intervals, wrong model names, and incorrect role descriptions. With ground-truth access, the critic caught all four on pass 1.

| Role | Sees ground truth? | Why |
|:---|:---:|:---|
| **Critic** | ✓ | Verifies claims against evidence |
| **Author B** | ✓ | Revisions stay accurate |
| **Synthesizer** | ✓ | Merged output stays accurate |
| **Author A** | ✗ | First draft = what the model "thinks" it knows |
| **Judges** | ✗ | Evaluate quality, not accuracy (that's the critic's job) |

---

## Design Decisions

| Decision | Choice | Rationale |
|:---|:---|:---|
| Agent isolation | Fresh per role per pass | B re-emerged at passes 17–21 after 15 passes of irrelevance — a persistent agent would have learned to defer |
| Judge panel | 3 same-model judges | Averages out individual biases. Correlated biases remain — mixed-model panels untested |
| Evaluation method | Ranked choice + Borda count | No rubric injection. The task prompt is the rubric |
| Tiebreak | Conservative (incumbent wins) | Removed 3 unnecessary churn events in 26 passes |
| Convergence threshold | 2 consecutive A wins | Threshold 3 never reached in 26 passes. 2 converges at the quality plateau |
| Judge prompting | Chain-of-thought | 3× faster convergence, more decisive scores, zero architecture changes |

---

## Open Questions

1. **Mixed-model judge panel** — would decorrelated biases (sonnet + gpt-4o + gemini) change convergence behavior?
2. **Model scaling** — can architectural modifications recover autoreason's advantage with stronger models?
3. **Human evaluation** — do human judges agree with LLM judges?
4. **Other model families** — all current results are Anthropic. Does the method generalize?

---

## Quickstart

```bash
pip install litellm pyyaml

python experiments/v2/run_v2.py --task 1              # run to convergence
python experiments/v2/run_v2.py --task 1 --max-passes 20   # cap at 20
python experiments/v2/run_v2.py --task 1 --dry-run         # preview
```

Uses [litellm](https://docs.litellm.ai/) for model routing. Set the model in `config_v2.yaml` and the corresponding API key:

| Provider | Model format | Env var |
|:---|:---|:---|
| Anthropic | `anthropic/claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` |
| OpenRouter | `openrouter/anthropic/claude-sonnet-4` | `OPENROUTER_API_KEY` |
| Google | `gemini/gemini-2.5-pro` | `GEMINI_API_KEY` |

<details>
<summary><strong>Repository structure</strong></summary>

```
├── README.md                ← you are here
├── OVERVIEW.md              ← shareable intro
├── RESULTS.md               ← full findings + design space matrix
├── paper/                   ← LaTeX paper + charts
├── tasks/                   ← task prompts
├── experiments/
│   ├── v2/                  ← iterative loop, judge panel, fresh agents
│   │   ├── run_v2.py
│   │   ├── config_v2.yaml
│   │   ├── results_v2/           ← 5-task results
│   │   ├── results_multi_task/   ← multi-task comparison
│   │   ├── results_46_task02/    ← sonnet 4.6 scaling experiment
│   │   └── ...
│   ├── v1/                  ← single-pass, single judge, Monte Carlo
│   └── prior/               ← exploratory experiments
```

</details>

## License

MIT
