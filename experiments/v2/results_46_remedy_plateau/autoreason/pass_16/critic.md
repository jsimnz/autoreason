## Real Problems

### 1. The Document Describes Itself More Than the System

The opening two pages are a meta-document: a changelog, a resolution table, a list of what prior versions got wrong. This is version control commentary embedded in a design document. A reader trying to understand the notification system must excavate through self-referential prose before reaching any architectural content. The "Document Status" section would be appropriate in a commit message or a review thread, not in the artifact itself.

### 2. The Confidence Interval Construction Is Not Shown

The document repeatedly asserts that delay figures have confidence intervals "derived from input distributions" with "construction method shown" in §2.3. The actual §2.3 content is not present in this excerpt. The executive summary table presents intervals like "47 min (CI: 18–95 min)" as if they are analytically derived, but the derivation is deferred to a section that is either missing or truncated. Readers are asked to trust the intervals without seeing the queue model, the assumed distribution families, or how volume uncertainty propagates through them. The claim of rigor is present; the rigor itself is not.

### 3. The Default Decision Mechanism Is Structurally Unsound

The document states that if no sign-off occurs within 14 days, the default is Option C. This means inaction produces a decision. For a choice the document itself describes as requiring "product lead and engineering lead jointly," a silent default is not a substitute for joint sign-off — it is a way to make the decision without the required parties explicitly agreeing. If either stakeholder is unaware of the 14-day window, or disagrees with Option C but fails to respond in time, the document has laundered an unconsented decision as a default.

### 4. The Email Volume Calculation Is Opaque

The volume table states email volume is "8.0M/day" with a population base of "5M MAU with verified email" and a "78% weighted daily fraction." Where 78% comes from is never explained. It is not broken down, not cited, and not listed among the five flagged unvalidated assumptions — yet it directly determines 23% of total dispatch volume. The document is explicit about flagging unvalidated assumptions, but this one is presented as a figure without that treatment.

### 5. The "Factor of 2" Infrastructure Sizing Claim Is Unsubstantiated

The document states infrastructure is "sized to handle the factor-of-2 upper bound under sustained load" but does not specify what that sizing actually is. The volume range is 20M–55M/day, which is not a factor of 2 — it is a factor of 2.75. The worker capacity table shows 3,000/sec as a planning midpoint for 100 workers. Whether 100 workers at 3,000/sec handles 55M/day sustained is not demonstrated. The claim and the arithmetic do not reconcile.

### 6. The 8× Spike Is Called "Beyond Cited Data" But Still Planned For

The document simultaneously states that any multiplier above 8× "is beyond the range of cited data and any reasonable extrapolation" and that the 8× scenario itself is "extrapolation beyond cited data." If 8× is already extrapolation, the boundary at 8× is arbitrary. The document does not explain why 8× is the correct upper planning bound rather than 6× or 10×. The stress scenario is treated as if it has analytical grounding it does not have.

### 7. The In-App Consistency Contract Is Deferred Without a Placeholder

Section §4.3 is referenced multiple times as specifying "the in-app consistency contract and failure behavior," but no content from §4.3 appears in this document. The failure mode — user receives push alert but sees nothing in-app — is described as "addressed in §4.3," yet the address is not present. This is a known failure mode with no visible resolution in the document as written.

### 8. The DAU/MAU Remediation Procedure References Authority and Lead Time Without Stating Them

The document says §1.1.1 "adds remediation procedure, authority, and lead time" for the DAU/MAU validation commitment. The sensitivity table appears, but the actual remediation procedure — who has authority, what the lead time is, what action is taken if the ratio falls outside the modeled range — is not present in the visible content. The resolution table claims this was fixed; the document body does not show it.

### 9. Worker Capacity Range Is Internally Inconsistent

The key figures table states worker capacity for 100 workers as "2,200–4,400/sec" with a planning figure of 3,000/sec. The planning figure is described as "planning midpoint" but 3,000 is not the midpoint of 2,200–4,400 — the midpoint is 3,300. The document notes this is "not a midpoint of the latency range" and claims the distinction is explained in §1.1.2, but the explanation is not visible. The figure is used throughout the document as if it were a midpoint when it is not.

### 10. The Timeline Slack Budget Is Referenced but Not Visible

Section §7.1 is cited as aggregating "all conditional time costs against the 6-month constraint" and the interaction analysis concludes that 3.5 engineer-weeks of potential rework "is within the slack budget aggregated in §7.1." This claim is load-bearing — it is part of the justification for the default decision — but §7.1 content does not appear. A reader cannot verify whether the slack budget actually accommodates the contingency costs.

### 11. SMS Volume Is Treated as Negligible Without Justification

SMS is listed as ~50K/day and then effectively ignored in all subsequent analysis. For an auth-event channel, volume is not reach-limited but event-limited. The document never specifies what triggers an SMS, what the expected auth event rate is, or whether SMS has different latency SLAs than other channels. A channel handling authentication OTPs likely has stricter latency requirements than push social notifications, but this is never addressed.