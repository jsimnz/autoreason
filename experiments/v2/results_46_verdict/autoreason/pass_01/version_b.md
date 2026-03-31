# Notification System Design Proposal (Revised)
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Revision Notes

This revision addresses eleven specific technical and operational problems identified in review. Each fix is called out inline. Where a criticism revealed a genuine design error, the design is changed. Where it revealed an underspecified assumption, the assumption is made explicit with its tradeoffs stated.

---

## Executive Summary

This proposal designs a notification system handling ~30M notifications/day across push, email, in-app, and SMS channels. *(Volume revised downward from 50M — see Section 1.)* Given the team size and timeline, we prioritize proven infrastructure over custom-built components, operational simplicity over theoretical elegance, and incremental delivery over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or complex event streaming. This is the right tradeoff for a team of 4 — it's debuggable, replaceable, and sufficient for 10M MAU. We revisit at 50M.

---

## 1. Scale Assumptions and Constraints

### Traffic Modeling — Revised

**Fix for Criticism #5:** The original model used DAU as the denominator for all channels, which is wrong. Push notifications go to installed-app users regardless of daily activity. In-app notifications only reach logged-in users. These are different populations. The original 17 notifications/user/day figure was also implausibly high for push and would cause mass opt-outs in practice. Revised model below.

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU (social apps) |
| Installed-app users (push-eligible) | 7M | 70% of MAU have app installed with push enabled |
| Push notifications/installed user/day | ~5 | Aggressive but not opt-out-inducing; industry benchmarks 3–8 |
| **Push volume/day** | **~35M** | 7M × 5 |
| In-app notifications/DAU/day | ~5 | Active users only |
| **In-app volume/day** | **~15M** | 3M × 5 |
| Email/day | ~1M | Digests + transactional; not every user daily |
| SMS/day | ~50K | Auth + security only; see Section 3.4 |
| **Total notifications/day** | **~51M** | Sum across channels |
| Peak multiplier | 3× | Morning/evening spikes |
| Peak throughput | ~1,770/sec | 51M × 3 / 86,400 |

**SMS volume revised dramatically downward — see Section 3.4 for the full explanation.** The original 1M SMS/day figure implied $225K/month in Twilio costs, which is an existential budget problem, not a footnote. The 50K/day figure (~$375/day, ~$11K/month) is still significant but defensible for auth-only SMS.

These remain estimates. We instrument from day one and publish a traffic model review in month 2. If push opt-in rates are lower than 70% or per-user rates are higher than 5, we adjust channel budgets before they become cost problems.

### Team Allocation — Revised

**Fix for Criticism #9:** The original allocation gave E2 sole ownership of all four channel integrations — the highest bus-factor risk in the system. Revised to distribute channel ownership and require cross-training.

| Engineer | Primary Responsibility | Channel Ownership | Cross-Trained On |
|----------|----------------------|-------------------|-----------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | — | In-app storage |
| E2 | Push integrations (APNs, FCM), WebSocket delivery | Push | Email |
| E3 | Preference management, user-facing API, suppression logic | In-app | SMS |
| E4 | Email/SMS integrations, reliability, monitoring, DevOps | Email + SMS | Push |

**Explicit cross-training requirement:** By month 3, E2 and E4 swap a one-week rotation on each other's channel integrations. Runbooks for all channels are written by the primary owner but reviewed and signed off by the cross-trainer. No channel integration is deployable without the cross-trainer having done at least one production deployment.

**Risk still present:** With 4 engineers, any two-person absence creates coverage gaps. We accept this. The mitigation is runbooks, not headcount we don't have.

---

## 2. System Architecture

### High-Level Data Flow

```
Event Sources
     │
     ▼
[Event Ingestion API]
     │
     ▼
[Notification Router]
  - Preference check (cache, with defined invalidation — see §5)
  - Suppression check
  - Priority assignment
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
     ├── Push (APNs / FCM — one request per token)
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

### Why This Architecture

**Single queue with priority scoring, not per-channel queues.** Per-channel queues create operational complexity: 4 queues to monitor, 4 dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set handles 51M items comfortably. We revisit when we need per-channel rate limiting at scale.

**Synchronous preference check at routing time, not delivery time.** User preferences are cached in Redis with explicit TTLs and invalidation (see Section 5). Checking at routing keeps workers dumb and fast, and avoids consuming queue capacity for notifications we'll discard.

**In-app notifications bypass the queue.** In-app notifications are writes to a PostgreSQL table that clients poll or receive via WebSocket. They're read-heavy, need random access by user, and benefit from immediate consistency. Putting them through the push queue adds latency for no benefit.

---

## 3. Delivery Channels

### 3.1 Push Notifications (~35M/day)

**Provider:** FCM for Android, APNs for iOS. Direct integrations, no intermediary.

**Tradeoff:** OneSignal/Braze saves 4–6 weeks of integration work but costs $50–150K/year at our scale and reduces control over retry behavior and delivery receipts. We build direct integrations and accept the upfront cost.

#### FCM Integration — Corrected

**Fix for Criticism #11:** The original proposal specified 500-token batch requests for FCM HTTP v1 API. This is wrong. FCM HTTP v1 does not support multi-token batch requests — that was a feature of the legacy FCM API (deprecated June 2024). The v1 API requires one HTTP request per device token. The throughput math based on 500-token batches was therefore entirely wrong and needs to be replaced.

**Corrected FCM approach:**

FCM HTTP v1 requires one request per token. At 35M push/day with a 70/30 Android/iOS split, that's ~24.5M FCM requests/day, or ~850/sec average, ~2,550/sec at 3× peak.

```
FCM Configuration:
- HTTP/2 multiplexing: 50 persistent connections, ~100 concurrent 
  streams per connection = 5,000 concurrent in-flight requests
- Throughput target: 3,000 req/sec sustained (headroom above 2,550 peak)
- FCM quota: default 600,000 requests/minute per project (~10,000/sec);
  we are well within this
- Token validation: on InvalidRegistration response, mark invalid 
  and never retry that token
- On 429 or 500: exponential backoff, max 3 retries for P1/P2; 
  P0 retries up to 10 times with 1s initial backoff
```

Workers are stateless; each worker maintains its own connection pool. At 2,550 peak req/sec across 20 P1 workers, each worker needs to sustain ~128 req/sec — achievable with HTTP/2 multiplexing.

**APNs Configuration:**

```
APNs Configuration:
- HTTP/2 with JWT authentication
- JWT rotation: every 55 minutes (APNs tokens expire at 60 minutes)
  — see Section 3.1.1 for rotation implementation
- Connection pool: 20 persistent HTTP/2 connections
- Priority header: 10 (immediate) for P0/P1, 5 (power-saving) for P2
- Collapse key: notification_type + entity_id to collapse stale notifications
- APNs also supports token-based batch: still one notification per 
  request, same as FCM v1
```

#### 3.1.1 APNs JWT Rotation — Operationally Hardened

**Fix for Criticism #8:** The original proposal mentioned JWT rotation as a configuration detail with no implementation. JWT rotation failure means all APNs delivery stops silently — this is a single point of failure that needs explicit handling.

**JWT lifecycle:**

APNs JWTs must be generated with a timestamp (`iat` claim) and are rejected after 60 minutes. We rotate at 55 minutes to avoid edge cases.

```python
class APNsJWTManager:
    """
    Manages APNs JWT lifecycle with monitoring and graceful rotation.
    Shared across all APNs connection pool workers via Redis.
    """
    
    JWT_TTL_SECONDS = 3300  # 55 minutes
    ROTATION_OVERLAP_SECONDS = 60  # keep old token valid during transition
    
    def get_current_token(self) -> str:
        """Returns current valid JWT, rotating if necessary."""
        token_data = self.redis.get("apns:jwt:current")
        
        if token_data is None:
            return self._rotate()
        
        token = APNsToken.parse(token_data)
        age = time.time() - token.issued_at
        
        if age >= self.JWT_TTL_SECONDS:
            return self._rotate()
        
        return token.value
    
    def _rotate(self) -> str:
        """
        Atomic rotation using Redis SET NX to prevent thundering herd.
        Only one worker rotates; others wait and then read the new token.
        """
        lock = self.redis.set(
            "apns:jwt:rotating", "1", 
            nx=True,  # only set if not exists
            ex=10     # lock expires in 10 seconds
        )
        
        if not lock:
            # Another worker is rotating; wait and return current or previous
            time.sleep(0.1)
            return self._get_with_fallback()
        
        try:
            new_token = self._generate_jwt()
            
            # Store new token; keep previous token accessible during overlap
            pipe = self.redis.pipeline()
            pipe.set("apns:jwt:previous", 
                     self.redis.get("apns:jwt:current") or "",
                     ex=self.ROTATION_OVERLAP_SECONDS)
            pipe.set("apns:jwt:current", new_token.serialize(), 
                     ex=self.JWT_TTL_SECONDS + 60)
            pipe.execute()
            
            self.metrics.increment("apns.jwt.rotation.success")
            return new_token.value
            
        except Exception as e:
            self.metrics.increment("apns.jwt.rotation.failure")
            self.alerting.page("APNs JWT rotation failed — delivery at risk",
                               severity="P1")
            raise
        finally:
            self.redis.delete("apns:jwt:rotating")
    
    def _get_with_fallback(self) -> str:
        """Returns current token if available, previous token as fallback."""
        current = self.redis.get("apns:jwt:current")
        if current:
            return APNsToken.parse(current).value
        previous = self.redis.get("apns:jwt:previous")
        if previous:
            return APNsToken.parse(previous).value
        # Both missing: rotation has failed or system just started
        return self._rotate()
```

**Monitoring requirements (non-negotiable):**
- Alert if `apns:jwt:current` age exceeds 50 minutes (rotation is late)
- Alert if rotation fails (exception caught above)
- Alert if APNs starts returning 403 (JWT rejected — rotation has failed silently)
- Dashboard: APNs 403 rate, JWT age, rotation success/failure count

**Deployment consideration:** During a rolling deployment, new workers may generate a new JWT before old workers have rotated. The overlap window (60 seconds) and previous-token fallback handle this. We test this explicitly in staging.

#### 3.1.2 Token Management

Stale push tokens are the #1 operational headache:

- Store tokens in `push_tokens` table with `last_used_at` and `is_valid` columns
- On FCM `InvalidRegistration` or `NotRegistered`: mark invalid immediately, never retry
- On APNs 410: record the timestamp APNs provides; tokens registered after that timestamp are valid
- On APNs 410 with no timestamp: mark invalid immediately
- Batch-purge tokens unused for 90 days (users uninstall without explicit logout)
- Weekly job: count invalid tokens by app version; sharp increases indicate a token registration bug

---

### 3.2 Email (~1M/day)

**Provider:** SendGrid Pro (~$500/month at 1M/day). We considered AWS SES ($0.10/1K = significantly cheaper) but SendGrid's suppression list management, webhook reliability, and deliverability tooling reduce operational burden for a team of 4.

**Email types:**

| Type | Trigger | Frequency Cap |
|------|---------|---------------|
| Transactional | Immediate (password reset, account alert) | No cap |
| Activity digest | Daily or weekly batch | User-controlled |
| Re-engagement | 7-day inactivity | Max 1/week |
| Marketing | Product announcements | Max 1/week |

**Template system:** SendGrid Dynamic Templates with Handlebars, versioned in Git, deployed via SendGrid API in CI/CD.

#### Digest Batching Logic — Carry-Forward Fixed

**Fix for Criticism #6:** The original `carry_forward_to_next_digest` function was undefined. More importantly, there was no cap on accumulation — a user generating 1–2 events/day could have notifications silently held for weeks with no delivery. This is both a product problem (users miss notifications) and potentially a compliance problem (users don't know what's being held).

```python
MAX_CARRY_FORWARD_DAYS = 3
MAX_CARRY_FORWARD_EVENTS = 20  # deliver regardless of threshold if exceeded

def build_daily_digest(user_id: str, date: date) -> DigestEmail | None:
    # Fetch today's events plus any carried-forward events
    todays_events = fetch_unbatched_events(user_id, date)
    carried_events = fetch_carried_events(user_id)
    
    # Discard carried events older than MAX_CARRY_FORWARD_DAYS
    # These are stale enough that delivering them would be confusing
    cutoff = datetime.utcnow() - timedelta(days=MAX_CARRY_FORWARD_DAYS)
    carried_events = [e for e in carried_events if e.created_at > cutoff]
    if len(carried_events) != len(fetch_carried_events(user_id)):
        metrics.increment("digest.events.discarded_stale")
    
    all_events = carried_events + todays_events
    
    if len(all_events) == 0:
        return None
    
    grouped = group_by_entity_and_type(all_events)
    
    # Send if: enough items, OR accumulated for too long, OR too many events
    oldest_event_age_days = (datetime.utcnow