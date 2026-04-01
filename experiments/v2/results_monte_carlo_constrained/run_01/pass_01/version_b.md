# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI-powered tools—including code assistants, writing assistants, and generative models—by all 200 employees across engineering, sales, and all other functions.
2. This policy applies to company-licensed tools and personal or free-tier AI tools accessed on company devices or for company work.
3. Compliance with this policy is required to maintain SOC2 Type II certification, GDPR obligations, and FedRAMP authorization targeted for Q3.
4. As of this policy's effective date, all prior informal use of AI tools not listed under Permitted Uses is unauthorized. Employees currently using other tools must cease that use immediately; no grandfather period applies. *(Fixes Problem 6: acknowledges the 73%/45% survey findings and eliminates ambiguity about existing unauthorized use.)*

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI tool for all employees. Use is limited to the 80 licensed seats; Engineering leadership assigns and revokes seats within 5 business days of a request.
2. The 40 engineers without an assigned Copilot seat may not use any AI coding assistant until a seat is assigned to them. Seat waitlist priority is set by Engineering leadership. *(Fixes Problem 7: addresses the 40 engineers without seats.)*
3. Engineers with assigned seats may use GitHub Copilot Business for code completion, boilerplate generation, and test writing on codebases containing no customer PII or financial data.
4. All AI-generated code must pass human pull request review before merge. Reviewers check for third-party license headers or identifiable copied content and are accountable for approving compliant code only.
5. The $50K annual AI tooling budget is administered by Engineering and Finance jointly; no new AI tool may be expensed or deployed without written approval from both.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR liability.]*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be sent to customers or prospects without a human reviewer reading it for third-party copyrighted material before sending. *[Basis: Incident 2—sales rep sent AI output containing verbatim competitor copyrighted marketing copy.]* *(Fixes Problem 3: "confirming" replaced with a concrete process step.)*
3. **No commits containing AI-generated code with open-source license headers.** Reviewers must reject such pull requests during human code review. *[Basis: Incident 3—intern committed code with a GPL header sourced from AI training data.]* *(Fixes Problem 4: enforcement is through existing human PR review, not automated tooling.)*
4. **No representation of AI-generated work as independently copyrightable company IP** in contracts, filings, or customer deliverables. *[Basis: Outside counsel flagged that AI-generated code may not be copyrightable.]*

---

## Enforcement

1. Violations are investigated by the employee's direct manager and HR within 5 business days of identification.
2. Confirmed violations result in: first offense—written warning and mandatory policy re-acknowledgment; second offense—revocation of AI tool access and performance review; third offense or any incident causing customer data exposure—termination and legal referral. *(Fixes Problem 3: "potential legal referral" replaced with "legal referral.")*
3. Pull request reviews and access logs for GitHub Copilot Business serve as the audit trail; no new tooling is required.
4. This policy is acknowledged via the existing annual policy sign-off process in the HR system.

---

**Changes summary by problem:**
- **Problem 1 (word count):** Removed Permitted Use #3 permitting unnamed sales drafting tools and Prohibited Use #4 on Slack re-enabling, which also fixed Problems 2 and 5; remaining edits were net reductions.
- **Problem 2 (Slack prohibition):** Removed Prohibited Use #4 entirely; no base fact motivates a prohibition on re-enabling Slack AI features beyond the current disabled state.
- **Problem 3 (hedging language):** Replaced "confirming it contains no" with "reading it for" in Prohibited Use #2; replaced "potential legal referral" with "legal referral" in Enforcement #2.
- **Problem 4 (automated tooling implied):** Replaced "are blocked from merge" with "Reviewers must reject such pull requests during human code review."
- **Problem 5 (unapproved sales tools):** Removed Permitted Use #3 granting sales access to unnamed AI drafting tools; GitHub Copilot Business is now the sole approved tool.
- **Problem 6 (survey figures unaddressed):** Added Scope #4 acknowledging prior informal use and establishing no grandfather period.
- **Problem 7 (40 engineers without seats):** Added Permitted Use #2 explicitly governing engineers without assigned seats.