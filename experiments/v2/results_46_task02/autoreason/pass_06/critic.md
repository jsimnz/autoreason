## Real Problems with This Proposal

### Architectural Problems

**The outbox-to-Redis relay is not atomic, and the design knows this but doesn't resolve it.** The "read-before-mark" on Redis adds ~1ms latency but does not eliminate the crash window between confirming Redis has the item and marking the outbox row as relayed. If the poller crashes after the Redis write but before the mark, the outbox re-relays on next poll, producing a duplicate in Redis. The idempotency mechanism (DB constraint + advisory lock) operates at delivery time, not at queue ingestion time. Duplicates in the Redis sorted set are structurally possible and the proposal doesn't specify how they're detected or collapsed there.

**P0 uses Redis Sentinel, not Redis Cluster.** The proposal uses Redis Cluster for P1/P2 but Redis Sentinel for P0. Sentinel provides failover but not horizontal scaling. If P0 queue throughput spikes (viral auth event, mass account compromise triggering OTPs), there's a single Redis primary handling all P0 writes with `appendfsync always`. This is a potential bottleneck that's never analyzed. The proposal discusses P1/P2 burst capacity extensively but ignores P0 throughput limits entirely.

**The two-active-instance P0 poller with advisory lock is underspecified where it matters most.** The proposal says "follower polls for leader liveness" but the document cuts off before specifying the failover timing, what happens to in-flight batches during leader transition, or whether the follower can promote before the leader's advisory lock is released. This is described as "fully specified in Section 3.5" but Section 3.5 doesn't appear in the document.

**P2 starvation mitigation has a race condition by design.** The proposal explicitly states all 10 P2 workers may simultaneously enter assist mode via independent threshold checks, leaving P2 completely unserved. This is called "correct behavior." But P2 is never defined — if it includes anything time-sensitive (delivery receipts, preference updates that affect routing), complete P2 starvation during P1 backlogs is not obviously correct. The proposal treats P2 as fully deferrable without establishing that this is true.

**The dedicated P0 PostgreSQL instance creates a consistency boundary that's never addressed.** In-app notifications are written in the same transaction as outbox entries. If in-app and P0 notifications share a user action (e.g., a security alert that triggers both in-app and SMS OTP), they now span two PostgreSQL instances with no distributed transaction. The proposal doesn't specify how cross-instance consistency is handled or whether this scenario exists.

### Capacity and Scaling Problems

**The burst analysis is internally contradictory.** The proposal calculates 10,000–14,000 notifications/second for a viral event affecting the top 20% cohort, then says "we cannot sustain this, we absorb it via queue depth." But it also says P1 alert threshold is queue age exceeding 5 minutes. At 14,000/sec inbound and ~1,750/sec sustainable throughput, the queue grows at ~12,000/sec. Five minutes of accumulation is 3.6M items. The proposal never specifies what happens at that depth — whether workers degrade, whether Redis memory becomes a constraint, or what the actual P1 SLA becomes during a sustained viral event.

**Redis memory sizing is absent.** The proposal specifies three Redis sorted sets plus three dead-letter queues plus sliding window rate limit state, but never estimates memory requirements. At 50M notifications/day with burst accumulation, payload sizes matter enormously for whether the Redis tier fits in memory. This is a basic capacity planning omission.

**The 6× burst ceiling is contradicted by the proposal's own math.** The document calculates that the top-20% cohort can generate 8–10× their personal baseline, which translates to fleet-level bursts well above 6×. The 6× ceiling is then described as a "hedge against being wrong about the fleet average" — but the proposal demonstrates it's already wrong about the fleet average. The ceiling is retained anyway without justification.

### Operational Problems

**Section 3.5 and 3.6 are referenced but not present.** The P0 leader election failover behavior is "fully specified in Section 3.5." Dead-letter queue drain procedures have their own runbooks in "Section 3.6." Neither section exists in the document. These aren't minor omissions — the P0 failover spec is described as a hard dependency for the month-2.5 launch, and the DLQ runbooks are cited as justification for the three-queue operational cost.

**The E3/E4 backup problem is acknowledged but the mitigation is inadequate.** The proposal admits E3 will not be expert in E4's domain by launch and that a novel 3am failure means E3 pages E1 or E2, "negating some of the rotation benefit." What it doesn't acknowledge is that E4 owns monitoring and alerting — the systems that determine whether anyone gets paged at all. If E4 is unavailable and the alerting infrastructure has a novel failure, E3's ability to "execute runbooks" is contingent on knowing something is wrong in the first place.

**The feedback processor is a box with no internals.** Bounces, delivery receipts, and token invalidations are mentioned in the architecture diagram and nowhere else. APNs token invalidation in particular requires specific handling — failing to process invalidations means continued delivery attempts to dead tokens, which APNs will eventually interpret as a signal to throttle the sender. This affects all push delivery, not just the affected users.

**DLQ drain is listed as a maintenance burden without specifying who owns it or how often.** The proposal quantifies DLQ maintenance as part of the 5 engineer-hours/month figure but doesn't specify ownership rotation or what "drain procedure" means operationally. If a DLQ fills with failed OTP notifications, the decision about whether to retry, escalate, or discard requires product and security input — not just an engineer running a script.

### Process and Governance Problems

**The OTP escalation path is a hard launch blocker owned by E4 with a week-3 escalation trigger, but there's no specified escalation target.** The proposal says "the project lead escalates" if there's no documented decision by week 3 of month 1. E4 is a 4-person team. Who is the project lead? Who do they escalate to? The mechanism for forcing a product and security decision is undefined.

**SMS spend cap sign-off has Finance and Product as joint owners with no tiebreaker.** If Finance approves a budget and Product wants a higher cap, or vice versa, the proposal provides no resolution path. The consequence (SMS delayed to month 4) assumes the delay decision itself can be made unilaterally by the engineering team, which is unlikely if Product has committed to SMS in month 3.

**The co-build schedule extension from month 2 to month 2.5 is stated as a consequence of co-building, but the original month-2 deadline presumably has external dependencies.** If there are product commitments, marketing timelines, or contractual obligations tied to a month-2 launch, a 2-week slip decided unilaterally in the design document is not actually resolved — it's deferred to a conversation that hasn't happened yet.

**The proposal requires Finance sign-off on SMS spend caps but provides a cost estimate range of $60K–$240K/month — a 4× spread.** This is too wide to be actionable for budget approval. Finance cannot approve "somewhere between $60K and $240K" as a monthly line item. The estimate would need to narrow before sign-off is realistic, but the proposal says real data won't exist until month 2 — after the sign-off deadline.