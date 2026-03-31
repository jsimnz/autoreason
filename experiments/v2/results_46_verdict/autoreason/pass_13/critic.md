## Real Problems

### 1. The Document Ends Mid-Sentence

Section 1.1d cuts off: "Determination of which provisioning scenario" — the document is incomplete. Any decision-maker reading this cannot act on it as written.

---

### 2. The Circuit Breaker Threshold Is Internally Inconsistent

The executive summary sets the P2 circuit breaker at 4,000/sec. Section 1.1b sets the provisioned design ceiling at 6,400/sec instantaneous. If the system can handle 6,400/sec, a circuit breaker at 4,000/sec fires during normal burst traffic, not just overload events. The document never reconciles this. The 4,000/sec figure appears to have been chosen independently of the throughput analysis in §1.1b.

---

### 3. The Month 2 Review Has No Defined Consequence for Non-Action

Section 1.1d specifies an owner, format, quorum rules, and deliverables with considerable precision. It does not specify what happens if the review findings require provisioning changes and those changes are not implemented. The escalation path for the traffic review itself is absent. The document treats the review as self-enforcing, which it is not.

---

### 4. P0 Classification Circular Dependency Is Understated

The document acknowledges the circular dependency between the SMS budget analysis and the §3.1 taxonomy, then says it "adds at most 2 days to the week 1 schedule." There is no basis for the 2-day estimate. The taxonomy session could produce a P0 definition that invalidates the entire SMS budget matrix — for example, if P0 volume comes in at 5% rather than 1-2%. The document treats taxonomy definition as a bounded, fast task when it is actually a product negotiation with no guaranteed timeline.

---

### 5. WebSocket Scaling Claim Is Contradicted by Its Own Caveat

Section 1.1a states that horizontal WebSocket scaling is valid "because WebSocket connections are stateless between messages." This is only true if no feature requires cross-instance awareness. The document then immediately acknowledges that cross-instance fan-out would require Redis pub/sub and defers that decision. For a social app, cross-instance fan-out is not an edge case — it is the normal case when a user receives a notification while connected to any instance. The scaling claim assumes away the primary coordination problem.

---

### 6. The Burst Multiplier Validation Timeline Is Too Late

The 3× burst multiplier is explicitly called "an estimate, not a derived figure" and is scheduled for validation in month 5 load testing. The system launches before month 5. A real viral event before that point is explicitly described as "an unvalidated region." This is not a mitigation — it is an acknowledgment that the system's core capacity ceiling is unvalidated during the entire launch window.

---

### 7. The SMS Allowlist Emergency Process Has No Rollback Path

The emergency allowlist addition process allows merging and deploying a change within 30 minutes with two approvals. There is no specified rollback procedure if the emergency addition proves incorrect or is abused. Given that the allowlist directly controls SMS spend and that the document's own analysis shows SMS costs can reach $47,250/month, an incorrect emergency addition has immediate and significant financial consequences with no fast-path reversal defined.

---

### 8. Engineer Assignments Are Undefined Except for E4

Section 1.1d assigns the month 2 review to E4 and names E1 as the backup. No other section assigns work to specific engineers. With 4 engineers and 6 months, the absence of ownership assignments beyond one administrative task is a gap the document does not acknowledge. It is unclear whether this is intentional deferral or an omission.

---

### 9. The "Shed P2 Notifications Queued for Off-Peak" Claim Is Unanalyzed

The executive summary states that shed P2 notifications are queued for the next off-peak window, not dropped. No section analyzes what happens to that queue under sustained overload. If the condition causing P2 shedding persists across multiple peak windows, the deferred queue grows unboundedly. The document presents queuing-instead-of-dropping as a safe default without examining the failure mode.

---

### 10. The $25,000/Month Operational Target Is Described as Both a Ceiling and Not a Ceiling

Section 1.1c states "$25,000/month operational target" and then immediately states "no automated hard cap on security-critical notifications." The $25,000 figure is then called a ceiling "enforced through human escalation." A target enforced through human escalation after the fact is not a ceiling — it is a lagging indicator. The document uses both terms for the same number without distinguishing them, which will cause confusion in budget conversations.