## Real Problems

### 1. The 4-Business-Hour Contest Window Is Unworkable in Practice

The NSTL Backup waits 4 business hours for a contest before assuming duties. "Business hours" is not defined anywhere in the document. If the activation statement is sent at 3pm Friday, "4 business hours" could mean Monday afternoon depending on interpretation. The document does not specify what timezone governs, what the business day start and end times are, or whether the organization's holiday calendar applies. The activation trigger—non-performance of a Monday duty—is most likely to occur on a Monday, but the window calculation is undefined in all cases.

### 2. The Oversight Body Contact Is a Single Point of Failure With No Fallback Named

§0.2 repeatedly references "the oversight body contact stored in the tracker" as the escalation endpoint for contested activations and other disputes. The document states in §0.2 that if the general inbox produces no valid representative within two business days, any team member may escalate to the CEO or equivalent. But the oversight body contact stored in the tracker is a single named individual. If that individual is unavailable, recused, or is themselves the source of the dispute, there is no defined path short of the CEO escalation. The intermediate layer—the oversight body as a body—has no defined quorum, meeting trigger, or decision procedure documented here.

### 3. The NSTL Backup's "First Action" Verification Has No Time Bound

Upon activation, the NSTL Backup's first action is to verify the current tracker state against the repository and correct discrepancies. No deadline is given for completing this verification. During this period, gate status is uncertain and dependent work may be blocked. A complex discrepancy could take an indefinite amount of time to resolve, and there is no instruction for what happens to time-sensitive gate obligations while the verification is in progress.

### 4. The Proxy Confirmation Window Exception Creates a Structural Gap

Step 5 states that if the 48-hour confirmation deadline falls on a weekend or holiday, it extends to 17:00 on the next business day. But step 6 describes a fallback where the NSTL restarts the 48-hour window from confirmed receipt through an alternative channel. The extension rule in step 5 applies to the original window. It is not stated whether the extension rule also applies to the restarted window in step 6. A restarted window that begins Thursday afternoon could expire Saturday, and whether it then extends to Monday 17:00 is unresolved.

### 5. "Signed by Repository Commit" Is Not a Defined Procedure for the Handoff Entry

The return-of-duties handoff requires both the NSTL and the NSTL Backup to "sign this entry by repository commit." The document does not define what signing by repository commit means—whether it requires separate commits by each person, a co-authored commit, a specific commit message format, or something else. If the NSTL and NSTL Backup make separate commits, the order matters for determining when the handoff is legally effective, and neither ordering nor simultaneity is specified.

### 6. The Known-Event Implausibility Test Uses a Fixed Threshold That Ignores Event Count

The known-event test flags any week with a proxy commit, escalation, or gate deadline check-in that shows less than 1 hour of coordination time. But a week could contain multiple proxy commits, multiple gate deadline check-ins, and an escalation simultaneously. The 1-hour floor does not scale with event count. A log showing 1.1 hours in a week with five such events passes the test and would not be flagged, even though the threshold was chosen with a single event in mind. The test is stated as a fixed floor, not a per-event minimum.

### 7. The Document Is Cut Off Mid-Sentence

The document ends mid-sentence: "The Gate 3 two-source check (3—". Gate 4 is listed in the revision table as written in full (row 15), but it does not appear in the submitted document. Several sections referenced in the revision table (§0.3, §0.4, §0.5) do not appear in the submitted document at all. Problems described as resolved in the revision table—including the fill sequence, the acceptance file access grant, and the Gate 4 tiebreak procedure—cannot be evaluated because the relevant sections are absent. The revision table's claim that all referenced sections exist in this document is false.

### 8. The NSTL Backup Has Write Access to the Tracker During Normal Operations

The handoff procedure states the NSTL Backup "gains write access to the tracker and time log" at activation. But the NSTL Backup is described as having "standing awareness of the role" and independently observing tracker inactivity during normal operations. It is not stated whether the NSTL Backup has read access to the tracker before activation. More significantly, if the NSTL Backup gains write access only at activation, the mechanism by which the NSTL Backup independently observes tracker inactivity—one of the three surfacing mechanisms for NSTL non-performance—is not explained. A person without tracker access cannot verify tracker inactivity.

### 9. The Spike-Event Test Is Tied to a Single Scheduled Event With No Generalization

The spike-event test requires 3 hours of coordination time logged in the week the Gate 3 two-source check is scheduled, occurring in Month 2. This test is written for one specific event. No analogous test is defined for other high-complexity gate weeks, for weeks containing multiple simultaneous gate deadlines, or for any event outside Month 2. The implausibility framework is structurally incomplete for the rest of the project timeline.

### 10. The Deputy EM Notification at Handoff Return Has No Defined Obligation

When the return handoff is complete, the NSTL Backup notifies the Deputy EM by email. No obligation is placed on the Deputy EM upon receiving this notification—no required acknowledgment, no required action, no defined consequence if the Deputy EM does not respond. The notification is described as "the independent record that the handoff occurred," but an email sent to a recipient who has no defined obligation to respond or act is not a reliable independent record. The Deputy EM could be unreachable, and the document does not address this.