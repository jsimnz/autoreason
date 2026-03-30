## Real Problems with This Proposal

### 1. The WAND Estimate Is Structurally Broken Before It's Used

The document acknowledges WAND "cannot be meaningfully estimated until Day 7" and "a stable estimate requires Week 4," then builds the base digest email scenario around a 2M WAND figure anyway. The conservative/base/aggressive scenarios (1M/2M/3M) have no derivation. Where did 2M come from? This isn't a minor gap — it's the "largest single unknown in the volume model" by the document's own admission, and the infrastructure sizing depends on it.

### 2. The Consent Ledger Is Load-Bearing but Never Specified

The consent ledger appears repeatedly as the authoritative source for digest thresholds, eligible population counts, and compliance decisions. Its schema, consistency guarantees, failure modes, and ownership are never defined anywhere in this document. If it's eventually consistent, the Day 7 threshold derived from it may be stale by hours. If it's a database table, it's a single point of failure for multiple critical paths. The document mentions it as though it already exists.

### 3. The OTP GDPR "Legitimate Interests" Argument Is Cited but Not Made

The executive summary states the legal basis for the OTP carve-out is "a GDPR legitimate interests argument, analyzed in Section 6.3." Section 6.3 is not included in this document. This is not a formatting artifact — the legal justification for the system's most consequential compliance decision is missing. Fail-closed behavior for all other notifications is explicitly justified. The OTP exception is not.

### 4. The P-CB Tier Is Introduced and Then Cut Off

The priority tier table ends with P-CB and a note that "The rationale is in Section..." — the sentence is incomplete. The credential breach subsystem is described as "architecturally isolated with its own queue, worker pool, and capacity analysis," but the capacity analysis is not present. A 10M-recipient SMS blast is the highest-stakes operational event in the entire system and its architecture is literally mid-sentence.

### 5. The 35% DAU Assumption Has No Source

The document is explicit about the OneSignal opt-in source and its limitations, but the 35% DAU/MAU ratio is stated with no methodology, no benchmark, and no sensitivity analysis. For a social app, DAU/MAU ratios vary enormously (10%–60%+). SMS OTP volume, in-app delivery estimates, and alarm baselines all depend on this figure. It receives none of the scrutiny applied to push opt-in rates.

### 6. The Stability Assessment Logic Has a Silent Failure Mode

The alarm attribution rule states that an alarm firing at 23:55 contaminates Day N but an alarm firing at 22:00 on Day N−1 and still active at 00:01 on Day N does not contaminate Day N. This means a sustained multi-hour outage straddling midnight could leave both days "stable" depending on exact timing. The document acknowledges a narrow version of this (the 23:58 edge case) but the mitigation — logging to `baseline_instability_reason` — only helps after the fact. The baseline promotion logic can be gamed by outage timing.

### 7. The SQS FIFO Resharding Migration Procedure Is Cited but Not Present

The executive summary states "the procedure is specified in Section 2.4." Section 2.4 is not in this document. SQS FIFO resharding is a known operational hazard — message group rebalancing during a live migration can break the ordering guarantees that are the entire reason FIFO was chosen for P1. Citing a section that doesn't exist is not the same as specifying a procedure.

### 8. Load Test Parameters Are Undefined

The document repeatedly defers alarm thresholds to "load test baselines" and states load tests "run during the week before launch." The load test scenarios, target volumes, pass/fail criteria, and who owns running them are not specified. The entire alarm initialization methodology in Section 1.4 depends on load test output that has no defined scope. "500K/day sustained" for transactional email appears once with no justification for why that's the right target.

### 9. The IP Pool Warm-Up Schedule Is Promised but Not Delivered

The executive summary describes the digest/transactional IP pool separation as "a deliverability decision with direct revenue impact" and states the "warm-up schedule, complaint rate monitoring, and operational ownership are specified in Section 3.3." Section 3.3 is not included. IP pool warm-up is operationally specific — it requires day-by-day volume ramps. Referencing it without including it means the most operationally risky email decision has no actual specification.

### 10. The 8 Always-On P0 Instance Count Has Circular Validation

The document states "P0 workers are fixed at 8 always-on instances" and that "the derivation is in Section 2.5," then adds "that capacity must first be demonstrated sufficient through load testing." Section 2.5 is not present. The number 8 appears without its derivation, and the validation mechanism (load testing) is itself underspecified per problem 8 above. The claim that 8 instances handles P0 load at <5 second P95 is unverifiable from this document.

### 11. Phase Boundaries Are Described but Not Defined

Section 8 is referenced for phase definitions, team scope, and rotation policy, but Section 8 is not included. For a 4-engineer team on a 6-month timeline — which the document correctly identifies as the central constraint — the absence of actual scope boundaries means the feasibility claim in the executive summary cannot be evaluated.

### 12. The ±10 Point Decision Rule Threshold Is Inconsistently Justified

The document states that moving from 60/40 to 50/50 shifts push volume by ~5% (within tolerance) and 60/40 to 40/60 shifts it by ~10% (requires reassessment). But the trigger is defined as ±10 points from 60%, meaning 50/50 is at the boundary and would trigger recalibration despite being described as within tolerance. The justification and the rule don't align.