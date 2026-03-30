## Real Problems with This Proposal

### 1. The Model Validates Itself

The document repeatedly states that figures will be "measured at the validation gate" and worker count "adjusted" based on actual throughput. But the architectural decisions (Redis Sentinel vs. Cluster, dedicated worker pool, queue topology) are being made *now*, before measurement, based on the estimates those measurements are supposed to validate. If the 30/sec per worker figure is wrong by the stated 2.7× spread, the queue architecture may be fundamentally wrong, not just the worker count. Measuring throughput post-decision doesn't validate the architecture; it validates a number that feeds into an already-locked structure.

### 2. The Confidence Intervals Are Ungrounded

The document presents intervals like "±30 min" for the 47-minute delay and "±7 min" for the 14-minute delay, but provides no basis for these specific bounds. They aren't derived from the stated input uncertainties (±50% on volume, 2.7× spread on latency). A ±50% volume uncertainty and a 2.7× latency uncertainty compound nonlinearly in a queuing model — the delay figures could be off by far more than ±30 minutes in the tail. Presenting specific confidence intervals without showing how they were derived from the input distributions gives false precision while claiming to avoid it.

### 3. The Burst Multiplier Problem Is Acknowledged But Not Resolved

The document explicitly states the 12× combined peak multiplier is "an extrapolation beyond what the cited data supports" and calls the 200MB queue depth an "order-of-magnitude placeholder." It then uses these figures throughout the capacity analysis. Acknowledging a number is uncalibrated doesn't make it safe to use as a planning input. If the actual spike is 20× rather than 12×, the 47-minute delay figure is not just wrong — the queue may never drain, which is a qualitatively different failure mode.

### 4. The DAU/MAU Sensitivity Table Contradicts the Infrastructure Sizing Claim

The document claims "worker capacity of 3,000/sec handles all scenarios up to and including the 40% DAU/MAU case without architectural changes," but the 40% case produces ~1,050/sec sustained, which during a 12× spike becomes ~12,600/sec — more than four times the stated worker capacity of 3,000/sec. The sensitivity table shows sustained rates, not spike rates. The claim that the architecture handles the upper bound of the sensitivity range is only true at sustained load, not under the spike conditions the rest of the document is designed around.

### 5. The Routing Rule Has an Unanalyzed Race Condition

The email/push routing rule ("email only when user has no active session at routing time") creates a race condition: a user's session can expire between the routing decision and the push delivery attempt, or a session can begin after the email is dispatched. The document treats session state as a clean binary at routing time. In a system processing 840/sec at base case, session state is continuously changing. The document doesn't address what happens to the delivery guarantee when session state changes mid-dispatch, or how often this occurs.

### 6. The "Default Decision" Framing Misrepresents the Risk

The document frames the 14-day timeout defaults as protecting the project from indecision, but the defaults are not neutral. Defaulting to Option A (dedicated high-priority worker pool) is described as costing "~3 engineer-weeks," and defaulting to Sentinel is described as the "simpler option." However, the document also notes that Sentinel has a 10–30 second failover window during which the PostgreSQL fallback queue activates. The interaction between these two defaults — a dedicated worker pool architecture combined with a Sentinel failover that forces queue migration — isn't analyzed. The defaults could interact badly, and the document treats them as independent decisions with independent costs.

### 7. The In-App Clarification Creates an Unaddressed Dependency

The document correctly clarifies that in-app delivery is a client-side read operation, not a dispatch. But this means in-app delivery depends on the notification feed read path being available and consistent with the dispatch state. If a push notification is dispatched but the notification feed read fails (Redis unavailable, circuit breaker open), the user gets a push but sees nothing in-app on open. The document scopes out in-app entirely after the clarification, but the dispatch system's failure modes directly affect in-app consistency. That dependency is unaddressed.

### 8. The Session-Correlation Model Is Applied in One Direction Only

The document correctly notes that during viral events, more users are in-session, reducing email volume by ~5%. But the same dynamic means more users are in active sessions, which means the push delivery path is handling more concurrent connections and FCM/APNs is under higher load from more apps simultaneously. The session-correlation model is used to reduce email volume (a small conservatism) but isn't applied to the push delivery latency assumption. If provider API latency increases during viral events precisely because everyone is in-session and hammering FCM simultaneously, the 15–40ms latency range understates spike-case latency, and the delay figures are optimistic in the scenario they're most important for.

### 9. The PostgreSQL Fallback Queue Is Underspecified at the Moment It Matters Most

The circuit breaker routes to PostgreSQL when Redis is unavailable. The document specifies Redis failover at 10–30 seconds (Sentinel) but doesn't specify PostgreSQL's throughput under spike load, the schema for the fallback queue, how workers transition between Redis and PostgreSQL queues, or how the two queues reconcile when Redis comes back. The fallback is invoked precisely during failure scenarios, which are also likely to coincide with elevated load. An underspecified fallback that activates under the worst conditions is a significant gap.

### 10. The Timeline Has No Slack Accounting

The document states a 6-month timeline with 4 engineers and identifies that the concurrent default scenario consumes "~37% of one engineer's time." It doesn't account for the other identified uncertainties that require engineering response: the validation gate at 500K MAU, the re-plan trigger if DAU/MAU exceeds 45%, the spike injection test needed to calibrate the 200MB queue depth, and the worker count adjustment after measuring actual throughput. Each of these is a conditional engineering commitment. The document lists them individually but never aggregates their expected time cost against the 6-month, 4-engineer constraint. The timeline may already be overcommitted before any of the conditional triggers fire.