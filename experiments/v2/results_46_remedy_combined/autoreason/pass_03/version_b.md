# Notification System Design — Revised Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This proposal designs a notification system for a social app at 10M MAU. The previous version made four architectural bets that remain correct: durable managed queuing, third-party delivery providers, incremental delivery with explicit failure handling, and a preference system trading occasional staleness for throughput. This revision addresses ten specific problems in the previous version: an unvalidated scale model that drove all downstream decisions, a FIFO queue throughput miscalculation, two correctness problems in the APNs token manager, a P0 dependency on Redis availability that contradicted P0's own requirements, an unexamined team scope, a compliance window mischaracterized as a UX tradeoff, an undesigned in-app store, an absent DLQ processing strategy, a cost alarm with a $4,999/day blind spot, and an engineer allocation that named owners without allocating time.

Each section below identifies what changed and why.

---

## 1. Scale Model

### 1.1 The Notification Rate Problem

The previous version used 15 notifications/opted-in user/day as the basis for all volume estimates. A critic correctly identified this as doing enormous work with no validation. The figure is not wrong as a rough industry midpoint, but the architecture is sensitive to it in ways that weren't examined.

**Why this matters concretely:**

| Rate Assumption | Push/day | Peak throughput | P1 FIFO risk |
|----------------|----------|-----------------|--------------|
| 5/user/day | 30M | ~1,400/sec | None |
| 15/user/day | 90M | ~4,300/sec | Moderate |
| 30/user/day | 180M | ~8,600/sec | High |

At 30 notifications/user/day — plausible if this app is primarily a messaging product — the architecture requires a different queue backend for P1 and different worker counts. We cannot know which scenario applies before launch.

**What we do about it:**

We instrument actual notification volume from day one and define explicit scaling triggers before those triggers are needed. The architecture is designed to scale up without structural changes; the triggers define when scaling is required.

```
Week 1 target: instrument actual sends per user per day
               segment by notification type (DM, mention, like, digest)

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

The 15/user/day figure is used for initial provisioning. We provision for 2× that figure (30/user/day) on queues and workers because over-provisioning SQS workers costs almost nothing — SQS pricing is per-request, not per-worker. Under-provisioning causes queue backup and delivery latency. The asymmetry favors over-provisioning.

**Revised traffic model:**

| Metric | Conservative (5/day) | Base (15/day) | High (30/day) |
|--------|---------------------|---------------|---------------|
| Push/day | 30M | 90M | 180M |
| Email/day | 4M | 4M | 4M (digest model caps this) |
| In-app/day | 10M | 30M | 60M |
| SMS/day | 150K | 150K | 150K (hard cap) |
| Peak throughput | ~1,400/sec | ~4,300/sec | ~8,600/sec |

We size workers for the high scenario. We size costs against the base scenario and flag the delta.

### 1.2 SMS Cost — Revised Alarm Structure

The previous version set a single $5,000/day alarm for OTP SMS. A critic correctly identified this as a $4,999/day blind spot: a moderate credential stuffing attack generating ~630K forced re-auths sits entirely below the alarm threshold with no automated response.

**Revised alarm tiers:**

| Tier | Threshold | Response |
|------|-----------|----------|
| Advisory | $500/day OTP SMS | Log to dashboard; no page |
| Warning | $1,500/day OTP SMS | Page on-call; investigate source |
| Critical | $3,000/day OTP SMS | Page on-call + security team; automated rate limiting activates |
| Emergency | $5,000/day OTP SMS | Automated fallback to email OTP; security incident declared |

**Automated response at Critical tier:**

```python
class OTPSMSRateLimiter:
    """
    Activates automatically when OTP SMS spend crosses $3,000/day.
    Does not wait for human response.
    """
    def should_send_sms_otp(self, user_id: str) -> tuple[bool, str]:
        daily_spend = self.metrics.get_daily_sms_spend()

        if daily_spend >= EMERGENCY_THRESHOLD:
            # Fallback is already active system-wide; this path
            # should not be reached but is a safety check
            return False, "sms_disabled_emergency"

        if daily_spend >= CRITICAL_THRESHOLD:
            # Rate limit: allow SMS OTP only for users with no
            # registered email, or who have explicitly disabled
            # email 2FA. Everyone else gets email OTP.
            has_email_otp = self.user_store.has_email_otp_enabled(user_id)
            if has_email_otp:
                return False, "rate_limited_to_email"

        # Check per-user rate limit regardless of global spend
        user_key = f"otp_sms:{user_id}:{date.today()}"
        count = self.redis.incr(user_key)
        if count == 1:
            self.redis.expire(user_key, 86400)

        if count > MAX_OTP_SMS_PER_USER_PER_DAY:
            return False, "per_user_limit_exceeded"

        return True, "ok"
```

**Decision required from Security before launch:** The emergency fallback to email OTP must be authorized. Some security postures treat email-based OTP as insufficiently strong. Engineering implements whatever is authorized; the default above is email fallback rather than blocking authentication entirely, because blocking authentication at scale during a security incident creates a second incident.

### 1.3 Team Allocation — Revised with Time Accounting

The previous version named owners without examining whether scope was achievable. E2 owned four channel integrations plus cross-channel consistency; E4 owned reliability, monitoring, failure handling, infrastructure, a test harness, and on-call rotation. Neither allocation was examined against available hours.

**Available engineering time:**

```
6 months × 4 engineers × ~160 hours/month = ~3,840 engineer-hours
Subtract: on-call rotation, meetings, code review, ramp-up = ~20%
Net available: ~3,072 engineer-hours
```

**Revised allocation by work category:**

| Category | Hours | Owner | Notes |
|----------|-------|-------|-------|
| Core pipeline + queue infrastructure | 400 | E1 | SQS setup, routing logic, worker framework |
| Push channel (APNs + FCM) | 350 | E2 | Token management, connection pools, feedback |
| Email channel (SendGrid) | 150 | E2 | Template system, bounce processing |
| SMS channel (Twilio) | 100 | E2 | Rate limiting, OTP separation |
| Cross-channel consistency | 200 | E1 + E2 | Shared ownership; see below |
| Preference management + user API | 300 | E3 | Opt-out, suppression, preference store |
| In-app notification store | 250 | E3 | PostgreSQL design, retention, inbox API |
| DLQ processing + failure handling | 200 | E4 | All four DLQs; see Section 6 |
| Monitoring + alerting | 150 | E4 | CloudWatch, dashboards, runbooks |
| Test harness | 200 | E4 | Six named failure classes |
| Infrastructure (IaC, deployments) | 150 | E4 | Terraform, ECS task definitions |
| Buffer (integration, bugs, scope creep) | 422 | All | ~14% of total |
| **Total** | **3,072** | | |

**Cross-channel consistency is now co-owned by E1 and E2** with 200 hours allocated. The previous version named E2 as sole owner without time. The specific problem — a user receiving duplicate notifications across channels during an in-flight preference update — requires coordination between the routing layer (E1) and the channel dispatchers (E2). Section 5 describes the concrete mitigation.

**The test harness is 200 hours, not 15% of E4's time.** 15% of E4's time is ~72 hours over six months. 200 hours is the minimum to cover the six named failure classes with meaningful test coverage. This is the correct number. It means E4 has less time for other work, which is reflected in the allocation above. The previous version stated a percentage that was too small and described it as sufficient.

**What this allocation does not cover:**

- A/B testing framework for notification copy
- Notification scheduling (send-time optimization)
- Rich push notifications (images, action buttons beyond basic)
- Analytics beyond delivery and open tracking

These are explicitly out of scope for the initial six months. If product requires any of them, scope must be cut elsewhere. Engineering does not absorb scope additions silently.

---

## 2. Queue Architecture

### 2.1 Backend Choice: Amazon SQS

Unchanged from the previous version. The correctness arguments for SQS over Redis sorted sets — durability and atomic dequeue — remain valid. This section focuses on the FIFO throughput problem the previous version did not model.

### 2.2 FIFO Queue Throughput — Corrected Analysis

The previous version stated P0 and P1 traffic "stays well within" the 3,000 messages/second FIFO limit without providing a breakdown. A critic correctly identified that on a social app where DMs and mentions are primary engagement vectors, P1 could easily saturate at peak.

**What P1 actually contains and why it's the risk:**

P0 (OTPs, security alerts) is low volume by nature — it requires a user action to trigger. P1 (DMs, mentions) scales with engagement. On a messaging-heavy social app, P1 is the dominant traffic class.

**Modeling P1 volume under different assumptions:**

| Scenario | Total peak/sec | P1 fraction | P1/sec | FIFO headroom |
|----------|---------------|-------------|---------|---------------|
| Feed-first app | 4,300 | 15% | 645 | Comfortable |
| Mixed app | 4,300 | 35% | 1,505 | Moderate |
| Messaging-first app | 4,300 | 60% | 2,580 | Marginal |
| Messaging-first, high rate | 8,600 | 60% | 5,160 | **Exceeds limit** |

**The risk is real.** A messaging-first app at the high notification rate hits the FIFO limit.

**Mitigation: Message Group ID sharding within FIFO queues**

SQS FIFO queues support multiple message groups. The 3,000 messages/second limit applies per queue. We can shard across multiple P1 FIFO queues using the recipient's user ID:

```python
def get_p1_queue_url(recipient_id: str) -> str:
    """
    Shard P1 traffic across N FIFO queues by recipient ID.
    Ordering is preserved per recipient across shards.
    """
    shard_count = settings.P1_QUEUE_SHARD_COUNT  # default: 4
    shard_index = hash(recipient_id) % shard_count
    return f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/notif-p1-{shard_index}.fifo"
```

With 4 shards, effective P1 throughput ceiling is 12,000/sec — above our high-scenario projection. Adding shards requires no architectural change, only a configuration increment and new queue creation.

**Week-1 action:** Instrument P1 fraction of total traffic. If P1 exceeds 40% of traffic during the first two weeks, activate 4-shard configuration immediately rather than waiting for saturation.

**Queue configuration — revised:**

```
notif-p0.fifo           — Critical (OTP, security alerts)
                          Single queue; P0 volume is inherently low
                          3,000/sec ceiling is not a risk

notif-p1-{0..3}.fifo    — High (DMs, mentions)
                          4 shards provisioned from launch
                          Effective ceiling: 12,000/sec
                          MessageGroupId: recipient_id
                          Expand to 8 shards if scaling trigger A fires

notif-p2                — Normal (likes, follows, comments)
                          Standard queue; ordering not semantically meaningful

notif-p3                — Batch (digests, re-engagement)
                          Standard queue
```

### 2.3 DLQ Processing Strategy

The previous version acknowledged four dead-letter queues as operational surface and then never described what happens to messages in them. For P0 (OTPs), a message in the DLQ means a user cannot authenticate. This is not an acceptable silent state.

**DLQ processing is a first-class feature, not an afterthought.** E4 owns it. 200 hours of E4's time covers DLQ processing as part of failure handling (see Section 1.3).

**Per-queue DLQ strategy:**

**P0 DLQ — OTPs and security alerts:**

```
Trigger: Message reaches DLQ (maxReceiveCount: 3, visibility timeout: 30s)
Immediate response:
  1. CloudWatch alarm fires within 60 seconds (alarm period: 1 minute)
  2. On-call paged immediately — not a 5-minute aggregation
  3. Automated fallback: attempt delivery via secondary channel
     - If push OTP failed: send via SMS if available, else email
     - If SMS OTP failed: send via email
     - Fallback attempt is logged separately from original attempt
  4. If fallback also fails: user-facing error on next auth attempt
     instructs them to request a new OTP
  
Manual review: DLQ messages are not retried automatically after 3 failures.
The failure reason is logged. On-call determines whether the failure is
transient (provider outage → retry after recovery) or permanent
(invalid token → suppress and clean up).
```

**P1 DLQ — DMs and mentions:**

```
Trigger: maxReceiveCount: 5, visibility timeout: 60s
Response:
  1. CloudWatch alarm: fires when DLQ depth > 100 messages
  2. On-call paged if DLQ depth > 500 messages (sustained provider issue)
  3. Automated retry: DLQ processor re-enqueues to P1 after 15-minute delay
     - Maximum 2 automated retries from DLQ
     - After 2 DLQ retries: mark notification as permanently failed
     - User sees "Message delivery failed" in in-app notification center
     - In-app delivery is attempted as fallback for DMs (content is stored)
  4. Metrics: DLQ entry rate tracked per channel; spike = provider issue
```

**P2/P3 DLQ — Likes, follows, digests:**

```
Trigger: maxReceiveCount: 5 (P2), 3 (P3)
Response:
  1. CloudWatch alarm: fires when DLQ depth > 1,000 messages
  2. Automated retry: re-enqueue with 30-minute delay, once
  3. After single DLQ retry: drop permanently
     - Rationale: a like notification from 2 hours ago has no value
     - Digest failures: next scheduled digest will include the content
  4. No user-facing error state for dropped P2/P3 notifications
  5. Metrics: drop rate tracked; sustained drops indicate systemic issue
```

**DLQ processor architecture:**

```python
class DLQProcessor:
    """
    Runs as a separate ECS task, not as part of the main worker pool.
    Polls each DLQ on a schedule; does not compete with main workers.