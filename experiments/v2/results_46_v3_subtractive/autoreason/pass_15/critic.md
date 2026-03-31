## Real Problems with This Proposal

### 1. The Document Cuts Off Mid-Sentence

Section 1.6.1 ends abruptly: "On cache miss or read failure, the system can fall back to—" The architectural constraint for the fail-closed recommendation is never stated. This is the section that handles TCPA legal liability, which the executive summary explicitly calls out as escalated risk requiring a business decision. The most legally consequential section is incomplete.

### 2. The Email Worker Math Is Self-Contradictory

Section 1.3.3 states that at a 5-minute window, 4 workers handling ~8,300 emails each at 150ms would require approximately 17 workers and "triggers a worker pool review." Then it immediately states that at the current 30-minute window, 4 workers handle ~8,300 emails per window — the same number — and it "works with margin." This is impossible. The per-worker email count cannot be the same at both 5-minute and 30-minute windows given the same daily volume. The numbers are internally inconsistent, and the conclusion that the current setup works is undermined by the same arithmetic used to flag the 5-minute threshold as problematic.

### 3. The Fanout Clearance Math Assumes No Queue Backlog

Section 1.5.3 calculates P3 clearance time assuming the non-fanout half of P3 capacity (2,000 events/second) is fully available to drain the fanout output. But organic P3 events are also arriving continuously during that window. At baseline, organic P3 events arrive at roughly 14.4M/day ÷ 86,400 seconds ≈ 167 events/second. The calculation ignores this, making the 8-minute estimate for a 500,000-follower user optimistic. The margin against the 15-minute SLA is thinner than stated, and the proposal acknowledges "limited margin" without quantifying it accurately.

### 4. Bus Factor Risk Is Named But Never Specified

The executive summary mentions "bus factor remediation" for TCPA compliance as a solved problem. E1 and E3 are named as the simultaneous-unavailability risk. But nowhere in the visible document is the actual bus factor remediation described — what was done, who cross-trained, what runbooks exist. The risk is "named and escalated" but the mitigation is asserted without content.

### 5. The 1.2 Fanout Multiplier Is Inconsistent with the High-Follower Path

The 1.2 multiplier is described as accounting for actions that notify "slightly more than one person on average." But the high-follower fanout path routes flagged users' events separately. This means the 1.2 multiplier applies to the remaining population. If high-follower users generate a disproportionate share of multi-recipient events (which is definitionally true — they have more followers), stripping them out of the main pipeline and then applying a 1.2 multiplier to the remainder likely overstates the remaining population's multiplier. The traffic model doesn't account for this segmentation.

### 6. The 500-Follower Threshold Has No Stated Basis

Section 1.5.2 states the 500-follower threshold is configurable and owned by E1, but provides no derivation or rationale. Given that the entire fanout rate limit and P3 SLA analysis depends on where this threshold is set, the absence of a basis for the number is a gap in the same rigor the proposal applies to other derived values.

### 7. P2 Worker Pool Is Explicitly Unspecified

Section 1.1.2 notes that the P2 worker pool "scales with DAU volume and requires a recount at optimistic volume using the same methodology as P3." But Section 2.1, referenced as the source of the sizing derivation, is never shown. The P2 pool size at any volume is never stated anywhere in the visible document. P2 presumably covers comments, mentions, and similar mid-priority events — a significant traffic category — with no concrete capacity number.

### 8. The Opt-In Rate Assumptions Have No Stated Source

The channel opt-in rates (65% push, 20% email) are presented without any basis — no industry benchmarks cited, no internal data referenced, no sensitivity analysis. These numbers drive all downstream capacity calculations. A 10-percentage-point error in push opt-in rate changes push delivery volume by roughly 15%, which affects worker pool sizing. The proposal demands derivation rigor everywhere else but asserts these foundational inputs.

### 9. The 4-Hour Maximum Batching Window Is Unexplained

The configuration management policy sets a maximum batching window of 4 hours with no justification. At 4 hours, the digest grouping rationale still holds, but user experience implications (a user takes an action and receives no email for up to 4 hours) seem product-relevant. The proposal states product leads must sign off on the follower notification launch gate but apparently not on a batching window change that could be set to 4 hours by a single engineer with one code review.

### 10. "Horizontal Scaling" at Optimistic Volume Is Asserted Without Architecture

Section 1.1.1 states the optimistic scenario (50% DAU/MAU) is handled "with horizontal scaling — no architectural changes required." But the fanout rate limit is derived from a fixed P3 worker pool size, the queue depth burst absorption depends on absolute capacity, and Section 1.1.2 acknowledges a non-proportional worker pool recount is needed. Saying "no architectural changes required" while simultaneously requiring a non-trivial recount, re-derivation of the fanout rate limit, and validation of the P3 SLA at new tail cases is a contradiction.