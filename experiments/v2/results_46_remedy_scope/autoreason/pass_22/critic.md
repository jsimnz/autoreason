## Real Problems with This Proposal

### 1. The 16-Worker-Type Complexity Is Understated

The document claims "sixteen logical worker types, one deployable binary" and calls this a simplification. But 4 channels × 4 priorities means sixteen distinct Kubernetes deployments, each with its own replica count, resource limits, HPA configuration (month 2), and label selectors. The traffic response matrix already shows operators manually scaling push-worker, inapp-worker, and email-worker as separate commands. With 4 engineers over 6 months, the operational surface area of sixteen deployments is a real burden that the framing as "one binary" obscures. The document acknowledges "deployment complexity tradeoffs are in Section 3.3" but Section 3.3 is not included.

### 2. FCM Rate Limit Is Load-Bearing but Unverified

The document explicitly states FCM rate limits are not contractually specified and that if the actual limit is below 2,000/sec "the P1 protection claims in this document are materially wrong." The entire priority queue architecture's credibility for push notifications — 70% of volume — rests on a number the team does not have. This is not a minor caveat. The P1 delay figures in Section 1.4 (referenced repeatedly as planning estimates) cannot be validated without it, yet the document proceeds to build a traffic response matrix, worker pool sizing, and escalation thresholds on top of that unknown.

### 3. The Month-1 Missed-Checkpoint Default Is Dangerous

The procedure for a missed month-1 review tells the on-call rotation owner to scale deployments within 24 hours using hardcoded replica counts. The justification for those specific numbers (push-worker to 12, inapp-worker to 6) is not provided. More seriously, this procedure fires regardless of what actual traffic looks like — it could scale up a system that is running well below plan, wasting resources, or scale a system that is already in the 80M+/day band where those replica counts are insufficient. The "verify deployment names" guard is not a substitute for traffic-conditional logic.

### 4. The Correlated Sensitivity Table Has an Internal Contradiction

The document states that DAU/MAU ratio and notifications-per-user are positively correlated and that treating them independently understates high-engagement risk. The sensitivity table then uses a 3× peak multiplier uniformly across all rows. But if high-engagement scenarios also imply different user behavior patterns (more real-time interaction, more evening concentration), the peak multiplier itself should vary by row. Using a fixed 3× across scenarios while explicitly noting correlation risk is inconsistent.

### 5. Per-User Rate Limit Justification Is Circular

The 20 notifications/hour limit with burst of 5 is described as derived from research showing degradation above "approximately 15–25 notifications/hour." The chosen limit of 20 sits in the middle of that range with a "conservative margin" that is not defined. A burst allowance of 5 means a user can receive 25 in a short window, which exceeds the upper bound of the cited research range. The document then marks this as a product decision required, but the engineering team has already embedded a specific value in the implementation. The product team is being asked to confirm a number that is already built in.

### 6. Redis Failover During a Traffic Event Is Worse Than Presented

The Option B degraded window is described as "15–30 minutes" and "recoverable, documented procedure." But the scenario where Option B failover is triggered is precisely a traffic spike — meaning the system is already under stress when operators must execute a replica promotion. The document does not address what happens to in-flight queue entries during the promotion window, whether the processing sorted set state is preserved across the failover, or how workers behave when Redis is temporarily unavailable. "Recoverable" is asserted but not demonstrated.

### 7. The Deduplication Mechanism Description Is Ambiguous

The document describes two separate deduplication mechanisms with separate memory bounds: a per-user 60-second sliding window, and a system-wide delivered-ID set for cross-channel deduplication. The interaction between these two mechanisms is not explained. It is unclear which one fires first, whether a notification suppressed by the sliding window is recorded in the delivered-ID set, and whether the 60-second window resets on suppression or only on delivery. For a system where worst-case outcome is duplication rather than loss, the deduplication logic is under-specified.

### 8. The Fanout Cap Creates an Undocumented Consistency Problem

Followers beyond position 10,000 receive notifications up to 5 minutes later. The document frames this as a product-visible latency issue. It is also a consistency issue: during those 5 minutes, some followers have seen a notification about content (a post, a comment, a follow) while others have not, and users in the first batch may have already acted on it. For a social app, this is not just a delay — it affects social interactions. The document does not flag this as a product decision about consistency semantics, only about latency acceptability.

### 9. Section 1.4 Is Referenced Repeatedly but Not Present

The document references Section 1.4 for P1 delay figures, load test owner, schedule, and launch gate at least five times in the first two sections. That section is not included. Readers are told to treat figures as planning estimates until a load test is signed off, but cannot verify what those figures are, who owns the test, or what the gate criteria are. This is a structural gap, not a placeholder issue — the document's own guidance about how to read it cannot be followed.

### 10. The 4-Engineer Constraint Has No Staffing Impact Analysis

The document mentions 4 engineers and 6 months in the title and executive summary and nowhere else. There is no analysis of what 4 engineers can realistically build, operate, and validate in 6 months given sixteen worker deployment types, a pre-production load test, HPA deployment and validation in month 2, sharding pre-staging in month 3, per-channel per-priority monitoring, and an on-call rotation. The on-call rotation owner is a named deployment gate, but with 4 engineers, that person is also building the system. The staffing constraint is treated as a label, not a design input.