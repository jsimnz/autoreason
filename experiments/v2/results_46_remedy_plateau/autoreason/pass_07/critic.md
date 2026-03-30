## Real Problems with This Proposal

### 1. The Document Cuts Off Mid-Sentence

The proposal ends abruptly at `KEYS[1]: "sms_cap:{user` — the Lua script is incomplete, §1.2.1 is unfinished, and §1.2.2 (global caps), §1.2.3 (email vendor evaluation), and §§2–7 are entirely missing. The executive summary references all of these sections as containing critical specifications. The document is not reviewable as a complete proposal.

### 2. The Self-Referential Citation Problem Is Unresolved

The executive summary acknowledges circular reasoning in §1.1.1 but doesn't actually fix it — it just names the problem. Saying "we acknowledge these numbers are judgment calls" and "the production rollout will correct them" is not a mitigation; it's a plan to find out you were wrong after launch. The entire provisioning architecture (worker count, Redis instance size, RDS write capacity) is downstream of numbers the document admits are not validated. The acknowledgment of circularity reads as intellectual honesty but functions as inoculation against criticism.

### 3. The Base Case Peak/Sec Arithmetic Is Internally Inconsistent

The table states peak/sec (burst) for the base case is ~8,000. But §1.1.2 derives 8,000/sec by applying a 3× multiplier to primetime sustained rate (~2,360/sec), then rounding up with a 10% margin. The table presents ~4,500/sec for the low tier and ~8,000 for the base case, implying the same 3× burst multiplier applies equally regardless of engagement tier. A 65% DAU/MAU user base almost certainly has different burst characteristics than a 20% DAU/MAU base — more correlated activity, larger follower graphs, higher viral spike amplitudes. Using the same multiplier across all tiers is inconsistent with the document's own structural argument about engagement correlation.

### 4. The Staffing Section (§7) Is Referenced But Absent

The executive summary makes a specific claim: "§7 maps specific work to specific engineers with explicit sequencing, interface contracts, and a feasibility argument that can actually be evaluated." This section does not exist in the document as presented. A proposal for 4 engineers over 6 months that cannot be evaluated for feasibility is not a complete proposal.

### 5. The 21-Minute Delay Analysis Ignores Queue Composition

The backlog clearance arithmetic treats all 1.8M backlogged messages as standard priority. But during a spike, high-priority notifications (DMs, mentions) are also being enqueued. The document claims high-priority notifications clear within 3 minutes under spike conditions, but doesn't show the arithmetic that supports this given that the single sorted set is draining at a fixed 5,000/sec total — shared across all priority tiers. If the spike is driven by a viral post generating millions of mention notifications (which would be high-priority), the 3-minute SLA for high-priority is not demonstrated.

### 6. The Email Cost Figure Has an Obvious Error

The table shows email at ~3.7% of volume (~1.9M/day) at $0.0008/notification = $1,520/day. But the document rounds this to "$1,500/day" and calls it "48% of channel cost." The total daily cost shown is $3,125. Email at $1,500 is actually 48% of that total — but push at $390 and SMS at $1,185 together equal $1,575. Email is the largest single channel cost but the "48%" framing obscures that SMS at $1,185/day for 0.3% of volume is nearly as expensive per-day and far more expensive per-notification. The cost analysis focuses attention on email while the more alarming cost ratio is SMS, which the document simultaneously restricts and under-scrutinizes in the visible sections.

### 7. The Rollout Abort Criterion Is Underspecified

"The same stop threshold is triggered three times within 48 hours after recovery" — "after recovery" is ambiguous. Does the 48-hour window reset after each recovery? Does it start from the first trigger? If three separate stop-threshold events occur with full recovery between each one over 47 hours, is that an abort? The criterion as written can be read either way, which means it will be interpreted optimistically under launch pressure — exactly the failure mode the document claims to be preventing.

### 8. The Benchmarks Are Outdated and the Document Knows It

The document cites Twitter 2013 data and Facebook 2014–2016 data, then explicitly acknowledges "different era with different notification philosophies." Modern social apps operate under iOS notification permission prompt changes (iOS 14+), Android notification permission changes (Android 13+), and significantly different user opt-in rates than 2013–2016. The Braze 2021 survey is the only recent data point, and it aggregates across app types. The 8/17/28/40 notifications-per-DAU-per-day estimates in the table are plausible for high-engagement social apps but are at the high end of what post-2020 permission rate changes would support. The document doesn't model what happens if actual opt-in rates are 40–50% rather than assumed near-100%.

### 9. The In-App Bypass Architecture Creates an Unacknowledged Split-Brain Risk

The document states in-app notifications "bypass the queue for latency reasons and write directly to a dedicated delivery store via a separate path with its own retry logic." This means a user receiving both a push notification and an in-app notification for the same event has those notifications written through different code paths, different retry logic, and different failure modes. The document doesn't address deduplication across these paths or what happens when one path succeeds and the other fails — a user sees the push but not the in-app badge, or vice versa. The mechanism is deferred to §3, which is not present.

### 10. The Scale Trigger Mechanism Has a Monitoring Gap

"Weekly rolling average via the existing analytics pipeline. Monthly review checks the 7-day average against scale triggers." These two sentences are in tension. A weekly rolling average checked monthly means you could cross the 35% DAU/MAU threshold and not act on it for up to 4 weeks. The document says "the scale-up runbook is initiated before the next review cycle" if the threshold is crossed — but the review cycle is monthly. Crossing the threshold on day 2 of a monthly cycle means 28 days before the next review. The document doesn't specify continuous monitoring or alerting on the DAU/MAU ratio; it specifies periodic review.