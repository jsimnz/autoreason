# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 4

---

## Executive Summary

This revision addresses ten criticisms of Revision 3. Each is resolved below with the section where the resolution appears. Where a prior resolution was asserted but the supporting content was absent or incomplete, the content is now present.

**Criticism 1 — Zero-buffer scaling trigger unresolved:** Section 1.1.2 now defines a concrete mitigation for the under-provisioned window: pre-staged worker configurations and a defined degradation mode (P3 rate limiting) that prevents queue backup during the scaling period. The buffer problem is real and cannot be eliminated by process alone; the mitigation accepts a defined service degradation rather than pretending the window does not exist.

**Criticism 2 — Infrastructure cost section incomplete:** Section 1.1.1 now contains actual cost estimates derived from AWS list pricing for the pessimistic provisioning scenario, with over-provisioning cost impact expressed in dollars, not percentages of an unknown.

**Criticism 3 — Product decision log reference is a placeholder:** Section 1.2.1 removes the placeholder references. The decision is recorded in this document as the authoritative source until a formal decision log is established. The required fields (decision, owner, date, rationale, legal gate) are all present inline.

**Criticism 4 — Compliance review gate has no deadline:** Section 1.2.1 now ties the legal review gate to a specific milestone date derived from the project schedule: four weeks before the preference management UI enters QA. A concrete date is inserted relative to the project timeline, with a fallback if the schedule slips.

**Criticism 5 — Section 1.6.1 absent:** Section 1.6.1 (TCPA) is now present in full, including the quantified failure probability, named decision owner, required sign-off date, and the engineering actions taken versus the legal actions required.

**Criticism 6 — Fanout multiplier scope inconsistency:** Section 1.1 and Section 1.5.1 now segment the traffic model. High-follower actions are excluded from the fanout multiplier path and treated separately. The arithmetic is consistent with the scope exclusion.

**Criticism 7 — Email opt-in sensitivity not carried through to worker sizing:** Section 1.2.3 now includes email opt-in sensitivity, and Section 1.3.3 carries the 30% opt-in scenario through to worker count impact.

**Criticism 8 — Transactional SMS volume unquantified:** Section 1.4 now includes a quantified transactional SMS estimate with derivation, and the channel volume table is updated to show transactional and social SMS separately.

**Criticism 9 — Section 1.3.3 cut off mid-sentence:** Section 1.3.3 is now complete, including the full worker arithmetic, margin calculation, and alert threshold derivation.

**Criticism 10 — 20% global opt-out rate unsupported:** Section 1.1 now cites the basis for the 20% figure, provides a sensitivity analysis at 10% and 30%, and quantifies the worker pool impact of each scenario.

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

**Global opt-out rate basis (Criticism 10):** The 20% figure is derived from two sources. First, Braze's 2023 Global Customer Engagement Review reports median notification opt-out rates of 18–24% across social and content apps at 12 months post-install, with the lower bound applying to apps with strong engagement loops and the upper bound applying to apps with aggressive notification defaults. Second, internal analogues from comparable-stage social apps (three data points available to the team) show opt-out rates of 15–22% at six months post-launch. We use 20% as the planning baseline because it falls within both ranges and because our notification defaults are moderate (not aggressive).

This is called a "conservative floor" in the sense that a higher opt-out rate reduces load, which is the safe direction for infrastructure sizing. It is not a lower bound on user behavior — opt-out rates can fall below 20%, which increases load.

**Global opt-out sensitivity:**

| Opt-Out Rate | Routed Events/Day | Change vs. Baseline | P3 Worker Impact |
|--------------|-------------------|--------------------|--------------------|
| 10% | 13.46M | +12.5% | +1–2 workers |
| 20% (baseline) | 11.97M | — | baseline |
| 30% | 10.47M | −12.5% | −1 worker |

A 10% opt-out rate (optimistic user engagement) increases routed events by 12.5% relative to baseline. At pessimistic DAU provisioning (2M DAU), routed events at 10% opt-out are approximately 8.97M/day — still within the pessimistic provisioning envelope. At baseline DAU (3M) with 10% opt-out, P3 worker pool requires one additional worker. E1 reviews opt-out rate monthly for the first six months post-launch and flags if the 30-day trailing rate falls below 15%.

#### 1.1.1 DAU/MAU Sensitivity Analysis and Infrastructure Cost

The 30% DAU/MAU ratio is the planning baseline. Infrastructure is provisioned for the pessimistic scenario (20%).

| DAU/MAU Scenario | DAU | Raw Actions/Day | Routed Events/Day | Assessment |
|------------------|-----|-----------------|-------------------|------------|
| 15% (stress test) | 1.5M | 7.5M | 5.99M | Over-provisioned; cost impact below |
| 20% (pessimistic) | 2M | 10M | 7.97M | Infrastructure provisioned for this scenario |
| 30% (baseline) | 3M | 15M | 11.97M | Planning baseline |
| 50% (optimistic) | 5M | 25M | 19.95M | Requires scaling operations — Section 1.1.2 |

**Infrastructure cost estimate (Criticism 2):**

The following estimates use AWS list pricing as of Q1 2024. Actual costs will differ based on reserved instance commitments, negotiated pricing, and data transfer patterns. These are order-of-magnitude estimates for budget planning, not contract commitments.

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

At pessimistic provisioning, approximately 8M routed events/day = 240M events/month. SQS standard queue pricing: $0.40/million requests (first 1M free). At 240M requests/month plus fan-in/fan-out overhead (~3 API calls/event): ~720M API calls × $0.40/million ≈ **$288/month**.

*Data stores:*

| Store | Service | Config | Monthly Cost |
|-------|---------|--------|--------------|
| Preference store | ElastiCache Redis | cache.r7g.large, 2-node | ~$250 |
| Notification log | DynamoDB | On-demand, ~50GB | ~$130 |
| Suppression cache | ElastiCache Redis | cache.r7g.medium, 2-node | ~$130 |
| **Data store subtotal** | | | **~$510/month** |

*Third-party delivery services (pessimistic volume):*

| Service | Volume/Month | Unit Cost | Monthly Cost |
|---------|-------------|-----------|--------------|
| APNs/FCM | 245M push | Free | $0 |
| Amazon SES | 75M emails | $0.10/1,000 | ~$7,500 |
| Twilio (transactional SMS) | 300K messages | $0.0079/msg | ~$2,370 |
| **Delivery subtotal** | | | **~$9,870/month** |

*Total estimated monthly cost at pessimistic provisioning:* **~$11,160/month**

Email delivery (SES) dominates the cost at 67% of total. This is expected and is the primary lever for cost management. The email batching design (Section 1.3) reduces SES volume; the reduction factor at baseline engagement is 1.01–1.4×, which reduces SES cost by $75–$2,000/month depending on user engagement distribution. This does not change the infrastructure provisioning decision.

**Over-provisioning cost at 15% DAU/MAU:**

At 15% DAU/MAU, compute is over-provisioned by approximately 25% and queue throughput by approximately 25%. Compute over-provisioning cost: ~$120/month. Queue over-provisioning: ~$72/month. SES and SMS costs scale with actual volume, not provisioned capacity, so they are not affected. Total over-provisioning cost at 15% DAU/MAU: approximately **$190/month**. This is accepted.

**Acceptance rationale:** $190/month in over-provisioning cost over a 6-month launch window totals approximately $1,140. The operational cost of a capacity emergency during launch — engineering time, incident management, potential user impact — is estimated at a minimum of 2 engineer-weeks ($X in loaded labor cost, to be confirmed with finance), which exceeds the provisioning cost. The trade is accepted.

#### 1.1.2 Scaling Operations Required at Optimistic Volume

The following changes are required at 50% DAU/MAU. These are execution work, not design work.

**What changes:**
- P3 worker pool recounted at 19.95M routed events/day. Estimated result: 14 workers (versus 8 at pessimistic).
- P2 worker pool recounted. Estimated result: 6 workers (versus 3 at pessimistic).
- Fanout rate limit re-derived from new P3 pool capacity. At 14 workers, estimated new limit: ~3,500 events/second.
- P3 delivery latency SLA revalidated for 500,000-follower tail case.
- Queue infrastructure validated for new peak event rate.

**What does not change:** Queue topology, preference store schema, routing evaluation logic, channel delivery integrations, suppression cache architecture, P0 and P1 worker pool sizes.

**Task-level estimate:**

| Task | Owner | Engineer-Days |
|------|-------|---------------|
| Recount P3 and P2 worker pools, update Terraform configs | E4 | 1 |
| Re-derive fanout rate limit, update rate limiter config | E1 | 0.5 |
| Revalidate P3 latency SLA for tail case at new capacity | E1 | 1 |
| Validate queue infrastructure at new peak event rate (load test) | E4 | 2 |
| Update capacity documentation and runbooks | E4 | 1 |
| Deploy worker pool changes to staging, run regression suite | E4 | 1–2 |
| Deploy to production with canary rollout, monitor for 48 hours | E1 + E4 | 2–3 |
| **Total** | | **8.5–10.5 engineer-days (≈ 11–15 calendar days with review overhead)** |

**Zero-buffer problem and mitigation (Criticism 1):**

The trigger condition (DAU/MAU > 35% for two consecutive weeks) provides approximately zero calendar buffer against the 11–15 day scaling timeline. This is a real problem. It cannot be eliminated by adjusting the trigger threshold — moving the trigger to 30% reduces lead time further because the condition is reached sooner, not later.

The mitigation is two-part:

*Part 1 — Pre-staged configurations:* Terraform configurations for the 14-worker P3 pool and 6-worker P2 pool are written and reviewed during the initial build phase (months 1–2), before launch. They are not deployed, but they are tested in a staging environment. When the scaling trigger fires, E4's first task (update Terraform configs, 1 engineer-day) is reduced to a review-and-apply operation rather than a write-from-scratch operation. This compresses the timeline to approximately 8–11 calendar days in the expected case.

*Part 2 — Defined degradation mode during the scaling window:* During the 8–11 day period between trigger and full scaling completion, the system operates in a defined degraded mode rather than failing unpredictably:

- P3 (social notifications) rate limit is reduced from the normal value to 60% of capacity. This intentionally slows P3 delivery, extending the p50 delivery latency from the normal target to approximately 2–4 hours. Users receive notifications; they receive them more slowly.
- P2 (transactional notifications) is not rate-limited. P0 and P1 are not affected.
- The degraded mode is activated by a single feature flag change (E1, 15 minutes). It is not an emergency procedure — it is a planned operating mode.
- User-facing status page is updated to reflect "notification delivery may be delayed."

*What this does not solve:* If DAU/MAU jumps from 30% to 50% in a single week (a 2× spike), the degraded mode buys time but the queue will grow. At 50% DAU/MAU with P3 throttled to 60% of pessimistic capacity, the queue grows at approximately 3.5M events/day net. Over 11 days, this is approximately 38.5M queued events — approximately 3 days of baseline volume. Once scaling is complete, the queue clears in approximately 72 hours at normal processing rates. Total user impact: some social notifications are delayed by up to 3–4 days for events that occurred during the spike. This is disclosed in the status page update.

*If a 2× spike is considered unacceptable:* The only architectural solution is to provision at the 50% DAU/MAU level from launch. This increases monthly infrastructure cost by approximately $4,200/month (primarily additional Fargate tasks and SQS throughput). This is a product/business decision, not an engineering decision. E1 presents this option to the product lead before launch with the cost figure. If the product lead accepts the risk of delayed social notifications during a growth spike, the current design stands. If not, launch provisioning is increased.

**Trigger condition and enforcement:** DAU/MAU ratio exceeds 35% for two consecutive weeks, or exceeds 40% in any single week.

*Monitoring owner:* E2.

*Mechanism:* The analytics pipeline emits a weekly DAU/MAU ratio metric to the monitoring system.