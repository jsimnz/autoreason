## Real Problems

### 1. The "Single Priority Queue" Claim Is Contradicted by the Design

The executive summary calls this "a single priority queue," but §1.1.4 mentions "priority queue placement" for time-sensitive notifications, and §2.2 is referenced but not included. The document already assumes multiple priority tiers. The core architectural claim is internally inconsistent before the architecture section even appears.

### 2. The 21-Minute Delay Is Declared Acceptable Without Justification

The backlog clearance arithmetic shows a 21-minute worst-case delay for social notifications. The document asserts this is "acceptable" but provides no basis — no user research, no product requirement, no comparison to what competitors deliver. For a social app where "like" notifications drive re-engagement, 21 minutes may destroy the product's core engagement loop. This is a product decision being made silently inside an infrastructure document.

### 3. The Correlated Variable Model Is Circular

The DAU/MAU-to-notification-rate correlation argument claims structural validity, but the specific numbers (8, 17, 28, 40 notifications/DAU) are not derived from the benchmarks cited — the document admits they are "judgment calls within those constraints." The benchmarks are then used to provide apparent legitimacy to numbers that were chosen independently. This is circular: the benchmarks constrain the range, the numbers are picked within the range, and the benchmarks are cited as the basis.

### 4. The Email Cost Dwarfs Push Despite Being 3.7% of Volume

Email at $1,500/day ($547K/year) is 48x the per-notification cost of push and represents roughly 48% of total channel cost despite handling 3.7% of volume. The document never questions whether the email volume justification, channel design, or vendor selection warrants this cost asymmetry. SendGrid Pro is assumed without evaluating whether the volume (1.9M/day) fits a lower pricing tier or alternative vendor.

### 5. The 5% Rollout Cannot Validate the Burst Assumption

The document explicitly states the 3× burst multiplier is a judgment call, and that the production rollout will surface whether it's adequate. But a 5% rollout generates 5% of real traffic. A viral spike at 5% scale is not a viral spike — the high-follower account with 100K followers reaches 5,000 users in the rollout. The burst behavior the document is trying to validate cannot manifest at 5% exposure. The rollout validates steady-state, not spikes.

### 6. The Stop Thresholds Have No Recovery Criteria

The rollout stop thresholds specify when to pause but not what constitutes a resolved state. "The on-call engineer and EM decide whether to investigate and resume or abort" is not a criterion — it's a delegation of the decision. A team of four engineers, presumably under launch pressure, has no defined bar for what "resolved" means before resuming. This is the condition most likely to result in a bad call under pressure.

### 7. Redis as Both Queue and Cap Enforcement and Preference Cache Is a Single Point of Failure

The document uses Redis (ElastiCache) for the notification queue, the SMS cap atomic counter, the global SMS cap counter, and the preference cache (>95% hit rate dependency). These are four separate critical functions with different failure modes consolidated onto what appears to be a single Redis deployment. The document discusses Redis queue sizing but never addresses what happens to cap enforcement or preference lookups if the Redis instance is unavailable. ElastiCache r6g.xlarge is mentioned as singular.

### 8. The Lua Script TTL Edge Case Is Acknowledged but the Monitoring Claim Is Unspecified

The document admits the NTP/clock-drift edge case "is not fully eliminated by the script alone" and says they'll monitor for "unexpected count resets." No definition of what an unexpected count reset looks like in a monitoring system, what the alert threshold is, or how it would be distinguished from a legitimate midnight rollover. The mitigation is named but not designed.

### 9. The Staffing Model Is Referenced but Absent

Section §7 is referenced multiple times as containing engineer-to-work mappings, interface contracts, and explicit sequencing. It is not included in this document. For a proposal whose credibility rests partly on the claim that four engineers can execute this in six months, the absence of the staffing section means the central feasibility argument cannot be evaluated.

### 10. IP Warming Timeline Assumes SendGrid Account Procurement Already Complete

Email IP warming starts "month 1, week 3" as a prerequisite for the email channel going live six weeks later. IP warming requires a provisioned SendGrid account, a dedicated IP (not available on all tiers), DNS configuration, and initial domain authentication. The document treats procurement and provisioning as already done. If SendGrid account setup, dedicated IP provisioning, or SPF/DKIM/DMARC configuration takes longer than three weeks — which is common in organizations with procurement processes — the email channel launch date slips with no contingency.

### 11. The "Atomic" Global SMS Cap Has a Sequencing Gap

Section 1.2.2 begins describing the fallback sequencing for the global SMS cap but is cut off. What exists states the router "determines the notification requires SMS" and then stops. The document promises a sequencing that prevents race conditions for the global cap but does not deliver it. The per-user Lua script is specified; the global cap mechanism is not.