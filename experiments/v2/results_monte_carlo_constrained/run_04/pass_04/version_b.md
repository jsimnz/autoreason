I'll address each problem systematically, then present the revised document.

**Changes made and which problems they fix:**

- **Removed Scope item 3's second sentence** ("Prior undocumented use does not constitute permission") — fixes *Scope item 3 redundancy/filler*.
- **Revised Scope item 3** to acknowledge Slack AI features are already disabled and specify IT controls that setting — fixes *Slack ambiguity* and *missing Slack coverage*.
- **Revised Permitted Uses item 4** to remove the invented approval workflow; replaced with a statement that additional tools may be funded from the $50K budget only after Legal and Engineering leadership approval, without fabricating a submission process — fixes *invented process not derivable from base facts*.
- **Removed Enforcement item 4** (quarterly performance review language) — fixes *aspirational/non-enforceable language* violation.
- **Revised Enforcement item addressing the 80-seat cap** to specify that requests exceeding 80 seats are denied by IT until a seat is reallocated by Engineering leadership — fixes *80-seat cap enforcement mechanism undefined*.
- **Corrected Prohibited Uses item 3's motivating fact citation** — removed the unsupported "copyright ownership risk" attribution to outside counsel; the copyright concern motivating that item is the incident itself and the verbatim reproduction risk — fixes *misstatement of outside counsel's flagged concern*.
- **Removed FedRAMP as a cited motivating fact** in Prohibited Uses item 2 — fixes *FedRAMP inference not directly derivable from base facts*.
- **Removed Enforcement item 6** (handbook restatement) — fixes *unnecessary filler*, and also reduces word count.
- All remaining cuts are trimming verbose phrasing to achieve the **500-word maximum** — fixes *word count violation*.

---

# AI Tool Usage Policy
**Effective Date:** [DATE] | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all use of AI-assisted tools by all 200 employees, including interns, for any work-related task.
2. This policy covers AI coding assistants, AI writing tools, AI chat interfaces, and AI features embedded in existing platforms.
3. This policy supersedes all informal practices. Slack AI features are currently disabled; IT controls that setting and must not enable it without Legal and Engineering leadership approval.

---

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI coding assistant. Use is limited to the 80 licensed seats, allocated by Engineering leadership. IT denies access requests that would exceed 80 seats until Engineering leadership reallocates an existing seat.
2. Engineers may use GitHub Copilot Business for code completion, test generation, and documentation drafting on files containing no customer PII, financial data, or database schemas.
3. All AI-generated code must be reviewed by a human engineer before commit. Reviewers must confirm output contains no third-party license headers before approving.
4. Additional AI tools may be funded from the $50K annual AI tooling budget only after explicit approval by Legal and Engineering leadership. No tool is used before that approval is granted.

---

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, or database schemas into any third-party AI tool is prohibited. *(Motivating facts: SOC2 Type II obligations; GDPR obligations for EU customers; outside counsel flagged that inputting customer data into third-party AI services likely violates existing DPA terms; Incident #1: engineer pasted customer database schema into ChatGPT.)*
2. **No unapproved AI tools.** Using any AI tool not approved under this policy is prohibited, including AI coding tools other than GitHub Copilot Business and any external AI writing tool. *(Motivating facts: 73% of engineers and 45% of sales using unapproved tools without authorization; outside counsel flagged DPA violations from unapproved third-party AI services.)*
3. **No unreviewed AI-generated content in external communications.** AI-generated text in emails or proposals must be reviewed and edited by the authoring employee before sending. *(Motivating facts: Incident #2: sales rep transmitted a competitor's copyrighted marketing copy verbatim in AI-generated text.)*
4. **No committing AI-generated code containing third-party license notices.** Commits must not contain AI-generated license headers or third-party license notices not intentionally authored. *(Motivating facts: Incident #3: intern committed a GPL license header sourced from AI training data; outside counsel flagged that AI-generated code may not be copyrightable.)*

---

## Enforcement

1. GitHub Copilot Business access is provisioned and revoked by IT through existing identity management.
2. Violations identified during code review trigger immediate access review by Engineering leadership.
3. Violations by non-engineering employees are escalated by HR to Legal upon identification.
4. All incidents must be reported to Legal and Security within 24 hours using the existing incident reporting channel. Incidents discovered without a prior report are treated as aggravating factors in disciplinary review.