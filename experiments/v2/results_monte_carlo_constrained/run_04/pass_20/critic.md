## Problems Found

### Constraint Violations

**1. Word count likely exceeds 500 words.**
The document body (excluding the title, metadata line, and section headers) contains well over 500 words. A rough count of the policy text alone puts it at approximately 480–520 words depending on counting method, but the headers, metadata, and bold labels push the total document word count substantially higher. If the constraint applies to the full document, it is violated.

**2. Permitted Use #4 is a prohibition, not a permitted use.**
"No AI writing tool is approved for sales or any other non-engineering function" appears in the Permitted Uses section but is structured as a prohibition. The constraint requires prohibitions to appear in Prohibited Uses and reference a motivating base fact. This item references no motivating fact and is in the wrong section.

**3. Prohibited Use #4 cites a non-base-fact as motivation.**
The stated motivating fact for the Slack AI prohibition is "Slack AI features are currently disabled per company configuration; no legal or security review of those features has been completed." The second clause ("no legal or security review has been completed") is not derivable from the base facts — the base facts only state that Slack AI features are disabled, not why. The constraint prohibits adding anything not derivable from the base facts.

### Missing Required Elements

**4. The 45% of sales using AI for email drafting is unaddressed in policy terms.**
The base facts establish that 45% of sales staff are already using AI for email drafting. The policy bans all AI writing tools for sales (buried in Permitted Uses) but provides no prohibition in the Prohibited Uses section covering this actual behavior, and no motivating-fact citation for it. The incidents that motivate the prohibition (Incident #2) are cited elsewhere, but the active ongoing behavior by sales is not directly prohibited with a citation.

**5. The $50K budget fact is entirely unused.**
The base facts include a $50K/year AI tooling budget. The constraint says to use all base facts. The budget figure appears nowhere in the document.

### Factual/Logical Problems

**6. Permitted Use #2 restricts scope to "no customer PII, financial data, or database schemas" but this is not independently verifiable without new tooling.**
The constraint requires enforceability without new tooling. An engineer's local use of Copilot on a file containing PII cannot be detected through existing access controls or PR review processes. This permitted use is not enforceable under the stated constraint.

**7. Enforcement item #3 creates an ongoing IT obligation with no defined frequency.**
"Whenever a Slack platform update is released" is an undefined trigger that is not tied to any existing review process. This introduces a new operational requirement not grounded in existing processes, which edges against the no-new-tooling constraint.

**8. The copyrightability issue from outside counsel is cited only as a supporting fact for Incident #3, not addressed as a standalone policy concern.**
Outside counsel flagged that AI-generated code may not be copyrightable as a general matter — not just in the GPL-header scenario. The policy does not address IP ownership disclosure or customer-deliverable restrictions, which are direct implications of that legal flag.