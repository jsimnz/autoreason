## Real Problems with This Proposal

### 1. The 47-Minute and 14-Minute Delay Figures Are Not Derived in This Document

The executive summary table cites §1.1.2 and §2.3 as sources for these figures. The document ends mid-table before completing §1.1.2's spike analysis, and §2.3 is never reached. The "derivation is complete" claim in the Document Status section is false based on the content actually present. Stakeholders are being asked to sign off on figures whose derivations don't exist in this document.

### 2. The Spike Phase Analysis Is Internally Inconsistent

The document claims "at the average burst rate, workers keep pace with the spike" and "the queue does not grow unboundedly." But Phase 1 explicitly shows 1,062,000 notifications accumulating in the queue. If the queue absorbs over a million notifications during Phase 1, workers cannot simply "keep pace" — they must process the Phase 1 backlog *in addition to* ongoing Phase 2 arrivals. The 47-minute delay figure presumably accounts for this, but the Phase 2 narrative contradicts it by claiming equilibrium. The document cannot simultaneously assert the queue drains cleanly and that standard-priority delays reach 47 minutes.

### 3. The 4× Instantaneous Multiplier Is Applied to an Already-Multiplied Rate

The document defines average burst rate as 3× primetime, then applies a 4× instantaneous multiplier to that figure, yielding 12× primetime as the t=0 peak. The Firebase reference data cited supports 3–5× spike-to-sustained ratios. A 12× figure is not supported by any cited source and is not flagged as an extrapolation. The 200MB memory figure and Phase 1 queue accumulation calculation both derive from this uncalibrated compound multiplier.

### 4. The Email Volume Correction Undermines the Document's Own Stress Case

The document correctly identifies that viral events suppress email dispatch because session activity is elevated. It then uses 60% as the email-eligible fraction during viral events. But the total daily volume figure of 34.6M is what drives worker sizing and the delay calculations. If email volume drops during the exact spikes that stress the system, the spike arrival rate is lower than the model assumes — the delay figures are derived from a volume that partially cancels itself out during stress conditions. This interaction is not reconciled anywhere.

### 5. The "Channel Exclusivity" Correction Is Incompletely Applied

The document retracts the 51M figure on the grounds that the prior model double-counted channels by not accounting for routing exclusivity. But the revised 34.6M figure still adds push (26.5M) and email (8M) as separate dispatch operations, treating them as non-overlapping populations. The routing rule in §3.1 routes email only to users not in active session — but push notifications are sent regardless of session state. A DAU who is in-session receives both an in-app notification and a push notification for the same event. The document does not clarify whether push and in-app are counted separately or whether the 26.5M push figure already excludes in-session users. If push fires regardless of session state, the exclusivity argument used to correct the email double-count does not apply to push.

### 6. The Default Decision Mechanism Creates Unacknowledged Risk

Decision A defaults to implementing Option A (dedicated high-priority worker pool, ~3 engineer-weeks) if no sign-off occurs within 14 days. Decision B defaults to Redis Sentinel. These defaults are presented as conservative choices, but the combination — if both time out — consumes 3 engineer-weeks and locks the Redis architecture simultaneously, without any explicit acknowledgment that both could time out concurrently. On a 6-month timeline with 4 engineers, a silent 3-engineer-week commitment triggered by inaction is a significant untracked risk.

### 7. The Validation Gate Is Structurally Circular

The pre-launch validation gate (§4.3, referenced but not present in the document) is supposed to measure actual worker throughput and calibrate the spike multiplier. But the delay figures requiring sign-off (Decision A) are derived from the uncalibrated model. Stakeholders are being asked to approve or reject latency figures before the measurements that would validate those figures are taken. The document acknowledges the 200MB figure is a placeholder pending spike injection testing, but does not apply the same caveat to the delay figures, which depend on the same uncalibrated multiplier.

### 8. The Primetime Window Assumption Is Not Justified for the Stress Case

The model uses a single 4-hour US primetime window (14:00–18:00 local). For a social app with viral notification dynamics, the stress case is not predictable daytime primetime — it is an off-hours viral event when the worker pool is sized for low load and a spike arrives unexpectedly. The 47-minute delay is derived assuming the spike occurs during primetime when the queue already has load. An off-hours spike against a lightly loaded queue would behave differently, but a spike during a secondary international peak (if the app has any non-US users) could be worse. The document does not address this.

### 9. The DAU/MAU Ratio Is Asserted Without Sensitivity Analysis

The model uses 3M DAU against 10M MAU, a 30% ratio, as the base case. The push volume (26.5M/day), which drives 77% of total volume, is calculated against DAU. The document provides sensitivity analysis on push opt-in rate but not on the DAU/MAU ratio itself. A 40% DAU/MAU ratio (4M DAU) would increase push volume by 33%, pushing primetime rates from 840/sec to ~1,120/sec and materially changing the spike analysis. This is a larger uncertainty than the opt-in rate sensitivity that is analyzed.

### 10. The Retraction Language Overstates the Reliability of the Replacement Figures

The Document Status section frames the 51M→34.6M and 35/sec→30/sec corrections as resolutions of prior errors, implying the replacement figures are now correct. But the 34.6M figure still rests on the uncalibrated DAU/MAU ratio, the unvalidated notifications-per-DAU assumption, and the session-correlation model that is acknowledged to be a judgment call. The 30/sec figure rests on a latency budget where the dominant term (provider API call at 15–40ms) has a 2.7× range. Correcting arithmetic errors does not make the underlying estimates reliable, and presenting corrections as resolutions may cause reviewers to treat the new figures with more confidence than is warranted.