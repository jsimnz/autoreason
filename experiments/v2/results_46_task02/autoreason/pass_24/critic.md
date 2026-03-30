## Real Problems

### 1. The NSTL Role Is Structurally Unsustainable

One of four backend engineers is assigned full-time enforcement responsibilities: weekly gate audits, 48-hour escalation windows, two-business-day schedule recalculations, same-day slip presentations, conflict-of-interest monitoring. This is described as a collateral duty for someone who is also presumably writing code. The document never accounts for the engineering output lost to this overhead, and the four-engineer, six-month budget in Section 5 presumably does not either. The role as described is closer to a part-time project manager than an engineer with additional duties.

### 2. Gate 0 Cannot Actually Block Gates 1–4

The document states gates 1–5 "have no valid owner until Gate 0 resolves" and that the deadline is end of Week 2, Month 1. But Gates 1, 2, and 4 have their own deadlines at end of Week 4, Month 1 — only two weeks later. If Gate 0 slips even slightly, the window for owners to actually do the work behind Gates 1, 2, and 4 collapses to near zero. The slip analysis covers Gate 2/3 in detail but ignores this tighter dependency entirely.

### 3. The Conflict-of-Interest Rule Is Incomplete

The document says if the NSTL is "somehow assigned ownership of a gate item," a second engineer takes over enforcement for that gate. But the NSTL is one of four backend engineers. The document does not address what happens when the NSTL has a personal or professional interest in a gate resolving a particular way without formally owning it — for example, if the NSTL strongly prefers a specific technical architecture that depends on Gate 2 resolving as messaging-primary. Formal ownership is not the only vector for conflicts.

### 4. Both Gate Owners Must Sign Gate 4, But Only One Can Miss It

Gate 4 requires both the Product Owner and the Security Lead to sign. The consequence of a miss defaults to Configuration A. But the document gives no mechanism for handling the case where one owner signs and the other does not. Does one signature constitute a partial resolution? Does the dissenting owner's silence default to A? The two-owner requirement creates a deadlock scenario the document does not address.

### 5. The Runbook Repository Is Referenced But Never Defined

Gates resolve when a named individual posts written acknowledgment "to the runbook repository." This repository is mentioned nowhere else in the document. Its location, access controls, who can post to it, and whether non-engineers (product owner, analytics owner, security lead) have access are entirely unspecified. The entire enforcement mechanism depends on this repository existing and being accessible to people who may not normally use engineering tooling.

### 6. R=3 Is Unvalidated But the Sensitivity Range Treats It as the Center

The document correctly flags R=3 as an unvalidated working assumption and provisions for the upper bound of the sensitivity range (9%) pending Gate 3. But the sensitivity range itself (5–9%) is derived from the same unvalidated model with R varying. If R=3 is wrong, the range boundaries are also wrong. Provisioning for the "upper bound" of a range whose derivation depends on the assumption under question does not actually bound the risk.

### 7. The Flag Threshold System Has a Measurement Gap

Flag thresholds are defined in terms of peak demand in req/sec, but the table in Section 1.2 shows sustained averages, not peak demand. The provisioned floor is 5,200/sec and the peak factor is 6×, derived in Section 1.4. A sustained average of 521/sec with a 6× peak factor implies a peak of ~3,126/sec — which is in the ✓ band. But a sustained average near the ⚠ boundary of ~583/sec (3,500/sec ÷ 6) would hit the ⚠ threshold at peak. The table flags cells based on sustained averages without converting them to peak demand, making the flag assignments potentially misleading. The 20% DAU/MAU, 25/day cell is flagged ⚠→ at ~579/sec sustained, which implies a peak near 3,474/sec — just above the ⚠ threshold. But the 30% DAU/MAU, 20/day cell at ~694/sec sustained implies a peak of ~4,164/sec and is also flagged ⚠, yet these two scenarios have meaningfully different headroom situations that the shared flag obscures.

### 8. The Engineering Manager Is Both Gate 0 Owner and Escalation Target

The engineering manager owns Gate 0 and is also the escalation target when gate owners are unresponsive. If the engineering manager is the one who is slow to complete Gate 0, the NSTL is supposed to escalate — to the engineering manager. The document does not identify who sits above the engineering manager in the escalation chain, making this a dead end.

### 9. The Four-Week Slip Conclusion Is Asserted, Not Derived

The four-week slip scenario concludes with "approximately 0.5 weeks" of hardening time and declares it "not recoverable without scope reduction." The two-week slip arithmetic is shown explicitly. The four-week slip arithmetic is not. For a document that is otherwise precise about derivations, this is an inconsistency that matters: the four-week scenario is the one most likely to drive an emergency scope decision, and the calculation supporting that decision is absent.

### 10. Gate 5 Consequence Creates an Unacknowledged Spend Discrepancy

If Gate 5 is missed, the document says to treat spend as Configuration B "for spend cap purposes" and log it as a "known underestimate." Configuration C with users still on SMS during the nudge period is not equivalent to Configuration B — it could be more expensive than B depending on nudge timeline and conversion rate. Calling it a "known underestimate" without quantifying the potential range means the spend cap for Configuration C during launch is undefined, which is the period when SMS costs are hardest to control.