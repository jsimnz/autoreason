I'll address each problem, then present the revised memo only—no preamble in the deliverable.

**Changes made and why:**

1. **Removed the change-log preamble from the deliverable** — fixes Problem 1 (document is not a memo) and Problem 2 (word count).
2. **Revised Permitted Use #3** to remove the budget gatekeeping claim and conditional "until" framing — fixes Problems 3 and 8. The item now states only what the base facts support: non-engineering tools require CTO written approval, and the $50K budget is allocated for AI tooling.
3. **Deleted Enforcement item 4 (Slack AI)** — fixes Problem 4 (orphaned enforcement item with no corresponding prohibition).
4. **Revised Permitted Use #2** to remove the "author of record" claim — fixes Problem 5. The item now requires legal review of copyright status rather than asserting an ownership claim outside counsel says is uncertain.
5. **Added FedRAMP citation to Prohibited Use #4** — fixes Problems 6 and 7. The pending FedRAMP authorization is now explicitly cited as a motivating base fact in a prohibition.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** CTO | **Audience:** All Employees, Contractors, and Interns

---

## Scope

1. This policy applies to all employees, contractors, and interns using any AI tool for any work-related task, on company or personal devices.
2. This policy covers AI-assisted code generation, text generation, and conversational AI interfaces.

---

## Permitted Uses

1. Engineers with assigned seats may use GitHub Copilot Business, allocated by Engineering Leads via GitHub admin controls.
2. AI-assisted code generation is permitted only when an Engineering Lead approves the pull request containing that code, confirming the code has been reviewed for open-source license artifacts and that its copyright status has been assessed by Legal.
3. Employees in non-engineering roles may use AI tools only when those tools are explicitly approved in writing by the CTO. The $50K annual AI tooling budget is allocated for AI tooling; no tool is approved for use without CTO written authorization.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Incident 1: engineer pasted a customer database schema into ChatGPT; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
2. **No unverified AI-generated content in outbound communications.** Sending or publishing AI-generated text without confirming it contains no third-party copyrighted material is prohibited. *(Incident 2: sales rep sent AI-generated text containing a competitor's copyrighted marketing copy verbatim)*
3. **No AI-generated code committed without legal review.** Committing AI-generated code that contains open-source license artifacts or that has not been reviewed for copyright ownership is prohibited. *(Incident 3: intern committed code with a GPL header from AI training data; outside counsel finding that AI-generated code may not be copyrightable)*
4. **No unapproved AI tools for work purposes.** Using any AI service not listed as approved in this policy is prohibited for all covered individuals. *(Incidents 1 and 2 involved unapproved external services; outside counsel DPA finding; pending FedRAMP authorization requires demonstrable control over all data-handling tools)*

---

## Enforcement

1. Engineering Leads verify compliance during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
2. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and treated as a data incident under the existing SOC2 incident response process.
3. Engineering Leads flag license artifacts and copyright ownership gaps during code review (Prohibited Use #3) and escalate to Legal.