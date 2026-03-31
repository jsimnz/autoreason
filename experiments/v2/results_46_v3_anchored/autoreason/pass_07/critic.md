## Real Problems with This Proposal

### 1. The "35%/30 scenario requires redesign" is unexamined but consequential

The document explicitly acknowledges that the highest-engagement scenario (6,757/sec) "requires horizontal scaling" and "redesign," then dismisses it by saying product success would justify the investment. But the architecture commits to Redis sorted sets and per-channel queues now. If Redis sorted set operations become the bottleneck at 6,757/sec, "horizontal scaling" is not a straightforward answer — Redis sorted set operations don't scale horizontally the way stateless workers do. The document waves at a problem it hasn't analyzed.

### 2. The opt-out race condition sign-off is structured to obscure the actual risk

The document asks legal and product to sign off on "residual risk after mitigations," but never quantifies the staleness window, the expected frequency of opt-out violations, or what a violation actually means legally. "Sign off on residual risk" without a number attached is asking stakeholders to accept undefined liability. This is a liability transfer disguised as transparency.

### 3. The email volume model is asserted, not derived

"35% of MAU per day = 3.5M emails/day" appears with no derivation. The document says this is "an explicit modeling assumption" but the 35% figure has no source, no sensitivity analysis, and no connection to any stated product behavior. The push/SMS models show their work; the email model does not. Email is also the highest absolute volume channel at the planning basis, making this the largest unexamined number in the document.

### 4. The Default C escalation path names no one

The document says Default C escalates to "[named executive]" but that bracket is never filled in. A pre-approved escalation path that depends on an unnamed person with unstated availability provides no actual protection. If this document is finalized with that bracket empty, Default C is not a real option.

### 5. The 2-hour peak window assumption is not defended

The entire throughput model depends on 90% of push/in-app volume concentrating in two 2-hour windows. For a social app with global users, this assumption may be wrong — timezone distribution could flatten peaks significantly, or a viral content event could create a spike outside those windows entirely. The document applies sensitivity analysis to DAU/MAU ratios and notifications-per-user but treats the peak concentration model as a constant. A 60% concentration figure instead of 90% changes the sizing target meaningfully.

### 6. The suppression/queue boundary description contradicts itself

Section 1.2 says E3's suppression layer "produces a boolean (deliver/suppress) and a channel list" that E1 consumes. But Section 2.1's data flow diagram shows preference check and suppression check both happening inside the Notification Router, not as a prior stage. It's unclear whether suppression is a separate service, a library called by the router, or logic embedded in the router. The ownership table and the architecture diagram describe different systems.

### 7. Four engineers, six months, and the monitoring overhead estimate is suspiciously precise

The document claims queue monitoring overhead is "estimated at 2–3 engineer-weeks across the build phase." This figure is used to justify a foundational architectural decision (per-channel queues), but there's no breakdown of where those weeks go. Alerting rules, runbooks, DLQ triage procedures, and the cross-cutting ownership described in Section 1.2 suggest the actual ongoing operational load is higher than a one-time build cost. The estimate is doing rhetorical work it hasn't earned.

### 8. The Month 2 calibration checkpoint has no defined measurement methodology

The checkpoint compares "actual vs. planned" volume, but the document doesn't specify how actual volume will be measured — what metrics, what time windows, what counts as the comparable unit. If push notifications are counted at enqueue time by one engineer and at delivery confirmation by another, the comparison is meaningless. The checkpoint is described as a decision gate but has no defined inputs.

### 9. The SMS cost framing buries the worst case

The executive summary says a 2× spike for a full day adds "at most ~$1,600 above the daily baseline," which sounds trivial. But the body of the document acknowledges that the 40% login rate / 20% OTP rate scenario produces $33–40K/month in ongoing costs — roughly double the planning basis estimate. The executive summary's spike framing directs attention away from the scenario where the baseline itself is twice as expensive as presented.

### 10. "Debuggable by an on-call engineer at 2am" is stated but not demonstrated

This claim is made for the chosen infrastructure stack. But the document then describes a system where on-call responsibility is split across four engineers with different domains, DLQ triage requires distinguishing APNs invalid tokens from FCM 503s from Twilio carrier rejections, and the suppression/queue boundary is owned jointly by two engineers. The 2am debuggability claim is not consistent with the operational complexity honestly described elsewhere in the same document.