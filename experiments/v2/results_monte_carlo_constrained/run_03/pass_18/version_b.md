I'll address each problem systematically before presenting the revised document.

**Changes made and problems fixed:**

1. **Word count violation** — Rewrote all sections for brevity. Eliminated redundant items, condensed enforcement entries, and removed duplicated GDPR language in Scope.

2. **Permitted Uses item 4 was a prohibition** — Removed it from Permitted Uses. The underlying obligation (copyright risk from AI-generated code) is now captured entirely in Prohibited Uses item 3 and Enforcement item 3.

3. **Prohibition embedded in Permitted Uses item 1** — Removed the Legal review clause from Permitted Uses. Unapproved tool use is addressed solely in Prohibited Uses item 4.

4. **No enforcement mechanism for the flagging obligation** — Removed the obligation entirely rather than invent an enforcement mechanism not derivable from base facts. The copyright risk is addressed through the PR review prohibition instead.

5. **Sales enforcement vague / no existing process referenced** — Enforcement item 2 now references manager sign-off as the existing review process, consistent with the PR review model. Enforcement item 5 references the manager as the reporting party, matching the existing management chain.

6. **Implied available seats / unspent budget** — Removed Permitted Uses item 3 entirely. Removed the claim that sales can request tools within budget. The policy states only what is approved now.

7. **Merge "blocked" assumes new tooling** — Replaced with "may not be approved by the PR reviewer," which uses the existing PR review process without asserting a technical gate.

8. **Scope item 3 redundant with Prohibited Uses item 1** — Removed GDPR restatement from Scope item 3. GDPR reference is retained only in Prohibited Uses item 1 where it motivates a prohibition.

9. **Permitted Uses items 1 and 5 redundant** — Merged into a single item in Permitted Uses. The prohibition on unapproved tools stands alone in Prohibited Uses.

---

**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

# AI Tool Usage Policy

## Scope

1. Applies to all employees, contractors, and interns across all functions, effective immediately.
2. Governs all use of AI tools for coding, writing, data analysis, and customer communications.
3. Covers all customer PII and financial data the company handles.

## Permitted Uses

1. **GitHub Copilot Business** (80 licensed seats, managed by Engineering leadership) is the only approved AI tool. No other AI tool is approved for any work task.
2. Seat holders may use GitHub Copilot for code suggestions, boilerplate generation, and test writing on internal and customer-facing work.
3. Sales, non-engineering, and unseated engineering staff have no approved AI tool for work tasks.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or customer-identifiable information into any AI service other than GitHub Copilot Business is prohibited. *(Incident 1; outside counsel DPA finding; SOC2 Type II certification; GDPR obligations for EU customers; pending FedRAMP authorization.)*
2. **No unreviewed AI-generated content in external communications.** AI-generated text may not be transmitted externally without manager sign-off confirming accuracy, originality, and legal compliance. *(Incident 2: sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code merged without license review.** A PR containing AI-generated code may not be approved by the PR reviewer unless the reviewer confirms in the PR record that no third-party license headers or GPL-encumbered content are present. *(Incident 3; outside counsel finding that AI-generated code may carry embedded license terms and may not be copyrightable.)*
4. **No unapproved AI tools.** Using any AI service other than GitHub Copilot Business for work tasks is prohibited. *(GitHub Copilot Business is the only tool assessed against DPA, SOC2, GDPR, and FedRAMP requirements.)*
5. **Slack AI features remain disabled.** Enabling or circumventing disabled Slack AI features is prohibited. *(SOC2 Type II certification; outside counsel DPA finding; company handles customer PII and financial data.)*

## Enforcement

1. Violations of Prohibited Use 1 are escalated immediately to Security and Legal for breach assessment; documented in the employee's HR file; subject to disciplinary action up to termination.
2. Violations of Prohibited Use 2 are reported by the employee's manager to Legal; documented in the employee's HR file; subject to disciplinary action up to termination.
3. Violations of Prohibited Use 3 are reported by Engineering leadership to Legal; the reviewing engineer is accountable; documented in the reviewer's HR file; subject to disciplinary action up to termination.
4. Violations of Prohibited Uses 4 and 5 are reported by the employee's manager to Security and Legal; documented in the employee's HR file; subject to disciplinary action up to termination.