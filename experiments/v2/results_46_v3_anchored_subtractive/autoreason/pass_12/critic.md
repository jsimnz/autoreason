Here are the real problems I found:

---

**1. The `Average < 1` heartbeat logic is wrong.**

The document claims `Average < 1` fires when data stops arriving entirely (missing data → BREACHING). But if data *is* arriving — say, 2 of 3 publishers are alive and emitting 1 — the average is still 1.0, not < 1. The alarm never fires for partial failure, which the document acknowledges. But more critically: the document's own explanation of *why Average works* is incoherent. It says "Average < 1 fires when PublisherHeartbeat data points stop arriving entirely" — but that's the missing data treatment doing the work, not the Average statistic. The Average statistic is doing nothing here that Sum wouldn't also do if the threshold were set correctly. The justification is confused, and a confused justification for a monitoring decision is a real operational risk.

**2. The heartbeat alarm cannot distinguish publisher crash from CloudWatch publish failure.**

If `_cw.put_metric_data` fails — network partition, CloudWatch throttle, IAM permission revoked — the publisher loop catches the exception, logs it, and continues sleeping. The heartbeat stops arriving. `SMS_METRIC_PUBLISHER_DEAD` fires. But the publisher is not dead; Redis reads may be succeeding fine. On-call is paged with the wrong signal. The failure mode table presumably says "publisher dead" but the actual condition is broader. This is the same class of error the document corrected in Finding 6, but it reappears here for CloudWatch failures.

**3. Redis key rollover at midnight is unhandled.**

The consumed counter key is `sms:social:consumed:{today}` where `today` is UTC date. At midnight UTC, the publisher starts reading a new key that doesn't exist yet, gets `None`, coerces it to 0, and publishes 0. The circuit breaker at dispatch also reads the new key and sees 0 consumed. For however long it takes the new day's first messages to arrive, the system behaves as if nothing has been sent. There is no TTL management, no key initialization, and no discussion of this boundary condition anywhere in the document.

**4. The AUTH sub-cap headroom claim is unfalsifiable at build time.**

The document states AUTH volume is "estimated at 3–5K/day" and that 20K provides "4–6× headroom," with the assumption reviewed quarterly. But there is no specified data source for the 3–5K estimate. The analytics pipeline is mentioned as a data source for the SOCIAL threshold (Section 2.5, Finding 2 resolution), but AUTH SMS volume from an existing system that isn't built yet has no measurement basis cited. If the estimate is wrong by 2×, the headroom claim collapses before the first quarterly review.

**5. The Lambda constraint check is a TOCTOU race.**

Section 2.1 and 2.5 describe the Lambda reading both cap values, checking the constraint, then writing. In a concurrent scenario — manual AUTH cap increase happening simultaneously with an attack triggering the Lambda — the read and write are not atomic. DynamoDB conditional writes are not mentioned. The document describes a check-then-act pattern with no atomicity guarantee, then states "enforcement... is rejected before the DynamoDB write executes" as if this is reliable.

**6. `essential: false` creates an unmonitored gap between publisher crash and alarm.**

The document acknowledges the 3-minute detection window. What it doesn't address: during an active attack — exactly when the publisher is most likely to be stressed — there is a 3-minute window where consumption metrics are blind and no one is paged. The document frames this as acceptable because the Redis circuit breaker still functions. But the alarm that would page on-call about the attack's consumption rate is also the alarm that depends on the publisher. If the publisher dies during the attack, on-call loses visibility precisely when they need it most, with a 3-minute delay before even knowing the publisher is down.

**7. The document is cut off.**

The last line reads "Finding 5 resolution: The prior revision listed AWS/ElastiCache / CacheClusterStatus as the metric source. Cache" — the sentence is incomplete. This is the same class of defect that Finding 1 in this revision claims to have fixed ("The document has been reviewed in full before submission"). The document was not reviewed in full before submission.

**8. `publish_once` makes two separate `datetime.now()` calls.**

`today` and `now` are computed from separate calls to `datetime.now(timezone.utc)`. If these calls straddle midnight UTC, `today` is one date and `now` is the next. The Redis key read uses yesterday's date; the CloudWatch timestamp is tomorrow. This is a minor but real correctness issue with no mitigation.

**9. No cap on CloudWatch `put_metric_data` cost at scale.**

With N ECS tasks each running a publisher emitting 4 metrics every 60 seconds, the CloudWatch API call volume is `N × 1/min`. The document doesn't specify expected task count or bound it. At high task counts during an attack (if the service autoscales), CloudWatch costs and API limits become relevant. CloudWatch has a `PutMetricData` limit of 1,000 requests/second per account. This is likely not a problem at this scale, but the document never examines it, and the per-task publisher architecture makes it a linear function of task count with no acknowledgment.

**10. The runbook reference to Section 2.7 is forward-declared but Section 2.7 is not in the document.**

Section 2.1 says "the runbook step for it is added to Section 2.7." Section 2.7 is not included in the submitted text. Whether it exists or not cannot be verified from this document.