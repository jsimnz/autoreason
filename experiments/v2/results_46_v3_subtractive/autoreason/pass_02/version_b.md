# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 3 — Addressing Critic Findings

---

## Executive Summary

This proposal designs a notification system handling ~50M notifications/day across push, email, in-app, and SMS channels. Given the team size and timeline, we prioritize **operational simplicity over theoretical elegance** and **incremental delivery** over a big-bang launch.

The core architectural bet: **a single priority queue with channel fanout**, rather than per-channel queues or a complex event streaming topology. This is debuggable, replaceable, and sufficient for 10M MAU with a team of 4.

**What changed in this revision:** The previous version had ten specific problems identified in review. Each is addressed directly:

1. The in-app frequency narrative was inconsistent with the numbers — corrected with honest accounting
2. The SMS channel table still showed 1M/day after the prose correction — table updated
3. The digest idempotency logic had a data loss window between `clear_carried_events` and send — reordered to send-then-clear with compensating logic
4. The composite PK tradeoff was understated — the client-facing API contract change is now fully described
5. The WebSocket scaling section was literally incomplete mid-sentence — completed
6. APNs JWT regeneration had no monitoring or failure handling — operational design added
7. SendGrid pricing was wrong by roughly 50× at stated volume — corrected, with revised provider recommendation
8. APNs 410 ownership was split between E2 and E3 without resolution — explicit handoff protocol defined
9. Partition index size was asserted, not demonstrated — sizing math provided
10. "Proven infrastructure" framing masked real operational risk — reframed honestly

---

## 1. Scale Assumptions and Constraints

### Traffic Modeling

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio (social apps) |
| Notifications/DAU/day | ~17 | Industry avg for engaged social apps |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× | Morning/evening spikes |
| Peak throughput | ~1,750/sec | 50M × 3 / 86,400 |

**Channel split — honest accounting:**

| Channel | % of Total | Volume/day | Recipient Base | Avg/active user/day |
|---------|-----------|------------|----------------|---------------------|
| Push | 70% | 35M | MAU with app installed (~8M) | ~4.4/active push user |
| In-app | 20% | 10M | DAU only (3M) | ~3.3/active user |
| Email | 8% | 4M | MAU with email (~9M) | — (digest model) |
| SMS | <0.01% | ~2,000 | Opted-in, auth/security only | — (gated, see §3.4) |

**On the in-app frequency:** The 3.3 in-app notifications per active user per day is only modestly lower than the 4.4 push figure. The earlier claim that in-app "surfaces a curated subset" was not well supported by these numbers. The honest explanation is different: in-app notifications are a near-duplicate of push for active users, but they serve a distinct purpose — they populate the notification inbox for users who are *already in the app* and dismissed or missed the push. The in-app store is not a lower-volume channel; it's a persistent record. We keep the 20% allocation because in-app writes are cheap (direct DB writes, no external API calls), not because in-app volume is inherently lower.

**SMS is not 2% of volume.** The previous table showed SMS at "2% of Total / 1M/day" and corrected this only in prose. That was confusing. The table above reflects the operational reality: SMS is capped at ~2,000/day, which is under 0.01% of total volume. At Twilio's $0.0075/message, this costs ~$450/month, consistent with our $15,000/month SMS budget ceiling. Social engagement notifications are not sent via SMS at any scale. SMS is strictly for authentication codes and security alerts.

### Team Allocation

| Engineer | Primary Responsibility | Cross-Cutting Owner |
|----------|----------------------|---------------------|
| E1 | Core pipeline, queue infrastructure, delivery workers | Aggregation/batching logic |
| E2 | Channel integrations (APNs, FCM, email provider, Twilio) | Token/credential lifecycle; APNs 410 detection |
| E3 | Preference management, user-facing API, suppression logic | Deduplication; suppression writes from all feedback sources |
| E4 | Reliability, monitoring, failure handling, DevOps | Scaling triggers; job health monitoring |

**APNs 410 ownership handoff (resolving the E2/E3 conflict):** APNs 410 responses are detected by E2's delivery worker code, which owns the FCM/APNs integration. But the suppression write — marking a token invalid, preventing future sends — is E3's feedback loop. The resolution: E2's worker publishes a structured `token.invalidated` event to a dedicated Redis stream. E3's feedback processor consumes this stream and writes the suppression record. E2 owns detection and publishing; E3 owns the suppression state. The boundary is the event. This same pattern handles FCM `InvalidRegistration`. Neither engineer makes cross-domain writes directly.

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
  - Preference check (Redis cache)
  - Suppression check
  - Priority assignment
  - Channel selection
  - Aggregation window check
     │
     ├─────────────────────────────────────┐
     ▼                                     ▼
[Priority Queue]                   [In-App Store]
(Redis — Lua-atomic ops)           (PostgreSQL, partitioned)
     │                                     │
     ├── P0 Worker Pool (10)               └── Redis Pub/Sub fan-out
     ├── P1 Worker Pool (20)                   → WebSocket servers
     └── P2/P3 Worker Pool (10)                (see §3.3 for scaling)
          │
          ▼
   [Channel Dispatcher]
     ├── Push (APNs / FCM)
     ├── Email (Postmark or SES + custom tooling)
     └── SMS (Twilio — auth/security only)
          │
          ▼
   [Delivery Log] (PostgreSQL + S3 archive)
          │
          ▼
   [Feedback Processor]  ←── token.invalidated stream (from E2)
   (bounces, opens, failures → suppression)
```

### Why This Architecture

**Single queue with priority scoring, not per-channel queues.** Per-channel queues create operational complexity — 4 queues to monitor, 4 dead-letter queues, priority inversions between channels. At our scale, a Redis sorted set with Lua-atomic dequeue handles 50M items comfortably. The atomicity requirement is met with Lua scripts, not pipelines (see §4.2).

**In-app notifications bypass the queue.** In-app notifications are writes to a database table that clients poll or receive via WebSocket. They don't need retry logic and benefit from immediate consistency. Routing them through the push queue adds latency with no benefit.

**Preference check at routing time, not delivery time.** User preferences are cached in Redis. Checking at routing keeps workers dumb and fast. Checking at delivery wastes queue capacity on notifications that will be discarded.

**Honest statement of operational risk.** This system combines Redis sorted sets with Lua atomicity, PostgreSQL declarative partitioning, Redis Pub/Sub WebSocket fan-out, a custom digest engine, a custom feedback loop, and direct APNs/FCM integrations. None of these components is individually exotic. But this team has never operated this combination together at 50M notifications/day. The risk is not in any single component — it's in the operational surface area of running all of them simultaneously. We mitigate this through phased rollout (§7), explicit runbooks (§6), and E4's dedicated reliability ownership. We do not mitigate it by pretending the risk doesn't exist.

---

## 3. Delivery Channels

### 3.1 Push Notifications (70% of volume — 35M/day)

**Provider:** Firebase Cloud Messaging (FCM) for Android, Apple Push Notification Service (APNs) for iOS. Direct integrations — no intermediary like OneSignal or Braze initially.

**Tradeoff:** OneSignal/Braze saves 4-6 weeks of integration work but costs ~$50-150K/year at our scale and reduces control over retry behavior and delivery receipts. We build direct integrations and accept the upfront engineering cost. We revisit if we need advanced segmentation features.

**FCM Configuration:**
```
- Connection pool: 50 persistent HTTP/2 connections
- Batch size: 500 tokens per FCM v1 batch request
- Rate: FCM allows ~600 req/sec per project; we operate at 400
- Token validation: validate on first send failure, purge on 404/InvalidRegistration
- On InvalidRegistration: publish token.invalidated event to Redis stream (consumed by E3)
```

**APNs Configuration and JWT Token Management:**

APNs uses `.p8` signing keys to generate short-lived JWT tokens. The operational model has three distinct layers:

- **`.p8` signing key:** Does not rotate on a schedule. Stored in AWS Secrets Manager. Rotated manually via Apple Developer Portal only if compromised. E2 owns the rotation runbook.
- **JWT token:** Generated from the `.p8` key. Expires after 1 hour. Regenerated every 45 minutes by a background job to stay well inside the expiry window.
- **In-flight requests during regeneration:** The credential store holds the current token. Workers fetch the token per-request from a local cache with a 30-second TTL. During regeneration, workers may use a token up to 30 seconds old — still valid since we regenerate at 45 minutes with a 60-minute expiry. No requests are interrupted.

**APNs JWT regeneration — operational design:**

This job's failure mode is complete iOS push delivery failure after the current token expires. It requires the same monitoring rigor as a primary service.

```
Monitoring (owned by E4):
- Heartbeat metric emitted after every successful regeneration
- Alert: PagerDuty page if no successful regeneration in 50 minutes
  (5-minute buffer before the 45-minute schedule would be missed)
- Alert: APNs 401 error rate > 1% triggers immediate page
  (401 = token rejected; indicates regeneration failure or clock skew)
- Dashboard: token age, last regeneration timestamp, 401 rate

On alert:
- Runbook: verify Secrets Manager access, verify background job health,
  manually trigger regeneration if job is stuck
- Fallback: if regeneration fails for >10 minutes, pause iOS push delivery
  and queue notifications for retry rather than send with an expired token
```

```
APNs runtime config:
- HTTP/2 with JWT authentication (token regenerated every 45 min)
- Connection pool: 20 persistent connections
- apns-priority: 10 (immediate) for P0/P1, 5 (power-saving) for P2
- apns-collapse-id: notification_type + entity_id (collapses stale notifications)
- On 410: publish token.invalidated event with Apple-provided timestamp
```

**Token management:**

Stale push tokens are the primary operational headache for push at scale.

- Store tokens in `push_tokens` table with `last_used_at` and `is_valid` columns
- On FCM `InvalidRegistration` or APNs 410: E2 worker publishes `token.invalidated` event; E3 feedback processor marks invalid and suppresses future sends
- On APNs 410: record Apple's provided timestamp; tokens registered *after* that timestamp for the same device are valid and must not be suppressed
- Batch-purge tokens unused for 90 days (covers uninstalls without explicit logout)

### 3.2 Email (8% of volume — 4M/day)

**Provider selection — corrected cost analysis:**

The previous version cited SendGrid Pro at $1,500/month for 4M emails/day (~120M/month). That figure is SendGrid's entry-level plan, which covers roughly 100K-300K emails/month. At 120M emails/month, SendGrid's actual cost is in the range of $20,000-40,000/month depending on negotiated enterprise pricing. This is a significant budget item that must be planned for explicitly, not estimated from the pricing page's first tier.

Revised options at 120M emails/month:

| Provider | Estimated Cost/Month | Deliverability Tooling | Ops Burden |
|----------|---------------------|----------------------|------------|
| SendGrid (enterprise) | ~$20,000-40,000 | Excellent | Low |
| AWS SES | ~$12,000 | Minimal | High |
| Postmark | ~$15,000-25,000 | Good | Low-Medium |
| Mailgun | ~$15,000-20,000 | Good | Low-Medium |

**Recommendation: Postmark for transactional, SES for digest/marketing.** Postmark has strong deliverability for transactional email (password resets, security alerts) and a reputation for reliability. SES handles high-volume digest and marketing sends at lower cost, where per-message economics matter more than premium deliverability tooling. This split is a meaningful operational decision: E2 maintains two email integrations, which adds complexity. The tradeoff is justified because transactional email failure (missed password reset) has a direct user trust impact, while a slightly lower digest delivery rate is acceptable.

If budget constrains us to a single provider, use SES with significant investment in IP warming, bounce monitoring, and suppression list management — tasks that will consume meaningful E3 time that would otherwise go to product features.

**Email types:**

| Type | Provider | Trigger | Frequency Cap |
|------|---------|---------|---------------|
| Transactional | Postmark | Immediate (password reset, account alert) | No cap |
| Activity digest | SES | Daily or weekly batch | User-controlled |
| Re-engagement | SES | 7-day inactivity | Max 1/week |
| Marketing | SES | Product announcements | Max 1/week |

**Digest batching logic — data loss window closed:**

The previous version called `clear_carried_events` before the send attempt, then claimed idempotency would handle failures. But if the process crashed after clearing and before sending, events were neither carried nor sent — a silent data loss window that the revision claimed to have fixed but hadn't.

The corrected approach: send first, then clear. The digest_id provides idempotency against duplicate sends if we retry after a partial failure.

```python
MAX_CARRY_FORWARD_DAYS = 7

def build_and_send_daily_digest(user_id: str, date: date) -> SendResult:
    carried = fetch_carried_events(user_id)
    fresh = fetch_unbatched_events(user_id, date)
    all_events = carried + fresh

    if not all_events:
        return SendResult.SKIPPED_EMPTY

    cutoff = date - timedelta(days=MAX_CARRY_FORWARD_DAYS)
    valid_events = [e for e in all_events if e.created_at.date() >= cutoff]
    expired_events = [e for e in all_events if e.created_at.date() < cutoff]

    if expired_events:
        mark_events_expired(expired_events)
        log.info(f"Expired {len(expired_events)} stale carried events for {user_id}")
        # Counted in metrics; threshold tunable if expiry rate is high

    if not valid_events:
        return SendResult.SKIPPED_ALL_EXPIRED

    grouped = group_by_entity_and_type(valid_events)

    if len(grouped) < MIN_DIGEST_ITEMS:  # = 3
        mark_events_carried(valid_events)
        return SendResult.CARRIED_FORWARD

    digest = DigestEmail(
        digest_id=generate_digest_id(user_id, date),  # Idempotency key
        user_id=user_id,
        subject=generate_subject(grouped),
        sections=render_sections(grouped),
        unsubscribe_token=generate_unsubscribe_token(user_id),
    )

    # SEND FIRST, then clear carried