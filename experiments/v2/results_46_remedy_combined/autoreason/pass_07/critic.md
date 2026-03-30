## Real Problems with This Proposal

### 1. The 35% DAU/MAU Assumption Is Load-Bearing and Unexamined

The document acknowledges "35% is a planning assumption, not a measurement" but then uses 3.5M DAU as the foundation for SMS cost models, OTP rate limiting, in-app volume estimates, and alarm thresholds. The SMS alarm tiers ($2,000 advisory, $4,000 warning) are calibrated against the $1,383 baseline, which is directly derived from the 35% figure. If actual DAU is 50% of MAU (5M), the baseline shifts to ~$1,975/day and the advisory alarm fires on day one as a false positive. The proposal identifies this as a measurement gap but makes no adjustment to the alarm thresholds to account for the uncertainty range.

### 2. The WAND Segment Problem Is Worse Than Acknowledged

The proposal correctly flags WAND as the largest unknown, but the "Week 1 measurement plan" has a logical gap. WAND is defined as "weekly-active-not-daily," which requires at least 7 days of session data to compute — you cannot measure it in Week 1. The plan to "instrument WAND segment size from actual session data in the first week" cannot produce a valid WAND cohort until the end of Week 1 at earliest, and a stable estimate requires multiple weeks. The proposal then says infrastructure is provisioned for the aggressive scenario "to avoid re-provisioning during early growth," but the aggressive scenario (1.3M/day) is 10× the conservative scenario (120K/day). Provisioning for a number that could be wrong by 10× in either direction is not a risk mitigation — it's an acknowledgment that the model is not useful.

### 3. The P1 Peak Factor Is Asserted Without Justification

The proposal uses a "peak factor of 5×" for social app traffic to calculate worst-case P1 throughput. This number appears once with no source, no sensitivity analysis, and no reference to whether it applies to per-queue throughput or aggregate throughput. The entire FIFO sharding decision — 4 shards at launch, scaling trigger at 2,000 messages/second per shard — depends on this factor being approximately correct. If the real peak factor is 8× or 10× (plausible for a social app with time-zone-concentrated evening usage), the high-scenario peak calculation of 2,425 messages/second becomes 3,880–4,850 messages/second, which exceeds the 4-shard ceiling of 4,000 messages/second (4 × the stated 3,000/second but actually 4 × 3,000 = 12,000, so this specific number is fine — but the proposal's own arithmetic is inconsistent: it says 4 shards gives a "combined ceiling of 12,000 messages/second" but the scaling trigger fires at 2,000/shard, implying concern well below the stated ceiling, with no explanation of why 2,000 rather than 2,900 was chosen as the trigger).

### 4. The OTP Correction Creates a New Race Condition

The proposal states the OTP rate limiter was corrected so "Redis increment now occurs only on confirmed send." This introduces a race condition: if two OTP requests for the same user arrive simultaneously, both can read a count below the limit, both proceed to send, and both increment after confirmed delivery — resulting in over-delivery before the counter catches up. The original pre-send increment had a different failure mode (overcounting on send failure) but prevented this race. The proposal presents the new logic as a straightforward fix without acknowledging the concurrency tradeoff.

### 5. The Transactional Email SLA Has No Measurement Mechanism Described

The proposal defines SLAs (password reset < 30 seconds, security alert < 60 seconds) and mentions "latency monitoring described" in the executive summary changelog. Section 6.4 is referenced but the document is cut off before it appears. The SLA definition without the monitoring mechanism is incomplete — it is not possible to evaluate whether the SLA is achievable or how violations would be detected from what is presented.

### 6. The Digest Alert Threshold Logic Is Inverted for Its Stated Purpose

The proposal says: "If digest volume exceeds 1.5M/day sustained, investigate whether a bug is sending digests to non-opted-in users before attributing it to organic growth." But 1.5M/day is above the aggressive scenario ceiling of 1.3M/day. If the aggressive scenario is the provisioning ceiling, a volume above it should trigger investigation immediately, not after ruling out bugs. More importantly, a bug sending digests to non-opted-in users is a legal/compliance problem (CAN-SPAM, GDPR), not just an operational anomaly. Framing it as something to investigate after the threshold is crossed — rather than as a condition requiring immediate halt — understates the severity.

### 7. The "Named Owner" Escalation Structure Is Not Actually Described

The executive summary states that decisions requiring authorization outside the engineering team are "identified with a named owner, a deadline, and an escalation path." The proposal references "Blocking Decision Point 1" as resolved. There is no visible structure in the presented text that shows what other blocking decision points exist, who owns them, or what the escalation paths are. The claim in the executive summary is not verifiable from the document as presented.

### 8. The Cost Table Treats SMS as Flat When It Is Explicitly Variable

The infrastructure cost table in Section 1.5 shows Twilio at "~$1,383/month" for both base and high scenarios with no delta. But the proposal's own SMS cost model in Section 1.4 shows that SMS cost varies directly with authentication event volume, which scales with DAU. The high scenario involves higher engagement, which should produce more authentication events and higher SMS costs. Listing SMS as identical in both scenarios contradicts the proposal's own modeling and makes the high-scenario cost estimate unreliable.

### 9. The Sharding Key Creates Ordering Inconsistency Across a Conversation

The proposal assigns P1 messages to FIFO shards by `hash(conversation_id) % N_SHARDS`. This means all messages in a given conversation go to the same shard, preserving per-conversation ordering. However, the proposal also states that message group IDs are "one group ID per conversation thread for P1." SQS FIFO guarantees ordering only within a message group, not across message groups on the same shard. A shard handling thousands of conversations simultaneously provides no cross-conversation ordering guarantee, which is fine — but the proposal does not address what happens when a user is a participant in multiple active conversations that hash to the same shard. Under load, head-of-line blocking within one busy conversation's message group can delay delivery for all other conversations on that shard, creating latency variance that is invisible in the throughput analysis.

### 10. The Document Is Incomplete

Section 2.3 is cut off mid-sentence: "Four queue families, each with a main queue and a—". Sections referenced throughout (6.4, the full team allocation breakdown, the complete blocking decision point list) are either missing or truncated. Evaluating the proposal's claims about transactional email infrastructure, monitoring, and team allocation is not possible from what is presented. This is not a minor formatting issue — several of the ten changelog items claim to address problems in sections that do not appear in the document.