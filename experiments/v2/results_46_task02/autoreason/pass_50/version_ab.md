# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

**Document version:** 8.0
**Document owner:** Priya Mehta (notifications lead)
**Last revised:** [date]
**Status:** Draft — see §0.1 for the specific conditions that must be met before this document is distributed to any stakeholder

---

## Table of Contents

- §0 Preface
  - §0.1 Distribution Gate — Conditions Required Before Circulation
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
- §A Kickoff Checklist (full text — not a reference to a separate document)
- §B Project Timeline and Milestone Definitions

---

## §0 Preface

### §0.1 Distribution Gate — Conditions Required Before Circulation

This section exists because an earlier version of this document instructed readers not to distribute it before certain fields were populated, while simultaneously circulating it as a draft with those fields empty. That approach is self-defeating: the warning is only readable by people who have already received the document in an incomplete state. This version corrects that by making the distribution gate explicit and enforceable before the document leaves the document owner's hands.

**This document must not be sent to any stakeholder — including engineers on the team — until all five conditions below are satisfied.** The project lead and document owner jointly certify these conditions by signing §A item 1. If you are reading this document and §A item 1 is unsigned, you have received it prematurely and should notify the document owner.

1. §0.2 owner table is fully populated with real names. No placeholder rows remain.
2. §A (kickoff checklist) is complete and signed, including the tenure ranking in §A item 5.
3. The legal counsel name is recorded in §0.3 and in §A item 3.
4. The project timeline in §B is populated with calendar dates for all milestones.
5. The product lead has confirmed the product's primary category per §1.1.2, and that confirmation is recorded in §A item 2.

Condition 5 is required before distribution because the benchmark rates in §1.1.2 are only applicable to the correct product category. Distributing the document with unvalidated benchmark rates creates a false impression of analytical rigor. If the product category confirmation has not been obtained, the document owner holds the document rather than circulating it with a note that confirmation is pending.

---

### §0.2 Named Owners and Escalation Chain

**This table must be fully populated before this document is distributed. See §0.1.**

| Role | Name | Responsibility |
|---|---|---|
| Notifications lead / document owner | Priya Mehta | All technical decisions; 14-day and 60-day validation reviews (§1.1.4); escalation first contact; tier reassignment approval (§0.4) |
| Project lead | **[name — required before distribution, per §0.1 condition 1]** | §B timeline population; kickoff checklist sign-off; legal counsel identification (§0.3); infrastructure purchasing sign-off; escalation if Priya Mehta unavailable |
| Product lead | **[name — required before distribution, per §0.1 condition 1]** | Product category confirmation (§1.1.2); DM usage pattern clarification (§1.1.2); Tier 1 SMS degradation sign-off (§0.3); tier reassignment approval (§0.4); user-facing disclosure decision (§0.3); final escalation point |

**Simultaneous unavailability of Priya Mehta and project lead:** Decision authority passes by a single unambiguous criterion: years of tenure on this team, with ties broken by date of hire (earlier hire ranks higher). This ranking must be recorded in §A item 5 at kickoff — it is not determined in the moment of an incident. The highest-ranked available engineer assumes temporary ownership of all time-sensitive decisions, contacts the product lead within 24 hours, and designates a permanent replacement within 48 hours. The ranking is reviewed and updated whenever team composition changes.

The tenure ranking in §A item 5 is not optional. If the kickoff checklist is signed without populating §A item 5, the document owner must refuse to accept the sign-off. §A item 5 is reproduced in full in §A below — it is not a reference to a separate document, and its contents are inspectable by any reviewer of this document.

---

### §0.3 Legal Review — Scope, Owner, Deadline, and Contingency

**What the legal review covers:** SMS and email channel implementation (§1.6 and §1.7) requires compliance verification for: TCPA consent requirements for SMS in the United States; CAN-SPAM and GDPR requirements for email including unsubscribe mechanics, data residency for EU users, and retention limits on notification preference data; and any jurisdiction-specific opt-in requirements for push notifications beyond Apple and Google platform requirements.

**What the legal review does not cover:** Push notification delivery mechanics (§1.4), in-app notification store (§1.5), and all infrastructure decisions (§1.9) are not gated on this review. Work on those sections proceeds on the main timeline.

**Owner:** [Legal counsel name — required before distribution, per §0.1 condition 3. Project lead is responsible for identifying this person and recording the name here and in §A item 3 before kickoff checklist sign-off.]

**Legal review deadline:** [Calendar date — to be inserted by project lead at kickoff, per §B milestone M3. This date is: SMS/email implementation start date (§B milestone M4) minus six weeks. The project lead reads the M4 date from §B and subtracts six weeks to produce a calendar date here. A formula is not a deadline. A calendar date is required.]

To make the constraint concrete: if SMS/email implementation is planned for month four of the six-month timeline, the legal review deadline is approximately the end of month two. §B must be populated with calendar dates before this field can be set, which is why §B population is a distribution gate condition in §0.1. The sequencing is self-consistent: the project lead cannot complete this field without a populated §B, which means the distribution gate is not satisfied, which means the document is not distributed.

**Contingency if the deadline is missed — Tier 1 degradation acknowledged:**

If the legal review is not complete by the stated deadline, SMS and email channel implementation is deferred. This has a direct consequence for Tier 1 security notifications that must be acknowledged explicitly and cannot be silently defaulted.

Tier 1 security events use the delivery sequence push → SMS → email. SMS serves as fallback when push fails — for example, when a user has no registered push token, has uninstalled the app, or has disabled push at the OS level. If SMS is unavailable, a user in that situation receives a security notification only via email. Email is a weaker fallback: it is slower, less likely to produce immediate attention, and more likely to land in spam filters. A user who has uninstalled the app and has email filtered to spam may receive no effective security alert. This is a user safety consequence, not an infrastructure monitoring problem.

The following steps are required if SMS is deferred. None are implied by silence or inaction.

**Step 1 — Product lead written sign-off:** The product lead signs off on operating without SMS fallback for Tier 1 events, with explicit acknowledgment of the user safety consequence described above. This sign-off is recorded in §A item 6.

**Step 2 — User-facing disclosure decision:** The product lead must choose one of the following options before launch. The decision is recorded in §A item 6 alongside the sign-off.

- *Option A:* Notify affected users proactively that they should ensure email notifications are enabled, because push delivery cannot be guaranteed.
- *Option B:* Accept the degradation without proactive user notification.

Option B requires written justification addressing: (i) the estimated size of the affected population (users without valid push tokens, measured per step 4 below); (ii) why the safety risk to that population is acceptable without disclosure; and (iii) whether any regulatory requirement — including GDPR's transparency obligations — affects this decision. Justification for Option B is reviewed by legal counsel before the decision is recorded as final.

If the product lead does not make this decision before the launch gate defined in §B milestone M6, the launch gate is not satisfied and launch does not proceed. The project lead owns escalating a non-response to the product lead's manager. "The product lead did not respond" is not a valid reason to default to either option silently.

**Step 3 — Delivery logic update:** The Tier 1 delivery logic must reflect only actually available channels before launch. Monitoring and alerting must not reference SMS as an available channel if it has not shipped.

**Step 4 — Push token coverage measurement:** The fraction of users without a valid push token is measured during the first week of operation and reported at the 14-day validation review (§1.1.4), with the product lead and legal counsel present. The threshold for triggering a disclosure decision revision is set at that review based on actual data and the specific product and regulatory context, not set in advance without analysis. A threshold derived from real data is more defensible than one set arbitrarily before launch. The measurement result also informs whether any Option B justification recorded in step 2 remains valid given the actual affected population size.

**Step 5 — Priority ordering:** SMS legal clearance is treated as the highest-priority legal task, ahead of email, because of its Tier 1 dependency. The product lead owns escalating this with legal counsel.

If the revised legal review date falls within the six-month delivery window, SMS ships in the final sprint with reduced scope if necessary. If it falls outside the window, SMS is explicitly descoped from v1 and documented as v2 work, with the Tier 1 degradation formally acknowledged in the v2 planning document. This decision requires product lead sign-off and is not made unilaterally by the backend team.

---

### §0.4 Event Type Tier Assignment — Governance Process

§1.2 establishes that tier assignments are immutable at the per-notification level and can only be changed by modifying the event type definition. An immutability guarantee without a defined change process is not a safety property — it is an undocumented bottleneck. This section defines the governance process for those changes.

**Who can initiate a tier reassignment:** Any engineer, product manager, or legal counsel may propose a tier reassignment. The proposal must be submitted in writing to Priya Mehta and must include: the event type being reassigned, the current tier, the proposed tier, the reason for the change, and the expected volume impact.

**Review required:** Tier reassignments require sign-off from Priya Mehta (technical correctness and load impact) and the product lead (user experience and product intent). Legal counsel sign-off is additionally required if the change affects a channel with regulatory implications.

**Alternate approver when Priya Mehta is unavailable:** If Priya Mehta is unavailable and the reassignment is classified as urgent, technical sign-off authority passes to the highest-ranked available engineer per the tenure ranking in §A item 5 — the same criterion used for simultaneous unavailability in §0.2. There is no scenario in which an urgent tier reassignment is blocked solely because Priya Mehta is unavailable. The alternate approver must notify Priya Mehta of any reassignment made in her absence within 24 hours of her return.

**Handling in-flight notifications during a tier reassignment — the race condition:** When a tier reassignment is deployed, notifications for the same event type may be in the system simultaneously under different tier assignments. Notifications created before the deployment timestamp process under the original tier; those created after process under the new tier. This is correct for most reassignments but creates a specific hazard for security event elevations.

If a reassignment elevates a security event to Tier 1, queued notifications created before the deployment timestamp will continue processing under the lower original tier and will not receive the expedited delivery path. Operators must handle this explicitly:

- The deployment record must flag whether the reassignment is an elevation (lower → higher tier) or a demotion (higher → lower tier).
- For elevations affecting security events, the deploying engineer checks queue depth for the affected event type before deploying. The decision criteria are:
  - *Queue depth zero or negligible (fewer than 100 notifications):* deploy immediately. No drain required.
  - *Queue depth between 100 and 10,000 notifications:* the deploying engineer decides whether to drain first, considering that a drain of this size typically takes under five minutes and does not block other event types. The decision and rationale are recorded in the deployment record.
  - *Queue depth exceeds 10,000 notifications:* drain before deploying. At the expected processing rate, 10,000 notifications represents approximately [X minutes — to be computed from §1.9 throughput figures before launch and inserted here]. If the drain duration is unacceptable given the urgency of the elevation, the on-call engineer escalates to Priya Mehta or the alternate approver, who decides whether to accept the race window or halt queue processing during deployment.

These thresholds reflect the following reasoning: below 100 notifications, the practical user safety impact of processing under the wrong tier is negligible. Above 10,000, the affected population is large enough that the decision should not be discretionary. The middle range is where engineering judgment is appropriate. If this reasoning is wrong for a specific event type — for example, a security event where even one missed notification is unacceptable — the event type definition must note that explicitly, and the deploying engineer must drain regardless of queue depth.

- Queue depth monitoring surfaces backlog size before and after deployment so the scope of the race window is visible and recorded.

**Turnaround expectations:**
- Non-urgent reassignments: reviewed within one sprint cycle.
- Urgent reassignments (e.g., a legal requirement discovered post-launch): reviewed within 48 hours, with the product lead and legal counsel notified immediately.

---

## Part 1: Technical Design

### §1.1 Scale and Load Estimates

10M MAU implies roughly 2–3M DAU on a social app. The working figure is 2.5M DAU (25% DAU/MAU ratio). This ratio must be validated against actual product analytics at the 14-day review (§1.1.4).

#### §1.1.1 Compounded Assumption Risk and the Provisioning Choice

The peak throughput figure used for provisioning is derived by multiplying three independent estimates:

1. **DAU/MAU ratio:** assumed at 25% (2.5M DAU). Plausible range: 20–45%.
2. **Notification rate per DAU:** assumed per event type in §1.1.2. Drawn from general social app benchmarks, not product-specific data.
3. **Evening peak multiplier:** assumed at 3×. Not supported by product-specific data.

Compounding three independent assumptions produces uncertainty that cannot be fully quantified before launch. The direction of risk is asymmetric: a highly engaged user base tends to produce higher values on all three dimensions simultaneously, because engagement, notification density, and peak concentration are correlated.

**The provisioning choice — an honest accounting:**

The provisioning target uses 2× headroom over the estimated peak. This is a cost decision and deserves honest justification rather than circular reasoning.

The case for 2×: (a) queue buffering absorbs spikes while auto-scaling responds, typically within 2–5 minutes, so short-window under-provisioning produces backlog rather than dropped notifications; (b) the validation process in §1.1.4 replaces assumptions with measurements within 14 days of launch, after which provisioning is adjusted based on real data; (c) baseline instances are set at 2× projected peak from day one, meaning effective starting headroom is higher than the steady-state target.

The honest case against 2×: if all three compounding assumptions are simultaneously wrong in the same direction, actual peak could substantially exceed the provisioning target. 3× or 4× headroom would reduce that risk. The reason 2× is chosen over 3× is cost, not superior engineering certainty.

**The cost comparison must be obtained before the provisioning choice is finalized.** The project lead obtains the cost difference between 2× and 3× headroom at projected load from the infrastructure vendor and records it in §A item 7 before any purchasing commitment. The provisioning choice is not final until §A item 7 is populated. If the cost difference is less than 15% of the total six-month infrastructure budget — the project lead applies this criterion to the actual figures and documents the result — the project lead must bring the 3× option back to Priya Mehta for reconsideration before purchasing is finalized.

This is the complete justification for 2×: it is cheaper, queue buffering limits the