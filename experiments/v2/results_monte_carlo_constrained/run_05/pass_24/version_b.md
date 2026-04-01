# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all employees on company systems or when handling company data or deliverables.
2. "Customer data" means any PII, financial data, database schemas, or configuration files identifying or derived from customer environments.
3. GitHub Copilot Business (80 licensed seats, allocated to engineering roles) is the sole currently approved AI tool for work-related tasks.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, test generation, and documentation on files containing no customer data.
2. All other employees — including sales and non-engineering roles — have no approved AI tool for work-related tasks. Any work-related AI use requires written approval from the CEO and Legal before use begins.

---

## Prohibited Uses

1. **No customer data in any AI tool.** *(Motivating facts: Incident #1; SOC2 Type II certification; GDPR obligations; pending FedRAMP authorization; outside counsel DPA violation finding.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Scope item 3 for work-related tasks is prohibited. *(Motivating facts: Outside counsel DPA violation finding; outside counsel finding that inputting customer data into third-party AI services likely violates existing DPA terms.)*
3. **No third-party IP in merged or delivered content.** Reviewers must reject code containing third-party license headers or GPL markers. Managers must reject external communications containing verbatim third-party copyrighted material. *(Motivating facts: Incident #2; Incident #3.)*
4. **No delivery of AI-generated work product without human authorship review.** All AI-generated code and content must be substantively reviewed and attested by the submitting employee before delivery or merge. *(Motivating fact: Outside counsel finding that AI-generated code may not be copyrightable, creating company IP ownership risk.)*

---

## Enforcement

1. Violations of Prohibition 1 result in immediate disciplinary action up to and including termination and are reported to Legal for DPA, GDPR, and FedRAMP impact assessment.
2. Violations of Prohibition 2 identified through pull request review, document review, or manager attestation result in a formal written warning. A second violation within 12 months results in termination.
3. Violations of Prohibition 3 or 4 require reversion or withholding of affected content and disciplinary review of both the submitting employee and the approving reviewer. A second violation within 12 months by either party results in termination.
4. Unauthorized procurement of AI tools in violation of Prohibition 2 results in immediate revocation of purchasing authority and disciplinary review.

---

**Changes made:**

- **Problems 1 and 2:** "Changes made" block removed from the deliverable body. Word count of the policy memo itself is within the 500-word limit.
- **Problem 3:** Permitted Uses item 2 added, explicitly addressing sales and non-engineering employees by stating they have no approved tool and specifying the approval path required before any use begins. This eliminates the enforcement ambiguity for the 80 non-Copilot-seat employees.
- **Problem 4:** Enforcement item 5 (conduct rule requiring manager or PR approval before merge/delivery) removed from Enforcement. That requirement is carried by Prohibited Uses item 4, which already prohibits delivery without human authorship review.
- **Problem 5:** Prohibition 2 motivating fact citation revised. The prevalence survey finding ("73% of engineers and 45% of sales already using unapproved tools informally") is removed. The citation now references the outside counsel DPA violation finding, which identifies the actual risk motivating the prohibition.
- **Problem 6:** "Communication audit" removed from Enforcement item 2's detection mechanisms. Detection is now limited to pull request review, document review, and manager attestation — all processes supportable by existing access controls and workflows identified in the base facts.