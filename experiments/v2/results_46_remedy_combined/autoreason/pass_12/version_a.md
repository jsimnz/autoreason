# Notification System Design — Synthesized Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## How to Read This Document

This is a forward-facing design specification. Where a decision required choosing between alternatives, the choice and reasoning are stated inline. Where a decision requires authorization outside engineering, the responsible role, required decision, and deadline are identified explicitly.

Fifteen specific design decisions are addressed explicitly. Each is stated as a named commitment, not a hedged preference. Where a decision requires authorization outside the engineering team, it is identified with a named owner, a deadline, and an escalation path that does not terminate in an engineering role.

**Sections:**
1. Scale Model
2. Delivery Architecture and Priority Logic
3. Channel Specifications (Push, Email, SMS, In-App)
4. In-App Notification Store
5. Infrastructure and Cost
6. Failure Handling
7. Compliance and Preference Management
8. Team Scope and Feasibility

---

## Executive Summary

This proposal designs a notification system handling 20–225M notifications/day across push, email, in-app, and SMS channels. The architecture makes four core bets:

1. **Durable managed queuing over custom Redis structures.** AWS SQS provides at-least-once delivery guarantees, dead-letter queues, and operational maturity that a 4-engineer team cannot replicate in 6 months. Redis is used for caching preference reads, not as the delivery backbone.

2. **Proven third-party delivery providers over self-operated infrastructure.** FCM/APNs for push, SendGrid for email, Twilio for SMS. Each provider is abstracted behind a thin interface layer; substitution is possible without architectural change.

3. **Incremental delivery with explicit failure handling over optimistic pipelines.** Every notification that cannot be delivered is written to a dead-letter queue with a structured failure record. No notification is silently dropped.

4. **A preference system whose cache TTL is a performance optimization, not a compliance mechanism.** Opt-outs are enforced by writing a suppression flag to the database synchronously on receipt. If the database is unavailable when a worker checks suppression, the worker **fails closed** — the notification is not delivered. This is a deliberate compliance decision with an explicit operational cost: during a database outage, no notifications are sent. The alternative — delivering notifications during an outage and reconciling after — creates compliance exposure that outweighs the availability cost.

**Fifteen specific design decisions:**

1. **Opt-out staleness is not a compliance solution.** Suppression flags are written synchronously to the database on opt-out receipt. Cache TTL governs read performance only. Fail-closed behavior on database unavailability is fully specified in Section 7.

2. **Alarm thresholds during Weeks 1–2 use pre-launch load test baselines.** A 14-day rolling average promotes to replace the load test baseline after 7 consecutive stable days. "Stable" is defined as: no Warning-tier or higher alarms fired, AND observed traffic is within 20% above and 10% below the rolling average for that day. The asymmetric bounds are intentional: a traffic spike cannot contaminate its own baseline, and an outage day (traffic 10%+ below average) is excluded to prevent the baseline from drifting downward. Section 1.4 specifies the full definition.

3. **Digest email halt has an explicit resumption SLA with weekend and holiday coverage.** Resumption requires compliance owner sign-off within 4 business hours on business days. A halt occurring Friday after 5 PM local time or on a public holiday triggers a named on-call compliance contact with a 2-hour response SLA regardless of business hours. The escalation path and on-call rotation are specified in Section 3.2. The escalation path does not terminate in an engineering role.

4. **Volume anomalies trigger a three-check automated diagnostic.** The `optin_source` check uses a registry table, not string matching against examples. The registry is owned by a named role, updated through a defined process, and its absence triggers Path B rather than a silent pass. Section 1.3 specifies the full design including registry mechanics and failure modes.

5. **Population boundaries are principled and consistent.** SMS OTP and security alerts are DAU-bounded because they are triggered by session events. Credential breach notifications are MAU-bounded because they are proactive administrative actions not bounded by session state. The credential breach scenario is fully costed in Section 5.3. Every row in the population table identifies which boundary applies and why.

6. **Provisioning for the aggressive scenario is justified on cost-of-uncertainty grounds.** The ~$160/month delta between SendGrid plan tiers is the cost of insuring against under-provisioning given irreducible pre-launch uncertainty. This is a cost-of-uncertainty argument, not a forecast.

7. **OTP email fallback has an explicit upper bound, cost model, and OTP lifetime dependency.** The 60-second P95 delivery SLA is only acceptable if the application's OTP lifetime is ≥90 seconds. If OTP lifetime is shorter, the SLA must tighten or the fallback must be reconsidered. OTP lifetime is a required input from the product team; the named owner and decision deadline are in Section 3.4.

8. **Peak factor sensitivity is fully specified.** Section 2.5 covers 3×, 5×, 8×, and 10× peak factors with explicit arithmetic showing queue depth, worker count, and scaling trigger at each factor.

9. **The blended opt-in rate is replaced with a methodology-consistent figure.** A single source (OneSignal prompt-conversion benchmarks) combined with an explicit platform mix assumption yields a 60% base rate modeled over a 45–75% range. A Day 3 production measurement protocol is specified; if the observed platform split differs from the assumed 60/40 iOS/Android by more than ±10 percentage points, the cost model is recalibrated before Week 2 closes.

10. **In-app notification durability is fully specified.** Retention policy: 90 days for read notifications, 365 days for unread. Storage growth model and archival strategy keep the hot store bounded. Full specification in Section 4.

11. **SQS FIFO throughput ceiling is addressed before launch.** P1 notifications use per-conversation message group IDs. The documented SQS FIFO ceiling is 3,000 messages/second per queue. Horizontal sharding design is specified in Section 2.4 and implemented pre-launch, not deferred.

12. **Team scope is explicitly examined.** Section 8 maps every component to specific engineer roles and time budgets. The original scope is not fully deliverable in 6 months by 4 engineers. A phased scope reduction with explicit tradeoffs is proposed.

13. **The OTP fallback conversion assumption is stated as an assumption with a sensitivity range.** The 40% figure is a planning estimate. The full range and the decision threshold at which the fallback becomes a material budget line are specified in Section 3.4.

14. **The WAND estimate problem at steady state is addressed directly.** The compliance diagnostic threshold is a dynamic value recalibrated on a defined schedule against the consent ledger count, not a fixed figure derived from the WAND estimate. Section 1.3 specifies the recalibration schedule and the failure mode of a lagging threshold.

15. **The `optin_source` check uses a registry table with a defined ownership and update process.** A new legitimate source not registered in the table triggers Path B on valid sends — this is a known false-positive risk. The registry update process is designed to make registration fast (under 30 minutes) so the false-positive window is narrow. Section 1.3.1 specifies the registry design, ownership, and update process.

---

## 1. Scale Model

### 1.1 Population Definitions

Two population figures appear throughout this document. They are not interchangeable. Every volume estimate identifies which one it uses and why.

**MAU (10M):** Monthly active users. Used for push opt-in estimates and credential breach notifications. Push tokens are registered at install and persist across sessions; a user who opens the app once per month retains their token.

**DAU:** Daily active users, modeled at 35% of MAU (3.5M) for pre-launch sizing. Used for SMS OTP modeling, in-app delivery estimates, and alarm baseline calibration. The 35% figure is a planning assumption, not a measurement. All operational thresholds that depend on DAU are expressed as multiples of a load-test-anchored baseline — not as absolute figures derived from the 35% assumption. See Section 1.4.

**WAND (Weekly-Active-Not-Daily):** Users active in a given week but not on a given day. Used for digest email modeling at steady state. Cannot be meaningfully estimated until Day 7 of production traffic; a stable estimate requires Week 4. The 2M base estimate is the largest single unknown in the volume model. The compliance diagnostic threshold is calibrated against the consent ledger count, not the WAND estimate — this is addressed directly in Section 1.3.

| Model | Population | Boundary Type | Why |
|-------|-----------|--------------|-----|
| Push opt-in base | MAU (10M) | Install-bounded | Token persists; opt-in is a device setting |
| Push volume | Opted-in MAU | Install-bounded | Notifications sent to opted-in users |
| SMS OTP / security alerts | DAU (measured) | Session-bounded | Triggered by active session events |
| In-app | DAU (measured) | Session-bounded | Delivered to active sessions |
| Digest email | WAND (estimated until Week 4) | Engagement-bounded | Target audience; see Section 1.3 |
| Transactional email | Event-driven | Event-bounded | Not population-derived |
| Credential breach notification | MAU (10M) | Administrative | Proactive action; not bounded by session state |

The credential breach row is the only place in this document where MAU is used for an SMS model. The principled boundary is trigger type: SMS OTP and security alerts are session-bounded. A credential breach notification is a proactive administrative action sent to all affected accounts regardless of session state. Any model that switches population without this explanation is a bug. This table is the reference. The cost of a full-MAU credential breach SMS send is modeled explicitly in Section 5.3.

---

### 1.2 Push Opt-In Rate

**Why the prior blended figure is withdrawn:**

Three sources were previously averaged into a "55% blended" opt-in rate. Those sources use incompatible measurement methodologies:

- **Airship (2023):** Measures the fraction of an app's installed base that has push enabled at a point in time. An installed-base metric.
- **OneSignal (2023):** Measures the fraction of users who grant permission when shown a push permission prompt. A prompt-conversion metric.
- **AppsFlyer (2023):** Measures the effect of prompt timing on prompt-conversion rate. A prompt-design variable, not a standalone opt-in rate.

Averaging these produces a number with no coherent interpretation. The blended figure is withdrawn.

**Replacement approach — single methodology-consistent source:**

We use OneSignal prompt-conversion benchmarks for social apps (iOS ~49%, Android ~81%) as the sole source. This is the right measurement for sizing a new app's opted-in population: it measures what happens when a new user is shown a permission prompt.

**Acknowledged limitation:** OneSignal's benchmarks are derived from apps that chose OneSignal as their push provider — a self-selected sample. We cannot quantify this selection bias before launch. It is an irreducible source of uncertainty.

**Platform mix assumption:** 60% iOS / 40% Android, based on US smartphone OS market share. This is the most uncertain single input in the calculation.

Weighted opt-in rate: (0.60 × 49%) + (0.40 × 81%) = **61.8%**, rounded to **60%** base.

| Platform Mix (iOS/Android) | Weighted Opt-In Rate |
|---------------------------|---------------------|
| 40/60 | 68.2% |
| 50/50 | 65.0% |
| **60/40 (assumed)** | **61.8%** |
| 70/30 | 58.6% |

**Day 3 measurement protocol:**

On Day 3 of production, the platform mix is read directly from device registration logs. This is a direct measurement, not an estimate — every push token registration records the OS.

**Decision rule:** If the observed iOS share differs from the assumed 60% by more than ±10 percentage points (i.e., observed iOS share is outside the 50%–70% range), the cost model is recalibrated before Week 2 closes.

**Why ±10 points:** The sensitivity table shows that moving from 60/40 to 50/50 changes the opt-in rate from 61.8% to 65.0% — a 3.2-point change that shifts push volume by roughly 5%, within planning tolerance. Moving from 60/40 to 40/60 changes the opt-in rate to 68.2% — a 6.4-point change that shifts push volume by roughly 10% and may require plan tier reassessment. The ±10-point threshold triggers recalibration at the point where cost impact becomes material.

**Operational response if recalibration is needed:** The infrastructure lead (Engineer A, Section 8) produces a revised cost model within 2 business days of Day 3. If the revised model requires a plan tier change, the decision is escalated to the engineering manager and product owner with a 24-hour decision window. The system can operate on the existing tier during this window without risk of service disruption — the aggressive scenario is already provisioned.

We model over a **45%–75% range** to cover platform mix uncertainty and source bias. Architecture is sized for 75% opt-in at 30 notifications/day. Costs are modeled at 60% at 15 notifications/day. The Week 1 production measurement supersedes this estimate.

**Sensitivity table:**

| Opt-In Rate | 5 notifs/user/day | 15 notifs/user/day | 30 notifs/user/day |
|-------------|-------------------|--------------------|--------------------|
| 45% (4.5M users) | 22.5M/day | 67.5M/day | 135M/day |
| 60% (6M users) | 30M/day | 90M/day | 180M/day |
| 75% (7.5M users) | 37.5M/day | 112.5M/day | 225M/day |

---

### 1.3 Email Volume

**Transactional and digest email use separate IP pools.** A spam complaint spike from digest mail can blacklist the pool used for password resets. This is a deliverability decision with direct revenue impact and is not negotiable.

**Transactional email:**

| Event | Daily Volume | Basis |
|-------|-------------|-------|
| Account verification | ~50K | ~0.5% of MAU/day |
| Password reset | ~30K | ~0.3% of MAU/day |
| Security alerts — new device login | ~100K | ~1% of MAU/day |
| Billing / policy notices | ~50K | Estimated |
| OTP email fallback | Variable; see Section 3.4 | Activated when SMS rate-limited |
| **Total** | **~230K–500K/day** | |

Alert threshold: >750K/day sustained for 30+ minutes. 50% above ceiling signals a security incident or instrumentation error.

**Digest email:**

| Scenario | WAND Segment | Digest Opt-In | Daily Volume |
|----------|-------------|---------------|-------------|
| Conservative | 1M users | 20% | ~120K/day |
| Base estimate | 2M users | 40% | ~526K/day |
| Aggressive | 3M users | 60% | ~1.3M/day |

**The measurement timeline:**

*Days 1–6:* No digest sends. The eligible population is zero — you cannot send a weekly digest before a week has elapsed. No measurement problem exists during this period.

*Day 7 — First digest send:* Volume is bounded by users who completed onboarding in Week 1 and opted into digest email during that flow. This is a directly measurable count from the consent ledger, not a WAND estimate.

*Days 7–27 (Weeks 1–4):* Digest send volume grows as more users complete their first week and become eligible. The eligible population is fully enumerable from the consent ledger.

*Week 4 onward:* The WAND population is now estimable from session logs. Steady-state digest volume depends on WAND.

**The WAND steady-state problem — addressed directly:**

The prior version argued the WAND estimate was "irrelevant" during Weeks 1–4. This is true for the ramp phase but sidesteps the steady-state problem: if the WAND estimate is wrong at steady state, a fixed threshold of 1.3M/day is miscalibrated.

**Resolution — dynamic threshold recalibration:**

The diagnostic threshold is not a fixed number derived from the WAND estimate. It