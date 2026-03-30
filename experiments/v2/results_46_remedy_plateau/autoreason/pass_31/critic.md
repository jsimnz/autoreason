## Real Problems with This Proposal

### 1. The "Authoritative Version" Claim Is Structurally Broken

The document declares itself final and implementation-ready while simultaneously acknowledging two open decisions requiring sign-off within 14 days. These are contradictory states. If the open decisions affect implementation, nothing downstream of them is actually final. If they don't affect implementation, they shouldn't be blocking sign-offs. The document doesn't say what the open decisions are (§9 is cut off), so reviewers cannot assess the risk of proceeding.

### 2. DAU/MAU Ratio Is Presented as Derived, But It's Assumed

The 30% DAU/MAU ratio is labeled as a "derivation" in the table but is actually an assumption imported from industry averages. The document says "assuming standard social app engagement patterns" without defining what kind of social app this is. A messaging-heavy app might be 60%+ DAU/MAU. A content-discovery app might be 15%. The entire infrastructure sizing in §5 and capacity planning in §7 flows from this number, and it has no basis in actual product data.

### 3. Peak Throughput Math Is Wrong

The document claims peak hourly volume is ~8M events derived from "2.5× average during 6–10 PM local time." But 6–10 PM local time spans multiple timezones. For a global app at 10M MAU, the peak doesn't concentrate into a single hour — it smears across timezone offsets. If the user base is US-centric this might be defensible, but that assumption is never stated. The 2,200 events/second peak figure used for infrastructure sizing could be significantly wrong.

### 4. "Stop When Delivery Is Confirmed" Logic Has No Confirmation Mechanism for Push

Section 2.1 states the system stops attempting channels once delivery is confirmed. Section 2.2 then states that FCM/APNs delivery receipts are processed asynchronously by a separate consumer. There is no explanation of how the channel selection logic waits for asynchronous push confirmation before deciding whether to attempt email. The architecture diagram shows no feedback path from the receipt queue back to the channel router. Either multi-channel fallback doesn't actually work as described, or there's a missing component.

### 5. Frequency Cap Reset at Midnight UTC Is Unexamined

Push caps reset at midnight UTC. For users in UTC+9 (Japan, Korea) or UTC-8 (US Pacific), this means the reset happens at 9 AM or 4 PM local time respectively — mid-day, not the intuitive user expectation of "daily limit." A user in Tokyo could receive 20 push notifications before lunch, hit the cap, and receive nothing for the rest of their day. This is a product decision with real user experience consequences presented as a trivial implementation detail.

### 6. The Deduplication Window Is Hardcoded at 60 Seconds With No Justification

The 60-second deduplication window is stated without analysis of what it's protecting against. If upstream producers retry on failure with exponential backoff, duplicates might arrive minutes apart, not seconds. If the window is too short, deduplication fails. If it's too long, legitimate re-sends (user likes, unlikes, and re-likes a post) get suppressed. The SHA256 key includes `source_entity_id` but not the event's own timestamp or sequence number, meaning the system cannot distinguish a retry from a new event on the same entity.

### 7. JSONB Override Field Creates a Hidden Scaling Problem

The document acknowledges JSONB is hard to query in aggregate but dismisses this as an analytics concern. This is incomplete. At 10M users, any feature that requires scanning `per_type_overrides` across the user base — compliance audits, preference migration when event types are renamed or deprecated, bulk suppression for a deprecated notification type — becomes operationally painful. Event type names in JSONB keys are also invisible to schema migration tooling, meaning a renamed event type silently breaks existing user overrides with no error.

### 8. Global Unsubscribe Stored on User Record Creates a Cross-System Dependency

Storing the global unsubscribe flag on the `users` table rather than the preferences table means the notification system has a hard read dependency on the users table for every delivery. This is presented as a feature ("checked at the earliest possible point") but it couples the notification pipeline to the users table schema and deployment lifecycle. If the users table is owned by a different team or service, this creates an implicit contract that isn't documented anywhere in this proposal.

### 9. WebSocket Scaling Is Completely Unaddressed

Section 2.3 describes Redis pub/sub with a channel per user for real-time delivery. At 3M DAU with any meaningful session concurrency, this means potentially millions of active pub/sub channels. The proposal says nothing about how many WebSocket server instances are needed, how pub/sub channel fan-out is handled across instances, or what happens to the Redis cluster under this load. Redis pub/sub is not persistent — messages published when no subscriber is connected are lost, and the fallback ("notification sits in the database") is mentioned but the reconciliation logic between socket delivery and database state is not specified.

### 10. 99.9% Availability Target Is Unanalyzed Against the Architecture

The document states 99.9% availability as a success criterion but never analyzes whether the architecture achieves it. The system has at least five external dependencies in the critical path: SQS, SNS, Redis, the database, and FCM/APNs. Each has its own availability SLA. AWS SQS is 99.9%, Redis on ElastiCache is 99.99%, RDS is 99.95%, but FCM and APNs publish no formal SLA. Chained availability of even well-behaved dependencies can easily fall below 99.9%. The warm standby mentioned in §1.2 is never specified — no RTO, no RPO, no description of what "warm" means operationally.

### 11. The 14-Day Sign-Off Deadline Is Unenforceable as Written

The document says open decisions require "joint sign-off within 14 days of issue date" but doesn't state what happens if sign-off doesn't occur. There is no escalation path specified for this scenario (the escalation procedure in §10 is presumably for implementation issues, not pre-implementation governance). With four stakeholders named on the document, a disagreement between product and engineering on an open decision has no defined resolution mechanism within the 14-day window.

### 12. Email Deliverability Risk Is Dismissed Too Quickly

The proposal notes SendGrid or Postmark are "acceptable alternatives if deliverability becomes an issue" with SES, and claims "switching costs are low." Switching email providers mid-operation requires migrating suppression lists, re-establishing domain authentication (SPF, DKIM, DMARC), rebuilding bounce/complaint webhook integrations, and warming up the new provider's sending reputation — none of which is trivial for a 10M MAU product. The claim of low switching costs is not supported.

### 13. SMS Opt-In Requirement Conflicts With Security Event Delivery

Section 2.5 states SMS requires explicit opt-in, and users who haven't opted in receive push or email for security events instead. Section 3.1 classifies "new device login" and "2FA" as Critical notifications that attempt all appropriate channels in parallel. These two statements conflict: if SMS is a channel for Critical events but requires opt-in, the parallel delivery logic must handle the opt-in check — but this conditional is not described anywhere in the routing architecture. It's unclear whether the system attempts SMS and filters at the channel router, or whether SMS is excluded from the channel list before routing begins.