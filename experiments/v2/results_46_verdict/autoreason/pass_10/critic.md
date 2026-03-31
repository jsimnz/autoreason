## Real Problems with This Proposal

### 1. The Peak Throughput Math Is Internally Inconsistent

The document criticizes "compounding two elevation factors" when applying a spike multiplier to an already-elevated peak rate, then does exactly that. The 2,125/sec figure is the *average* rate within the peak window—already elevated above the daily average. Applying a 50% buffer on top produces 3,190/sec, which is precisely the compounding the document claims to avoid. The justification offered ("conservative headroom, not a primary sizing input") is rhetorical, not analytical. The design ceiling is either justified by a model or it isn't.

### 2. The SMS Budget Analysis Contains a Hidden Assumption That Drives the Conclusion

The P0 fallback SMS cost is calculated using a 2% push failure rate applied to 2% of push volume. Both percentages are asserted without basis. The 2% push failure rate is particularly important: FCM/APNs delivery rates vary significantly by device state, network conditions, and token staleness. Industry-observed failure rates for push are often 5–15% when including silent failures and expired tokens. If the actual failure rate is 10%, P0 fallback SMS becomes ~42,000/day instead of 8,400—nearly tripling total SMS cost and potentially breaching the $15,000 cap within days of launch. The budget analysis is sensitive to this input and the input has no stated basis.

### 3. The Coverage Gate Timeline Has a Structural Contradiction

The document states coverage gates require a minimum 3-week span, then schedules both in-app and push coverage gates to complete within month 2's four weeks. Gate 1 starts week 1, Gate 2 is week 3, Gate 3 is week 4. That's three weeks from start to finish—the stated minimum. This leaves zero schedule float. A single Gate 2 failure (which the document explicitly acknowledges as possible) pushes Gate 3 into month 3, but month 3 already has email and SMS coverage gates scheduled. The document says "gate failures are channel-specific and do not cascade," but engineer availability does cascade—E3 cannot simultaneously be the primary owner supporting email development and the coverage partner completing a failed in-app Gate 2 retry.

### 4. E1's Dual-Role Conflict Is Not Actually Resolved

The proposed resolution is sequencing: E1 completes push coverage gates in month 2 "after infrastructure has been running in production for a full month." But month 1 infrastructure is internal-traffic-only. The first month of real production load is month 2, concurrent with E1's Gate 3 solo on-call week for push. The document describes E1 as triaging a potential infrastructure incident during that week and deciding whether to hand off the push incident—this is not a resolution, it's a description of the conflict. The "explicit tradeoff" framing acknowledges the risk but the mitigation (E2 pages E1 immediately) requires E2 to be monitoring infrastructure while also being the primary push responder. That's another dual-role conflict one level down.

### 5. The In-App Month 1 Risk Acceptance Is Understated

The document accepts that E3 is the sole responder for in-app in month 1, with E4 as "informal backup." It then offers three mitigations, two of which are weak: "well-understood failure modes" is asserted, not demonstrated (the system hasn't run in production yet), and "internal traffic only" means incidents still affect real users—engineers, employees, or beta users are still users. The third mitigation—that E4 is a competent engineer who can triage—directly contradicts the document's own framing of coverage gates as necessary precisely because informal competence is insufficient. The document argues strenuously that coverage must be demonstrated capability, then accepts undocumented informal capability for month 1.

### 6. The Notification Type Taxonomy Is a Prerequisite With No Failure Mode Documented

The taxonomy is identified as a hard prerequisite for month 1 launch, allocated to 2 days in week 1, requiring review by E2 and E3. No failure mode is specified: what happens if the taxonomy review reveals disagreements about classification? What happens if P0 classification criteria conflict with the SMS fallback gate logic, which depends on notification type? A 2-day estimate for a cross-team definitional artifact that gates all downstream components has no buffer and no stated escalation path if the definition is contested.

### 7. The Channel Freeze Procedure Conflicts With the Timeline's Implicit Dependencies

Month 4 spot-checks can trigger a channel freeze for any channel that fails. Month 5 delivers re-engagement campaigns using push and email. If push fails its month 4 spot-check and is frozen at current traffic levels, month 5's re-engagement campaign work is blocked or must launch on a degraded channel. The document does not address this dependency. The milestone table treats months 4, 5, and 6 as independent, but the channel freeze mechanism creates conditional dependencies that are unacknowledged.

### 8. The Document Is Incomplete Mid-Sentence

Section 3a cuts off: "FCM is mocked at this load level. This is an explicit—" The document is unfinished. This is not a minor editorial issue in a design proposal being used to make infrastructure and staffing decisions. Whatever followed "explicit" was presumably material to understanding what the load test actually validates.

### 9. The Runbook Maintenance Process Creates Perverse Incentives

Requiring a runbook update as a condition of incident closure means engineers under pressure to close incidents are incentivized to write minimal updates that technically satisfy the requirement rather than genuinely useful documentation. The document acknowledges the monthly review requires "no changes required" sign-off as an alternative to actual updates—this creates a path where engineers sign off monthly without substantive review and the runbook drifts from reality. The enforcement mechanism (sprint planning template required field) catches absence of sign-off, not quality of sign-off.

### 10. The Per-Channel Queue Justification Assumes a Specific Failure Mode Without Demonstrating It

The core architectural decision—per-channel queues over single queue with fanout—is justified by FCM backpressure blocking email and in-app delivery. This is a real failure mode in some architectures. However, the document does not specify what queue implementation would exhibit this behavior. Standard message queue implementations (SQS, RabbitMQ, Kafka consumer groups) with separate consumer pools per channel already provide isolation within a single queue topology. The failure mode described is a consumer pool design problem, not a queue topology problem. The architectural decision may still be correct, but the stated justification doesn't support it.