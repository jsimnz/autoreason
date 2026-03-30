## Real Problems with This Proposal

### 1. The Legal Dependency Is Structurally Unresolved

The document identifies a potentially architecture-breaking legal dependency in §1.2.1, names it as a blocker, but leaves both the owner name and required completion date as unfilled placeholders (`[Product lead name]`, `[Date]`). A document that explicitly states "implementation of §1.3 is blocked" pending a review, and then ships with the reviewer and deadline blank, has not actually blocked anything. The blocker exists only in text.

### 2. §1.3 Is Incomplete

The document ends mid-sentence: "**Per-channel behavior under Tier 1:**" followed by a horizontal rule and nothing. The preface explicitly states "forward references to section numbers that do not exist in this document are a defect" and invites readers to report them, but the more serious defect — a section that begins and stops — goes unacknowledged. The Tier 1 delivery path is the highest-stakes part of the design (security events, password resets) and it has no specified behavior.

### 3. The Ownership Failure-Mode Chain Has a Hidden Assumption

The document constructs an elaborate ownership transfer chain for the named load validation owner, including simultaneous unavailability scenarios, with the product lead as "the final escalation point" who "is not part of the backend team, so this chain does not loop." But the product lead's contact information is explicitly deferred: "recorded in the project kickoff checklist, not only in this document." If the kickoff checklist hasn't been completed — a failure mode the document itself acknowledges as possible — the escalation chain terminates at an unreachable person. The chain's loop-prevention argument depends on information that may not exist yet.

### 4. The DM Volume Note Requests a Clarification That Should Have Blocked the Estimate

The document states the DM volume assumption "is the highest-risk figure in this table" and that "the product team must clarify expected DM usage pattern before this figure is used for capacity planning beyond initial provisioning." But the figure is already used for capacity planning — it feeds directly into the provisioning target in §1.1.3. The document simultaneously uses the figure and says it shouldn't be used until clarified. This is not a documented tradeoff; it's a contradiction.

### 5. The "Unified Headroom Standard" Decision Rules Are Inconsistent With the Stated Standard

The unified headroom standard is declared to be "1.5× the measured sustained peak" and to "apply in all cases without exception." But the first decision rule — "if actual peak is within 50% of 130/second in either direction: no infrastructure changes required" — does not mandate setting baselines to 1.5× the measured peak. It says to update the working figure. A system running at, say, 100/second measured peak with baselines provisioned for 260/second is not at the 1.5× standard; it's at 2.6×. The "no changes required" rule contradicts the "apply in all cases without exception" statement.

### 6. The 2× Provisioning Headroom Argument Is Circular

§1.1.1 argues that provisioning for a 6× spike "would be prohibitively expensive and would itself rest on an unsupported number." But the 2× headroom also rests on an unsupported number — it was calibrated to handle one assumption being "wrong by a large margin," which is itself an unquantified claim. The document is correctly skeptical of the 6× figure but not skeptical of the 2× figure by the same standard. The reasoning does not distinguish between them on principled grounds.

### 7. The "Immediate" Tier 3 Preference Creates an Unanalyzed Load Problem

§1.2.3 specifies that users can select "immediate" delivery for Tier 3 notifications, which delivers each notification individually rather than in hourly digests. The document asserts this preference "does not affect Tier 2 queue depth." But it says nothing about what it does to Tier 3 queue depth or total system load. Likes are the highest-volume event type in the table. If a meaningful fraction of users select "immediate" for Tier 3, the batching that was used to justify the volume estimates in §1.1.2 no longer applies to those users. The load model doesn't account for this.

### 8. The Pre-Distribution Check Cannot Enforce Itself

§1.1.4 states that before distribution, the project lead must verify the named owner reflects current team composition, and that "if the checklist is not completed, distribution is blocked." This check and its enforcement mechanism are described inside the document being distributed. There is no mechanism by which the document can block its own distribution. The instruction is self-referentially unenforceable.

### 9. Sections 1.4 Through 1.10 Are Referenced but Absent

The preface lists the document as covering §1.4 through §1.10 and states that forward references to nonexistent sections are a defect. §1.4 (push error handling for APNs and FCM), §1.5 (in-app notification store), §1.6–1.7 (email and SMS), §1.8 (user preferences), §1.9 (infrastructure), and §1.10 (failure handling) do not appear in the document. The preface's self-audit mechanism catches this only if someone reads the preface against the table of contents — but the document has no table of contents, and the preface's defect-reporting instruction points to "the document owner," who is not named anywhere in the document.