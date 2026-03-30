## Real Problems

### 1. The Runbook Dependency Is a Launch Blocker With No Enforcement

The preface states the runbook "must be authored and maintained separately" and Section 7.1 has a gate requiring it to exist and be linked before production deployment. But there is no named owner for authoring the runbook, no deadline for its creation, and no fallback if it doesn't exist. Every other unresolved decision has a named authority and a fallback. The runbook requirement has neither. Under the same logic applied to the five product decisions, the product owner's silence on runbook authorship would deploy... nothing, because there is no fallback state for "runbook does not exist."

### 2. Section 7.1 and 7.2 Are Referenced Dozens of Times But Never Shown

The document references Section 7.1 for named owners, deadlines, authority, the pre-flight checklist, the month-1 checkpoint procedure, and the backup escalation trigger. It references Section 7.2 for on-call rotation, escalation chains, and the procedure for when the on-call schedule is inaccessible. Neither section appears in this document. Every concrete accountability mechanism in the design points to sections that contain no content here. The document repeatedly asserts that critical procedures are "specified in Section 7.1" or "in Section 7.2" as a substitute for actually specifying them.

### 3. The Staffing Arithmetic Is Promised but Never Delivered

The executive summary explicitly states "Section 1.5 contains the staffing arithmetic" and that "the arithmetic is not circular." Section 1.5 is listed in the table of contents as "Staffing Analysis" but does not appear in the document body. The claim that 16 deployments were reduced to 6 based on a derivation from fixed engineer-weeks is asserted but undemonstrable from the content provided. The document's own framing — that the staffing constraint is "a design input, not a caveat" — makes the absence of this section more damaging, not less.

### 4. The In-App Volume Accounting Note Is Truncated

Section 1.2 ends mid-sentence: "The 
" — the accounting note for in-app notifications cuts off. This is not a minor formatting issue. In-app is 20% of daily volume (9M/day), generates distinct database writes, and the incomplete sentence was apparently explaining something important about how it differs from push quota consumption. Whatever followed that sentence is missing from the design.

### 5. The Month-1 Recalibration Has No Specified Procedure

The document repeatedly states that the on-call rotation owner "recalibrates active hours and multipliers at the month-1 checkpoint using actual traffic data" and that "the procedure is in Section 7.1." Section 7.1 is not present. The backup escalation path on day 34 also terminates in Section 7.2. The entire calibration mechanism — which the document explicitly acknowledges is necessary because the 14-active-hours figure is an unvalidated assumption carrying ±25% uncertainty — has no actual procedure anywhere in this document.

### 6. FCM Rate Verification Has No Fallback Timeline

Section 1.4 is listed in the table of contents as "FCM/APNs Rate Limit Verification" and is referenced in the infrastructure sizing dependency chain as determining which Redis branch applies. The section does not appear in the document body. The dependency chain states Branch B is the default if FCM verification is not complete before launch, but there is no specification of what verification entails, who performs it, or when it must complete. A named infrastructure decision with two explicit sizing branches depends on a verification process that is entirely unspecified.

### 7. The Fanout Correction Undermines Its Own Credibility

The document corrects a "45-minute figure in earlier drafts" to ~10 minutes, attributing the prior error to a miscalculation of the token bucket guarantee. This is presented as transparency. The problem is that the document is now in a state where at least one prior numerical claim was wrong by a factor of 4.5x, and the correction relies on Section 3.2 parameters — which are described as "fully specified in Section 3.2, not referenced to it" — but Section 3.2 does not appear in the provided document. The corrected figure cannot be verified from the content present.

### 8. The SMS Cost Exposure Analysis Is Disconnected From Decision Authority

Section 1.1 calculates SMS cost exposure of up to $75,000/day from uncapped power-user volume. The authority for the daily spam threshold decision is assigned to the product owner. But the SMS cost exposure is a financial/legal concern, and Decision 5 (SMS opt-out compliance) is assigned to a "legal/compliance owner." There is no mechanism in the document for the financial risk of SMS volume to route to whoever owns the SMS cost budget. The product owner could set a permissive spam threshold without visibility into the cost implications that the legal/compliance owner might care about, and vice versa.

### 9. The Deduplication Retention Window Decision Has an Underspecified Consequence

Decision 4 states the deduplication retention window "determines Redis key volume" and feeds the infrastructure sizing dependency chain. But the fallback is 24 hours with no analysis of what happens to deduplication correctness if the actual required window is longer. If a user receives a push notification and later opens the app within 25 hours, a 24-hour window would allow a duplicate in-app notification to appear. The document specifies the infrastructure consequence of the decision but not the product correctness consequence of the fallback being wrong.

### 10. The "Worst-Case Delivery Outcome Is Duplication, Not Loss" Claim Is Not Defended for All Failure Modes

The executive summary asserts duplication as the worst-case outcome. Section 4.2 is cited for the derivation of the 90-second recovery window. Section 4.2 does not appear in the document. The claim is load-bearing — it is the justification for the ID-based queue architecture — and it is unverifiable from the content present. More specifically, the claim applies to crash recovery, but the document also describes a Redis failover scenario in Section 6.2 with an "unavailability gap." What happens to queue entries that are in-flight during that gap is described as specified in Section 6.2, which also does not appear in the document body.