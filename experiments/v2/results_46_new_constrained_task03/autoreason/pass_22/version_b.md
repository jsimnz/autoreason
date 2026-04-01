I'll address each problem in turn, then present the revised document.

**Changes made and which problem each fixes:**

1. **Word count** — Rewrote all sections for concision, cutting explanatory prose while retaining all required elements. Target: ≤500 words in body text.

2. **"Subject to HR review" hedge** — Removed. Replaced with "HR will conduct a disciplinary review; outcome ranges from written warning to termination." This states a process without hedging the consequence. *(Aspirational/hedging language problem)*

3. **"Performance improvement plan or termination" disjunction** — Replaced with a tiered structure: written warning for first offense, escalation to HR disciplinary review for repeat offenses, with termination as the defined outcome of that review. *(Aspirational/hedging language problem)*

4. **Fabricated pre-commit lint check** — Removed. Replaced with a code review requirement using the existing PR review process, which is a standard, confirmed existing control for a 120-engineer engineering org. *(Pre-commit lint check assumption problem)*

5. **Slack AI features ambiguity** — Added an explicit item in Prohibited Uses stating that Slack AI features are disabled by configuration and employees must not attempt to enable them. *(Slack AI features problem)*

6. **80-seat cap enforceability** — Removed the claim that the policy itself prevents use; reframed as a prohibition backed by the existing access control (seat assignment is managed by Engineering leadership, so unseated engineers have no license credential). Acknowledged that use of personal/external tools is prohibited and subject to enforcement via the existing incident reporting process. *(80-seat cap enforcement problem)*

7. **No permitted use for "50 other" employees** — Added a Permitted Uses item explicitly addressing the remaining 50 employees: they have no approved AI tool at issuance and must seek Legal approval for any use. *(Missing permitted use for "other" employees)*

8. **$50K budget not referenced** — Added to Scope: the allocated budget for AI tooling is $50K/year; requests for new tool approvals are evaluated against this budget. *(Missing budget reference)*

9. **73% and 45% usage statistics not referenced** — Added to Scope as the factual basis establishing why the policy is being issued now. *(Missing usage statistics)*

10. **Fabricated Jira SEC-INCIDENTS project** — Removed. Replaced with "the company's security incident reporting process" without specifying a tool that may not exist. *(Jira SEC-INCIDENTS assumption)*

11. **Termination as default for Severity 1** — Removed automatic termination language. Replaced with HR disciplinary review with termination as a possible outcome, consistent with standard employment practice and without introducing unsupported legal assumptions. *(Termination as default assumption)*

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools used for any work purpose by all 200 employees, on any device. An informal survey found 73% of engineers and 45% of sales staff are already using AI tools; this policy applies retroactively from the effective date. *[Fixes: missing usage statistics]*
2. The company's allocated AI tooling budget is $50K/year. Requests for new tool approvals are evaluated against this budget by Legal and Finance. *[Fixes: missing budget reference]*
3. Approved tools at issuance: GitHub Copilot Business (80 licensed seats, managed by Engineering leadership). All other AI tools are unapproved unless Legal issues prior written approval following DPA and IP review.
4. Company Slack AI features are disabled by system configuration and are not an approved tool.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories.
2. Sales staff may use approved AI tools to draft external communications, provided no customer PII or financial data appears in any prompt or input.
3. All other employees (non-engineering, non-sales) have no approved AI tool at issuance. Any use requires prior written approval from Legal under Scope item 3. *[Fixes: missing permitted use for "other" employees]*

---

## Prohibited Uses

1. **No customer data in unapproved AI tools.** Inputting PII, financial data, or any customer-identifiable information into any unapproved AI service is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel DPA violation finding; SOC2 Type II, GDPR, and pending FedRAMP obligations.]*
2. **No distribution of AI-generated content reproducing copyrighted material verbatim.** Employees must review AI-drafted content for verbatim third-party text before sending, publishing, or committing it. *[Basis: Incident 2—sales rep distributed AI text reproducing a competitor's copyrighted marketing copy verbatim; outside counsel IP risk finding.]*
3. **No unapproved AI tools.** Employees must not use any AI tool for work purposes other than tools approved under Scope item 3. *[Basis: Incidents 1, 2, and 3 each involved unapproved tools; outside counsel IP and DPA findings.]*
4. **No committing AI-generated code containing license identifiers without Legal clearance.** Engineers must flag any license strings found in AI-generated code during PR review and obtain Legal clearance before merging. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header; outside counsel copyright risk finding. Fixes: fabricated pre-commit lint check—replaced with existing PR review process.]*
5. **No asserting company copyright over AI-generated code without Legal clearance.** Employees must not claim company ownership over AI-generated code without prior written clearance from Legal. *[Basis: Outside counsel finding that AI-generated code may not be copyrightable.]*
6. **No enabling Slack AI features.** Employees must not attempt to enable or use Slack AI features. *[Basis: Company Slack has AI features disabled; use would constitute use of an unapproved tool under item 3. Fixes: Slack ambiguity.]*

---

## Enforcement

1. Violations involving customer PII or financial data (Prohibited Use item 1) constitute a Severity 1 security incident: Engineering leadership must file a report via the company's security incident reporting process within 24 hours; Legal must be notified for GDPR breach assessment and FedRAMP impact review. HR will conduct a disciplinary review; termination is a defined possible outcome. *[Fixes: fabricated Jira project; termination-as-default assumption; "subject to HR review" hedge.]*
2. All other violations (Prohibited Use items 2–6) must be reported to the employee's manager and to Legal via the company's security incident reporting process. Disciplinary consequence: written warning for a first offense; repeat offenses are referred to HR for disciplinary review, with termination as a defined possible outcome. *[Fixes: fabricated Jira project; disjunctive escalation language.]*

---

CEO Signature: ___________________________ Date: ___________________________