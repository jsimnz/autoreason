I'll address each problem in turn, then present the revised document.

**Changes made and their motivations:**

- **Problem 1 (word count):** Cut aggressively throughout — condensed items, removed redundant phrases, merged where possible.
- **Problem 2 (Scope item 4):** Removed the characterization of past behavior as non-compliant; restated neutrally as a statement of known adoption.
- **Problem 3 (Enforcement item 1):** Split the run-on into three discrete numbered items (1a/1b/1c logic → items 1, 2, 3), then renumbered.
- **Problem 4 (Permitted Uses item 2):** Removed the per-repository admin enablement condition; scoped use to licensed seats only.
- **Problem 5 (Enforcement item 2):** Separated the audit trails for Prohibited Use #1 (manager attestation and HR records, since no existing tool captures external ChatGPT use) and Prohibited Use #3 (PR history).
- **Problem 6 (Permitted Uses item 3):** Replaced "identifiable copied content" with the concrete, checkable standard already established in Prohibited Use #3: third-party license headers.
- **Problem 7 (FedRAMP not cited):** Added FedRAMP as a co-basis in Prohibited Use #1, where external data handling is directly at stake.
- **Problem 8 (budget unenforced):** Added Finance sign-off as an existing process that creates a paper trail; cited Finance records as the audit trail in Enforcement.
- **Problem 9 (new disclosure process):** Removed the AI-use disclosure requirement from Enforcement item 5, as no existing mechanism supports it.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work.
2. This policy covers company-licensed tools and personal or free-tier tools used for company purposes.
3. Compliance is required to maintain SOC2 Type II certification, meet GDPR obligations for EU customers, and satisfy pending FedRAMP authorization requirements.
4. Company survey data shows 73% of engineers and 45% of sales staff currently use AI tools; this policy establishes the rules governing that use.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI tool. Use is limited to the 80 licensed seats; Engineering leadership assigns and revokes seats.
2. Copilot-seated engineers may use GitHub Copilot for code completion, boilerplate generation, and test writing.
3. All AI-generated code must pass human pull request review before merge. Reviewers are accountable for confirming the absence of third-party license headers before approving.
4. Additional AI tools require joint written sign-off from Engineering and Finance within the $50K annual budget.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms, creating GDPR liability; this also implicates pending FedRAMP authorization controls.]*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects without human review confirming it contains no third-party copyrighted material. *[Basis: Incident 2—sales rep sent AI output containing verbatim competitor copyrighted marketing copy.]*
3. **No commits containing AI-generated code with third-party license headers.** Reviewers must reject any pull request carrying such a header, including GPL. *[Basis: Incident 3—intern committed code with a GPL header sourced from AI training data.]*
4. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack. *[Basis: Slack AI features are currently disabled; enabling them routes company and customer data through an unapproved external AI service, violating DPA terms per outside counsel.]*
5. **No representation of AI-generated work as independently copyrightable company IP** in contracts, filings, or customer deliverables. *[Basis: Outside counsel flagged that AI-generated code may not be copyrightable.]*

---

## Enforcement

1. Violations are reported to the employee's direct manager within one business day of discovery.
2. The manager opens a formal HR investigation within five business days of the report; confirmed violations result in disciplinary action up to and including termination.
3. Incidents involving customer data exposure are referred to Legal immediately upon discovery.
4. Prohibited Use #1: Manager attestation and HR incident records constitute the audit trail; no existing tool captures external service use, so managers are responsible for intake and documentation.
5. Prohibited Use #2: Outbound email records and CRM activity logs constitute the audit trail; Sales management reviews flagged communications upon complaint or spot-check.
6. Prohibited Use #3: Pull request history constitutes the audit trail; Engineering leadership reviews quarterly.
7. Prohibited Use #4: Slack workspace admin logs record any request to enable AI features; the Slack administrator denies all such requests.
8. Prohibited Use #5 and Permitted Uses #4: Legal reviews all customer contracts and IP filings before execution; Finance records of joint sign-off constitute the audit trail for unapproved tool spend.