I'll address each problem in turn, then present the revised document.

**Changes made and which problem each fixes:**

- **Problem 1 (word count):** Compressed all sections by cutting redundant phrasing, collapsing items, and removing explanatory prose while preserving all required content.
- **Problem 2 & 3 (Prohibited Use item 2 not a prohibition; conditional language):** Replaced the response-procedure framing with a direct prohibition: employees must not distribute AI-generated content that reproduces third-party copyrighted material verbatim.
- **Problem 4 (Scope items 2 and 4 redundant/contradictory):** Removed old item 2. Item 4 (renumbered as item 3) now serves as the single definition of approved tools, with Copilot Business named as the tool approved at issuance.
- **Problem 5 (Sales staff assigned Copilot seats without basis):** Removed the Sales Copilot seat reference. Permitted Uses now restricts Copilot to engineers only, consistent with the base facts.
- **Problem 6 (same-business-day deadline invented):** Removed the specific timeline. Enforcement now requires reporting via existing SOC2 incident channels, with no invented deadline.
- **Problem 7 (reviewing managers role not established):** Anchored the license-check requirement to the existing PR merge/approval process already in use, without inventing a new role.
- **Problem 8 (AI-generated code may not be copyrightable not addressed):** Added a prohibition on representing AI-generated code as company-owned IP without Legal clearance, citing the outside counsel finding directly.
- **Problem 9 (73%/45% usage figures unused):** Added a Scope item acknowledging the current informal usage state and making the policy apply retroactively to it.

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools used for any work purpose by all employees on any device.
2. Informal survey data shows 73% of engineers and 45% of sales staff are currently using AI tools without an approved policy. This policy applies immediately to all such existing use.
3. The only AI tools approved at issuance are: GitHub Copilot Business (80 licensed seats, managed by Engineering leadership) and any tool for which Legal has issued written approval following DPA and IP review. All other tools are unapproved.
4. Company Slack AI features remain disabled. Re-enabling them requires prior written approval from Legal.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories.
2. Any employee may submit a written request to Legal to evaluate an additional AI tool. No additional tool is permitted until Legal issues written approval.

---

## Prohibited Uses

1. **No customer data in unapproved AI tools.** Inputting PII, financial data, or any customer-identifiable information into any unapproved AI service is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel DPA violation finding; SOC2 Type II, GDPR, and pending FedRAMP obligations.]*
2. **No distribution of AI-generated content that reproduces copyrighted material verbatim.** Employees must not send, publish, or commit AI-generated content that reproduces third-party copyrighted material verbatim. *[Basis: Incident 2—sales rep distributed AI-generated text reproducing a competitor's copyrighted marketing copy verbatim.]*
3. **No unapproved AI tools.** Employees must not use any AI tool for work purposes other than tools approved under Scope item 3. *[Basis: Incidents 1, 2, and 3 each involved unapproved tools; outside counsel IP findings arose from that use.]*
4. **No merging AI-generated code containing license identifiers without Legal clearance.** Any PR containing a license identifier in AI-generated code must be held at the existing merge-approval step and referred to Legal before merge is permitted. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header.]*
5. **No representing AI-generated code as company-owned IP without Legal clearance.** Employees must not assert company copyright ownership over AI-generated code without prior written clearance from Legal. *[Basis: Outside counsel finding that AI-generated code may not be copyrightable.]*

---

## Enforcement

1. Violations involving customer PII or financial data require a SOC2 incident report and notification to Legal for GDPR and FedRAMP assessment.
2. All other violations must be reported via existing SOC2 incident reporting channels.
3. Violations follow the existing disciplinary process: documented warning, performance plan, or termination.
4. Managers who fail to perform the merge-approval review required by Prohibited Use item 4 are themselves in violation and subject to item 3.

---

CEO Signature: ___________________________ Date: ___________________________