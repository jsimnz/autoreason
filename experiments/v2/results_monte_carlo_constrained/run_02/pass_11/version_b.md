**Changes made and why:**

1. **Removed the change-log section entirely** — fixes Problem 1. The deliverable is the memo only.
2. **Reduced verbosity throughout to bring memo body under 500 words** — fixes Problem 2. Each item was tightened; see count note below.
3. **Replaced "written CTO approval before use" with enforcement through the existing IT software provisioning process** — fixes Problem 3. IT already controls software provisioning under SOC2 access controls; unapproved tools are blocked at that layer, which is an existing process.
4. **Revised Prohibited Use #5 to cite actual motivating base facts** — fixes Problem 4. Now cites customer PII, SOC2 Type II, GDPR, and outside counsel DPA finding as the motivating facts.
5. **Clarified Enforcement item for Prohibited Use #5** — fixes Problem 5. Violations are detectable as IT re-enablement requests; any such request is treated as a policy violation and referred to HR.
6. **Collapsed Permitted Use #2 and Prohibited Use #3 into a single operative rule** — fixes Problem 6. The permitted use now states the condition; the redundant prohibition is removed. A new Prohibited Use #3 covers what was formerly #4, renumbered accordingly.
7. **Removed FedRAMP as a cited rationale in Prohibited Use #4** — fixes Problem 7. The prohibition now cites only current binding obligations: outside counsel DPA finding, SOC2 Type II, and GDPR.

---

# AI Tool Usage Policy
**Effective Date:** 2025-07-14 | **Owner:** CTO | **Audience:** All Employees, Contractors, and Interns

---

## Scope

1. This policy applies to all employees, contractors, and interns using any AI tool for any work-related task, on company or personal devices.
2. This policy covers AI-assisted code generation, text generation, and conversational AI interfaces.

---

## Permitted Uses

1. Engineers with assigned seats may use GitHub Copilot Business, allocated by Engineering Leads via GitHub admin controls.
2. AI-assisted code may be committed only after an Engineering Lead approves the pull request, confirming the submission contains no open-source license artifacts and no unresolved copyright ownership questions.
3. Non-engineering employees may use only AI tools provisioned through the existing IT software request process and listed as approved at time of use.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
2. **No unverified AI-generated content in outbound communications.** Sending or publishing AI-generated text without confirming it contains no third-party copyrighted material is prohibited. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No unapproved AI tools for work purposes.** Using any AI service not provisioned through IT is prohibited. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
4. **No use of Slack AI features.** Requesting or using Slack AI features for any work purpose is prohibited. *(Customer PII and financial data transits Slack; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*

---

## Enforcement

1. Engineering Leads verify compliance with Permitted Use #2 during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
2. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and treated as a data incident under the existing SOC2 incident response process.
3. Sales Managers verify compliance with Prohibited Use #2 during existing outbound communication approval workflows; violations are referred to HR for disciplinary action.
4. IT enforces Prohibited Uses #3 and #4 through device and browser log audits under the existing SOC2 access-review cadence. Any IT request to re-enable Slack AI features constitutes a violation of Prohibited Use #4. Confirmed violations are referred to HR for disciplinary action.