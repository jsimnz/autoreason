I'll address each problem in turn, then present the revised document.

**Changes made and problems addressed:**

- **Problem 1 (word count):** Cut Prohibited Uses bases to inline citations, tightened all prose, removed redundant restatements throughout.
- **Problem 2 (item 2 is procedural, not a prohibition):** Restated as a flat prohibition: AI-generated content may not be distributed externally unless Legal has confirmed no third-party copyrighted material is present.
- **Problem 3 (Slack basis fabricated):** Replaced the fabricated causal chain with the base fact only: Slack AI features are currently disabled per company configuration.
- **Problem 4 (item 6 basis fabricated):** Removed the prohibition entirely. The base fact (outside counsel flagged copyrightability uncertainty) does not support a flat prohibition on employee assertion behavior. The legal risk is noted in the DPA/copyright prohibition where it is derivable.
- **Problem 5 (item 4 circular/adds new process):** Removed the approval-process item from Permitted Uses. The base facts do not establish a formal approval process; only the two approved tools are derivable. The $50K budget fact is used only to note the budget exists, not to invent a process.
- **Problem 6 (email enforcement unworkable):** Removed the manager pre-approval requirement for outbound written content. Replaced with a prohibition on distribution without Legal review, enforceable through existing HR incident reporting after the fact, consistent with existing processes.
- **Problem 7 (sales use case not addressed):** Prohibited Uses item 2 now explicitly covers external distribution (the harm in Incident 2) rather than banning AI drafting entirely, preserving the sales drafting use case while prohibiting the specific harmful act.
- **Problem 8 (item 4 redundant):** Removed the "no unapproved AI tools" item. Permitted Uses already defines the exclusive list; the redundant inverse adds nothing enforceable.

---

# AI Tool Usage Policy

**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [DATE]
**RE:** AI Tool Usage Policy — Effective Immediately

---

## Scope

1. This policy applies to all employees, contractors, and interns performing work for the company.
2. It governs all AI-powered tools used for company work, on company systems or networks.
3. It covers AI coding assistants, writing assistants, and any generative AI model producing code, text, or data.

---

## Permitted Uses

1. GitHub Copilot Business is the sole approved AI coding tool. Engineering leadership assigns the 80 licensed seats to named individuals via existing GitHub Copilot Business seat controls.
2. Seat-holders may use GitHub Copilot Business for code completion, boilerplate generation, and test writing.
3. All AI-generated code must pass the existing pull-request review process before merge.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1; outside counsel confirmed this violates existing DPA terms; company holds GDPR obligations and has pending FedRAMP authorization.]*
2. **No external distribution of AI-generated content without Legal review.** AI-generated text may not be sent externally unless Legal has confirmed no third-party copyrighted material is present. *[Basis: Incident 2; outside counsel flagged copyright infringement risk in AI-generated content.]*
3. **No commits with third-party license headers.** Pull-request reviewers must reject any commit carrying an AI-generated third-party license header. *[Basis: Incident 3; an intern committed AI-generated code carrying a GPL header sourced from AI training data.]*
4. **Slack AI features must remain disabled.** No employee may enable AI features within company Slack. *[Basis: Slack AI features are currently disabled per company configuration.]*

---

## Enforcement

1. For code, the pull-request reviewer must confirm AI-generated content complies with this policy before approving any merge.
2. Any employee who discovers a violation must report it to Legal through the existing HR incident reporting process within one business day of discovery.
3. Upon Legal's confirmation of a violation, Legal must record it in the employee's HR file.
4. The violating employee's direct manager must conduct a review within five business days of Legal's confirmation.
5. If the violating employee holds a seat or access grant for an approved AI tool, Engineering leadership must revoke that access through existing seat controls upon Legal's confirmation.
6. HR must administer disciplinary action, up to and including termination, through the existing HR disciplinary process upon Legal's confirmation of a violation.