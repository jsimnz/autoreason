# AI Tool Usage Policy
**Effective Date:** Date of CEO Signature | **Owner:** Engineering & Legal | **Applies To:** All Employees

**Definition:** "Customer data" means any PII, financial data, database schemas, or configuration files that identify or are derived from customer environments. This definition applies throughout this policy.

---

## Scope

1. This policy governs all use of AI tools — including code assistants, writing tools, and generative AI services — by all 200 employees on company systems or when handling company data or deliverables.
2. GitHub Copilot Business is the sole currently approved AI tool, with 80 seats allocated. A $50K annual budget is allocated for additional AI tooling; new tools require approval per Enforcement item 4 before any use.
3. Company Slack AI features are disabled and remain unavailable until a tool approval under Enforcement item 4 is completed.
4. Employees without an assigned Copilot seat have no approved AI tool and no permitted AI use until a seat is assigned or a new tool is approved under Enforcement item 4.

---

## Permitted Uses

1. GitHub Copilot Business (80 licensed seats) may be used by assigned engineers for code completion, test generation, and documentation on files that do not contain customer data.
2. Sales employees may use GitHub Copilot Business seats, if available within the 80-seat allocation, for drafting internal and customer-facing written communications that do not contain customer data, subject to the review requirements in Enforcement item 3.
3. All other employees may use GitHub Copilot Business seats, if available within the 80-seat allocation, for drafting work-related documents that do not contain customer data, subject to the review requirements in Enforcement item 3.

---

## Prohibited Uses

1. **No customer data in any AI tool.** Inputting customer data into any AI service — including approved tools — is prohibited. *(Motivating facts: Incident #1 schema exposure; SOC2 Type II certification requirements; GDPR obligations for EU customers; outside counsel flag that inputting customer data into third-party AI services likely violates existing DPA terms.)*
2. **No unapproved AI tools.** Using any AI tool not listed in Permitted Uses for any work-related task is prohibited. *(Motivating facts: Incident #2, in which an unapproved tool produced verbatim competitor copyrighted marketing copy in a sales communication; Incident #3, in which an unapproved tool produced GPL-licensed code committed to the codebase; 73% of engineers and 45% of sales staff confirmed using unapproved tools without controls.)*
3. **No AI-generated content submitted without IP review.** Employees must confirm before submission that AI-generated text contains no verbatim third-party copyrighted material and that AI-generated code contains no third-party license headers or GPL markers. Pull request reviewers must reject code submissions lacking that confirmation. *(Motivating facts: Incident #2 verbatim reproduction of a competitor's copyrighted marketing copy; Incident #3 GPL header committed to codebase; outside counsel flag that AI-generated code may not be copyrightable.)*
4. **No AI tool approved or used without DPA and FedRAMP clearance.** From the date of this policy through completion of FedRAMP authorization, no AI tool — including tools otherwise eligible under Enforcement item 4 — may be approved or used unless Legal has confirmed in writing that its use does not violate existing DPA terms and does not jeopardize the pending FedRAMP authorization. *(Motivating facts: Outside counsel flag on DPA violations from third-party AI tool use; pending FedRAMP authorization with Q3 target imposing distinct data-handling and tool-vetting requirements.)*

---

## Enforcement

1. Violations of Prohibited Uses items 1–2 result in immediate disciplinary action, up to and including termination.
2. Violations of Prohibited Uses item 3 require mandatory remediation — affected code is reverted or withheld — followed by disciplinary review. Pull request reviewers who approve merges lacking the required IP confirmation share accountability and are subject to the same disciplinary review as the submitting employee. Repeated violations result in escalating discipline up to and including termination.
3. Violations of Prohibited Uses item 4 are escalated immediately to Legal and the CEO, result in suspension of the tool pending written DPA and FedRAMP clearance, and are followed by disciplinary action up to and including termination.
4. All AI-generated content in external communications or committed code is subject to manager review before delivery or merge, using existing pull request approval workflows for code and existing email approval chains for sales communications. No new tooling is required.
5. Requests to approve new AI tools are submitted to Legal and Security in writing. Legal confirms in writing that the tool does not violate existing DPA terms and does not jeopardize FedRAMP authorization before any approval proceeds. Approved tools are added to Permitted Uses by written amendment signed by the CEO. No tool is used before that amendment is signed.