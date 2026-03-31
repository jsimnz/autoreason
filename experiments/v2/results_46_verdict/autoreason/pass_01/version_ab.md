# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This document designs a notification system handling ~51M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **proven infrastructure over custom-built components**, **operational simplicity over theoretical elegance**, and **incremental delivery** over a big-bang launch. We ship a working system in month 2, iterate through month 5, and spend month 6 on hardening.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or complex event streaming. This is the right tradeoff for a team of 4 — it's debuggable, replaceable, and sufficient for 10M MAU. We revisit at 50M MAU.

Every tradeoff in this document is explicit. Where we accept risk, we name it. Where we defer complexity, we state the trigger for revisiting.

---

## 1. Scale Assumptions and Constraints

### 1.1 Traffic Modeling

A critical modeling error to avoid upfront: different channels have different eligible populations. Push notifications reach installed-app users regardless of daily activity. In-app notifications only reach logged-in users. Treating DAU as the denominator for all channels produces wrong numbers.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Push-eligible users | 7M | 70% of MAU with app installed and push enabled |
| Push/push-eligible user/day | ~5 | Aggressive but not opt-out-inducing; industry benchmarks 3–8 |
| **Push volume/day** | **~35M** | 7M × 5 |
| In-app/DAU/day | ~5 | Active users only |
| **In-app volume/day** | **~15M** | 3M × 5 |
| **Email/day** | **~1M** | Digests + transactional; not every user daily |
| **SMS/day** | **~50K** | Auth and security only — see Section 3.4 |
| **Total/day** | **~51M** | Sum across channels |
| Peak multiplier | 3× | Morning/evening spikes |
| **Peak throughput** | **~1,770/sec** | 51M × 3 / 86,400 |

**On SMS volume:** An earlier draft of this design estimated 1M SMS/day. At Twilio's volume pricing (~$0.0075/message), that is $225K/month — an existential budget problem, not a footnote. Restricting SMS to auth and security events brings this to ~$375/day (~$11K/month), which is significant but defensible. SMS is treated as a privileged channel with hard gates throughout this document.

**On push volume:** 5 notifications/day/installed user is a deliberate product constraint, not a technical one. Exceeding this risks mass opt-outs. We monitor opt-out rates weekly and treat any week-over-week increase above 0.5% as a P1 incident.

These are estimates. We instrument from day one and publish a traffic model review in month 2. If push opt-in rates or per-user rates deviate materially, we adjust channel budgets before they become cost or deliverability problems.

### 1.2 Team Allocation

**Bus factor is the primary organizational risk with 4 engineers.** The original instinct to give one engineer sole ownership of all channel integrations is wrong. We distribute ownership and require cross-training.

| Engineer | Primary Responsibility | Channel Ownership | Cross-Trained On |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | In-app storage |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | Email |
| E3 | Preference management, user-facing API, suppression logic | In-app | SMS |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | Push |

**Cross-training requirement:** By month 3, E2 and E4 complete a one-week rotation on each other's channel integrations. Runbooks are written by the primary owner, reviewed and signed off by the cross-trainer. No channel integration is deployable without the cross-trainer having completed at least one production deployment.

All engineers rotate on-call. No dedicated QA — engineers own quality. This is a risk we accept given the timeline. The mitigation is runbooks and observability, not headcount we don't have.

### 1.3 Delivery Milestones

| Month | Deliverable |
|-------|-------------|
| 1 | Infrastructure provisioned, in-app notifications live, preference API |
| 2 | Push (FCM + APNs) live, email transactional live, basic monitoring |
| 3 | Email digests, SMS (auth only), aggregation logic, cross-training rotation |
| 4 | Full preference management, suppression lists, advanced batching |
| 5 | Re-engagement campaigns, A/B framework for notification copy |
| 6 | Hardening: chaos testing, runbook review, load testing to 2× peak |

---

## 2. System Architecture

### 2.1 High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
     │
     ▼
[Notification Router]
  - Preference check (Redis cache, explicit TTL + invalidation)
  - Suppression check (do-not-contact, frequency caps)
  - Priority assignment (by notification type)
  - Channel selection
     │
     ├─────────────────────────────────────────────┐
     ▼                                             ▼
[Priority Queue]                          [In-App Store]
  (Redis Sorted Set + Lua scripts)         (PostgreSQL, partitioned)
     │                                             │
     ├── P0 Worker Pool (10 workers)               ▼
     ├── P1 Worker Pool (20 workers)      [WebSocket Pub/Sub]
     └── P2 Worker Pool (10 workers)       (Redis, best-effort)
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (SendGrid)
     └── SMS (Twilio — auth/security only)
          │
          ▼
   [Delivery Log]
   (PostgreSQL + S3 archive)
          │
          ▼
   [Feedback Processor]
   (bounces, opens, failures, token invalidation)
```

### 2.2 Architectural Decisions and Tradeoffs

**Single queue with priority scoring, not per-channel queues.**
Per-channel queues create operational complexity: N queues to monitor, N dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set handles 51M items comfortably. The tradeoff is that per-channel rate limiting requires logic in the dispatcher rather than queue topology. This is acceptable at 10M MAU and revisited at 50M.

**Synchronous preference check at routing time, not delivery time.**
User preferences are cached in Redis with explicit TTLs and invalidation (see Section 5). Checking at routing keeps workers stateless and fast, and avoids consuming queue capacity for notifications we'll discard. The tradeoff is that preference changes during the routing-to-delivery window may not take effect immediately — acceptable for a social app, unacceptable for a financial or medical app.

**In-app notifications bypass the queue.**
In-app notifications are writes to a PostgreSQL table that clients poll or receive via WebSocket. They're read-heavy, need random access by user, and benefit from immediate consistency. Routing them through the push queue adds latency with no benefit. The tradeoff is two code paths to maintain; we accept this because the operational profiles are genuinely different.

**Managed providers over self-hosted.**
We use FCM/APNs directly, SendGrid for email, and Twilio for SMS. We do not self-host SMTP, build our own push infrastructure, or run our own message broker beyond Redis. The tradeoff is vendor dependency and cost; the benefit is that 4 engineers don't spend 6 months building infrastructure instead of product.

---

## 3. Delivery Channels

### 3.1 Push Notifications (~35M/day)

**Provider:** FCM HTTP v1 API for Android, APNs HTTP/2 for iOS. Direct integrations.

**Tradeoff vs. OneSignal/Braze:** A managed push platform saves 4–6 weeks of integration work but costs $50–150K/year at our scale and reduces control over retry behavior, delivery receipts, and token management. We build direct integrations. We revisit if we need advanced segmentation features in year 2.

#### FCM Integration

**Critical implementation note:** FCM HTTP v1 API does not support multi-token batch requests — that was a feature of the legacy API, deprecated June 2024. The v1 API requires one HTTP request per device token. Any throughput calculation based on 500-token batches is wrong.

At 35M push/day with a 70/30 Android/iOS split, that's approximately 24.5M FCM requests/day, or ~850/sec average and ~2,550/sec at 3× peak.

```
FCM Configuration:
- HTTP/2 multiplexing: 50 persistent connections
- ~100 concurrent streams per connection = 5,000 concurrent in-flight requests
- Throughput target: 3,000 req/sec sustained (headroom above 2,550 peak)
- FCM quota: default 600,000 requests/minute (~10,000/sec); well within limit
- Workers are stateless; each maintains its own connection pool
- At 2,550 peak req/sec across 20 P1 workers: ~128 req/sec per worker
  — achievable with HTTP/2 multiplexing

Error handling:
- InvalidRegistration / NotRegistered: mark token invalid, never retry
- 429 / 500: exponential backoff, max 3 retries for P1/P2
- P0: up to 10 retries with 1s initial backoff
- 503: treat as transient, retry with backoff
```

**Payload design:**

```json
{
  "notification": {
    "title": "{{actor}} liked your photo",
    "body": "{{actor}} and 3 others liked your photo"
  },
  "data": {
    "notification_id": "ntf_01H8X...",
    "type": "like",
    "entity_type": "post",
    "entity_id": "pst_01H7Y...",
    "deep_link": "myapp://posts/pst_01H7Y",
    "badge_count": "12"
  },
  "apns": {
    "headers": {
      "apns-collapse-id": "like:pst_01H7Y",
      "apns-priority": "10"
    }
  }
}
```

#### APNs JWT Rotation — Operationally Hardened

APNs JWTs must be generated with an `iat` claim and are rejected after 60 minutes. We rotate at 55 minutes. JWT rotation failure means all APNs delivery stops silently — this is a single point of failure that requires explicit handling, not a configuration footnote.

```python
class APNsJWTManager:
    """
    Manages APNs JWT lifecycle with monitoring and graceful rotation.
    Shared across all APNs workers via Redis to prevent thundering herd.
    """
    JWT_TTL_SECONDS = 3300      # 55 minutes
    OVERLAP_SECONDS = 60        # keep previous token valid during transition

    def get_current_token(self) -> str:
        token_data = self.redis.get("apns:jwt:current")
        if token_data is None:
            return self._rotate()
        token = APNsToken.parse(token_data)
        if time.time() - token.issued_at >= self.JWT_TTL_SECONDS:
            return self._rotate()
        return token.value

    def _rotate(self) -> str:
        # SET NX prevents multiple workers from rotating simultaneously
        lock = self.redis.set("apns:jwt:rotating", "1", nx=True, ex=10)
        if not lock:
            time.sleep(0.1)
            return self._get_with_fallback()
        try:
            new_token = self._generate_jwt()
            pipe = self.redis.pipeline()
            # Preserve previous token for overlap window
            pipe.set("apns:jwt:previous",
                     self.redis.get("apns:jwt:current") or "",
                     ex=self.OVERLAP_SECONDS)
            pipe.set("apns:jwt:current",
                     new_token.serialize(),
                     ex=self.JWT_TTL_SECONDS + 60)
            pipe.execute()
            self.metrics.increment("apns.jwt.rotation.success")
            return new_token.value
        except Exception as e:
            self.metrics.increment("apns.jwt.rotation.failure")
            self.alerting.page(
                "APNs JWT rotation failed — delivery at risk",
                severity="P1"
            )
            raise
        finally:
            self.redis.delete("apns:jwt:rotating")

    def _get_with_fallback(self) -> str:
        current = self.redis.get("apns:jwt:current")
        if current:
            return APNsToken.parse(current).value
        previous = self.redis.get("apns:jwt:previous")
        if previous:
            return APNsToken.parse(previous).value
        return self._rotate()
```

**Required monitoring (non-negotiable):**
- Alert if `apns:jwt:current` age exceeds 50 minutes (rotation is late)
- Alert if rotation raises an exception
- Alert if APNs 403 rate exceeds 0.1% (JWT rejected — silent rotation failure)
- Dashboard: JWT age, rotation success/failure count, APNs 403 rate

**Deployment note:** During rolling deployments, new workers may generate a new JWT before old workers have rotated. The 60-second overlap window and previous-token fallback handle this. We test this explicitly in staging.

#### Token Management

Stale push tokens are the top operational headache in push systems:

- Store tokens in `push_tokens` table with `last_used_at`, `is_valid`, `app_version` columns
- On FCM `InvalidRegistration` or `NotRegistered`: mark invalid immediately, never retry that token
- On APNs 410 with timestamp: tokens registered after that timestamp are valid; older ones are not
- On APNs 410 without timestamp: mark invalid immediately
- Batch-purge tokens unused for 90 days (uninstalled apps)
- Weekly job: count invalid tokens by app version; a sharp increase indicates a token registration bug in a specific release

### 3.2 Email (~1M/day)

**Provider:** SendGrid (~$500/month at 1M/day). AWS SES would be significantly cheaper but SendGrid's suppression list management, deliverability tooling, and webhook reliability reduce operational burden for a team of 4.

| Type | Trigger | Frequency Cap |
|------|---------|---------------|
| Transactional | Immediate (password reset, security alert) | No cap |
| Activity digest | Daily or weekly batch | User-controlled |
| Re-engagement | 7-day inactivity | Max 1/week |
| Marketing | Product announcements | Max 1/week |

**Template system:** SendGrid Dynamic Templates with Handlebars, versioned in Git, deployed via SendGrid API in CI/CD. Designers work in SendGrid's editor; engineers manage deployment. Templates are immutable once deployed — new versions get new IDs.

**Deliverability requirements (configured on day 1, not later):**
- Dedicated IP pool for transactional vs. marketing (warmed separately)
- SPF, DKIM, and DMARC configured before first send
- Bounce rate target: <2%; spam complaint rate target: <0.1%
- Suppression list: sync SendGrid suppression list to our database daily

#### Digest Batching — With Carry-Forward Bounds

A common digest implementation error: defining a minimum-item threshold for sending, then silently holding events indefinitely for low-activity users. This is a product problem (users miss notifications) and potentially a compliance problem (users don't know what's being held). We bound accumulation explicitly.

```python
MAX_CARRY_FORWARD_DAYS = 3
MIN_DIGEST_ITEMS = 3
MAX_CARRY_FORWARD_EVENTS = 20