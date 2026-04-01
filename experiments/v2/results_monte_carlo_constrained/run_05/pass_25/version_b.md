I'll address each problem in turn, then present the revised document.

**Changes made and problems addressed:**

- **Problem 1 (word count):** Tightened prose throughout, particularly in Prohibited Uses motivating citations and Enforcement, to reduce total word count.
- **Problem 2 (circular motivation for Prohibition 2):** Replaced the DPA-only citation with the three incidents collectively, which directly motivate the need to control which tools are used. The incidents all involve unapproved or uncontrolled tool use causing harm.
- **Problem 3 (Scope item 3 unsupported inference):** Removed "allocated to engineering roles" — the seat allocation to specific roles is not stated in the base facts.
- **Problem 4 (Permitted Uses item 2 is a prohibition):** Removed the prohibitory content from Permitted Uses and relocated the substance to Prohibited Uses. Permitted Uses item 2 is now a genuine permission.
- **Problem 5 (budget unused):** Added the $50K budget in Scope as the authorized budget ceiling for AI tooling approvals.
- **Problem 6 (45% sales statistic unused):** Added to Scope to establish factual basis for the policy's applicability to sales.
- **Problem 7 (73% engineer statistic unused):** Added to Scope alongside the sales statistic.
- **Problem 8 (Enforcement item 2 cross-reference mismatch):** Corrected so PR review and document review are cited under Prohibition 3/4 enforcement, and Prohibition 2 enforcement references the appropriate detection mechanisms (expense review, IT audit, manager reporting).
- **Problem 9 (vague "disciplinary review"):** Replaced with defined outcomes (written warning, then termination) consistent with the pattern used elsewhere.

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all employees on company systems or when handling company data or deliverables.
2. "Customer data" means any PII, financial data, database schemas, or configuration files identifying or derived from customer environments.
3. An informal survey found 73% of engineers and 45% of sales staff are already using AI tools for work tasks. This policy applies retroactively to all such use from its effective date.
4. GitHub Copilot Business (80 licensed seats) is the sole currently approved AI tool. A $50K annual budget is authorized for approving additional tools through the process in Prohibited Uses item 2.

---

## Permitted Uses

1. Employees with an assigned GitHub Copilot Business seat may use it for code completion, test generation, and documentation on files containing no customer data.
2. Employees in any role may request approval to use additional AI tools by submitting a written request to the CEO and Legal; approved tools are added to Scope item 4.

---

## Prohibited Uses

1. **No customer data in any AI tool.** *(Motivating facts: Incident #1; SOC2 Type II certification; GDPR obligations; pending FedRAMP authorization; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms.)*
2. **No unapproved AI tools for work-related tasks.** Any tool not listed in Scope item 4 requires written CEO and Legal approval before use. *(Motivating facts: Incidents #1, #2, and #3 each resulted from uncontrolled tool use; outside counsel DPA finding.)*
3. **No third-party IP in merged or delivered content.** Reviewers must reject code containing third-party license headers or GPL markers. Managers must reject external communications containing verbatim third-party copyrighted material. *(Motivating facts: Incident #2; Incident #3.)*
4. **No delivery of AI-generated work product without human authorship review.** All AI-generated code and content must be substantively reviewed and attested by the submitting employee before delivery or merge. *(Motivating fact: Outside counsel finding that AI-generated code may not be copyrightable, creating IP ownership risk.)*

---

## Enforcement

1. Violations of Prohibition 1 result in immediate disciplinary action up to and including termination and are reported to Legal for DPA, GDPR, and FedRAMP impact assessment.
2. Violations of Prohibition 2, identified through IT audit, expense review, or manager reporting, result in a formal written warning. A second violation within 12 months results in termination. Unauthorized tool procurement also results in immediate revocation of purchasing authority.
3. Violations of Prohibition 3 or 4, identified through pull request review or document review, require reversion or withholding of affected content. The submitting employee and approving reviewer each receive a formal written warning. A second violation within 12 months by either party results in termination.