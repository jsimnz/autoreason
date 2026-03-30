## Real Problems with This Proposal

### 1. The NSTL Role Is Structurally Overloaded and Unexamined

The document assigns the NSTL — one of four backend engineers — approximately 10–15% time for coordination duties, then uses that figure as the entirety of the accounting. But the NSTL is also the person who performs the Gate 3 two-source check, executes all proxy commits, escalates to the Engineering Manager within 48 hours of missed deadlines, notifies the Deputy EM of Engineering Manager non-performance, escalates to the oversight body if both EM and Deputy EM fail, documents the pre-deadline email intent check, and updates the tracker every Monday. These are not captured in the 10–15% figure. The document says "this is accounted for in §5.1" but §5.1 is never shown. The accounting claim is unverifiable within the document.

### 2. The Deputy EM Has No Confirmation Row Logic That Works

The Named Individuals Table requires the Engineering Manager to confirm the Deputy EM row. But the Deputy EM exists specifically to act when the Engineering Manager is non-performing. If the Engineering Manager is the person who fails to fill in the table (i.e., Gate 0 slips), the Deputy EM row may never be confirmed — meaning the Deputy EM backstop is unavailable precisely when it is needed. The document acknowledges the EM-as-single-point-of-failure problem for other roles but not for this one.

### 3. The Oversight Body Representative Row Has a Circular Confirmation Problem

The Engineering Manager confirms the Oversight Body Representative row. But the Oversight Body Representative is the escalation target when the Engineering Manager fails. If the Engineering Manager does not confirm that row, the contact stored "in plaintext in the tracker" (obtained at kickoff, pre-Gate 0) is the only reliable path — and that contact information is itself obtained from the Engineering Manager at kickoff. There is no independent source for the oversight body contact. The pre-Gate 0 requirement depends entirely on the Engineering Manager volunteering accurate information before any accountability structure is in place.

### 4. Gate 3's Two-Source Check Is Methodologically Weak and Presented as Rigorous

The document presents the [1.5, 6] range as a principled threshold ("within a factor of 2 of R=3"), but R=3 is explicitly described as unvalidated. A factor-of-2 band around an arbitrary assumption is not a confidence interval — it is an arbitrary band around an arbitrary number. The industry benchmark source compounds this: Leanplum, Braze, and Airship publish benchmark reports as marketing materials for their own products, with self-selected customer samples. Using these as a validity check on a core sizing assumption treats vendor marketing as independent data. The document does not acknowledge this.

### 5. Gate 2's Fallback Sizing Rationale Contradicts Its Own Logic

The document argues that 20/day is a bad fallback because it "produces a sustained average in the warning band, which itself triggers a re-sizing review," and that "a fallback that generates a downstream review moves the uncertainty rather than resolving it." But 25/day as a fallback also does not resolve the uncertainty — it just prices it higher. The underlying uncertainty (what the actual orientation is) remains. The document claims 25/day is "expensive and stable" but does not show that 25/day is stable either; if the actual orientation is content-discovery, 25/day is wrong, not stable. The argument proves less than it claims.

### 6. The Proxy Acknowledgment Path Has a Security Gap in Repository Access Grants

Section 0.1 states the NSTL grants gate owners direct write access to `gates/` within 48 hours of a proxy resolution. Write access to a runbook repository is presumably controlled by someone other than the NSTL — likely an infrastructure owner or admin. The document assumes the NSTL can unilaterally grant this access within 48 hours. If that requires a ticket, an admin approval, or a separate process, the 48-hour commitment is unenforceable by the NSTL alone. This is not addressed.

### 7. Gate 4's Tiebreak Default Rationale Assumes the Security Lead's Position Is Correct

The document justifies Configuration B as the tiebreak default by arguing that defaulting to A "means a security regression occurs precisely because the process failed." But a tiebreak situation means both parties disagree — it does not establish which party is correct. The Security Lead may be wrong, may be applying standards inappropriate to this app's threat model, or may be advocating for Configuration C for reasons unrelated to security. The document's reasoning assumes the Security Lead's position is substantively correct and uses that assumption to justify a default that favors their position. This is not a process-neutral tiebreak.

### 8. The "Canonical Filename" Requirement Is Fragile

Gate resolutions must reference the document by its canonical filename `notification-system-design-v3.md`. If this document is revised and the filename changes — which is likely over a six-month project — prior gate resolutions reference a filename that no longer corresponds to the active document. The document does not address versioning or what happens when the canonical filename changes. This is a practical problem that will occur.

### 9. The Concurrent Product Owner Failure Scenario Is Noted But Not Resolved

The revision notes state a concurrent failure scenario was added for the Product Owner holding Gates 1, 2, and 4. The gate register shows consequences for each gate individually if missed, but there is no analysis of what happens if all three slip simultaneously. The document acknowledges this failure mode exists but does not address it beyond noting it.

### 10. "Engineering Manager's Duties Are Outside the Engineering Budget" Is Unexplained

Section 0.2 states the Engineering Manager's duties are outside the engineering budget without explanation. On a four-person team, the Engineering Manager may also be a contributing engineer. If so, the schedule-revision duty (two business days after any slip), the Gate 4 tiebreak duty, and the Gate 3 escalation response (24 hours) all consume engineering time that is not accounted for anywhere in the document. The statement reads as a scope exclusion that may not reflect reality.