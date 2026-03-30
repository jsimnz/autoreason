# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: Scope and Constraints

This document provides the technical design for the notification system. It is calibrated for a four-person backend team over six months: infrastructure choices favor operational simplicity over theoretical capability, limitations are stated explicitly rather than papered over, and every significant tradeoff names what is being given up and why that is acceptable.

Two constraints govern the entire document. First, every number that rests on an assumption states that assumption explicitly and identifies what measured data would replace it. Second, where a constraint cannot be fully resolved within this design's scope, the limitation is stated along with the action required to resolve it and who owns that action.

**Document completeness:** This document covers load estimation and validation (§1.1), notification tiers (§1.2), Tier 1 delivery path (§1.3), delivery channels including complete push error handling for APNs and FCM (§1.4), in-app notification store (§1.5), email and SMS (§1.6–1.7), user preference management (§1.8), infrastructure (§1.9), and failure handling (§1.10). Forward references to section numbers that do not exist in this document are a defect; if any are found, report them to the document owner.

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

The 2× provisioning headroom described in §1.1.3 is calibrated to handle any single assumption being wrong by a large margin, or two assumptions being modestly wrong simultaneously. **It does not cover the scenario where all three are simultaneously wrong in the same direction.** That scenario is addressed through two mechanisms: the queue buffering described in §1.1.3, which absorbs spikes while auto-scaling responds, and the load validation review in §1.1.4, which replaces assumptions with measurements as quickly as the data permits.

The 2× headroom is therefore simultaneously an acknowledged-insufficient worst-case bound and the best available provisioning stance given pre-launch uncertainty. These two characterizations are not contradictory: the headroom is the right choice given what is known, it is insufficient for the worst case, and both things are true. The response to the worst case is the validation and escalation process, not additional static provisioning — provisioning for a 6× spike on unvalidated assumptions would be prohibitively expensive and would itself rest on an unsupported number.

**Why 14 days, not 30:** By day 14, enough traffic has been observed to replace the peak multiplier and per-user notification rate with measured values, even if the DAU/MAU ratio is still stabilizing. Replacing two of the three compounded assumptions substantially reduces uncertainty in the provisioning target. A 30-day window would leave the system running on all three unsupported assumptions for twice as long with no actionable data. The 14-day data may not represent fully stable steady-state behavior — the 60-day review in §1.1.4 exists specifically to catch this — but it is far preferable to continued reliance on unvalidated placeholders.

#### 1.1.2 Notification Volume Estimates

The per-event rates below are drawn from general social app benchmarks, not product-specific data. This is a material limitation. Notification rates vary substantially across social product types: a platform with algorithmically amplified content will produce radically higher per-user like notification rates than a close-friends network where content distribution is narrow. **The rates in this table should be treated as order-of-magnitude placeholders, not calibrated estimates.** Any single rate could be off by 2–5× in either direction.

| Event type | Rate assumption | Basis | Daily volume |
|---|---|---|---|
| Post liked | 15% of DAU trigger one like notification | Sender activity | 375,000 |
| Comment received | 8% of DAU receive one comment notification | Recipient-side | 200,000 |
| New follower | 5% of DAU | Recipient-side | 125,000 |
| Mention | 3% of DAU | Recipient-side | 75,000 |
| Direct message | 20% of DAU send at least one | Recipient-side; see note | 500,000 |
| System/product | 2% of DAU | — | 50,000 |
| **Total baseline** | | | **~1.3M/day** |

**Direct message volume note:** The DM row assumes each sender reaches one recipient per day. If the product supports group messaging and the average sender reaches multiple recipients, the actual notification volume scales linearly with that average. A product where DM senders average 5 recipients per day would generate 2.5M DM notifications daily, not 500,000. **The DM volume assumption is the highest-risk figure in this table and should be the first validated against product analytics.** The product team must clarify expected DM usage pattern (1-to-1 vs. group) before this figure is used for capacity planning beyond initial provisioning.

#### 1.1.3 Peak Throughput Derivation and Spike Buffering

- Average over 24 hours: ~15 notifications/second
- Average over active hours (08:00–22:00, 14 hours, assuming 80% of volume): ~21/second
- Evening peak at 3× active-hours average: ~63/second
- Provisioning target with 2× headroom: **~130 notifications/second**

**Geographic distribution and peak multiplier interaction:** A globally distributed user base would smooth the global delivery curve, because evening peaks in different timezones partially offset each other. However, the geographic distribution of users is unknown at this stage. Applying a cross-timezone smoothing discount to an unsupported peak multiplier would compound two unsupported assumptions in opposite directions, producing a figure with false precision. The correct approach is to use the single-timezone worst case for provisioning — this is the direction of safe error — and note that a globally distributed user base will produce a lower actual peak than provisioned for.

**Spike buffering and the auto-scaling gap:** Auto-scaling under cloud providers typically provisions new instances within 2–5 minutes. During that window, a spike above current processing capacity accumulates in the queue rather than dropping requests. At 130/second provisioning target and a 3× spike (390/second), the queue accumulates approximately 390 × 150 seconds = 58,500 jobs during a 2.5-minute gap — roughly 58MB at ~1KB per job, well within standard queue capacity. At the acknowledged worst-case 6× spike (780/second), the queue accumulates approximately 117,000 jobs (~117MB) during the same gap, also within standard queue capacity. What changes at 6× is the time required to drain the backlog after auto-scaling completes. The queue depth monitoring in §1.1.4 surfaces this condition to the on-call engineer before the backlog reaches problematic depth.

All queue consumers and delivery workers are deployed with auto-scaling configured from day one, with baseline instance counts set to handle 2× the projected peak from launch. The system is intentionally over-provisioned at launch. The cost of that over-provisioning is explicitly accepted as insurance against the compounded assumption uncertainty described in §1.1.1.

#### 1.1.4 Load Validation — Owner, Process, Decision Rules, and Enforcement

**Current owner:** Priya Mehta (backend engineer, notifications lead).

**Pre-distribution check:** Before this document is distributed to any stakeholder, the project lead must verify that the named owner above reflects current team composition. This verification is a named step in the project kickoff checklist. If the checklist is not completed, distribution is blocked.

**Ownership transfer process:** If the named owner's role changes, the project lead designates a replacement in writing within 48 hours and updates this document. The replacement owner acknowledges the assignment in writing. If the project lead fails to make this designation within 48 hours, the team lead assumes temporary ownership and designates a permanent replacement within the following 48 hours.

**Failure mode — simultaneous unavailability of named owner and project lead:** On a four-person team, the named owner and project lead may be simultaneously unavailable (leave, illness, departure). If both are unavailable: the most senior available engineer on the team assumes temporary ownership of all time-sensitive decisions related to this document, notifies the product lead within 24 hours, and designates a permanent replacement within 48 hours. The product lead is the final escalation point and is not part of the backend team, so this chain does not loop. The product lead's contact information is recorded in the project kickoff checklist, not only in this document.

**Required instrumentation, in place before launch:**
- Per-second notification creation rate by tier and subtype, with p50/p95/p99 over rolling 5-minute windows
- Queue depth per queue, sampled every 30 seconds
- Worker throughput per pool (notifications processed per second)
- DAU count, updated daily from product analytics

**Review schedule:**

*14-day review (mandatory):* Produces a written update to this section replacing the assumed per-user notification rate and peak multiplier with measured values. The review is not optional and is not deferred because nothing appears wrong. This update becomes the authoritative figure for all subsequent planning.

*60-day review (mandatory):* Reassesses whether day-14 measurements have proven representative of ongoing behavior. If the product has grown substantially or user behavior has shifted, the provisioning target is recalculated from current measurements. This review exists specifically because day-14 data may not represent steady-state behavior.

Both reviews are also triggered immediately — before their scheduled date — if any of the following are observed:
- Actual peak throughput exceeds 200/second sustained for more than 10 minutes
- Queue depth exceeds 500,000 messages during non-incident conditions
- DAU/MAU ratio exceeds 35%

**Enforcement:** Both review dates are entered as calendar events with the team lead and product lead as required attendees at project kickoff. Missing a review requires explicit sign-off from the team lead, who must document the reason and set a new date within 72 hours. Failure to do so escalates to the product lead. The notifications lead owns scheduling; the team lead owns enforcement.

**Decision rules — unified headroom standard:**

All decision rules target the same headroom standard: **baseline instance counts set to handle 1.5× the measured sustained peak.** This standard applies in all cases without exception. New baselines are computed from the measured peak directly — do not apply a mechanical ratio from the old estimate.

- If actual peak is within 50% of 130/second in either direction: no infrastructure changes required; update the working figure and cost projections.
- If actual peak is 50–100% above estimate: increase baseline instance counts to handle 1.5× the measured peak.
- If actual peak is more than 100% above estimate: escalate to team lead and product within 24 hours; implement infrastructure changes within one sprint; document what the estimate got wrong and why.
- If actual peak is more than 50% below estimate: reduce baseline instance counts to handle 1.5× the measured peak. Do not reduce below 1.5× the measured peak regardless of cost pressure — the safety margin is intentional, but the degree of over-provisioning was calibrated to uncertainty that has now been partially resolved.

---

### 1.2 Notification Tiers

Tiers govern delivery priority, channel selection, batching behavior, and failure handling. Every notification is assigned a tier at creation time based solely on its event type. The tier assignment is immutable — it cannot be changed by user preference or batching logic, only by the event type definition.

The tier system exists to prevent two failure modes. First, it prevents a backlog of Tier 3 ambient notifications from delaying Tier 1 security events — they run on separate queues with separate workers. Second, it prevents per-user notification volume from being dominated by high-volume, low-urgency events that would obscure higher-value interactions if delivered immediately and individually.

User preferences can control delivery *timing* within a tier's rules — specifically, the cadence at which Tier 3 digests are assembled — but cannot move a notification between tiers or change which infrastructure processes it. This distinction matters because the interaction between tier assignment and user timing preferences creates edge cases that must be specified explicitly; those are addressed in §1.2.3.

#### 1.2.1 Tier 1 — Security and Account Events

Examples: password reset, email address change, login from new device, account recovery.

Delivery is concurrent across all available channels (push, email, SMS, in-app). No batching. No quiet-hour suppression. Failure on any single channel does not suppress delivery on others. Delivery is attempted on every channel regardless of user opt-in, because the user's ability to act on a security event must not depend on which channels they have configured.

**Legal dependency — architecture-affecting, not a footnote:** Some privacy frameworks require explicit opt-in for all commercial communications regardless of category, including transactional and security messages. If legal review concludes that opt-in is required for SMS or email in jurisdictions where the app operates, the Tier 1 delivery architecture must change in one of two ways: either Tier 1 delivery is restricted to channels the user has opted into (which means a user with no channels configured cannot receive a password reset), or the app's onboarding flow mandates opt-in to at least one channel before account creation completes (which changes the product design). Both alternatives have significant implications for product and engineering.

**This legal review must be completed before the Tier 1 architecture is finalized, not after.** The current design assumes opt-in is not required for security events. If that assumption is wrong, §1.2.1 and §1.3 require revision before implementation begins.

**Owner of legal review:** [Product lead name]. **Required completion date:** [Date — at least 4 weeks before implementation of §1.3 begins]. **If legal review is not completed by this date, implementation of §1.3 is blocked.** This is a named blocker in the project plan, not a background dependency.

#### 1.2.2 Tier 2 — Direct Social Interactions

Examples: direct messages, mentions, comments on the user's own content.

Delivered promptly (target: within 60 seconds of the triggering event for an online device). Subject to quiet-hour suppression. Not batched. Every Tier 2 notification is written to the in-app notification store before push is attempted — the mechanism and atomicity guarantee for this are specified in §1.5.

#### 1.2.3 Tier 3 — Ambient Social Activity and the Timing Preference Interaction

Examples: likes on posts, new followers, reposts.

Batched into digests delivered at most once per hour per user by default. Subject to quiet-hour suppression. Written to the in-app store when the digest is assembled, not when the triggering event occurs.

**User timing preference for Tier 3:** Users can select a delivery cadence of "immediate," "hourly" (default), or "daily" for Tier 3 notifications via preference settings (§1.8). The "immediate" option delivers each Tier 3 notification individually rather than waiting for the hourly digest. This preference controls delivery timing only — the notification still goes through the Tier 3 delivery worker. Tier assignment is not affected by this preference, and the Tier 3 worker is not replaced by the Tier 2 worker for users who select "immediate." The distinction matters for queue isolation: Tier 2 queue depth must not be affected by users who have elected immediate Tier 3 delivery.

---

### 1.3 Tier 1 Delivery Path

Tier 1 notifications require a delivery approach distinct from Tier 2 and Tier 3 because the cost of non-delivery is high and the user cannot be expected to have any particular channel preference configured. A user who has never set up push notifications still needs to receive a password reset email.

**Delivery behavior:** All available channels are attempted concurrently at the moment the Tier 1 event is created. "Available" means the channel infrastructure is operational, not that the user has opted into it — user channel preferences do not suppress Tier 1 delivery, subject to the legal caveat in §1.2.1.

**Per-channel behavior under Tier 1:**