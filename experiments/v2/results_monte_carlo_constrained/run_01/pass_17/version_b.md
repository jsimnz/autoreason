I'll address each problem in turn, then present the revised document.

**Changes made and which problems they fix:**

- **Problem 1 (word count):** Tightened language throughout; removed redundant phrases; deleted Scope item 3 (also fixes Problem 10).
- **Problem 2 (Enforcement item 1 aspirational):** Replaced passive expectation with a specific, triggered review event: managers must review AI-generated outputs at each code review or output approval event.
- **Problem 3 (incomplete basis citation in Prohibited item 2):** Added outside counsel's copyright finding to the basis citation.
- **Problem 4 (invented customer disclosure obligation):** Removed Permitted Uses item 4 entirely; replaced with a factually grounded item addressing the 80-seat cap and seat-request handling (also fixes Problem 9).
- **Problem 5 (Engineering leadership approving sales tools):** Changed approval authority to "department head and Legal" so the rule is coherent for all departments.
- **Problem 6 (cascading obligation with no terminal consequence):** Added a terminal consequence: if the department head fails to route within the additional business day, Legal opens an intake record automatically on day three.
- **Problem 7 (Slack administrator controls contradiction):** Removed the Slack administrator controls reference from Enforcement item 5; enforcement for Slack violations addresses only GitHub Copilot Business seat revocation.
- **Problem 8 ($50K budget unaddressed):** Added a budget-referencing item in Permitted Uses governing the tool approval process.
- **Problem 9 (80-seat cap unaddressed):** Addressed in the replacement for Permitted Uses item 4 (seat requests fulfilled in order of submission until seats are exhausted).
- **Problem 10 (Scope item 3 is prose justification):** Deleted.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Legal & Engineering | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI-powered tools—code assistants, writing assistants, and generative models—used by any employee on company devices or for company work.
2. Personal and free-tier AI tools used for company purposes are subject to this policy on the same terms as licensed tools.

---

## Permitted Uses

1. GitHub Copilot Business is the sole approved AI coding tool. Engineering leadership assigns the 80 licensed seats to named individuals through existing GitHub Copilot Business seat controls; seat requests are fulfilled in submission order until all 80 seats are allocated.
2. Copilot-seated engineers may use GitHub Copilot Business for code completion, boilerplate generation, and test writing.
3. All AI-generated code must receive human reviewer approval before merge.
4. Additional AI tools may be approved within the $50K annual AI tooling budget. Requests require written approval from the requesting employee's department head and Legal before any use begins.

---

## Prohibited Uses

1. **No customer data in external AI tools.** Inputting customer PII, financial data, or database schemas into any third-party AI service is prohibited. *[Basis: Incident 1—engineer pasted a customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms and creates GDPR liability.]*
2. **No AI-generated external content without manager approval.** AI-generated text for external distribution requires direct manager approval before sending. *[Basis: Incident 2—a sales rep distributed AI-generated text containing a competitor's copyrighted marketing copy verbatim; outside counsel flagged that AI-generated content carries copyright infringement risk.]*
3. **No commits with third-party license headers.** Reviewers must reject any pull request carrying an AI-generated third-party license header. *[Basis: Incident 3—an intern committed AI-generated code carrying a GPL license header originating from AI training data.]*
4. **No unapproved AI tools.** No employee may use any AI tool not approved under Permitted Uses item 4. *[Basis: 73% of engineers and 45% of sales staff already use informal tools with no data-handling controls, creating DPA, GDPR, and IP exposure.]*
5. **Slack AI features must remain disabled.** No employee may request or self-enable AI features within company Slack. *[Basis: Company handles customer PII and financial data subject to GDPR obligations; Slack AI features are currently disabled; enabling them would jeopardize the pending FedRAMP authorization.]*

---

## Enforcement

1. At each code review or output approval event, the assigned reviewer confirms that AI-generated content complies with this policy before approving.
2. Any violation involving customer data exposure, copyright infringement, or license header incidents must be routed to Legal via the existing Legal intake process within one business day of discovery by any manager or department head.
3. If the responsible manager does not complete that routing within one business day, the obligation transfers to the department head, who must complete routing within one additional business day. If the department head does not complete routing by that deadline, Legal opens an intake record on day three.
4. A confirmed violation is recorded in the employee's existing HR file and triggers a mandatory manager review within five business days.
5. Where a confirmed violation involves GitHub Copilot Business access, Engineering leadership revokes that access through existing GitHub Copilot Business seat controls.