# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

**Definition:** "Customer data" means any PII, financial data, database schemas, or configuration files that identify or are derived from customer environments. This definition applies throughout this policy.

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables.
2. GitHub Copilot Business is the sole currently approved AI tool, with 80 seats allocated. A $50K annual budget is allocated for additional AI tooling; new tools require approval per Enforcement item 4 before any use.
3. Company Slack AI features are disabled and remain unavailable until a tool approval under Enforcement item 4 is completed.
4. Engineers without an assigned Copilot seat have no approved AI tool and no permitted AI use until a seat is assigned or a new tool is approved under Enforcement item 4.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) may be used by assigned engineers for code completion, test generation, and documentation on files that do not contain customer data.
2. Sales employees may use GitHub Copilot Business seats, if available within the 80-seat allocation, for drafting internal and customer-facing written communications that do not contain customer data, subject to the review requirements in Enforcement item 3.
3. All other employees may use GitHub Copilot Business seats, if available within the 80-seat allocation, for drafting work-related documents that do not contain customer data, subject to the review requirements in Enforcement item 3.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer data into any AI service — including approved tools — is prohibited. *(Motivating facts: Incident #1 schema exposure; SOC2 Type II certification requirements; GDPR obligations for EU customers.)*
2. **No customer data shared with third-party AI services specifically.** Inputting customer data into any third-party AI service is independently prohibited. *(Motivating fact: Outside counsel flag that inputting customer data into third-party AI services likely violates existing Data Processing Agreement terms.)*
3. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited. *(Motivating facts: Incident #2, in which an unapproved tool produced verbatim competitor copyrighted marketing copy in a sales communication; Incident #3, in which an unapproved tool produced GPL-licensed code committed to the codebase; 73% of engineers and 45% of sales staff confirmed using unapproved tools without controls.)*
4. **No AI-generated content submitted without IP review.** Employees must confirm before submission that AI-generated text contains no verbatim third-party copyrighted material and that AI-generated code contains no third-party license headers or GPL markers. Pull request reviewers must reject code submissions lacking that confirmation. *(Motivating facts: Incident #2 verbatim reproduction of a competitor's copyrighted marketing copy; Incident #3 GPL header committed to codebase; outside counsel flag that AI-generated code may not be copyrightable.)*
5. **No use of any AI tool that has not passed DPA review during FedRAMP authorization.** From the date of this policy through completion of FedRAMP authorization, no AI tool — including tools otherwise eligible for approval under Enforcement item 4 — may be approved or used unless Legal has confirmed in writing that its use does not conflict with existing Data Processing Agreement terms and does not jeopardize the pending FedRAMP authorization. *(Motivating facts: Outside counsel flag on DPA violations from third-party AI tool use; pending FedRAMP authorization with Q3 target imposing distinct data-handling and tool-vetting requirements.)*

---

## Enforcement

1. Violations of Prohibited Uses items 1–3 result in immediate disciplinary action, up to and including termination.
2. Violations of Prohibited Uses item 5 are escalated immediately to Legal and the CEO and result in suspension of the tool pending DPA and FedRAMP review, followed by disciplinary action up to and including termination.
3. All AI-generated content in external communications or committed code is subject to manager review before delivery or merge. This review uses existing pull request approval workflows for code and existing email approval chains for sales communications; no new tooling is required.
4. Requests to approve new AI tools are submitted to Legal and Security in writing. Legal confirms in writing that the tool's use does not violate existing DPA terms before any approval proceeds. Approved tools are added to Permitted Uses by written amendment signed by the CEO. No tool is used before that amendment is signed.

---

**Changes made and problems addressed:**

- **Problem 3:** Moved the "customer data" definition out of Permitted Uses item 1 into a standalone definition block at the top of the document, where it governs all sections.
- **Problem 1:** Split Permitted Uses into three items covering engineers, sales employees, and other employees, giving all three populations explicit permitted use statements and addressing the 45% of sales staff using AI for email drafting.
- **Problem 7:** Added Scope item 4 explicitly stating that engineers without an assigned Copilot seat have no permitted AI use.
- **Problem 6:** Renumbered the tool-approval process as Enforcement item 4 and updated all forward references to point to it; Scope items 2 and 3 now reference Enforcement item 4, which is a shorter forward jump and is consistently labeled throughout.
- **Problem 4:** Split the DPA concern out of Prohibited Uses item 1 into its own prohibition (item 2) covering third-party AI services, and added Prohibited Uses item 5 creating an explicit DPA-review gate on all tool approvals during FedRAMP authorization. Added a corresponding DPA-confirmation step to Enforcement item 4.
- **Problem 5:** Prohibited Uses item 5 gives FedRAMP authorization an explicit operational consequence — no tool approval proceeds without Legal's written FedRAMP and DPA clearance — rather than treating it only as a citation footnote.
- **Problem 2:** Separated the copyright/IP prohibition into its own item (Prohibited Uses item 4) with motivating facts that specifically call out the verbatim copyright reproduction risk and the copyrightability flag from outside counsel, distinct from the unapproved-tool prohibition in item 3.