## Real Problems with This Proposal

### 1. The 4.3% Headroom Acknowledgment Undermines the Entire Design

The document explicitly states there is 4.3% operational headroom (110/sec) between planned peak and worker ceiling, then proceeds as if this is a solved problem. It is not. Normal variance in daily traffic — not densification, not viral spikes — can easily exceed 4.3%. A Monday following a holiday weekend, a news cycle, a feature launch: any of these can push peak rates 10–15% above baseline. The system is designed to operate in a regime where it is perpetually one medium-sized event away from hitting the ceiling. The reassessment trigger process requires 6–8 days minimum. The gap between "normal variance" and "trigger fires" is not analyzed.

### 2. The Viral Spike Model Is Referenced But Never Defined

The document mentions "viral spike model" and "explicit spike multipliers" in the worker sizing section, then never provides them. Worker sizing is stated to use "the High scenario plus explicit spike multipliers defined in the viral spike model below" — but no such model appears in the document. This is a missing section masquerading as a cross-reference. The spike behavior of a social app is precisely when the notification system faces its worst-case load, and the design provides no analysis of it.

### 3. The Reassessment Trigger Is Borderline by the Document's Own Admission, and the Mitigation Is Circular

The document acknowledges the 2,400/sec trigger provides only 6 days of lead time at the 1.5 densification rate, against a required 8 days. The stated mitigation is to initiate reassessment early if the observed densification rate is ≥1.3/DAU/day/quarter. But this mitigation depends on accurately measuring the densification rate at 4–6 weeks post-launch, correctly projecting forward, and someone actually executing the runbook task. None of these are guaranteed. The document is using a future manual process to patch a structural design gap, then presenting that patch as if it resolves the gap.

### 4. Default A's Demand Reduction Math Doesn't Close the Gap It Claims To

Default A activates at 2,550/sec and claims to bring demand to 2,220–2,295/sec, within the 2,650/sec ceiling. But the ceiling is a *sustained* ceiling, and Default A reduces Tier 3 throughput — meaning Tier 3 messages queue up rather than disappear. The demand on the system (messages arriving) hasn't changed; only the processing rate has. If the system is above ceiling because of arrival rate, throttling dispatch doesn't reduce load, it defers it. The queues grow. When Default A is eventually lifted, there's a backlog that creates a second peak. This is not addressed.

### 5. The Compliance Architecture Decision Has Schema Implications That Are Understated

The document states the compliance choice has "direct index and query-pattern implications that cannot be cleanly retrofitted." This is presented as a scheduling argument for the Week 2 deadline. The actual risk is larger: if the synchronous default is built into Month 1 schema work and legal later approves the cached architecture, the retrofit isn't just messy — it requires changing the data access pattern for every notification dispatch path. The document frames this as a deadline problem when it's an architectural lock-in problem.

### 6. SendGrid Enterprise Contract Is a Launch Dependency With No Fallback Cost Analysis

The document states the self-hosted email fallback "activates" if the SendGrid contract isn't signed by end of Month 1. The self-hosted fallback is also identified as one of two scenarios that break the engineer-week budget. The document does not say by how much it breaks the budget, what the self-hosted option actually is, what it costs to stand up, or how long it takes. "Triggers explicit stakeholder conversation" is not a fallback plan — it's a description of what happens when the fallback plan is missing.

### 7. The Sign-Off Table Lists "E1" as Owner for Multiple Items That Require External Parties

Items where Legal, Product, and external vendors must act are listed with E1 as the owner. E1 cannot own the SMS budget decision (Product + E1 is listed, but the consequence falls on E1's planning basis). E1 cannot own the SendGrid contract (that's a procurement/finance decision). Listing an engineer as owner of decisions that require legal or business action creates false accountability. When these deadlines are missed — and the document implicitly expects some will be, given the Default A machinery — there is no clear escalation path because ownership is ambiguous.

### 8. The Per-Channel Queue Rationale Has a Hidden Assumption

The stated reason for per-channel queues is that FCM rate-limiting should not delay OTP delivery. But OTPs are typically delivered via SMS, not FCM. If OTPs go through the SMS channel and push notifications go through FCM, they're already isolated regardless of queue topology. The foundational architectural bet #1 is justified by a scenario that may not actually occur — FCM congestion blocking SMS OTPs — because they would be on separate channels anyway. The actual benefit of per-channel queues may be real, but the stated justification doesn't support it.

### 9. The Engineer-Week Budget Claims Fit but Provides No Breakdown

Section 1.3 is referenced as containing "complete aggregate engineer-week accounting" showing the work fits in 96 engineer-weeks. The budget is referenced but not shown in this document. The two scenarios that break the budget are identified (self-hosted email, option b batching) but without the underlying numbers, there's no way to evaluate whether the base case actually fits, whether the margin is 2 engineer-weeks or 20, or whether the budget is being calculated optimistically.

### 10. "Proven Infrastructure" Is Listed as a Foundational Bet but PostgreSQL at This Scale Is Not Examined

The document lists PostgreSQL as proven infrastructure for a system handling 30–70M notifications/day. At 2,500+ writes/sec sustained (every notification dispatch presumably touches the database for preference checks, delivery tracking, and deduplication), PostgreSQL becomes a serious bottleneck that requires careful schema design, connection pooling, and potentially read replicas. None of this is examined. The compliance section mentions a synchronous PostgreSQL round-trip adding 12ms p99 — this is a single-query latency figure that doesn't address what happens to that latency at sustained 2,500/sec write load with four concurrent queues all hitting the same database.