## Real Problems with This Proposal

### 1. The DAU/MAU Paralysis Is Self-Defeating

The document repeatedly warns that nothing should be provisioned until the DAU/MAU ratio is resolved in §9, but then proceeds to make dozens of specific infrastructure decisions anyway — Redis pub/sub architecture, SQS, WebSocket topology, token management rules, email provider selection. If the ratio truly blocks everything, the document shouldn't exist in its current form. If it doesn't block those decisions, the warnings are overcautious and will cause the team to wait 14 days unnecessarily. The document can't have it both ways.

### 2. The 99.9% Availability Claim Is Circular

The proposal says the 99.9% figure is "derived from the failure mode and dependency analysis in §6.4" and that §6.4 "enumerates the failure probability and recovery time of each system component." But §6.4 doesn't appear in the provided document. The availability number is asserted in §1.3 without the supporting analysis being present. This is exactly the problem the document claims to avoid — the target and the derivation are decoupled.

### 3. Critical Parallel Dispatch Creates an Unacknowledged Duplicate Delivery Problem

The document claims duplicate delivery for Critical notifications is a "product decision" accepted by Jordan Rivera, but the mitigation offered — idempotent copy phrasing — does not address the actual problem. A user receiving three simultaneous SMS, push, and email messages for a 2FA code will find the code in one of them and ignore the others, but the SMS charges are incurred three times per security event. At scale, if security events are even modestly frequent, this multiplies SMS costs by up to 3x with no mention in the cost projections. The SMS cost analysis in §2.1 explicitly says SMS "does not scale directly with DAU/MAU ratio" but ignores this per-event multiplication entirely.

### 4. The 15 Events/DAU/Day Figure Is Completely Unexamined

This number is listed as coming from "industry averages" but receives none of the sensitivity analysis given to DAU/MAU. It is the second multiplier in every throughput calculation. A messaging-heavy app might generate 50–100 events per DAU per day. A content-discovery app might generate 5. The document acknowledges DAU/MAU can vary 4x (15% to 60%) but treats 15 events/DAU as fixed. The throughput calculations are therefore not just sensitive to one unknown — they're sensitive to two unknowns that compound.

### 5. The WebSocket Concurrent Connection Calculation Contains a Hidden Assumption

The calculation assumes sessions are uniformly distributed across a 16-hour active window. This directly contradicts the peak multiplier analysis in §1.1.2, which explicitly models traffic concentration during evening hours. If sessions are concentrated in a 4-hour evening window rather than spread across 16 hours, the concurrent connection estimate of 62,500 is off by roughly 4x — peak concurrent connections would be closer to 250,000, not 62,500. The document correctly handles this concentration effect for throughput calculations but ignores it entirely for WebSocket sizing.

### 6. Redis Pub/Sub Fan-Out Math Is Wrong or Incomplete

The document calculates "~6,240 wasted lookups/second across the fleet" during peak, but this assumes each published notification goes to exactly one user's channel. In practice, a single user action (e.g., a popular post getting 500 likes in a minute) generates 500 separate notifications to 500 separate users. The pub/sub rate of ~1,040 events/second is the notification generation rate, not a fan-out-adjusted figure. The actual wasted lookup rate is 1,040 × (N-1) where N is instance count, which is what the document calculates — but the document then says this is "negligible" without acknowledging that at 20 instances the wasted work becomes 19,760 lookups/second, and the threshold for revisiting is vaguely set at "significantly beyond 20 instances" with no justification for that number.

### 7. Token Soft-Delete Logic Has a Race Condition That Isn't Addressed

The document describes two invalidation paths: 90-day soft-delete and hard-delete on FCM/APNs invalid-token error. It explains why both exist. But it doesn't address what happens when a token is soft-deleted while a notification dispatch is in flight. If the soft-delete runs between the eligibility check and the actual FCM/APNs call, the dispatch proceeds to a token that has just been marked inactive. The worker receives either a successful delivery or an invalid-token error. In the success case, the delivery is recorded against a soft-deleted token, creating an inconsistency. This isn't a theoretical edge case — it's a standard TOCTOU problem in any system that checks eligibility before acting.

### 8. The Email Section Is Incomplete and Cut Off

Section 2.4 ends mid-sentence: "This is not a set—". This is not a minor formatting issue. The document explicitly calls out deliverability management as a real tradeoff that "must be managed actively," then provides no guidance on what that management entails. For a team of 4 engineers, SES deliverability management (IP warming, bounce rate thresholds, complaint feedback loops, suppression list maintenance) is non-trivial operational work. Cutting off here leaves the most operationally risky part of the email channel completely undocumented.

### 9. The 5-Device Token Limit Has No Enforcement Mechanism Described

The document states "one user may have up to 5 active device tokens" but provides no description of what happens when a user attempts to register a 6th device. Is the oldest token evicted? Is registration rejected? Does this interact with the 90-day soft-delete threshold — i.e., does a stale token count against the limit? This is not an edge case; users who reinstall apps or switch devices regularly will hit this limit, and the behavior at the boundary determines whether tokens accumulate silently or are managed correctly.

### 10. The Escalation Procedure (§10) and Open Decisions (§9) Are Referenced but Not Present

The document references §9 as the location of the two open decisions that block all provisioning, and §10 as the escalation procedure. Neither section appears in the provided document. Given that the entire document's validity is staked on §9 resolution, omitting it is a significant structural problem — reviewers cannot evaluate whether the open decisions are correctly scoped or whether the resolution criteria are well-defined.

### 11. The "Product Review on [DATE]" Placeholder Is a Governance Gap

The parallel dispatch decision for Critical notifications — acknowledged as a product tradeoff with real UX and cost consequences — is attributed to a product review on "[DATE — to be filled before publication]." This is not a minor placeholder. It is the justification for a deliberate design choice that will generate duplicate SMS charges and simultaneous multi-channel interruptions for security events. If the date is unfilled, the review may not have happened, and the decision may not actually be confirmed. The document is treating an unconfirmed decision as confirmed.