## Real Problems with This Proposal

### 1. The DAU/MAU Sensitivity Table Is Internally Inconsistent

The table in Section 1.2 shows sustained inbound rates derived from 24-hour averages, but the document states the provisioned floor of ~2,500/sec is set against peak rates, not sustained averages. The table's caption says "these are sustained averages" and then immediately claims the provisioned floor "provides headroom through the 45% DAU/MAU, 25/day scenario." At 45% DAU/MAU and 25/day, the sustained average is ~1,302/sec. At a 3× diurnal peak factor, that's ~3,906/sec — which exceeds the 2,500/sec provisioned floor. The claim is false on the document's own arithmetic.

### 2. The Channel Split Percentages Don't Survive Their Own Logic

The document argues that in-app and push are substitutes: when a user is in the foreground, in-app replaces push. But the channel split treats them as if they draw from the same total notification volume independently. If 20% of events go to in-app because those users are in-session, then push should capture ~80% of the remaining events — not 71.5%. The 8.5 percentage point gap is silently absorbed by the SMS and email figures, which aren't large enough to account for it. The accounting explanation offered ("the two channels are substitutes") actually contradicts the arithmetic used to derive the split.

### 3. The Bottom-Up SMS Estimate Is Off by an Order of Magnitude from the Top-Down Figure and the Explanation Is Circular

The document acknowledges a ~5× discrepancy between the bottom-up SMS estimate (~47,000/day) and the top-down 0.5% share (~225,000/day), then explains this by saying the 0.5% figure is set "conservatively to allow for SMS use cases not enumerated." But the spend cap is then calibrated against the bottom-up estimate, not the top-down figure. If the top-down figure is the actual provisioned ceiling, the spend caps of $200–$450/day are sized against a volume that is 5× lower than what the system is designed to handle. The caps would trigger constantly under normal operation if the top-down figure is accurate.

### 4. The 2FA SMS Rate Assumptions Are Presented as a Range When They're Actually a Binary

The document presents 8% and 50% SMS-2FA selection rates as "the two ends of a plausible product configuration range." These aren't empirical bounds on a continuous variable — they're two discrete product configurations (authenticator-first vs. SMS-default). There's no basis given for the 8% figure for authenticator-first adoption, and no acknowledgment that SMS-2FA selection rates on SMS-default configurations vary enormously by user population (age, geography, technical sophistication). The 2.3× cost difference framing implies a smooth tradeoff when the actual decision space is categorical and the cost estimates are unanchored.

### 5. The Viral Event Analysis Is Truncated

The document cuts off mid-sentence: "At 40% DAU/MAU and 20/day (a plausible success scenario), the diurnal peak reaches ~2,778/sec, which exceeds the 1," — the section ends there. The viral burst factor is referenced repeatedly as an independent multiplier applied on top of the diurnal peak, but Section 1.4 (Viral) is either missing or was never written. Every downstream claim about the provisioned floor surviving viral events is therefore unsupported.

### 6. The Escalation Ladder Threshold Is Self-Undermining

The alert tier fires at 75% of provisioned capacity (~1,875/sec). The document states that at the working assumption diurnal peak of 1,563/sec, this leaves ~20% margin before alerting. But 75% of 2,500 is 1,875, and 1,875 / 1,563 = 1.20, meaning a 20% increase above the expected diurnal peak triggers an alert. The document presents this as adequate headroom, but a 20% variance above expected peak is well within normal day-to-day fluctuation for consumer apps — the document's own diurnal peak factor is given as a range of 3–4×, meaning the upper end of normal variance alone (4× vs. 3×) would push the rate to ~2,084/sec, above the alert threshold. The escalation ladder would fire routinely under normal conditions.

### 7. The Redis Spend Counter Isolation Justification Contradicts Itself

The document justifies a dedicated Redis instance for the SMS spend counter "not by memory requirements but by operational isolation: the spend cap counter must not be subject to eviction pressure from the main notification Redis cluster." But a Redis instance with no eviction policy — as specified — does not evict keys regardless of memory pressure. Eviction only occurs when a maxmemory policy is set and memory is exhausted. The stated justification for the dedicated instance doesn't apply to the configuration described.

### 8. The Fan-Out Model Is Referenced but Not Present

Section 1 references fan-out being "modeled by notification type, not aggregate multiplier" as a key design decision. The reshare event is identified as "the only high-fan-out type." No fan-out model appears in the visible document. The worker sizing and queue depth calculations presumably depend on fan-out distribution, but there's no derivation to evaluate. This isn't a documentation gap — it means the sizing claims can't be verified.

### 9. The Diurnal Peak Factor Source Is Internally Contradicted

The document cites "Localytics 2022, AppsFlyer 2023" for a 3–5× peak-to-average ratio, then selects 3× as the "conservative working figure." But 3× is the low end of a cited range — using the low end of a range as a conservative estimate for a floor sizing calculation is backwards. Conservative sizing for a floor should use the high end of the peak factor range, because underestimating the peak leads to under-provisioning. The document's own framing of "conservative" is inverted.

### 10. The On-Call Runbook Is Designated a Launch Gate but Has No Owner Accountability Mechanism

The document states the SMS cap runbook "is assigned to the on-call infrastructure owner as a launch gate item." There is no definition of what "on-call infrastructure owner" means in a four-engineer team, no launch gate review process described, and no consequence specified if the deliverable isn't completed. Calling something a launch gate in a design document without a corresponding gate-keeping mechanism means it will be treated as optional documentation in practice.