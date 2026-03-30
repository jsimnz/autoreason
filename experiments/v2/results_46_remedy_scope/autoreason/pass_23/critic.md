## Real Problems with This Proposal

### 1. The Document Is Its Own Obstacle

The "How to Use This Document" section promises self-contained incident response, but the matrix in Section 1.3 is visibly cut off mid-sentence ("expect 15–30" ends the document). Whatever instructions follow that truncation are missing. This is not a formatting issue — it means the Redis Option B failover procedure is incomplete, directly contradicting the document's own guarantee of self-containment under incident conditions.

### 2. The FCM Rate Assumption Undermines the Core SLA

The document repeatedly cites P1 delay figures of 20–40 minutes (or 50–80 minutes under database failure) but then qualifies these as dependent on an unverified FCM rate assumption. These figures appear in the Executive Summary as concrete planning outputs. Any engineer, manager, or stakeholder reading the summary will anchor on those numbers. The caveat is buried and easy to miss. The document acknowledges this risk but does not resolve it — it defers it to a pre-launch step that may not happen.

### 3. The Staffing Analysis Is Circular

The document states the reduction from 16 to 6 worker deployments was "driven by staffing constraints" and promises the tradeoff is "explained in Section 1.5." Section 1.5 does not appear in the provided text. The justification for one of the four core architectural decisions is entirely missing. The document cannot be evaluated on its own terms.

### 4. The Deployment Checklist Is Referenced But Never Shown

Sections 7.1 and 7.2 are cited repeatedly as the location for named humans, Redis option selection, product decisions, and escalation fallbacks. None of this content appears in the document. The pre-flight check that blocks deployment on placeholder text references a checklist that isn't here. This means the enforcement mechanism described in the introduction is unverifiable.

### 5. Product Decision Gates Are Structurally Incoherent

The fanout cap decision records itself as: "Decision is recorded in the deployment checklist as: [PRODUCT DECISION RECORDED HERE]." This is a template placeholder inside a document that claims placeholder text triggers deployment failures. The document has failed its own gate condition.

### 6. The Burst Allowance Justification Is Invented

The document claims a burst allowance of 4 (not 5) is justified by "research on social app spam perception" showing degradation above 15–25 notifications/hour, and that 4 keeps the maximum at 24. This arithmetic does not follow from the stated limit of 20/hour — burst allowance governs short-window excess above the sustained rate, not the hourly ceiling. The conclusion (24 vs. 25 notifications) does not derive from the cited research in any way that is traceable. This is post-hoc rationalization dressed as empirical justification, and product is being asked to "confirm" a number built on it.

### 7. The Month-1 Checkpoint Has an Accountability Gap

The procedure triggers "if month-1 traffic data is not reviewed by day 35" — but the on-call rotation owner who executes the procedure is the same role responsible for the review that was missed. There is no independent trigger or escalation path if that person is the reason the review was missed.

### 8. The Correlated Sensitivity Table Contradicts Itself

The document criticizes using a fixed 3× peak multiplier as "internally inconsistent" with acknowledging correlation risk, then presents a table where the plan row uses exactly 3× with no stated rationale for why that specific multiplier is correct for the plan-rate scenario. The critique of the inconsistency is not resolved — it is restated with different numbers.

### 9. Scale-Down Requires Engineering Lead Sign-Off With No Defined Timeline

The step-down procedure after month-1 scaling requires engineering lead sign-off and 7 days of post-review data. If the system was over-scaled and the engineering lead is unavailable, Section 7.2 is invoked — but Section 7.2 is not in the document. The cost of over-provisioning has no defined resolution path.

### 10. The Auto-Scaling Gap Creates Unacknowledged Risk

The document states auto-scaling is unavailable at launch and available "from month 2 after HPA deployment and validation." The traffic response matrix covers scenarios up to 7,500/sec, all requiring manual intervention. The document does not address what happens if a viral spike occurs in month 1 outside business hours, when manual response time is materially longer than during the day. The response times cited in the matrix are not specified at all — making "manual response times apply" an empty commitment.

### 11. The Deduplication Section Is Incomplete

Section 2.2, which is promised to contain full arithmetic on deduplication set sizes and the interaction between the sliding window and cross-channel delivered-ID set, does not appear in the document. The power-user risk analysis in Section 1.1 explicitly depends on this content.

### 12. Redis Section 6.2 Is Referenced But Absent

Section 6.2 is cited in the "How to Use This Document" section as the place to go for Redis failover under incident conditions, including in-flight behavior during the promotion window. It does not appear in the document. The claim that "'Recoverable' is demonstrated, not asserted" cannot be evaluated.