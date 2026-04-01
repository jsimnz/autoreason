## Problems Found

### Constraint Violations

**1. Word count.**
The document exceeds 600 words. The body text (excluding the table formatting characters and header markup) runs approximately 620–640 words. This is a hard constraint violation.

**2. Hedging language is present.**
The constraint explicitly bans hedging language. The Summary contains "the majority of which retried successfully" — the base facts state "most retried successfully within 2 hours of recovery," so "most" is the factual claim. "Majority" is not the problem; the phrasing "effectively unavailable" is an editorialization/hedge. More clearly: the Summary says "rendering the payment processing API effectively unavailable" — "effectively" is a hedge. The API either was or wasn't unavailable; the postmortem should state which.

**3. Timeline contains editorializing.**
The constraint specifies "chronological, no editorializing." The entry at 15:10–17:45 reads: "Team continues pursuing traffic-based hypotheses; replicas, connection pool limits, and caching layers investigated." The phrase "traffic-based hypotheses" is editorial framing, not a neutral factual statement of what occurred. The base facts do not specify that caching layers were investigated — this is added detail not derivable from the base facts.

### Fabricated Detail Not Derivable from Base Facts

**4. Specific index name invented.**
The root cause section names `transactions.created_at` as the specific index column. The base facts state only that "a database migration script dropped an index on the transactions table." No column name is given. This violates the constraint "add nothing that isn't derivable from them."

**5. "Paginated merchant query" invented.**
The root cause describes the index as "used by every paginated merchant query." Pagination is not mentioned anywhere in the base facts. This is fabricated.

**6. Connection pool limits and caching layers investigated.**
The 15:10–17:45 timeline entry states the team investigated "connection pool limits, and caching layers." The base facts mention only that the on-call engineer scaled up database replicas as the wrong action. No other investigation steps are specified. These details are invented.

**7. Index rebuild timing.**
The timeline adds "17:55 — Index rebuild initiated" as a distinct event. The base facts state only that the senior engineer identified the missing index at 17:52 via EXPLAIN ANALYZE and rebuilt it, with latency recovered by 18:41. A separate 17:55 event is an invented granularity not present in the source material.

### Logical / Accuracy Issues

**8. "3 hours and 17 minutes" calculation is wrong.**
The document states the senior engineer intervened "3 hours and 17 minutes into the incident." The incident started at 14:23 and the senior engineer identified the issue at 17:52. That is 3 hours and 29 minutes, not 3 hours and 17 minutes.

**9. Outage duration stated incorrectly in Summary.**
The Summary says "4 hours and 18 minutes." From 14:23 to 18:41 is 4 hours and 18 minutes — this is arithmetically correct, but the document elsewhere calls it "a 4-hour outage" (per the original task framing). This is not a hard error, but the precision is self-introduced and should be consistent.

### Missing Required Elements

**10. No falsifiability problem per se, but Remediation Item 5 is borderline.**
The constraint requires every remediation item to be falsifiable (checkable in 30 days). Item 5 ("Run one tabletop exercise") has a December 15 deadline — outside 30 days from a November incident date — meaning it cannot be checked within 30 days. The constraint says "someone could check in 30 days whether it happened," and this item structurally fails that test.