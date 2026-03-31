## Real Problems Found

### 1. Zero-buffer scaling trigger is acknowledged but not resolved

Section 1.1.2 explicitly states "a two-week trigger provides approximately zero buffer at the outer bound" for scaling work that takes 11–15 calendar days. The 40% single-week escalation path is a partial patch, but if the ratio climbs from 30% to 41% in a single week, E2 escalates "immediately" — yet the scaling work still takes 11–15 days. The system can be in an under-provisioned state for two weeks with no mitigation described. The proposal names this problem and leaves it open.

### 2. Infrastructure cost section is explicitly incomplete

Section 1.1.1 contains "$X/month (infrastructure cost section to be completed at vendor quote stage)." The over-provisioning cost impact is expressed as a percentage of an unknown number. The acceptance of that cost is therefore meaningless — you cannot accept a cost you have not calculated. This is a placeholder in a Revision 3 document that has already addressed ten prior criticisms.

### 3. Product decision log reference is a placeholder

Section 1.2.1 cites "[DATE]" and "[DECISION LOG REFERENCE]" for the in-app non-disableable product decision. In a revision specifically responding to criticism about this decision lacking justification, the supporting record is not actually present. The rationale text exists, but the audit trail it claims to rest on is empty.

### 4. The compliance review gate has no deadline

Section 1.2.1 states the legal review "must be completed and signed off before the preference management UI is finalized" but gives no date. The preference management UI finalization date is not defined anywhere in the document. This gate is unenforceable without a concrete date, and the same section was added specifically to address Criticism 4's complaint about unresolved escalation — yet the structural problem recurs here for a different legal risk.

### 5. TCPA resolution creates a new unresolved dependency

Section 1.6.1 is referenced in the executive summary as resolved by naming a decision owner and required sign-off date, but Section 1.6.1 does not appear in the document as provided. The resolution is asserted in the summary but the section content is absent. Whether the resolution is adequate cannot be evaluated.

### 6. The fanout multiplier applies only to the non-high-follower population

The table in Section 1.1 labels the 1.05 multiplier as applying to the "non-high-follower population," and the executive summary says follower fanout notifications are not being built at launch. But the traffic model uses this multiplier on the full 15M raw actions/day without segmenting out high-follower actions. If high-follower fanout is excluded from scope, the multiplier should apply only to non-high-follower actions. If high-follower actions are included in the 15M, the model is understating recipients for those actions. Either the scope exclusion or the arithmetic is inconsistent.

### 7. Email opt-in sensitivity is not carried through to worker sizing

Section 1.2.3 provides push opt-in sensitivity (±10pp → ±1 worker) but provides no equivalent analysis for email opt-in despite the stated range being 15–30% (a ±33% spread around the 20% baseline). A shift from 20% to 30% opt-in increases email delivery volume by 50%. Section 1.3.3 is cut off before completing the worker arithmetic, so it is impossible to assess whether this gap matters — but the asymmetry in sensitivity treatment is unexplained.

### 8. SMS transactional volume is distinguished but not quantified

Section 1.4 is referenced in the executive summary as now distinguishing transactional SMS from social SMS and examining launch promotion scenarios. The channel volume table in Section 1.2.2 shows only social SMS (<0.01%, ~1,500/day). Transactional SMS (2FA, account verification) volume does not appear anywhere in the visible document. For a 10M MAU app, transactional SMS at even 0.1% daily trigger rate is 10,000 messages/day — potentially an order of magnitude larger than social SMS. The distinction is named but the transactional volume is unexamined in the visible sections.

### 9. Section 1.3.3 is cut off mid-sentence

The document ends mid-sentence during the email worker arithmetic explanation: "all four workers process their shares" — incomplete. This is Revision 3, and the email worker arithmetic (Criticism 3) was a named prior criticism. The resolution is literally unfinished in the submitted document.

### 10. The 20% global opt-out rate is called a "conservative floor" with no basis

The traffic model table labels 20% as a "conservative floor" but no citation, benchmark, or derivation appears anywhere in the visible document. Unlike push and email opt-in rates, which cite OneSignal, Airship, and Mailchimp benchmarks with date ranges, the opt-out rate has no supporting reference. Because this figure is applied before channel opt-in, it has the largest single multiplier effect on total routed volume — a floor of 10% instead of 20% increases routed events by 12.5%, which may affect worker pool sizing.