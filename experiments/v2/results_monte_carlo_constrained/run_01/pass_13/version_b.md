I'll address each problem, then present the revised document.

**Changes made and why:**

- **Problem 1 & 4:** Removed the preamble entirely. Tightened language throughout the memo body to bring the word count under 500.
- **Problem 2:** Added the $50K budget figure to Permitted Uses item 4 as the stated ceiling for additional tool spend, which is directly derivable from the base fact.
- **Problem 3:** Replaced the circular self-referential basis in Prohibited Uses item 4 with the actual motivating base facts: DPA terms, GDPR obligations, and FedRAMP authorization requirements that make any unapproved AI data-processing feature a compliance risk.
- **Problem 5:** Replaced the invented sign-off process in Permitted Uses item 4 with a reference to the existing $50K budget allocation and the existing GitHub Copilot seat management process as the control mechanism.
- **Problem 6:** Removed "immediately" and replaced with a concrete, enforceable step tied to existing HR and Legal intake processes.
- **Problem 7:** Restructured Enforcement items 3 and 4 so that item 3 applies to all confirmed violations (HR file entry), and item 4 specifies the additional consequence of seat revocation where AI tool access exists—eliminating the inconsistency.
- **Problem 8:** Merged the duplicate HR file language from former items 4 and 5 into a single item.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work, including personal or free-tier tools used for company purposes.
2. An internal survey found 73% of engineers and 45% of sales staff already use AI tools without an official policy; this policy governs all such existing and future use.
3. Compliance is required to maintain SOC2 Type II certification, meet GDPR obligations for EU customers, and satisfy requirements under the pending FedRAMP authorization.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding tool. Engineering leadership assigns and revokes the 80 licensed seats; no seat may be shared.
2. Copilot-seated engineers may use GitHub Copilot for code completion, boilerplate generation, and test writing within the licensed environment only.
3. All AI-generated code must receive human reviewer approval before merge.
4. Additional AI tools may be adopted only within the $50K annual AI tooling budget. Engineering leadership adds any new tool to the approved seat inventory before use begins; use without that inventory entry is a policy violation.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR and FedRAMP liability.]*
2. **No AI-generated external content without manager approval.** AI-generated text intended for external distribution requires direct manager approval before sending. *[Basis: Incident 2—a sales rep distributed AI-generated text containing a competitor's copyrighted marketing copy verbatim.]*
3. **No commits containing AI-generated code with third-party license headers.** Pull request reviewers must reject any pull request carrying such a header; pull request history is the audit trail. *[Basis: Incident 3—an intern committed AI-generated code carrying a GPL license header originating from AI training data.]*
4. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack. *[Basis: Company handles customer PII and financial data subject to DPA terms, GDPR obligations, and FedRAMP requirements; enabling Slack AI features would route that data through a third-party AI service without approved data processing agreements.]*

---

## Enforcement

1. The discovering employee or reviewer reports any suspected violation to the violating employee's direct manager upon discovery.
2. The manager routes any violation involving customer data to Legal using the existing Legal intake process within one business day.
3. A confirmed violation is recorded in the employee's existing HR file, which serves as the official violation log, and triggers a mandatory manager review within five business days.
4. Where the confirmed violation involves AI tool access, Engineering leadership revokes that access through existing GitHub Copilot seat controls or Slack administrator controls as applicable.