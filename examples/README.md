# Examples

Three sample prompts covering different subjective-work categories. Each is a single markdown file containing a task description.

| File | Domain | What it's testing |
|---|---|---|
| `gtm-strategy.md` | Go-to-market | Business strategy — needs grounding in specifics, not generic advice |
| `remote-work-policy.md` | HR / policy | Political tradeoffs, multi-stakeholder constraints |
| `incident-response.md` | Technical operations | Detailed process design with concrete artifacts |

## Run them

```bash
# Short smoke test (3 passes)
autoreason run --prompt-file examples/gtm-strategy.md --max-passes 3

# Full run — loop until convergence (up to 30 passes)
autoreason run --prompt-file examples/remote-work-policy.md

# With a specific model and judge count
autoreason run \
  --prompt-file examples/incident-response.md \
  --model anthropic/claude-sonnet-4-5 \
  --judges 5 \
  --max-passes 20
```

Outputs land in `runs/<timestamp>-<slug>/`. See the top-level README for the full artifact layout.

## Compare outputs

Running the same prompt with different models or judge counts produces comparable runs:

```bash
autoreason run --prompt-file examples/gtm-strategy.md --judges 3 --output runs/gtm-3j
autoreason run --prompt-file examples/gtm-strategy.md --judges 7 --output runs/gtm-7j
autoreason compare runs/gtm-3j runs/gtm-7j --judge
```
