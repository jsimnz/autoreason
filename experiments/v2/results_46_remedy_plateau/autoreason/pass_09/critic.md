Here are the real problems I found:

---

**1. The spike model's "exponential decay" is described but not modeled as exponential decay.**

The document claims an exponential decay arrival shape, then immediately calculates "14,000/sec average instantaneous rate" over the first 90 seconds. That is a uniform rate, not an exponential decay. The entire queue depth arithmetic that follows uses flat rates. The shape claim is decorative — the math doesn't change from the prior draft's uniform model in any meaningful way. The "front-loaded" correction is largely cosmetic.

**2. The 5,000/sec processing rate appears without derivation.**

The queue depth calculations throughout §1.1.2 use 5,000/sec as the worker processing rate, but the worker pool is sized at 50 workers × 100 notifications/sec = 5,000/sec. That 100 notifications/sec per worker figure is never justified. It determines whether the entire spike analysis is valid or not, and it has no supporting measurement, benchmark, or reference.

**3. The high-priority SLA analysis contains a logical error.**

The document calculates that a high-priority message enqueued at t=0 waits ~3 minutes. But the revised allocation (70% of workers) is triggered when queue depth exceeds 50,000 — which takes time to detect and act on. The SLA calculation then uses the post-reallocation processing rate for the entire 90-second window, including the period before reallocation fires. The worst-case delay for messages enqueued at t=0 is understated.

**4. The document cuts off mid-sentence.**

The specification of the dynamic reallocation mechanism — explicitly called out in the revision notes as "now fully specified" — ends abruptly mid-line (`HIGH_PRIORITY_`). This is the single most-criticized item from the prior draft. The revision notes claim it is resolved. It is not present in the document at all.

**5. The "second spike arrives mid-drain" failure mode is listed as addressed in the revision notes but never appears in the text.**

Revision note #1 explicitly states the failure mode analysis includes "what happens when a second spike arrives mid-drain." No such analysis exists anywhere in the visible document. This is the same class of error as the prior draft — claiming a problem is solved in the summary without solving it in the body.

**6. The token bucket starvation prevention mechanism is mentioned but not specified.**

The executive summary says starvation prevention is "now addressed mechanically" via a token bucket with a "concrete minimum throughput guarantee." No token bucket parameters appear anywhere in the document — no fill rate, no bucket capacity, no minimum guaranteed throughput number. The claim of concreteness is false.

**7. The routing logic uses `user.is_active_session` as an always-deliver condition, but this creates a race condition that isn't acknowledged.**

If a user's session ends between the routing decision and delivery, the in-app notification is lost silently — the same silent drop problem the section is designed to prevent. The `fate = "attempted"` is set based on session state at routing time, not delivery time, and there's no reconciliation path.

**8. The 70% high-priority worker reallocation during spike conditions interacts with the token bucket starvation prevention in an unspecified way.**

When workers are reallocated to 70% high-priority during a spike, standard-priority throughput drops to 30% of capacity. Whether the token bucket minimum guarantee is maintained under this condition is never addressed. These two mechanisms are described independently as if they don't interact.

**9. The validation commitment for the 3× burst multiplier is not actually a validation.**

The commitment states: "If the 3× scenario produces queue behavior materially different from the model, the multiplier and capacity plan are revised." "Materially different" is undefined. There is no pass/fail criterion, no threshold, no decision owner, and no timeline for when the revision would be complete relative to launch. This is a commitment in form only.

**10. The email reach footnote contradiction is unresolved.**

The table says email reach is "50% of registered users at launch" with a note that "70% is steady-state." But registered users and DAU are different populations, and the prior volume calculations don't specify which base is used. A 50% reach of registered users at 10M MAU could be 5M users; 50% of DAU at 3M is 1.5M. The channel volume totals in §1 depend on which figure is used, and it's never stated.