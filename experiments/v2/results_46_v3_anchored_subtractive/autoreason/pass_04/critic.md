Here are the real problems with this proposal:

## Concurrency and Correctness

**The Redis delete on SQS failure creates a race it claims to accept but doesn't fully analyze.** The proposal says "we accept this" when the delete-then-retry window allows a concurrent caller to enqueue a duplicate. But the window is not just brief — it includes the full round-trip time of the failed SQS call plus the Redis delete. Under SQS timeouts (which can be seconds), this window is meaningful. The proposal waves this away without quantifying it.

**The "hung call" scenario in Section 3.2 is more common than acknowledged.** The proposal claims FCM/APNs client timeouts of 5 seconds make this rare "in practice," but 5 seconds is close enough to a 10-second visibility timeout that any cumulative latency — connection establishment, TLS handshake, DNS, queuing in the HTTP/2 connection pool — can push the total over 10 seconds without the call itself hanging. The proposal treats this as an edge case when it is a normal latency distribution tail.

**The worker-layer dedup check has a race the proposal doesn't acknowledge.** Two workers can both read `sent:{notification_id}` as absent (before either sets it) if the SQS visibility timeout expires at the exact moment a second consumer picks up the message. The `SET NX` fix applied to the router layer is not applied here — the worker section describes the check conceptually but doesn't guarantee atomicity in the same explicit way.

## Architecture

**The two-queue P0 routing in Section 3.3 introduces a new ordering problem.** The push/email queue and the in-app queue are independent. There is no guarantee the in-app write completes before or around the same time as push delivery. A user who receives a push notification and immediately opens the app may find no corresponding in-app record — not just for "the same second" as the proposal admits, but potentially for however long the in-app writer queue is backed up. The proposal dismisses this but it directly undermines the stated purpose of the in-app record as a "guaranteed backstop" the user can see.

**The SQS FIFO per-group throughput concern in Section 3.1 is unresolved, not mitigated.** The proposal acknowledges AWS documentation "does not specify per-group throughput limits clearly" and that there is "no empirical data for this usage pattern" at 1,000 groups. It then proceeds to use 1,000 groups as the design. The lack of empirical data is presented as a reason to be conservative, but conservatism here means choosing a number without knowing whether it works — not validating it before committing.

**The "revisable decision" framing for group count obscures a real constraint.** The proposal says increasing from 1,000 to 5,000 groups "does not require a code change." This is true for the group ID calculation but ignores that changing group counts on an active FIFO queue changes which messages are in which groups mid-stream, potentially reordering in-flight messages for users who straddle the transition.

## Team and Operational

**The E2 "secondary familiarity" with the core pipeline is undefined.** The proposal says E2 can "maintain the pipeline in a steady state — keeping it running, handling incidents, making small changes." What constitutes a "small change" is unspecified. This distinction matters because the boundary between "incident response" and "a change that requires pipeline ownership" is exactly what gets crossed during a real incident.

**The DLQ alert threshold of "depth 3" is misconfigured for the stated purpose.** Depth 3 means three *processing attempts* per message, not three messages in the DLQ. A single P0 notification that fails three times triggers the alert. But the proposal elsewhere describes transient failures (slow APNs, brief database hiccups) as expected. Three retries on a transient failure is a normal occurrence, not a PagerDuty event. The alert will fire constantly under normal operating conditions.

**The SMS hard alert at 150K/day against a 100K/day cap is not actionable.** The proposal says there is a "hard system-level alert at 150K/day" but does not specify what the system does when that threshold is hit — whether SMS continues, stops, queues, or drops. An alert without a defined response is monitoring theater.

## Specification Gaps That Remain

**The APNs token manager implementation is truncated in the proposal itself.** The document ends mid-string-literal inside the `_generate_token` method. This is not a minor omission — the token generation is the security-critical path for all APNs delivery, and it is literally unfinished in Revision 4.

**The P0 email escalation criteria are referenced in the executive summary as a problem that was fixed, but no specification appears in the document.** The summary says "P0 email escalation criteria" was among the ten problems addressed, but Section 4 does not define what triggers a P0 email escalation versus a standard email.

**The OTP abandoned delivery cleanup mentioned in the executive summary has no corresponding section.** It is listed as one of the ten addressed problems but does not appear in the document body.