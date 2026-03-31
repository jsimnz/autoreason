Here are the real problems with this proposal:

**1. The peak throughput math is internally inconsistent.**
The document defines the design envelope as ~6,375/sec (3× the sustained peak), then Test 1 validates at 2× (~4,250/sec) and calls that "the test against which we claim the system works." These two numbers are never reconciled. The system is designed to a 6,375/sec envelope but validated at 4,250/sec, and the gap is papered over with the FCM rate-limit excuse. That excuse doesn't hold: the 3× spike applies to the entire system, not just FCM. Internal queues, workers, and the database can be tested at 6,375/sec with mocked FCM. Choosing 2× as the validation target is a real coverage gap, not an honest limitation.

**2. The coverage gate structure creates an impossible month 2 timeline.**
Month 1 ends with E4 completing Gate 3 solo on-call for queue/in-app scope. Month 2 requires E4 to complete Gates 1–3 for push coverage while simultaneously building email transactional delivery. Gates 1–3 are defined as sequential, time-separated checkpoints. Gate 1 is a runbook review, Gate 2 is a simulation one week later, Gate 3 is a solo on-call week after that. That's a minimum of three weeks of coverage process for push, plus email implementation, in a four-week month. The proposal defers email to month 3 if scaffolding runs long, but says nothing about what happens if push coverage gates slip. There is no stated resolution.

**3. E2's coverage gates are never defined.**
The table says "E2 Gates 1–3 for email coverage" in month 2, but E2's primary responsibility is push integrations. E2 covering email means E2 is the coverage partner for E4's email channel. But the team allocation table lists E4's coverage partner as E2 and E2's coverage partner as E4. This is circular, not mutual as claimed. If E4 is unavailable, E2 covers email — but who covers push while E2 is handling email incidents? The document asserts coverage partnerships are "mutual, not circular" and then constructs a circular dependency.

**4. The SMS allowlist governance is described but never operationalized.**
The document says the SMS allowlist "requires two-engineer sign-off" and defines an escalation path in Section 3.3 — but Section 3.3 is never included in the document. This is a hard gate on a channel with existential budget consequences, and the escalation path for urgent additions is a forward reference to missing content.

**5. The opt-out drift detection during weeks 1–8 is explicitly manual with no accountability structure.**
The document admits this is "a manual process that depends on someone actually looking at the dashboard." The only accountability mechanism is a dashboard link in the sync template. There is no owner named, no consequence for skipping the review, and no record kept of whether reviews occurred. For a system explicitly identified as having an audience damage risk that is permanent and irreversible, this is a meaningful gap.

**6. The per-type cap of "1 per type per user per day" is unenforceable as stated.**
Notification types are not defined anywhere in this document. Without a controlled, versioned taxonomy of notification types, this limit cannot be enforced at the dispatcher. Enforcement requires that the type field be a closed enum with defined membership — otherwise callers self-classify, the cap is trivially circumvented, and the protection is nominal.

**7. The 2,500-recipient exclusion threshold for per-type alerting has no stated review process.**
Types with fewer than 2,500 recipients are excluded from automated alerting and "reviewed manually in the weekly traffic review." There is no mechanism to graduate a type from manual review to automated alerting as its volume grows, no owner for the manual review, and no definition of what "reviewed" means or what action it triggers. A type could stay below 2,500 recipients indefinitely and remain in a permanently manual, unstructured review state.

**8. The ramp gate for increasing push frequency from 3/day to 5/day requires statistical alerting that doesn't exist yet.**
The gate requires "no notification type with an opt-out rate above 1% in the most recent 4-week window." But per-type statistical baselines aren't computed until week 9, and the per-type absolute threshold during weeks 1–8 is 2%, not 1%. The ramp could theoretically begin at week 8 (after no aggregate alert for 8 weeks), but the 1% per-type gate references a measurement that doesn't exist until week 9. This is an unresolved sequencing conflict.

**9. The document ends mid-section.**
Section 2.1 has a header and nothing else. The architecture — the central technical content of a system design document — is absent. All the scaling math, failure mode analysis, and governance machinery described in Section 1 exists without any actual system design to support it.