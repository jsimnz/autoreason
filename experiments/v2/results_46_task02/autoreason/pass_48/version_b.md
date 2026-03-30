# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Document version:** 3.0
**Document owner:** Priya Mehta (notifications lead)
**Last revised:** [date]
**Status:** Draft — legal review scope defined in §0.3; SMS/email implementation gated on that review

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
- §A Kickoff Checklist (Appendix)

---

## §0 Preface

### §0.1 Scope and Constraints

This document provides the technical design for the notification system, calibrated for a four-person backend team over six months. Infrastructure choices favor operational simplicity over theoretical capability. Limitations are stated explicitly rather than papered over. Every significant tradeoff names what is being given up and why that is acceptable given the constraints.

Two principles govern the entire document. First, every number that rests on an assumption states that assumption and identifies what measured data would replace it. Second, where a constraint cannot be resolved within this design's scope, the document states the limitation, the action required to resolve it, and who owns that action by name.

### §0.2 Named Owners and Escalation Chain

All three people in the escalation chain are identified here. Contact information is recorded in the kickoff checklist (§A) rather than this document because contact details change and belong in a single authoritative source. The kickoff checklist must be completed and signed before this document is distributed to any stakeholder. The project lead owns that step.

| Role | Name | Responsibility in this document |
|---|---|---|
| Notifications lead / document owner | Priya Mehta | All technical decisions; 14-day and 60-day validation reviews; escalation first contact |
| Project lead | [name — required before distribution] | Kickoff checklist completion; escalation if Priya Mehta is unavailable; infrastructure purchasing sign-off |
| Product lead | [name — required before distribution] | Final escalation point; DM usage pattern clarification (§1.1.2); capacity decisions above sprint budget |

**This table must be fully populated before distribution.** A row with a placeholder name is a blocking defect. The project lead is responsible for providing both unnamed entries and updating this table before the kickoff checklist is signed.

**Simultaneous unavailability:** The four backend engineers are ranked by a single unambiguous criterion for the purpose of incident decision authority: years of tenure on this team, with ties broken by date of hire (earlier hire ranks higher). This ranking is recorded explicitly in §A item 7 and must be populated at kickoff. It is not determined in the moment of an incident. If both Priya Mehta and the project lead are simultaneously unavailable, the highest-ranked available engineer on that list assumes temporary ownership of all time-sensitive decisions, contacts the product lead within 24 hours using the kickoff checklist contact information, and designates a permanent replacement within 48 hours. The ranking is reviewed and updated whenever team composition changes.

### §0.3 Legal Review — Scope, Owner, Deadline, and Contingency

**What the legal review covers:** SMS and email channel implementation (§1.6 and §1.7) requires compliance verification for: TCPA consent requirements for SMS in the United States; CAN-SPAM and GDPR requirements for email including unsubscribe mechanics, data residency for EU users, and retention limits on notification preference data; and any jurisdiction-specific opt-in requirements for push notifications beyond Apple and Google platform requirements.

**What the legal review does not cover:** Push notification delivery mechanics (§1.4), in-app notification store (§1.5), and all infrastructure decisions (§1.9) are not gated on this review. Work on those sections proceeds on the main timeline.

**Owner:** [Legal counsel name — required before distribution. Project lead is responsible for identifying this person and recording the name here before kickoff checklist sign-off.]

**Deadline:** Legal review must be complete by [date — set as 6 weeks before planned SMS/email implementation begins. Project lead sets this date at kickoff].

**Contingency if deadline is missed — Tier 1 degradation acknowledged:**

If the legal review is not complete by the stated deadline, SMS and email channel implementation is deferred. This has a direct consequence for Tier 1 security notifications that must be acknowledged explicitly and is not acceptable to simply defer.

Tier 1 security events (§1.2.1) use the delivery sequence push → SMS → email, where SMS serves as fallback when push fails — for example, when a user has no registered push token, has uninstalled the app, or has disabled push at the OS level. If SMS is unavailable because it has not cleared legal review, a user in that situation receives a security notification only via email. Email is a weaker fallback for security events: it is slower, less likely to produce immediate user attention, and more likely to land in spam filters.

**This degraded Tier 1 behavior is not acceptable as a silent default.** The following steps are required if SMS is deferred:

1. The product lead must explicitly sign off on operating without SMS fallback for Tier 1 events. This sign-off must be in writing and is not implied by silence.
2. The Tier 1 delivery logic must be updated before launch to reflect the actual available channels, so monitoring and alerting reflect real behavior rather than a theoretical sequence that includes an unavailable channel.
3. The fraction of users without a valid push token must be measured during the first week of operation. If it exceeds 10%, the product lead and project lead are notified immediately, because the population experiencing degraded Tier 1 delivery is larger than anticipated.
4. SMS legal clearance is treated as the highest-priority legal task, ahead of email, because of its Tier 1 dependency. The product lead owns escalating this with legal counsel.

If the revised legal review date falls within the 6-month delivery window, SMS ships in the final sprint with reduced scope if necessary. If it falls outside the window, SMS is explicitly descoped from v1 and documented as v2 work, with the Tier 1 degradation formally acknowledged in the v2 planning document.

### §0.4 Event Type Tier Assignment — Governance Process

§1.2 establishes that tier assignments are immutable at the per-notification level and can only be changed by modifying the event type definition. This section defines the governance process for those changes, because an immutability guarantee without a change process is not a safety property — it is an undocumented bottleneck.

**Who can initiate a tier reassignment:** Any engineer, product manager, or legal counsel may propose a tier reassignment. The proposal must be submitted in writing to Priya Mehta and must include: the event type being reassigned, the current tier, the proposed tier, the reason for the change, and the expected volume impact.

**Review required:** Tier reassignments require sign-off from Priya Mehta (technical correctness and load impact), the product lead (user experience and product intent), and legal counsel if the change affects a channel with regulatory implications (e.g., moving an event type into Tier 1 would add it to the SMS fallback sequence).

**Handling in-flight notifications during transition:** When a tier reassignment is approved, the implementation is a two-step deployment. Step one: update the event type definition in the configuration store with the new tier assignment. Step two: the configuration change takes effect for all notifications created after the deployment timestamp. Notifications already in queue at deployment time are processed under their original tier assignment. No retroactive reprocessing occurs. The deployment timestamp is logged and retained for 90 days so that any anomalies in delivery behavior around the transition can be investigated.

**Turnaround expectation:** Non-urgent reassignments are reviewed within one sprint cycle. Urgent reassignments (e.g., a legal requirement discovered post-launch) are reviewed within 48 hours, with the product lead and legal counsel notified immediately.

---

## Part 1: Technical Design

### §1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app. The working figure is 2.5M DAU (25% DAU/MAU ratio). This ratio must be validated against actual product analytics at the 14-day review.

#### §1.1.1 Compounded Assumption Risk and the 2× Provisioning Choice

The peak throughput figure used for provisioning is derived by multiplying three independent estimates:

1. **DAU/MAU ratio:** assumed at 25% (2.5M DAU). Plausible range: 20–45%.
2. **Notification rate per DAU:** assumed per event type in §1.1.2. Drawn from general social app benchmarks.
3. **Evening peak multiplier:** assumed at 3×. Not supported by product-specific data.

Compounding three independent assumptions produces uncertainty that cannot be fully quantified before launch. The direction of risk is asymmetric: a highly engaged user base tends to produce higher values on all three dimensions simultaneously, because engagement, notification density, and peak concentration are correlated.

**The 2× headroom choice is a cost decision, not an engineering determination.** The argument for 2× over higher multiples is not that 2× is better-grounded in data — it has exactly the same epistemic status as a 6× estimate, which is to say neither is grounded in product-specific measurement. The argument is: (a) 2× is cheaper; (b) queue buffering absorbs spikes while auto-scaling responds, limiting the consequence of being under-provisioned for a short window; (c) the validation process in §1.1.4 replaces assumptions with measurements within 14 days of launch, limiting the duration of exposure to the unvalidated estimate; and (d) the cost of revising upward after measurement is accepted explicitly as part of the design.

The case against higher multiples is not that they are wrong. It is that they are equally unsupported and substantially more expensive. Spending significantly more money to provision against a worst-case scenario that is itself an unvalidated estimate does not reduce risk in proportion to its cost, because the estimate could be wrong in either direction. The validation process addresses the uncertainty more directly than additional static provisioning does.

**What 2× does not cover:** If all three assumptions are simultaneously wrong in the same direction, actual peak throughput could substantially exceed the provisioning target. That scenario is addressed through queue buffering and the validation process. It is not addressed through additional static provisioning.

#### §1.1.2 Notification Volume Estimates

**Benchmark sourcing — important caveat:** The per-event rates below are labeled "general benchmark" because they are drawn from published industry analyses of social apps of comparable scale, not from this product's own data. The specific sources are: [source 1, year], [source 2, year], [source 3, year]. These sources must be recorded in the kickoff checklist (§A item 8) before infrastructure purchasing decisions are made. They are placeholders in this document because the appropriate benchmarks depend on the product's category — a messaging-first app has a materially different notification profile than a photo-sharing or interest-graph app — and that categorization must be confirmed by the product lead before the rates below are treated as applicable. If the product lead determines the product category differs from the benchmark sources, the rates must be renegotiated before provisioning decisions are finalized.

Any single rate could be off by 2–5× in either direction even with appropriate benchmark sources. These are order-of-magnitude planning figures, not forecasts.

**DM volume — clarification required before infrastructure purchasing:**

The direct message row assumes each DM sender reaches one recipient per day. This is a placeholder. If the product supports group messaging and the average sender reaches multiple recipients, DM notification volume scales linearly with that average.

The full impact of the high-end assumption is larger than a simple doubling. At 5 recipients per sender: DM notifications rise from 500,000 to 2,500,000 per day. Total daily volume rises from approximately 1.3M to approximately 3.3M — a 2.5× increase in total volume, not a near-doubling. The downstream provisioning target of approximately 130 notifications/second would need to be approximately 325/second. This is a material difference in infrastructure cost and must be resolved before any purchasing commitment.

**Required action:** The product lead must specify the expected DM usage pattern (1-to-1 vs. group; if group, expected average recipients per sender) before any infrastructure purchasing decision is made.

**Owner:** [product lead name — from §0.2 table]
**Required by:** [date — at least 2 weeks before any infrastructure purchasing commitment; project lead sets this date at kickoff]

**If this clarification is not received by the stated date:** The provisioning target must be recomputed using the high-end DM assumption (5 recipients per sender), yielding a target of approximately 325/second. The resulting cost increase must be documented and escalated to the product lead for sign-off. Infrastructure purchasing does not proceed on the low-end assumption after the deadline has passed without a response.

| Event type | Rate assumption | Basis | Daily volume |
|---|---|---|---|
| Post liked | 15% of DAU trigger one like notification | General benchmark [sources in §A item 8] | 375,000 |
| Comment received | 8% of DAU receive one comment notification | General benchmark | 200,000 |
| New follower | 5% of DAU | General benchmark | 125,000 |
| Mention | 3% of DAU | General benchmark | 75,000 |
| Direct message | 20% of DAU send at least one; 1 recipient per sender (placeholder — see note above) | Placeholder | 500,000 |
| System/product | 2% of DAU | — | 50,000 |
| **Total baseline (low-end DM assumption)** | | | **~1.3M/day** |
| **Total baseline (high-end DM assumption, 5 recipients/sender)** | | | **~3.3M/day** |

All downstream calculations in §1.1.3 use the low-end figure. Any infrastructure purchasing decision made on the low-end figure before DM clarification is received must be documented as made on an unvalidated assumption, with explicit sign-off from the project lead.

#### §1.1.3 Peak Throughput and Spike Buffering

Using low-end DM assumption (1.3M/day):
- Average over 24 hours: ~15 notifications/second
- Average over active hours (08:00–22:00, 14 hours, 80% of volume): ~21/second
- Evening peak at 3× active-hours average: ~63/second
- Provisioning target with 2× headroom: **~130 notifications/second**

Using high-end DM assumption (3.3M/day):
- Average over active hours: ~52/second
- Evening peak at 3×: ~157/second
- Provisioning target with 2× headroom: **~315/second**

**Tier 3 "immediate" preference load impact:** §1.2.3 allows users to select "immediate" delivery for Tier 3 notifications rather than the default hourly digest. The load model assumes 20% or fewer users select this option at steady state. This is a chosen trigger point for the review process, not a data-derived figure. If more than 20% of users select "immediate," effective peak throughput rises because batching compression is reduced. The Tier 3 worker pool is provisioned separately, so the impact is contained to that pool, but aggregate system load increases. The 14-day validation review must measure the actual fraction and recalculate effective throughput if it exceeds 20%.

**Spike buffering:** Auto-scaling typically provisions new instances within 2–5 minutes. During that window, a spike above current capacity accumulates in the queue. At 130/second provisioning and a 3× spike (390/second), the queue accumulates approximately 58,500 jobs during a 2.5-minute gap (~58MB at ~1KB per job). At 6×, approximately 117,000 jobs (~117MB). Both are within standard queue capacity. What changes at 6× is the time to drain the backlog after auto-scaling completes. Queue depth monitoring surfaces this to the on-call engineer before the backlog reaches problematic depth.

All queue consumers and delivery workers are deployed with auto-scaling configured from day one. Baseline instance counts are set to handle 2× the projected peak at launch — intentionally over-provisioned as insurance against the compounded assumption uncertainty in §1.1.1. The cost of that over-provisioning is accepted explicitly.

#### §1.1.4 Load Validation — Process, Decision Rules, and Enforcement

**The validation schedule and infrastructure purchasing timing:** Infrastructure purchasing decisions may need to be made before the 14-day review produces measured data. The validation schedule is therefore not a mechanism for informing initial purchasing decisions — it cannot be, given the timeline. Its purpose is to replace assumed values with measured ones as quickly as possible after launch, and to trigger escalation if measurements reveal that initial decisions were substantially wrong. The initial purchasing decisions are made on the DM clarification (which must