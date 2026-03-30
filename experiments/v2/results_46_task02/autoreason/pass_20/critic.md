## Real Problems with This Proposal

### 1. The 4× Peak Factor Is Asserted, Not Derived

The provisioned floor of 3,200/sec is the central capacity commitment, and it rests entirely on a "4× diurnal peak factor" that appears without derivation, reference, or sensitivity treatment. The document derives DAU/MAU ratios and notifications-per-user from published benchmarks with explicit sourcing. The peak factor receives none of that treatment. A social app with a strong timezone concentration (e.g., a primarily US-based userbase) could easily exhibit 6–8× peaks relative to 24-hour sustained averages. If the true peak factor is 6×, the ✓ flags in the sensitivity table are wrong, and scenarios currently marked as safe require re-sizing.

### 2. The In-App Fraction Derivation Contains a Hidden Assumption That Invalidates the Math

The document calculates in-app share as session_minutes / (16 × 60), assuming a uniform 16-hour active window and that notification events are uniformly distributed across that window. Neither assumption holds. Notification events are correlated with user activity — likes and comments spike when users are actively posting and browsing, which is precisely when other users are also in-session. The actual in-app fraction is higher than the independence assumption produces. The document treats this as a conservative estimate, but the direction of the error is opposite to what's claimed.

### 3. SMS Spend Cap Is Set Against an Unverified Cost Figure

The cap arithmetic uses $0.0079/SMS throughout, but Twilio's and similar providers' per-SMS rates vary by country destination, message type, and volume tier. For a 10M MAU social app with any international user base, a meaningful fraction of SMS traffic will hit rates of $0.05–$0.15/SMS (e.g., India, Indonesia, Brazil). The daily cost figures in the spend cap table ($210–$504/day) could be off by an order of magnitude depending on geographic distribution, which the document never addresses.

### 4. The Email Opt-In Rate Has No Derivation

The 8% opt-in rate that drives the entire email volume estimate appears without a source, a benchmark range, or a sensitivity flag. The document applies rigorous sensitivity treatment to DAU/MAU and notifications-per-user but simply asserts 8% for email, then acknowledges 5–12% as a range in a single parenthetical. For a newly launched app, opt-in rates at signup depend heavily on whether opt-in is default-on or default-off — a product decision that engineering cannot make — and this is never acknowledged.

### 5. Configuration C SMS Volume Modeling Is Internally Inconsistent

The document states Configuration C "at launch resembles B" and sets the spend cap against launch-time volume. But the working estimate for Configuration C (~29,000/day) is lower than Configuration B's working estimate (~42,500/day), not similar to it. If C resembles B at launch, the working estimate should be in B's range at launch and decline over time. The cap is therefore set against a figure that contradicts the document's own qualitative description of the configuration.

### 6. The "Development Default" Mechanism Creates Unacknowledged Risk

The document states that if no product decision on SMS 2FA configuration is received, the default is Configuration A, but only when "acknowledged in writing by a named product owner." This creates a gap: if no acknowledgment is received, there is no valid default by the document's own definition — but development presumably cannot stall indefinitely. The document does not specify what happens if the written acknowledgment is not received before sprint planning begins. It describes a mechanism that blocks on an external party with no fallback or escalation path.

### 7. The Escalation Threshold Logic Has a Contradiction

The document sets the escalation alert at 85% of provisioned capacity and explains that 75% is excluded because it "fires within normal diurnal variance at working assumption." But the sensitivity table marks scenarios at roughly 75–80% of provisioned capacity as ⚠ requiring a "re-sizing review." These two thresholds serve different purposes but are never reconciled. An operator watching the 85% alert has no guidance on whether a ⚠-flagged scenario in the table should have already triggered action before the alert fires.

### 8. Worker Count Derivation Is Referenced but Never Shown

Section 1.4 is referenced repeatedly as the location where worker count derivation is shown, but the document as presented contains no Section 1.4. This is either a missing section or a forward reference to content that was not included. The provisioned floor of 3,200/sec and the worker count figures cannot be verified without it.

### 9. The Runbook Assignment Mechanism Assumes Kickoff Has Occurred

The SMS cap runbook is assigned to "the engineer designated as on-call lead at project kickoff," but the document offers no contingency for what happens if that person leaves the team, is unavailable during an incident, or if the designation was never formally made. The second-engineer sign-off gate is a launch blocker by design, but there is no description of what constitutes valid sign-off or how it is recorded — "must carry sign-off" is stated but the mechanism is not.

### 10. Push Volume Assumes APNs and FCM Have Equivalent Delivery Characteristics

The document treats push as a single channel handling ~43.9M events/day without distinguishing between iOS (APNs) and Android (FCM). These have meaningfully different rate limits, payload size constraints, token invalidation behaviors, and failure modes. Treating them as interchangeable in the worker sizing model means that a skewed platform split (e.g., 70% iOS) could create APNs-specific bottlenecks invisible in the aggregate capacity model.