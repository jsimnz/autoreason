# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Document version:** 1.1
**Document owner:** Priya Mehta (notifications lead)
**Last revised:** [date of revision]
**Status:** Draft — pending legal review completion before §1.3 implementation begins

---

## Table of Contents

- §1.1 Scale and Load Estimates
- §1.2 Notification Tiers
- §1.3 Tier 1 Delivery Path
- §1.4 Delivery Channels — Push (APNs and FCM)
- §1.5 In-App Notification Store
- §1.6 Email Channel
- §1.7 SMS Channel
- §1.8 User Preference Management
- §1.9 Infrastructure
- §1.10 Failure Handling

All sections listed above are present in this document. A section that appears in this list but not in the document body is a defect; report it to Priya Mehta.

---

## Preface: Scope and Constraints

This document provides the technical design for the notification system. It is calibrated for a four-person backend team over six months: infrastructure choices favor operational simplicity over theoretical capability, limitations are stated explicitly rather than papered over, and every significant tradeoff names what is being given up and why that is acceptable.

Two constraints govern the entire document. First, every number that rests on an assumption states that assumption explicitly and identifies what measured data would replace it. Second, where a constraint cannot be fully resolved within this design's scope, the limitation is stated along with the action required to resolve it and who owns that action.

**On section completeness:** Every section listed in the table of contents above is present and complete in this document. Sections are not truncated. If a section ends mid-sentence or with a placeholder like "---" followed by nothing, that is a defect; report it to the document owner named above.

---

## Part 1: Technical Design

### 1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app (industry baseline: 20–30% DAU/MAU ratio; working figure: 2.5M DAU). **This ratio must be validated against actual product analytics within 14 days of launch.** The rationale for 14 days rather than 30 is explained in §1.1.1.

#### 1.1.1 Compounded Assumption Risk

The peak throughput figure used for provisioning is derived by multiplying three independent estimates:

1. **DAU/MAU ratio:** assumed at 25% (2.5M DAU from 10M MAU). Range of plausible values: 20–45%.
2. **Notification rate per DAU:** assumed per event type in §1.1.2. These figures are drawn from general social app benchmarks, not product-specific data.
3. **Evening peak multiplier:** assumed at 3×. Explicitly unsupported by product-specific data.

Compounding three independent assumptions produces a confidence interval that is never fully quantifiable before launch. The direction of risk is clear: a highly engaged user base tends to produce higher values on all three dimensions simultaneously, because engagement, notification density, and peak concentration are correlated. If all three assumptions are simultaneously wrong in the same direction, peak throughput could exceed the provisioning target by a factor of 3 or more.

The 2× provisioning headroom described in §1.1.3 is chosen over alternatives as follows. Provisioning for 1× (no headroom) leaves no margin for any assumption being wrong. Provisioning for 6× (the acknowledged worst case) costs roughly 3× more than the 2× stance and still rests on an unsupported number — the worst-case multiplier is not derived from data, it is derived from the observation that all three assumptions could be simultaneously wrong in the same direction, which is itself an estimate of an estimate. The 2× stance is chosen because it handles any single assumption being substantially wrong, or two assumptions being modestly wrong simultaneously, at a cost that is defensible given pre-launch uncertainty. It does not cover the simultaneous worst case across all three dimensions. That scenario is addressed through queue buffering (which absorbs spikes while auto-scaling responds) and the validation process in §1.1.4 (which replaces assumptions with measurements as quickly as the data permits). The response to the worst case is the validation and escalation process, not additional static provisioning.

This reasoning applies symmetrically: the 2× figure is no more precisely justified than the 6× figure would be. Both rest on qualitative calibration rather than measurement. The 2× figure is chosen because it is the cheapest defensible stance given what is known, not because it is known to be correct. The validation process in §1.1.4 is the mechanism by which "defensible given uncertainty" is replaced with "calibrated to measurement."

**Why 14 days, not 30:** By day 14, enough traffic has been observed to replace the peak multiplier and per-user notification rate with measured values, even if the DAU/MAU ratio is still stabilizing. Replacing two of the three compounded assumptions substantially reduces uncertainty in the provisioning target. A 30-day window would leave the system running on all three unsupported assumptions for twice as long with no actionable data. The 14-day data may not represent fully stable steady-state behavior — the 60-day review in §1.1.4 exists specifically to catch this — but it is far preferable to continued reliance on unvalidated placeholders.

#### 1.1.2 Notification Volume Estimates

**DM volume — a required clarification that currently blocks the capacity estimate:**

The direct message row in the table below assumes each DM sender reaches one recipient per day. This assumption is not a calibrated estimate; it is a placeholder. If the product supports group messaging and the average sender reaches multiple recipients, actual DM notification volume scales linearly with that average. A product where senders average five recipients per day would generate 2.5M DM notifications daily, not 500,000 — nearly doubling the total estimated volume and materially changing the provisioning target in §1.1.3.

This clarification is required before the provisioning target in §1.1.3 is used for infrastructure purchasing decisions or capacity planning beyond initial launch provisioning. Using the current figure for those decisions while acknowledging it could be off by 5× is not a documented tradeoff; it is using a number known to be unreliable for a purpose that requires reliability.

**Required action:** The product team must specify expected DM usage pattern (1-to-1 vs. group, and if group, expected average recipients per sender) before any infrastructure purchasing decision is made. **Owner: [product lead name]. Required by: [date — at least 2 weeks before any infrastructure purchasing commitment].** If this clarification is not received by that date, the provisioning target must be computed using the high-end DM assumption (5 recipients per sender) rather than the current placeholder, and the resulting cost increase must be documented and escalated.

The per-event rates below are drawn from general social app benchmarks, not product-specific data. This is a material limitation. Notification rates vary substantially across social product types. **The rates in this table should be treated as order-of-magnitude placeholders, not calibrated estimates.** Any single rate could be off by 2–5× in either direction.

| Event type | Rate assumption | Basis | Daily volume |
|---|---|---|---|
| Post liked | 15% of DAU trigger one like notification | Sender activity | 375,000 |
| Comment received | 8% of DAU receive one comment notification | Recipient-side | 200,000 |
| New follower | 5% of DAU | Recipient-side | 125,000 |
| Mention | 3% of DAU | Recipient-side | 75,000 |
| Direct message | 20% of DAU send at least one; 1 recipient per sender | Recipient-side; see clarification note above | 500,000 |
| System/product | 2% of DAU | — | 50,000 |
| **Total baseline** | | | **~1.3M/day** |

#### 1.1.3 Peak Throughput Derivation and Spike Buffering

- Average over 24 hours: ~15 notifications/second
- Average over active hours (08:00–22:00, 14 hours, assuming 80% of volume): ~21/second
- Evening peak at 3× active-hours average: ~63/second
- Provisioning target with 2× headroom: **~130 notifications/second**

**Load model adjustment for Tier 3 "immediate" preference:** §1.2.3 specifies that users may select "immediate" delivery for Tier 3 notifications rather than the default hourly digest. Likes are the highest-volume event type in the table. If a meaningful fraction of users select this option, the batching assumption that underlies the volume estimates above no longer applies to those users. The load model here assumes that 20% or fewer of users select "immediate" Tier 3 delivery at steady state. If that fraction is exceeded, the effective peak throughput rises because batching compression is reduced. The Tier 3 worker pool is provisioned separately from Tier 1 and Tier 2, so the impact is contained to that pool, but the aggregate system load increases. The 14-day validation review in §1.1.4 must measure the fraction of users who have selected "immediate" Tier 3 delivery and recalculate the effective unbatched volume if that fraction exceeds 20%. If it does, the Tier 3 worker pool baseline must be increased to handle 1.5× the measured Tier 3 throughput before digest compression.

**Geographic distribution:** A globally distributed user base would smooth the global delivery curve because evening peaks in different timezones partially offset each other. The geographic distribution of users is unknown at this stage. Applying a cross-timezone smoothing discount to an unsupported peak multiplier would compound two unsupported assumptions in opposite directions, producing false precision. The correct approach is to use the single-timezone worst case for provisioning — this is the direction of safe error — and note that a globally distributed user base will produce a lower actual peak than provisioned for.

**Spike buffering and the auto-scaling gap:** Auto-scaling under cloud providers typically provisions new instances within 2–5 minutes. During that window, a spike above current processing capacity accumulates in the queue. At the 130/second provisioning target and a 3× spike (390/second), the queue accumulates approximately 58,500 jobs during a 2.5-minute gap — roughly 58MB at ~1KB per job, well within standard queue capacity. At a 6× spike (780/second), the queue accumulates approximately 117,000 jobs (~117MB) during the same gap, also within standard queue capacity. What changes at 6× is the time required to drain the backlog after auto-scaling completes. Queue depth monitoring in §1.1.4 surfaces this condition to the on-call engineer before the backlog reaches problematic depth.

All queue consumers and delivery workers are deployed with auto-scaling configured from day one, with baseline instance counts set to handle 2× the projected peak from launch. The system is intentionally over-provisioned at launch. The cost of that over-provisioning is explicitly accepted as insurance against the compounded assumption uncertainty described in §1.1.1.

#### 1.1.4 Load Validation — Owner, Process, Decision Rules, and Enforcement

**Current document owner and validation owner:** Priya Mehta (backend engineer, notifications lead). This name must be verified against current team composition by the project lead before this document is distributed to any stakeholder. That verification step is recorded in the project kickoff checklist. **The kickoff checklist is a separate document, not a section of this one.** The kickoff checklist must be completed and signed before distribution occurs; the project lead owns that step. This document cannot enforce its own pre-distribution check — the enforcement mechanism is the kickoff checklist process and the project lead, not this document.

**Escalation chain and contact information:** The escalation chain below names roles and individuals. Contact information for each person in the chain — specifically for the product lead, who is the final escalation point and not a member of the backend team — is recorded in the project kickoff checklist, not duplicated here. **If the kickoff checklist has not been completed, the escalation chain is incomplete and distribution of this document is blocked.** The project lead is responsible for ensuring the checklist is complete before distribution.

**Ownership transfer process:** If the named owner's role changes, the project lead designates a replacement in writing within 48 hours and updates this document. The replacement owner acknowledges the assignment in writing.

**Failure mode — simultaneous unavailability of named owner and project lead:** If both are unavailable simultaneously, the most senior available engineer on the team assumes temporary ownership of all time-sensitive decisions, notifies the product lead within 24 hours using the contact information in the kickoff checklist, and designates a permanent replacement within 48 hours. The product lead is the final escalation point and is not part of the backend team, so this chain does not loop back to the backend team. If the kickoff checklist is not complete and the product lead's contact information is therefore not recorded, this failure mode cannot be resolved through the designed chain. This is a reason the kickoff checklist must be completed before distribution, not a reason to record the product lead's contact information in this document — contact information that changes frequently belongs in a single authoritative source, not duplicated across design documents where it will become stale.

**Required instrumentation, in place before launch:**
- Per-second notification creation rate by tier and subtype, with p50/p95/p99 over rolling 5-minute windows
- Queue depth per queue, sampled every 30 seconds
- Worker throughput per pool (notifications processed per second)
- DAU count, updated daily from product analytics
- Fraction of users with "immediate" Tier 3 delivery preference selected, updated daily

**Review schedule:**

*14-day review (mandatory):* Produces a written update to this section replacing the assumed per-user notification rate, peak multiplier, and Tier 3 "immediate" preference fraction with measured values. This update becomes the authoritative figure for all subsequent planning. The review is not optional and is not deferred because nothing appears wrong.

*60-day review (mandatory):* Reassesses whether day-14 measurements have proven representative of ongoing behavior. If the product has grown substantially or user behavior has shifted, the provisioning target is recalculated from current measurements.

Both reviews are also triggered immediately — before their scheduled date — if any of the following are observed:
- Actual peak throughput exceeds 200/second sustained for more than 10 minutes
- Queue depth exceeds 500,000 messages during non-incident conditions
- DAU/MAU ratio exceeds 35%
- Fraction of users with "immediate" Tier 3 preference exceeds 20%

**Enforcement:** Both review dates are entered as calendar events with the team lead and product lead as required attendees at project kickoff. Missing a review requires explicit sign-off from the team lead, who must document the reason and set a new date within 72 hours. Failure to do so escalates to the product lead.

**Decision rules — headroom standard:**

All decision rules target the same headroom standard: **baseline instance counts set to handle 1.5× the measured sustained peak.** This standard applies in all cases without exception. New baselines are computed from the measured peak directly.

The rules below specify when infrastructure changes are required. In all cases, the post-change state must satisfy the 1.5× standard — "no infrastructure changes required" means the current provisioning already satisfies 1.5× the measured peak and no further action is needed, not that the 1.5× standard is suspended.

- If actual peak is within 50% of 130/second in either direction: verify that current provisioning satisfies 1.5× the measured peak. If it does, no changes are required; update the working figure and cost projections. If it does not — for example, because the system was initially over-provisioned at 2× and the measured peak is low enough that 1.5× would imply a significant reduction — adjust baseline counts to 1.5× the measured peak. Do not reduce below 1.5× the measured peak regardless of cost pressure; the safety margin is intentional.
- If actual peak is 50–100% above estimate: increase baseline instance counts to handle 1.5× the measured peak.
- If actual peak is more than 100% above estimate: escalate to team lead and product within 24 hours; implement infrastructure changes within one sprint; document what the estimate got wrong and why.
- If actual peak is more than 50% below estimate: reduce baseline instance counts to handle 1.5× the measured peak. Do not reduce below 1.5× the measured peak regardless of cost pressure.

---

### 1.2 Notification Tiers

Tiers govern delivery priority, channel selection, batching behavior, and failure handling. Every notification is assigned a tier at creation time based solely on its event type. The tier assignment is immutable — it cannot be changed by user preference or batching logic, only by the event type definition.

The tier system exists to prevent two failure modes. First, it prevents a backlog of Tier 3 ambient notifications from delaying Tier 1 security events — they run on separate queues with separate workers. Second, it prevents per-user notification volume from being dominated by high-volume, low-urgency events that would obscure higher-value interactions if delivered immediately and individually.

User preferences can control delivery *timing* within a tier's rules — specifically,