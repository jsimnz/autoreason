## Real Problems with This Proposal

### 1. The Coverage Gate System Is Operationally Unworkable

The proposal requires Gate 2 (independent incident simulation) to be conducted with the primary owner "unavailable for the duration." With 4 engineers, making any engineer fully unreachable during a business day creates real operational risk. The proposal acknowledges simultaneous unavailability as a gap but then builds a mandatory process that deliberately creates it. There's no analysis of what happens to the rest of the system during the simulation window.

### 2. E1's Dual-Role Conflict Is Understated

The proposal calls E1's dual-role conflict during Gate 3 week "a one-week conflict" and accepts the residual risk. But E1 owns "the most critical component" by the proposal's own description, and the mitigation is E2 paging E1 while E1 is simultaneously handling a push incident. This isn't a documented escalation path — it's hoping two incidents don't overlap during a specific week. No staffing solution is offered; the risk is simply named and accepted.

### 3. The Traffic Model Has an Unexamined Denominator Problem

The proposal correctly flags that push reaches MAU while in-app reaches DAU, then applies a 70% opt-in rate to MAU for push. But 70% opt-in of installed users is an assumption presented without a source or a sensitivity analysis. Push opt-in rates in social apps are highly variable (often 40–60%). If actual opt-in is 45%, push volume at target frequency drops significantly and the design ceiling calculation changes. The proposal treats this as a known input rather than a meaningful uncertainty.

### 4. The SMS Fallback Gate Has a Race Condition

The fallback gate checks a monthly spend counter before dispatching. In a distributed system processing ~3,190/sec at peak, multiple workers can read the counter simultaneously before any write commits, allowing spend to exceed the cap before the check catches it. The proposal doesn't address atomic counter reads or any locking mechanism. The $15,000 hard cap may not actually be hard.

### 5. The P0 Push Failure Rate Assumption Is Circular

The SMS budget analysis assumes a 2% push failure rate to estimate P0 SMS fallback volume. Push failure rates are highly dependent on the quality of the push infrastructure being built — which hasn't been built yet. Using 2% as a planning input without acknowledging that actual failure rates could be 5–10% (common in early push implementations) means the SMS budget ceiling of $15,000/month could be breached in normal operation, not just edge cases.

### 6. Month 1 Acceptance of Sole Responder Is Underweighted

The proposal accepts E3 as the sole incident responder for in-app during month 1, with E4 as an "informal backup." E4 is explicitly not coverage-gate-qualified. But the proposal elsewhere states that coverage gates exist precisely because "cross-training in the sense of watching someone else work does not constitute coverage ability." E4 as informal backup is exactly the coverage model the proposal argues against. The internal-traffic mitigation doesn't eliminate incidents; it reduces their frequency.

### 7. The Runbook Maintenance Process Depends on Sprint Planning Enforcement

The monthly runbook review is enforced via a "required field in the sprint planning template." This is process theater — a required field in a template is trivially satisfied by typing anything. The proposal provides no mechanism to verify that the sign-off reflects an actual review versus a checkbox. The same month 4 and 6 spot-checks that are supposed to catch runbook drift are themselves dependent on runbooks being current to be meaningful tests.

### 8. Gate Failure Consequences Are Asymmetric in a Way That Creates Perverse Incentives

A failed Gate 2 simulation defers the channel launch and triggers a runbook rewrite. A failed month 4 or 6 spot-check triggers a channel freeze on *ramp-up* only — the channel continues operating at its current traffic level. This means a coverage partner who cannot demonstrate competency is still on-call for existing traffic. The proposal identifies this as acceptable but doesn't explain why the standard for ongoing operation is lower than the standard for initial launch.

### 9. The Document Is Truncated

Section 3a is cut off mid-sentence ("FCM is mocked at this load level. This is an explicit—"). The three-part validation suite described as having three distinct purposes and three distinct tests only begins describing Test 1. Tests 2 and 3 are missing. This is a submitted proposal with missing content, not a draft marker.

### 10. The Per-Channel Queue Rationale Addresses One Failure Mode

The document argues for per-channel queues specifically to prevent FCM backpressure from blocking email and in-app. This is a real failure mode. But the proposal doesn't analyze failure modes that the per-channel design *introduces* — specifically, what happens when the shared priority classifier becomes the bottleneck or failure point. The classifier is now a single point of failure across all four channels, and it receives no dedicated reliability analysis despite being the component that all channels depend on.

### 11. The Emergency SMS Allowlist Approval Process Has No Fallback

The emergency allowlist path requires two approvals within 30 minutes — the on-call engineer and the engineer's manager. If the manager is unreachable (travel, time zone, weekend), the process stalls. With 4 engineers, the manager may also be one of the 4 engineers, creating ambiguity about whether the engineer approves their own emergency change. No alternate approver is named.