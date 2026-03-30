## Real Problems with This Proposal

### 1. The P2-Steals-from-P1 Mechanism Is Underspecified and Likely Broken

The document says "P2 workers check P1 queue depth before pulling from P2; if P1 depth exceeds a threshold, P2 workers temporarily pull from P1." This is described in one sentence and never specified further. What is the threshold? How do workers coordinate to avoid all P2 workers simultaneously migrating to P1, leaving P2 completely unserved? What triggers the return? This is not a minor implementation detail — it's the entire starvation mitigation strategy, and it's absent.

### 2. The Dedicated P0 Poller Is Architecturally Inconsistent

The high-level diagram shows "4 general instances + 1 dedicated P0 instance" but the poller fleet section heading promises throughput analysis and fleet design, then the document cuts off. More importantly: if the outbox poller uses `FOR UPDATE SKIP LOCKED` on a single table filtered by priority, a dedicated P0 poller and general pollers are competing on the same table with overlapping index scans. The document never explains how P0 rows are reserved exclusively for the dedicated poller rather than being grabbed by general instances first.

### 3. The Idempotency Key Mechanism Has a Race Condition

The schema uses `notification_delivery_attempts` with a composite primary key `(notification_id, channel)` as the idempotency store. The document says "written before send, checked before each attempt." But two workers processing a duplicate-enqueued notification concurrently will both read no existing row, both attempt to insert, and the loser gets a constraint violation — which may be treated as a failure and trigger a retry rather than a deduplication. The document acknowledges duplicates are "an inherent property of at-least-once delivery" but the specified mechanism doesn't actually handle the concurrent duplicate case.

### 4. The Outbox Poller Throughput Calculation Is Incomplete

The document literally cuts off mid-sentence: "With 4 general instances: **" — the conclusion, the headroom calculation, and the "17× headroom" claim referenced in the executive summary are missing. The executive summary states "4-instance poller fleet, 17× headroom over peak" as a key design decision, but the supporting analysis is absent. This is not a minor omission; it's the primary justification for the fleet sizing.

### 5. The Failure Mode in Section 2.3 Is Worse Than Acknowledged

The document identifies "push-enabled, in-app-disabled users when push relay fails permanently" as the worst case. But it understates the problem. If a user has push enabled and in-app disabled, the in-app record written in the transaction is permanently invisible to them by preference — but the outbox row still gets dead-lettered after retry exhaustion. The document asks for product sign-off but doesn't specify what the system *actually does* in this state. Does it escalate? Alert? Nothing? The sign-off question is asked without giving product the information needed to answer it.

### 6. The SMS Cost Analysis Contradicts Itself

The document correctly identifies that blended international SMS cost is "$0.02–$0.04/message" and that domestic-only estimates are misleading. It then says "spend caps require finance and product sign-off before launch" — but it's launching in month 2 with SMS as a live channel. If spend caps aren't defined until sign-off happens, what governs SMS spend between launch and sign-off? The document lists this as an open question without acknowledging that shipping SMS without a spend cap is the actual risk.

### 7. The Month-2 Launch Risk Is Understated for E4's Domain

The document acknowledges the month-2 cross-training gap but focuses on queue infrastructure (E1/E2). E4 owns "reliability, monitoring, failure handling, DevOps" — meaning E4 owns the on-call response tooling, runbooks, and alerting for a live production system. E3 is E4's designated backup. But E3's primary domain is preference management and user-facing APIs, which is the furthest from reliability tooling of any pairing. A month-2 incident requiring deep knowledge of the delivery pipeline failure handling falls to E4, whose backup has the least relevant context.

### 8. The Payload TTL Creates an Unacknowledged Failure Window

The outbox poller writes payloads to Redis with a 2-hour TTL, then enqueues the notification ID. If a P2 notification sits in the queue for more than 2 hours during a backlog — plausible given P2 is lowest priority and can be deprioritized by the starvation mitigation — the worker fetches the notification ID, goes to Redis for the payload, finds nothing, and must either fail, fall back to PostgreSQL, or drop the notification. None of these behaviors are specified.

### 9. The "Fail Closed" Preference Check Has No Specified Behavior

The router does a "preference check (Redis cache → DB fallback → fail closed)" but "fail closed" is never defined. Does it mean suppress the notification entirely? Queue it for later? Return an error to the caller? For auth OTPs classified as P0, failing closed and suppressing the notification is a serious correctness problem. The document calls out the OTP escalation question as requiring sign-off (Section 3.6, which isn't shown) but the fail-closed behavior upstream of that is also unspecified.

### 10. The Three-Queue Operational Overhead Is Acknowledged but Not Costed

The document admits three queues means "three DLQs, three alert thresholds" but doesn't account for the full operational surface: three sets of backlog metrics, three capacity scaling decisions, three sets of retry policies, and the starvation mitigation logic that must be maintained alongside all of them. With 4 engineers and no dedicated ops, this is a real ongoing maintenance burden that the document lists as a cost accepted but doesn't quantify against the team's available capacity.