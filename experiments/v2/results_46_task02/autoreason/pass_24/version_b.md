# Notification System Design
## Social App — 10M MAU, 4 Engineers, 6 Months
### Revision 3

---

## Revision Notes

This revision addresses ten structural problems identified in the review of Revision 2. Each problem is listed with the resolution applied.

| Problem | Resolution |
|---------|------------|
| NSTL role is structurally unsustainable as a collateral engineering duty | NSTL responsibilities are scoped and time-budgeted. Section 5 engineering budget is adjusted to reflect the overhead. The role is redefined as coordination duties, not project management. |
| Gate 0 cannot actually block Gates 1–4 given the two-week window | Gate 0 deadline moved to end of Week 1, Month 1. Gate 1/2/4 deadlines remain at end of Week 4, giving owners three weeks to act. Slip analysis extended to cover the Gate 0 → Gates 1/2/4 chain. |
| Conflict-of-interest rule covers only formal ownership, not informal interest | Rule extended to cover the NSTL's architectural preferences. Disclosure mechanism added. |
| Gate 4 two-owner requirement creates an unaddressed deadlock scenario | Explicit partial-resolution rules added: one signature with the other silent defaults to A; one signature with the other actively dissenting escalates immediately. |
| Runbook repository is referenced but never defined | Repository specification added: location, access controls, posting rights, and onboarding instructions for non-engineering owners. |
| R=3 sensitivity range is derived from the same unvalidated model it is meant to bound | Acknowledged explicitly. The provisioned upper bound (9%) is now described as a model-internal bound only, not a true risk bound. A model-external stress test is added. |
| Flag table shows sustained averages but thresholds are defined in peak demand terms | Table revised to show both sustained average and implied peak. Flag assignments now reflect peak demand directly. |
| Engineering manager is both Gate 0 owner and escalation target | Escalation chain extended: VP Engineering (or equivalent) is the target when the engineering manager is the unresponsive party. |
| Four-week slip arithmetic is asserted, not derived | Arithmetic shown explicitly, matching the format of the two-week scenario. |
| Gate 5 miss creates undefined spend during launch period | Configuration C launch-period spend range quantified using nudge conversion bounds. Spend cap set at the upper bound of that range, not at Configuration B equivalence. |

---

## 0. Gate System

### 0.1 What Gates Are

Gates are decisions that block specific work items. A gate is not resolved until a named individual posts written acknowledgment to the runbook repository (defined in Section 0.6), referencing this document by version number, with a timestamp. Verbal commitments, Slack messages, and meeting notes do not resolve gates.

### 0.2 Enforcement: Honest Account

The actual enforcement mechanism is a named human role: the **Notification System Technical Lead (NSTL)**. This is one of the four backend engineers. Project trackers record state; they do not enforce it. The NSTL enforces it.

**Scoped NSTL responsibilities — what this role actually requires:**

| Responsibility | Estimated weekly time cost |
|----------------|---------------------------|
| Monday gate status check and tracker update | 30 minutes |
| Reviewing runbook entries for completeness | 15 minutes per entry, estimated 1–2 entries per week during active gate period |
| Escalating unresponsive gate owners (when required) | 1 hour per escalation, estimated 0–1 per week |
| Schedule recalculation on a slip (when required) | 2–3 hours per slip event, not a recurring cost |
| Conflict-of-interest disclosure review | 15 minutes per disclosure |

**Total recurring overhead during active gate period (Months 1–2):** approximately 1–2 hours per week. This is a coordination duty, not a project management role. The NSTL is not responsible for tracking non-gate work, managing stakeholder relationships, or producing status reports beyond the gate register.

**Section 5 adjustment:** The engineering budget in Section 5 accounts for 1.5 hours per week of NSTL overhead across Months 1 and 2 (12 hours total), applied against the NSTL's individual capacity. This is a real reduction in that engineer's coding capacity during that period and is not hidden.

**The NSTL is responsible for:**

- Verifying gate status each Monday morning and updating the tracker
- Rejecting informal resolutions and requiring written runbook entries
- Escalating to the engineering manager if a gate owner is unresponsive within 48 hours of a deadline
- Escalating to the VP Engineering if the engineering manager is the unresponsive party (see Section 0.4, Gate 0)
- Recalculating the project schedule when a gate slips and presenting the updated schedule to the full team within two business days of the slip

**Conflict-of-interest handling — extended:**

Gate owners are product, analytics, or security roles, not engineering. If the NSTL is formally assigned ownership of a gate item, a second engineer assumes enforcement responsibility for that gate only.

Formal ownership is not the only conflict vector. The NSTL may have a strong architectural preference that depends on a specific gate outcome — for example, preferring a messaging-primary architecture that depends on Gate 2 resolving as messaging-primary. This is a conflict even without formal ownership.

**Disclosure requirement:** Before Gate 2 (and any other gate where the NSTL has a stated architectural preference), the NSTL must post a one-paragraph disclosure to the runbook repository identifying the preference and the gate outcome it favors. A second engineer reviews gate enforcement actions for that gate. The disclosure does not disqualify the NSTL from enforcement duties; it makes the potential bias visible to the full team. If the second engineer believes the NSTL's enforcement actions are being influenced by the preference, they escalate to the engineering manager.

**The limit of this mechanism:** If the NSTL is pressured to accept informal resolutions, or if a disclosure is omitted, the system can fail. The mitigation is that enforcement actions and disclosures are visible to the full team in the tracker and runbook repository. This is not a perfect mechanism. It is an honest one.

### 0.3 Named Individuals Table

**The gate system is inert until this table is complete.** Gate 0 requires this table to be filled before any other gate can open.

| Role | Name | Email | Confirmed by (NSTL signature) | Date Confirmed |
|------|------|-------|-------------------------------|----------------|
| Notification System Technical Lead (NSTL) | [FILL BEFORE ACTIVE] | | | |
| Product Owner (Gates 1, 2, 4) | [FILL BEFORE ACTIVE] | | | |
| Analytics Owner (Gate 3) | [FILL BEFORE ACTIVE] | | | |
| Security Lead (Gates 4, 5) | [FILL BEFORE ACTIVE] | | | |
| Engineering Manager (escalation target for Gates 1–5) | [FILL BEFORE ACTIVE] | | | |
| VP Engineering (escalation target if Engineering Manager is unresponsive) | [FILL BEFORE ACTIVE] | | | |

**Instructions:** The engineering manager fills in the NSTL row. The NSTL fills in all other rows after confirming each person's acceptance of their role. No gate beyond Gate 0 has a valid owner until the corresponding row is signed and dated.

---

### 0.4 Gate Register

#### Gate 0 — Owner Assignment (Meta-Gate)

| Field | Value |
|-------|-------|
| Decision | Named individuals table (Section 0.3) is complete and confirmed |
| Owner Role | Engineering Manager |
| Hard Deadline | **End of Week 1, Month 1** |
| Dependent Work | All other gates. Gates 1–5 have no valid owner until Gate 0 resolves. |
| Consequence if Missed | All gates 1–4 are treated as unresolved as of their own deadlines. Schedule is recalculated immediately. |

**Why the deadline is Week 1, not Week 2:** Gates 1, 2, and 4 have deadlines at end of Week 4, Month 1. Gate 0 must resolve with enough lead time for owners to do substantive work before their own deadlines. Week 1 resolution gives owners three weeks. Week 2 resolution gives owners two weeks, which is marginal. Week 3 resolution makes Gate 1/2/4 deadlines functionally unreachable for any owner who needs more than one week to prepare a position. Week 1 is the right deadline.

**Escalation chain for Gate 0:** If the engineering manager has not completed the named individuals table by end of Week 1, the NSTL escalates to the VP Engineering (or equivalent organizational superior). This is the one gate where the normal escalation target is the owner, requiring a different escalation path. The VP Engineering row in Section 0.3 exists specifically for this scenario.

---

#### Gate 1 — Email Opt-In Posture

| Field | Value |
|-------|-------|
| Decision | Default-on vs. default-off for marketing email |
| Owner Role | Product Owner |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | Email worker sizing; provider contract; IP warm-up schedule |
| Consequence if Missed | Email channel deferred to post-launch v1.1. Push, in-app, and SMS launch without email. Email is the channel least likely to affect core retention in the first 90 days post-launch. The deferral is logged as a known gap. |

---

#### Gate 2 — App Orientation

| Field | Value |
|-------|-------|
| Decision | Messaging-primary vs. content-discovery |
| Owner Role | Product Owner |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | Notifications-per-user figure lock; all worker sizing dependent on that figure; Gate 3 deadline |
| Consequence if Missed | System is provisioned for the messaging-primary upper bound (25/day). The product owner receives a written statement that the over-provisioning cost is a direct consequence of the unresolved decision. The cost differential is calculated in Section 1.3b and presented at escalation. This is not a safe default — it is an expensive one, made visible. |

**Why 25/day and not 20/day:** The 20/day scenario at 30% DAU/MAU produces a sustained average of ~694/sec, which implies a peak of ~4,164/sec. This falls in the ⚠ band (see Section 1.2), meaning the fallback itself would trigger a re-sizing review. A fallback that generates a downstream review is not a fallback. The 25/day scenario at 30% DAU/MAU produces a peak of ~5,208/sec, which is at the provisioned floor. It is expensive but stable. The cost of stability is documented; the cost of a self-triggering fallback is not recoverable.

---

#### Gate 3 — Session Time Data

| Field | Value |
|-------|-------|
| Decision | Average session minutes per DAU per day |
| Owner Role | Analytics Owner |
| Hard Deadline | End of Week 2, Month 2 (two weeks after Gate 2 deadline; shifts by the same duration if Gate 2 slips) |
| Dependent Work | In-app worker sizing (final); in-app fraction lock |
| Consequence if Missed | In-app workers sized for the upper bound of the model-internal sensitivity range (9%) plus the external stress-test buffer described in Section 1.3a. |

---

#### Gate 4 — SMS 2FA Configuration

| Field | Value |
|-------|-------|
| Decision | Configuration A (SMS-only), B (SMS + authenticator app, SMS default), or C (SMS + authenticator app, authenticator default with nudge) |
| Owner Role | Product Owner + Security Lead (both must sign) |
| Hard Deadline | End of Week 4, Month 1 |
| Dependent Work | SMS spend cap; SMS worker sizing; authenticator app integration (if C) |

**Two-owner requirement — partial resolution rules:**

The two-owner requirement creates a potential deadlock. The following rules govern all partial-resolution scenarios:

| Scenario | Resolution |
|----------|------------|
| Both owners sign the same configuration | Gate resolves normally |
| One owner signs; the other is silent past the deadline | Default to Configuration A. The silent owner's manager is notified. The NSTL documents which owner was silent. |
| One owner signs Configuration X; the other signs Configuration Y | Immediate escalation to engineering manager. Engineering manager has 48 hours to impose a resolution. If no resolution in 48 hours, default to Configuration A and document both positions. |
| One owner signs; the other explicitly dissents in writing | Treat as a conflict between two signed positions. Immediate escalation to engineering manager. Same 48-hour rule applies. |

**Why Configuration A is the default, not B or C:** Configuration A is the simplest implementation and the most predictable spend. It is not the preferred security outcome — Configuration C is — but it is the outcome that unblocks the engineering team with the least ambiguity. The cost of choosing A when C was intended is documented and reversible post-launch. The cost of an unresolved two-owner deadlock is an indefinitely blocked SMS implementation.

**Consequence if Gate 4 misses deadline entirely (both owners silent):** Default to Configuration A. Both owners' managers are notified. Cost documented as in Gate 2.

---

#### Gate 5 — SMS 2FA Nudge Timeline (Configuration C only)

| Field | Value |
|-------|-------|
| Decision | Timeline and messaging for nudging users from SMS to authenticator app |
| Owner Role | Security Lead |
| Hard Deadline | End of Week 2, Month 2 |
| Dependent Work | Configuration C launch-period spend cap; nudge implementation |
| Condition | Required only if Gate 4 resolves as Configuration C |

**Consequence if Gate 5 is missed — quantified:**

If Gate 5 is missed, the nudge timeline is undefined. This means the duration of the Configuration C launch period — during which users remain on SMS before converting to authenticator — is unknown. The spend cap cannot be set at Configuration B equivalence, because Configuration C with an undefined nudge timeline is not equivalent to B.

The spend range during an undefined nudge period is bounded as follows:

- **Lower bound:** All users convert to authenticator on day one of the nudge. SMS spend equals Configuration B spend (nudge has no SMS cost). This is unrealistic.
- **Upper bound:** No users convert during the launch period (0% conversion). SMS spend equals Configuration A spend for the full launch period.
- **Realistic range:** Nudge conversion rates in analogous 2FA migrations (Authy, Google Workspace) run 15–40% within 30 days of first nudge. At 30% conversion over 30 days with a linear adoption curve, average daily SMS volume during the nudge period is approximately 70% of Configuration A volume.

**Spend cap if Gate 5 is missed:** Set at the upper bound — Configuration A spend for the full launch period. This is conservative and will likely over-provision. The over-provisioning cost is documented and presented to the Security Lead as a consequence of the unresolved decision. The spend cap is adjusted downward once Gate 5 resolves.

**Why not treat it as Configuration B:** Configuration B has no nudge period and no conversion uncertainty. Setting Configuration C's spend cap at B equivalence would underestimate spend by up to 40% during the nudge period. "Known underestimate" is not an acceptable spend cap posture for SMS, where costs are hardest to control at launch.

---

### 0.5 Slip Analysis

#### Gate 0 → Gates 1/2/4 Chain

Gate 0 must resolve by end of Week 1. Gates 1, 2, and 4 must resolve by end of Week 4. This gives owners three weeks to prepare positions after Gate 0 resolves on time.

| Gate 0 resolution | Owner preparation window | Gates 1/2/4 status |
|------------------|-------------------------|--------------------|
| End of Week 1 (on time) | 3 weeks | Achievable |
| End of Week 2 (1-week slip) | 2 weeks | Tight but achievable for owners who engage immediately |
| End of Week 3 (2-week slip) | 1 week | Marginal. Engineering manager must confirm owner availability on the day Gate 0 resolves. |
| End of Week 4 (3-week slip) | 0 weeks | Gates 1/2/4 miss simultaneously. All three consequences activate. Schedule recalculated immediately. |

**The NSTL escalates to VP Engineering on the first business day of Week 2 if Gate 0 has not resolved.** This is not a 48-hour window from the deadline — it is a same-day trigger on the first day the deadline is missed, because every day of Gate 0 slip compresses the owner preparation window for Gates 1/2/4.

#### Gate 2 / Gate 3 Chain

Integration testing is scheduled to begin in Month 4