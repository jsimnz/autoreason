# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Preface: Scope and Constraints

This document provides the technical design for the notification system. It is calibrated for a four-person backend team over six months: infrastructure choices favor operational simplicity over theoretical capability, limitations are stated explicitly rather than papered over, and every significant tradeoff names what is being given up and why that is acceptable.

Two constraints govern the entire document. First, every number that rests on an assumption states that assumption explicitly and identifies what measured data would replace it. Second, where a constraint cannot be fully resolved within this design's scope, the limitation is stated along with the action required to resolve it and who owns that action.

**Document completeness:** This document covers load estimation and validation (§1.1), notification tiers (§1.2), Tier 1 delivery path (§1.3), delivery channels including complete push error handling for both APNs and FCM (§1.4), in-app notification store (§1.5), email and SMS (§1.6–1.7), user preference management (§1.8), infrastructure (§1.9), and failure handling (§1.10). Sections are complete as written. Forward references to section numbers that do not exist in this document are a defect; if any are found, report them to the document owner.

---

## Part 1: Technical Design

### 1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app (industry baseline: 20–30% DAU/MAU ratio; working figure: 2.5M DAU). **This ratio must be validated against actual product analytics.** The validation schedule and what it can and cannot resolve are described in §1.1.2.

#### 1.1.1 Compounded Assumption Risk

The peak throughput figure used for provisioning is derived by multiplying three independent estimates:

1. **DAU/MAU ratio:** assumed at 25% (2.5M DAU from 10M MAU). Range of plausible values: 20–45%.
2. **Notification rate per DAU:** assumed per event type in §1.1.3. These figures are drawn from general social app benchmarks, not product-specific data.
3. **Evening peak multiplier:** assumed at 3×. Explicitly unsupported by product-specific data.

Compounding three independent assumptions produces a confidence interval that is never fully quantifiable before launch. The direction of risk is clear: a highly engaged user base tends to produce higher values on all three dimensions simultaneously, because engagement, notification density, and peak concentration are correlated. If all three assumptions are simultaneously wrong in the same direction, peak throughput could exceed the provisioning target by a factor of 3 or more.

The 2× provisioning headroom described in §1.1.4 is calibrated to handle any single assumption being wrong by a large margin, or two assumptions being modestly wrong simultaneously. **It does not cover the scenario where all three are simultaneously wrong in the same direction.** That scenario is addressed through two mechanisms: the queue buffering described in §1.1.4, which absorbs spikes while auto-scaling responds, and the load validation review in §1.1.5, which replaces assumptions with measurements as quickly as the data permits.

The 2× headroom is therefore simultaneously an acknowledged-insufficient worst-case bound and the best available provisioning stance given pre-launch uncertainty. These two characterizations are not contradictory: the headroom is the right choice given what is known, and it is insufficient for the worst case, and both of those things are true. The response to the worst case is the validation and escalation process, not additional static provisioning, because provisioning for a 6× spike on unvalidated assumptions would be prohibitively expensive and would itself rest on an unsupported number.

#### 1.1.2 What Load Validation Can and Cannot Resolve — and When

The load validation review described in §1.1.5 replaces assumed values with measured values. It is important to be precise about what it resolves and what it does not.

**What the review can resolve:** By day 14, the system has observed actual notification creation rates by event type and actual per-second peak throughput. These replace the per-user notification rate assumption and the peak multiplier assumption with measured values, provided the traffic observed is representative of ongoing behavior.

**What the review cannot fully resolve:** The DAU/MAU ratio and overall notification volume are functions of user base size and behavior, both of which continue to change during early growth. A social app in its first two weeks post-launch is typically in a growth phase where user acquisition, activation, and early churn are all elevated. The day-14 measured peak may not represent steady-state behavior at 10M MAU.

**The honest position:** The review at day 14 replaces two of the three compounded assumptions with measured values, but those measured values may themselves shift as the product matures. The review reduces uncertainty; it does not eliminate it. The decision rules in §1.1.5 account for this by setting headroom targets (1.5× measured peak) rather than absolute capacity targets, so that subsequent growth is absorbed by the headroom margin rather than requiring re-provisioning. The review schedule includes a 60-day follow-up specifically to catch cases where day-14 measurements proved unrepresentative.

The 14-day timing is chosen because it is the earliest point at which the per-second peak and per-user notification rate have enough sample data to be meaningful. It is not chosen because the data is fully stable by then — it is not — but because waiting longer leaves the system running on entirely unvalidated assumptions for longer, which is the worse error given the cost of under-provisioning.

#### 1.1.3 Notification Volume Estimates

The per-event rates below are drawn from general social app benchmarks, not product-specific data. This is a material limitation. Notification rates vary substantially across social product types: a platform with algorithmically amplified content will produce radically higher per-user like notification rates than a close-friends network where content distribution is narrow. **The rates in this table should be treated as order-of-magnitude placeholders, not calibrated estimates.** Any single rate could be off by 2–5× in either direction.

| Event type | Rate assumption | Basis | Daily volume |
|---|---|---|---|
| Post liked | 15% of DAU trigger one like notification | Sender activity; see note | 375,000 |
| Comment received | 8% of DAU receive one comment notification | Recipient-side | 200,000 |
| New follower | 5% of DAU | Recipient-side | 125,000 |
| Mention | 3% of DAU | Recipient-side | 75,000 |
| Direct message | See note below | Recipient-side | 500,000 |
| System/product | 2% of DAU | — | 50,000 |
| **Total baseline** | | | **~1.3M/day** |

**Direct message volume note:** The DM row requires explicit treatment because the notification is generated for the *recipient*, not the sender. The 500,000 figure assumes that 20% of 2.5M DAU send at least one DM, and that the average DM sender reaches 1 recipient per day. If the average sender reaches multiple recipients — which is plausible in a group messaging product — the actual notification volume scales linearly with that average. A product where DM senders average 5 recipients per day would generate 2.5M DM notifications daily, not 500,000. **The DM volume assumption is the highest-risk figure in this table and should be the first validated against product analytics.** The product team must clarify the expected DM usage pattern (1-to-1 vs. group) before this figure is used for capacity planning beyond initial provisioning.

#### 1.1.4 Peak Throughput Derivation and Spike Buffering

- Average over 24 hours: ~15 notifications/second
- Average over active hours (08:00–22:00, 14 hours, assuming 80% of volume): ~21/second
- Evening peak at 3× active-hours average: ~63/second
- Provisioning target with 2× headroom: **~130 notifications/second**

**Geographic distribution and peak multiplier interaction:** A globally distributed user base would smooth the global delivery curve, because evening peaks in different timezones partially offset each other. However, the geographic distribution of users is unknown at this stage. Applying a smoothing discount to an unsupported peak multiplier would compound two unsupported assumptions in opposite directions, producing a figure with false precision. The correct approach is to use the single-timezone worst case for provisioning — this is the direction of safe error — and note that a globally distributed user base will produce a lower actual peak than provisioned for.

**Spike buffering and the auto-scaling gap:** Auto-scaling under cloud providers typically provisions new instances within 2–5 minutes. During that window, a spike above current processing capacity accumulates in the queue rather than dropping requests. At 130/second provisioning target and a 3× spike (390/second), the queue accumulates approximately 390 × 150 seconds = 58,500 jobs during a 2.5-minute gap, or roughly 58MB at ~1KB per job — within standard queue capacity.

The document has acknowledged that a 6× spike is possible if all three compounded assumptions are simultaneously wrong. At 6× (780/second above baseline), the queue accumulates approximately 780 × 150 seconds = 117,000 jobs during the same gap, or roughly 117MB. This is also within standard queue capacity. The queue depth alert threshold in §1.1.5 fires before the queue reaches problematic depth in either scenario, because the alert is set to trigger on sustained elevated queue depth, not on queue size alone. The buffering argument holds for the worst-case spike; what changes is the time required to drain the backlog after auto-scaling completes, which is longer at 6× than at 3×. The queue depth monitoring in §1.1.5 surfaces this condition to the on-call engineer.

#### 1.1.5 Load Validation — Owner, Process, Decision Rules, and Enforcement

**Current owner:** Priya Mehta (backend engineer, notifications lead).

**Pre-distribution check:** Before this document is distributed to any stakeholder, the project lead must verify that the named owner above reflects current team composition. This verification is a named step in the project kickoff checklist. If the checklist is not completed, distribution is blocked.

**Ownership transfer process:** If the named owner's role changes, the project lead designates a replacement in writing within 48 hours and updates this document. The replacement owner acknowledges the assignment in writing.

**Failure mode — simultaneous unavailability of named owner and project lead:** On a four-person team, the named owner and project lead may be simultaneously unavailable (leave, illness, departure). The escalation chain must not depend on both being available. If both are unavailable: the most senior available engineer on the team assumes temporary ownership of all time-sensitive decisions related to this document, notifies the product lead within 24 hours, and designates a permanent replacement within 48 hours. The product lead is the final escalation point and is not part of the backend team, so this chain does not loop. The product lead's contact information is recorded in the project kickoff checklist, not only in this document.

**Required instrumentation, in place before launch:**
- Per-second notification creation rate by tier and subtype, with p50/p95/p99 over rolling 5-minute windows
- Queue depth per queue, sampled every 30 seconds
- Worker throughput per pool (notifications processed per second)
- DAU count, updated daily from product analytics

**Review schedule:**

*14-day review (mandatory):* Produces a written update to this section replacing the assumed per-user notification rate and peak multiplier with measured values. The review is not optional and is not deferred because nothing appears wrong. The review is also triggered immediately — before day 14 — if actual peak throughput exceeds 200/second sustained for more than 10 minutes, queue depth exceeds 500,000 messages during non-incident conditions, or DAU/MAU ratio exceeds 35%.

*60-day review (mandatory):* Reassesses whether day-14 measurements have proven representative of ongoing behavior. If the product has grown substantially or user behavior has shifted, the provisioning target is recalculated from current measurements. This review exists specifically because day-14 data may not represent steady-state behavior.

**Enforcement:** Both review dates are entered as calendar events with the team lead and product lead as required attendees at project kickoff. Missing a review requires explicit sign-off from the team lead, who must document the reason and set a new date within 72 hours. Failure to do so escalates to the product lead. The notifications lead owns scheduling; the team lead owns enforcement.

**Decision rules — unified headroom standard:**

All decision rules target the same headroom standard: **baseline instance counts set to handle 1.5× the measured sustained peak.** This standard applies in all cases without exception.

- If actual peak is within 50% of 130/second in either direction: no infrastructure changes required; update the working figure and cost projections.
- If actual peak is 50–100% above estimate: increase baseline instance counts to handle 1.5× the measured peak.
- If actual peak is more than 100% above estimate: escalate to team lead and product within 24 hours; implement infrastructure changes within one sprint; document what the estimate got wrong and why.
- If actual peak is more than 50% below estimate: reduce baseline instance counts to handle 1.5× the measured peak. Do not reduce below 1.5× the measured peak regardless of cost pressure.

---

### 1.2 Notification Tiers

Tiers govern delivery priority, channel selection, batching behavior, and failure handling. Every notification is assigned a tier at creation time based solely on its event type. The tier assignment is determined by the event type definition and cannot be overridden by batching logic.

User preferences can control delivery *timing* within a tier's rules — specifically, the cadence at which Tier 3 digests are assembled — but cannot move a notification between tiers or change which infrastructure processes it. The distinction between tier assignment and delivery timing is addressed specifically in §1.2.3, because the interaction between them creates edge cases that must be specified explicitly.

The tier system exists to prevent two failure modes. First, it prevents a backlog of Tier 3 ambient notifications from delaying Tier 1 security events — they run on separate queues with separate workers. Second, it prevents per-user notification volume from being dominated by high-volume, low-urgency events that would obscure higher-value interactions if delivered immediately and individually.

#### 1.2.1 Tier 1 — Security and Account Events

Examples: password reset, email address change, login from new device, account recovery.

Delivery is concurrent across all available channels (push, email, SMS, in-app). No batching. No quiet-hour suppression. Failure on any single channel does not suppress delivery on others.

**Legal dependency — architecture-affecting, not a footnote:** Tier 1 delivery attempts all channels regardless of user opt-in, because the user's ability to act on a security event must not depend on which channels they have configured. However, some privacy frameworks require explicit opt-in for all commercial communications regardless of category, including transactional and security messages.

This is not a minor caveat. If legal review concludes that opt-in is required for SMS or email in jurisdictions where the app operates, the Tier 1 delivery architecture must change in one of two ways: either Tier 1 delivery is restricted to channels the user has opted into (which means a user with no channels configured cannot receive a password reset), or the app's onboarding flow mandates opt-in to at least one channel before account creation completes (which changes the product design). Both alternatives have significant implications.

**This legal review must be completed before the Tier 1 architecture is finalized, not after.** The current design is written as if opt-in is not required for security events. If that assumption is wrong, §1.2.1 and §1.3 require revision before implementation begins.

**Owner of legal review:** [Product lead name]. **Required completion date:** [Date — must be at least 4 weeks before implementation of §1.3 begins]. **If legal review is not completed by this date, implementation of §1.3 is blocked.** This is recorded as a named blocker in the project plan, not as a background dependency.

#### 1.2.2 Tier 2 — Direct Social Interactions

Examples: direct messages, mentions, comments on the user's own content.

Delivered promptly (target: within 60 seconds of the triggering event for an online device). Subject to quiet-hour suppression. Not batched. Every Tier 2 notification is written to the in-app notification store before push is attempted — the mechanism and atomicity guarantee for this are specified in §1.5.

#### 1.2.3 Tier 3 — Ambient Social Activity and the Timing Preference Interaction

Examples: likes on posts, new followers, reposts.

Batched into digests delivered at most once per hour per user by default. Subject to quiet-hour suppression. Written to the in-app store when the digest is assembled, not when the triggering event occurs.

**User timing preference for Tier 3:** Users can select a delivery cadence of "immediate," "hourly" (default), or "daily" for Tier 3 notifications via preference settings (§1.8). The "immediate" option delivers each Tier 3 notification individually rather than waiting for the hourly digest