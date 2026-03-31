## Real Problems with This Proposal

### 1. The Revision Trigger Logic Is Circular and Possibly Wrong

The document justifies the 15/DAU revision trigger by showing that at 15/DAU, Default A fires "during normal high-end operation." But the calculation uses the high scenario DAU (3,500,000), not the base scenario DAU (2,500,000). If the actual rate is 15/DAU at base DAU (2.5M), the peak is:

```
(2,500,000 × 15 × 0.90) ÷ 10,800 = 3,125/sec
```

That is well below the 4,400/sec Default A threshold. The trigger rationale only holds if the high DAU scenario is assumed simultaneously with the elevated per-DAU rate. The document does not state this assumption. It presents the trigger as a property of the per-DAU rate alone, which is misleading.

---

### 2. The Validation Timeline Has No Slack Analysis

The document claims "one week of margin" between measurement delivery (Week 9) and infrastructure lock (Week 10). One week of margin for a decision that determines whether the entire infrastructure sizing is correct is not analyzed for what happens if the measurement report is delivered but shows ambiguous or noisy data. A 30-day cohort of 50,000 users may produce wide confidence intervals. The document treats delivery of the report as equivalent to a usable result. These are not the same thing.

---

### 3. The Instagram and Twitter Benchmarks Are Used Inconsistently

The document uses Instagram's ~10–13 generated events/DAU as "consistent with the lower half of the range" and Twitter's 12–24 generated events/DAU as "bracketing the full range." But 12–24 does not bracket a range of 7.5–23 — it excludes the lower portion (7.5–12). The document then claims these figures establish that 14/DAU is "plausible" without noting that the two sources, taken together, are not actually consistent with each other at the low end. The benchmarks are doing more epistemic work than they can support.

---

### 4. The 90% Concentration Factor Is Unexplained and Unvalidated

The spike calculations throughout §1.1 apply a 0.90 concentration factor, representing 90% of daily events occurring within a 3-hour window. This figure appears in multiple critical calculations — including the Default A threshold calibration — but its origin is never stated. It is not part of the beta cohort validation plan. If the actual concentration is 0.75 or 0.95, the threshold calibrations are wrong. This is a load-shaping assumption with more leverage on the design than the per-DAU rate itself, and it receives no scrutiny.

---

### 5. The Tier 1 Queue Is "Unbounded During Spike" With Memory Risk Accepted but Not Bounded

The placeholder table states Tier 1 is "unbounded during spike" and that "memory risk accepted." This is not a design decision — it is an absence of one dressed up as acceptance. The document does not state what happens when Tier 1 exhausts available memory. There is no circuit breaker, no fallback, no ceiling. For the highest-priority queue in the system, this is a critical gap, and the document does not flag it as a sign-off item. It appears as a table row rather than an unresolved risk.

---

### 6. The Partial Decoupling Path Creates a Hidden Dependency on Legal Prioritization

The document correctly identifies the opt-out architecture as "the harder blocker" but then instructs that "Legal must be informed of this asymmetry." The document has no mechanism to ensure Legal acts on the asymmetry. If Legal treats both items as equivalent priority and resolves the DM policy first, the document's own analysis says schema work cannot begin. The design assumes Legal will internalize the asymmetry and act accordingly, but the sign-off table assigns both items the same deadline and the same owner with no differentiation in escalation path.

---

### 7. The Beta Cohort Size Is Not Justified Relative to the Measurement Goal

The cohort is set at 50,000 users. The design basis is 14/DAU with a range of 6–16. The document does not state what statistical precision 50,000 users produces over 30 days, nor what precision is required to make the infrastructure decision at Week 10. If the confidence interval at 50,000 users spans, say, 11–17/DAU, the measurement does not resolve the question of whether 15/DAU triggers a revision. The cohort size appears arbitrary.

---

### 8. The Document Ends Mid-Sentence

The final sentence — "This framing is intentional: the spike" — is cut off. This is the second instance of a truncation problem in this document. The revision log explicitly lists "Document cut off mid-sentence" as a resolved finding. It is not resolved.

---

### 9. The Default B Alert Threshold of 3 Activations per 24 Hours Is Not Connected to the Spike Taxonomy

The document defines four spike types (Type 1 through Type 4) with different expected frequencies and durations. The alert threshold of 3 activations per 24 hours is presented as distinguishing "legitimate spike response" from routine degradation, but no analysis connects this threshold to how often each spike type is expected to occur. If Type 1 spikes (the smallest) are expected to occur 4–5 times during a major sports event, the alert threshold would fire on legitimate load. The threshold is asserted without reference to the spike model the document itself defines.

---

### 10. The Cost Estimate Section Referenced in the Sign-Off Table Cannot Be Evaluated

The sign-off table references cost figures ($8,000–$12,000/month for the self-hosted SendGrid fallback) and states cost is "presented as absolute monthly figure with justification" in §1.1. The justification is not present in the visible text of §1.1. The revision log claims this was corrected, but the correction is not visible in the document as provided. Whether the correction exists or whether this is another instance of a claimed fix that did not land cannot be determined — but the absence is notable given the pattern.