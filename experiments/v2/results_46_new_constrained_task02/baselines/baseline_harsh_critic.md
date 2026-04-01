# Payment API Outage — 2023-11-14, 14:23–18:41 UTC

**Severity:** SEV-1
**Duration:** 4 hours 18 minutes (14:23–18:41 UTC)
**Document owner:** [Engineering Manager name]
**Contributing authors:** [On-call lead], [Database Platform lead], [SRE lead]
**Review participants:** [Engineering Manager name], [On-call lead], [Database Platform lead], [SRE lead], [Observability lead], [Infrastructure lead], [Customer Success lead]
**Approved by:** [Engineering Manager name]
**Approval date:** [Date]
**Status:** Final — approved for distribution

> **Pre-distribution checklist:** Before this document is distributed externally or shared with merchants, every placeholder in square brackets must be replaced with a confirmed value. Placeholders requiring replacement: all named roles (document owner, contributing authors, review participants, approver), approval date, version 1.0 date, all ticket links, the number of migration reviewers in the Root Cause section, the shadow environment sample threshold in action item 2, and all absolute transaction counts and per-merchant breakdowns in the Scope of Impact section. The absolute transaction counts are being compiled by [Customer Success lead] and [Database Platform lead] from payment processor logs and must be complete before this document is released; they are required before merchant outreach begins per action item 7 and before regulatory notification is assessed per action item 8. Distribution before all placeholders are replaced and the Scope of Impact transaction counts are populated is not authorized. The approval holder is responsible for verifying that no placeholder remains and that the Scope of Impact section is fully populated before release. Target completion date for transaction counts: [Date].

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | 2023-11-15 | [On-call lead] | Initial draft |
| 0.2 | 2023-11-15 | [Database Platform lead] | Root cause and timeline detail added |
| 0.3 | 2023-11-16 | [Database Platform lead] | Rollback mechanism and constraint detail added; migration authoring and review process documented |
| 0.4 | 2023-11-17 | [On-call lead] | Timeline entries for escalation and runbook exhaustion verified against PagerDuty and Slack logs |
| 1.0 | [Date] | [Engineering Manager name] | Final review and approval |

---

## Summary

At 14:23 UTC on November 14, 2023, a manually authored database migration script executed in production and dropped the index on `transactions.created_at`. The drop was not an intentional part of the migration. It occurred as an implicit side effect of a `DROP CONSTRAINT` statement that removed a `NOT NULL` constraint on the `transactions.merchant_id` column. That constraint had been originally defined with an explicit `USING INDEX` clause referencing the `created_at` index by name, binding the index to the constraint's lifecycle. Dropping the constraint dropped the index with it. The script did not recreate the index. No automated step in the deployment pipeline verified index presence after the migration completed.

Every paginated query in the payment processing API depends on this index to satisfy the `ORDER BY created_at` clause present in all transaction listing endpoints. Without it, the database executed full sequential scans against the `transactions` table, which contained approximately 800 million rows at the time of the incident. These figures — approximately 800 million rows in production and approximately 800,000 rows in staging — are working estimates pending confirmation from the database team; the 1,000-to-1 ratio between them is derived from the same unconfirmed source and should be treated as an approximation until the database team provides confirmed counts. Sequential scans at production table size drove p99 query latency from the sustained pre-incident baseline of 12ms — measured as the 30-day rolling p99 immediately preceding the incident — to a sustained 8,400ms peak observed during the outage window, 700 times slower. At 8,400ms, upstream HTTP clients reached their timeout thresholds before receiving responses. The payment processing API — comprising all transaction listing, payment initiation, and payment status endpoints, which together constitute its full externally visible surface area — was fully unavailable from 14:23 to 18:41 UTC. No other endpoints existed within the payment processing API during the outage window; "fully unavailable" is accurate.

Twelve thousand merchants experienced failed transactions during the outage window. Affected gross merchandise volume (GMV — the total value of transactions attempted through the payment API during the outage window) totaled $9.2M, derived from payment processor records. This figure is a working estimate: the underlying transaction logs are the same source used to compile per-merchant transaction counts, which are still being reconciled as of the approval date. The GMV figure will be confirmed or revised when that reconciliation is complete. Approximately 78% of failed transactions were recovered by automatic client-side retry logic within two hours of service restoration; the remaining approximately 22% required manual merchant resubmission or were abandoned. These percentages are estimates derived from payment processor log analysis completed as of the approval date and are pending final reconciliation. Absolute transaction counts broken down by merchant are being compiled and will be populated in the Scope of Impact section before distribution, as required by the pre-distribution checklist above.

An incorrect initial diagnosis attributed the degradation to a pre–Black Friday traffic surge. This hypothesis persisted from 14:35 UTC, when the on-call engineer acknowledged the alert, until 17:52 UTC, when a senior engineer identified the missing index — a delay of 3 hours and 17 minutes after the alert was acknowledged, and 3 hours and 29 minutes after the migration executed. These two intervals measure different starting points and are both stated here to avoid ambiguity: 3 hours 17 minutes is the time from alert acknowledgment to root cause identification; 3 hours 29 minutes is the time from migration execution to root cause identification. The elevated request rate visible on the Datadog dashboard at 14:35 made the traffic surge hypothesis plausible; that elevation was caused by client-side retries against the failing API rather than genuine new demand, but no tooling available to the on-call engineer at the time distinguished these two causes. The on-call engineer followed the existing runbook correctly and exhausted every listed hypothesis before escalating. The delay was a predictable consequence of a runbook that contained no query diagnostic step and an alert payload that provided no database-layer signal. It was not a failure of individual judgment.

Index rebuild using `CREATE INDEX CONCURRENTLY` began at 17:55 UTC. The concurrent method was chosen to avoid acquiring a table lock, which would have blocked all writes to `transactions` for the duration of the rebuild. The alternative — reversing the `NOT NULL` constraint removal — was evaluated and rejected: re-validating all existing rows against the reinstated constraint was estimated to require substantially more time than the index rebuild based on observed row count and historical constraint validation rates. The index rebuild completed at 18:41 UTC, and p99 latency returned to the 12ms baseline at that time.

Six factors produced this outage and extended its duration: a migration toolchain with no post-execution index verification step; a migration authoring and review process that neither detected the implicit index drop nor required rollback documentation before execution; a staging environment too small to surface query performance defects at production scale; an incident response runbook with no mechanism to prompt database-layer diagnosis during a latency investigation; an alert payload that provided no database-layer signal and no schema-change context; and the absence of a pre–Black Friday change freeze policy, which allowed a schema migration to execute two days before the highest-traffic period of the year. All six are addressed in the action items section.

All non-payment API services — including merchant dashboards, reporting, account management, webhook delivery, and the partner API — remained fully operational throughout the outage, confirmed by independent Datadog monitoring of each service. The current production schema has been confirmed correct. The index on `transactions.created_at` is present, was rebuilt successfully, and carries no residual data integrity issues. The `NOT NULL` constraint removal that was the intended purpose of the migration is also confirmed present and correct.

---

## Timeline

All times UTC. Events are reconstructed from PagerDuty incident logs, Datadog alert history, Slack incident channel messages, and database query logs. All timestamps are confirmed against at least two independent sources unless noted as single-source.

| Time (UTC) | Event |
|---|---|
| 14:23 | Migration script executes in production via the standard deployment pipeline, triggered manually by [Database Platform lead]. The script issues `DROP CONSTRAINT merchant_id_not_null` on the `transactions` table. Because the constraint was originally defined with `USING INDEX created_at_idx`, PostgreSQL drops `created_at_idx` as part of the constraint removal. The index drop is not logged as a discrete event by the deployment pipeline. The migration completes and the pipeline reports success. No post-execution verification of index presence occurs. |
| 14:24 | Query latency begins rising on all transaction listing, payment initiation, and payment status endpoints. Datadog records p99 latency crossing 500ms within 60 seconds of migration completion. |
| 14:27 | p99 latency crosses 2,000ms. The first HTTP 504 timeout errors appear in application logs. |
| 14:31 | p99 latency reaches 8,400ms and stabilizes at that level for the duration of the outage. All three affected endpoint categories begin returning 504 errors on effectively every request. |
| 14:33 | Datadog fires a SEV-1 alert: "Payment API p99 latency > 5,000ms sustained 2 minutes." Alert payload contains: service name, p99 latency value, affected endpoint list, and a link to the Datadog dashboard. Alert payload does not contain: database query execution time, index usage statistics, active lock information, or recent schema change events. PagerDuty pages the on-call engineer. |
| 14:35 | On-call engineer ([On-call lead]) acknowledges the PagerDuty alert and opens the Datadog dashboard. Dashboard shows elevated request rate alongside elevated latency. On-call engineer forms initial hypothesis: pre–Black Friday traffic surge is overwhelming API capacity. This hypothesis is consistent with all signals visible on the dashboard at this time. The elevated request rate is in fact caused by client-side retry amplification against the failing API, but the dashboard does not distinguish retry traffic from new-request traffic. On-call engineer begins working through the latency runbook. |
| 14:41 | On-call engineer rules out upstream rate limiting (no 429 responses in logs). Runbook directs to next hypothesis. |
| 14:52 | On-call engineer rules out application-layer memory pressure (heap metrics normal). Runbook directs to next hypothesis. |
| 15:08 | On-call engineer rules out network throughput saturation (network I/O within normal bounds). Runbook directs to next hypothesis. |
| 15:24 | On-call engineer rules out external payment processor degradation (processor status page green; direct probe to processor API returns 200 within 180ms). Runbook directs to next hypothesis. |
| 15:47 | On-call engineer rules out application deployment artifact issue (no deployment had occurred in the 6 hours prior to the incident per the deployment log; the migration execution is not recorded as a deployment event and does not appear in the deployment log the runbook directs the engineer to check). Runbook directs to next hypothesis. |
| 16:15 | On-call engineer rules out CDN or load balancer misconfiguration (load balancer health checks passing; CDN pass-through confirmed). Runbook directs to next hypothesis. |
| 16:44 | On-call engineer rules out application configuration drift (configuration hashes match expected values). Runbook directs to next hypothesis. |
| 17:12 | On-call engineer rules out downstream cache failure (cache hit rate normal; cache latency normal). The runbook contains no further hypotheses. The runbook does not include a database query diagnostic step at any point. |
| 17:45 | On-call engineer, having exhausted all runbook hypotheses without identifying the cause, escalates to [Database Platform lead] and [SRE lead] per the SEV-1 escalation procedure. Time elapsed since alert acknowledgment: 3 hours 10 minutes. Time elapsed since migration execution: 3 hours 22 minutes. Escalation is made via PagerDuty secondary escalation and a direct Slack message in the incident channel. Context transferred at escalation: Datadog dashboard link, list of all hypotheses checked and ruled out, application log excerpt showing 504 errors, and a note that no deployment had occurred per the deployment log. |
| 17:52 | Senior engineer ([Database Platform lead]) joins the incident channel and runs `EXPLAIN ANALYZE` on the slowest active query identified in `pg_stat_activity`. Output shows a sequential scan on `transactions` with an estimated row count of approximately 800 million. Senior engineer immediately checks `pg_indexes` for `transactions.created_at`. The index is absent. Senior engineer identifies the missing index as the root cause. Time elapsed since alert acknowledgment: 3 hours 17 minutes. Time elapsed since migration execution: 3 hours 29 minutes. |
| 17:54 | [Database Platform lead] confirms the migration executed at 14:23 and identifies the `USING INDEX` clause as the mechanism by which the constraint drop removed the index. Root cause is confirmed and communicated in the incident channel. |
| 17:55 | [Database Platform lead] and [SRE lead] evaluate two recovery options. Option A: `CREATE INDEX CONCURRENTLY created_at_idx ON transactions (created_at)` — rebuilds the index without acquiring a table lock; estimated duration based on table size and observed I/O capacity: 40–50 minutes; no writes blocked during rebuild. Option B: Reverse the `DROP CONSTRAINT` by reissuing `ADD CONSTRAINT merchant_id_not_null NOT NULL` on `transactions.merchant_id` — requires PostgreSQL to re-validate the `NOT NULL` constraint against all existing rows before the constraint is accepted; estimated duration based on row count and historical constraint validation rates: substantially longer than Option A; all writes to `transactions` blocked for the duration. Option A is selected. `CREATE INDEX CONCURRENTLY` begins at 17:55. |
| 18:10 | Index rebuild is 35% complete per `pg_stat_progress_create_index`. API continues returning 504 errors; no partial recovery is possible until the index is fully built. |
| 18:31 | Index rebuild is 90% complete. |
| 18:41 | Index rebuild completes. PostgreSQL begins using the index immediately. p99 latency drops from 8,400ms to 12ms within 90 seconds. 504 error rate drops to zero. The payment processing API is fully operational. Outage duration: 4 hours 18 minutes. |
| 18:45 | [SRE lead] confirms via Datadog that all three endpoint categories are returning 200 responses with p99 latency at or below the 12ms baseline. Incident is marked resolved in PagerDuty. |
| 18:50 | [On-call lead] opens the incident retrospective document. Incident channel is preserved and locked for log retention. |

---

## Scope of Impact

**Affected services:** Transaction listing endpoints, payment initiation endpoints, and payment status endpoints. These three endpoint categories constitute the full externally visible surface area of the payment processing API. No other endpoints exist within the payment processing API. All three were fully unavailable from 14:23 to 18:41 UTC.

**Unaffected services:** Merchant dashboards, reporting, account management, webhook delivery, and the partner API remained fully operational throughout the outage. Confirmed by independent Datadog monitoring of each service for the full outage window.

**Affected merchants:** 12,000 merchants experienced at least one failed transaction during the outage window.

**Affected GMV:** $9.2M in gross merchandise volume was affected during the outage window, derived from payment processor records. This is a working estimate pending final reconciliation of transaction logs. See the transaction count note below.

**Transaction recovery:** Approximately 78% of failed transactions were recovered by automatic client-side retry logic within two hours of service restoration. Approximately 22% required manual merchant resubmission or were abandoned. These percentages are working estimates from payment processor log analysis as of the approval date, pending final reconciliation.

**Absolute transaction counts:** Per-merchant transaction counts and total absolute transaction counts are being compiled by [Customer Success lead] and [Database Platform lead] from payment processor logs. These counts are required before this document may be distributed. They will be populated in the table below before release. The GMV figure above is derived from the same log source and will be confirmed or revised when reconciliation is complete.

| Merchant | Transactions attempted | Transactions failed | Transactions recovered by retry | Transactions requiring manual action or abandoned |
|---|---|---|---|---|
| *To be populated before distribution* | | | | |
| **Total** | | | | |

---

## Root Cause

The root cause was the implicit deletion of the `created_at_idx` index on the `transactions` table, caused by a `DROP CONSTRAINT` statement in a manually authored migration script that executed in production at 14:23 UTC.

**The constraint-index binding.** The `NOT NULL` constraint on `transactions.merchant_id` — named `merchant_id_not_null` — was originally defined using the clause `USING INDEX created_at_idx`. In PostgreSQL, this syntax binds the named index to the constraint