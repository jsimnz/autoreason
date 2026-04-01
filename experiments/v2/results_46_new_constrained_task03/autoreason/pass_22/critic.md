## Problems Found

### Constraint Violations

**Word count.** The document substantially exceeds 500 words. The body text alone (excluding headers, the signature block, and formatting labels) runs well over 500 words. This is a hard constraint violation.

**Aspirational/hedging language.** The constraint explicitly prohibits hedging language. "Subject to HR review" in Enforcement item 1 is a hedge — it conditions the stated consequence on a secondary process, making the stated penalty unenforceable as written. Similarly, "performance improvement plan or termination" in items 2 and 3 is disjunctive in a way that gives no enforceable guidance; a manager can always choose the lesser option, making the escalation threat hollow.

---

### Things That Don't Work As Described

**Pre-commit lint check assumption.** Prohibited Use item 4 states engineers must scan AI-generated code using "the repository's existing pre-commit lint checks." There is no base fact establishing that any such lint checks exist or are configured to detect license strings. This is a fabricated enforcement mechanism, which also violates the constraint that the policy be enforceable using existing access controls and review processes — it references a process not confirmed to exist.

**Slack AI features.** The base facts state the company's Slack instance has AI features disabled. The policy never addresses this. Employees could reasonably interpret Slack's AI features as either permitted (because it's a company tool) or irrelevant (because they're disabled). The policy creates ambiguity it doesn't resolve.

**80-seat cap enforcement.** Scope item 3 and Permitted Use item 1 state that engineers without an assigned seat have no approved tool, but there is no existing access control mechanism described or referenced that prevents an unseated engineer from using a personal ChatGPT or other tool. The policy says they "may not" but provides no mechanism to enforce this beyond honor system, which contradicts the enforceability constraint.

---

### Missing Required Elements

**No permitted use for the "50 other" employees.** The Scope correctly applies to all 200 employees, but Permitted Uses only address engineers and sales staff. The 50 "other" employees have no permitted use defined, leaving their status entirely unclear — are they prohibited from all AI use, or is this an oversight?

**No reference to the $50K budget.** The base facts include an allocated AI tooling budget. The constraint says to use all base facts. The budget figure appears nowhere in the document.

**No reference to the 45% sales usage statistic or the 73% engineer usage statistic.** The constraint says to use all base facts. These figures from the informal survey do not appear. The constraint is explicit: "use ALL of these."

---

### Assumptions That Are Wrong

**Jira SEC-INCIDENTS project.** The policy references a specific Jira project ("project: SEC-INCIDENTS") as if it exists. No base fact establishes this. This is an invented detail, and if the project doesn't exist, the enforcement mechanism in items 2 and 3 is broken on day one.

**Termination as default for Severity 1.** Specifying termination as the disciplinary consequence for a first-offense PII incident, even "subject to HR review," likely conflicts with standard employment law procedures and HR policy, none of which are established in the base facts. This is an assumption with significant legal exposure introduced without basis.