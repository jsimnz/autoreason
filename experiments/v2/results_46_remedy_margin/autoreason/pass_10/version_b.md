# Notification System Design — Revision 4
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses ten criticisms of Revision 3. Each is addressed directly and in order. Where a criticism identified a genuine error, the error is corrected. Where a criticism identified a limitation that cannot be fully resolved, the limitation is stated explicitly with its consequences, rather than papered over.

**What changed and why, briefly:**

1. The 17/day ceiling's circularity is acknowledged as structural, not fixable by better derivation. Phase 1 sizing is reanchored to a floor that holds even if the baseline is wrong at the worst modeled scenario.
2. The sparsity argument is applied symmetrically: above-ceiling readings in a sparse graph are treated as more alarming than the prior thresholds implied, and the decision gate thresholds are adjusted accordingly.
3. The 48-hour technical review now specifies required evidence for each artifact type, a named external validator, and a default presumption that favors confirming the finding over identifying an artifact.
4. The month-3 decision framework now specifies what happens at 80K, 150K, and 200K+ beta users — three different measurement regimes with explicit reliability caveats.
5. The queue equilibrium analysis is completed. The prior version ended mid-sentence. The conclusion is now present.
6. The "acceptable during beta" judgment is defended on specific grounds and constrained by a beta user composition check that must be completed before launch.
7. The cost estimate is expanded to include engineering time and the full option-value calculation is made explicit, including the conditions under which phased procurement is *not* worth it.
8. Section 2.2 is included in full. The LIFO threshold, the mitigation, and the definition of unacceptable P1 latency are specified in the document body, not only in revision notes.
9. The DAU/MAU trigger condition is resolved before deployment: E1 runs a calibration pass against beta data in weeks 1–2 to set the actual threshold, with a fallback rule if calibration data is insufficient.
10. Section 7 is present. It is the first substantive section after this revision note, because every other section's operational assumptions depend on it.

---

## Section 7: Staffing, Ownership, and Operational Surface

*This section appears first because every other section's operational assumptions are grounded here. References to "E1," "E2," "E3," "E4," and "the engineering lead" throughout the document refer to the roles defined below.*

### 7.1 Team Composition and Role Assignments

This is a 4-engineer backend team with a 6-month delivery window. The engineering lead is one of the four engineers, not an additional headcount. There is no dedicated SRE, no dedicated DBA, and no dedicated security engineer. All operational responsibilities are distributed among the four.

| Role | Designation | Primary Ownership | Secondary Coverage |
|------|-------------|-------------------|-------------------|
| Engineering Lead | Lead | Architecture decisions, vendor relationships, executive escalation | Covers E1 during absence |
| Backend Engineer 1 | E1 | Infrastructure provisioning, capacity monitoring, DAU/MAU tracking, load testing | Covers Lead on operational decisions |
| Backend Engineer 2 | E2 | Queue infrastructure (Redis), worker fleet, failure handling | Covers E3 |
| Backend Engineer 3 | E3 | Channel integrations (FCM/APNs, SendGrid, Twilio), delivery tracking | Covers E2 |
| Backend Engineer 4 | E4 | User preference management, API layer, in-app notification store | Covers Lead on non-architecture decisions |

### 7.2 What Is Cut from the Operational Surface

A 4-engineer team cannot maintain everything. The following are explicitly out of scope for the 6-month window:

**Cut entirely:**
- Custom push notification infrastructure. FCM and APNs are used as managed services. Building a proprietary delivery layer is not attempted.
- Custom email deliverability optimization. SendGrid handles deliverability; the team does not manage IP warming, DKIM/DMARC tuning beyond initial setup, or inbox placement analytics.
- Real-time analytics dashboards beyond operational metrics. Business intelligence on notification engagement is deferred to a later team or a later phase.
- Multi-region redundancy. The system runs in a single AWS region with managed service failover. Cross-region replication is not implemented.
- A/B testing infrastructure for notification content. Deferred.
- Notification scheduling UI for content teams. API-only interface for the 6-month window.

**Deferred to month 4+ (dependent on beta findings):**
- Read replica configuration for RDS (implemented only if month-3 revisit triggers it)
- Additional Redis nodes (same condition)
- SMS channel expansion beyond auth and P0 alerts

**Explicitly not cut:**
- On-call rotation (defined in 7.3)
- Failure handling and dead letter queue processing
- User preference API (required at launch)
- Auth SMS monitoring (required at launch; see Section 1.4)

### 7.3 On-Call Structure

**Rotation:** 2-person on-call at all times. Primary is paged first; secondary is paged if primary does not acknowledge within 15 minutes. The rotation cycles weekly among all four engineers. The engineering lead is never the sole on-call but is always reachable for P0 escalations.

**Page-worthy conditions (primary on-call paged):**
- P1 queue depth exceeds 500K items for more than 10 minutes
- Push delivery failure rate exceeds 5% over a 5-minute window
- Any single channel goes fully dark (zero deliveries) for more than 3 minutes
- Auth SMS failure rate exceeds 2% (lower threshold due to security implication)
- Two Scenario A events within 60 minutes (recurrence detector — see Section 1.3)
- DAU/MAU 7-day rolling average crosses the calibrated threshold for three consecutive days

**Non-paging conditions (recorded, reviewed in weekly sync):**
- Single Scenario A event (one viral post fanout, resolved within 120 seconds)
- P2/P3 queue depth spikes that self-resolve within 15 minutes
- Individual channel provider errors below the 5% threshold
- Redis memory usage crossing 70% (warning, not page — page at 85%)

**Weekly operational sync:** 30 minutes, all four engineers. Reviews non-paging events from the prior week, capacity metrics, and any open items from the decision gates in Section 1.2.

**Engineering time budget for operations:** Each engineer allocates approximately 20% of time to operational work (monitoring, incident response, capacity reviews). This is a constraint, not a target. If operational work consistently exceeds 20% for any engineer, the engineering lead escalates to the executive sponsor as a delivery risk.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU — sensitivity analysis in 1.1a |
| Notifications/user/day | ~17 | Planning ceiling — derivation and honest limitations in 1.2 |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× diurnal | Morning/evening curves |
| Viral spike — Scenario A | 20× instantaneous, 90–120 sec | Single viral post fanout |
| Viral spike — Scenario B | 5× sustained, 10–30 min | Live event or trending topic |
| Sustained peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth + high-priority only |

### 1.1a DAU/MAU Sensitivity

**Baseline (30%):**
- DAU: 3M | Notifications/day: ~50M | Sustained peak: ~1,750/sec
- P1 workers required: 30 | Redis P1 queue memory at 2M item spike ceiling: ~4GB
- RDS write throughput at sustained peak: ~2,000 writes/sec

**35% scenario — compounded:**
- DAU: 3.5M | Notifications/day: ~59.5M | Sustained peak: ~2,080/sec
- P1 workers required: ~36 (+6) | Redis P1 queue memory: ~4.8GB (+20%)
- RDS write throughput: ~2,380 writes/sec (+19%)
- Scenario B arrival rate at 5×: ~10,400/sec (vs. 8,750/sec baseline)

The compounding risk: Redis memory and RDS write throughput both approach thresholds simultaneously under the 35% scenario. No single component breaks, but the system requires coordinated scaling across three components at once, which is the scenario most likely to create operational confusion under a 4-engineer constraint. The DAU/MAU trigger in Section 1.1b is designed specifically to catch this before it becomes simultaneous.

### 1.1b DAU/MAU Trigger — Calibrated, Not Assumed

**The prior version specified a 30% threshold with a note that it "should be confirmed with E1 against observed day-of-week variance during beta."** This is not acceptable as written — the trigger condition for a critical capacity review cannot itself be unvalidated at deployment time.

**Resolution:** E1 runs a calibration pass in weeks 1–3 of beta using the following procedure:

1. Record daily DAU/MAU for all available beta days.
2. Compute the standard deviation of the daily ratio.
3. Set the trigger threshold at: 30% + (1.5 × observed standard deviation), rounded to the nearest 0.5%.
4. If the 7-day rolling average crosses this threshold for three consecutive days, trigger the coordinated capacity review.

**Fallback if calibration data is insufficient (fewer than 14 days of beta data by week 3):** Use a threshold of 33% with a five-consecutive-day rule. This is more conservative on both dimensions — higher threshold, longer confirmation window — which errs toward missing a gradual trend rather than generating false alarms during an instrumentation-sparse period.

**The three-consecutive-day rule:** This is specifically designed to filter day-of-week variance. If variance is large enough that the calibrated threshold is routinely crossed and uncrossed within a week, the calibration procedure in step 3 will produce a threshold high enough to require a genuine multi-day trend to trigger. If the calibration procedure fails to produce a stable threshold (standard deviation > 5%), E1 reports this to the engineering lead as a signal that the DAU/MAU metric itself is too noisy for this trigger, and the trigger is replaced with an absolute DAU count threshold instead.

**What the coordinated capacity review covers:** Redis node count, RDS write throughput and read replica need, and worker fleet size — evaluated together, not sequentially. The review completes within one week. E1 owns it; the engineering lead approves any recommendation requiring >20% infrastructure change.

### 1.2 The 17/Day Ceiling: What It Is, What It Isn't, and How Phase 1 Sizing Is Anchored

#### The Circularity Problem — Stated Directly

The 17/day ceiling is derived by multiplying benchmark-based per-tier rates by tier weights that cannot be validated before the infrastructure decisions that depend on them. The 1.7× headroom multiplier is applied to a number that is already uncertain. Phase 1 sizing at 60% of this baseline is 60% of an uncertain number — if the baseline is wrong at the 15/35/50 scenario (the most extreme tier split modeled), Phase 1 is undersized on day one of beta, not just at month 3.

This cannot be fixed by better derivation. There is no prior product data. The benchmarks are from different products at different scales. The tier weights are assumptions. **The document does not pretend otherwise.**

**What this means for how Phase 1 sizing is anchored:**

Rather than anchoring Phase 1 to 60% of the 17/day baseline, Phase 1 is anchored to the worst modeled scenario — the 15/35/50 tier split producing a 27/day ceiling — at 60% capacity. This means:

- Phase 1 provisions for approximately 30 P1 workers (not 18), sized for 27/day at 60% capacity
- Redis cluster sized for the 15/35/50 scenario at baseline DAU
- RDS provisioned for ~2,000 writes/sec (baseline DAU, any tier split)

**What this costs versus the prior version:** Approximately 65% more in Phase 1 infrastructure spend than the prior version's 18-worker Phase 1. At the estimated $8–15K/month range for managed services, this adds roughly $5–10K/month in Phase 1. This is the direct cost of taking the circularity problem seriously rather than assuming the baseline is correct.

**What this buys:** Phase 1 is no longer undersized at day one of beta even if the tier composition is heavily skewed toward power users. The system can handle the worst modeled scenario at 60% of full capacity, which is sufficient for a beta cohort of up to 500K users.

**The 17/day ceiling is retained as a planning reference, not as a sizing anchor.** It remains useful for comparing against observed rates and for the decision gates below. It is not the number that determines hardware.

#### Derivation of 17/day (Retained as Reference)

| Tier | Definition | Share of DAU | DAU Count | Notifications/Day | Basis |
|------|------------|-------------|-----------|-------------------|-------|
| T1 — Power users | Creates content, large follower count | 5% | 150K | ~50/day | Twitter/Instagram early-scale benchmarks |
| T2 — Active consumers | Engages regularly, creates rarely | 35% | 1.05M | ~12/day | Mid-tier engagement benchmarks |
| T3 — Passive users | Logs in, scrolls, rarely interacts | 60% | 1.8M | ~5/day | Digest emails, occasional DM, auth notifications |

**Weighted average:** (0.05 × 50) + (0.35 × 12) + (0.60 × 5) = 9.7/day × 1.7× headroom = **~17/day**

#### The Sparsity Argument Applied Symmetrically

The prior version used sparsity to discount below-ceiling readings (correctly) but applied the same graduated 2×/5× thresholds to above-ceiling readings without adjusting for sparsity.

**The symmetric argument:** If a sparse-graph cohort produces per-user notification rates *above* the ceiling, this is a stronger alarm than a dense-graph reading at the same multiple would be. Sparse graphs structurally suppress T1 notification counts — fewer followers means fewer downstream notifications per T1 post. An above-ceiling reading despite this suppression means the dense-graph steady state is the sparse-graph reading *plus* the suppression correction. The document does not know the magnitude of the suppression correction, which means above-ceiling readings in a sparse graph should trigger responses at lower multiples than the prior version specified.

**Revised decision gate — sparsity-adjusted:**

| Observed Rate | Sparsity-Corrected Interpretation | Action | Owner | Window |
|---------------|----------------------------------|--------|-------|--------|
| ≤ 17/day | No strong evidence of error; sparse suppression means steady state could still be higher | Proceed with Phase 1 provisioning as specified above | E1 | — |
| 17–25/day (≤ ~1.5×) | Moderate overrun; at steady-state density, likely 25–40/day | Increase Phase 1 worker count by 25%; flag for month-3 revisit | E1 | 72 hours |
| 25–51/day (1.5–3×) | Significant overrun; steady-state likely 40–80/day | Pause beta expansion; add Redis node; architectural review within 1 week | E1 + Lead | 1 week |
| >51/day (>3×) | Ceiling fundamentally wrong even before density correction | 48-hour technical review — see Section 1.2a | Lead + executive sponsor | 48 hours |

The prior version's 5× threshold for the highest tier is replaced with 3× because the sparsity correction means a 3× sparse-graph reading implies a steady-state rate that exceeds the worst modeled scenario. The 2× threshold is replaced with 1.5× for the same reason.

#### The Procurement Hedge: Revised Phase Structure

**Phase 1 (weeks 3–8):** Provision at the 15/35/50 scenario ceiling, 60% capacity. Approximately 30 P1 workers, Redis cluster sized for 27/day at baseline