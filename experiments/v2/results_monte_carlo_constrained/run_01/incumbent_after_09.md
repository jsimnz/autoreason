I'll address each problem, then present the revised document.

**Changes made and problems addressed:**

- **Problem 1:** Removed the editorial preamble entirely.
- **Problem 2:** Cut word count aggressively across all sections to meet the 500-word limit.
- **Problem 3:** Collapsed the 5 audit-trail sub-items into their parent prohibition items; Enforcement is now a flat numbered list.
- **Problem 4:** Removed termination language; no disciplinary outcome beyond access revocation is derivable from base facts.
- **Problem 5:** Removed permanent-revocation escalation; no disciplinary ladder exists in base facts.
- **Problem 6:** Removed "written warning"; no HR warning framework is derivable from base facts.
- **Problem 7:** Removed Finance head sign-off requirement; Finance has budget authority in base facts but no stated approval role over tool selection.
- **Problem 8:** Rewrote the Slack prohibition basis to lead with the DPA violation rationale; removed the circular current-state justification.
- **Problem 9:** Removed Legal's mandatory pre-execution review role; replaced with a prohibition on the representation itself, enforceable by the contracting employee's manager.
- **Problem 10:** Removed the implication that sales staff have a currently approved AI writing tool. Sales AI drafting is now addressed only as a future possibility through the approval process.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work.
2. This policy covers both company-licensed tools and personal or free-tier tools used for company purposes.
3. Compliance is required to maintain SOC2 Type II certification, meet GDPR obligations for EU customers, and satisfy pending FedRAMP authorization requirements.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding tool. Engineering leadership assigns and revokes the 80 licensed seats; no seat may be shared.
2. Copilot-seated engineers may use GitHub Copilot for code completion, boilerplate generation, and test writing within the licensed environment only.
3. All AI-generated code must pass human pull request review before merge.
4. Additional AI tools may be approved through joint written sign-off from the heads of Engineering and Legal, within the $50K annual budget. Approved tools are added to this policy by amendment before use begins.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. Managers audit violations using HR incident records. *[Basis: Incident 1; outside counsel confirmed this violates existing DPA terms and creates GDPR and FedRAMP liability.]*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects without human review confirming it contains no third-party copyrighted material. Sales management reviews outbound email records monthly and escalates flagged items to Legal. *[Basis: Incident 2—sales rep sent AI output containing verbatim competitor copyrighted marketing copy.]*
3. **No commits containing AI-generated code with third-party license headers.** Reviewers must reject any pull request carrying such a header. Pull request history constitutes the audit trail. *[Basis: Incident 3—intern committed code with a GPL header sourced from AI training data.]*
4. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack. Slack administrator logs and denies all such requests. *[Basis: Outside counsel confirmed that enabling Slack AI features routes company and customer data through an unapproved external AI service, violating existing DPA terms.]*
5. **No representation of AI-generated code as independently copyrightable company IP** in contracts or customer deliverables. The responsible employee's manager reviews any flagged contract language before execution. *[Basis: Outside counsel flagged that AI-generated code may not be copyrightable; Incident 3 demonstrated AI output can carry third-party IP encumbrances.]*

---

## Enforcement

1. A confirmed violation results in revocation of AI tool access pending manager review.
2. Violations are reported to the employee's direct manager upon discovery.
3. Legal is notified immediately for any incident involving customer data.
4. Managers document all violations in HR incident records; these records constitute the official violation log.