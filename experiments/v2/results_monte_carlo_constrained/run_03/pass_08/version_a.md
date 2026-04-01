**TO:** All Employees, Contractors, and Interns
**FROM:** Office of the CEO
**DATE:** [Date]
**SUBJECT:** AI Tool Usage Policy — Effective Immediately

---

# AI Tool Usage Policy

## Scope

1. This policy applies to all employees, contractors, and interns across all functions, effective immediately upon issuance.
2. This policy governs any use of AI tools for work-related tasks, including coding, writing, data analysis, and customer communications.
3. This policy supersedes all prior informal AI tool usage, for which no official policy previously existed.

## Permitted Uses

1. **GitHub Copilot Business** is the sole approved AI tool; Engineering leadership manages allocation of the 80 licensed seats.
2. Seat holders may use GitHub Copilot for code suggestions, boilerplate generation, and test writing on tasks that do not involve customer data.
3. Use of any other AI tool for work-related tasks requires prior written approval from the CTO and Legal, documented before any use begins.

## Prohibited Uses

1. **No customer data in external AI services.** Inputting customer PII, financial data, database schemas, or any customer-identifiable information into any non-approved AI service is prohibited. *(Motivating facts: Incident 1 — engineer pasted a customer database schema into ChatGPT; outside counsel finding that this likely violates existing DPA terms; SOC2 Type II certification, GDPR obligations, and pending FedRAMP authorization.)*
2. **No AI-generated content in external communications without prior manager approval.** AI-generated text may not be transmitted to customers or prospects until the sender's manager has reviewed it for accuracy, originality, and legal compliance and has recorded that approval in the relevant email thread or CRM record. *(Motivating fact: Incident 2 — sales rep transmitted AI-generated text containing verbatim copyrighted competitor copy.)*
3. **No AI-generated code committed without license review.** Code produced by AI tools may not be committed without the pull request reviewer confirming in the pull request record that no third-party license headers or GPL-encumbered content are present. *(Motivating facts: Incident 3 — intern committed code containing a GPL license header from AI training data; outside counsel finding that AI-generated code may not be copyrightable.)*
4. **Slack AI features must remain disabled.** Enabling or circumventing the disabled AI features in company Slack is prohibited. *(Motivating facts: Company Slack is provisioned with AI features disabled; enabling those features would introduce an unapproved AI service with unassessed DPA, SOC2, GDPR, and FedRAMP compliance exposure.)*
5. **No unapproved AI tools on company systems.** Accessing or installing non-approved AI services via company devices, accounts, or networks is prohibited. *(Motivating facts: GitHub Copilot Business is the only approved tool; unapproved tools have not been assessed for DPA, SOC2, GDPR, or FedRAMP compliance.)*

## Enforcement

1. Violations involving customer data, copyright, or license exposure are escalated immediately to the Security and Legal teams for breach assessment.
2. Engineering leadership reverts any pull request merged without the required license confirmation and holds it pending completed review.
3. Managers whose direct reports transmit unapproved AI-generated external communications are required to log the incident in the CRM record and notify Legal within 24 hours.
4. First violations result in a written warning and mandatory manager review; repeated violations result in disciplinary action up to and including termination.
5. Engineering leadership revokes GitHub Copilot seat access for any seat holder found in violation of this policy.

---

**Changes made and problems each fixes:**

- **Scope item 3 rewritten** (fixes Problems 7 and 3): Removed the survey statistics (which did policy no work and slightly mischaracterized the base facts) and replaced with a factual statement that no official policy previously existed, avoiding the distortion of "superseding informal practice."
- **Scope item 4 deleted** (fixes Problems 2 and 3): The item restated compliance certifications as background and ended with the vague obligation "must remain consistent with these obligations," which is soft language the constraints prohibit. Removing it eliminates both the filler and the prohibited language.
- **Permitted Uses item 1, budget reference removed** (fixes Problem 8): The $50K figure carried no enforceable consequence; removing it leaves only the policy-relevant fact about seat count and allocation responsibility.
- **Prohibited Use 4 motivation strengthened** (fixes Problem 5): Added explicit compliance risks — unassessed DPA, SOC2, GDPR, and FedRAMP exposure — as the motivating facts, replacing the circular citation of current state alone.
- **Enforcement item 3 added** (fixes Problem 6): Provides a concrete, existing-process enforcement mechanism (CRM logging and Legal notification) for Prohibited Use 2 violations on the sales side.
- **Overall tightening throughout** (fixes Problem 1): Removing Scope item 4, the budget reference, and condensing parentheticals brings the document within the 500-word limit.
- **Permitted Uses item 3 retained as-is** (Problem 4 assessed and not changed): The CTO-and-Legal written approval requirement uses existing personnel and documentation channels — email and CRM records — rather than new tooling. The criticism conflates creating a new rule with requiring new infrastructure; the mechanism (written approval, documented in existing records) is available without new systems.