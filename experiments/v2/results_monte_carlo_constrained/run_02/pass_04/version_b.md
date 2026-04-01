I'll address each problem in turn, then present the revised document.

**Changes made and problems fixed:**

1. **Word count / parenthetical citations:** Compressed motivating-fact citations to inline shorthand (e.g., "*(Incident 1; DPA terms; SOC2/GDPR)*") rather than full sentences. Tightened all item prose throughout. *Fixes: word count violation.*

2. **Scope items rewritten as enforceable rules:** Changed Scope items from definitional prose to binding applicability statements that function as rules (who is bound, what triggers the policy). *Fixes: Scope numbered items read as prose paragraphs.*

3. **Permitted Use #3 corrected:** Removed Sales from GitHub Copilot Business. Sales permitted use is limited to human-reviewed outbound drafting with no customer data, without specifying an approved tool (none is established in base facts for Sales). *Fixes: GitHub Copilot Business misassigned to Sales.*

4. **Prohibited Use #4 motivating-fact citation corrected:** Removed the unsupported claim that all three incidents involved unapproved tools. Citation now references only the two incidents where that is clear and the DPA terms finding. *Fixes: inaccurate motivating-fact claim for Prohibited Use #4.*

5. **Slack prohibition motivating fact corrected:** Removed the fabricated causal mechanism. Citation now references only the base facts: Slack AI features are currently disabled, and outside counsel's DPA finding. *Fixes: fabricated causal mechanism in Slack prohibition.*

6. **$50K budget incorporated:** Added a Permitted Uses item establishing that AI tool expenditures are governed by the allocated $50K/year budget, administered by the budget owner. *Fixes: $50K budget absent from document.*

7. **FedRAMP prohibition motivating fact corrected:** Removed the unsupported phrase about unconfirmed data handling requirements. Citation now states only that FedRAMP authorization is pending Q3. *Fixes: unsupported reasoning added to FedRAMP prohibition.*

8. **Enforcement item 3 revised to pre-send mechanism:** Changed Sales enforcement to require Sales Managers to confirm human review of AI-assisted content before sending, using existing pre-send approval step in deal workflows, rather than catching violations in post-hoc review meetings. *Fixes: enforcement item 3 was a post-hoc catch mechanism, not a pre-send control.*

9. **Enforcement item 5 split into discrete numbered items:** Separated license artifact review, FedRAMP workstream enforcement, and Slack administrative controls into individual numbered items. *Fixes: enforcement item 5 was a bundled run-on fragment.*

10. **Placeholders filled / acknowledgment mechanism added:** Added effective date instruction, named owner role (Chief Technology Officer), and added an Enforcement item requiring HR to distribute the policy and collect signed acknowledgments from all covered individuals before the effective date. *Fixes: unenforceable placeholders and missing acknowledgment mechanism.*

---

# AI Tool Usage Policy
**Effective Date:** [DATE — must be populated before distribution] | **Owner:** Chief Technology Officer | **Audience:** All Employees, Contractors, and Interns

---

## Scope

1. This policy binds all employees, contractors, and interns performing work on behalf of the company.
2. This policy governs all AI tools used for any work-related task, including code assistants, text generators, and chat interfaces.
3. Individuals who have not signed acknowledgment of this policy are not authorized to use any AI tool for work purposes.

---

## Permitted Uses

1. Engineers may use GitHub Copilot Business seats allocated by Engineering Leads via GitHub admin controls.
2. Engineers may use AI-assisted code generation only when the committing engineer reviews, understands, and accepts ownership of every line before commit.
3. Sales employees may use AI tools to draft outbound content using only non-confidential, non-customer data, with human review completed before sending.
4. AI tooling expenditures are limited to the $50K/year allocated budget, administered by the Chief Technology Officer.

---

## Prohibited Uses

1. **No customer or PII data in external AI tools.** Inputting customer data—including database schemas, records, or identifiers—into any third-party AI service is prohibited. *(Incident 1; outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
2. **No unverified AI-generated content in outbound communications.** Publishing or sending AI-generated text without confirming it contains no third-party copyrighted material is prohibited. *(Incident 2)*
3. **No AI-generated code committed without license review.** Committing AI-generated code containing open-source license artifacts is prohibited. *(Incident 3; outside counsel copyright finding)*
4. **No unapproved AI tools for work purposes.** Using any AI service other than GitHub Copilot Business is prohibited. *(Incidents 1 and 2 involved external third-party services; outside counsel DPA finding)*
5. **No enabling of Slack AI features.** Employees must not enable Slack AI features, which are currently disabled. *(Outside counsel DPA finding; SOC2 Type II and GDPR obligations)*
6. **No GitHub Copilot Business use on FedRAMP-scoped workstreams** until FedRAMP authorization is obtained. *(FedRAMP authorization pending Q3 target)*

---

## Enforcement

1. HR distributes this policy to all covered individuals and collects signed acknowledgments before the effective date; no covered individual may use AI tools for work purposes until acknowledgment is on file.
2. Engineering Leads verify compliance during existing pull request and code review workflows; violations are referred to HR for disciplinary action.
3. Violations involving customer data (Prohibited Use #1) are escalated immediately to Legal and treated as a potential data incident under the existing SOC2 incident response process.
4. Sales Managers confirm human review of AI-assisted outbound content as a required step in the existing pre-send deal approval workflow before content is transmitted; unconfirmed content is not approved to send.
5. GitHub admin controls enforce seat allocation and access revocation for all GitHub Copilot Business usage.
6. Engineering Leads flag license artifacts during code review (Prohibited Use #3) and escalate to Legal.
7. Engineering Leads enforce the FedRAMP workstream prohibition (Prohibited Use #6) by excluding GitHub Copilot Business from repositories scoped to FedRAMP workstreams via existing repository access controls.
8. IT enforces the Slack AI feature prohibition (Prohibited Use #5) via existing Slack administrative controls.