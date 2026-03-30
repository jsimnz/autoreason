## Real Problems

### 1. The 47-Minute Standard-Priority Delay Is Buried, Not Resolved

The executive summary flags 47 minutes as an "open decision requiring sign-off" but the document never presents the business consequence clearly. For a social app, a 47-minute delay on standard-priority notifications (which likely includes likes, comments, follows — core engagement drivers) is not a latency tradeoff, it's a product failure. The document treats this as an acceptable degraded mode pending sign-off, but never states what percentage of daily volume is standard-priority versus high-priority, so the reader cannot assess how often this worst case materializes or what fraction of users are affected during a 3× spike.

### 2. The Document Is Incomplete and Cites Sections That Don't Exist

The proposal references §2, §2.3, §3.2, and §7 repeatedly for critical specifications — the starvation mechanism, the pending store design, and the scope cut list — but none of these sections are present in the submitted document. This is not a minor omission. The routing code explicitly depends on §3.2 for SESSION_DELIVERY_WINDOW_SECONDS, the high-priority SLA derivation depends on §2.3, and the timeline contingency depends on §7. The document is not reviewable as a complete proposal.

### 3. The 8-Minute High-Priority SLA Is Asserted Without the Derivation

The executive summary states "High-priority SLA: 8 minutes worst-case (completed analysis in §1.1.2; prior 3- and 5-minute claims are retracted)" but §1.1.2 as presented contains no such derivation. The section cuts off mid-sentence. The retraction of prior claims without a replacement derivation leaves the proposal with no defensible high-priority SLA at all.

### 4. The Worker Throughput Model Contradicts Itself

The document states sustained throughput is 35/sec per worker, describes this as "slightly above the midpoint," then derives the midpoint as 31/sec with a further 2% retry reduction yielding ~30/sec. 35/sec is not slightly above 30/sec in a way that is conservative — it is 17% above the adjusted midpoint figure the document itself computed. The pre-launch validation table then treats 35/sec as the baseline and 30–34/sec as a scaling trigger, meaning the capacity plan is built on a figure the document's own arithmetic does not support.

### 5. The Burst Model Is Structurally Incomplete

The table lists an instantaneous peak of ~24,100/sec for the base case at t=0 but leaves the High and Top-quartile instantaneous peaks blank. The document then states the system is "designed to absorb" rather than process the instantaneous peak in real time — but the sentence cuts off before explaining what "absorb" means quantitatively, what the maximum queue depth is, and whether Redis has sufficient memory to hold the spike backlog. Without this, the burst absorption claim is unverified.

### 6. The Opt-In Rate Assumption Is Treated as Validated When It Isn't

The document cites a 52% push opt-in rate for capacity calculations. The cited industry range is 45–60%. The proposal selects a figure near the middle of that range and uses it as a planning assumption, but the entire daily volume estimate (26.5M push notifications) scales directly with this number. A 45% opt-in rate versus 60% changes push volume by 33%. The document acknowledges this is a judgment call but does not present sensitivity analysis on this specific figure despite it being called out as one of the three assumptions that "most affect infrastructure sizing."

### 7. The Routing Code Has an Unacknowledged Atomicity Problem

The routing function writes a pending record, then appends the in-app channel to the dispatch list, then calls dispatch. If the process crashes between the pending store write and the dispatch call, the pending record exists but no notification is ever dispatched. The record will expire and generate an audit entry with reason "pending_record_expired" — which is indistinguishable in the audit log from the case where dispatch succeeded but delivery failed before session end. The document identifies the session-end race condition but does not identify this crash-between-write-and-dispatch gap.

### 8. The Email Volume Calculation Uses an Inconsistent Population Base

The throughput table computes email volume as 1.2M users × 5 notifications/day = 6M/day, using DAU as the base. But email notifications for a social app are typically sent to users who are *not* in an active session — they are re-engagement or catch-up notifications. Using DAU as the base for email reachable users likely overcounts active-session users who would receive in-app notifications instead and would not receive the email. The document separates throughput and list-size figures carefully but does not address this overlap between email and in-app delivery populations.

### 9. The Pre-Launch Validation Gate Has No Timeline or Owner

The spike injection test is described as a hard gate before production rollout, but the document specifies no date, no owner, no environment requirements beyond "staging FCM/APNs sandbox," and no criteria for what constitutes a valid 10-minute sustained measurement (e.g., what load profile, what queue depth at test start). Given that the entire capacity plan depends on this test's outcome, the absence of these details means the gate cannot actually be enforced.

### 10. Redis Sentinel Failover Time Is Not Addressed Against the SLA

The proposal uses Redis Sentinel for automatic failover with a PostgreSQL fallback queue. Redis Sentinel's typical failover time is 10–30 seconds. During failover, workers attempting to dequeue from Redis will fail and must detect the outage before routing to PostgreSQL. The document does not specify the detection mechanism, the switchover latency, or whether in-flight notifications at the moment of failover are at risk of duplication or loss. This is directly relevant to the 8-minute high-priority SLA — a 30-second outage plus switchover during a spike could consume a meaningful fraction of that budget.