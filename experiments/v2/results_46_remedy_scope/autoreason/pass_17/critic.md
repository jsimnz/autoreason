## Real Problems

### 1. The Document Is Partially Missing
The viral spike analysis ends mid-sentence: "The worst case is not the spike—". Section 2.1, 2.2, 3, 3.2, 7, and others are referenced repeatedly but never appear. This is not a minor omission — the starvation conditions, crash recovery mechanism, deduplication tradeoff, and the entire escalation chain are promised and absent. The document cannot be evaluated as a complete design.

---

### 2. The FCM Rate Limit Assumption Is Load-Bearing and Circular
The entire spike analysis, P1 protection claim, and architecture validity hinge on FCM sustaining 10,000/sec. The document simultaneously acknowledges this cannot be confirmed in advance, proposes a load test as the resolution, and then admits the load test produces "useful signal but not a production guarantee." The architecture is therefore never actually validated — it is conditionally valid pending a test that cannot confirm the condition. The 2,000/sec re-evaluation gate is defined, but the document does not account for the scenario where load testing returns a number between 2,000 and 10,000/sec, which is the most likely outcome and produces ambiguous guidance.

---

### 3. The Starvation "Prevention" Is Not Prevention
Section 3.2 is missing, but the executive summary explicitly states the token bucket "does not guarantee forward progress for P2/P3 under sustained P0/P1 saturation." This means the document is describing a priority queue system with starvation prevention as a named feature while simultaneously disclosing that the feature does not prevent starvation under the exact conditions (sustained high-priority load) that make starvation a problem. The framing as a "prevention" mechanism is misleading regardless of what Section 3.2 says.

---

### 4. The Orphaned Processing Set Entries Problem Is Unresolved
The executive summary acknowledges a documented gap: if the worker hosting the recovery goroutine crashes and the container is destroyed, processing set entries may be orphaned. The mitigation is a "cross-instance recovery sweep described in Section 2.1" — which does not exist in this document. This is not a theoretical edge case; container destruction during a spike or DB pressure event is exactly the failure mode the system should handle. The gap is disclosed but the resolution is absent.

---

### 5. The Traffic Response Matrix Contains an Unactionable Instruction
The 80M–225M/day band specifies "shard queue namespace by user ID range — 1 week of engineering." This is a week of unplanned engineering work prescribed as a same-incident response to a traffic event. There is no pre-staging, no partial implementation, and no fallback if that week of work is unavailable (e.g., team is on-call, other incidents are active). The matrix implies a response that cannot actually be executed in the time window where it would matter.

---

### 6. The 20–40 Minute P1 Delay Is Inconsistent With the Sensitivity Table
The executive summary states worst-case P1 delay is "20–40 minutes under a standard spike." The spike analysis table shows P1 delay of 15–25 minutes for all non-DB-outlasting scenarios. These ranges do not overlap. The document does not explain where 20–40 minutes comes from, which means one of the two figures is wrong and there is no way to determine which without the missing derivation steps.

---

### 7. The Named Human Requirement Has No Enforcement Mechanism
The document states three decisions require named humans before production and that placeholder text blocks the deployment checklist. The deployment checklist is not defined anywhere in this document. The mechanism for blocking deployment is not described. The 30-day re-confirmation process has no owner. The fallback chain is in Section 7, which is absent. The governance structure is described in terms of its outputs but none of its actual mechanics exist in the document.

---

### 8. The Month-1 Default Provisioning Creates a Cost Trap With No Exit Criteria
If the month-1 review is missed, the system defaults to provisioning for 100M/day. The document states "the incentive is to do the review" but provides no upper bound on how long this elevated provisioning persists, no process for confirming the review was done, and no criteria for stepping back down to lower provisioning after the review occurs. The default is open-ended.

---

### 9. The DAU/MAU Correlation Argument Omits Its Own Counterexample
The document argues that cross-scenarios (high DAU/MAU × low notification rate) are "omitted to avoid false precision" because they are less likely than correlated cases. But the notification rate is partly a product of system behavior and feature decisions, not purely a function of engagement. A high-engagement app with aggressive notification suppression or user opt-out rates could produce exactly this cross-scenario. Omitting it is a modeling choice that is not justified by the correlation argument given.

---

### 10. PostgreSQL Pool Exhaustion Arithmetic Is Referenced but Absent
The executive summary states the pool exhaustion risk is "quantified with arithmetic shown in full in Section 2.1." Section 2.1 does not exist in this document. The claim that the risk is quantified cannot be evaluated. Given that every worker fetches full payloads from PostgreSQL on dequeue, and the document describes coincident DB failures as a primary failure mode, this is a central gap.

---

### 11. The Conservative Fallback Mode Is Underspecified for Its Purpose
The fallback mode during FCM re-evaluation is defined as "P0 only, all other channels queued but not dispatched." The document does not specify what happens to the queued messages during the re-evaluation window, how large those queues are allowed to grow, what happens if the re-evaluation concludes the architecture requires major changes (messages are now weeks old), or whether users receive any indication their notifications are not being delivered. A two-week queue accumulation of undelivered notifications is not addressed.

---

### 12. The Document's Self-Referential Structure Obscures Missing Content
The executive summary is written as a summary of sections that do not exist. This structure makes the document appear more complete than it is — a reader scanning the summary sees quantified claims, specific mechanisms, and named fallbacks, all of which are presented as if they are elaborated elsewhere. They are not. The effect is that the document's actual coverage cannot be determined without exhaustively checking every cross-reference, which is a significant problem for a document intended to be used under incident conditions.