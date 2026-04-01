## Problems Found

### Constraint Violations

**1. Word count likely exceeds 500 words.**
The document body (excluding the header block) runs well over 500 words. The Enforcement section alone is dense, and the Prohibited Uses section with its parenthetical citations is lengthy. This is a hard constraint violation.

**2. "Every prohibition must reference which base fact motivates it" — Prohibition 4 fails this.**
The parenthetical for Prohibited Use 4 states "(GitHub Copilot Business is the only tool assessed against DPA, SOC2, GDPR, and FedRAMP requirements)" — this is a rationale statement, not a reference to a base fact. No specific base fact (incident, compliance requirement, legal finding, or budget item) is cited as the motivating fact. The other prohibitions cite specific incidents or specific findings; this one does not.

**3. Prohibited Use 5 parenthetical cites motivating facts inconsistently with the constraint.**
The constraint says every prohibition must reference "which base fact motivates it." The Slack prohibition cites SOC2 and DPA findings as motivation, but the actual base fact is simply that Slack AI features are currently disabled by company decision. The cited facts don't explain *why* re-enabling them is prohibited beyond circular reasoning — no incident, no legal finding specifically about Slack AI is provided in the base facts.

---

### Wrong Assumptions / Unsupported Claims

**4. Prohibited Use 1 asserts GitHub Copilot Business is exempt from the customer data prohibition.**
The base facts do not state that GitHub Copilot Business has been assessed and cleared for inputting customer PII or financial data. The DPA concern flagged by outside counsel applies to "third-party AI services" broadly. The document implicitly treats Copilot as safe for customer data, which is not derivable from the base facts.

**5. Permitted Use 3 invents a rule about "unseated engineering staff" having no approved tool.**
The base facts state 80 Copilot seats are licensed and 120 engineers exist — the 40-seat gap is real — but the base facts say nothing about what unseated engineers are permitted or prohibited from doing. This is an addition not derivable from the base facts, violating the "add nothing that isn't derivable from them" constraint.

**6. Enforcement items assign specific escalation paths (e.g., "manager reports to Legal") not grounded in base facts.**
The base facts describe no reporting hierarchy, HR documentation process, or disciplinary framework. These procedural details are invented, violating the constraint against adding information not derivable from base facts.

---

### Missing Required Elements

**7. No prohibition references the $50K budget fact.**
The base facts include a $50K/year AI tooling budget. The constraint requires using *all* base facts. This fact appears nowhere in the document.

**8. The 45% sales AI usage statistic is never used.**
The informal survey finding about sales is a base fact that goes entirely unaddressed, despite being directly relevant to the sales-related incident and permitted/prohibited uses for sales staff.