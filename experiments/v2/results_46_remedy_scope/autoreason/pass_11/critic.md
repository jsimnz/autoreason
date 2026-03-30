## Real Problems with This Proposal

### 1. The Starvation Prevention Claim Is Unsubstantiated

The executive summary states the "P1-drains-P2/P3 mechanism is fully specified with starvation prevention," but no actual starvation prevention mechanism appears anywhere in the visible document. There are no token buckets, no minimum service rates, no work-stealing logic for P2/P3 under sustained P1 load. The claim is made and never delivered.

### 2. The Deduplication Layer Is Referenced but Never Defined

The document references "the deduplication layer" in sections 2.3 and implicitly elsewhere as the solution to duplicate delivery from the slow-worker race condition. This layer is never specified. How it works, where it lives, what its storage backend is, its own failure modes, and its performance cost are entirely absent. It is load-bearing architecture treated as a footnote.

### 3. The Recovery Lock TTL Creates a Gap It Claims to Prevent

The lock TTL is 45 seconds and the recovery cycle runs every 30 seconds. If a recovery process acquires the lock, runs for longer than 30 seconds (plausible under Redis latency or a large stale set), and then the lock expires at 45 seconds, a second recovery instance can acquire the lock before the first has finished. The Lua script is described as a "second layer of defense" against this, but the document simultaneously claims the lock prevents concurrent execution. Both cannot be fully true. The actual concurrency guarantee is weaker than stated.

### 4. Worker Count Derivation Is Missing

The document states worker capacity is "~26,000/sec" and references a "worker matrix" as a single source of truth, but neither the matrix nor the derivation of individual worker throughput figures appears in the visible document. The 26,000/sec figure is asserted. The basis for per-worker throughput (the ~1,000 rows/sec/worker figure for in-app workers appears once, without justification) is never established. Capacity planning built on unanchored numbers is not capacity planning.

### 5. The APNs New-Bundle-ID Throttling Mitigation Is Promised but Absent

The executive summary states "The APNs new-bundle-ID throttling failure case has a specified mitigation." No such mitigation appears in the visible text. This is a known, painful operational problem with real production consequences, and the document claims to address it without doing so.

### 6. The 79× In-App Overcapacity Justification Is Circular

The three reasons given for not sizing down in-app workers are: ancillary workload (unquantified), a hypothetical 50% concurrency scenario (not the planning figure), and that in-app workers are "cheap." None of these constitute a sizing rationale. The ancillary workload—read-state updates and delivery confirmations—is described as adding "load not captured in the delivery rate" but is never estimated. A worker matrix built on unquantified load is not a matrix, it is a guess.

### 7. The P0 Failover Behavior Quantification Is Missing

The executive summary claims "P0 behavior during the failover window is quantified." The visible document does not contain this quantification. The Redis primary/replica failover window duration, the specific P0 impact during that window, and the basis for any numbers given are not present in the provided text.

### 8. The Viral Spike Analysis Contains a Logical Error

The document argues the system absorbs a 20× viral spike because worker capacity (26,000/sec) exceeds the spike demand (~10,500/sec). But the spike is then correctly identified as hitting FCM rate limits. The worker capacity argument is therefore irrelevant to the actual constraint—the bottleneck is the external provider, not the workers. The document reaches the right conclusion (P2/P3 shedding) through flawed reasoning, which means the reasoning provides no actual safety guarantee for correctly identified edge cases.

### 9. The Expiry Pruning Process Is Cut Off

The document ends mid-sentence during the description of TTL enforcement and the expiry pruning process. This is not a minor omission—TTL enforcement is one of the four core architectural decisions named in the executive summary. The pruning race condition (between expiry and dequeue), the handling of messages that expire while in the processing set, and the interaction between the expiry sorted set and the recovery process are all unspecified.

### 10. The 30-Day Validation Commitment Has No Defined Response

The planning decision states to "re-plan before month 3" if measured traffic diverges from projections by more than 2×. For a team of 4 engineers on a 6-month timeline, a re-plan triggered at day 30 with a month-3 deadline consumes roughly a third of the total project duration. The document does not acknowledge this timeline risk or identify what "re-plan" means in terms of scope, personnel, or what gets cut.

### 11. The Configuration-Change Capacity Shift Is Slower Than Presented

The document states shifting channel capacity takes "approximately 5 minutes for a 5-worker pool." This assumes the rolling restart is scripted, tested, and the on-call engineer is immediately available. The runbook is referenced but not included. At 3 AM during a viral event, the actual time-to-capacity-shift is not 5 minutes. The document presents a best-case operational number as a planning figure.