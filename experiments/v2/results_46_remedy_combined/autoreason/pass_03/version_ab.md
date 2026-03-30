# Notification System Design — Synthesized Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system handling approximately 90–180M notifications/day across push, email, in-app, and SMS channels, depending on which traffic scenario materializes. The architecture makes four core bets: durable managed queuing over custom Redis structures, proven third-party delivery providers over self-operated infrastructure, incremental delivery with explicit failure handling over optimistic pipelines, and a preference system that trades occasional staleness for throughput.

Every tradeoff is named. Where a decision requires authorization from outside the engineering team — budget, product behavior, legal compliance — that decision point is identified and the engineering default is stated. Engineers do not make business risk decisions unilaterally; they implement whatever is authorized and instrument everything so the consequences of those decisions are visible.

Three structural improvements over prior drafts: the scale model is treated as a range with explicit scaling triggers rather than a single point estimate; the FIFO queue throughput ceiling is modeled against realistic P1 traffic fractions rather than asserted as safe; and DLQ processing is designed as a first-class feature with per-priority strategies rather than acknowledged as operational surface and left unaddressed.

---

## 1. Scale Model

### 1.1 The Notification Rate Problem

All volume estimates depend on a single figure: notifications per opted-in user per day. That figure is unknown before launch and the architecture is sensitive to it.

**Why this matters concretely:**

| Rate Assumption | Push/day | Peak throughput | P1 FIFO risk |
|----------------|----------|-----------------|--------------|
| 5/user/day | 30M | ~1,400/sec | None |
| 15/user/day | 90M | ~4,300/sec | Moderate |
| 30/user/day | 180M | ~8,600/sec | High |

At 30 notifications/user/day — plausible for a messaging-first product — the architecture requires a different queue configuration for P1 and different worker counts. We cannot know which scenario applies before launch.

**What we do about it:** We instrument actual notification volume from day one, segment by type, and define explicit scaling triggers before those triggers are needed. We provision workers for the high scenario because over-provisioning SQS workers costs almost nothing (SQS pricing is per-request, not per-worker), while under-provisioning causes queue backup and delivery latency. The asymmetry favors over-provisioning.

**Scaling triggers — defined before launch, not after an incident:**

```
Week 1 target: instrument actual sends per user per day,
               segmented by notification type (DM, mention, like, digest)

Scaling trigger A: sustained peak > 6,000/sec for 15 minutes
  → Add 30 workers across P1/P2 queues
  → Re-evaluate FIFO queue headroom (see Section 2.2)

Scaling trigger B: sustained peak > 10,000/sec for 15 minutes
  → P1 queue migration from FIFO to standard + application-level ordering
  → Architecture review required; this is a structural change

Scaling trigger C: daily volume > 150M notifications for 3 consecutive days
  → SQS cost re-projection
  → Evaluate whether direct provider integration remains cost-optimal
```

**Traffic model across scenarios:**

| Metric | Conservative (5/day) | Base (15/day) | High (30/day) |
|--------|---------------------|---------------|---------------|
| Push opt-in rate | 60% → 6M users | — | — |
| Push/day | 30M | 90M | 180M |
| Email/day | 4M | 4M | 4M (digest model caps this) |
| In-app/day | 10M | 30M | 60M |
| SMS/day | 150K | 150K | 150K (hard cap) |
| Peak throughput | ~1,400/sec | ~4,300/sec | ~8,600/sec |

We size workers for the high scenario. We size costs against the base scenario and flag the delta.

### 1.2 SMS Cost — Tiered Alarms with Automated Response

SMS is the only channel where a security incident can generate unbounded costs. OTP and security SMS is exempt from the engagement cap but tracked separately.

| Scenario | OTP Volume | Daily Cost (Twilio $0.0079/msg) |
|----------|-----------|----------------------------------|
| Baseline (2FA logins, ~5% of DAU) | ~150K/day | ~$1,185 |
| Credential stuffing (forced re-auth, 20% MAU) | ~2M/day | ~$15,800 |
| Major security incident (all MAU forced re-auth) | ~10M/day | ~$79,000 |

A single $5,000/day alarm creates a $4,999/day blind spot. A moderate credential stuffing attack generating ~630K forced re-auths sits entirely below that threshold with no automated response. The correct structure is tiered alarms with automated escalation at each tier.

**Revised alarm tiers:**

| Tier | Threshold | Response |
|------|-----------|----------|
| Advisory | $500/day OTP SMS | Log to dashboard; no page |
| Warning | $1,500/day OTP SMS | Page on-call; investigate source |
| Critical | $3,000/day OTP SMS | Page on-call + security team; automated rate limiting activates |
| Emergency | $5,000/day OTP SMS | Automated fallback to email OTP; security incident declared |

**Automated response at Critical tier — does not wait for human response:**

```python
class OTPSMSRateLimiter:
    def should_send_sms_otp(self, user_id: str) -> tuple[bool, str]:
        daily_spend = self.metrics.get_daily_sms_spend()

        if daily_spend >= EMERGENCY_THRESHOLD:
            return False, "sms_disabled_emergency"

        if daily_spend >= CRITICAL_THRESHOLD:
            # Route to email OTP for users who have it enabled.
            # Only users with no email registration get SMS.
            has_email_otp = self.user_store.has_email_otp_enabled(user_id)
            if has_email_otp:
                return False, "rate_limited_to_email"

        # Per-user rate limit regardless of global spend
        user_key = f"otp_sms:{user_id}:{date.today()}"
        count = self.redis.incr(user_key)
        if count == 1:
            self.redis.expire(user_key, 86400)

        if count > MAX_OTP_SMS_PER_USER_PER_DAY:
            return False, "per_user_limit_exceeded"

        return True, "ok"
```

**Decision required from Security before launch:** The emergency fallback to email OTP must be authorized. Some security postures treat email-based OTP as insufficiently strong. Engineering implements whatever is authorized. The default above is email fallback rather than blocking authentication entirely — blocking authentication at scale during a security incident creates a second incident.

### 1.3 Team Allocation — With Time Accounting

Named owners without time allocation are not accountability. Available hours:

```
6 months × 4 engineers × ~160 hours/month = ~3,840 engineer-hours
Subtract: on-call rotation, meetings, code review, ramp-up (~20%)
Net available: ~3,072 engineer-hours
```

**Allocation by work category:**

| Category | Hours | Owner | Notes |
|----------|-------|-------|-------|
| Core pipeline + queue infrastructure | 400 | E1 | SQS setup, routing logic, worker framework |
| Push channel (APNs + FCM) | 350 | E2 | Token management, connection pools, feedback |
| Email channel (SendGrid) | 150 | E2 | Template system, bounce processing |
| SMS channel (Twilio) | 100 | E2 | Rate limiting, OTP separation |
| Cross-channel consistency | 200 | E1 + E2 | Shared ownership; see Section 5 |
| Preference management + user API | 300 | E3 | Opt-out, suppression, preference store |
| In-app notification store | 250 | E3 | PostgreSQL design, retention, inbox API |
| DLQ processing + failure handling | 200 | E4 | All four DLQ strategies; see Section 6 |
| Monitoring + alerting | 150 | E4 | CloudWatch, dashboards, runbooks |
| Test harness | 200 | E4 | Six named failure classes |
| Infrastructure (IaC, deployments) | 150 | E4 | Terraform, ECS task definitions |
| Buffer (integration, bugs, scope creep) | 422 | All | ~14% of total |
| **Total** | **3,072** | | |

**Cross-channel consistency is co-owned by E1 and E2** with 200 hours explicitly allocated. The problem — a user receiving duplicate notifications across channels during an in-flight preference update — requires coordination between the routing layer (E1) and the channel dispatchers (E2). A single named owner without the other's involvement cannot solve it.

**The test harness is 200 hours.** The six named failure classes (duplicate sends, missed suppressions, incorrect aggregation counts, timezone errors, broken unsubscribe links, token invalidation races) require meaningful coverage. This is not a percentage of E4's time — it is a fixed scope allocation. It means E4 has less time for other work, which is reflected above.

**Explicit out-of-scope for initial six months:**
- A/B testing framework for notification copy
- Send-time optimization
- Rich push notifications (images, deep action buttons)
- Analytics beyond delivery and open tracking

If product requires any of these, scope must be cut elsewhere. Engineering does not absorb additions silently.

---

## 2. Queue Architecture

### 2.1 Backend Choice: Amazon SQS

We use Amazon SQS with priority queues rather than Redis sorted sets. Two correctness problems make Redis the wrong choice.

**Problem 1 — Durability.** Redis in default configuration is not durable. A crash between enqueue and delivery loses notifications silently. For P0 traffic (OTPs, security alerts), silent loss is unacceptable. Configuring Redis with `appendfsync always` degrades write throughput and requires a replication topology we would need to operate ourselves.

**Problem 2 — Dequeue atomicity.** A Redis pipeline batches commands but does not provide atomicity. Two workers executing `ZRANGE + ZREM` simultaneously will dequeue overlapping items. The correct fix is a Lua script, but this adds operational complexity we do not need when SQS solves the problem natively.

**Tradeoff explicitly accepted:** Four queues means four dead-letter queues to monitor and four sets of CloudWatch alarms. This is more operational surface than one Redis sorted set. We accept this because SQS's durability and correct concurrent dequeue semantics are non-negotiable for P0 traffic, and managed operations are less work than operating Redis with AOF replication ourselves.

**SQS cost:** ~$0.40/million requests. At 125M notifications/day plus retries, approximately $1,800/month.

### 2.2 FIFO Queue Throughput — Modeled, Not Assumed

The SQS FIFO limit is 3,000 messages/second per queue. P0 is safe by nature — OTPs require a user action to trigger and are inherently low volume. P1 is the risk.

**Modeling P1 volume against traffic fraction:**

| Scenario | Total peak/sec | P1 fraction | P1/sec | FIFO headroom |
|----------|---------------|-------------|---------|---------------|
| Feed-first app | 4,300 | 15% | 645 | Comfortable |
| Mixed app | 4,300 | 35% | 1,505 | Moderate |
| Messaging-first app | 4,300 | 60% | 2,580 | Marginal |
| Messaging-first, high rate | 8,600 | 60% | 5,160 | **Exceeds limit** |

A messaging-first app at the high notification rate hits the FIFO ceiling. This is a real risk, not a theoretical one.

**Mitigation: Message Group ID sharding across multiple P1 FIFO queues**

SQS FIFO queues support multiple message groups. We shard P1 traffic across N queues using the recipient's user ID. Ordering is preserved per recipient within each shard.

```python
def get_p1_queue_url(recipient_id: str) -> str:
    """
    Shard P1 traffic across N FIFO queues by recipient ID.
    Ordering is preserved per recipient; shards are independent.
    """
    shard_count = settings.P1_QUEUE_SHARD_COUNT  # default: 4
    shard_index = hash(recipient_id) % shard_count
    return (
        f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT}"
        f"/notif-p1-{shard_index}.fifo"
    )
```

With 4 shards, effective P1 ceiling is 12,000/sec — above our high-scenario projection. Adding shards requires no architectural change, only a configuration increment and new queue creation.

**Week-1 action:** Instrument P1 fraction of total traffic. If P1 exceeds 40% of traffic in the first two weeks, activate 4-shard configuration immediately rather than waiting for saturation.

**Queue configuration:**

```
notif-p0.fifo           — Critical (OTP, security alerts)
                          Single queue; P0 volume is inherently low
                          3,000/sec ceiling is not a risk

notif-p1-{0..3}.fifo    — High (DMs, mentions)
                          4 shards from launch
                          Effective ceiling: 12,000/sec
                          MessageGroupId: recipient_id
                          Expand to 8 shards if Scaling Trigger A fires

notif-p2                — Normal (likes, follows, comments)
                          Standard queue; ordering not semantically meaningful

notif-p3                — Batch (digests, re-engagement)
                          Standard queue
```

**Worker allocation:**

```
P0:  15 workers — exclusive poll of notif-p0.fifo
P1:  25 workers — polling notif-p1-{0..3}.fifo (distributed evenly)
P2:  20 workers — polling notif-p2
P3:   5 workers — polling notif-p3
```

### 2.3 Idempotency on Standard Queues

Standard queues provide at-least-once delivery. Duplicate delivery is possible. We suppress duplicates with idempotency keys in Redis:

```python
class NotificationDispatcher:
    def dispatch(self, message: SQSMessage) -> None:
        notification_id = message.body["notification_id"]
        lock_key = f"sent:{notification_id}"

        # SET NX: only the first worker to acquire this key proceeds
        acquired = self.redis.set(lock_key, "1", nx=True, ex=86400)

        if not acquired:
            message.delete()
            self.metrics.increment(
                "dispatch.duplicate_suppressed",
                tags={"priority": message.body["priority"]}
            )
            return

        try:
            self._send_to_channel(message.body)
            message.delete()
        except Exception:
            if self._is_max_retries_exceeded(message):
                # Clear idempotency key so DLQ processor can retry cleanly
                self.redis.delete(lock_key)
            raise  # SQS visibility timeout returns message to queue
```

**Tradeoff explicitly accepted:** If Redis is unavailable, duplicate suppression fails and a user may receive a duplicate notification. For P0 (OTPs), this is acceptable — OTP tokens are single-use regardless of delivery count. For P1/P2, a duplicate mention or like is a UX annoyance, not a correctness failure. FIFO queues handle deduplication natively for P0 and P1, so the Redis dependency for duplicate suppression only applies to P2/P3 standard queues.

---

## 3. Delivery Channels

### 3.1 Push Notifications (~90M/day at base scenario)

**Provider:** FCM (Android) and APNs (iOS) directly, without an intermediary aggregator. At this volume, intermediary margins matter and direct provider APIs are well-documented.

**APNs JWT token management — distributed coordination:**

Two concepts that must not be conflated:
- **Signing key (.p8 file):** Rotated manually, only when comprom