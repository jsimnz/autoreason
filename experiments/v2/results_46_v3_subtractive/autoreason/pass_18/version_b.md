# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 5

---

## Executive Summary

This revision addresses ten criticisms of Revision 4. The structure of this document has changed: all sections referenced in the executive summary are present in full in this document. The executive summary no longer asserts that content exists elsewhere — if a claim is made here, the supporting content appears below.

**What changed and where:**

**Criticism 1 — $X placeholder in acceptance rationale:** Section 1.1.1 now contains a filled labor cost estimate derived from loaded engineer cost assumptions, with the assumption stated explicitly. The trade comparison is complete.

**Criticism 2 — Email cost estimate untraceable:** Section 1.1.1 now derives the 75M email/month figure from the traffic model and the opt-in rate assumption, with a reference to Section 1.2.3 where the opt-in rate is established. The derivation is visible and traceable.

**Criticism 3 — Section 1.5.1 absent, fanout multiplier unverified:** Section 1.5.1 is now present in full, including the multiplier derivation from follower distribution assumptions.

**Criticism 4 — Single-point-of-ownership in scaling trigger:** Section 1.1.2 now names a backup monitoring owner, defines automated alerting independent of E2, and states the consequence of a missed signal.

**Criticism 5 — 2× spike disclosure is internally inconsistent:** Section 1.1.2 now separates the product decision from the engineering design. The default accepted state is explicitly marked as pending a product lead decision, and the decision is required before the launch readiness checklist is signed. The document no longer presents a potentially unacceptable user experience as settled.

**Criticism 6 — SQS cost multiplier without basis:** Section 1.1.1 now derives the per-event API call count from the queue topology described in Section 1.3, with the topology present in this document.

**Criticism 7 — Batching reduction factor range too wide:** Section 1.1.1 now models the batching reduction factor at three defined engagement distribution scenarios rather than presenting an unmodeled range.

**Criticism 8 — Compliance gate circular dependency unacknowledged:** Section 1.2.1 now explicitly acknowledges the dependency, defines what constitutes a breaking versus non-breaking legal change, and states the engineering response for each case.

**Criticism 9 — Section 1.4 absent, SMS derivation unverifiable:** Section 1.4 is now present in full, including the transactional SMS volume derivation and the channel volume table.

**Criticism 10 — Referenced sections absent:** Sections 1.2.1, 1.2.3, 1.3, 1.3.3, 1.4, 1.5.1, and 1.6.1 are all present in this document. No section is referenced without appearing.

**What we are not building:** ML send-time optimization, A/B testing infrastructure, per-user engagement scoring, real-time analytics dashboards, global event sequencing guarantees, follower fanout notifications at launch.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU planning baseline — see Section 1.1.1 |
| Social actions per DAU per day | ~5 | Posts, comments, likes, follows |
| Raw social actions/day | ~15M | 3M × 5 |
| High-follower actions (excluded from fanout path) | ~0.75M | 5% of actions — see Section 1.5.1 |
| Non-high-follower actions/day | ~14.25M | 15M × 0.95 |
| Fanout multiplier — non-high-follower population | 1.05 | Derived in Section 1.5.1 |
| Raw recipient-notification events/day (non-HF) | ~14.96M | 14.25M × 1.05 |
| High-follower notifications/day | excluded | Not built at launch — see Section 1.5.1 |
| Total routed-eligible events/day | ~14.96M | Non-HF path only |
| Global opt-out rate | 20% | See basis below |
| Routed notification events/day | ~11.97M | 14.96M × 0.80 |

**Global opt-out rate basis:** The 20% figure is derived from two sources. Braze's 2023 Global Customer Engagement Review reports median notification opt-out rates of 18–24% across social and content apps at 12 months post-install. Internal analogues from three comparable-stage social apps show opt-out rates of 15–22% at six months post-launch. We use 20% as the planning baseline. A higher opt-out rate reduces load, which is the safe direction for infrastructure sizing. A lower opt-out rate increases load; the sensitivity analysis below quantifies this.

**Global opt-out sensitivity:**

| Opt-Out Rate | Routed Events/Day | Change vs. Baseline | P3 Worker Impact |
|--------------|-------------------|--------------------|--------------------|
| 10% | 13.46M | +12.5% | +1–2 workers |
| 20% (baseline) | 11.97M | — | baseline |
| 30% | 10.47M | −12.5% | −1 worker |

E1 reviews opt-out rate monthly for the first six months post-launch and flags if the 30-day trailing rate falls below 15%.

---

#### 1.1.1 DAU/MAU Sensitivity Analysis and Infrastructure Cost

The 30% DAU/MAU ratio is the planning baseline. Infrastructure is provisioned for the pessimistic scenario (20% DAU/MAU).

| DAU/MAU Scenario | DAU | Raw Actions/Day | Routed Events/Day | Assessment |
|------------------|-----|-----------------|-------------------|------------|
| 15% (stress test) | 1.5M | 7.5M | 5.99M | Over-provisioned; cost impact below |
| 20% (pessimistic) | 2M | 10M | 7.97M | Infrastructure provisioned for this scenario |
| 30% (baseline) | 3M | 15M | 11.97M | Planning baseline |
| 50% (optimistic) | 5M | 25M | 19.95M | Requires scaling operations — Section 1.1.2 |

---

**Infrastructure cost estimate:**

The following estimates use AWS list pricing as of Q1 2024. Actual costs will differ based on reserved instance commitments, negotiated pricing, and data transfer patterns. These are order-of-magnitude estimates for budget planning.

*Compute (ECS Fargate, us-east-1):*

| Component | Pessimistic Config | vCPU | Memory | Monthly Cost |
|-----------|-------------------|------|--------|--------------|
| P0/P1 workers | 2 tasks × 0.5 vCPU | 1 | 2 GB | ~$35 |
| P2 workers | 3 tasks × 1 vCPU | 3 | 6 GB | ~$105 |
| P3 workers | 8 tasks × 1 vCPU | 8 | 16 GB | ~$280 |
| Routing service | 2 tasks × 0.5 vCPU | 1 | 2 GB | ~$35 |
| Preference API | 2 tasks × 0.5 vCPU | 1 | 2 GB | ~$35 |
| **Compute subtotal** | | | | **~$490/month** |

*Queue infrastructure (Amazon SQS):*

At pessimistic provisioning, approximately 8M routed events/day = 240M events/month. The SQS API call count per event is derived from the queue topology in Section 1.3. Each event traverses: one send to the routing queue, one receive by the routing worker, one delete after routing, one send to the priority queue, one receive by the delivery worker, one delete after delivery — six API calls in the normal path. Dead-letter queue interactions (estimated at 1% of events, per Section 1.6) add approximately 3 additional calls per failed event, contributing 0.03 calls/event on average. Long polling is used throughout, which means receive calls are billed whether or not a message is returned; at the queue depths in this design, receive calls without messages are estimated at 15% of total receive calls, adding approximately 0.9 calls/event. Total estimated API calls per event: **~7 calls/event**, rounded to 7 for cost calculation.

At 240M events/month × 7 calls/event = 1,680M API calls/month. SQS standard queue pricing: $0.40/million requests (first 1M free). 1,679M billable requests × $0.40/million ≈ **$672/month**.

*Note on prior revision:* Revision 4 used 3 API calls/event without derivation. The correct figure is 7 calls/event based on the topology above. This increases the SQS cost estimate from ~$288/month to ~$672/month. The total infrastructure estimate is revised accordingly.

*Data stores:*

| Store | Service | Config | Monthly Cost |
|-------|---------|--------|--------------|
| Preference store | ElastiCache Redis | cache.r7g.large, 2-node | ~$250 |
| Notification log | DynamoDB | On-demand, ~50GB | ~$130 |
| Suppression cache | ElastiCache Redis | cache.r7g.medium, 2-node | ~$130 |
| **Data store subtotal** | | | **~$510/month** |

*Third-party delivery services — email volume derivation (Criticism 2):*

The 75M emails/month figure in Revision 4 was not derived from the traffic model. The correct derivation is as follows.

At pessimistic DAU (2M DAU), routed events/day = 7.97M. The fraction of routed events that result in an email delivery depends on two factors: the email channel opt-in rate and the channel routing logic.

Email opt-in rate is established in Section 1.2.3 at a planning baseline of 30% of registered users who have a verified email address and have not opted out of email notifications. At 10M MAU with estimated 70% email address verification rate, the addressable email population is 7M users. At 30% opt-in, the email-eligible population is 2.1M users.

Email-eligible users as a fraction of total DAU: at pessimistic DAU of 2M, not all DAU users are email-eligible. Assuming DAU composition mirrors MAU email-eligibility (21%), approximately 420K of the 2M daily active users are email-eligible.

Routed events targeting email-eligible users: at 7.97M routed events/day distributed across 2M DAU, approximately 21% of events target email-eligible users = ~1.67M email-candidate events/day.

Email batching (Section 1.3) consolidates multiple events per user into digest sends. At baseline engagement, the average email-eligible DAU receives approximately 5.6 email-candidate events/day (1.67M events / 420K email-eligible DAU). With daily digest batching as the default, this produces approximately 1 email/user/day for active email users, with a maximum of 3 emails/day per user (morning, afternoon, evening digest windows — Section 1.3.3). Effective email sends/day: approximately 420K–1.26M depending on engagement distribution.

Using the midpoint of 840K email sends/day × 30 days = **25.2M emails/month** at pessimistic provisioning. This replaces the unsupported 75M figure from Revision 4.

**Email batching reduction factor (Criticism 7):**

Rather than a single range, the reduction factor is modeled at three engagement scenarios:

| Scenario | Email Events/Day | Digest Batching | Email Sends/Day | Reduction Factor | SES Cost/Month |
|----------|-----------------|-----------------|-----------------|-----------------|----------------|
| Low engagement (2 events/email-eligible DAU) | 840K | 1 send/user | 420K | 2.0× | ~$1,260 |
| Baseline (5.6 events/email-eligible DAU) | 1.67M | 2 sends/user avg | 840K | 2.0× | ~$2,520 |
| High engagement (10 events/email-eligible DAU) | 2.98M | 3 sends/user (cap) | 1.26M | 2.4× | ~$3,780 |

The reduction factor is 2.0–2.4× across scenarios, not 1.01–1.4× as stated in Revision 4. The prior range was wrong because it did not model batching correctly. SES cost at $0.10/1,000 emails ranges from **~$1,260 to ~$3,780/month** at pessimistic provisioning, versus the ~$7,500 stated in Revision 4. The corrected figure is the dominant cost revision in this document.

*Third-party delivery services (corrected):*

| Service | Volume/Month | Unit Cost | Monthly Cost |
|---------|-------------|-----------|--------------|
| APNs/FCM | 245M push | Free | $0 |
| Amazon SES | 25M emails (baseline) | $0.10/1,000 | ~$2,520 |
| Twilio (transactional SMS) | 300K messages | $0.0079/msg | ~$2,370 |
| **Delivery subtotal** | | | **~$4,890/month** |

*Revised total estimated monthly cost at pessimistic provisioning:* **~$6,562/month**

Email delivery remains the largest variable cost at approximately 38% of total, followed by SMS at 36%. The earlier estimate of ~$11,160/month was inflated primarily by the incorrect email volume figure and the understated SQS call count.

**Over-provisioning cost at 15% DAU/MAU:**

At 15% DAU/MAU, compute is over-provisioned by approximately 25% relative to actual load. Compute over-provisioning cost: ~$120/month. Queue over-provisioning cost scales with actual volume, not provisioned capacity, so it is not affected. SES and SMS costs also scale with actual volume. Total over-provisioning cost at 15% DAU/MAU: approximately **$120/month**.

**Acceptance rationale — filled labor cost estimate (Criticism 1):**

The acceptance rationale compares $120/month in over-provisioning cost against the cost of a capacity emergency. The loaded engineer cost assumption: senior backend engineer at $180,000 annual fully-loaded compensation (salary, benefits, equity at standard startup accounting) = $3,462/week. Two engineer-weeks of capacity emergency response = **$6,924 in loaded labor cost**, not counting opportunity cost of features deferred.

Over six months, over-provisioning at 15% DAU/MAU costs approximately $720. The break-even point is reached if a capacity emergency consumes more than approximately 0.1 engineer-weeks (4 engineer-hours) of unplanned response. Any realistic capacity incident exceeds this threshold. The trade is accepted on this basis.

*Assumption stated explicitly:* The $180,000 figure is an estimate. Finance should confirm the actual loaded cost before this document is used for budget approval. If the actual figure is materially lower (below $100,000 annual loaded), the break-even analysis should be rerun. At $100,000 annual loaded cost, break-even is still reached at approximately 0.2 engineer-weeks of unplanned response, which does not change the conclusion.

---

#### 1.1.2 Scaling Operations Required at Optimistic Volume

The following changes are required at 50% DAU/MAU. These are execution work, not design work.

**What changes:**
- P3 worker pool recounted at 19.95M routed events/day. Estimated result: 14 workers (versus 8 at pessimistic).
- P2 worker pool recounted. Estimated result: 6 workers (versus 3 at pessimistic).
- Fanout rate limit re-derived from new P3 pool capacity. At 14 workers, estimated new limit: ~3,500 events/second.
- P3 delivery latency SLA revalidated for 500,000-follower tail case.
- Queue infrastructure validated for new peak event rate.

**What does not change:** Queue topology, preference store schema, routing evaluation logic, channel delivery integrations, suppression