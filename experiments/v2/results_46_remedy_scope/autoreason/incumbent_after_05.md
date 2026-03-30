# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling ~45M notifications/day across push, email, in-app, and SMS channels. The core architectural decisions:

1. **Traffic assumptions are explicit and sensitivity-tested.** The 45M/day planning figure compounds two uncertain inputs (DAU/MAU ratio, notifications per user). Both are range-tested; the infrastructure tier is validated at the 15M low bound and 100M high bound.
2. **Four isolated priority queues (P0–P3)** with TTL semantics enforced via companion expiry sorted sets and a background pruning process — Redis Lists have no per-element TTL, and without active pruning, expiry sets grow without bound under worker outage.
3. **Full payload storage in queue entries** — storing only IDs creates a crash window between dequeue and payload fetch that causes silent, unrecoverable message loss. Redis memory is explicitly sized to justify this choice.
4. **Deduplication uses atomic SET NX**, not check-before-set — the race condition is solved, not just described.
5. **Worker pools are per-channel and per-priority**, reconciled in a single source-of-truth matrix with every zero cell explicitly justified.
6. **APNs capacity planning is range-based until month 2 validation** — using an unvalidated throughput figure as if reliable is not acceptable. Workers are sized to a conservative floor with an explicit re-planning gate.
7. **SMS has two independent budgets with enforced controls**, not just separate accounting. A tiered circuit breaker with automatic email OTP fallback is specified.
8. **Email OTP fallback routes to a dedicated P0 sub-queue**, not the standard P1 email queue. The priority hole is closed.
9. **Managed infrastructure throughout** — a team of 4 does not operate its own Redis cluster or PostgreSQL primary.
10. **P0 has minimum 2 workers per channel** — no single point of failure on the security-critical path.
11. **WebSocket sequence numbers are designed, not deferred** — reconnect catch-up logic is specified in Section 5.
12. **P3 has no push path by design** — sending push notifications for weekly digests drives opt-out rates. This is a product decision encoded in the architecture.

Every tradeoff is named explicitly, including the uncomfortable ones.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model — Assumptions, Not Validated Figures

Both inputs to the daily volume estimate are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:** The 30% figure is reasonable for mature social apps (Facebook historically ~65%, Twitter ~40%, newer apps often 15–25%). The correct planning range for an unspecified social app is **15–50%**. We use 30% as the planning figure.

**Notifications per active user per day:** 17/day is an industry average that includes high-engagement outliers. A more defensible figure for a mid-engagement social app is 15/day.

**Sensitivity table:**

| DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr window) |
|---------|-----|----------------|-----------|----------------------|
| 15% (low) | 1.5M | 10 | 15M | ~525/sec |
| **30% (plan)** | **3M** | **15** | **45M** | **~1,575/sec** |
| 50% (high) | 5M | 20 | 100M | ~3,500/sec |

**Planning decision:** Size for 45M/day (~1,575/sec peak). Validate actual rate within the first 30 days of production traffic. If the measured figure diverges from the 15M–100M range by more than 2×, re-plan before month 3.

**Channel split:**

| Channel | Share | Daily volume (45M plan) |
|---------|-------|------------------------|
| Push (FCM + APNs) | 70% | 31.5M/day |
| In-app | 20% | 9M/day |
| Email | 8% | 3.6M/day |
| SMS | 2% | 0.9M/day (capacity ceiling, not operating target) |

### 1.2 Active-User Correction — Applied Consistently

Logged-in users during peak: 3M DAU × 20% concurrently active = ~600K users online at peak. This correction applies differently by channel:

**Push:** Push serves offline or background users. The concurrent-user correction does not apply here — the 70% channel allocation already represents the full DAU-based volume. Applying a second population filter to the same volume figure understates demand.

- Push peak demand = 31.5M/day × 3 / 86,400 = **~1,094/sec**

**In-app:** In-app notifications are only delivered to users with an active WebSocket connection. The correction applies here because delivery is gated on connection state — a notification to an offline user does not consume in-app delivery resources; it falls back to push or queues for next login.

- In-app peak demand = 9M/day × 3 / 86,400 × (600K / 3M) = **~63/sec**

Push and in-app are not additive for the same user at the same moment. Treating them as additive overstates demand and leads to over-provisioning. The correction is applied to in-app (where connection state gates delivery) and not to push (where it does not).

### 1.3 Redis Memory Sizing — Required Before Infrastructure Selection

Full payload storage is the correct choice; the memory cost is the honest price of that correctness. We calculate it before selecting hardware.

**Why not store only IDs:** Reduces queue memory to ~840MB (8.4M entries × 100B). The cost is a crash window: if a worker dequeues an ID and the payload fetch fails (database unavailable, network partition), the notification is lost with no recovery path. At 45M/day, even a 0.01% loss rate is 4,500 lost notifications/day, including potentially OTP messages. Full payload storage eliminates this failure mode.

**Payload size distribution:**

| Notification type | Estimated payload size | % of volume |
|---|---|---|
| Push (title + body + metadata) | 500B–2KB | 70% |
| In-app (full content + action URLs) | 1–3KB | 20% |
| Email (template ID + parameters, not body) | 200–500B | 8% |
| SMS (message text + recipient) | 100–300B | 2% |

Conservative sizing: **2KB/entry** (accounts for JSON overhead, metadata, and high-end push payloads with media URLs).

**Queue memory at peak accumulation:**

At 1,575/sec input and combined worker capacity of ~26,000/sec, the system drains faster than it fills. Peak accumulation occurs during the 2-hour spike window before workers fully engage. Estimated excess: ~7.6M entries.

| Scenario | Queue entries | Memory |
|---|---|---|
| Conservative (2KB/entry) | 7.6M | **15.2GB** |
| Worst case (5KB/entry) | 7.6M | **38GB** |

**Full Redis memory breakdown:**

| Component | Calculation | Estimate |
|-----------|-------------|----------|
| Queue payloads (conservative) | 7.6M × 2KB | 15.2GB |
| Queue payloads (worst case) | 7.6M × 5KB | 38GB |
| Expiry sorted sets | 7.6M × 40B | ~305MB |
| Deduplication keys (5-min TTL)* | 174K × 50B | ~8.7MB |
| Preference cache | 500B × 3M active users | ~1.5GB |
| Aggregation state | 200B × 500K windows | ~100MB |
| Pub/Sub overhead | — | ~500MB |
| **Total (conservative)** | | **~17.6GB** |
| **Total (worst case)** | | **~40.4GB** |

*At 45M notifications/day and 5-minute TTL, simultaneously active deduplication keys = 45M × (5/1,440) ≈ 156K keys ≈ **7.8MB**. A figure of 1.5GB would require all daily keys to be simultaneously active, which contradicts the TTL. The correct figure is ~8.7MB — immaterial to hardware selection but the methodology matters for future sizing.

**ElastiCache selection:** r7g.4xlarge (128GB RAM, Multi-AZ) provides 3× headroom over worst case. This is a single-node logical view with Multi-AZ replication — not a cluster, which adds operational complexity a 4-person team should not absorb.

**Scaling triggers:**
- At 15M/day low bound: peak queue ~2.5M entries, ~5–13GB required. If production traffic validates this at month 2, downgrade to r7g.2xlarge (64GB), saving ~$400/month.
- At 100M/day high bound: peak queue ~17M entries, ~34–85GB required. Scale to r7g.8xlarge (256GB) before month 3 if the high bound materializes.

### 1.4 Worker Capacity Sizing

**Per-worker throughput:**

| Channel | Mechanism | Effective throughput |
|---------|-----------|---------------------|
| FCM (Android push) | 500-token batches, ~250ms RTT | ~2,000 tokens/sec/worker |
| APNs (iOS push) | HTTP/2 multiplexed streams | **300–1,000 req/sec/worker** (unvalidated range; see gate below) |
| Email | SendGrid async API | ~1,000 notifications/sec/worker |
| SMS | Twilio synchronous | ~67/sec/worker |
| In-app | PostgreSQL batch insert, 100 rows/batch | ~1,000 rows/sec/worker |

**APNs throughput — range-based planning with a re-planning gate:**

Apple does not publish per-bundle-ID rate limits. Production reports range from 300 to 2,000 req/sec depending on account age, app category, and Apple's opaque throttling policy. Using a single unvalidated figure as if reliable is not acceptable for a P0 delivery path.

- **Month 1–2:** Size for the conservative floor of 300 req/sec/worker.
- **Month 2 milestone:** E2 runs APNs load tests against the production bundle ID and measures actual throughput.
- **Re-planning gate:** Measured ≥ 600/sec → reduce workers. Measured < 300/sec → escalate; this is an architecture problem, not a tuning problem.

**Worker matrix — single source of truth:**

| | FCM | APNs | Email | SMS | In-app | Row total |
|--|-----|------|-------|-----|--------|-----------|
| **P0** | 2 | 2 | 1* | 2 | 1 | **8** |
| **P1** | 2 | 2 | 1 | 1 | 2 | **8** |
| **P2** | 0 | 0 | 1 | 0 | 1 | **2** |
| **P3** | 0 | 0 | 2 | 0 | 1 | **3** |
| **Col total** | **4** | **4** | **5** | **3** | **5** | **21** |

*P0 email workers serve the OTP fallback sub-queue only. See Section 1.5.

Any change to a single cell must update both the row total and the column total. The architecture diagram and capacity narrative derive from this table, not vice versa.

**Justification for every zero cell:**

- **P2/P3 FCM and APNs:** Bulk social notifications (likes, follows, digests) do not require dedicated push workers at elevated priority. P1 push workers drain P2/P3 queues via priority-aware consumers during off-peak. A separate P2/P3 push worker would be idle >95% of the time.
- **P2/P3 SMS:** SMS is reserved for security-critical messages (P0/P1 only). Social SMS is not permitted. P2/P3 SMS workers would have no work to do.
- **P0 in-app:** Security alerts (new device login, suspicious activity) displayed in-app warrant P0 priority. One P0 in-app worker is included.

**Why P3 has no push path:** P3 notifications are bulk digests and non-urgent social updates. Push delivery for P3 content is intentionally disabled. Sending a push notification for a weekly digest drives notification fatigue and opt-out rates — this is a product decision encoded in the architecture. If a user is not actively using the app, a P3 notification waits for their next session (in-app) or is delivered via email digest. P3 has two delivery paths: in-app for logged-in users, email for everyone else.

**Demand vs. capacity:**

| Channel | Peak demand | Workers | Peak capacity | Utilization at peak |
|---------|-------------|---------|---------------|---------------------|
| FCM | ~547/sec† | 4 | ~8,000/sec | ~7% |
| APNs | ~547/sec† | 4 | ~1,200–4,000/sec | ~14–46% |
| Email | ~125/sec | 5 | ~5,000/sec | ~2.5% |
| SMS | ~4/sec (capped) | 3 | ~200/sec | ~2% |
| In-app | ~63/sec | 5 | ~5,000/sec | ~1.3% |

†FCM and APNs each handle approximately 50% of total push volume (Android/iOS split).

**Honest assessment:** These utilization figures are low. Worker counts are driven by redundancy requirements (minimum 2 per channel on P0/P1 paths) and the APNs uncertainty floor — not raw throughput demand. At the 100M/day high bound, FCM utilization reaches ~35% and APNs reaches ~70–100%, at which point the month 2 APNs load test becomes the binding planning constraint.

**Queue drain analysis:**

Combined worker capacity across all channels: ~26,000/sec. Net drain rate post-peak: ~24,400/sec. The 7.6M excess accumulated during the 2-hour spike clears in approximately **5 minutes** after peak ends.

At 15M/day low bound: excess accumulates at ~230/sec. 2-hour excess: ~1.7M items. Clears in ~70 seconds post-peak. The system is not embarrassingly over-provisioned at lower volume.

Queue depth alerts: 500K items for P1–P3; **1,000 items for P0** — P0 queue accumulation is an incident, not a capacity event.

### 1.5 Email OTP Fallback Priority — Gap Closed

**The problem:** P0 excludes email workers because email has 5–30 minute delivery latency. The SMS circuit breaker routes OTP to email when SMS volume exceeds the threshold. Without explicit routing, the email OTP fallback routes through the standard P1 email queue — a priority hole on the security-critical path.

**The fix:** The email channel has two logically separate sub-queues:

- **P0-email-otp:** Dedicated queue for OTP fallback messages only. Served by the 1 P0 email worker in the matrix above. This worker does nothing except drain this queue and is not shared with P1 email traffic.
- **P1/P2/P3-email:** Standard email queue for digests, social notifications, and non-critical alerts. Served by the remaining 4 email workers.

**Why this works:** The latency objection to P0 email concerns *inbox delivery* after the API call, which is outside our control regardless of queue priority. The P0 designation ensures the SendGrid API call is made without queuing delay — the same latency path as the P0 SMS worker calling Twilio. The part we control (time from trigger to API call) is treated as P0. The part we do not control (inbox delivery time) is acknowledged as a limitation.

**OTP router logic:**

```python
if channel == SMS and daily_sms_counter > SMS_FALLBACK_THRESHOLD:
    if user.verified_email:
        enqueue(P0_EMAIL_OTP_QUEUE, payload)   # not P1 email
    else:
        enqueue(P0_SMS_QUEUE, payload)          # SMS regardless; log for budget review
else:
    enqueue(P0_SMS_QUEUE, payload)
```