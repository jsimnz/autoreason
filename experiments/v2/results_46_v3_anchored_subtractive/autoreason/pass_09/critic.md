## Real Problems Found

### 1. The Redis-to-CloudWatch Pipeline Is Undocumented and Untested as a Dependency

The entire alarm structure depends on a Redis gauge being published to CloudWatch every 60 seconds. This pipeline is mentioned once ("published to CloudWatch every 60 seconds as a gauge") but never specified: what publishes it, how it's deployed, what happens when it fails, and whether it has its own monitoring. If this publisher crashes or lags, the consumed counter stops updating in CloudWatch, alarms stop firing, and the circuit breaker is silently dead. The Lambda pass criteria test the Lambda itself but not the health of the metric publication pipeline that triggers it. A silent failure in this pipeline is indistinguishable from a quiet day.

### 2. The Idempotency Implementation Has a Race Condition in the Read Path

After catching `ConditionalCheckFailedException`, the code does a separate `get_item` to read the current value for logging. Between the failed conditional write and the `get_item`, another invocation could write a different value. The logged "current value" may not reflect what actually won the race. This is cosmetic for logging but indicates the author is treating the read-after-failed-write as reliable, which it is not. More seriously, the `updated_at` field is set to `context.aws_request_id`, which is not a timestamp. Any system or human reading `updated_at` to determine when the cap was reduced will get a request ID string, not a time.

### 3. The 90% Threshold Automation Has No Time-of-Day Awareness

The Lambda fires when 72K SOCIAL messages are consumed, regardless of what time of day it is. If 72K is consumed by 11 PM from entirely legitimate traffic on a high-engagement day, the Lambda locks the SOCIAL cap at 10K for the remaining hour. The next day it resets. This may be acceptable, but the document explicitly states "normal consumption never approaches 72K before end of day" without demonstrating this. There is no stated monitoring of daily consumption trends, no stated process for raising the sub-cap if the app grows, and no stated consequence if legitimate growth causes the automation to fire routinely on non-attack days.

### 4. The Rollback Runbook RB-07 Is Referenced but Not Present

Pass criterion 4 requires E4 to execute RB-07 and complete it in under 5 minutes without E1 present. RB-07 is not included in this document. There is no way to evaluate whether the 5-minute criterion is realistic, whether E4 actually can execute it alone, or whether it requires any preconditions (credentials, access, pre-staged values) that might not be satisfied at 2 AM during an incident.

### 5. The AUTH Sub-Cap Exhaustion Response Is Explicitly Deferred to Human Judgment With No Stated SLA

The document says AUTH cap exhaustion "requires human judgment, not automation" and pages on-call at 80% consumption. At 3–5K normal daily volume, reaching 16K is already 3–5× normal. But the document gives no response time expectation, no escalation path if on-call doesn't respond, and no fallback if AUTH SMS is exhausted before a human acts. For OTP and security events, exhaustion means users cannot authenticate or receive security alerts. The document identifies this as the worst possible outcome in Section 2.2 and then provides no automated protection for it.

### 6. The Document Ends Mid-Sentence Again

Section 3.2 ends with "If not pre-staged, E1 cannot complete rotation alone" followed by a horizontal rule and nothing. Finding 3 from Revision 5 was that the document ended mid-sentence. This revision claims that finding was resolved in full. It was not.

### 7. The Boundary Test in Pass Criterion 3 Is Internally Contradictory

The criterion states the test value is 59,999 "to confirm the threshold boundary," then says "a separate boundary test sets the value to 60,001." The 60,001 boundary test is mentioned but not defined as a formal criterion with pass/fail conditions, responsible parties, or environment. It exists as a parenthetical. If it's necessary to confirm threshold behavior, it should be a numbered criterion. If it's not necessary, it shouldn't be mentioned as something that happens.

### 8. The 80-Account Attack Calculation Assumes Maximum Per-User Rate Is Sustained

The analysis states 80 accounts × 10 req/sec = 800 req/sec, with the 75% alarm firing after 75 seconds. This assumes all 80 accounts sustain maximum rate simultaneously for 75 continuous seconds. A more realistic distributed attack would use more accounts at lower rates to stay below per-user limits while still consuming cap. The document acknowledges IP-based WAF doesn't fire for authenticated attackers but doesn't address whether per-user rate limits are enforced across accounts belonging to the same attacker. The consumption-based alarm still fires eventually, but the claimed 75-second detection window is derived from a maximum-rate assumption that an attacker has no reason to satisfy.

### 9. The SOCIAL/AUTH Split Totals Are Asserted Without Accounting for Growth

The document fixes AUTH at 20K and SOCIAL at 80K with the total at 100K. The 20K AUTH figure is justified by 4–6× headroom over current volume. But the document covers a 6-month build for a 10M MAU app with no stated growth rate. If MAU grows significantly during the 6-month window, AUTH volume grows proportionally, and the 4–6× headroom shrinks. There is no stated process for reviewing or adjusting sub-cap allocations, and the AUTH cap is explicitly made non-adjustable by automation. Adjusting it presumably requires a deployment or manual intervention, but this is never stated.