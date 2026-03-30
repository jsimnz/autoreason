## Real Problems with This Proposal

### 1. The Dynamic Reallocation Mechanism Is Underspecified and Likely Broken

The document claims high-priority workers are "temporarily reassigned" when high-priority backlog depth < 1,000 messages, implemented as "a queue depth check in the worker dispatch loop." This is not specified anywhere beyond this sentence. How frequently is the check performed? What prevents all workers from draining to standard-priority simultaneously, leaving zero capacity if a second high-priority spike arrives mid-drain? The 28-minute calculation depends entirely on this reallocation working correctly, but the mechanism has no specification, no failure mode analysis, and no mention in §7's work allocation.

### 2. The Spike Scenario Is Constructed to Validate the Architecture, Not Stress-Test It

The worst-case scenario uses a single viral post generating 800K mentions and 1M likes. But the scenario assumes these arrive over 10 full minutes at a steady 8,000/sec. Real viral spikes are not uniform — they front-load heavily in the first 60–90 seconds as the post is shared. A more realistic spike shape would produce a much higher instantaneous enqueue rate, potentially exceeding the claimed Redis capacity ceiling and invalidating the O(log N) queue depth arithmetic. The document acknowledges the 21-minute figure was wrong due to unrealistic spike composition, then constructs another convenient spike shape.

### 3. The Single Redis Sorted Set Has an Unacknowledged Starvation Risk

The document claims the dequeue policy "ensures high-priority messages are processed first while not starving standard-priority messages entirely" but provides no mechanism for this. A strict priority-ordered sorted set with weighted scoring will mathematically starve lower-priority entries whenever higher-priority traffic is sustained. The document doesn't specify what prevents standard-priority starvation during extended high-engagement periods — not just during spikes. A 65% DAU/MAU app generating continuous high-priority traffic could starve standard-priority queues indefinitely.

### 4. The Opt-In Rate Analysis Contradicts Itself

The executive summary states "the channel mix shifts, not the total notification count" when push opt-in rates are applied. This is wrong. If 48% of DAUs don't receive push notifications, those notifications don't automatically route to another channel — they require explicit user preference configuration. The system as described routes un-opted users to in-app, but in-app is only shown to "active session users." A user who isn't in-session gets nothing. The document treats this as a provisioning detail but it's actually a product correctness problem: a meaningful fraction of notifications are silently dropped.

### 5. The Burst Multiplier Reasoning Is Circular

The document argues high-engagement tiers need higher burst multipliers because denser networks produce more correlated activity. This is plausible. But the multipliers (2×, 3×, 4×, 5×) are then used to size infrastructure for tiers the team hasn't reached and won't validate before launch. More critically, the base case 3× multiplier is attributed to "Firebase engineering data on mid-scale social apps" — a source that isn't cited, isn't in the benchmarks table, and doesn't appear elsewhere in the document. This is the only multiplier that will be tested at launch and it has the least documented justification.

### 6. The Abort Criterion Has a Logical Flaw

The rollout abort criterion uses "three trigger events within any 48-hour window." The document specifies the window resets on each new trigger event, not on recovery. This means a system experiencing continuous degradation that produces trigger events every 25 hours will never accumulate three events in a 48-hour window and will never trigger an abort — the window keeps resetting. The intent was presumably to catch sustained problems, but the mechanism allows indefinite degradation to continue as long as events are spaced slightly more than 24 hours apart.

### 7. The Three Separate Redis Deployments Multiply Operational Burden Without Acknowledgment

The executive summary presents separate Redis deployments for queue, SMS caps, and preference cache as a solved problem. But the document's stated constraint is 4 engineers over 6 months. Three separate Redis clusters means three separate failure modes, three separate monitoring configurations, three separate backup and recovery procedures, and three separate upgrade cycles. The document justifies the architectural choice by noting different failure modes but doesn't account for the operational cost of running three clusters with a team this size. This directly contradicts the stated principle of "operational simplicity over theoretical elegance."

### 8. The In-App Deduplication Claim Is Not Substantiated

The document states in-app notifications "share a deduplication key with push/email/SMS" and that §3 specifies "split-brain prevention mechanism and divergence handling." The executive summary references this as a solved problem. But the document is cut off before §3 appears. This is a significant gap: in-app bypasses the queue entirely while other channels go through it, and the deduplication must work across a queue-bypassing fast path and a queued slow path. The claim that this is handled is stated but never demonstrated in the visible text.

### 9. The Feasibility Argument for the 6-Month Timeline Is Absent

§7 is described as mapping "specific work to specific engineers with sequencing, interface contracts, and a feasibility argument that can be evaluated." The document doesn't reach §7. More fundamentally, the executive summary lists eight distinct complex subsystems (tiered queue, SMS cap enforcement with Lua scripts, three Redis deployments, dynamic worker reallocation, burst injection testing, production rollout with abort criteria, preference management, DAU/MAU monitoring). There is no visible analysis of whether four engineers can design, build, test, and operate all of this in 26 weeks. The claim that a feasibility argument exists is not the same as the argument.

### 10. The 70% Email Reach Assumption Is Unexamined

The channel reach table assumes 70% of registered users receive email notifications, reduced only by unsubscribes. This ignores deliverability: a new domain sending millions of emails per day will face significant spam filtering, ISP rate limiting, and reputation scoring problems that take months to resolve. New sending infrastructure typically starts at much lower deliverability rates. The document treats email as a reliable fallback channel for un-opted push users, but for a new app with no sending history, email deliverability is a launch-week problem, not a steady-state one.