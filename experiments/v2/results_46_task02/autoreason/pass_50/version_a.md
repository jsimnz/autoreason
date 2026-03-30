# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Document version:** 6.0
**Document owner:** Priya Mehta (notifications lead)
**Last revised:** [date]
**Status:** Draft — requires named owner population (§0.2) and kickoff checklist completion (§A) before distribution

---

## Table of Contents

- §0 Preface
  - §0.1 Scope and Constraints
  - §0.2 Named Owners and Escalation Chain
  - §0.3 Legal Review — Scope, Owner, Deadline, and Contingency
  - §0.4 Event Type Tier Assignment — Governance Process
- §1 Technical Design
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
- §A Kickoff Checklist

---

## §0 Preface

### §0.1 Scope and Constraints

This document provides the technical design for the notification system, calibrated for a four-person backend team over six months. Infrastructure choices favor operational simplicity over theoretical capability. Limitations are stated explicitly rather than papered over. Every significant tradeoff names what is being given up and why that is acceptable given the constraints.

Two principles govern the entire document. First, every number that rests on an assumption states that assumption and identifies what measured data would replace it. Second, where a constraint cannot be resolved within this design's scope, the document states the limitation, the action required to resolve it, and who owns that action.

**On the relationship between stated process and actual enforcement:** Several sections define required actions, deadlines, and sign-offs. These are only meaningful if the people named in §0.2 are real, reachable, and aware of their responsibilities before work begins. The kickoff checklist in §A is not administrative overhead — it is the mechanism by which this document's process commitments become operational. Sections that reference §A are inoperable until §A is completed and signed. The project lead owns that completion as a precondition for any technical work beginning.

### §0.2 Named Owners and Escalation Chain

**This table must be fully populated before this document is distributed to any stakeholder.** Both placeholder rows are blocking defects. The project lead is responsible for providing both entries and for confirming that each named person has read this document and accepted their responsibilities before signing the kickoff checklist.

| Role | Name | Responsibility |
|---|---|---|
| Notifications lead / document owner | Priya Mehta | All technical decisions; 14-day and 60-day validation reviews; escalation first contact; tier reassignment approval (§0.4) |
| Project lead | **[name required before distribution]** | Kickoff checklist completion and sign-off; all deadline-setting responsibilities identified in §0.3; infrastructure purchasing sign-off; escalation if Priya Mehta unavailable |
| Product lead | **[name required before distribution]** | DM usage pattern clarification (§1.1.2); Tier 1 SMS degradation sign-off (§0.3); tier reassignment approval (§0.4); final escalation point |

**Simultaneous unavailability of Priya Mehta and project lead:** Decision authority passes by a single unambiguous criterion: years of tenure on this team, with ties broken by date of hire (earlier hire ranks higher). This ranking must be recorded explicitly in §A item 5 at kickoff — it is not determined in the moment of an incident. The highest-ranked available engineer assumes temporary ownership of all time-sensitive decisions, contacts the product lead within 24 hours, and designates a permanent replacement within 48 hours. The ranking is reviewed and updated whenever team composition changes.

The tenure ranking in §A item 5 is not optional. If the kickoff checklist is signed without populating §A item 5, the escalation chain is incomplete and the document owner must refuse to accept the sign-off.

### §0.3 Legal Review — Scope, Owner, Deadline, and Contingency

**What the legal review covers:** SMS and email channel implementation (§1.6 and §1.7) requires compliance verification for: TCPA consent requirements for SMS in the United States; CAN-SPAM and GDPR requirements for email including unsubscribe mechanics, data residency for EU users, and retention limits on notification preference data; and any jurisdiction-specific opt-in requirements for push notifications beyond Apple and Google platform requirements.

**What the legal review does not cover:** Push notification delivery mechanics (§1.4), in-app notification store (§1.5), and all infrastructure decisions (§1.9) are not gated on this review. Work on those sections proceeds on the main timeline.

**Owner:** [Legal counsel name — required before distribution. Project lead is responsible for identifying this person and recording the name here and in §A item 3 before kickoff checklist sign-off.]

**Deadline: [DATE TO BE INSERTED BY PROJECT LEAD AT KICKOFF]**

This date is set by the project lead as: the planned SMS/email implementation start date minus six weeks. The project lead must insert a calendar date here, not a formula. A formula is not a deadline. To make the constraint concrete: if SMS/email implementation is planned for month four of the six-month timeline, the legal review deadline is approximately the end of month two. If this field still contains a formula or placeholder at the time the kickoff checklist is signed, the project lead has not completed their responsibility and the sign-off is invalid.

**Contingency if the deadline is missed — Tier 1 degradation acknowledged:**

If the legal review is not complete by the stated deadline, SMS and email channel implementation is deferred. This has a direct consequence for Tier 1 security notifications that must be acknowledged explicitly and cannot be silently defaulted.

Tier 1 security events use the delivery sequence push → SMS → email. SMS serves as fallback when push fails — for example, when a user has no registered push token, has uninstalled the app, or has disabled push at the OS level. If SMS is unavailable, a user in that situation receives a security notification only via email. Email is a weaker fallback: it is slower, less likely to produce immediate attention, and more likely to land in spam filters.

This degradation affects real users. A user who has uninstalled the app and has email notifications filtered to spam may receive no effective security alert. This is a user safety consequence, not only an infrastructure monitoring problem. The following steps are required if SMS is deferred, and none of them are implied by silence or inaction:

1. **Product lead written sign-off** on operating without SMS fallback for Tier 1 events, with explicit acknowledgment of the user safety consequence described above. This sign-off is recorded in §A item 6.

2. **User-facing disclosure decision:** The product lead must decide, in writing, whether affected users — those without valid push tokens — are notified that their security alert delivery may be delayed. The options are: (a) notify affected users proactively that they should ensure email notifications are enabled; (b) accept the degradation silently and document the rationale. Option (b) requires stronger written justification than option (a). The product lead's decision is recorded in §A item 6 alongside the sign-off. This decision must be made before launch, not after.

3. **Tier 1 delivery logic update:** The delivery logic must reflect the actual available channels before launch. Monitoring and alerting must not reference SMS as an available channel if it has not shipped.

4. **Measurement:** The fraction of users without a valid push token must be measured during the first week of operation. If it exceeds 10%, the product lead and project lead are notified immediately. This threshold triggers a mandatory review of whether the user-facing disclosure decision in step 2 remains appropriate given the actual affected population size.

5. **Priority ordering:** SMS legal clearance is treated as the highest-priority legal task, ahead of email, because of its Tier 1 dependency. The product lead owns escalating this with legal counsel.

If the revised legal review date falls within the six-month delivery window, SMS ships in the final sprint with reduced scope if necessary. If it falls outside the window, SMS is explicitly descoped from v1 and documented as v2 work, with the Tier 1 degradation formally acknowledged in the v2 planning document. This decision requires product lead sign-off and is not made unilaterally by the backend team.

### §0.4 Event Type Tier Assignment — Governance Process

§1.2 establishes that tier assignments are immutable at the per-notification level and can only be changed by modifying the event type definition. This section defines the governance process for those changes. An immutability guarantee without a change process is not a safety property — it is an undocumented bottleneck.

**Who can initiate a tier reassignment:** Any engineer, product manager, or legal counsel may propose a tier reassignment. The proposal must be submitted in writing to Priya Mehta and must include: the event type being reassigned, the current tier, the proposed tier, the reason for the change, and the expected volume impact.

**Review required:** Tier reassignments require sign-off from Priya Mehta (technical correctness and load impact) and the product lead (user experience and product intent). Legal counsel sign-off is additionally required if the change affects a channel with regulatory implications.

**Alternate approver when Priya Mehta is unavailable:** If Priya Mehta is unavailable and the reassignment is classified as urgent, technical sign-off authority passes to the highest-ranked available engineer per the tenure ranking in §A item 5 — the same criterion used for simultaneous unavailability in §0.2. There is no scenario in which an urgent tier reassignment is blocked solely because Priya Mehta is unavailable. The alternate approver must notify Priya Mehta of any reassignment made in her absence within 24 hours of her return.

**Handling in-flight notifications during a tier reassignment — the race condition:** When a tier reassignment is deployed, notifications for the same event type may be in the system simultaneously under different tier assignments. Notifications created before the deployment timestamp process under the original tier; those created after process under the new tier. This is intentional and correct for most reassignments, but it creates a specific hazard for security event elevations.

If a reassignment elevates a security event to Tier 1 — for example, because a new attack vector has been identified — queued notifications created before the deployment timestamp will continue processing under the lower original tier and will not receive the expedited delivery path. Operators must handle this explicitly:

- The deployment record must flag whether the reassignment is an elevation (lower → higher tier) or a demotion (higher → lower tier).
- For elevations affecting security events: the deploying engineer must manually inspect queue depth for the affected event type at deployment time. If queued notifications exist under the original tier, the on-call engineer decides whether to drain the queue before deploying or accept that a bounded number of notifications will process under the old tier. That decision is documented in the deployment record.
- Queue depth monitoring surfaces the backlog size before and after deployment so the scope of the race window is visible.

**Turnaround expectations:**
- Non-urgent reassignments: reviewed within one sprint cycle.
- Urgent reassignments (e.g., a legal requirement discovered post-launch): reviewed within 48 hours, with the product lead and legal counsel notified immediately. The alternate approver path applies if Priya Mehta is unavailable during this window.

---

## Part 1: Technical Design

### §1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app. The working figure is 2.5M DAU (25% DAU/MAU ratio). This ratio must be validated against actual product analytics at the 14-day review.

#### §1.1.1 Compounded Assumption Risk and the Provisioning Choice

The peak throughput figure used for provisioning is derived by multiplying three independent estimates:

1. **DAU/MAU ratio:** assumed at 25% (2.5M DAU). Plausible range: 20–45%.
2. **Notification rate per DAU:** assumed per event type in §1.1.2. Drawn from general social app benchmarks, not product-specific data.
3. **Evening peak multiplier:** assumed at 3×. Not supported by product-specific data.

Compounding three independent assumptions produces uncertainty that cannot be fully quantified before launch. The direction of risk is asymmetric: a highly engaged user base tends to produce higher values on all three dimensions simultaneously, because engagement, notification density, and peak concentration are correlated.

**The provisioning choice — an honest accounting:** The provisioning target uses 2× headroom over the estimated peak. This is a cost decision and deserves honest justification rather than circular reasoning.

The case for 2×: (a) queue buffering absorbs spikes while auto-scaling responds, typically within 2–5 minutes, so short-window under-provisioning produces backlog rather than dropped notifications; (b) the validation process in §1.1.4 replaces assumptions with measurements within 14 days of launch, after which provisioning can be adjusted based on real data; (c) baseline instances are intentionally set at 2× projected peak from day one as additional insurance, meaning effective starting headroom is higher than the steady-state target.

The honest case against 2×: if all three compounding assumptions are simultaneously wrong in the same direction, actual peak could substantially exceed the provisioning target. 3× or 4× headroom would reduce that risk. The reason 2× is chosen over 3× is cost, not superior engineering certainty. The estimated cost difference between 2× and 3× headroom at projected load is approximately **[dollar figure — project lead to obtain from infrastructure vendor before purchasing commitment]**. If that figure is small relative to project budget, the project lead should revisit this choice before purchasing is finalized.

This is the complete justification for 2×: it is cheaper, queue buffering limits the consequence of being wrong in the short term, and the validation process limits the duration of exposure to unvalidated estimates. The choice is documented so it can be revisited when cost figures are available.

**What 2× does not cover:** A simultaneous worst-case on all three assumptions. That scenario is addressed through queue buffering and the validation process, not additional static provisioning.

#### §1.1.2 Notification Volume Estimates

**Benchmark sourcing:** The per-event rates below are drawn from published industry analyses of social apps at comparable scale. The specific sources are listed in §A item 2. §A item 2 must be populated before any infrastructure purchasing decision is made — not as a formality, but because the appropriate benchmarks depend on the product's category. A messaging-first app has a materially different notification profile than a photo-sharing or interest-graph app. The product lead must confirm the product's primary category before the rates below are treated as applicable, and that confirmation is recorded in §A item 2 alongside the sources.

Any single rate could be off by 2–5× in either direction. These are order-of-magnitude planning figures, not forecasts.

**DM volume — clarification required before infrastructure purchasing:**

The direct message row assumes each DM sender reaches one recipient per day. This is a placeholder. If the product supports group messaging, DM notification volume scales linearly with the average recipients per sender.

Full impact of the high-end assumption: at 5 recipients per sender, DM notifications rise from 500,000 to 2,500,000 per day. Total daily volume rises from approximately 1.3M to approximately 3.3M — a 2.5× increase. The downstream provisioning target rises from approximately 130 to approximately 325 notifications/second. This is a material infrastructure cost difference.

**Required action:** The product lead must specify the expected DM usage pattern (1-to-1 vs. group; if group, expected average recipients per sender) before any infrastructure purchasing commitment. This clarification is recorded in §A item 4.

**Owner:** [product lead name — from §0.2 table]

**Deadline: [DATE TO BE INSERTED BY PROJECT LEAD AT KICKOFF — at least two weeks before any infrastructure purchasing commitment. A formula is not a deadline. The project lead inserts a calendar date.]**

**If this clarification is not received by the stated deadline:** The provisioning target is recomputed using the high-end DM assumption (5 recipients per sender), yielding approximately 325 notifications/second. The resulting cost increase is documented and escalated to the product lead for sign-off. Infrastructure purchasing does not proceed on the low-end assumption after the deadline passes without a response. The project lead owns this escalation.

| Event type | Rate assumption | Basis | Daily volume |
|---|---|---|---|
| Post liked | 15% of DAU trigger one like notification | General benchmark [§A item 2] | 375,000 |
| Comment received | 8% of DAU receive one comment notification | General benchmark | 200,000 |
| New follower | 5% of DAU | General benchmark | 125,000 |
| Mention | 3% of DAU | General benchmark | 75,000 |
| Direct message | 20% of DAU send at least one; 1 recipient per sender (placeholder — see above) |