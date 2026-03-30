## Real Problems with This Proposal

### 1. The Revision Table Is Unverifiable

The revision notes claim eleven specific problems were resolved, but the actual section content for most of those sections is not present in this document. Sections 2.2, 3.1–3.3, 4.1–4.3, 5.1–5.4, 6.1, 6.2, 6.3, 7.1, 7.2, and 8 are entirely absent. The table claiming resolution of findings 3, 4, 5, 7, 8, 11 (among others) cannot be audited. The revision process it describes is therefore not actually completable from this document.

### 2. The Document Is Incomplete and Does Not Detect This

The "How to Use This Document" section describes a CI job that diffs the rendered document against a section manifest to catch missing or empty sections. That CI job either does not exist yet, is not running, or is not passing — because most sections listed in the Table of Contents are absent from this document. The document makes completeness guarantees it visibly fails to satisfy.

### 3. Pre-Flight Script Is Referenced But Not Present

Section 7.1 is cited repeatedly as the location for named owners, deadlines, unresolved decision fields, and the pre-flight invocation path. Section 7.1 does not appear in this document. The pre-flight script's enforcement of ordering constraints (retention window before Redis provisioning, FCM verification before Redis sizing) cannot be verified. The claim that "the pre-flight script blocks on any unresolved field" is unauditable.

### 4. Five Unresolved Product Decisions Are Load-Bearing and Have No Fallback

Three of the five unresolved decisions — burst allowance, fanout cap, and daily spam threshold — directly affect queue behavior, worker load, and infrastructure sizing. The document defers all five to "Section 7.1" for owners and deadlines, but Section 7.1 is absent. More critically, the document provides no behavior specification for what the system does if these decisions are not made before launch. The pre-flight script is supposed to block on them, but if the script itself is not complete, there is no enforcement mechanism.

### 5. FCM/APNs Rate Limit Claim Is Still Load-Bearing Despite the Disclaimer

The executive summary states the claim that FCM/APNs rate limits are the binding constraint "is not used as a design assumption until the verification is complete." But Section 6.2 is described as containing two explicit Redis sizing branches contingent on that verification. Section 6.2 is absent. The two branches do not exist in any reviewable form. The disclaimer does not neutralize the load-bearing nature of the claim if the alternative sizing path is not actually specified anywhere.

### 6. The 90-Second Crash Recovery Bound Is Asserted, Not Shown

The executive summary states the 90-second orphaned-entry reclaim window is "derived in Section 4.2." Section 4.2 is absent. This bound matters operationally: it determines worst-case duplicate delivery windows and affects SLA commitments. Describing a derivation that does not appear in the document is not the same as providing one.

### 7. The Worst-Case Fanout Completion Time Is Asserted, Not Derived

The document states the ~45-minute worst-case fanout bound "is derived from token bucket parameters in Section 3.2." Section 3.2 is absent. The distinction the document draws between "derived" and "asserted" is a meaningful quality claim, and it is not satisfied here.

### 8. The Month-1 Checkpoint Procedure Is Truncated Mid-Sentence

The final paragraph of Section 1.1 ends abruptly: "it names a specific role, not an" — the sentence is incomplete. This is the escalation path for the scenario where both the on-call rotation owner and the named backup are unavailable by day 34. That is exactly the kind of edge case the document claims to have resolved (finding 4 in the revision table). The resolution is literally cut off.

### 9. Section 1.3c Is Listed in the Table of Contents But Does Not Appear

The "How to Use This Document" section explicitly directs users to Section 1.3c for after-hours spikes in month 1 before auto-scaling is live. This is an operational path a responder might need under time pressure. The section does not exist in this document.

### 10. Staffing Arithmetic in Section 1.5 Is Claimed but the Section Is Absent

The executive summary states "Section 1.5 contains the staffing analysis — including the full arithmetic." Finding 9 in the revision table says "Section 1.5 written in full." Section 1.5 is not present. The claim that the reduction from 16 to 6 worker deployments was justified by staffing arithmetic cannot be evaluated.

### 11. The Sensitivity Table's Extreme Row Exceeds the Stated Runbook Threshold Without Explanation

The extreme scenario is 162M/day. The runbook threshold cited throughout is >80M/day. The document does not specify whether the extreme-scenario runbook covers the full range up to 162M/day or only up to some intermediate point. The traffic response matrix (Section 1.3) that would clarify this is absent.

### 12. Redis Sizing Has Two Branches That Cannot Be Compared

The document states Redis sizing has two explicit branches depending on FCM verification outcome (findings 5 and 11). Both branches are in sections (1.4, 6.1, 6.2) that are absent. An engineer cannot evaluate whether the two branches are actually distinct, whether the worse branch is still acceptable, or whether the ordering constraint (retention window → FCM verification → Redis provisioning) is correctly enforced.

### 13. The Standalone Scale-Down Fallback Is Circular in a New Way

The document states that if the document itself is unavailable, the scale-down procedure is in `ops/runbooks/notification-scaledown.md`. But the document also states that the CI completeness check runs against a manifest in `ops/runbooks/section-manifest.txt` in the same external repo. If the external repo is the dependency that makes the document unavailable (repo outage, access issue), both the fallback procedure and the CI verification mechanism fail simultaneously. The fallback does not survive the failure mode it is designed for.