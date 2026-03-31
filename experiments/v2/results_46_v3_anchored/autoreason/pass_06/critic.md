## Real Problems with This Proposal

### 1. The Opt-Out Staleness Problem Is Understated and Then Abandoned

The document correctly identifies the race condition in Section 2.4 and then... stops mid-sentence. The document ends before describing the mitigation plan it claims exists. Legal and product are asked to sign off on residual risk from a mitigation plan they cannot read. This is the highest-stakes item in the entire proposal — the one explicitly flagged as a legal and trust problem — and it's incomplete.

### 2. The Peak Throughput Model Has a Hidden Assumption That Breaks the Math

The formula `Daily volume × 0.90 ÷ (2 windows × 7,200 sec)` assumes 90% of notifications fall in exactly two 2-hour windows. But the sensitivity matrix applies this same peak multiplier to email volume, which the proposal explicitly states uses MAU (not DAU) as its denominator and "works regardless of app activity." Email to lapsed users doesn't concentrate in social traffic peaks. Applying the social traffic peak model to email inflates the email peak rate and makes the 1,500/sec sizing target harder to evaluate for correctness.

### 3. The SMS Volume Derivation Uses Undefended Constants

The formula `DAU × 0.30 × 0.10` is presented as a derivation, but both inputs (30% of DAU trigger a new session daily, 10% of logins require OTP) are asserted without any benchmark, source, or sensitivity range. For a system where the SMS budget sign-off is a hard gate on E2's work plan, the cost estimate rests entirely on two numbers with no stated basis. The proposal treats this as a solved problem by calling it "derived."

### 4. The 6× Peak Multiplier Is Inconsistently Applied

The document states the peak multiplier is "approximately equivalent to 6×" and then uses `Daily volume × 0.0625` in the sensitivity matrix. But 0.0625 applied to daily volume gives the rate over the peak window, not a multiplier over average rate. The average per-second rate for the planning basis is roughly 475/sec (41.1M ÷ 86,400). The peak rate is 838/sec. That's 1.76×, not 6×. The 6× figure appears to be the ratio of peak-window density to uniform distribution across the full day, which is a different and less useful number. Using it to characterize "peak multiplier" is misleading when evaluating whether 1,500/sec is adequate headroom.

### 5. The Calibration Checkpoint Default Undermines the Escalation Path

The ">60% above plan" path states that if stakeholder sign-off cannot be obtained within one week, "the default is horizontal scaling within the existing architecture with no new feature work in Month 3." This means the engineering team unilaterally freezes the product roadmap for a month as the fallback when stakeholders don't respond. That's not a safe default — it's a significant product decision being made by the team lead under time pressure. It's presented as a documented non-surprise, but it wasn't agreed to by stakeholders when this document was written.

### 6. The DLQ Ownership Split Creates an Unresolved Gap at Failure Time

E4 owns DLQ infrastructure; E2 owns triage and resolution. But the document doesn't specify who is paged at 2am when a DLQ fills. If E4 is paged (infrastructure owner), they cannot resolve a Twilio carrier rejection without E2. If E2 is paged, they may not have access or context to diagnose queue depth issues. The "runbooks" that supposedly resolve this are referenced but don't exist yet in the proposal. The ownership table creates the appearance of clarity without it.

### 7. The "Proven Infrastructure" Claim Is Partially Undercut by the Design

The executive summary cites "debuggable by an on-call engineer at 2am" as a justification for using Redis, PostgreSQL, and direct integrations. But the system uses Redis Sorted Sets for three of four queues, a Lua script for atomic cache invalidation with version fencing, a write-through cache with explicit race condition acknowledgment, and four separate DLQ pipelines. This is not a simple system. The "proven infrastructure" framing is accurate about the components but misleading about the operational complexity of the resulting architecture.

### 8. The QA Sign-Off Gate Is Circular

The executive summary flags QA approach (Section 7) as carrying "real risk if approved without deliberate acknowledgment" — but Section 7 is not included in this document. Stakeholders are being asked to acknowledge risk in a section they cannot read, for a system that is already partially scoped and has engineer assignments. This is the same problem as the opt-out mitigation plan: the document asks for sign-off on content that isn't present.

### 9. The Email Volume Is Suspiciously Flat Across All Scenarios

In the sensitivity matrix, email volume is 3.5M/day in every single scenario regardless of DAU/MAU ratio or notifications-per-user. No explanation is given for why email doesn't scale with engagement or DAU. If email is truly MAU-based and MAU is fixed at 10M, the flat number might be defensible — but the proposal doesn't say that. It just repeats 3.5M across every row without justification, which either reflects an unstated assumption or an error.