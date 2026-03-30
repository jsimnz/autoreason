## Real Problems with This Proposal

### Structural and Organizational Problems

**The document organization is self-defeating.** Section 7 is placed first because subsequent sections reference it, but Section 7.3 references Section 1.1, which comes later. The introduction acknowledges this by telling readers to go read Section 1.1 before Section 7.3. This is circular. The document cannot be read linearly in either direction.

**The engineering lead role is structurally compromised.** The lead is one of four engineers, carries primary ownership of architecture decisions and vendor relationships, provides executive escalation, covers E4 during absences, is "always reachable for P0 escalations," and approves any infrastructure recommendation requiring more than 20% change. This person also rotates on-call. The document acknowledges the team is under staffing pressure but does not acknowledge that the lead's non-development obligations alone likely consume more than the 20% steady-state operational budget assigned to each engineer.

**Coverage matrix has a single point of failure the document does not acknowledge.** If the Lead and E1 are simultaneously unavailable, there is no coverage for "operational decisions" and "infrastructure provisioning." E2 covers "non-architecture decisions" for the Lead but E2's own primary is queue infrastructure. The matrix looks balanced but has not been stress-tested against simultaneous absences of more than one person.

### On-Call and Operational Reality

**The 40% escalation trigger is not actionable.** The document says if any engineer exceeds 40% operational load for two consecutive weeks, the lead escalates to the executive sponsor "as a delivery risk." What happens after escalation is not defined. There is no described outcome, no authority granted, no staffing lever available. Escalation without a defined response option is documentation theater.

**The on-call rotation math is not presented honestly.** A 4-person rotation with 2-person coverage means each engineer is on primary or secondary call roughly half the time, not "every other week" as stated. Every other week for primary, plus every other week for secondary, is essentially continuous coverage responsibility with one week of relief. The document understates this.

**Page-worthy thresholds are not connected to staffing reality.** The DAU/MAU 7-day rolling average crossing a threshold for three consecutive days is listed as a page-worthy condition. This is a slow-moving trend metric. Paging an on-call engineer at 2am because a 7-day rolling average crossed a threshold for day three is not an appropriate use of an interrupt. It is a metric for a weekly review.

### Technical Sizing Problems

**The Scenario A spike multiplier is not reconciled with the queue depth threshold.** A 20× instantaneous spike at 1,750/sec sustained peak produces approximately 35,000 notifications/sec instantaneously. The P1 page threshold is 500K queue depth for more than 10 minutes. Whether 30 P1 workers can drain a queue filling at 35,000/sec fast enough to stay under 500K is not calculated anywhere in the document. The threshold and the spike definition exist in separate sections without being connected.

**The 60% capacity provisioning rationale is asserted, not derived.** The document states Phase 1 is provisioned at 60% capacity against the 15/35/50 worst-case ceiling. Why 60% and not 70% or 50% is never explained. This is a significant infrastructure cost decision presented as if it were a natural constant.

**Redis memory sizing contains a gap.** The document sizes Redis P1 queue memory at ~4GB for a 2M item spike ceiling at baseline DAU, and ~4.8GB at 35% DAU/MAU. It does not account for Redis overhead, key expiry metadata, or the memory used by non-queue data structures (session data, rate limiting, etc.) that presumably also live in this cluster. The 4GB and 4.8GB figures appear to be raw payload estimates.

**The sparsity suppression correction is acknowledged as unquantifiable but still used directionally.** The document explicitly states the suppression magnitude "cannot be quantified" and that applying it as a multiplier "adds false precision." It then uses the suppression argument to justify setting the escalation threshold at 3× rather than 5×. This is the false precision the document claims to avoid. The 3× figure is not derived — it is asserted with the suppression argument as rhetorical support.

### Process and Decision Gate Problems

**The >3× false positive protocol has no defined outcome if the 48-hour window is missed.** The protocol says if no valid artifact is identified within 48 hours, the finding is confirmed and the Section 1.2a escalation protocol activates. Section 1.2a is not included in this document — it is cut off. The most severe decision gate references a section that does not appear.

**The week-6 calibration procedure has a failure mode that produces an arbitrary fallback.** If DAU/MAU standard deviation exceeds 5%, the document discards the ratio metric entirely and substitutes an absolute DAU threshold of 3.5M. The 3.5M figure is not derived from the calibration data — it corresponds to the 35% DAU/MAU scenario from Section 1.1a. This substitution is presented as a calibration outcome but is actually a pre-chosen number dressed as an adaptive response.

**The Phase 2 procurement trigger is incomplete.** The document ends mid-sentence: "ElastiCache and RDS read replicas are available within days; EC2 worker" — the Phase 2 section is cut off. This is not a minor omission; Phase 2 is the actual production scaling plan.

### Cost and Accountability Problems

**The cost range is too wide to be useful and the document acknowledges this without consequence.** A $4–8K/month delta on a $12–18K/month baseline is a 22–67% range of uncertainty. The document says these ranges "cannot be narrowed further before beta data is available" and instructs informing the executive sponsor. No budget approval process, no ceiling, and no authority to proceed or stop is defined. The sponsor is informed of an unresolvable uncertainty with no mechanism to act on it.

**The document explicitly states some features will slip during high-incident beta weeks but does not identify which features are slippable.** "Some features will slip" is presented as a correct tradeoff, but without a defined priority ordering, this means the decision about what slips will be made under incident pressure by whoever is not on-call that week. That is not a plan.