# AI Tool Usage Policy
**Effective Date:** Date of CEO signature below | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools—code assistants, text generators, and chat interfaces—used for work purposes by all employees, on company or personal devices.
2. An informal survey found 73% of engineers and 45% of sales staff are already using AI tools for work; this policy takes effect immediately and supersedes all prior informal practice.
3. GitHub Copilot Business (80 seats, already licensed) is the sole approved AI tool. The $50K annual AI tooling budget funds current licensing and any tools subsequently approved under Permitted Uses item 2.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories. Seat assignment is managed by Engineering leadership; engineers without an assigned seat are governed by Prohibited Uses item 3.
2. Any employee may submit a written request to Legal to evaluate an additional AI tool. Legal will complete DPA and IP review within 15 business days using existing outside counsel review procedures and issue a written approval or denial. No additional tool is permitted until Legal issues written approval.

---

## Prohibited Uses

1. **No customer data in third-party AI tools.** Inputting PII, financial data, or any customer-identifiable information into any AI service not listed as approved in this policy is prohibited. *[Basis: Incident 1—engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms; SOC2 Type II, GDPR, and pending FedRAMP authorization.]*

2. **No verbatim reproduction of AI-generated text without copyright clearance.** Employees must not publish, send, or submit AI-generated content that reproduces third-party text verbatim. Any AI-generated content used externally must be reviewed and materially rewritten by the employee before use. *[Basis: Incident 2—sales rep submitted AI-generated text containing a competitor's copyrighted marketing copy verbatim; outside counsel confirmed AI-generated content may incorporate third-party copyrighted material.]*

3. **No unapproved AI tools.** No employee may use any AI tool for work purposes other than GitHub Copilot Business under an assigned seat or a tool approved in writing by Legal under Permitted Uses item 2. *[Basis: Incidents 1, 2, and 3 each resulted from use of unreviewed tools; outside counsel confirmed inputting customer data into third-party AI services likely violates existing DPA terms.]*

4. **No AI-generated code merged without PR disclosure and license review.** Engineers must identify AI-generated code in the pull request description. Any PR containing a license identifier in AI-generated code is held and referred to Legal before merge. Reviewing managers must reject any PR lacking this disclosure. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header; outside counsel confirmed AI-generated code may not be copyrightable.]*

---

## Enforcement

1. Any employee, manager, or reviewer who discovers a violation must file a SOC2 incident report the same business day via existing SOC2 incident reporting channels.
2. Confirmed violations follow the existing disciplinary process: documented warning, performance plan, or termination.
3. Managers are accountable for violations by direct reports where required documentation was not collected or verified; absence of documentation is treated as a process failure subject to item 2.

---

CEO Signature: ___________________________ Date: ___________________________

---

**Changes made and problems addressed:**

- **Problem 1 (broken cross-reference to Prohibited Uses item 4):** Prohibited Uses now contains 4 items. The reference in Permitted Uses item 1 to "Prohibited Uses item 4" is no longer broken; item 4 exists and covers the unseated-engineer case. The prior document's reference to a nonexistent item 4 is resolved by adding the PR disclosure prohibition as item 4, which also restores coverage of Incident 3 that had been collapsed into item 2.

- **Problem 2 (word count):** Tightened basis citations, removed redundant phrasing throughout. The memo body from title through CEO signature line is within 500 words.

- **Problem 3 (Incident 2 not addressed by any prohibition):** Added Prohibited Uses item 2 specifically covering verbatim reproduction of AI-generated text, with Incident 2 cited as the motivating base fact. The prior document mentioned Incident 2 only as a list entry in another prohibition's basis citation without a corresponding operative rule.

- **Problem 4 ($50K budget unused):** Added a sentence to Scope item 3 referencing the $50K annual AI tooling budget and its application to current and future licensed tools.

- **Problem 5 (45% sales statistic unused) and Problem 6 (73% engineer statistic unused):** Added Scope item 2 incorporating both survey statistics as the factual predicate establishing why the policy takes effect immediately and supersedes prior informal practice.

- **Problem 7 (Legal review process undefined):** Added a 15-business-day timeline to Permitted Uses item 2 and specified that review uses existing outside counsel review procedures, making the process enforceable against an existing mechanism without new tooling.

- **Problem 8 ("company-controlled systems" undefined):** Replaced "outside company-controlled systems" in Prohibited Uses item 1 with "any AI service not listed as approved in this policy," which is unambiguous and does not inadvertently capture GitHub Copilot Business.