I'll address each problem in turn, then present the revised document.

**Changes made and problems addressed:**

- **Problem 1 (word count):** Tightened language throughout all sections to bring the body under 500 words.
- **Problem 2 (Permitted Uses #3 adds non-base-fact tool pathway):** Deleted Permitted Uses #3. No approved tool exists for non-engineers in the base facts; the item cannot stand.
- **Problem 3 (Slack AI motivation is an added fact):** Changed the motivation citation for Prohibited Use #5 to reference only the base fact: Slack AI features are currently disabled and the company holds SOC2 Type II certification and GDPR obligations. Removed the unsupported assertion that PII transits Slack.
- **Problem 4 ("unresolved copyright ownership questions" is unenforceable):** Replaced the unenforceable legal-determination condition in Permitted Uses #2 with a concrete, enforceable action: Engineering Leads must confirm no open-source license headers or identifiers are present in the committed code, which is an observable artifact check, not a legal conclusion.
- **Problem 5 (80-seat cap unaddressed):** Added a numbered item to Permitted Uses stating that seat allocation follows Engineering Lead assignment and that engineers without an assigned seat must not use GitHub Copilot Business until a seat is available.
- **Problem 6 (FedRAMP not referenced):** Added FedRAMP pending authorization as a cited motivation in Prohibited Use #4, where the restriction on unapproved external AI services is most directly relevant.
- **Problem 7 (dual enforcement of Prohibited Use #4):** Removed Prohibited Use #4 from Engineering Lead enforcement scope in Enforcement #1; Engineering Leads enforce only Prohibited Use #3. IT retains sole enforcement of #4 and #5.
- **Problem 8 (IT request treated as a violation):** Replaced the incoherent "request constitutes a violation" language with a clear statement that re-enabling Slack AI features by any means is the prohibited act, and that IT enforces this through existing access-review controls.

---

# AI Tool Usage Policy
**Effective Date:** 2025-07-14 | **Owner:** CTO | **Audience:** All Employees, Contractors, and Interns

---

## Scope

1. This policy applies to all employees, contractors, and interns using any AI tool for any work-related task, on company or personal devices.
2. This policy covers AI-assisted code generation, text generation, and conversational AI interfaces.

---

## Permitted Uses

1. Engineers with assigned seats may use GitHub Copilot Business; seats are allocated by Engineering Leads via GitHub admin controls. Engineers without an assigned seat may not use GitHub Copilot Business until a seat is assigned.
2. AI-assisted code may be committed only after an Engineering Lead approves the pull request, confirming the submission contains no open-source license headers or license identifiers introduced by the AI tool.
3. No AI tool other than GitHub Copilot Business is currently approved for any work purpose.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
2. **No unverified AI-generated content in outbound communications.** Sending or publishing AI-generated text without confirming it contains no third-party copyrighted material is prohibited. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without Engineering Lead review.** Committing AI-generated code containing open-source license headers or identifiers is prohibited. *(Incident 3: intern committed code with a GPL header from AI training data; outside counsel finding that AI-generated code may not be copyrightable)*
4. **No unapproved AI tools for work purposes.** Using any AI service not listed in Permitted Use #3 is prohibited. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding; SOC2 Type II, GDPR obligations, and pending FedRAMP authorization)*
5. **No enabling of Slack AI features.** Re-enabling Slack AI features by any means for any work purpose is prohibited. *(Slack AI features are currently disabled; SOC2 Type II and GDPR obligations)*

---

## Enforcement

1. Engineering Leads verify compliance with Prohibited Use #3 during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
2. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and treated as a data incident under the existing SOC2 incident response process.
3. Sales Managers verify compliance with Prohibited Use #2 during existing outbound communication approval workflows; violations are referred to HR for disciplinary action.
4. IT enforces Prohibited Uses #4 and #5 through device and browser log audits under the existing SOC2 access-review cadence. Confirmed violations are referred to HR for disciplinary action.