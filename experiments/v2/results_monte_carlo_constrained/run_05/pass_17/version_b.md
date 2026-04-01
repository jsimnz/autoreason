I'll address each problem in turn, then present the revised document.

**Changes made and which problems they fix:**

- **Problem 1 (word count):** Compressed all sections, eliminated redundant cross-references, shortened motivating-fact citations, and removed filler language throughout to bring the document under 500 words.

- **Problem 2 (fifth section):** Removed the standalone Definition block. The definition of "customer data" is folded into Scope item 1 as a parenthetical, where it functions as part of a policy rule rather than a separate structural section.

- **Problem 3 (non-enforceable filler in Enforcement item 4):** Removed "No new tooling is required." The item now states only the enforceable review obligation.

- **Problem 4 (incorrect characterization of survey data):** Removed the reference to "unapproved tools without controls" as a gloss on the survey figures. The motivating fact cited is now only the three incidents, which directly establish the risk of uncontrolled AI use.

- **Problem 5 (Scope items as recitals):** Rewrote Scope items 2–4 as affirmative policy rules (what is authorized, what is not available, what employees without seats must do) rather than restatements of background facts.

- **Problem 6 (unenforceable "if available" seat allocation):** Removed sales and other-employee Copilot permissions entirely. The 80 seats are allocated to engineers. Sales and other employees have no approved tool until a new tool is approved. This is directly supported by the base facts (80 seats, 120 engineers as the primary user population) and eliminates the unenforceable availability condition.

- **Problem 7 (new approval process not in base facts):** Removed the formal written tool-approval workflow from Enforcement. The prohibition on unapproved tools is stated in Prohibited Uses; the Enforcement section references only existing review processes (pull request approvals, manager review, escalation to Legal and CEO) that are derivable from the base facts.

- **Problem 8 (new self-certification process):** Removed the employee self-certification requirement. IP review responsibility is reassigned to pull request reviewers and managers using existing review workflows, which are derivable from the base facts.

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables. "Customer data" means any PII, financial data, database schemas, or configuration files that identify or are derived from customer environments.
2. GitHub Copilot Business is the sole approved AI tool. The 80 licensed seats are allocated to engineering roles. Employees without an assigned seat have no approved AI tool.
3. Company Slack AI features are disabled and unavailable under this policy.
4. Employees without an approved tool assignment have no permitted AI use for any work-related task.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, test generation, and documentation on files that do not contain customer data.
2. All AI-generated code and external written content is subject to manager or pull request reviewer approval before merge or delivery, using existing pull request workflows and email approval chains.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer data into any AI service is prohibited. *(Motivating facts: Incident #1, engineer pasted customer database schema into ChatGPT; SOC2 Type II certification requirements; GDPR obligations for EU customers; outside counsel determination that inputting customer data into third-party AI services likely violates existing DPA terms.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited. *(Motivating facts: Incident #2, AI-generated sales text contained verbatim competitor copyrighted marketing copy; Incident #3, AI-generated code contained a GPL license header committed to the codebase.)*
3. **No AI-generated content merged or delivered without IP review.** Pull request reviewers must reject code containing third-party license headers or GPL markers. Managers must reject external communications containing verbatim third-party copyrighted material. *(Motivating facts: Incident #2 verbatim copyrighted copy; Incident #3 GPL header in committed code; outside counsel determination that AI-generated code may not be copyrightable.)*
4. **No new AI tool approved or used without Legal clearance.** No AI tool outside Permitted Uses may be used until Legal confirms in writing that its use does not violate existing DPA terms and does not jeopardize the pending FedRAMP authorization. *(Motivating facts: Outside counsel DPA flag; pending FedRAMP authorization with Q3 target.)*

---

## Enforcement

1. Violations of Prohibited Uses items 1–2 result in immediate disciplinary action up to and including termination.
2. Violations of Prohibited Uses item 3 require reversion or withholding of the affected content and disciplinary review of both the submitting employee and the approving reviewer. Repeated violations escalate to termination.
3. Violations of Prohibited Uses item 4 are escalated immediately to Legal and the CEO, the tool is suspended, and disciplinary action up to and including termination follows.
4. Manager and pull request reviewer approval of all AI-generated code and external content is mandatory before merge or delivery, using existing approval workflows.