You are writing a technical incident postmortem for a 4-hour outage of a payment processing API that affected 12,000 merchants. This will be published on the company's engineering blog.

Base facts (use ALL of these, add nothing that isn't derivable from them):
- Service: Payment processing API handling $2.3M/hour in transactions
- Outage window: 14:23 UTC to 18:41 UTC on a Tuesday
- Root cause: A database migration script dropped an index on the transactions table, causing query latency to spike from 12ms to 8,400ms
- Detection: PagerDuty alert fired at 14:31 (8 min after start) on p99 latency exceeding 500ms
- First response: On-call engineer attempted to scale up database replicas (did not help — wrong diagnosis)
- Actual fix: Senior engineer identified the missing index at 17:52 via EXPLAIN ANALYZE, rebuilt it, latency recovered by 18:41
- Impact: 12,000 merchants affected, ~$9.2M in failed transactions (most retried successfully within 2 hours of recovery), 847 support tickets
- Contributing factors: Migration script had no index verification step, staging environment had 1/1000th the data volume so the missing index wasn't noticeable
- Timeline gap: 3 hours between first response and correct diagnosis because the team initially assumed it was a traffic spike (Black Friday was 2 days away)

Constraints:
- Maximum 600 words
- Must follow this exact structure: Summary (2-3 sentences), Timeline (chronological, no editorializing), Root Cause, What Went Wrong, What We're Changing (specific, measurable actions with owners and deadlines)
- No hedging language ("we believe", "it appears", "possibly")
- Every remediation item must be falsifiable (someone could check in 30 days whether it happened)

Write the postmortem.