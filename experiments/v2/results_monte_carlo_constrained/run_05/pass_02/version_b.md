# AI Tool Usage Policy
**Effective Date:** [Date] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI tools—including code assistants, writing tools, and generative AI services—by all 200 employees on company systems or when handling company data or deliverables.
2. This policy supersedes all informal practices. Prior use without policy coverage does not establish precedent.
3. Compliance with this policy is a condition of employment.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) is the sole approved AI coding assistant; seat assignments are managed by Engineering Ops.
2. Copilot is approved for code completion, test generation, and documentation on codebases containing no customer PII or financial data.
3. AI-drafted sales and customer communications are permitted only when reviewed, edited, and sent by the authoring employee.
4. Requests for additional AI tools against the $50K annual tooling budget require Legal sign-off before use.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer PII, financial data, or database schemas into any AI service is prohibited. *(Incidents #1; outside counsel DPA violation flag; SOC2 Type II, GDPR, and pending FedRAMP obligations.)*
2. **No unapproved external AI services.** Using AI tools not listed in Permitted Uses for any work-related task is prohibited. *(Outside counsel DPA violation flag; pending FedRAMP authorization.)*
3. **No unreviewed AI-generated code committed to production.** All AI-generated code requires human review confirming the absence of third-party license headers, GPL markers, or verbatim copied text before merge. *(Incident #3 GPL header commit; outside counsel copyright non-ownership flag.)*
4. **No AI-generated content published externally without IP review.** Sales and marketing content must be checked against source material before external distribution. *(Incident #2 verbatim competitor copyrighted copy.)*
5. **Slack AI features must not be enabled.** No employee may request or configure re-enablement without CISO and Legal approval. *(Outside counsel DPA violation flag; SOC2 Type II and pending FedRAMP obligations.)*

---

## Enforcement

1. Violations of Prohibited Use items 1–2 are reportable security incidents. Employees must self-report to Security within 24 hours; managers must escalate to CISO within 48 hours. Failure to self-report is itself a violation subject to the disciplinary framework in item 4.
2. Engineering Leads conduct AI-usage spot audits during existing monthly code review cycles. Sales Managers review outbound AI-assisted communications during existing pipeline review cycles.
3. Pull request templates are updated immediately to include a mandatory checkbox: *"No AI-generated code present, OR AI-generated code reviewed for license markers and IP conflicts."*
4. First violations result in mandatory retraining and a documented written warning. Repeat or willful violations proceed under the standard disciplinary process, up to and including termination.

---

**Changes made and problems addressed:**

- **Problem 1 (word count):** Tightened phrasing across all sections to bring the policy body under 500 words.
- **Problem 2 (fifth section):** Removed the "Changes made" block from the submitted document body. It appears here as required revision commentary only, outside the four policy sections.
- **Problem 3 (prose in numbered items):** Broke Permitted Use item 1 into two discrete items (items 1 and 2), removing the embedded justification clause. Parenthetical motivating-fact blocks in Prohibited Uses are retained because the constraint explicitly requires each prohibition to reference its motivating base fact; they are the minimal form for satisfying that requirement.
- **Problem 4 (unverifiable personal-device claim):** Replaced "personal workflows connected to company data or deliverables" in Scope item 1 with "on company systems or when handling company data or deliverables," limiting scope to conditions enforceable through existing access controls.
- **Problem 5 (aspirational enforcement review):** Deleted Enforcement item 5 entirely; no base fact establishes Legal's commitment to periodic policy review, and the item functioned as aspirational future intent.
- **Problem 6 (sales review requirement unmotivated):** Retained Permitted Use item 3. Incident #2 shows that unreviewed AI-generated sales content caused an external IP violation; the review requirement is directly derivable from that incident as the control that would have prevented it.
- **Problem 7 (contractors not in base facts):** Removed "and contractor engagement" from Scope item 3, limiting the policy to the 200 employees established in the base facts.