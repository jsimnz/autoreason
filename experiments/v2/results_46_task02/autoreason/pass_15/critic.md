## Real Problems With This Proposal

### 1. The 30% DAU/MAU Assumption Is Load-Bearing and Unjustified

The entire sizing cascade starts with 3M DAU from a 30% DAU/MAU ratio described only as a "social app benchmark." No source. No range. No sensitivity analysis. If the actual ratio is 20% (common for social apps with significant dormant accounts), total daily notifications drop to ~33M and the provisioned floor is over-built. If it's 45% (healthy engaged social app), the floor is under-built before viral effects are applied. This single input moves the worker count by ±30%, yet it receives less scrutiny than the viral cohort multiplier.

### 2. The 70/8/20 Channel Split Is Asserted Without Derivation

Push is 70%, email 8%, in-app 20%, SMS derived separately. These percentages determine the per-channel worker allocation directly. No basis is given for why 70% of notifications are push versus in-app or email. On a social app where logged-in web users exist, in-app could be substantially higher. If push is actually 55% and in-app is 35%, the worker table is wrong in ways that matter: push workers are over-provisioned, in-app workers hit the single-worker ceiling earlier. The document treats these splits as facts while acknowledging elsewhere that pre-launch data doesn't exist.

### 3. The In-App Worker Capacity Is Functionally Unconstrained and That's Concealed

The in-app worker is listed as capable of 3,000/sec but "capped at 360/sec by inbound." This means one worker handles 20% of total load with 88% headroom. Fine. But the document never addresses what happens to in-app during the elevated or high inbound scenarios. At 6,200/sec total inbound, in-app load is ~1,240/sec (still under the 3,000/sec figure). But the 3,000/sec figure is derated from 10,000/sec with a hand-wave about "pipeline flush overhead and key expiry operations." No arithmetic supports that specific 70% deration. The in-app channel gets the least scrutiny of any channel despite serving 20% of volume.

### 4. Section 1.3 Is Cut Off Mid-Sentence

The section ends: "Phone verification rate: ~60% of new registrations" — and then nothing. The document claims in the revision note that Section 1.3 was written and included. It was not completed. The SMS spend cap design, which is called out in the Executive Summary as a specific design decision, depends on this derivation. The 7/sec SMS figure in the worker table has no visible basis in the document as presented.

### 5. The Shedding Trigger Thresholds Are Internally Inconsistent

The alert fires when queue depth exceeds a 60-second drain time. Auto-scaling triggers at a 3-minute drain time. Shedding triggers at a 10-minute drain time. These are presented as a coherent sequence, but the ordering is wrong: the alert fires *before* auto-scaling triggers. An operator receives an alert about a 60-second queue depth before the system has even begun scaling. If scaling takes 4–12 minutes (per the document's own honest range), the system will be in alert state for the entire scaling window without having triggered shedding, which doesn't engage until 10 minutes of queue depth. The thresholds don't form a coherent escalation ladder.

### 6. The "2 Spare" Workers Have No Principled Basis

The worker count rounds from 22 to 24 "with 2 spare." Spare for what? Failure replacement? Headroom? Rolling deploys? Two spare push workers at 75/sec each add 150/sec of push capacity. Two spare email workers would add 100/sec of email capacity. But the spares are not allocated by channel — they're just added to the total. In a channel-specialized worker architecture, a spare push worker cannot cover email queue depth. The spare capacity doesn't map onto the failure modes it's presumably meant to cover.

### 7. The Viral Spike Multiplier Calibration Mixes Incompatible Units

The table lists multiplier ranges calibrated against "10K–100K engagements in 15 min" for moderate viral content. But the multiplier is defined as "the ratio of spike-period notification rate to a user's baseline rate." These are different things. Engagement count is a platform-level aggregate. The per-user baseline rate is an individual-level figure. The calibration note says the multiplier is "estimated from engagement rate × notification fan-out" but doesn't show that arithmetic. The 8× working assumption is asserted without connecting the engagement-count calibration to the per-user rate ratio definition. The two columns of the table don't measure the same thing.

### 8. The Email Head-of-Line Argument Proves Too Much

The revised argument correctly identifies SMTP handshake latency (100–300ms) blocking push dispatch (5ms) as head-of-line blocking. This is accurate. But the same argument applies equally to in-app writes blocking push dispatch, since Redis pipeline flushes — while faster than SMTP — still introduce variable latency that can delay push. The document uses the argument selectively to justify email/push separation while placing in-app and push in the same conceptual tier. If head-of-line blocking justifies separating email from push, the same logic should be applied consistently across all channel pairs, and the document should explain why in-app latency doesn't create the same problem.

### 9. The Idempotency Architecture Is Mentioned But Never Specified

The Executive Summary lists "receipt-independent delivery state machine" as a key design decision with the note that it "breaks idempotency circular dependency during APNs connection failures." This appears nowhere else in the document. The per-worker table mentions "idempotency write (pipelined Redis SET)" as a line item. But the state machine itself — its states, transitions, what "receipt-independent" means operationally, how it handles the case where APNs accepts a notification but the receipt is lost — is never described. A design decision listed as key in the summary should have a design.

### 10. The Honest Uncertainty Framing Is Applied Selectively

The document is admirably explicit about uncertainty in the viral cohort assumptions and the APNs rate limits. But the 200ms SMTP handshake figure used to justify channel specialization and size email worker throughput is stated without uncertainty bounds, despite being the number that directly determines email worker count (3 workers instead of 2 or 5). SMTP relay performance varies significantly by provider, network conditions, and authentication overhead. The same epistemic rigor applied to the viral multiplier should apply to the latency figures that drive worker sizing.