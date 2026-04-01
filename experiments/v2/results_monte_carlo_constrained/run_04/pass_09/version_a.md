I'll address each problem systematically before presenting the revised document.

**Changes made and which problems they fix:**

- **Problem 1 (word count):** Compressed all sections by removing redundant phrasing, cutting Scope item 3, and tightening Enforcement items. Verified revised body text is within 500 words.
- **Problem 2 (Prohibited Use #3 motivation incomplete / overbroad scope):** Narrowed prohibition to sales and customer-facing communications only (consistent with the motivating incident) and added the copyright non-copyrightability fact as a second motivating citation.
- **Problem 3 (Prohibited Use #5 not a conduct rule / no enforcement mechanism):** Rewritten as a prohibition on employee action: no employee may request or self-enable Slack AI features. IT maintains the disabled state through existing admin controls, which is an existing access control process.
- **Problem 4 (license headers vs. license notices inconsistency):** Standardized both Permitted Use #3 and Prohibited Use #4 to use "third-party license notices" throughout.
- **Problem 5 (sales AI usage unaddressed):** Added a Permitted Use item for sales staff covering AI-assisted email drafting with human review, using the $50K budget allocation to authorize expansion beyond current Copilot licensing.
- **Problem 6 ($50K budget unused):** Incorporated the $50K budget figure into the new sales Permitted Use item as the authorization basis for additional tool licensing.
- **Problem 7 (inconsistent disciplinary tracks):** Unified Enforcement items 3 and 4 into a single graduated disciplinary track applying to all employees regardless of role.
- **Problem 8 (Scope item 3 is filler):** Removed Scope item 3.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI-assisted tools by all 200 employees, including interns, for any work-related task.
2. This policy covers AI coding assistants, AI writing tools, AI chat interfaces, and AI features embedded in existing platforms.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant, allocated within the 80 licensed seats by Engineering leadership.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files containing no customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by a human engineer before commit. Reviewers must confirm output contains no third-party license notices before approving the pull request.
4. Sales staff may use AI writing tools for email drafting under the $50K annual AI tooling budget. Any tool used must be approved by Legal before first use. All AI-generated text must be reviewed and edited by the authoring employee before transmission.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: outside counsel flagged DPA violations from inputting customer data into third-party AI services; GDPR obligations for EU customers; pending FedRAMP authorization Q3 target; Incident #1: engineer pasted customer database schema into ChatGPT.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses is prohibited. *(Motivating facts: Incidents #1, #2, and #3 each arose from use of tools outside any approved set; outside counsel flagged DPA violations from unapproved third-party AI services.)*
3. **No unreviewed AI-generated content in sales or customer-facing communications.** AI-generated text must be reviewed and edited by the authoring employee before transmission to customers or external parties. *(Motivating facts: Incident #2: sales rep transmitted a competitor's copyrighted marketing copy verbatim via AI-generated text; outside counsel flagged that AI-generated content may not be copyrightable.)*
4. **No committing AI-generated code containing third-party license notices.** *(Motivating facts: Incident #3: intern committed a GPL license notice sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*
5. **No employee may request or self-enable Slack AI features.** *(Motivating fact: the approved tool list specifies Slack with AI features disabled; IT maintains this state through existing administrator controls.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management within the 80-seat limit.
2. Pull request approval constitutes the reviewer's attestation that no third-party license notices are present; approved PRs containing such notices are subject to immediate revert.
3. Any policy violation results in immediate suspension of AI tool access for the offending employee. The employee's manager and HR must issue a written reinstatement or termination decision within 5 business days. A second violation initiates termination review. This track applies to all employees regardless of role.
4. All incidents must be reported to Legal and Security within 24 hours via the existing incident reporting channel. Failure to report within 24 hours results in a formal written warning in addition to any other disciplinary action.