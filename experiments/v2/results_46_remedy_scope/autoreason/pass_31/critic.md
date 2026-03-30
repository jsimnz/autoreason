## Real Problems

### 1. The Document Is Structured as an Incident Runbook and a Design Document Simultaneously

The "How to Use This Document" section directs operators to specific section numbers during incidents. But this is a design proposal, not operational documentation. When this document is revised, renumbered, or superseded, every embedded section reference in the runbook header becomes a liability. Section 4.3 being "self-contained" is a property asserted in the design document, not verified in a separate operational artifact. Operators under incident conditions will be reading a design doc, not a runbook.

### 2. The Escalation Chain Encodes Org Structure Into a Technical Document

Section 7.2 is referenced for day-34 escalation with "no available lead." The escalation chain names a "senior engineer on the current on-call rotation by role, not by name." This means the document's correctness depends on the on-call schedule being accurate, accessible, and consistently maintained at the location specified in Section 7.2. That location is not shown. If the on-call schedule moves, is stale, or uses different role terminology, the escalation path silently breaks. The document presents this as a solved problem when it has merely deferred the dependency.

### 3. Product Decision Fallbacks Are Presented as Engineering Unilateral Authority Without Stating Who Authorized That Authority

The daily spam threshold section explicitly states "Engineering has unilateral authority to enforce this fallback without a product decision." No one is named as having granted this authority. In a real organization, engineering asserting unilateral authority over a product behavior in a design document does not make it so. This creates a false sense of resolved governance.

### 4. The FCM/APNs Rate Limit Disclaimer Undermines the Entire Capacity Plan

The "What this document does not guarantee" section states FCM/APNs rate limits are not contractually specified and that P1 delay figures are estimates pending sign-off. Push is 70% of volume. The peak rate calculations, worker sizing, and Redis branch selection all depend on FCM throughput assumptions. The document acknowledges this uncertainty and then proceeds to build the entire capacity plan on top of it without quantifying the uncertainty range. Branch B is named as a fallback but the document does not state what Branch B's limits are relative to FCM's actual behavior.

### 5. The Correlated Sensitivity Table's Extreme Row Is Not Covered by the Infrastructure Plan

The extreme scenario is 162M/day at ~9,643/sec. The traffic response matrix in Section 1.3 is said to cover "the full range from plan through 162M/day" with "no gap between the 80M/day threshold and the 162M/day extreme." This claim cannot be evaluated because Section 1.3 is not shown. The document asserts coverage without demonstrating it.

### 6. The 90-Second Recovery Window Is Described as Derived but the Derivation Is Not Present

The executive summary states the 90-second crash recovery bound is derived in Section 4.2. This is a load-bearing claim — it determines worst-case duplication exposure and is cited as a design guarantee. If the derivation contains an error or an unstated assumption, nothing in the visible portion of the document would reveal it. Stating that a derivation exists elsewhere is not equivalent to the derivation being correct.

### 7. The SMS Cost Table Is Incomplete

The SMS cost table is cut off mid-row in the visible document. The plan row's 5% column is missing its annual figure. This is not a formatting issue in isolation — the table is cited as the basis for the $81,000/day SMS exposure figure used to justify the daily spam threshold decision. A decision justified by a number that appears in an incomplete table is not well-supported.

### 8. The Active-Hours Methodology Is Presented as a Correction but Introduces an Unstated Assumption

The document criticizes the 24-hour denominator approach and replaces it with a 14-active-hours denominator, claiming this is the "conservative (higher-peak) estimate." But 14 active hours is itself an assumption "from general social-app patterns." The document acknowledges this in the calibration note but has already used 14 hours to generate the plan row numbers and to criticize the prior methodology. If actual active hours are 16 or 18, the peak rates are lower than stated. The methodology change is not validated; it is substituted.

### 9. The Fanout Worst-Case Bound Depends on Token Bucket Parameters That Are Not Shown

The 45-minute worst-case fanout completion time for a 100,000-recipient event is described as derived from token bucket parameters in Section 3.2. Those parameters are not visible. The fanout cap product decision — including Option A's explicit acceptance of this worst-case — is being made against a number whose basis is elsewhere in the document. A product team accepting a 45-minute consistency gap cannot verify that number from what is presented.

### 10. Four Engineers Over Six Months Is Treated as a Fixed Constraint but the Staffing Arithmetic Is Circular

The document states that staffing drove the reduction from 16 to 6 worker deployments, and that "every simplification names the staffing constraint as its reason." But the staffing analysis is in Section 1.5, which is not shown. The executive summary uses the staffing constraint to justify architectural decisions, and Section 1.5 presumably uses the architectural decisions to validate the staffing constraint. If Section 1.5 simply confirms the decisions already made in the executive summary, the arithmetic is not independently constraining anything.