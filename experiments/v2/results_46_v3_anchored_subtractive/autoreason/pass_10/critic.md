## Real Problems Found

### 1. The Redis Failure Gap Is More Serious Than Admitted

The document acknowledges that Redis failure causes the publisher to emit 0 for consumed metrics, but the heartbeat still arrives, so `SMS_METRIC_PUBLISHER_DEAD` does not fire. The stated mitigation is "Redis failure is independently alarmed." But the document never defines that Redis alarm — its threshold, evaluation period, or action. The mitigation is asserted, not specified. If Redis is slow rather than fully failed (elevated latency, partial connectivity), the publisher may emit 0 without Redis being alarmed at all.

### 2. The Document Ends Mid-Sentence Again

Finding 6 from Revision 6 was "document ends mid-sentence." The executive summary claims this is resolved and "Section 3.2 is completed in full." Section 3.2 does not appear in this revision at all. More critically, Section 2.8 ends mid-sentence: "For a 200-account attack at 1 req/sec per account (200 req/sec total, below per-user rate limits):" — the calculation is never completed. The same defect that was marked as resolved has recurred in a different section.

### 3. The 22:00 UTC Guard Is Arbitrary and Unexplained

The document states that after 22:00 UTC, 72K consumed is "plausible on a max-volume day (80K × 22/24 ≈ 73K)." This math assumes perfectly linear consumption across 24 hours, which contradicts the 3× peak multiplier defined in Section 1. If peak traffic is 3× average and occurs during morning/evening spikes, consumption is not linear. The 22:00 threshold is not derived from the app's actual usage patterns — it is invented. The document does not state what timezone the user base is in or whether 22:00 UTC corresponds to peak or off-peak hours for actual users.

### 4. The ConditionExpression in the Lambda Only Checks the Normal Value

The `ConditionExpression='cap_value = :normal'` check in the Lambda only succeeds if the cap is exactly 80,000. If a human operator has manually set the cap to some intermediate value (e.g., 40,000 during a prior incident that did not fully resolve), the condition fails, the Lambda silently logs "already reduced," and no further action is taken. The `ConditionalCheckFailedException` handler treats any non-80K value as "already reduced" without verifying what the actual current value is.

### 5. RB-07 Requires Manual DynamoDB Console Edits With No Validation

The runbook instructs the operator to type `80000` into the DynamoDB console and set a timestamp manually in ISO 8601 format. There is no checksum, no confirmation step, and no protection against a typo (e.g., `800000` or `8000`). The verification step — waiting 60 seconds and checking `SocialSMSCapCurrent` — is described but that CloudWatch metric is never defined anywhere in the document. It is referenced only in RB-07.

### 6. The AUTH Fallback Has No Handling for Users Without Email

The document acknowledges that users without a verified email may be locked out during AUTH SMS exhaustion. It accepts this tradeoff. But there is no specification of what the system actually does for those users — does it return an error, silently fail, queue the OTP indefinitely, or drop it? The fallback behavior for the unhandled case is unspecified.

### 7. Sub-Cap Totals Do Not Add Up Cleanly Under the Adjustment Procedures

The AUTH cap starts at 20K and is "adjustable by E1 via manual procedure." The SOCIAL cap starts at 80K and is "adjustable by Lambda down to 10K." The document states the total is 100K/day across both paths, but there is no enforcement mechanism that keeps AUTH + SOCIAL ≤ 100K when E1 manually adjusts the AUTH cap upward. Two independent caps with independent adjustment procedures and a shared total constraint is not enforced anywhere in the design.

### 8. The Quarterly Review Process Is Defined by Reference Only

The document refers to a "quarterly sub-cap review process" and a "monthly review process" for consumption trends in multiple places, but neither process is defined. Who conducts it, what data is reviewed, what triggers a cap adjustment, and what the adjustment procedure entails are all absent. These are cited as mitigations for real risks (AUTH headroom shrinkage, undemonstrated consumption claims) but contain no substance.

### 9. The `essential: true` Restart Behavior Creates a Potential Amplification Problem

Setting `essential: true` on the publisher sidecar means a publisher crash restarts the entire ECS task, including the worker. During an active attack, repeated publisher crashes would repeatedly restart workers, interrupting in-flight processing and potentially causing message loss or duplicate processing at exactly the moment operational stability is most needed. The document presents `essential: true` as unambiguously correct but does not address this failure interaction.