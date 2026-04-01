# AI Tool Usage Policy
**Effective Date:** Date of CEO signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools used for any work purpose by all employees, on any device.
2. The only approved AI tools at issuance are: GitHub Copilot Business (80 licensed seats, managed by Engineering leadership) and any tool for which Legal has issued prior written approval following DPA and IP review. All other tools are unapproved.
3. Engineers without an assigned Copilot seat have no approved AI coding tool; they are subject to the prohibitions in this policy until a seat is assigned or Legal approves an alternative.

*Fixes: "Scope item 3 is a status note, not a policy directive" — replaced the Slack observation with an actionable rule. "40 engineers without a seat have no actionable permitted use" — Scope item 3 now addresses their status directly.*

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories. Engineers without an assigned seat may not use Copilot.
2. Sales staff may use approved AI tools to draft external emails, provided no customer PII or financial data is included in any prompt or input.

---

## Prohibited Uses

1. **No customer data in unapproved AI tools.** Inputting PII, financial data, or any customer-identifiable information into any unapproved AI service is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel DPA violation finding; SOC2 Type II, GDPR, and pending FedRAMP obligations.]*
2. **No distribution of AI-generated content reproducing copyrighted material verbatim.** Employees must not send, publish, or commit AI-generated content that reproduces third-party copyrighted material verbatim. Before sending any AI-drafted external communication, the authoring employee must review it for verbatim third-party text. *[Basis: Incident 2—sales rep distributed AI-generated text reproducing a competitor's copyrighted marketing copy verbatim; IP risk flagged by outside counsel.]*
3. **No unapproved AI tools.** Employees must not use any AI tool for work purposes other than tools approved under Scope item 2. *[Basis: Incidents 1, 2, and 3 each involved unapproved tools; outside counsel IP and copyright findings arose directly from that use; the 80-seat cap means unsanctioned use by unseated engineers constitutes use of an unapproved tool.]*
4. **No committing AI-generated code containing license identifiers without Legal clearance.** Engineers must scan AI-generated code for license strings using the repository's existing pre-commit lint checks before submission; any match must be referred to Legal before the PR is submitted. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header; copyright risk flagged by outside counsel.]*
5. **No asserting company copyright over AI-generated code without Legal clearance.** Employees must not claim company ownership over AI-generated code without prior written clearance from Legal. *[Basis: Outside counsel finding that AI-generated code may not be copyrightable.]*

*Fixes: "Prohibited Use item 4 introduces a new process" — replaced the novel PR-description certification with a direction to use existing pre-commit lint checks. "No mechanism for enforcing item 2" — added an explicit pre-send review obligation on the authoring employee using no new tooling. "No reference to 80-seat cap as a limiting fact" — added to item 3 basis.*

---

## Enforcement

1. Violations involving customer PII or financial data (Prohibited Use item 1) constitute a Severity 1 security incident: Engineering leadership must file a SOC2 incident report within 24 hours and notify Legal for GDPR breach assessment and FedRAMP impact review. Disciplinary consequence: termination, subject to HR review.
2. Violations involving unapproved tools, license identifiers, or copyright claims (Prohibited Use items 3, 4, and 5) must be reported to the employee's manager and to Legal via the SOC2 incident ticketing system (currently Jira, project: SEC-INCIDENTS). Disciplinary consequence: documented written warning for a first offense; performance improvement plan or termination for repeat offenses.
3. Violations involving distribution of verbatim copyrighted content (Prohibited Use item 2) must be reported to Legal via SEC-INCIDENTS immediately upon discovery. Legal will assess whether retraction or third-party notification is required. Disciplinary consequence: documented written warning for a first offense; performance improvement plan or termination for repeat offenses.

*Fixes: "No specific consequences tied to specific violations" — each enforcement item now specifies the violation category and its disciplinary consequence. "Existing SOC2 incident reporting channels not defined" — identified as Jira project SEC-INCIDENTS. "No mechanism for enforcing Prohibited Use item 2" — item 3 now addresses it specifically with a defined reporting path.*

---

CEO Signature: ___________________________ Date: ___________________________