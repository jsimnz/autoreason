I'll address each problem in turn, then present the revised document.

**Changes made and problems fixed:**

- **Problem 1 (word count):** Condensed all sections to reduce total policy content to under 500 words. Tightened phrasing throughout.
- **Problem 2 (numbered items in Enforcement):** Replaced lettered sub-items with fully numbered top-level items (1–9), each a discrete, self-contained rule.
- **Problem 3 (unenforceable Legal deadline in Permitted Uses item 2):** Removed the 60-day task assignment. Replaced with a rule governing employee behavior: sales employees have no approved tool and must obtain prior written Legal approval before using any AI tool.
- **Problem 4 (unenforceable FedRAMP prohibition):** Removed Prohibited Use item 4. No existing access control or review process can identify FedRAMP-scoped systems, and the base facts provide no mechanism from which one is derivable.
- **Problem 5 (automatic Article 33 notification):** Replaced the mandatory Article 33 notification with a requirement that Legal assess whether a notifiable breach has occurred under GDPR, which is the legally correct trigger.
- **Problem 6 (review burden on discovering employee):** Revised Prohibited Use item 2 and its enforcement item to place the review obligation and reporting obligation on the originating employee—the one who used and sent the AI-generated content.
- **Problem 7 (copyright ownership risk not addressed as standalone):** Added a new Prohibited Use item covering all AI-generated code: engineers must not represent AI-generated code as original company IP without Legal clearance, referencing outside counsel's finding that such code may not be copyrightable.
- **Problem 8 (45% of sales using AI unaddressed):** Added a Permitted Uses item establishing that sales employees currently using AI tools must cease use of unapproved tools by a defined date (14 days from effective date) and may not resume without prior written Legal approval, making the transition explicit and enforceable.
- **Problem 9 (Slack AI mechanism overstated):** Removed "by system configuration." Revised to state only that Slack AI features are disabled and are not an approved tool, consistent with the base facts.

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools used for any work purpose by all employees, on any device, from the effective date forward.
2. Approved tools at issuance: GitHub Copilot Business (80 licensed seats, managed by Engineering). All other AI tools require prior written Legal approval following DPA and IP review before use.
3. Slack AI features are disabled and are not an approved tool.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories.
2. Sales employees currently using unapproved AI tools must cease that use within 14 days of the effective date. Continued or new use of any AI tool by sales employees requires prior written Legal approval under Scope item 2.
3. All other employees have no approved AI tool at issuance; any use requires prior written Legal approval under Scope item 2.

---

## Prohibited Uses

1. **No customer data in AI inputs.** Employees must not input PII, financial data, or any customer-identifiable information into any AI service. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel DPA violation finding; SOC2 Type II and GDPR obligations.]*
2. **No distributing AI-generated content without review.** The employee who generates AI-drafted content must review it for verbatim third-party text before sending, publishing, or committing it. *[Basis: Incident 2—sales rep distributed AI text reproducing a competitor's copyrighted marketing copy verbatim; outside counsel IP risk finding.]*
3. **No committing AI-generated code containing license identifiers without Legal clearance.** Engineers must flag license strings in AI-generated code during PR review and obtain Legal clearance before merging. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header.]*
4. **No representing AI-generated code as original company IP without Legal clearance.** Engineers must disclose AI-generated code in PR review; Legal clearance is required before asserting ownership. *[Basis: Outside counsel finding that AI-generated code may not be copyrightable.]*

---

## Enforcement

1. Violations of Prohibited Use item 1 are Severity 1 security incidents; the violating employee must report to their manager immediately upon discovery.
2. The manager must file a security incident report within 24 hours of notification of a Prohibited Use item 1 violation.
3. Legal must assess whether a notifiable personal data breach has occurred under GDPR and act accordingly within the applicable regulatory timeframe.
4. HR will conduct a disciplinary review for Prohibited Use item 1 violations; termination is a defined possible outcome.
5. The employee who generated and distributed content in violation of Prohibited Use item 2 must report to Legal via the security incident process immediately upon discovery.
6. Legal will assess whether retraction or third-party notification is required for Prohibited Use item 2 violations.
7. Prohibited Use item 2 first offense results in a written warning; repeat offenses are referred to HR, with termination as a defined possible outcome.
8. All other violations must be reported by the violating employee to their manager and Legal via the security incident process immediately upon discovery.
9. All other violations: first offense results in a written warning; repeat offenses are referred to HR, with termination as a defined possible outcome.

---

CEO Signature: ___________________________ Date: ___________________________