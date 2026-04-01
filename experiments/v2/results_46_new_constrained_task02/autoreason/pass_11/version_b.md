I'll address each problem in order, then present the revised document.

**Changes made and which problems they fix:**

1. **"most" restored to retry claim** — fixes "No hedging language constraint violated" / "The Summary's retry claim is wrong."

2. **Timeline row "~14:31–17:52" replaced** with two discrete, non-editorial rows: one at 14:31 for the scaling action, one at 17:52 for the diagnosis — fixes "Timeline row editorializes" and removes the editorial characterization of team reasoning.

3. **"index rebuild begins" removed from 17:52 entry** — fixes "'Index rebuild begins' at 17:52 is not in the base facts."

4. **18:41 entry changed to "latency recovers"** rather than "returns to 12ms baseline" — fixes "18:41 entry states 'latency returns to 12ms baseline.'"

5. **Item 5 (slow query log alert enrichment) removed** — fixes "'What We're Changing' item 5 is not grounded in the base facts."

6. **Item 3 verification rewritten** to tie solely to the runbook merge (November 22 deadline), removing the December 22 drill — fixes "Verification language in Item 3 is partially non-falsifiable" and the inconsistent deadline.

7. **"was voluntary" removed** from What Went Wrong — fixes "'Voluntary' in What Went Wrong is editorializing."

8. **Root Cause and What Went Wrong tightened** to reduce overlap and cut word count — fixes "Root Cause and What Went Wrong substantially overlap" and contributes to fixing the word count violation.

9. **Verification criteria in all remediation items condensed** throughout — primary fix for the word count violation.

10. **Item 2 deadline changed to December 22** (giving three weeks from the December 1 refresh start for two successful executions) — fixes "Item 2's deadline inconsistency."

---

# Payment API Outage — Tuesday, 14:23–18:41 UTC

## Summary

A database migration script dropped a critical index on the `transactions` table, causing query latency to spike from 12ms to 8,400ms and transaction failures across the payment processing API for 4 hours and 18 minutes. 12,000 merchants experienced failed transactions totaling $9.2M; most retried successfully within 2 hours of recovery, and 847 support tickets were generated. Correct diagnosis did not occur until 3 hours after first response.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Outage begins; query latency elevated |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms; on-call engineer scales up database read replicas |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE`; identifies missing index |
| 18:41 | Latency recovers; index rebuild complete |

---

## Root Cause

The production migration script dropped an index on the `transactions` table without recreating it, replacing indexed lookups with full table scans and driving p99 query latency from 12ms to 8,400ms, causing upstream timeouts across the API.

---

## What Went Wrong

**The migration script had no index verification step.** No post-migration check confirmed required indexes existed after the script completed.

**Staging did not surface the problem.** The staging database holds 1/1,000th of production data volume, masking degradation that only became critical at production scale.

**The runbook contained no query-level diagnostic step.** The on-call engineer followed the existing runbook and scaled replicas without running query diagnostics, allowing the wrong hypothesis to persist for 3 hours.

**No escalation threshold existed for unresolved latency incidents.** No policy required senior engineer involvement within a defined timeframe.

---

## What We're Changing

**1. Mandatory post-migration index verification**
Owner: Database Platform team | Deadline: December 1
All migration scripts must include a post-execution step confirming required indexes exist; CI blocks merges on any migration missing this check. *Verified when a pull request omitting the check is rejected by CI, confirmed in the pipeline dashboard.*

**2. Production-scale shadow database for migration testing**
Owner: Infrastructure team | Deadline: December 22
Provision a shadow environment at no less than 50% of production data volume, refreshed weekly starting December 1, required as a gate for all schema migrations before production deploy. *Verified when the CI/CD pipeline shows a sample migration run against this environment at or above the 50% row threshold, and the weekly refresh job has executed successfully at least twice, confirmed by scheduler logs.*

**3. Query diagnostics step added to on-call runbook**
Owner: On-call lead (SRE team) | Deadline: November 22
The latency incident runbook must require `EXPLAIN ANALYZE` on the slowest active queries as a numbered step before any infrastructure scaling action. *Verified when the merged runbook pull request, approved by November 22, contains `EXPLAIN ANALYZE` as a numbered step preceding any scaling action.*

**4. Escalation threshold for unresolved latency incidents**
Owner: On-call lead (SRE team) | Deadline: November 22
Any p99 latency incident unresolved after 30 minutes triggers mandatory senior engineer escalation via PagerDuty. *Verified when the PagerDuty escalation policy shows the 30-minute rule and a test alert confirms escalation fires to the senior engineer tier at the 30-minute mark.*