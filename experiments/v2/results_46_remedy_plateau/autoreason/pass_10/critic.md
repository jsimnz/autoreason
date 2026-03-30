Here are the real problems with this proposal:

**1. The 37-minute delay figure is presented as derived but contains an unresolved internal contradiction.**
The document claims standard-priority workers process at 1,500/sec during the spike (30% of 5,000), then computes post-spike drain using the full 5,000/sec capacity. The 37-minute figure is stated as the conclusion but the arithmetic showing how you get from "565K backlog at t=90 at 1,500/sec drain" to "37 minutes total" is never completed. The document cuts off mid-sentence on the high-priority SLA analysis, which is one of two items requiring sign-off before the spike injection test. A document with open sign-off requirements cannot have its primary supporting arithmetic truncated.

**2. The worker throughput model assumes no concurrency, then assumes concurrency implicitly.**
The latency budget explicitly models a single-threaded worker processing one notification at a time. The 50/sec midpoint follows from that. But 100 workers × 50/sec = 5,000/sec is only achievable if each worker is fully saturated with no idle time between notifications — no dequeue wait, no backpressure, no retry logic. The model contains no accounting for worker idle time, retry overhead, or the dead time between completing one notification and picking up the next. The 5,000/sec figure is therefore a ceiling treated as a sustained rate throughout all the arithmetic.

**3. The single Redis sorted set is a single point of failure with no failover analysis.**
The document explicitly chose a single sorted set over per-channel queues for operational simplicity. It never addresses what happens when that Redis instance is unavailable. For a system processing 51M notifications/day, a Redis outage means total notification stoppage. The operational simplicity argument is made entirely in terms of steady-state management, not failure modes. There is no discussion of Redis Sentinel, Cluster, or any degraded-mode behavior.

**4. The token bucket starvation prevention mechanism is referenced but never specified.**
Section 2.3 is cited twice — once in the executive summary and once in the queue design — as where starvation is "addressed mechanically." The document never reaches or includes §2.3. This is not a truncation artifact; the executive summary explicitly flags this as a key architectural decision. The starvation problem is real (acknowledged), the solution is promised, and the solution is absent. Any reader evaluating the core architectural decision cannot do so.

**5. The opt-in rate is used inconsistently as both a reach figure and a throughput figure.**
The document correctly flags the population conflation problem between registered users and DAU for email. It then does not resolve it. The channel reach table shows email reach as "50% at launch = 5M reachable" using the MAU base, but states "all channel volume estimates use DAU as the base." These two statements cannot both be true simultaneously. If email throughput is based on DAU, the 5M reachable figure is irrelevant to capacity planning and should not appear in the same table as throughput-relevant figures.

**6. The session race condition fix introduces a new unquantified storage requirement.**
The pending-delivery record approach for in-app notifications requires writing a record per in-app notification per active session. At 3M DAU with some percentage in active sessions, this is a non-trivial write load to an unspecified store (called `pending_store` without any design). The SESSION_DELIVERY_WINDOW_SECONDS constant is referenced but never defined. The expiry path is deferred to §3.2. The document presents this as a solved problem in the routing logic section when it is actually a deferred design problem.

**7. The DAU/MAU monitoring thresholds imply operational capacity that contradicts the team size constraint.**
The document specifies a 24-hour runbook initiation SLA when the 7-day rolling average hits 35% DAU/MAU, and a 6-week architectural lead time at 55%. A 4-engineer team that is also building the system has no slack for a 24-hour runbook execution on top of ongoing development. The thresholds are stated without any analysis of whether the team can actually execute the implied response within the stated SLAs.

**8. The burst capacity margin is inconsistent with the spike model.**
The system is provisioned at 8,000/sec with a stated ~13% margin over the 7,080/sec burst target. The spike model then shows an instantaneous arrival rate of 24,100/sec at t=0 plus 2,360/sec background = ~26,460/sec total. The 8,000/sec figure is not a burst capacity target in any meaningful sense relative to the actual modeled spike. The document never reconciles these two numbers.

**9. The pre-launch validation commitment has a pass/fail criterion that does not cover the failure mode it is meant to catch.**
The spike injection test threshold is set at 40/sec per worker: if below this, increase to 125 workers. But the document's own pessimistic estimate is 25/sec per worker at 40ms provider latency. If actual throughput comes in at 25/sec, 125 workers gives 3,125/sec — well below the 5,000/sec required. The validation criterion does not specify what happens if throughput falls below 40/sec by more than the threshold implies.