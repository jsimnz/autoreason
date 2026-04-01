# Payment API Outage — 2024-11-14 14:23–18:41 UTC

**Severity:** SEV-1
**Status:** Resolved
**Incident Commander:** \[Name withheld — internal distribution only\]
**Last Updated:** 2024-11-18

---

## Summary

A database migration script dropped a critical index on the `transactions` table, causing query latency to spike 700× and rendering the payment processing API effectively unavailable for 4 hours and 18 minutes. Twelve thousand merchants experienced transactions that either failed outright or completed with severely degraded latency; the distinction between failed and degraded is reported separately in the Metrics section. Total affected gross payment volume was $9.2M. Approximately 89% of that volume by dollar amount retried successfully within 2 hours of service restoration at 18:41 UTC; an estimated $1.0M in gross volume had no successful retry within that window. These two figures are estimates derived from the same dataset and are kept consistent with each other; if either is revised, both will be updated simultaneously.

The migration was not caught before reaching production for two reasons: the script contained no post-execution verification step to confirm required indexes remained intact, and the staging environment — holding roughly 1/1,000th of production data volume — completed the degraded queries in under 50ms, well below alert thresholds, providing no signal that the change was unsafe.

An incorrect initial diagnosis extended the outage significantly. The team pursued a traffic-surge hypothesis for 3 hours and 21 minutes after the initial alert before running query-level diagnostics. Once the root cause was identified, index rebuild and full recovery took 49 minutes. Had the correct diagnosis been reached at the time of the initial alert, total outage duration measured from that alert is estimated at approximately 52 minutes. Measured from incident onset, the estimated minimum is approximately 60 minutes, because the 8-minute pre-alert window is a floor that faster diagnosis cannot eliminate regardless of how quickly engineers respond. The basis for both figures is explained in the Metrics section.

---

## Timeline

| Time (UTC) | Event |
|:-----------|:------|
| 14:23 | Migration script executes in production; `transactions.created_at` index dropped; query latency begins climbing |
| 14:31 | PagerDuty alert fires on p99 latency exceeding 500ms (8 minutes after onset) |
| 14:35 | On-call engineer begins investigation; with Black Friday two days out, forms initial hypothesis of traffic surge — a reasonable starting point given context, not yet contradicted by evidence |
| 14:50 | On-call engineer scales up database read replicas; no latency improvement observed |
| 15:00 | Incident escalated to full on-call rotation; traffic-based hypothesis maintained |
| 15:10 | Team begins systematic investigation of connection pool limits and caching layer configuration |
| 15:55 | Connection pool limits adjusted; no latency improvement observed |
| 16:30 | Caching layer configuration reviewed and ruled out; team returns to replica scaling hypothesis |
| 17:10 | Second round of replica scaling attempted; no improvement; team begins reviewing recent deploys |
| 17:45 | Deploy history reviewed; migration script identified as a candidate but not yet confirmed as cause |
| 17:52 | Senior engineer runs `EXPLAIN (ANALYZE, BUFFERS)` on a slow transaction query; missing index confirmed as root cause |
| 17:55 | Index rebuild initiated |
| 18:41 | p99 latency returns to baseline (12ms); all merchants restored |

---

## Metrics

| Metric | Value | Notes |
|:-------|:------|:------|
| Incident onset | 14:23 UTC | Time of migration execution |
| First alert | 14:31 UTC | 8 minutes after onset |
| Time to correct diagnosis | 3 hours 21 minutes | 14:31 alert to 17:52 root cause confirmed; measured from alert because engineers cannot respond before the alert fires |
| Time to recovery after correct diagnosis | 49 minutes | 17:55 index rebuild initiated to 18:41 baseline restored |
| Total outage duration | 4 hours 18 minutes | 14:23 onset to 18:41 recovery |
| Estimated outage duration if correct diagnosis at alert time — measured from alert | ~52 minutes | Applies the observed 3-minute triage-to-rebuild interval (17:52 to 17:55) plus the observed 49-minute rebuild time, starting from the 14:31 alert; estimated recovery at ~15:23 |
| Estimated outage duration if correct diagnosis at alert time — measured from onset | ~60 minutes | Same estimate above, measured from the 14:23 onset; the 8-minute pre-alert window is a fixed floor that faster diagnosis cannot reduce, because engineers have no visibility into the incident before the alert fires |
| Merchants affected — failed transactions | \[pending — see Open Questions\] | Transactions returning a non-retryable error during the outage window; Data Engineering is pulling from transaction logs; status as of 2024-11-18: in progress, due November 22 |
| Merchants affected — degraded transactions | \[pending — see Open Questions\] | Transactions that completed with p99 latency exceeding 1,000ms; combined total across both categories is confirmed at 12,000 merchants; status as of 2024-11-18: in progress, due November 22 |
| Gross payment volume affected | $9.2M | Total volume across failed and degraded transactions |
| Volume successfully retried within 2 hours of restoration | ~$8.2M (~89%) | Within 2 hours of service restoration at 18:41 UTC; figure is an estimate derived from transaction retry logs |
| Estimated volume with no successful retry | ~$1.0M | Gross volume with no confirmed retry within the 2-hour post-restoration window; derived from the same dataset as the ~$8.2M retry figure and will be updated in concert with it — these two figures must sum to $9.2M |
| Peak p99 query latency | 8,400ms | vs. 12ms baseline |
| Latency increase | ~700× | |

---

## Root Cause

The production migration script executed a schema change that dropped the index on `transactions.created_at` without recreating it. This index is used by every paginated merchant query. Without it, full table scans replaced indexed lookups, driving p99 query latency from 12ms to 8,400ms and causing upstream timeouts across the API layer.

The migration ran without error. No automated check verified that required indexes were intact after execution. No human review process was in place that would have caught the missing recreate step before the script ran in production.

---

## What Went Wrong

**The migration script had no index verification step.**
No pre- or post-migration check confirmed that required indexes existed after the script completed. The script executed cleanly from the database engine's perspective, producing no errors or warnings that would have triggered an alert. No review checklist or approval gate required a reviewer to confirm that every dropped index was explicitly recreated before the migration ran in production.

**Staging did not surface the problem.**
The staging database holds approximately 1/1,000th of production data volume, verified as of 2024-11-14. A full table scan on staging completed in under 50ms, well below alert thresholds. The same scan on production took 8,400ms. The staging environment provided no signal that the migration was unsafe, and no query performance gate existed to compensate for the volume disparity.

**The wrong mental model held for 3 hours and 21 minutes.**
With Black Friday two days out, the team anchored on a traffic-surge hypothesis from the first minutes of the incident. This model was plausible at the outset but was not tested against query-level evidence as successive scaling actions failed to produce improvement. Replicas, connection pools, and caching were each attempted and ruled out without prompting a diagnostic pivot to query analysis. No one ran `EXPLAIN (ANALYZE, BUFFERS)` on a slow query until a senior engineer intervened at 17:52. The latency runbook's first diagnostic step directed engineers toward infrastructure scaling rather than query analysis, which reinforced the wrong hypothesis and delayed escalation to the Database Platform team.

**The on-call diagnostic practice did not include query-level analysis as a first-response step.**
The correct diagnostic tool was available throughout the incident and was not used until a senior engineer joined the investigation. The runbook did not direct its use early enough, query-plan analysis was not part of the on-call engineer's practiced first-response routine, and the SEV-1 escalation path did not require a database specialist to be paged until the team had already exhausted infrastructure hypotheses. All three are systemic gaps, not individual failures.

---

## Open Questions

| Question | Owner | Due |
|:---------|:------|:----|
| What is the split between merchants affected by failed transactions vs. degraded transactions? | Data Engineering | November 22, 2024 |
| Is the current `log_min_duration_statement` setting already capturing queries exceeding 1,000ms, or does Action Item 4 require a configuration change before implementation can begin? | Database Platform team | November 22, 2024 |

Both questions have hard dependencies: the merchant-split data feeds the final Metrics table, and the `log_min_duration_statement` answer determines whether Action Item 4's scope or deadline requires adjustment. Owners must report findings to the incident commander by November 22 regardless of whether the answer is complete or preliminary.

---

## Interim Controls

The following controls are in effect immediately and remain mandatory until the corresponding action items are complete. Each control carries an explicit expiry condition. The owner of the corresponding action item is responsible for sending written confirmation to the SRE team distribution list when that condition is met, at which point the control is retired.

**Until the production-scale shadow database (Action Item 2) is provisioned and accepting migrations:**
All schema migrations require manual sign-off from a Database Platform engineer before promotion to production.

**Until the revised runbook (Action Item 3) is published and confirmed distributed to the on-call rotation:**
On-call engineers must treat any latency spike that does not improve after a single scaling action as a potential query-execution issue. Before attempting any further infrastructure changes, run `EXPLAIN (ANALYZE, BUFFERS)` on the top-5 slowest active queries. If any query plan shows a sequential scan on a large table, escalate immediately to the Database Platform team. The Action Item 3 owner will send written confirmation to the SRE team distribution list when the revised runbook is live and distributed; that confirmation retires this control.

**Until the SEV-1 escalation path is updated (Action Item 6):**
Any SEV-1 involving database latency must page a Database Platform engineer at the time of full on-call rotation escalation, not as a subsequent step.

---

## What We're Changing

### Action Item 1a — Required-Indexes Manifest: Initial Creation

**Owner:** Database Platform team
**Deadline:** November 25, 2024
**Dependency:** Action Item 1b depends on this item completing on time.

Create a machine-readable manifest listing every required index on tables with more than 10M rows, including index name, table, column(s), and the owning team. Requires review and sign-off from two Database Platform team leads before the manifest is considered authoritative.

**Risk acknowledgment:** This deadline is 7 days from publication. It requires two team leads to review a manifest covering all large-table indexes, which is a meaningful scope of work in a short window. If sign-off is not complete by November 25, the interim control requiring manual Database Platform sign-off on all migrations remains in force, and the Action Item 1b deadline extends by the same number of days the slip represents. The Database Platform lead must notify the incident commander by November 22 if the November 25 deadline is at risk, so that the 1b deadline can be adjusted before it is missed rather than after.

---

### Action Item 1b — Required-Indexes Manifest: Automated CI Enforcement

**Owner:** Database Platform team
**Deadline:** December 1, 2024
**Dependency:** Requires Action Item 1a complete and signed off before implementation begins.

Integrate the manifest produced in Action Item 1a into the CI pipeline. Any migration script that drops or modifies an index listed in the manifest must fail the pipeline unless the script also contains an explicit recreate step for that index, and unless a Database Platform engineer has approved an exception in writing. The CI check must run against the manifest version that was signed off in 1a; any subsequent manifest updates require a new sign-off cycle before they take effect in CI.

---

### Action Item 2 — Production-Scale Shadow Database for Migration Testing

**Owner:** Infrastructure team
**Deadline:** December 15, 2024

Provision a shadow database environment containing a minimum of 80M rows on the `transactions` table, representing 10% of the current approximately 800M production rows. The 80M-row dataset must be produced by a stratified random sample that preserves the production distributions of merchant concentration and date clustering, because these distributions affect index selectivity and query planner behavior. A uniform random sample is not sufficient. The Infrastructure team lead must document the sampling method and confirm with the Database Platform team that the resulting query plans on the shadow environment are representative of production plans before the environment is approved for use. All schema migrations must execute successfully against this environment, with p99 query latency remaining below 100ms, before promotion to production is permitted.

---

### Action Item 3 — Latency Runbook Revision

**Owner:** On-Call Engineering lead
**Deadline:** November 22, 2024
**Status as of 2024-11-18:** In progress.

Revise the SEV-1 latency runbook so that `EXPLAIN (ANALYZE, BUFFERS)` on the top-5 slowest active queries is the first diagnostic step, executed before any infrastructure scaling action is attempted. The current runbook directs engineers toward infrastructure scaling first; this ordering is what allowed the wrong hypothesis to persist for 3 hours and 21 minutes. The revised runbook must also include the explicit escalation trigger from the interim control: any sequential scan on a large table found in query plans requires immediate escalation to the Database Platform team. When the revised runbook is published and confirmed distributed to the full on-call rotation, the On-Call Engineering lead sends written confirmation to the SRE distribution list, retiring the corresponding interim control.

---

### Action Item 4 — Slow Query Logging and Automated Plan Capture

**Owner:** Database Platform team
**Deadline:** December 1, 2024
**Dependency:** Requires resolution of the `log_min_duration_statement` open question by November 22. See Open Questions section.

Configure `log_min_duration_statement` to capture all queries exceeding 1,000ms. Attach `EXPLAIN (ANALYZE, BUFFERS)` output — not bare `EXPLAIN` — automatically to PagerDuty alerts when p99 latency exceeds 500ms. Bare `EXPLAIN` shows the planner's estimated execution plan; `EXPLAIN (ANALYZE, BUFFERS)` shows actual execution, actual row counts, and buffer usage, which are the figures that matter when planner estimates diverge from reality. That divergence is precisely the class of problem that caused this incident, so attaching estimated-only plans to alerts would provide misleading signal.

If the November 22 open-question resolution reveals that the current configuration is already sufficient, the Database Platform team lead must confirm to the incident commander that the December 1 deadline and scope remain unchanged. If the configuration requires changes that affect scope or timeline, the Database Platform team lead must notify the incident commander by November 22 with a revised proposal. This action item is not considered on track until that confirmation or revision is received.

---

### Action Item 5 — On-Call Training: Query Diagnostics as First Response

**Owner:** Engineering Manager, Platform
**Deadline:** November 29, 2024

Conduct a structured 90-minute session with the full on-call rotation covering: (1) when and how to run `EXPLAIN (ANALYZE, BUFFERS)` on a live production system, (2) how to read a query plan and identify sequential scans on large tables, and (3) the revised escalation criteria from Action Item 3. Attendance is mandatory for all engineers in the on-call rotation. The Engineering Manager confirms attendance and completion to the SRE distribution list by November 29.

---

### Action Item 6 — SEV-1 Escalation Path: Mandatory Database Specialist Inclusion

**Owner:** On-Call Engineering lead
**Deadline:** November 25, 2024

Update the SEV-1 escalation policy so that any SEV-1 involving database latency pages a Database Platform engineer at the moment the full on-call rotation is escalated, not as a subsequent step after infrastructure hypotheses are exhausted. The 3-hour-21-minute misdiagnosis in this incident persisted for 2 hours and 52 minutes after the full rotation was paged at 15:00, in part because no database specialist was required to be present. The updated policy must define "database latency SEV-1" explicitly — using the same 500ms p99 threshold that triggers the PagerDuty alert — so that the paging criterion is unambiguous. When the policy is updated and distributed, the On-Call Engineering lead sends written confirmation to the SRE distribution list, retiring the corresponding interim control.

---

## What We Are Not Changing

**We are not adding a mandatory deployment delay before schema migrations run in production.**

The argument for a mandatory