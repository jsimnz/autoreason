# AI Tool Usage Policy
**Effective Date:** [Date] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools—including code assistants, writing tools, and generative AI services—by all 200 employees in company-owned and personal workflows connected to company data or deliverables.
2. This policy supersedes all informal practices. Prior use without policy coverage does not establish precedent.
3. Compliance with this policy is a condition of employment and contractor engagement.

---

## Permitted Uses

1. **GitHub Copilot Business** (80 licensed seats) is the sole approved AI coding assistant. Seat assignments are managed by Engineering Ops. Copilot is approved for work-related use because it is already licensed and does not receive customer PII or financial data under permitted use conditions.
2. Copilot may be used for code completion, test generation, and documentation on codebases containing no customer PII or financial data.
3. AI-drafted sales and customer communications are permitted only when the final text is reviewed, edited, and sent by the authoring employee.
4. Requests for additional AI tools against the $50K annual tooling budget require Legal sign-off before use.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Motivating facts: Incident #1 schema exposure; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved external AI services.** Using AI tools not authorized under Section 2 for any work-related task is prohibited. *(Motivating facts: Outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No unreviewed AI-generated code committed to production.** All AI-generated code requires human review confirming the absence of third-party license headers, GPL markers, or verbatim copied text before merge. *(Motivating facts: Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
4. **No AI-generated content published externally without IP review.** Sales or marketing content must be checked against source material before external distribution. *(Motivating fact: Incident #2 verbatim competitor copyrighted copy.)*
5. **Slack AI features must not be enabled.** No employee may request or configure re-enablement without CISO and Legal approval. *(Motivating facts: Outside counsel DPA violation flag applies to any unapproved AI service processing company data; SOC2 Type II and pending FedRAMP obligations.)*

---

## Enforcement

1. Violations of Prohibited Use items 1–2 are reportable security incidents. Employees must self-report to Security within 24 hours; managers must escalate to CISO within 48 hours. Failure to self-report is itself a violation subject to the disciplinary framework in item 4.
2. Engineering Leads conduct AI-usage spot audits during existing monthly code review cycles. Sales Managers review outbound AI-assisted communications during existing pipeline review cycles.
3. Pull request templates are updated immediately to include a mandatory checkbox: *"No AI-generated code present, OR AI-generated code reviewed for license markers and IP conflicts."*
4. First violations result in mandatory retraining and a documented written warning. Repeat or willful violations proceed under the standard disciplinary process, up to and including termination.
5. Legal reviews this policy at each SOC2 audit cycle and prior to FedRAMP authorization submission.

---

**Changes made and problems addressed:**

- **Problem 1 (word count):** Removed "AI attribution is not required externally" from Permitted Use #3, compressed Permitted Use #4 to one sentence, and tightened phrasing throughout to bring the document within 500 words.
- **Problem 2 (Prohibition #5 circular motivation):** Replaced the self-referential motivating fact with substantive base facts: the outside counsel DPA flag and SOC2/FedRAMP compliance obligations, which independently motivate keeping unapproved AI services disabled.
- **Problem 3 (attribution language):** Removed "AI attribution is not required externally" from Permitted Use #3, as no base fact supports it.
- **Problem 4 (invented budget process):** Replaced the invented Department Head submission route with a single sentence derivable from the base facts: a $50K budget exists and Legal sign-off is required.
- **Problem 5 (sales AI usage unaddressed):** Added a sales-specific audit mechanism to Enforcement #2, using existing pipeline review cycles, consistent with the constraint against requiring new tooling.
- **Problem 6 (Copilot exemption unexplained):** Added an explicit statement in Permitted Use #1 that Copilot is approved on the basis that it does not receive customer PII or financial data under permitted conditions, making the distinction from the ChatGPT incident logically explicit.
- **Problem 7 (non-reporting unenforced):** Added a sentence to Enforcement #1 stating that failure to self-report is itself a violation subject to the disciplinary framework in item 4.
- **Problem 8 ("deliberate control" framing):** Removed the phrase "deliberate control" from Prohibition #5; the prohibition now stands on cited compliance obligations rather than an assumed organizational intent.