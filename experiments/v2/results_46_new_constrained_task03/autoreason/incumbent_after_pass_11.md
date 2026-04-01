I'll identify the strongest element per dimension, then present the synthesis.

**Dimension-by-dimension selections:**

- **Scope:** Identical in both. Keep as-is.
- **Permitted Use 1:** Version X is stronger — it adds the seat-assignment process (engineering managers assign from 80 licensed seats) and the explicit fallback path for engineers without a seat. Version Y omits this, leaving a gap about who gets seats and what unseat engineers do.
- **Permitted Use 2:** Version X is stronger — it explicitly names Prohibited Use 4 (not 5) as the item the request doesn't violate, which is internally consistent with X's numbering and the seat/request logic. Version Y's cross-reference to Prohibited Use 5 is correct for Y's numbering but otherwise equivalent. Synthesized version will use correct internal numbering.
- **Permitted Use 3 (sales):** Version X adds an explicit Permitted Use for sales AI-assisted drafting with manager approval. Version Y handles this only in the prohibition. X is stronger — it affirmatively permits the practice 45% of sales already uses, which is necessary for the policy to be operable rather than purely restrictive.
- **Prohibited Use — customer data:** Version Y's framing ("No customer data in third-party AI tools") is slightly broader and cleaner than X's, and applies company-wide rather than only to engineers. Keep Y's framing.
- **Prohibited Use — AI-assisted external communications:** Version X correctly scopes this to sales employees and their sales managers, which matches the enforcement mechanism (sales manager approval). Version Y broadens it to all employees and all direct managers, which is unenforceable for engineering contexts where no such review workflow exists. Keep X's scoped framing.
- **Prohibited Use — PR disclosure:** Both versions are substantively identical. Keep as-is.
- **Prohibited Use — IP assertion in contracts (Version Y's Prohibited Use 4):** Version X correctly removes this as not derivable from base facts. The base facts state outside counsel flagged copyrightability risk; they do not establish that the company has customer contracts containing IP assertions. Version X is correct. Omit.
- **Prohibited Use — unapproved tools:** Substantively identical. Keep as-is, with correct internal numbering.
- **Prohibited Use — Slack AI:** Version X is stronger. Version Y directs IT to "deny any such request without escalation to Legal," which contradicts the correct control: requests should be routed *through* Legal review before IT acts. Denying without Legal review removes the legitimate path for ever enabling Slack AI. Version X correctly routes requests through Permitted Use 2's Legal review process.
- **Enforcement item 1:** Identical. Keep.
- **Enforcement item 2:** Identical. Keep.
- **Enforcement item 3:** Version X is stronger. Version Y's quarterly attestation framing falsely implies managers can verify what they cannot verify. Version X replaces attestation with AI tool usage as a standing one-on-one agenda item, which creates a genuine ongoing disclosure channel grounded in an existing mechanism.

---

# AI Tool Usage Policy
**Effective Date:** Date of CEO signature below | **Owner:** Engineering & Legal | **Applies To:** All Employees

---

## Scope

1. This policy governs all AI tools—code assistants, text generators, and chat interfaces—used by all employees across all functions, on company or personal devices used for work.
2. All AI tool use not explicitly permitted in the Permitted Uses section below is prohibited.

---

## Permitted Uses

1. Engineers with an assigned GitHub Copilot Business seat may use it for code completion, generation, and review in approved repositories. Engineering managers assign seats from the 80 licensed. Engineers without an assigned seat must follow Permitted Use 2 to request a seat or an alternative tool; they have no other permitted AI tool path.
2. Any employee may submit an additional AI tool to Legal for DPA and IP review, including a cost estimate for funding from the $50K/year AI tooling budget. No additional tool is permitted until Legal issues written approval. Submitting a request under this item is not a violation of Prohibited Use 4.
3. Sales employees may use AI-assisted drafting for external email and communications, subject to direct sales manager written approval before transmission, under the terms of Prohibited Use 2.

---

## Prohibited Uses

1. **No customer data in third-party AI tools.** Inputting PII, financial data, or any customer-identifiable information into any AI service outside company-controlled systems is prohibited. *[Basis: Incident 1—engineer pasted customer database schema into ChatGPT; outside counsel confirmed this violates existing DPA terms; SOC2 Type II, GDPR, and pending FedRAMP authorization require data handling controls.]*

2. **No AI-assisted sales communications transmitted without manager approval.** Sales employees must not transmit AI-generated or AI-assisted text to customers, prospects, or partners without prior written approval from their direct sales manager. *[Basis: Incident 2—sales rep transmitted verbatim competitor copyrighted marketing copy generated by AI; outside counsel confirmed AI-generated content carries unresolved copyright risk.]*

3. **No AI-generated code merged without PR disclosure and license-identifier review.** Engineers must identify AI-generated code in the pull request description; reviewing managers confirm disclosure during code review. Any PR in which AI-generated code contains a license identifier (e.g., GPL, MIT, Apache) is held and referred to Legal before merge. *[Basis: Incident 3—intern committed AI-generated code containing a GPL license header, creating an inbound license obligation; separately, outside counsel confirmed AI-generated code may not be copyrightable, creating ownership risk in merged code.]*

4. **No unapproved AI tools.** Employees without an assigned GitHub Copilot Business seat, or whose function is not covered by a Legal-approved tool, may not use any AI tool for work purposes. Submitting a request under Permitted Use 2 is not a violation of this item. *[Basis: No tool other than GitHub Copilot Business has received Legal DPA and IP review; Incidents 1, 2, and 3 each resulted from use of unreviewed tools.]*

5. **No requests to enable Slack AI features outside the Legal review process.** Employees must not request Slack AI enablement from IT or Slack administrators. Any such request must be submitted through the Legal review process in Permitted Use 2; IT may not act on any Slack AI enablement request that has not received written Legal approval. *[Basis: Slack AI features are currently disabled; enabling them without DPA and IP review would route internal communications containing PII and financial data through an unreviewed third-party service, undermining controls required under SOC2 Type II, GDPR, and pending FedRAMP authorization.]*

---

## Enforcement

1. Any employee, manager, or reviewer who discovers a violation must file a SOC2 incident report the same business day via existing SOC2 incident reporting channels. Violations involving customer PII, financial data, or FedRAMP-relevant systems are additionally escalated to the CEO the same business day.
2. Confirmed violations follow the existing disciplinary process: documented warning, performance plan, or termination.
3. Managers include AI tool usage as a standing agenda item in existing one-on-one meetings with direct reports, providing a recurring channel for employees to disclose use and for managers to identify potential violations before they become incidents.

---

CEO Signature: ___________________________ Date: ___________________________