Here are the real problems with this proposal:

## Scale Modeling

**The DAU/MAU table is internally inconsistent.** The "base case" row says 17 notifications/DAU but the scenario table in §1.1.2 labels 17/DAU as the base case there too — yet the DAU/MAU table uses "base 17/DAU" as a column header applied to all rows. A user at 20% DAU/MAU ratio doesn't necessarily generate 17 notifications/day; engagement level and notification rate are correlated, not independent variables. The model treats them as orthogonal when they aren't.

**The peak provisioning arithmetic doesn't hold.** "50% of daily volume in a 3-hour window" at 590/sec average gives 590 × 86400 × 0.5 / 10800 = ~2,360/sec sustained. Then "4–5× primetime rate for 5–10 minutes" gives 9,440–11,800/sec. But the document then states burst capacity of 12,000/sec, which is 5× primetime. These numbers are presented as derived from first principles but the upper bound requires selecting the most aggressive multiplier at every step simultaneously.

**The 15M–120M range in the executive summary doesn't match the scenario table.** The conservative scenario gives 15M/day, the high gives 120M/day — so the range is accurate — but the base case is 51M, not something in the middle of that range. The range implies symmetric uncertainty when the model is actually skewed.

## Technical Claims

**The Lua script has a correctness problem the document doesn't fully acknowledge.** The document says overshoot is "bounded by the number of concurrent workers routing for the same user simultaneously — typically 1–2." But this is not a property of the Lua script — it's a property of the worker architecture. If the worker pool has 40 workers and multiple are processing notifications for the same high-activity user, the overshoot bound is 40, not 1–2. The "typically" qualifier is doing a lot of unearned work.

**"Redis Lua execution is single-threaded" is true but potentially misleading at scale.** Single-threaded execution means scripts serialize, which is correct. But it also means a slow or blocked Lua script can stall all Redis operations. The document doesn't address what happens if the TTL calculation (seconds until midnight UTC) has a bug and sets a very long TTL — the cap resets at the wrong time and the cost model breaks silently.

**The RDS write rate claim is questionable.** The document states "RDS db.r6g.2xlarge" must handle "~10,500 inserts/sec" for delivery events. This is presented as a constraint to validate, but a db.r6g.2xlarge running PostgreSQL typically handles 5,000–8,000 simple inserts/sec under realistic conditions with indexes, WAL, and connection overhead. The document doesn't acknowledge this may already be over the instance's capacity at base case load.

**In-app notifications "bypass the queue but share unified delivery event log" is an unresolved tension.** If in-app bypasses the queue, it has different retry semantics by definition — the queue is where retry logic lives. The document asserts they share retry semantics without explaining the mechanism. This is a hand-wave on a non-trivial implementation problem.

## Operational and Organizational

**The backup engineer review gate for runbooks has a circular dependency.** E3 backs up E4, and E4 backs up E2. For month-1 runbooks, the backup engineers are reviewing documentation for systems they haven't been trained on yet — E2's cross-training is explicitly deferred to month 3. The review gate cannot function as a quality signal if the reviewer lacks the context to identify gaps.

**The SMS ownership split creates an unacknowledged coordination surface.** E4 owns the send path; E3 owns STOP handling and carrier suppression. When a user sends STOP, E3 must update suppression state that E4's send path must then check. The document doesn't define who owns the interface between these two systems, what the data contract is, or what happens when E4 sends an SMS to a user whose STOP was processed by E3 but not yet propagated.

**The scaling triggers table is cut off.** The document ends mid-sentence in §1.4. This isn't a minor formatting issue — the scaling triggers section was identified as a core improvement over "revisit at 50M MAU" deferrals, and it's incomplete.

**E1 owns "reliability/monitoring infrastructure" and is also the person who tracks runbook completion.** These are both load-bearing responsibilities given to the same engineer who also owns the core pipeline and queue infrastructure. The document criticizes the original allocation for creating single points of failure but replicates the pattern.

## Process and Framing

**The 5% production rollout in weeks 1–2 post-launch is presented as a provider validation mechanism, but no acceptance criteria are defined.** What error rate from FCM causes the rollout to pause? What SendGrid bounce rate triggers a stop? Without thresholds, "controlled production exposure" is just launching and watching.

**IP warming for SendGrid is acknowledged as a 4–6 week process, but the timeline shows email launching at end of month 2.** If IP warming starts at month-2 launch, the system won't reach full sending capacity until month 3 or 4. The document doesn't address what happens to the 1.9M emails/day in the interim — whether a shared IP pool is used, volume is ramped, or email is delayed. This is a significant gap in the delivery plan.

**"No engineer owns more than two channel integrations" is stated as a constraint in the executive summary but violated in the allocation table.** E3 owns preference management, user-facing API, suppression logic, in-app notifications, WebSocket layer, and SMS STOP handling. Whether these are called "channel integrations" or not, the workload concentration contradicts the stated principle.