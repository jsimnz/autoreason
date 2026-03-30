## Real Problems

### 1. The Core Validation Catch-22 Is Unresolved

The document acknowledges the cohort cannot confirm the 17/day ceiling, only detect large overruns. But the decision gate at ≤17/day says "proceed with procurement." This means the system is procured based on a number the document explicitly says cannot be confirmed. The acknowledgment of the problem does not fix the problem — it just documents it. The entire validation section is intellectually honest about an epistemic hole that the design then proceeds to ignore in the action column.

### 2. The Tier Weight Assumption Is Load-Bearing and Has No Validation Path

The document flags that 15/35/50 is plausible and produces materially different infrastructure requirements (~49 P1 workers, ~81M notifications/day). It says "revisit at month 3." But the cohort validation at week 2 cannot measure tier weights because of the sparsity problem already described. Month 3 is after procurement. There is no mechanism to validate tier weights before the infrastructure decisions that depend on them are made. The document names the risk and provides no actionable path to resolve it before commitment.

### 3. The 350/sec Per-Worker Assumption Is Never Justified

Worker counts throughout the document derive from a 350/sec per-worker throughput figure. This number appears in Section 1.3 references but its basis is never stated. It is not a benchmark, not a measurement, not a reference to a comparable system. Every worker count calculation — including the 5× headroom analysis, the 35% DAU/MAU stress test, and the 15/35/50 tier split scenario — inherits this assumption silently. If the actual figure is 200/sec, the headroom analysis in the 35% scenario ("headroom holds at 5×") is wrong.

### 4. The Interim Operating Mode Arithmetic Has an Unacknowledged Contradiction

Section 1.2a argues that a 1,500/sec controlled release rate exceeds post-suppression arrival of ~875–1,050/sec, enabling queue drain. But it also states the drain time for a 1.575M-item batch is 42–58 minutes, and the next batch begins accumulating during this drain. If drain takes up to 58 minutes and batches release every 15 minutes, there are up to three batches accumulating simultaneously before the first finishes draining. The queue does not shrink monotonically — it grows in steps. The document does not analyze whether the queue reaches a stable equilibrium under this overlap condition or grows without bound.

### 5. The False Positive Protection for the >5× Decision Is Operationally Implausible

The document says the rebuild decision requires "two consistent measurements or one measurement with a clear mechanistic explanation," with a second measurement in week 3 using a larger cohort sample "if available." A >5× overrun means observed rates above 85/day. At that level, the system is already under severe stress. Waiting an additional week for a confirmatory measurement while the infrastructure is running at 5× over ceiling — and while the rebuild decision is already facing a 5–7 month gap — is not a conservative safeguard. It is a delay that consumes the most valuable weeks of response time.

### 6. Auth SMS Exemption Creates an Unmonitored Cost Vector

The document states auth SMS is exempt from the budget cap and tracked on a separate counter. It does not specify: what the separate counter's limit is, who reviews it, at what frequency, or what triggers action. Auth SMS volume is a function of login attempts, which can be manipulated by credential stuffing or SMS pumping fraud. An exempt, separately tracked counter with no stated ceiling or review cadence is an open cost exposure. The document identifies the problem with the original design (push fallback doesn't work) but the replacement has no defined upper bound.

### 7. The LIFO "Accidental Feature" Framing Obscures a Real Delivery Guarantee Problem

The document describes Redis Lists BRPOP LIFO behavior under accumulation as "likely an accidental feature rather than a defect" for social notifications. But it does not define what "multi-minute accumulation" means in terms of queue depth, nor does it specify what happens to items that age past any defined threshold. If a P1 notification sits at the bottom of a LIFO queue during a spike, it may never be delivered until the queue drains — which could be the 42–58 minute window described in Section 1.2a. The document acknowledges the tradeoff is "unacceptable" in some cases but defers the definition of those cases to Section 2.2, which is not included in this document.

### 8. The Month-3 Tier Weight Revisit Has No Stated Decision Criteria

The document says the tier weight assumption "must be revisited at month 3." It does not state: what data will be available, what measurement methodology will be used, what threshold triggers infrastructure changes, who owns the decision, or what the lead time is for acting on the finding. Month 3 is the midpoint of a 6-month timeline. If the revisit at month 3 finds the 15/35/50 split is correct, the time remaining to procure and configure additional infrastructure before launch is approximately 3 months. Whether that is sufficient is not addressed.

### 9. The Scenario A Alert Replacement Loses Information Without Acknowledgment

The document replaces the paging alert for 20× instantaneous spikes with a "non-paging observability record" on the grounds that the event is over before intervention is possible. This is true for the spike itself. But a 20× instantaneous spike is also a signal that something in the content graph produced an extreme fanout event — which may recur. Downgrading it to a non-paging record means engineers reviewing it are doing so on a delayed, non-urgent basis. The document does not address how recurring Scenario A patterns are detected or escalated, or whether a second occurrence within a short window would still not page.

### 10. The 4-Engineer Operational Surface Acknowledgment Has No Specifics

The document states "the operational surface is at the edge of what 4 engineers can safely own" and defers to Section 7, which names what is cut and why. Section 7 is not present in this document. This is the single most consequential staffing constraint in the design, and its analysis is entirely absent. The statement that it is "at the edge" without defining what is cut means every other section's operational assumptions — on-call response times, capacity review windows, the week-3 confirmatory measurement, the month-3 revisit — are made without knowing which engineer owns them or whether that engineer has capacity.