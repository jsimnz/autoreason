## Real Problems with This Proposal

### 1. The Change Log Claims No Issues Are Carried Forward, But This Is Unverifiable

The change log states "No issues are carried forward unresolved," yet the document is explicitly cut off mid-sentence at the end of §1.1 ("Workers"). This is the same category of defect that was supposedly resolved in a prior revision. The claim of completeness is falsified by the document itself.

---

### 2. The Document References Sections That Do Not Exist in This Revision

Multiple sections are cited but not present: §2.4 (opt-out compliance failure scenarios), §5 (Redis memory sizing), §6 (connection pooling), §6.2 (SendGrid contract and email scheduling), and §7 (worker health monitoring). Legal is directed to §2.4 for failure scenarios needed to complete their sign-off. That section is absent. The sign-off table references §2.4 as the basis for a Week 2 deadline, but the content supporting that decision is not here.

---

### 3. The Consolidated Legal Sign-Off Creates a Single Point of Failure With No Contingency

The proposal consolidates two previously separate legal reviews into one, explicitly to resolve a circular dependency. But this means if Legal misses the Week 2 deadline on either item, both are blocked simultaneously. The document acknowledges a one-week slip in schema work but does not address whether the two items could be partially decoupled if one is ready and the other is not. The consolidation may have traded a dependency problem for a larger scheduling risk.

---

### 4. The 14/DAU Design Basis Is Asserted as Correct Without Validation Data

The document repeatedly characterizes 14/DAU as "plausible, not extreme," but this is an assertion. No user research, comparable app benchmarks, or measurement from a beta cohort is cited. The entire infrastructure sizing — worker count, Redis memory, connection pools — rests on this number. If actual usage comes in at 18–20/DAU (also plausible for a social app with DMs and social graph activity), the design basis is wrong in the same direction as the previous revision's 11/DAU basis was wrong.

---

### 5. Worker Count Is Specified as 24 But the Derivation Is Not Present

The change log states "Worker count specified (24); jitter analysis completed relative to count." The number 24 appears in the change log summary but no derivation, capacity model, or utilization calculation is visible in the document body. The jitter analysis that supposedly depends on this count is not shown. A reader cannot verify whether 24 workers is correctly sized for 4,083/sec at the assumed job processing time.

---

### 6. Default B Specification Cuts Off Before Describing Worker Recovery

The Default B specification reaches "Workers" and stops. The most operationally critical behavior — how workers exit Default B, what triggers recovery, whether Tier 3 queue depth is checked before resumption, and what happens to messages queued during suspension — is entirely absent. This is not a minor omission; it determines whether Tier 3 messages are reliably delivered after a spike or silently lost.

---

### 7. The Tiered Degradation Table Contains an Inconsistency in the Yellow Alert Row

The table shows the 3,200–3,600/sec band as "Yellow alert — no action" with all tiers unaffected. But the design basis normal peak is 4,083/sec. This means yellow alert activates well below normal peak operation, which contradicts the stated goal that "Default B should respond to genuine viral events, not to normal operation at the high end of the per-DAU range." The same logic applies to yellow alert — it would fire constantly during normal high-end operation.

---

### 8. The International Sustained Load Analysis Assumes a Geographic Distribution Without Basis

The 40/30/30 US/EU/APAC split is presented as a distribution assumption with no citation. The monitoring trigger (if 30% of DAU is outside the US) is calibrated against this assumed distribution. If the actual distribution is 60% APAC from launch — plausible for a social app depending on where it gains traction — the sustained load case is the default condition, not a threshold to watch for. The trigger may never fire because the condition may already be true at launch.

---

### 9. The Retry Contract Enforcement Sign-Off Has a Circular Dependency That Is Not Resolved

The sign-off table states that E4's enforcement layer work depends on the broadcast policy sign-off. But the producer registry and retry contract enforcement sign-off is listed as a separate item with a different deadline (before Month 2). If the broadcast policy sign-off slips past Month 3, E4 is blocked. But the retry contract enforcement — also owned partly by E4 — has an earlier deadline. The document does not clarify whether E4 can complete retry enforcement independently of broadcast, or whether a broadcast policy slip also delays retry enforcement.

---

### 10. "Invisible Data Loss" Is Named But Not Bounded

The sign-off table states that missing the producer registry deadline causes "429 responses produce invisible data loss for non-compliant producers." The document does not specify what fraction of producers are expected to be non-compliant at launch, what volume of notifications they represent, or how long data loss would persist. This is described as a consequence of a missed deadline but there is no way to assess the severity of that consequence from the information provided.

---

### 11. Default A and Default B Activation Times Are Inconsistent With the Yellow Alert Design

Default A requires 3 consecutive 10-second samples (30 seconds) above 3,600/sec. Default B requires 5 consecutive samples (50 seconds) above 5,200/sec. But there is no specification of what happens if the rate oscillates across the threshold — for example, 4 samples above 5,200/sec followed by 1 sample below, then 4 more above. Whether the counter resets or accumulates is unspecified, and this matters for whether Default B activates during a real spike or fails to activate due to measurement noise.

---

### 12. The Cost Implication Claim Is Unanchored

The document states infrastructure spend during spike windows will be "approximately 30–40% higher" under the 14/DAU basis versus 11/DAU sizing. No baseline cost figure is provided, so this percentage is uninterpretable in budget terms. Finance and Procurement are stakeholders in the SendGrid contract sign-off but have no basis to evaluate whether this cost increase is acceptable.