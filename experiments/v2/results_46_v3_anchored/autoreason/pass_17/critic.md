## Real Problems with This Proposal

### 1. The "Default A" Math Is Wrong

The document claims Default A reduces effective peak demand by 10–13% by throttling Tier 3 to 71% throughput, and that Tier 3 is 35–45% of push volume. The math: 0.35–0.45 × (1 – 0.71) = 10–13%. That's correct as stated. But the problem is that Default A activates at 2,550/sec, which already exceeds the 2,650/sec ceiling by only 100/sec — a 3.8% overage. Reducing demand by 10–13% at that point brings it to 2,220–2,295/sec, which the document claims is "within the ceiling." But the ceiling was already exceeded when Default A triggered. The document never addresses what happens during the 8-minute rolling restart window while the system is already above ceiling. That's not a minor gap — it's the exact moment the procedure is supposed to protect against.

### 2. The Batching Reduction Claim Is Unsubstantiated

Section 1.1 states that batching reduces push volume by "40–60%" during load shedding, calling it "the highest-leverage lever available." But earlier in the same section, the document says batching reduces raw events (7.5–23/DAU/day) to effective delivered (8–14/DAU/day). That's a reduction of roughly 6–39% depending on where you are in the range. The 40–60% figure during spikes is never derived or justified. During a viral spike, the spike is concentrated on high-engagement content — exactly the content least likely to be batch-eligible, since batch windows depend on time between events per recipient, not total platform volume. The 40–60% figure may be optimistic precisely when it matters most.

### 3. The Trigger Design Still Has the Flaw It Claims to Fix

The document explicitly identifies the flaw: "A trigger set at 13/DAU/day fires after the ceiling is already breached." It then introduces throughput-based triggers and claims this fixes the problem. But the reassessment trigger fires at a 3-day rolling peak of 2,400/sec, and the process takes 3 days to reach a stakeholder decision, plus 3–5 business days to provision capacity under option (a). That's 6–8 days minimum from trigger to relief. The ceiling is 2,650/sec. The trigger fires at 2,650 × 90.6% = 2,400/sec. If the rate is rising, the ceiling can be breached well within that 6–8 day window. The document acknowledges the original trigger problem but doesn't demonstrate that the new trigger provides enough lead time.

### 4. The Headroom Reconciliation Contradicts Itself

The document says the 25% volume buffer "sounds substantial" but "is not equivalent to a 25% throughput buffer," and correctly shows that a 25% volume increase produces a 3,175/sec peak exceeding the 2,650/sec ceiling. It then says the 25% buffer is "the distance between the current planning basis and the point at which worker capacity must already have been added." But the emergency threshold is set at 2,550/sec — which is only a 0.4% increase over the 2,540/sec current peak. The "25% buffer" framing is effectively abandoned, and the actual operational buffer between current peak and emergency threshold is less than 1%. The document never reconciles why it presents a 25% volume buffer as meaningful given this.

### 5. The Densification Rate and the Trigger Are Never Connected

The document correctly notes that the densification rate will be observable within 4–6 weeks of launch. It also establishes throughput-based triggers. But it never specifies what happens if the observed densification rate, once measured, implies the ceiling will be breached before the reassessment process can complete. The reassessment process is reactive (triggered by observed throughput). If densification is at 1.5/DAU/day/quarter, the ceiling breach at High DAU is approximately 4 months out from launch. The 4–6 week measurement window means you'd have roughly 10–12 weeks of lead time — enough to act. But the document doesn't establish a forward-projection step after the rate is measured. You get the rate, then apparently wait for the throughput trigger to fire.

### 6. The Sign-Off Table Has an Internal Inconsistency

The "Escalation default for capacity overruns" item lists the decision deadline as "Before finalization" with the consequence "Default A activates automatically." But Default A is defined as an operational procedure that activates at 2,550/sec emergency threshold — it doesn't require a stakeholder decision to activate. The sign-off item appears to be about something different (which option to select during reassessment), but the document conflates the two. If Default A activates automatically regardless, what exactly requires sign-off here? The table entry is either redundant or misdescribed, and the distinction matters because it's presented as a hard gate.

### 7. The Compliance Architecture Decision Has Asymmetric Risk That Isn't Disclosed

The document states that if no decision is received by end of Week 2, the conservative architecture (synchronous preference check) activates as default. It notes this carries "a latency penalty documented in Section 2.4." But Section 2.4 is referenced, not summarized. The sign-off table doesn't quantify the latency penalty, so stakeholders reading only the executive summary cannot assess the cost of inaction. For a decision framed as a hard gate with an automatic default, the consequence of that default should be quantified where the deadline appears — not deferred to a section reference.

### 8. The "Micro-Spike Absorbed by Queue Depth" Claim Is Unchecked

The spike table says micro-spikes (less than 5x normal rate) are "absorbed by queue depth; no action required." But the load-shedding threshold is 450,000 messages. At 2,540/sec peak, a 5x spike on even 10% of users produces roughly 1,270/sec of additional load. Over one hour, that's 4.5M additional messages — ten times the shedding threshold. The claim that micro-spikes are absorbed by queue depth is only true if "micro-spike" means something much smaller than 5x normal rate for affected users, or if affected users are a much smaller fraction than 10%. The classification boundary is inconsistent with the load-shedding math.

### 9. The Engineer-Week Budget Is Mentioned But Not Shown

The executive summary states "the described work fits within 96 engineer-weeks under the base case" and points to Section 1.3. But this document ends before Section 1.3 appears. Within what's presented, option (b) (batching changes) is said to consume "approximately 2 engineer-weeks from the active workstream" — but there's no accounting visible to verify the 96-week claim or assess how tight the budget actually is. The self-hosted email fallback is identified as a budget-breaker, but without the actual breakdown, the claim is unverifiable from this document.

### 10. The Hysteresis Justification Proves Too Much

The document argues for an asymmetric deactivation threshold (450k activate, 200k deactivate) to prevent oscillation. The reasoning is sound. But the document never addresses the user experience implication: notifications are held until queue depth drops to 200,000, which at normal throughput rates means a delay of roughly (450,000 – 200,000) / 2,540 ≈ 98 seconds after the spike passes before shedding deactivates. During that ~98 seconds, held notifications begin releasing. But the document elsewhere accepts "up to 2 hours" delay for likes and comments during major spikes. There's no analysis of what the actual delay distribution looks like for held notifications — the hysteresis band is justified operationally but its user-facing implications aren't examined.