# Payment API Outage — November 14, 14:23–18:41 UTC

## Summary

A migration script dropped the index on `transactions.created_at`, spiking query latency 700× and taking the payment API offline for 4 hours 18 minutes. Twelve thousand merchants experienced failed transactions representing $9.2M in gross volume; most retried successfully within 2 hours of restoration.

Two independent failures produced the outage. The migration pipeline had no mechanism to detect a broken post-migration schema, so a dropped index reached production silently. When the alert fired, the on-call team misdiagnosed the cause as a traffic surge and spent 3 hours 17 minutes scaling infrastructure instead of examining queries — the primary reason a 5-minute fix took 4 hours to apply.

Every corrective action below targets one of those two failures.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | Migration script executes; `transactions.created_at` index dropped; query latency begins climbing |
| 14:31 | PagerDuty fires on p99 latency > 500ms — 8 minutes after onset |
| 14:35 | On-call engineer attributes degradation to pre–Black Friday traffic surge; traffic-based investigation begins |
| 14:50 | Read replicas scaled up; no improvement |
| 15:10–17:45 | Team pursues traffic hypotheses; replicas, connection pool limits, and caching layers investigated in sequence; no improvement at any step |
| 17:52 | Senior engineer runs `EXPLAIN ANALYZE` on a slow transaction query; missing index identified — 3 hours 21 minutes after first alert |
| 17:55 | Index rebuild initiated |
| 18:41 | p99 latency returns to 12ms baseline; all merchants restored |

---

## Root Cause

The migration script dropped the index on `transactions.created_at` without recreating it. That index underpins every paginated merchant query. Without it, full table scans replaced indexed lookups, driving p99 latency from 12ms to 8,400ms and cascading into upstream API timeouts. The deployment completed without error. No automated check confirmed the table was in a valid post-migration state.

Two compounding failures determined the duration.

**1. The pipeline allowed a broken schema to reach production silently.** No post-migration validation ran. A passing deployment was indistinguishable from a correct one.

**2. The on-call team spent 3 hours 17 minutes on the wrong hypothesis.** With Black Friday two days out, the team anchored on a traffic spike and never challenged the assumption. The runbook had no requirement to examine query behavior before taking infrastructure action.

Either failure corrected in isolation would have limited the blast radius. Together, they converted a dropped index into a 4-hour outage.

---

## What Went Wrong

**The migration pipeline had no schema validation step.**
The script exited successfully with the database in a degraded state. No post-migration check confirmed required indexes existed. A passing deployment was indistinguishable from a correct one.

**Staging could not surface the failure.**
The staging database holds 1/1,000th of production volume. The full table scan that caused catastrophic latency at production scale completed within acceptable thresholds on staging. The failure mode was structurally invisible below production data volumes. Staging passed; production collapsed.

**A wrong hypothesis held for 3 hours 17 minutes.**
The team anchored on a traffic spike and never challenged it. No one ran query-level diagnostics until a senior engineer intervened. The team scaled infrastructure three times while the actual cause went unexamined. The runbook had no requirement to analyze query behavior before taking infrastructure action — the omission that converted a 5-minute diagnosis into a 3-hour detour.

---

## What We're Changing

**1. Mandatory post-migration index verification**
Owner: Database Platform | Deadline: December 1

Every migration script must include a post-execution step that queries `pg_indexes` against a required-indexes manifest and fails the deployment if any listed index is absent. The CI pipeline blocks merges on scripts missing this check. A broken schema cannot reach production silently.

**2. Production-scale shadow database for migration testing**
Owner: Infrastructure | Deadline: December 15

Provision a continuously refreshed shadow environment at ≥10% of production data volume. All schema migrations must pass against the shadow database before production deploy. This directly gates the class of volume-dependent failures that staging cannot detect. Staging remains; it no longer stands alone as the pre-production gate for schema changes.

**3. Query diagnostics required before infrastructure action**
Owner: On-call Lead, SRE | Deadline: November 22 — *highest priority*

`EXPLAIN ANALYZE` on the five slowest active queries becomes step 2 in the latency runbook, mandatory before any infrastructure scaling action. This step was absent during this incident. Had it been present, the root cause was 5 minutes from the first alert. This is the highest-priority fix because it directly addresses the decision failure that extended a fast diagnosis into a 3-hour detour.

**4. Slow-query snapshot attached to latency alerts**
Owner: Observability | Deadline: December 1

PagerDuty alerts firing on p99 breaches above 1,000ms automatically attach the top 10 slow-query logs from `pg_stat_statements` at alert time. Engineers arrive at the incident with query evidence already in hand. This eliminates the first diagnostic step and removes the conditions that allowed a traffic hypothesis to go unchallenged for three hours.

**5. Database degradation tabletop exercise**
Owner: Engineering Manager | Deadline: December 15

Run one tabletop exercise with the full on-call rotation against a database degradation scenario. Success criterion: reach query-level diagnosis before any infrastructure scaling action. This targets the exact decision pattern that extended this outage by three hours. The exercise is not complete until the team demonstrates the corrected runbook under simulated pressure.

---

## What We're Not Changing

Two proposals surfaced during the post-mortem and were declined.

**Deployment freeze windows.** A freeze would not have prevented this outage. The migration ran during normal hours with normal review. The failure was in validation, not timing.

**Additional staging capacity.** More staging data improves confidence but does not reach the volume threshold required to surface this failure class. The shadow database at ≥10% of production volume is the correct fix. Investing further in an environment structurally incapable of reproducing the failure is not.