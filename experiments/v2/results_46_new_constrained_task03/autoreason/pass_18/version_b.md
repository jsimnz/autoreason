I'll address each problem, then present the revised document.

**Changes made and why:**

**Problem 1 & 2 (word count; preamble not part of deliverable):** Removed the preamble entirely. The memo stands alone.

**Problem 3 (Permitted Uses gap for sales):** Added a third item to Permitted Uses explicitly permitting sales staff to use GitHub Copilot Business seats (where assigned) for email drafting, closing the gap between the base fact (45% of sales already using AI) and the policy.

**Problem 4 (copyright verification unenforceable without new tooling):** Removed the employee verification requirement. Replaced it with an obligation that is enforceable using the existing PR and outbound-communications approval process: managers must hold and refer to Legal any outbound content flagged by a recipient or discovered to contain verbatim third-party text—a reactive, process-based obligation rather than a proactive detection requirement.

**Problem 5 (Scope item 4 circular):** Rewrote Scope item 4 to remove the self-referential loop. An approved tool is now defined as GitHub Copilot Business or any tool Legal has issued written approval for following DPA and IP review. No cross-reference to Permitted Uses.

**Problem 6 (Enforcement item 1 conflates timeframes):** Unified the timeframe. Both the SOC2 incident report and Legal notification for PII/financial data violations are required immediately—defined as within the same business day the violation is discovered.

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools used for work purposes by all employees, on any device.
2. The approved AI tool is GitHub Copilot Business (80 licensed seats), funded from the $50K annual AI tooling budget.
3. Company Slack AI features remain disabled. Re-enabling them requires prior written approval from Legal.
4. An approved tool is GitHub Copilot Business or any tool for which Legal has issued written approval following DPA and IP review. All other tools are unapproved.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories. Seat assignment is managed by Engineering leadership. Engineers without an assigned seat may not use Copilot.
2. Sales staff with an assigned GitHub Copilot Business seat may use it for drafting outbound communications. Seat assignment is managed by Sales leadership. Sales staff without an assigned seat may not use Copilot.
3. Any employee may submit a written request to Legal to evaluate an additional AI tool. No additional tool is permitted until Legal issues written approval following DPA and IP review.

---

## Prohibited Uses

1. **No customer data in unapproved AI tools.** Inputting PII, financial data, or any customer-identifiable information into any unapproved AI service is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; DPA violation risk flagged by outside counsel; SOC2 Type II, GDPR, and pending FedRAMP obligations.]*

2. **No distribution of AI-generated content later found to reproduce copyrighted material.** Where outbound AI-generated content is found or alleged to reproduce third-party copyrighted material verbatim, the responsible manager must immediately halt further distribution and refer the matter to Legal. *[Basis: Incident 2—sales rep distributed AI-generated text reproducing a competitor's copyrighted marketing copy verbatim; IP risk flagged by outside counsel.]*

3. **No unapproved AI tools.** No employee may use any AI tool for work purposes other than tools approved under Scope item 4. *[Basis: Incidents 1, 2, and 3 each involved use of unapproved tools; outside counsel's IP and copyright findings arose directly from that unapproved use.]*

4. **No AI-generated code merged without license review.** Reviewing managers must check all PR code for license identifiers before approving merge. Any PR containing a license identifier in generated code is held and referred to Legal before merge. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header; copyright risk flagged by outside counsel.]*

---

## Enforcement

1. Any violation involving customer PII or financial data requires both a SOC2 incident report and notification to Legal for GDPR and FedRAMP assessment, both completed within the same business day the violation is discovered.
2. All other violations must be reported via SOC2 incident reporting channels by end of the business day the violation is discovered.
3. Violations follow the existing disciplinary process: documented warning, performance plan, or termination.
4. Managers are accountable for violations by direct reports where required review was not performed; failure to perform required review is itself a violation subject to item 3.

---

CEO Signature: ___________________________ Date: ___________________________