# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Document version:** 3.0
**Document owner:** Priya Mehta (notifications lead)
**Last revised:** [date]
**Status:** Draft — §0.4 lists incomplete sections and blocked decisions. Procedural apparatus in §0.1–§0.3 is recorded but not operative until the completion checklist in §0.4 is signed.

---

## Table of Contents

- §0 Preface
- §1.1 Scale and Load Estimates
- §1.2 Notification Tiers
- §1.3 Tier 1 Delivery Path
- §1.4 Push Notifications (APNs and FCM)
- §1.5 In-App Notification Store
- §1.6 Email Channel
- §1.7 SMS Channel
- §1.8 User Preference Management
- §1.9 Infrastructure
- §1.10 Failure Handling

---

## §0 Preface

### §0.1 Scope and Constraints

This document provides the technical design for the notification system. It is calibrated for a four-person backend team over six months. Infrastructure choices favor operational simplicity over theoretical capability. Limitations are stated explicitly rather than papered over. Every significant tradeoff names what is being given up and why that is acceptable given the constraints.

Two principles govern the entire document. First, every number that rests on an assumption states that assumption and identifies what measured data would replace it. Second, where a constraint cannot be resolved within this design's scope, the document states the limitation, the action required to resolve it, and who owns that action by name.

### §0.2 Named Owners and Escalation Chain

Contact information is recorded in the project kickoff checklist rather than this document because contact details change and belong in a single authoritative source. The kickoff checklist must be completed and signed before this document is distributed to any stakeholder. The project lead owns that step.

| Role | Name | Responsibility in this document |
|---|---|---|
| Notifications lead / document owner | Priya Mehta | All technical decisions; validation reviews; escalation first contact |
| Project lead | [name — required before distribution] | Kickoff checklist completion; escalation if Priya Mehta is unavailable; infrastructure purchasing sign-off |
| Product lead | [name — required before distribution] | Final escalation point; DM usage pattern clarification (§1.1.2); capacity decisions above sprint budget |

**This table must be fully populated before distribution.** A row with a placeholder name is a blocking defect. The project lead is responsible for providing both unnamed entries before the kickoff checklist is signed.

**Enforcement:** The kickoff checklist has a line item requiring both names before it can be signed. The kickoff meeting cannot be closed without a signed checklist. If the project lead attempts to distribute this document before the checklist is signed, Priya Mehta will not acknowledge the distribution as valid and will notify the product lead. This is a documented process, not a social norm.

**Simultaneous unavailability:** If both Priya Mehta and the project lead are simultaneously unavailable, the most senior available engineer assumes temporary ownership of all time-sensitive decisions, contacts the product lead within 24 hours using the kickoff checklist contact information, and designates a permanent replacement within 48 hours. This procedure requires the product lead's name to be recorded before it can function — a second reason the table must be populated before distribution.

### §0.3 Legal Review — Scope, Owner, Deadline, and Contingency

**What the legal review covers:** SMS and email channel implementation (§1.6 and §1.7) requires compliance verification for: TCPA consent requirements for SMS in the United States; CAN-SPAM and GDPR requirements for email including unsubscribe mechanics, data residency for EU users, and retention limits on notification preference data; and any jurisdiction-specific opt-in requirements for push notifications that the product's target markets impose beyond Apple and Google platform requirements.

**What the legal review does not cover:** Push notification delivery mechanics (§1.4), in-app notification store (§1.5), and all infrastructure decisions (§1.9) are not gated on this review. Work on those sections proceeds on the main timeline regardless of legal review status.

**Owner:** [Legal counsel name — required before distribution. Project lead is responsible for identifying this person.]

**Deadline:** Legal review must be complete by [date — set as 8 weeks before planned SMS/email implementation begins, ensuring at least two sprints for any required design changes. Project lead sets this date at kickoff].

**Contingency if deadline is missed — compliance is not a scheduling adjustment:**

If the legal review is not complete by the stated deadline, SMS and email implementation stops. Not "ships with reduced scope." Stops. Framing a missed compliance deadline as a scheduling problem that can be resolved by compressing implementation is precisely the scenario where TCPA, CAN-SPAM, and GDPR requirements get missed. The consequence is not a sprint delay; it is regulatory liability.

The actual contingency: the product lead is notified within 24 hours of the missed deadline. The project lead and legal counsel produce a revised completion date within one week. If the revised date allows two full sprints of implementation time before the six-month window closes, SMS and email proceed on the revised schedule. If it does not, SMS and email are descoped from v1 and documented as v2 work requiring a separate compliance-gated delivery. This decision requires product lead sign-off and is not made unilaterally by the backend team. The backend team does not implement SMS or email in any form — including a "partial" or "MVP" version — without a completed legal review.

### §0.4 Document Completion Status

This document is a draft. The following sections are incomplete. The procedural apparatus in §0.1–§0.3 is recorded here so it is not lost, but is **not operative** until this document is complete and the checklist below is signed by the project lead and product lead.

| Missing section | What it contains | What cannot be decided without it |
|---|---|---|
| §1.2.2 (partial) | Tier 2 delivery behavior, quiet hours, batching rules | Channel selection logic for DMs and mentions; worker pool sizing for Tier 2 |
| §1.3 | Tier 1 delivery path detail | Whether the push → SMS → email sequence is correct; SMS cost estimates for Tier 1 failures |
| §1.4 | APNs and FCM integration, token management, push failure rates | Expected push failure rate, which determines SMS fallback volume and cost |
| §1.5 | In-app notification store design | Read/unread state management; store retention policy |
| §1.6 | Email channel design | ESP selection; unsubscribe mechanics; GDPR data residency approach |
| §1.7 | SMS channel design | Provider selection; TCPA consent flow; cost model |
| §1.8 | User preference management | Preference data model; what users can and cannot control; UI constraints |
| §1.9 | Infrastructure choices | Queue technology selection; worker deployment; auto-scaling configuration |
| §1.10 | Failure handling | Dead-letter queue design; retry logic; on-call paging thresholds |

**Decisions blocked until completion:**
- Infrastructure purchasing (blocked by §1.9)
- SMS/email vendor selection (blocked by §1.6, §1.7, §1.10)
- Tier 1 channel sequence finalization (blocked by §1.3, §1.4 — specifically push failure rate analysis)
- Sprint planning beyond the first two sprints (blocked by §1.8, §1.9, §1.10)

**Completion target:** [date — set at kickoff by project lead]. Both the project lead and product lead sign this section when the document is complete. Their signatures make the procedural apparatus in §0.1–§0.3 operative.

---

## Part 1: Technical Design

### §1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app. The working figure is 2.5M DAU (25% DAU/MAU ratio). This ratio must be validated against actual product analytics at the 14-day post-launch review.

#### §1.1.1 Compounded Assumption Risk and Provisioning Headroom

The peak throughput figure used for provisioning is derived by multiplying three independent estimates:

1. **DAU/MAU ratio:** assumed at 25% (2.5M DAU). Plausible range: 20–45%.
2. **Notification rate per DAU:** assumed per event type in §1.1.2. Drawn from general social app benchmarks, not product-specific data.
3. **Evening peak multiplier:** assumed at 3×. Not supported by product-specific data.

These three assumptions are correlated in the upward direction. A highly engaged user base tends to produce higher values on all three dimensions simultaneously because engagement, notification density, and peak concentration move together. The most likely failure mode — actual load significantly exceeding the estimate — is also the scenario where all three assumptions are wrong in the same direction at once. That is not an edge case; it is the central risk.

**Provisioning headroom: 2×, with an explicit account of what it does and does not cover.**

The provisioning target uses 2× headroom over the estimated peak. This is a cost decision made under uncertainty, not an engineering determination that 2× is the correct figure.

What 2× actually provides: if the three assumptions are collectively off by a factor of up to 2 in the upward direction, the provisioning target is sufficient. That is the entire claim.

What 2× does not cover: if the assumptions are collectively wrong by more than a factor of 2 — which the correlated upward risk makes a plausible scenario — the provisioning target is insufficient. The mitigation is not additional static provisioning calibrated to an even less supported worst-case number. It is the queue buffering architecture (which absorbs spikes while auto-scaling responds) and the validation process (which replaces assumptions with measurements and triggers immediate escalation if thresholds are breached).

**Why not higher static headroom:** Provisioning to 4× or 6× rests on equally unsupported numbers. A 6× worst-case multiplier is an estimate of an estimate — it adds cost without adding confidence. The correct response to this level of uncertainty is faster measurement and faster adjustment, not higher static allocation. The 2× headroom choice and the validation process are a package; one without the other is insufficient.

#### §1.1.2 Notification Volume Estimates

**DM volume — clarification required before infrastructure purchasing:**

The direct message row below assumes each DM sender reaches one recipient per day. This is a placeholder. If the product supports group messaging and the average sender reaches multiple recipients, DM notification volume scales linearly with that average. A product where senders average five recipients per day generates 2.5M DM notifications daily rather than 500,000 — nearly doubling total estimated volume and materially changing the provisioning target.

**Required action:** The product lead must specify the expected DM usage pattern (1-to-1 vs. group; if group, expected average recipients per sender) before any infrastructure purchasing decision is made.

**Owner:** [product lead name — from §0.2 table]
**Required by:** [date — at least 2 weeks before any infrastructure purchasing commitment; project lead sets this date at kickoff]

**What happens if this clarification is not received by the deadline:** Infrastructure purchasing does not proceed on the low-end assumption. The project lead must document in writing that the purchase is being made on an unvalidated assumption and obtain explicit product lead sign-off acknowledging the risk. That sign-off is recorded in the project decision log before the purchase is made, not after. If the project lead cannot obtain product lead sign-off, the purchase does not happen. This ensures the person with budget authority is aware they are approving a purchase based on an assumption that could be wrong by a factor of 5.

| Event type | Rate assumption | Basis | Daily volume |
|---|---|---|---|
| Post liked | 15% of DAU trigger one like notification | General benchmark | 375,000 |
| Comment received | 8% of DAU receive one comment notification | General benchmark | 200,000 |
| New follower | 5% of DAU | General benchmark | 125,000 |
| Mention | 3% of DAU | General benchmark | 75,000 |
| Direct message | 20% of DAU send at least one; 1 recipient per sender (placeholder — see note above) | Placeholder | 500,000 |
| System/product | 2% of DAU | — | 50,000 |
| **Total baseline** | | | **~1.3M/day** |

**The 1.3M/day total is contingent on the DM clarification.** All downstream calculations use this figure because a decision must be made for initial provisioning and the low-end assumption is the only figure available. Any infrastructure purchasing decision made before the DM clarification is received must be logged as described above.

#### §1.1.3 Peak Throughput and Spike Buffering

- Average over 24 hours: ~15 notifications/second
- Average over active hours (08:00–22:00, 14 hours, 80% of volume): ~21/second
- Evening peak at 3× active-hours average: ~63/second
- Provisioning target with 2× headroom: **~130 notifications/second**

**Tier 3 "immediate" preference load impact:** The load model assumes 20% or fewer users select "immediate" delivery for Tier 3 notifications rather than the default hourly digest. This 20% figure is a chosen trigger point for review, not a data-derived estimate. If more than 20% of users select "immediate," effective peak throughput rises because batching compression is reduced. The impact is contained to the Tier 3 worker pool, which is provisioned separately, but aggregate system load increases. The 14-day validation review must measure the actual fraction and recalculate if it exceeds 20%.

**Spike buffering:** Auto-scaling typically provisions new instances within 2–5 minutes. During that window, a spike above current capacity accumulates in the queue. At 130/second provisioning and a 3× spike (390/second), the queue accumulates approximately 58,500 jobs during a 2.5-minute gap (~58MB at ~1KB per job). At 6×, approximately 117,000 jobs (~117MB). Both are within standard queue capacity. What changes at 6× is the time to drain the backlog after auto-scaling completes. Queue depth monitoring surfaces this to the on-call engineer before the backlog reaches problematic depth.

All queue consumers and delivery workers are deployed with auto-scaling configured from day one. Baseline instance counts are set to handle 2× the projected peak at launch — intentionally over-provisioned as insurance against the compounded assumption uncertainty in §1.1.1.

#### §1.1.4 Load Validation — Process, Decision Rules, and Enforcement

**The core coordination rule:** Capacity reductions require 60-day confirmation. Capacity increases do not.

This asymmetry is deliberate. The cost of maintaining excess capacity for 60 days is a known, bounded expense. The cost of reducing capacity prematurely and then experiencing degraded delivery is unbounded — it affects user experience and may not be immediately visible if degradation manifests as increased latency rather than outright failure.

**Required instrumentation, in place before launch:**
- Per-second notification creation rate by tier and subtype, p50/p95/p99 over rolling 5-minute windows
- Queue depth per queue, sampled every 30 seconds
- Worker throughput per pool (notifications processed per second)
- DAU count, updated daily from product analytics
- Fraction of users with "immediate" Tier 3 delivery preference selected, updated daily

**14-day review:** Produces a written measurement report replacing assumed per-user notification rate, peak multiplier, and Tier 3 "immediate" preference fraction with measured values. The report does not claim measured values are final steady-state — the product may still be growing and user patterns stabilizing. It claims they are better than pre-launch assumptions. The 60-day review exists specifically to catch cases where day-14 measurements proved unrepresentative.

One exception to the "measurement only" scope of the 14-day review: if measurements indicate capacity is materially insufficient — queue depth sustained above 200,000 or p99 delivery latency for Tier 1 exceeds 30 seconds — capacity increases are implemented immediately without waiting for the 60-day review.

**60-day review:** Reassesses whether day-14 measurements have proven representative of ongoing behavior. Capacity reductions identified at day 14 are implemented here, not earlier.

**Immediate triggers** (either review is also triggered before its scheduled date if):
- Actual peak throughput exceeds 200/second sustained for more than 10 minutes
- Queue depth exceeds 500,000 messages during non-incident conditions
- DAU/MAU ratio exceeds 35%
- Fraction of users with "immediate" Tier 3 preference exceeds 20%

**Decision rules — headroom standard:**

The target state after any review is: baseline instance counts set to handle **1.5× the measured sustained peak**. This standard applies without exception.

| Measured outcome | Action |
|---|---|
| Actual peak within 50% of 130/second in either