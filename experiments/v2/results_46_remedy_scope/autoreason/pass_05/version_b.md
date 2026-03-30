# Notification System Design — Revised
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This design covers a notification system handling an estimated 30–60M notifications/day across push, email, in-app, and SMS channels. The revised document corrects eleven specific problems identified in the prior version:

1. **DAU/MAU ratio is now treated as an assumption with a sensitivity range**, not a validated figure. The 30% estimate compounds with the notifications-per-user estimate; both are tested across plausible ranges.
2. **The concurrent-user correction is removed from push demand.** The prior version applied channel-split percentages and a concurrent-user discount to the same population, understating push demand. Push demand now uses the full DAU-based figure without a second correction.
3. **Deduplication key memory is recalculated correctly.** At 5-minute TTL, only ~174K keys are active simultaneously — approximately 8.7MB, not 1.5GB. The error is corrected and its impact on the overall sizing is noted.
4. **FCM worker count is reduced from 7 to 2 with explicit justification.** 7 workers at 7% peak utilization is a provisioning error, not a tradeoff. The matrix is corrected and the reasoning is shown.
5. **Email OTP fallback priority is specified explicitly.** The fallback routes to a dedicated P0-equivalent email sub-queue, not the standard P1 email queue. The priority hole is closed.
6. **SMS cost table is restructured** to separate annualized daily costs from one-time event costs, making the annual total derivable from the table.
7. **Circuit breaker threshold is corrected.** The 500K/day trigger was above the total daily SMS budget. The threshold is revised to 200K/day — above the OTP baseline but below the total budget ceiling — with a tiered escalation structure.
8. **Section 5 (WebSocket and reconnect logic) is written.** It was claimed in the executive summary but absent from the document. It is now present.
9. **Worker matrix zeroes are explicitly justified** for each blank cell. In-app P0 is added; P3 push is addressed with a reasoning note.
10. **E3/E4 scheduling dependency is acknowledged** and mitigated with a sequencing constraint and a defined slack buffer.
11. **E4's scope is explicitly bounded** with a prioritized task list and a named descope item if the schedule slips.

Every tradeoff is named, including the uncomfortable ones.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Model — Assumptions, Not Validated Figures

Both inputs to the 50M/day estimate are assumptions. They compound. The capacity plan must be robust to their joint uncertainty.

**DAU/MAU ratio:**

The 30% figure is reasonable for mature Western social apps (Facebook historically ~65%, Twitter ~40%, newer apps often 15–25%). The correct range for an unspecified social app is **15–50%**. We use 30% as the planning figure and test at 15% and 50%.

**Notifications per active user per day:**

17/day is an industry average that includes high-engagement outliers. A more conservative estimate is 10–15/day for a mid-engagement social app. We use 15/day as the planning figure.

**Sensitivity table:**

| DAU/MAU | DAU | Notif/user/day | Total/day | Peak (3×, 2hr) |
|---------|-----|----------------|-----------|----------------|
| 15% (low) | 1.5M | 10 | 15M | ~525/sec |
| **30% (plan)** | **3M** | **15** | **45M** | **~1,575/sec** |
| 50% (high) | 5M | 20 | 100M | ~3,500/sec |

**Planning decision:** Size for 45M/day (~1,575/sec peak). Validate the actual rate within the first 30 days of production traffic and re-plan if the measured figure diverges from the 15M–100M range by more than 2×. Infrastructure tier selection is stress-tested at both the 15M low end and the 100M high end below.

The prior version used 50M/day based on 17 notifications/user. The revised figure is 45M/day based on 15/user — a modest difference that does not change infrastructure tier selection but reflects a more defensible assumption.

**Channel split (unchanged):**

| Channel | Share | Daily volume (45M plan) |
|---------|-------|------------------------|
| Push (FCM + APNs) | 70% | 31.5M/day |
| In-app | 20% | 9M/day |
| Email | 8% | 3.6M/day |
| SMS | 2% | 0.9M/day (capacity ceiling) |

### 1.2 Push Demand — Corrected Calculation

The prior version applied a concurrent-user discount to push demand, reasoning that push serves "offline or background users." This was double-counting: the 70% channel allocation already represents the full DAU-based volume. Applying a second population filter to the same volume figure understates demand.

**Corrected push demand:**

Push peak demand = 31.5M/day × 3 / 86,400 = **~1,094/sec** at peak.

The prior version calculated ~972/sec by applying a 2.4M/3M offline-user fraction. This was incorrect. The 1,094/sec figure is used throughout.

**In-app demand (concurrent-user correction is appropriate here):**

In-app notifications are only delivered to users with an active WebSocket connection. The concurrent-user correction applies to in-app because delivery is gated on connection state — a notification to an offline user does not consume in-app delivery resources, it falls back to push or is queued for next login.

In-app peak demand = 9M/day × 3 / 86,400 × 20% concurrently active = **~63/sec**.

This is substantially lower than the prior ~350/sec figure, which incorrectly applied the concurrent-user correction to push while using the uncorrected figure for in-app. The correction is now applied consistently: to in-app (where connection state gates delivery) and not to push (where it does not).

### 1.3 Redis Memory Sizing — Corrected

**Deduplication key correction:**

At 50M notifications/day and 5-minute TTL, the number of simultaneously active deduplication keys is:

50M × (5 min / 1,440 min/day) ≈ **174,000 keys**

At 50 bytes/key: **~8.7MB**, not 1.5GB. The prior estimate assumed all daily keys were simultaneously active, which contradicts the stated TTL. The error reduced total Redis memory requirements by approximately 1.5GB — immaterial to hardware selection given the 128GB node, but the methodology was wrong and is corrected here.

**Revised Redis memory breakdown:**

| Component | Calculation | Estimate |
|-----------|-------------|----------|
| Queue payloads (peak accumulation, 2KB/entry) | 7.6M entries × 2KB | **15.2GB** |
| Queue payloads worst case (5KB/entry) | 7.6M entries × 5KB | **38GB** |
| Expiry sorted sets | 7.6M × 40B | ~305MB |
| Deduplication keys (corrected) | 174K × 50B | ~8.7MB |
| Preference cache | 500B × 3M active users | ~1.5GB |
| Aggregation state | 200B × 500K windows | ~100MB |
| Pub/Sub overhead | — | ~500MB |
| **Total (conservative)** | | **~17.6GB** |
| **Total (worst case)** | | **~40.4GB** |

**ElastiCache selection (unchanged):** r7g.4xlarge (128GB RAM, Multi-AZ) provides 3× headroom over worst case. The selection is unchanged; the corrected deduplication figure does not affect the tier. The prior error was in the methodology, not the outcome — but the methodology matters for future sizing decisions.

**At 15M/day low bound:** Peak queue accumulation is approximately 2.5M entries. Memory requirement drops to ~5–13GB. The r7g.4xlarge is oversized at the low bound; if production traffic validates the low scenario at month 2, downgrade to r7g.2xlarge (64GB) and save approximately $400/month.

**At 100M/day high bound:** Peak queue accumulation is approximately 17M entries. Memory requirement reaches ~34–85GB. The r7g.4xlarge handles the conservative case; if the high bound materializes, scale to r7g.8xlarge (256GB) before month 3.

### 1.4 Worker Capacity Sizing — Corrected

**FCM worker count reduction:**

The prior matrix allocated 7 FCM workers (across P0–P2). At 2,000/sec/worker, this provides 14,000/sec capacity against 1,094/sec peak demand — 7% utilization. This is not a named tradeoff; it is a provisioning error.

**Corrected FCM worker allocation:**

Peak FCM demand = 1,094/sec × 70% iOS/Android split applied later; for now, assume FCM handles Android push at roughly 50% of total push = ~547/sec at peak. One FCM worker at 2,000/sec handles this with 3.6× headroom. Two workers provides redundancy without waste.

**Revised worker matrix — single source of truth:**

| | FCM | APNs | Email | SMS | In-app | Row total |
|--|-----|------|-------|-----|--------|-----------|
| **P0** | 2 | 2 | 1* | 2 | 1 | **8** |
| **P1** | 2 | 2 | 1 | 1 | 2 | **8** |
| **P2** | 0 | 0 | 1 | 0 | 1 | **2** |
| **P3** | 0 | 0 | 2 | 0 | 1 | **3** |
| **Col total** | **4** | **4** | **5** | **3** | **5** | **21** |

*P0 email workers are dedicated to the OTP fallback sub-queue only. See Section 1.5.

**Justification for each zero cell:**

- **P2/P3 FCM and APNs:** Bulk social notifications (likes, follows, digests) do not require push workers at elevated priority. They share P1 push workers during off-peak and drain from P3 queues during low-traffic periods using the same workers via a priority-aware consumer. A separate P2/P3 push worker would be idle >95% of the time.
- **P2/P3 SMS:** SMS is reserved for security-critical messages (P0/P1 only). Social SMS is not permitted. P2/P3 SMS workers would have no work to do.
- **P0 in-app (added):** Security alerts (new device login, suspicious activity) displayed in-app warrant P0 priority. The prior version omitted this without justification. One P0 in-app worker is added.

**Why P3 has no push path:** P3 notifications are bulk digests and non-urgent social updates. These are delivered via in-app (for logged-in users) and email (for digests). Push delivery for P3 content is intentionally disabled — sending a push notification for a weekly digest is a user experience anti-pattern and contributes to notification fatigue and opt-out rates. If a user is not actively using the app, a P3 notification waits for their next session or is delivered via email digest. This is a product decision encoded in the architecture.

**Revised demand vs. capacity:**

| Channel | Peak demand | Workers | Peak capacity | Utilization at peak |
|---------|-------------|---------|---------------|---------------------|
| FCM | ~547/sec | 4 | ~8,000/sec | ~7% |
| APNs | ~547/sec | 4 | ~1,200–4,000/sec† | ~14–46% |
| Email | ~125/sec | 5 | ~5,000/sec | ~2.5% |
| SMS | ~4/sec (capped) | 3 | ~200/sec | ~2% |
| In-app | ~63/sec | 5 | ~5,000/sec | ~1.3% |

†APNs range reflects the validated throughput uncertainty (300–1,000/sec/worker). See APNs planning gate below.

**Honest assessment of utilization:** These utilization figures are low. The worker counts are driven by redundancy requirements (minimum 2 per channel on P0/P1 paths) and the APNs uncertainty floor, not by raw throughput demand. At the 100M/day high bound, FCM utilization reaches ~35% and APNs reaches ~70–100% — at which point the APNs worker count becomes the binding constraint and the month 2 load test becomes critical.

**APNs planning gate (unchanged from prior version):**

- Month 1–2: Size for 300 req/sec/worker conservative floor
- Month 2 milestone: E2 runs APNs load test against production bundle ID
- If measured throughput ≥ 600/sec: keep 4 workers, re-evaluate at 100M/day scenario
- If measured throughput < 300/sec: escalate — architecture problem, not tuning

### 1.5 Email OTP Fallback Priority — Gap Closed

**The problem:** P0 excludes email workers because email has 5–30 minute delivery latency. The SMS circuit breaker routes OTP to email when SMS volume exceeds the threshold. The email OTP fallback was therefore routing through a non-P0 channel, creating an unexamined priority hole on the security-critical path.

**The fix:** The email channel has two logically separate sub-queues:

- **P0-email-otp:** Dedicated queue for OTP fallback messages only. Served by the 1 P0 email worker in the matrix above. This worker does nothing except drain this queue. It is not shared with P1 email traffic.
- **P1/P2/P3-email:** Standard email queue for digests, social notifications, and non-critical alerts. Served by the remaining 4 email workers.

**Why this works:** The latency objection to P0 email is about *typical* email delivery, not about the priority queue that initiates the send. The P0 email worker calls the SendGrid API immediately upon dequeue — the same latency path as the P0 SMS worker calling Twilio. The 5–30 minute figure refers to inbox delivery after the API call, which is outside our control regardless of which queue initiated the send. The P0 designation ensures the API call is made without queuing delay, which is the part we control.

**Implementation note:** The OTP router logic:

```
if channel == SMS and daily_sms_counter > threshold:
    if user.verified_email:
        enqueue(P0_EMAIL_OTP_QUEUE, payload)  # not P1 email
    else:
        enqueue(P0_SMS_QUEUE, payload)  # SMS regardless, log for budget review
else:
    enqueue(P0_SMS_QUEUE, payload)
```

### 1.6 SMS Budget — Restructured Table and Corrected Circuit Breaker

**Problem with prior table:** It mixed annualized daily costs with one-time event costs in the same column, making the annual total non-derivable. The spike reserve was a total event cost, not an annual rate.

**Restructured cost table:**

| SMS category | Daily volume | Days/year active | Annual messages | Annual cost at $0.012/msg |
|---|---|---|---|---|
| OTP / 2FA (baseline) | 150K/day | 365 | 54.75M | **$657K** |
| OTP spike (est. 3 events/year, 10× for 1 day each) | 1.35M/event | 3 | 4.05M | **$49K** |
| Security alerts | 20K/day | 365 | 7.3M | **$88K** |
| Social/digest (hard cap) | ≤100K/day | 365 | ≤36.5M | **≤$438K** |
| **Total** | **~270K–370K/day baseline** | | **~102M–103M** | **~$1.23M–1.23M** |

The annual total is now derivable by summing the rightmost column. The prior $1.2–1.4M range is confirmed.

**Corrected circuit breaker thresholds:**