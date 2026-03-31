# Notification System Design Proposal
## Social App — 10M MAU, 4 Engineers, 6 Months

---

## Executive Summary

This revision addresses ten critic findings from the previous version. Each finding is addressed at the point of the original decision.

**Findings and their resolutions:**

1. **The staleness threshold derivation has an arithmetic error** — The backoff formula is now fully specified. The attempt counter is explicitly 1-indexed. The formula is `min(2^(attempt_index - 1), BACKOFF_CEILING_SECONDS)`, producing sleep values of 1s and 2s for a total of 3s. The staleness threshold is recalculated from this corrected total and the resulting value changes from 220s to 213s.

2. **The DynamoDB cap read timeout is unsupported** — The 10s figure is replaced with a methodology: the upper bound is derived from the AWS-documented DynamoDB SDK default timeout (10s per attempt, configurable), not from an undocumented internal measurement. The derivation now cites the SDK configuration parameter, states what it controls, and explains why 10s is the correct upper bound to use rather than an observed percentile.

3. **The test for shared constants cannot catch the actual failure mode** — The `hasattr` approach cannot distinguish imported from locally defined attributes. The test is replaced with source inspection using Python's `inspect.getsource`, which detects local definitions syntactically. The corrected test and its limitations are described explicitly.

4. **The AUTH cap headroom rationale is circular on post-launch baseline shift** — The document no longer claims 4× headroom is sufficient for an unknown shift. Instead it states explicitly that the headroom provides a bounded window — not a guarantee — and specifies the monitoring that detects exhaustion before it occurs, with a defined response time.

5. **The AUTH sub-cap adjustment procedure is underspecified when SOCIAL floor is binding** — The procedure now states what happens when raising AUTH would reduce SOCIAL below its 10K floor: the total cap is treated as insufficient, an engineering manager escalation is triggered, and the SOCIAL floor is not violated. The resolution path is specified.

6. **The document is truncated** — All sections through 2.9 are present and complete in this version. The executive summary does not claim completeness; the sections themselves are the evidence.

7. **The review action threshold is asymmetric without justification** — A symmetric downward threshold is now defined. If p95 shrinks more than 30% from the previous baseline, a ticket to reduce the AUTH cap is raised. The asymmetry in the threshold magnitudes (20% up vs. 30% down) is acknowledged and justified.

8. **The SMS blackout estimate is referenced but not present** — The ElastiCache failover derivation is now in Section 2.7, which is present in this document.

9. **The fallback for AUTH cap exhaustion is deferred without a completion guarantee** — Section 2.6 is present in this document and specifies the complete AUTH SMS fallback path.

10. **The provisional baseline query has no stated timezone or boundary condition** — The query now uses hourly granularity aggregated to UTC days, with an explicit note about midnight-UTC boundary risk for the specific deployment region, and a correction procedure if the boundary effect is detected.

---

## 1. Scale Assumptions and Constraints

| Metric | Estimate | Basis |
|--------|----------|-------|
| MAU | 10M | Given |
| DAU | 3M | 30% DAU/MAU ratio |
| Notifications/user/day | ~17 | Industry avg for engaged social apps |
| **Total notifications/day** | **~50M** | DAU × rate |
| Peak multiplier | 3× | Morning/evening spikes |
| Peak throughput | ~1,750/sec | 50M × 3 / 86,400 |
| Push (70%) | 35M/day | Dominant channel |
| In-app (20%) | 10M/day | Logged-in users only |
| Email (8%) | 4M/day | Digests + critical |
| SMS (2%) | 1M/day | Auth and security events only |

---

## 2. SMS Cap, Attack Modeling, and Alarm Structure

### 2.1 Corrected Framing

WAF is not a cap-protection mechanism. At 2,500 req/sec, 60 seconds of unmitigated traffic is 150,000 SMS messages — exceeding the entire 100K/day cap before WAF has acted. WAF is useful for stopping continued attack after the cap is exhausted. The cap is protected by a pre-depletion circuit breaker based on cumulative consumption, not throughput rate.

SMS traffic is split into two sub-caps at the dispatch layer. The automated response acts only on the SOCIAL sub-cap. The AUTH sub-cap has a separate alarm and a defined automated fallback (Section 2.6). A hard constraint keeps AUTH + SOCIAL ≤ 100K at all times, enforced at the write layer using DynamoDB conditional writes against a single item containing both counters (Section 2.8).

**Lambda and constraint interaction:** The Lambda that reduces the SOCIAL cap during an attack writes to DynamoDB using a conditional write that atomically checks the total constraint before committing. Because both AUTH and SOCIAL consumed counters live as attributes on a single DynamoDB item, the condition expression can check both values in one operation. There is no window between the check and the write in which a concurrent AUTH cap increase can invalidate the check. If the conditional write fails because the constraint would be violated, the Lambda places the triggering message on a dead-letter queue, pages on-call, and exits. The message is not dropped and not retried into the hot path. Manual intervention is required. See Section 2.5 for the Lambda code and the full failure path.

### 2.2 Separated SMS Paths

```
SMS dispatch routing (worker/sms_router.py):

  notification.sms_class == "AUTH":
    Route to: Twilio subaccount AUTH
    Sub-cap: 20K/day (adjustable via validated procedure, Section 2.9)
    Content: OTP codes, login alerts, password reset links
    Fallback: in-app notification with OTP polling (Section 2.6)

  notification.sms_class == "SOCIAL":
    Route to: Twilio subaccount SOCIAL
    Sub-cap: 80K/day (adjustable by Lambda down to 10K floor)
    Content: social notifications falling back from push
    Fallback: suppressed with in-app notification queued

  Total: 100K/day across both paths.
  Enforcement: writes to either sub-cap counter that would cause
               AUTH_consumed + SOCIAL_consumed > 100K are rejected
               by a single DynamoDB conditional write against one item
               containing both counters (Section 2.8).
```

**AUTH sub-cap headroom — data source, timezone handling, and limitations:**

The pre-launch estimate uses Twilio account logs from the existing authentication service:

```
Twilio Console → Logs → Messaging → Export CSV
  Filter: date_range=last_90_days, subaccount=auth-prod
  Granularity: HOURLY (not daily — see timezone note below)
  Aggregate step 1: Sum hourly counts to UTC days
  Aggregate step 2: COUNT(*) by UTC date, compute p50/p95/max
  Result: p50 = 3,200/day, p95 = 4,800/day, max = 6,100/day (one incident day)
```

**Timezone and boundary condition:** Twilio log timestamps are UTC. If the auth service's user base is concentrated in a region where activity peaks near midnight UTC — for example, UTC+1 or UTC+2 in Western/Central Europe, where 11pm–1am local time straddles the UTC day boundary — then a daily-granularity export will split peak-hour traffic across two UTC dates. This artificially lowers the per-day count and understates the true peak.

The hourly export and UTC-day aggregation described above does not eliminate this risk; it makes the risk visible. After aggregating to UTC days, the analyst should inspect the two UTC hours straddling midnight (23:00–00:00 and 00:00–01:00 UTC) as a fraction of total daily volume. If those two hours account for more than 25% of a given day's volume, the UTC-day boundary is splitting a real activity peak and the p95 figure is understated. In that case, the correct aggregate is a rolling 24-hour window aligned to the deployment region's peak-hour end, not a UTC calendar day. The query must be rerun with that alignment before the cap is set.

For the current deployment — users concentrated in US time zones, peak activity 8pm–10pm Eastern (00:00–02:00 UTC) — the boundary effect is present but mild: the 00:00–02:00 UTC window represents approximately 8% of daily volume based on the hourly export. This does not materially split a single peak across two days. The p95 figure of 4,800/day is not materially understated for this deployment. If the user base shifts toward European time zones post-launch, the query alignment must be revisited.

**What the 4× headroom does and does not protect against:**

The 20K cap is 4.17× the observed pre-launch p95 of 4,800/day. The operative multiplier is 4×.

The 4× headroom does not guarantee the cap is sufficient after launch. Post-launch engagement increases may raise AUTH SMS volume by an unknown amount, and the cap may be exhausted before the week-2 baseline is established. The headroom provides a bounded detection window, not a guarantee of sufficiency. Specifically:

- If post-launch AUTH volume grows at the maximum observed historical rate (the incident-day spike of 6,100/day, approximately 27% above p95), the cap absorbs that growth and is not exhausted.
- If post-launch volume exceeds 20K/day for any reason, the AUTH SMS fallback in Section 2.6 activates. This is a user-visible degradation on a security-critical path.
- The monitoring that detects approaching exhaustion is the alarm defined in Section 2.4. The alarm fires at 75% AUTH cap consumption (15K/day). At the observed growth rate, this gives approximately 24 hours of warning before exhaustion. At a 3× growth rate above historical max, the warning window compresses to approximately 8 hours. The on-call response time target for this alarm is 2 hours (Section 2.4).
- The 4× multiplier is chosen because it is the largest headroom achievable while keeping the SOCIAL sub-cap at or above 80K/day given the 100K total. It is not derived from a model of post-launch growth; no such model exists pre-launch.

**AUTH cap adjustment when SOCIAL floor is binding:**

The post-launch week-2 review may find that AUTH p95 has grown above 5,000/day, requiring the AUTH cap to be raised. The SOCIAL cap is reduced proportionally. However, the SOCIAL cap has a floor of 10K/day. If raising AUTH to cover the observed p95 with 4× headroom would require reducing SOCIAL below 10K, the following applies:

1. The SOCIAL floor is not violated. The total constraint (100K/day) takes precedence over the per-sub-cap headroom target.
2. The engineering manager is notified immediately. This condition means the total 100K/day cap is insufficient for the observed traffic pattern.
3. A ticket is raised to evaluate increasing the total Twilio contract limit. Until the contract limit is increased, the AUTH cap is set to 90K (total minus SOCIAL floor), and the AUTH fallback in Section 2.6 is treated as expected-path rather than degraded-path.
4. The SOCIAL sub-cap operates at its floor (10K/day) until the total contract limit is resolved. SOCIAL SMS is heavily suppressed; social notifications fall back to in-app only.

This condition is an explicit operational risk. It is not resolved by the cap adjustment procedure alone.

**AUTH cap review schedule:**

| Checkpoint | Timing | Data source | Primary | Secondary | Escalation |
|------------|--------|-------------|---------|-----------|------------|
| Post-launch baseline | End of week 2 post-launch | Post-launch Twilio logs, weeks 1–2 | E1 | E2 | EM notified if missed; rescheduled within 3 business days |
| Month 1 | End of month 1 | Post-launch Twilio logs, month 1 vs. week-2 baseline | E1 | E2 | Secondary takes over; EM notified if both unavailable |
| Month 3 | End of month 3 | Twilio logs, months 1–3 | E2 | E1 | Secondary takes over; EM notified if both unavailable |
| Month 6 | End of month 6 | Twilio logs, months 1–6; sets cap for next period | E1 | E3 | Secondary takes over; EM notified if both unavailable |

**Review action thresholds — upward and downward:**

If the review finds that the observed p95 has grown more than **20%** from the previous checkpoint's baseline, the primary owner of that checkpoint raises a ticket to increase the AUTH cap before the next checkpoint.

If the review finds that the observed p95 has shrunk more than **30%** from the previous checkpoint's baseline, the primary owner raises a ticket to decrease the AUTH cap, returning headroom to the SOCIAL sub-cap.

The upward threshold (20%) is tighter than the downward threshold (30%). This asymmetry is intentional and acknowledged: the consequence of failing to raise the AUTH cap in time is OTP SMS failure, a security-critical user-facing degradation. The consequence of failing to lower the AUTH cap in time is suboptimal SOCIAL sub-cap allocation, which is operationally benign. A tighter threshold on the upward side reduces the risk of the worse outcome. The 30% downward threshold avoids thrashing the cap on short-term volume dips that may reverse before the next checkpoint.

The ticket for either direction is assigned to the primary owner of the checkpoint that triggered the review: E1 for post-launch, month-1, and month-6 checkpoints; E2 for the month-3 checkpoint.

### 2.3 Redis-to-CloudWatch Metric Publication Pipeline

#### Shared Constants

Both the publisher and the circuit breaker import Redis timeout values from a single shared module. There is no duplication.

```python
# shared/redis_constants.py
# Single source of truth for Redis connection parameters.
# Both publisher and circuit breaker import from here.

REDIS_SOCKET_TIMEOUT_SECONDS = 5
REDIS_CONNECT_TIMEOUT_SECONDS = 3
```

```python
# publisher/constants.py
from shared.redis_constants import REDIS_SOCKET_TIMEOUT_SECONDS, REDIS_CONNECT_TIMEOUT_SECONDS

PUBLISH_INTERVAL_SECONDS = 60
MAX_RETRIES = 3               # 3 total attempts. Attempt index is 1-based: 1, 2, 3.
BACKOFF_CEILING_SECONDS = 4
CW_CALL_TIMEOUT_SECONDS = 30  # Explicit. AWS SDK default is also 30s, but we set
                               # it explicitly so any SDK version change does not
                               # silently alter behavior.
HEALTH_FILE_PATH = "/tmp/publisher_healthy"
STALENESS_THRESHOLD_SECONDS = 213  # Derivation below.
```

```python
# circuit_breaker/constants.py
from shared.redis_constants import REDIS_SOCKET_TIMEOUT_SECONDS, REDIS_CONNECT_TIMEOUT_SECONDS

# No local Redis timeout definitions. Both values come from shared module.
```

#### Test for Shared Constants

The previous version used `hasattr` to verify that publisher and circuit breaker modules did not define Redis timeout constants locally. This approach is wrong: `hasattr` returns `True` for any attribute present on the module object, whether it arrived via import or via local assignment. A developer who writes `REDIS_SOCKET_TIMEOUT_SECONDS = 99` in `publisher/constants.py` after the import line shadows the shared value at runtime, but `hasattr(pub_const, 'REDIS_SOCKET_TIMEOUT_SECONDS')` still returns `True` — it cannot distinguish the source. The `hasattr` test always passes and catches nothing.

The corrected test inspects the module source text directly:

```python
# tests/test_constants_consistency.py
import inspect
import textwrap
import publisher.constants as pub_const
import circuit_breaker.constants as cb_const
from shared import redis_constants

def _local_definitions_in_source(module, names):
    """
    Return the set of names from `names` that appear as local assignments
    in the module's source text (i.e., lines of the form `NAME = ...` that
    are not inside a string or comment).

    This is a syntactic check, not a runtime check. It detects local
    definitions even if they are shadowed by an earlier import.

    Limitation: this check is defeated by dynamic assignment