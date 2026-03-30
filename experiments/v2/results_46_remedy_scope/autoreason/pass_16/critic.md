## Real Problems with This Proposal

### 1. The Document Is Partially Truncated

Section 2.1 ends mid-sentence ("pool throughput") with no continuation. The PostgreSQL connection pool arithmetic that the executive summary specifically claims is "corrected" and "quantified" is simply absent. This is not a minor omission — the document explicitly promises this derivation and uses it to justify architectural decisions. Readers cannot evaluate the claims.

### 2. The FCM Rate Limit Assumption Is Structurally Circular

The sensitivity table shows that at 500/sec FCM limit, "P1 delays measured in hours," and the document sets a pre-production gate: if load testing shows limits below 2,000/sec, "the priority queue structure must be re-evaluated before launch." But the entire architecture — worker pool sizing, queue tier behavior, spike recovery arithmetic — is built around the 10,000/sec assumption. If load testing invalidates that assumption, the document provides no alternative architecture, just a gate that stops the launch. The gate is not a design; it is an acknowledgment that the design may be wrong with no contingency.

### 3. The Spike Recovery Arithmetic Contains an Unexamined Assumption

The post-spike drain calculation assumes workers accumulate backoff uniformly and reset uniformly. In practice, different worker instances will be at different points in their backoff cycles depending on when they started retrying. The document treats backoff as a fleet-wide synchronized state ("workers reset backoff" at 32–90 seconds), but individual workers will be desynchronized. The drain rate during the ramp-up window is not ~20–40% of capacity in a predictable way — it is highly variable. The clean timeline table obscures this.

### 4. The "Named Decision-Maker" Mechanism Does Not Survive Personnel Changes

The document repeatedly requires "named humans" to accept or reject decisions before production, with names recorded in a runbook. There is no mechanism described for what happens when those named individuals leave the team, change roles, or are unavailable for an extended period beyond the narrow "named backup" provision for month-1 traffic review. The engineering team is four people. One departure invalidates a non-trivial portion of the accountability structure as written.

### 5. The Processing Sorted Set Recovery Has a Silent Data Loss Condition

The recovery goroutine re-enqueues IDs older than 90 seconds from `processing:{worker_id}` sets. But if the worker instance that owns a processing set crashes and its container or VM is destroyed, the `processing:{worker_id}` key may be deleted along with it depending on deployment configuration. The document does not address this. The recovery goroutine runs in "a designated worker instance" — if that instance is the one that crashed, the goroutine itself is unavailable. The crash recovery mechanism has a gap precisely in the failure mode it is meant to address.

### 6. The Token Bucket Lua Script Is Asserted, Not Specified

The executive summary describes "an atomic token bucket implemented as a Lua script" as the starvation prevention mechanism. Section 3 is referenced for the worker pool structure that makes this meaningful, but the document as provided does not include Section 3 in sufficient detail to evaluate whether the Lua script actually prevents starvation or merely rate-limits lower-priority queues. A token bucket limits throughput; it does not guarantee forward progress for lower-priority messages if P0/P1 volume is sustained. Whether this constitutes starvation prevention depends entirely on the bucket parameters, which are not shown.

### 7. The Traffic Response Matrix Has a Timing Gap at the Critical Threshold

The matrix shows that the 45M–80M/day response involves provisioning push workers and increasing Redis instance size "same day." Increasing a Redis instance size is not a same-day operation in most managed cloud environments without pre-planned replica promotion or instance replacement. The document does not acknowledge that Redis resizing may require a failover event, brief unavailability, or pre-provisioned headroom. The "same day" claim is operationally optimistic and untested against actual infrastructure constraints.

### 8. The 50–70 Minute Worst Case Is Presented as Requiring a Decision, but the Decision Has No Deadline

The document states the 50–70 minute worst-case P1 delay "requires a real product decision before production" and must be "recorded with names and date before production launch." But unlike the month-1 checkpoint, which has an explicit day-35 default trigger, this decision has no enforcement mechanism if the product lead and engineering lead simply do not make it. The deployment checklist is mentioned as a gate, but the document does not specify what the default action is if this specific decision is not recorded — only that "placeholder text is not acceptable." Not recording the decision at all is not addressed.

### 9. The DAU/MAU Planning Figure Is Used as Though It Is Independent of Notification Volume

The sensitivity table varies DAU/MAU ratio and notifications-per-user independently, but these are correlated. Higher DAU/MAU ratios typically indicate higher engagement, which drives higher notification rates per user. The low scenario (15% DAU/MAU, 10 notif/user) and high scenario (50% DAU/MAU, 20 notif/user) are directionally correct but the compound uncertainty is larger than the table implies — the joint high case (50% DAU/MAU × 20 notif/user) produces 100M/day, but the joint low case compounds in the other direction. The table presents these as independent variables when they are not.

### 10. Section 2.2 Is Referenced but Not Present

The executive summary and Section 2.1 both reference Section 2.2 for deduplication. The delivered-ID set mechanism, its memory bounds, and the false-positive-rate-zero claim are all deferred to Section 2.2, which is not included in the document. Readers cannot evaluate the deduplication claims, the memory cost, or whether "bounded memory" is actually bounded at the traffic volumes described.