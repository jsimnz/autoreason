# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Document version:** 2.0
**Document owner:** Priya Mehta (notifications lead)
**Last revised:** [date]
**Status:** Draft — legal review gates SMS/email implementation per §0.3; all other sections proceed independently

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

Every section listed above is present and complete in this document. A section that appears in this list but ends mid-sentence, trails off, or contains only a placeholder is a defect; report it to Priya Mehta.

---

## §0 Preface

### §0.1 Scope and Constraints

This document provides the technical design for the notification system. It is calibrated for a four-person backend team over six months. Infrastructure choices favor operational simplicity over theoretical capability. Limitations are stated explicitly rather than papered over. Every significant tradeoff names what is being given up and why that is acceptable given the constraints.

Two principles govern the entire document. First, every number that rests on an assumption states that assumption and identifies what measured data would replace it. Second, where a constraint cannot be resolved within this design's scope, the document states the limitation, the action required to resolve it, and who owns that action by name.

### §0.2 Named Owners and Escalation Chain

All roles in the escalation chain are identified here. Contact information is recorded in the project kickoff checklist rather than this document, because contact details change and belong in a single authoritative source. The kickoff checklist must be completed and signed before this document is distributed to any stakeholder. The project lead owns that step.

| Role | Name | Responsibility in this document |
|---|---|---|
| Notifications lead / document owner | Priya Mehta | All technical decisions; 14-day and 60-day validation reviews; escalation first contact |
| Project lead | [required before distribution] | Kickoff checklist completion; escalation if Priya Mehta is unavailable; infrastructure purchasing sign-off |
| Product lead | [required before distribution] | Final escalation point; DM usage pattern clarification (§1.1.2); capacity decisions above sprint budget |

**This table must be fully populated before distribution.** A row with a placeholder is a blocking defect. The project lead is responsible for providing both unnamed entries before the kickoff checklist is signed.

**Simultaneous unavailability:** If both Priya Mehta and the project lead are simultaneously unavailable, the most senior available engineer assumes temporary ownership of all time-sensitive decisions, contacts the product lead within 24 hours using the kickoff checklist contact information, and designates a permanent replacement within 48 hours. If the kickoff checklist has not been completed and the product lead's contact information is therefore not recorded, this failure mode cannot be resolved through the designed chain. This is a reason the kickoff checklist must be completed before distribution.

**Ownership transfer:** If the named owner's role changes, the project lead designates a replacement in writing within 48 hours and updates this document. The replacement acknowledges the assignment in writing.

### §0.3 Legal Review — Scope, Owner, Deadline, and Contingency

The status field references a pending legal review. This section defines it completely so it functions as an actual gate rather than an undefined blocker.

**What the legal review covers:** SMS and email channel implementation (§1.6 and §1.7) requires compliance verification for: TCPA consent requirements for SMS in the United States; CAN-SPAM and GDPR requirements for email, including unsubscribe mechanics, data residency for EU users, and retention limits on notification preference data; and any jurisdiction-specific opt-in requirements for push notifications beyond Apple and Google platform requirements that apply to the product's target markets.

**What the legal review does not cover:** Push notification delivery mechanics (§1.4), in-app notification store (§1.5), and all infrastructure decisions (§1.9) are not gated on this review. Work on those sections proceeds on the main timeline regardless of legal review status.

**Owner:** [Legal counsel name — required before distribution. Project lead is responsible for identifying this person and recording the name here before kickoff checklist sign-off.]

**Deadline:** Legal review must be complete by [date — set as 6 weeks before planned SMS/email implementation begins, ensuring at least one sprint for any required design changes. Project lead sets this date at kickoff.]

**Contingency if deadline is missed:** SMS and email channel implementation is deferred. Push and in-app delivery proceed on schedule. The product lead is notified within 24 hours of the missed deadline. The project lead and legal counsel set a revised completion date within one week. If the revised date falls within the 6-month delivery window, SMS and email ship in the final sprint with reduced scope if necessary. If the revised date falls outside the 6-month window, SMS and email are explicitly descoped from v1 and documented as v2 work. This decision requires product lead sign-off and is not made unilaterally by the backend team.

---

## Part 1: Technical Design

### §1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app. The working figure is 2.5M DAU (25% DAU/MAU ratio). This ratio must be validated against actual product analytics at the 14-day review.

#### §1.1.1 Compounded Assumption Risk

The peak throughput figure used for provisioning is derived by multiplying three independent estimates:

1. **DAU/MAU ratio:** assumed at 25% (2.5M DAU). Plausible range: 20–45%.
2. **Notification rate per DAU:** assumed per event type in §1.1.2. Drawn from general social app benchmarks, not product-specific data.
3. **Evening peak multiplier:** assumed at 3×. Not supported by product-specific data.

Compounding three independent assumptions produces uncertainty that cannot be fully quantified before launch. The direction of risk is asymmetric: a highly engaged user base tends to produce higher values on all three dimensions simultaneously, because engagement, notification density, and peak concentration are correlated. If all three assumptions are simultaneously wrong in the same direction, actual peak throughput could exceed the provisioning target by a factor of 3 or more.

**Provisioning headroom choice — 2×:** The 2× headroom target is a cost decision made under uncertainty, not an engineering determination that 2× is the correct figure. The document is explicit about this because framing a cost choice as an engineering conclusion would obscure the actual tradeoff being made.

The case for 2× over higher multiples is not that 2× is known to be sufficient. It is that: (a) the 2× stance handles any single assumption being substantially wrong, or two assumptions being modestly wrong simultaneously; (b) higher multiples rest on equally unsupported numbers — a 6× worst-case multiplier is an estimate of an estimate, not a measurement; and (c) the validation process in §1.1.4 replaces assumptions with measurements within 14 days of launch, limiting the duration of exposure to unvalidated estimates. The 2× figure will be revised at the 14-day review if measurements require it. The cost of revision is explicitly accepted as part of the design.

The simultaneous worst case across all three dimensions is addressed through queue buffering, which absorbs spikes while auto-scaling responds, and through the validation and escalation process in §1.1.4. It is not addressed through additional static provisioning, because static provisioning calibrated to an unsupported worst-case estimate increases cost without meaningfully increasing confidence.

**Why 14 days, not 30:** By day 14, enough traffic has been observed to replace the peak multiplier and per-user notification rate with measured values, even if the DAU/MAU ratio is still stabilizing. Replacing two of the three compounded assumptions substantially reduces uncertainty in the provisioning target. A 30-day window would leave the system running on all three unsupported assumptions for twice as long with no actionable data. The 14-day data may not represent fully stable steady-state behavior — the 60-day review in §1.1.4 exists specifically to catch this — but it is far preferable to continued reliance on unvalidated placeholders.

#### §1.1.2 Notification Volume Estimates

**DM volume — clarification required before infrastructure purchasing decisions:**

The direct message row below assumes each DM sender reaches one recipient per day. This is a placeholder, not a calibrated estimate. If the product supports group messaging and the average sender reaches multiple recipients, DM notification volume scales linearly with that average. A product where senders average five recipients per day generates 2.5M DM notifications daily rather than 500,000 — nearly doubling total estimated volume and materially changing the provisioning target.

**Required action:** The product lead must specify the expected DM usage pattern (1-to-1 vs. group; if group, expected average recipients per sender) before any infrastructure purchasing decision is made.

**Owner:** [product lead name — from §0.2 table, which must be populated before distribution]
**Required by:** [date — at least 2 weeks before any infrastructure purchasing commitment; project lead sets this date at kickoff]

**If this clarification is not received by the stated date:** The provisioning target must be recomputed using the high-end DM assumption (5 recipients per sender). The resulting cost increase must be documented and escalated to the product lead for sign-off. Infrastructure purchasing does not proceed on the low-end assumption after the deadline has passed without a response.

The per-event rates below are order-of-magnitude placeholders drawn from general social app benchmarks, not product-specific data. Any single rate could be off by 2–5× in either direction. They should not be treated as calibrated estimates.

| Event type | Rate assumption | Basis | Daily volume |
|---|---|---|---|
| Post liked | 15% of DAU trigger one like notification | General benchmark | 375,000 |
| Comment received | 8% of DAU receive one comment notification | General benchmark | 200,000 |
| New follower | 5% of DAU | General benchmark | 125,000 |
| Mention | 3% of DAU | General benchmark | 75,000 |
| Direct message | 20% of DAU send at least one; 1 recipient per sender (placeholder — see note above) | Placeholder | 500,000 |
| System/product | 2% of DAU | — | 50,000 |
| **Total baseline** | | | **~1.3M/day** |

**The 1.3M/day total and all downstream calculations are contingent on the DM clarification above.** Any infrastructure purchasing decision made before that clarification is received must be documented as made on an unvalidated assumption, with explicit sign-off from the project lead acknowledging the risk.

#### §1.1.3 Peak Throughput and Spike Buffering

- Average over 24 hours: ~15 notifications/second
- Average over active hours (08:00–22:00, 14 hours, 80% of volume): ~21/second
- Evening peak at 3× active-hours average: ~63/second
- Provisioning target with 2× headroom: **~130 notifications/second**

**Geographic distribution:** A globally distributed user base would smooth the delivery curve because evening peaks in different timezones partially offset each other. The geographic distribution of users is unknown at this stage. Applying a cross-timezone smoothing discount to an already-unsupported peak multiplier would compound two unsupported assumptions in opposite directions, producing false precision. The correct approach is to use the single-timezone worst case for provisioning — the direction of safe error — and note that a globally distributed user base will produce a lower actual peak than provisioned for.

**Tier 3 "immediate" preference load impact:** §1.2.3 allows users to select "immediate" delivery for Tier 3 notifications rather than the default hourly digest. Likes are the highest-volume event type. The load model assumes 20% or fewer users select this option at steady state. This 20% figure is a chosen trigger point for the review process, not a data-derived threshold. If exceeded, effective peak throughput rises because batching compression is reduced. The Tier 3 worker pool is provisioned separately, so the impact is contained to that pool, but aggregate system load increases. The 14-day validation review must measure the actual fraction and recalculate if it exceeds 20%.

**Spike buffering and the auto-scaling gap:** Auto-scaling typically provisions new instances within 2–5 minutes. During that window, a spike above current capacity accumulates in the queue. At 130/second provisioning and a 3× spike (390/second), the queue accumulates approximately 58,500 jobs during a 2.5-minute gap — roughly 58MB at ~1KB per job, well within standard queue capacity. At 6× (780/second), approximately 117,000 jobs (~117MB) accumulate during the same gap, also within capacity. What changes at 6× is the time required to drain the backlog after auto-scaling completes. Queue depth monitoring in §1.1.4 surfaces this condition to the on-call engineer before the backlog reaches problematic depth.

All queue consumers and delivery workers are deployed with auto-scaling configured from day one. Baseline instance counts are set to handle 2× the projected peak at launch — intentionally over-provisioned as insurance against the compounded assumption uncertainty in §1.1.1. The cost of that over-provisioning is explicitly accepted.

#### §1.1.4 Load Validation — Process, Decision Rules, and Enforcement

**Required instrumentation, in place before launch:**
- Per-second notification creation rate by tier and subtype, p50/p95/p99 over rolling 5-minute windows
- Queue depth per queue, sampled every 30 seconds
- Worker throughput per pool (notifications processed per second)
- DAU count, updated daily from product analytics
- Fraction of users with "immediate" Tier 3 delivery preference selected, updated daily

**Review schedule:**

*14-day review (mandatory):* Produces a written update replacing assumed per-user notification rate, peak multiplier, and Tier 3 "immediate" preference fraction with measured values. This update becomes the working figure for subsequent planning. The day-14 data may not represent fully stable steady-state behavior — the 60-day review exists specifically to catch cases where day-14 measurements proved unrepresentative.

*60-day review (mandatory):* Reassesses whether day-14 measurements have proven representative of ongoing behavior. If the product has grown substantially or user behavior has shifted, the provisioning target is recalculated from current measurements.

**Immediate triggers** — either review is also triggered before its scheduled date if:
- Actual peak throughput exceeds 200/second sustained for more than 10 minutes
- Queue depth exceeds 500,000 messages during non-incident conditions
- DAU/MAU ratio exceeds 35%
- Fraction of users with "immediate" Tier 3 preference exceeds 20%

**Decision rules — headroom standard:**

The target state after any review is: baseline instance counts set to handle **1.5× the measured sustained peak**. This standard applies without exception. "No infrastructure changes required" means the current provisioning already satisfies 1.5× the measured peak — it does not mean the standard is suspended.

- **Actual peak within 50% of 130/second in either direction:** Verify current provisioning satisfies 1.5× the measured peak. Adjust if it does not. Do not reduce below 1.5× regardless of cost pressure.
- **Actual peak 50–100% above estimate:** Increase baseline instance counts to 1.5× the measured peak within one sprint.
- **Actual peak more than 100% above estimate:** Escalate to project lead and product lead within 24 hours. Implement infrastructure changes within one sprint. Document what the estimate got wrong and why.
- **Actual peak more than 50% below estimate:** Reduce baseline instance counts to 1.5× the measured peak. Do not reduce below 1.5× regardless of cost pressure.

**Enforcement:** Both review dates are entered as calendar events with Priya Mehta and the project lead as required attendees at kickoff. Missing a review requires explicit sign-off from the project lead, who must document the reason and set a new date within 72 hours. Failure to do so escalates to the product lead.

---

### §1.2 Notification Tiers

Tiers govern delivery priority, channel selection, batching behavior, and failure handling. Every notification is assigned a tier at creation time based solely on its event type. The tier assignment is immutable — it cannot be changed by user preference or batching logic, only by a change to the event type definition itself.

The tier system exists to prevent two failure modes. First, it prevents a backlog of Tier 3 ambient notifications from delaying Tier 1 security events — they run on separate queues with separate workers. Second, it prevents per-user notification volume from being dominated by high-volume, low-urgency events that would obscure higher-