# Notification System Design Proposal — Version 3
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses ten specific findings from the previous review. Each finding was valid. The changes fall into four categories: architectural corrections (SQS FIFO throughput limits, partition strategy), legal/compliance acknowledgments that were incorrectly framed as engineering tradeoffs (preference cache TTL, SMS cost ceiling), implementation bugs (APNs token manager race condition, collapse ID behavior), and structural gaps in ownership and process (feedback processor SLA, test harness ownership, IP warming schedule, SMS cap incident path).

Where a correction introduces a new tradeoff, that tradeoff is stated explicitly. Where a finding requires a decision from someone outside the engineering team, this document identifies that decision point rather than resolving it unilaterally.

---

## 1. Scale Assumptions and Constraints

*Volume model unchanged from V2. Reproduced here for completeness.*

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| Push opt-in rate | 60% | ~6M users |
| Email opt-in rate | 75% | ~7.5M users |
| SMS opt-in rate | 15% | ~1.5M users |
| Avg notifications/opted-in user/day | ~15 | Industry range 10–20 |
| **Total push/day** | **~90M** | 6M × 15 |
| **Total email/day** | **~4M** | Digest/batch model |
| **Total in-app/day** | **~30M** | ~3M DAU × 10 |
| **Total SMS/day (capped)** | **~150K** | Hard-gated; see Section 3.4 |
| **Total notifications/day** | **~125M** | Central estimate |
| Peak multiplier | 3× | Morning/evening spikes |
| Peak throughput | **~4,300/sec** | 125M × 3 / 86,400 |

### 1.1 SMS Cost — Corrected to Include OTP Exemption

The previous version presented $430K/year as the SMS cost ceiling. This was wrong because the 150K/day cap exempts OTP and security SMS, and that exemption volume was uncosted.

OTP exposure at scale:

| Scenario | OTP Volume | Daily SMS Cost |
|----------|-----------|----------------|
| Baseline (2FA logins, ~5% of DAU) | ~150K/day | ~$1,185 |
| Credential stuffing attack (forced re-auth, 20% of MAU) | ~2M/day | ~$15,800 |
| Major security incident (forced re-auth, all MAU) | ~10M/day | ~$79,000 |

The $430K/year figure covers only capped marketing/engagement SMS. The actual SMS cost ceiling is undefined because OTP volume is incident-dependent.

**Decision required from Finance and Security leadership before launch:** Establish a monthly OTP SMS budget with a hard ceiling and a defined response when that ceiling is approached (e.g., fall back to email-based OTP, disable new 2FA enrollments temporarily). Engineering will implement whatever ceiling and fallback is authorized, but we cannot set this number — it is a business risk decision, not an engineering one.

**What engineering will implement regardless:** OTP SMS is metered separately in the dashboard. A CloudWatch alarm fires when OTP SMS spend exceeds $5,000/day. The on-call engineer is notified; the response procedure is documented in the runbook. We do not silently absorb a $79,000/day event.

### 1.2 Team Allocation

*Unchanged from V2 except for test harness ownership, addressed in Section 7.*

---

## 2. System Architecture

### 2.1 Queue Backend — SQS FIFO Throughput Correction

The previous version assigned P0 and P1 traffic to SQS FIFO queues. This was incompatible with our scale.

**The problem:** SQS FIFO queues are limited to 3,000 messages/second with batching enabled, or 300/second without. P1 traffic alone (direct messages, mentions) during a 3× peak event would approach or exceed this limit. When a FIFO queue is saturated, messages queue behind the limit — there is no overflow path. P1 notifications would back up silently, which is the failure the priority system exists to prevent.

**Revised queue design:**

```
notif-p0-standard   — Critical (OTP, security alerts)
notif-p1-standard   — High (DMs, mentions)
notif-p2-standard   — Normal (likes, follows, comments)
notif-p3-standard   — Batch (digests, re-engagement)
```

All four queues are now SQS standard queues. This removes the FIFO throughput ceiling — standard queues support effectively unlimited throughput. The cost is that we lose the ordering and exactly-once guarantees FIFO provided.

**What we lose and how we compensate:**

*Ordering:* For OTPs, strict ordering matters less than delivery speed. A user requesting two OTPs in quick succession should receive both; the second supersedes the first regardless of delivery order. We handle this at the application layer: OTP tokens have short TTLs (5 minutes) and are validated against the most recently issued token for that user, not by arrival order.

For DMs, users on mobile expect near-real-time delivery, not ordered delivery. If two messages arrive out of order on the device, the client sorts by server timestamp before display. This is already standard practice for chat systems.

*Exactly-once:* Standard queues provide at-least-once delivery. Duplicate delivery is possible. We handle this with idempotency keys:

```python
class NotificationDispatcher:
    def dispatch(self, message: SQSMessage) -> None:
        notification_id = message.body["notification_id"]
        
        # Idempotency check: has this notification_id already been sent?
        # Uses Redis SET NX with TTL matching our deduplication window
        lock_key = f"sent:{notification_id}"
        acquired = self.redis.set(lock_key, "1", nx=True, ex=86400)
        
        if not acquired:
            # Already dispatched — delete from queue, do not resend
            message.delete()
            self.metrics.increment("dispatch.duplicate_suppressed",
                                   tags={"priority": message.body["priority"]})
            return
        
        try:
            self._send_to_channel(message.body)
            message.delete()
        except Exception as e:
            # Do not delete — SQS visibility timeout will make it reappear
            # Redis key remains set, so if another worker picks it up,
            # it will also be suppressed. We clear the key on confirmed failure
            # after max retries so the DLQ processor can retry cleanly.
            if self._is_max_retries_exceeded(message):
                self.redis.delete(lock_key)
                # Message will go to DLQ on next visibility timeout expiry
            raise
```

**Tradeoff we're accepting:** Duplicate suppression via Redis is best-effort. If Redis is unavailable, we fall back to no suppression — a user might receive a duplicate notification. For P0 (OTPs), this is acceptable because OTP tokens are single-use regardless of delivery count. For P1/P2, a duplicate like or mention notification is a UX annoyance, not a correctness failure. We explicitly accept this tradeoff and document it.

**Worker allocation (unchanged counts, now all polling standard queues):**

```
P0: 15 workers — exclusive poll of notif-p0-standard
P1: 25 workers — exclusive poll of notif-p1-standard  
P2: 20 workers — exclusive poll of notif-p2-standard
P3: 5 workers  — exclusive poll of notif-p3-standard
```

Standard queue throughput at 65 workers polling with 10-message batches: ~32,500 messages/poll cycle, well above our 4,300/sec peak.

---

## 3. Delivery Channels

### 3.1 Push Notifications — APNs Token Manager Race Condition

The previous version's `APNsTokenManager` used `threading.Lock()` and claimed this prevented concurrent token regeneration. The review correctly identified two problems: the "proactive refresh" check in worker code happened outside the lock, and the lock provides no protection across processes or nodes.

**Root cause:** Thread locks are intra-process. With 15 P0 workers potentially running as separate processes on separate nodes, each process has its own `APNsTokenManager` instance with its own lock. Concurrent token regeneration across nodes is not prevented by anything in the previous design.

**Revised approach: centralize token management in Redis.**

The JWT token is not sensitive in the same way the signing key is — it is a short-lived credential derived from the signing key. We can store it in Redis and use Redis's atomic operations to ensure only one process regenerates it at a time.

```python
class APNsTokenManager:
    TOKEN_KEY = "apns:jwt_token"
    TOKEN_GENERATED_AT_KEY = "apns:jwt_generated_at"
    REGENERATION_LOCK_KEY = "apns:regen_lock"
    TOKEN_LIFETIME_SECONDS = 3000       # 50 minutes; Apple expires at 60
    LOCK_TTL_SECONDS = 10               # Max time we hold the regen lock
    
    def __init__(self, key_id: str, team_id: str, secrets_client):
        self.key_id = key_id
        self.team_id = team_id
        self.secrets_client = secrets_client  # AWS Secrets Manager client
        self._redis = get_redis_client()

    def get_token(self) -> str:
        token = self._redis.get(self.TOKEN_KEY)
        if token:
            return token.decode()
        return self._regenerate_token()

    def _regenerate_token(self) -> str:
        # Distributed lock: only one process/node regenerates at a time
        lock = self._redis.set(
            self.REGENERATION_LOCK_KEY, "1",
            nx=True, ex=self.LOCK_TTL_SECONDS
        )
        
        if not lock:
            # Another process is regenerating — wait briefly and retry
            time.sleep(0.1)
            token = self._redis.get(self.TOKEN_KEY)
            if token:
                return token.decode()
            # If still not available after wait, regenerate anyway
            # (the lock holder may have crashed within its TTL)
            
        private_key = self.secrets_client.get_secret_value(
            SecretId="apns/signing-key"
        )["SecretString"]
        
        payload = {
            "iss": self.team_id,
            "iat": int(time.time()),
        }
        new_token = jwt.encode(
            payload, private_key, algorithm="ES256",
            headers={"kid": self.key_id}
        )
        
        # Store with TTL slightly shorter than Apple's expiry window
        self._redis.setex(self.TOKEN_KEY, self.TOKEN_LIFETIME_SECONDS, new_token)
        self._redis.delete(self.REGENERATION_LOCK_KEY)
        return new_token
```

**What this buys us:** Token generation is now coordinated across all worker nodes. When a token expires, exactly one node regenerates it; all others wait on the Redis key. The lock TTL of 10 seconds ensures that if the regenerating node crashes, another node will take over within 10 seconds rather than blocking indefinitely.

**What this does not solve:** If Redis itself is unavailable, `get_token()` will fail for all workers simultaneously. We handle this with a local in-process fallback: each worker caches the last known good token in memory with its generation timestamp. If Redis is unreachable, workers use the cached token until it expires, then log an error and pause sends. We do not attempt to regenerate tokens without Redis coordination — the risk of thundering herd against the APNs endpoint is worse than a brief send pause.

**Signing key storage:** The `.p8` file lives in AWS Secrets Manager. It is never written to disk. Key rotation (when required by security policy, not on a timer) requires a deployment step — updating the secret and restarting workers to pick up the new key_id. This is a deliberate operational step, not an automated one.

### 3.2 APNs Collapse ID — Corrected Behavior

The previous version set Collapse ID to `{notification_type}:{entity_id}`. The review correctly identified that this silently drops notifications when multiple users interact with the same entity.

**The specific failure:** Two users comment on post `abc123`. Both generate a push notification with Collapse ID `comment:abc123`. The second notification replaces the first on the recipient's device. The recipient never sees that the first comment happened.

This is a product decision, not an infrastructure decision. The infrastructure document should not be making it implicitly.

**Options, with their tradeoffs:**

| Collapse ID Scheme | Behavior | Tradeoff |
|---|---|---|
| `{type}:{entity_id}` (previous) | Latest notification per entity wins | Silent drops on popular content |
| `{type}:{entity_id}:{actor_id}` | One notification per actor per entity | No collapsing for same-actor repeat actions |
| `{type}:{entity_id}:{hour}` | Collapse within hourly window | Balances freshness with notification count |
| No Collapse ID | All notifications delivered | Device notification tray floods on viral content |
| `{type}:{entity_id}:{recipient_id}` | No collapsing (recipient is always unique) | Effectively no Collapse ID |

**Our recommendation:** `{notification_type}:{entity_id}:{recipient_id}` for all non-digest notifications. This is functionally equivalent to no Collapse ID for individual notifications — each recipient gets their own collapse namespace — while preserving the ability to collapse if the same user generates the same action twice (which APNs handles via the recipient-scoped key). For digest-style summaries, use `digest:{recipient_id}:{date}` so the latest digest always supersedes the previous one.

**Decision required from Product before launch:** The collapse behavior for high-engagement scenarios (popular posts with many comments) is a product decision. The engineering default is "deliver all notifications" — this maximizes engagement signal but increases notification fatigue on viral content. Product should review this before launch and specify the desired behavior. Engineering will implement whatever is decided; the Collapse ID scheme is a one-line configuration change per notification type.

### 3.3 Email — IP Warming Schedule Corrected

The previous version stated to warm transactional IPs first and begin marketing sends in week 3, while simultaneously projecting 4M emails/day from day one. These are incompatible.

**The problem:** ISPs (Gmail, Yahoo, Outlook) apply reputation scoring to sending IPs. A cold IP sending millions of messages immediately will be throttled or blocked, defeating the purpose of the email channel. The warming schedule needed for 4M/day transactional volume is not a matter of weeks — it is 6–8 weeks of graduated volume increases.

**Revised email ramp schedule:**

| Week | Transactional Volume | Marketing/Digest Volume | Notes |
|------|---------------------|------------------------|-------|
| 1 | 50K/day | 0 | Seed list only; monitor bounce/spam rates |
| 2 | 200K/day | 0 | Expand to engaged users (opened in last 30 days) |
| 3 | 500K/day | 0 | Continue transactional ramp |
| 4 | 1M/day | 50K/day | Begin marketing on separate warmed IP pool |
| 5 | 2M/day | 200K/day | |
| 6 | 3M/day | 500K/day | |
| 7 | 4M/day | 1M/day | Full transactional volume |
| 8+ | 4M/day | Up to 4M/day total | Marketing scales with transactional reputation |

**What this means for launch:** Full email volume is not available at launch. For the first 6 weeks, email notifications are rate-limited by the warming schedule, not by our infrastructure. Notifications that cannot be sent immediately are either queued (for time-sensitive transactional email) or dropped (for engagement digests — a user missing one week of digest email is not a correctness failure).

**SendGrid's role:** SendGrid manages IP reputation scoring and will flag if our sending patterns are creating deliverability problems. We configure SendGrid's Event Webhook to feed bounce and spam complaint data into our feedback processor. If the transactional bounce rate exceeds 2% or spam complaint rate exceeds 0.1% at any point