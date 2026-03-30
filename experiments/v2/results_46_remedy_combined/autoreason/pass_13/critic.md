## Real Problems with This Proposal

### 1. The "fail-closed on suppression" logic is internally contradictory

The proposal states the system fails closed during database outages — no notifications sent. Then it carves out OTP with a "local cache fallback." But the cache was populated from the same preference database that's now unavailable. The proposal doesn't specify cache TTL for the suppression path, what happens when the cache is cold (first outage after deploy), or how stale suppression data is acceptable for OTP but not for other notifications. The carve-out is asserted as safe without demonstrating it.

### 2. The credential breach SMS scenario is mentioned but never actually scoped

Section 1.1 flags a 10M-user SMS blast as a distinct cost model in Section 5.3, but the document cuts off before Section 5. This isn't a truncation artifact to dismiss — a 10M SMS send is operationally and financially unlike anything else in the system. Twilio rate limits, cost (potentially $500K–$1M+ at standard rates), regulatory requirements for mass messaging, and the decision authority to trigger such a send are all unaddressed. It's listed as a population boundary justification and then abandoned.

### 3. WAND is load-bearing but ungoverned before Week 4

The proposal acknowledges WAND can't be estimated until Week 4. The digest ramp section then says Day 7 volume is "directly measurable from the consent ledger" — but this sidesteps the problem. The *infrastructure* must be provisioned before Day 7. The aggressive scenario (1.3M/day) is cited as the floor for alarm thresholds, but there's no statement that infrastructure is provisioned to that ceiling, or what happens if Week 1 digest volume exceeds it. The measurement protocol doesn't solve the provisioning question.

### 4. The P0 worker count justification is circular

The document says P0 workers are fixed at 4 instances because "the operational risk of a scaling delay on OTP delivery outweighs the cost of 2 additional always-on tasks." But it never establishes what load 4 instances actually handles, whether 4 is sufficient at the 225M/day ceiling, or what failure mode occurs if P0 volume exceeds capacity. "Fixed" is presented as a safety property, but fixed-and-undersized is worse than auto-scaled with a warm minimum.

### 5. The SQS FIFO sharding scheme breaks its own ordering guarantee under resharding

The proposal uses consistent hashing on `conversation_id` across 4 FIFO queues. It notes shard count starts at 4 "at launch." It says nothing about what happens when shards are added. Consistent hashing minimizes remapping, but any remapping of a `conversation_id` to a new queue during active message processing produces out-of-order delivery for that conversation — exactly the property FIFO was chosen to prevent. The proposal presents sharding as a solved problem while omitting the only operationally difficult part of it.

### 6. The "stable day" definition creates a baseline that can never promote during normal growth

A day is unstable if volume is more than +20% above the 7-day rolling average. A social app at launch should expect week-over-week growth. If daily volume grows 5% per day — modest for a new launch — the rolling average will consistently lag, and most days will trigger the +20% ceiling. The 7-consecutive-stable-days requirement may never be met during the growth phase, leaving load-test baselines active indefinitely. The proposal doesn't acknowledge this.

### 7. The OneSignal opt-in benchmark limitation is acknowledged but the consequence isn't followed

The proposal correctly identifies that OneSignal's data is self-selected. It then uses it anyway as the sole source and sets infrastructure sizing at 75% opt-in. If the actual opt-in rate is lower — plausible given the selection bias — the system is over-provisioned, which is recoverable. But the document doesn't address the inverse: if the social app's design or audience skews toward higher engagement than OneSignal's benchmark population, 75% may be the floor, not the ceiling. The benchmark selection bias cuts both directions.

### 8. The "Day 3 measurement protocol" decision window is operationally unworkable

If iOS share falls outside 50–70%, the infrastructure lead has 2 business days to produce a revised cost model, then a 24-hour escalation window. That's potentially 3 business days of operating on potentially wrong infrastructure sizing. Day 3 of a production launch is not a moment where a 72-hour decision cycle is acceptable. The protocol also doesn't specify what "operating on the existing tier" means if the actual load is already stressing that tier.

### 9. Engineer C is a single point of failure for the digest threshold recalibration job

Section 1.3 names Engineer C as the owner of the weekly recalibration job. Section 8 (not shown) presumably defines team scope. A named individual owning a weekly operational job that sets alert thresholds is a coverage problem — illness, departure, or context switch means the threshold silently holds at its last value (per the failure behavior described), with only an alert to on-call as a backstop. The proposal treats ownership as equivalent to redundancy.

### 10. The document explicitly defers scope to Section 8 without showing it

The proposal references Section 8 ("Team Scope and Feasibility") for what ships in Phase 1, Phase 2, and what's deferred — then the document cuts off mid-Section 2. This means the feasibility case for the entire proposal is unreviewed. A design document that front-loads architectural decisions but defers the feasibility argument to a missing section cannot be evaluated as a complete proposal.