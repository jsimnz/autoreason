**Changes made:**

- **Problem 8:** Revision notes block removed entirely.
- **Problems 1, 2, 3, 4:** Permitted Uses item 2 deleted. It described a non-existent permission and forward-looking conditional state. No base fact supports a current permitted use for sales AI tools, so no item is warranted. Word count reduction also addresses Problem 1.
- **Problem 7:** Permitted Uses item 3 (mandatory review requirement) moved to Enforcement as a new item 5, where procedural requirements belong.
- **Problem 5:** Enforcement item 2 detection mechanisms expanded to include manager attestation and communication review, covering sales staff and all employee categories subject to Prohibition 2.
- **Problem 6:** Scope item 3 stripped of its embedded prohibition ("No additional tool may be used..."). The approved tool statement remains as a scoping fact. The prohibition on unapproved tools is carried entirely by Prohibited Uses item 2, which already exists and carries the required motivating fact citations.

---

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

---

## Prohibited Uses

1. **No customer data in any AI tool.** *(Motivating facts: Incident #1; SOC2 Type II certification; GDPR obligations; pending FedRAMP authorization; outside counsel DPA violation finding.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Scope item 3 for work-related tasks is prohibited. Written approval from the CEO and Legal is required before any additional tool may be used. *(Motivating facts: Outside counsel DPA violation finding; 73% of engineers and 45% of sales already using unapproved tools informally.)*
3. **No third-party IP in merged or delivered content.** Reviewers must reject code containing third-party license headers or GPL markers. Managers must reject external communications containing verbatim third-party copyrighted material. *(Motivating facts: Incident #2; Incident #3.)*
4. **No delivery of AI-generated work product without human authorship review.** All AI-generated code and content must be substantively reviewed and attested by the submitting employee before delivery or merge. *(Motivating fact: Outside counsel finding that AI-generated code may not be copyrightable, creating company IP ownership risk.)*

---

## Enforcement

1. Violations of Prohibition 1 result in immediate disciplinary action up to and including termination and are reported to Legal for DPA, GDPR, and FedRAMP impact assessment.
2. Violations of Prohibition 2 identified through pull request review, document review, manager attestation, or communication audit result in a formal written warning. A second violation within 12 months results in termination.
3. Violations of Prohibition 3 or 4 require reversion or withholding of affected content and disciplinary review of both the submitting employee and the approving reviewer. A second violation within 12 months by either party results in termination.
4. Unauthorized procurement of AI tools in violation of Prohibition 2 results in immediate revocation of purchasing authority and disciplinary review.
5. All AI-generated code and content must receive manager or pull request reviewer approval before merge or external delivery, using existing pull request workflows and email approval chains.