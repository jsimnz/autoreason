# Incident Response Process Design
## B2B SaaS Company - Strategic Implementation Guide

---

## 1. EXECUTIVE SUMMARY

This proposal establishes a robust incident response process designed to meet your 99.95% SLA commitment while managing realistic operational constraints. Given recent incidents and customer concerns, this framework prioritizes rapid response, clear communication, and sustainable operations that can actually be executed by your team.

**Key Commitments:**
- Response time targets based on business impact with honest coverage capabilities
- Clear decision authority eliminating approval bottlenecks
- Sustainable on-call model preventing burnout while maintaining coverage

---

## 2. BUSINESS-IMPACT DRIVEN SEVERITY CLASSIFICATION

### Clear Classification with Immediate Decision Authority

**Severity 1 (Critical) - ALL of these conditions must be met:**
**Response Time:** 30 minutes maximum
**Authority:** On-call engineer classifies immediately; no approval required

**Customer Impact Criteria (ALL must be true):**
- Complete service unavailability OR authentication/login completely broken
- Affects multiple customers OR affects any customer with active contract escalation
- Core business functionality completely inaccessible

**Technical Criteria:**
- Database completely inaccessible OR core application servers completely down OR DNS/networking preventing all customer access

*Fixes severity logic by requiring ALL conditions, eliminating over-classification from single customer complaints.*

**Severity 2 (High)**
**Response Time:** 2 hours maximum
**Authority:** On-call engineer classifies immediately

**Criteria:**
- Significant performance degradation (>50% slower than baseline) affecting customer workflows
- Non-core functionality unavailable (reporting, integrations, etc.)
- Database accessible but severely degraded performance
- Single customer executive escalation

*Fixes gray area by defining specific performance thresholds.*

**Severity 3 (Medium)**
**Response Time:** Next business day
**Criteria:** All other reported issues

### Executive Escalation (Automatic Triggers)

**Engineering Manager Notification (automatic):**
- All Sev 1 incidents (immediate notification)
- Any incident where on-call engineer requests help
- Sev 1 >4 hours: Available for consultation (IC retains command)

*Fixes IC authority conflicts by maintaining single command structure.*

**VP Engineering Notification (automatic):**
- Sev 1 incidents lasting >12 hours
- Customer threatens contract termination: Available within 4 business hours

*Fixes VP availability by defining "available" rather than "joins immediately."*

---

## 3. REALISTIC COVERAGE MODEL

### Team Size Assessment and Alternatives

**Coverage Options Based on Available Team:**

**Option A: 8+ Engineers Available**
- 1-week rotations
- Full timezone coverage as originally proposed
- Sustainable long-term model

**Option B: 4-7 Engineers Available**
- 2-week rotations maximum
- Single timezone primary coverage
- Cross-timezone coverage: Best effort within 2 hours
- Engineering Manager participates in rotation

**Option C: <4 Engineers Available**
- **Recommendation: Delay implementation until team growth**
- Alternative: Engineering Manager + VP Engineering share all critical incidents
- **Customer communication: "Limited after-hours coverage during team expansion"**

*Fixes resource math by providing specific alternatives for different team sizes.*

### Practical Coverage Schedule

**Business Hours (08:00-18:00 company primary timezone):**
- 1 engineer primary
- Backup engineer available for consultation within 1 hour

**After-Hours:**
- 1 engineer on-call (responds within 1 hour for Sev 1, within 2 hours for Sev 2)

**Coverage Gaps (Acknowledged):**
- 02:00-08:00 primary timezone: Response may be delayed up to 2 hours
- If no engineers in secondary timezone: Cross-timezone incidents may have delayed response
- **Customer communication template provided below addresses coverage limitations**

*Fixes geographic assumptions by focusing on company's primary timezone.*

### Sustainable Limits

**Individual Limits:**
- Maximum 1 week on-call per month (with 8+ person rotation) or 2 weeks per month (with smaller teams)
- Maximum 12 consecutive hours active incident response
- **Flexible handoff: Transfer when incident reaches stable troubleshooting phase, not arbitrary time limit**
- Compensation: $200/week on-call stipend + comp time 1:1 for weekend work >4 hours
- Comp time requires Engineering Manager approval

*Fixes perverse incentives by removing hourly pay and setting higher threshold for comp time.*

---

## 4. STREAMLINED ESCALATION AND COMMUNICATION

### Communication Authority with Realistic Backup

**Customer Communication Authority:**
- **Primary: Designated customer communication lead (Support Manager, Customer Success lead, or VP Engineering)**
- **Backup: VP Engineering**
- **If both unavailable: Engineering Manager provides technical updates only, with note that full communication will resume when primary available**

*Fixes Support Manager dependency by allowing role flexibility.*

**Incident Command:**
- On-call engineer becomes Incident Commander automatically
- IC authority: Technical decisions, resource requests, vendor engagement
- IC handoff: When incident reaches stable troubleshooting phase OR IC requests relief

### Security Incident Communication

**Security incidents require legal approval for external communication:**
- Legal counsel has 4 hours maximum to approve
- **If legal approval not received within 4 hours: VP Engineering authorizes generic "security investigation" communication**
- **After 8 hours: Automatic escalation to CEO for communication decision**

*Fixes meaningless legal constraint by defining enforcement mechanism.*

---

## 5. PRACTICAL COMMUNICATION TEMPLATES

### Detection and Initial Response

**Issue Detection Criteria:**
- Monitoring alert triggers
- Customer report received
- Internal team identifies problem affecting customers

*Fixes "confirmed service issue" ambiguity by defining detection triggers.*

#### Immediate Response (Within 30 minutes of detection)
**Subject: Service Issue - [Company] Platform**

```
We are investigating a service issue with our platform.

Issue detected: [time]
Current status: Investigating
Affected services: [If known] / Determining scope [If not]

We will provide an update within 2 hours with more details.

Status page: [URL]
Support: [contact]
```

*Fixes information availability problems by only requiring known information.*

#### Regular Updates (Every 2 hours until resolved)

```
Service Issue Update - [time]

Status: [Investigating/Identified cause/Implementing fix/Monitoring resolution]
Affected services: [Specific list or "Still determining"]
Impact: [What customers are experiencing]
Estimated resolution: [If we have confidence in timeline] / [No ETA available - investigation continuing]

Actions taken since last update:
- [Specific steps]

Next update: [Time - maximum 2 hours]
```

### Resolution Communication

```
Service Issue Resolved - [time]

Issue resolved: [time]
Total duration: [time]
Brief cause: [If determined] / [Root cause analysis in progress]

We will complete our investigation and share findings within [2 weeks for simple issues, 4 weeks for complex issues].

Thank you for your patience.
```

*Fixes arbitrary post-mortem timelines by providing immediate customer expectation.*

---

## 6. SIMPLIFIED TIMEZONE HANDOFF

### Flexible Handoff Based on Incident State

**Routine Handoff (Beginning of each shift):**
```
Handoff [Date]
Active incidents: [List with current status and IC]
Monitoring: [Any alerts trending toward thresholds]
Handoff contact: [Phone number for questions]
```

**Active Incident Handoff:**
- **Handoff timing: When incident reaches stable troubleshooting phase OR when IC requests relief**
- **Simple incidents:** Written status update in incident channel
- **Complex incidents:** 5-minute phone call + written status
- **Previous IC available for questions for 1 hour after handoff**

*Fixes mandatory 12-hour handoff by basing timing on incident state rather than arbitrary time.*

**Cross-timezone Coverage:**
- If no engineers available in secondary timezone: Acknowledge limitation upfront
- Cross-timezone escalation: Engineering Manager takes over until primary timezone available

*Fixes timezone assumptions by planning for single-timezone teams.*

---

## 7. PRACTICAL POST-MORTEM PROCESS

### Immediate Timeline Communication

**At Incident Start:**
All customers receive timeline expectation in resolution communication:
- **Simple issues (single system, known remediation): Investigation results within 2 weeks**
- **Complex issues (multi-system, unknown cause, security impact): Investigation results within 4 weeks**

*Fixes classification timing by setting expectations immediately.*

### Classification Criteria

**Simple Incident:**
- Single system failure
- Standard remediation successful
- No security implications
- Cause clearly identified during resolution

**Complex Incident:**
- Multi-system failure
- Required custom fixes or vendor engagement
- Security implications or data impact
- Cause requires investigation beyond immediate resolution

### Streamlined Review Process

**Post-Mortem Document:**
```
# [Incident Title] - [Date] - [Simple/Complex]

## Customer Impact
- Duration: [start to resolution]
- Services affected: [list]
- Customer experience: [what they saw/experienced]

## Timeline
- [Key events only - detection, major actions, resolution]

## Root Cause
- Technical cause: [if determined]
- Process gap: [if applicable]
- Why wasn't this prevented/detected faster?

## Action Items
- Must fix: [Critical items with owners and dates]
- Should improve: [Next sprint items]
- Could enhance: [Backlog items]
```

**Review Process:**
- Sev 1: 30-minute review meeting required
- Sev 2: Email review, meeting if process changes needed
- Action items integrated into regular sprint planning

*Fixes training assumptions by providing specific template and realistic time allocation.*

---

## 8. MONITORING AND ALERTING REQUIREMENTS

### Minimum Monitoring Requirements

**Before implementing this process, ensure:**
- Monitoring covers core customer-facing functionality
- Alerts trigger before customers typically notice issues
- False positive rate <10% (no more than 1 false alert per 10 real alerts)
- Monitoring system itself has uptime monitoring

**Monitoring Failure Protocol:**
- If monitoring down >2 hours: Engineering Manager coordinates manual service checks every 4 hours during business hours
- If monitoring down >24 hours: **Escalate to emergency monitoring restoration; consider external monitoring service**
- Customer reports become primary detection method during monitoring outages

*Fixes monitoring assumptions by defining minimum requirements and realistic manual fallback.*

---

## 9. SLA INTEGRATION AND IMPACT

### SLA Calculation Method

**Downtime Definition:**
- Sev 1 incidents: 100% downtime for duration
- Sev 2 incidents: 50% downtime for duration
- Sev 3 incidents: No SLA impact

**Monthly SLA Calculation:**
Total uptime = (Total minutes in month - Downtime minutes) / Total minutes in month

**SLA Credit Triggers:**
- Monthly uptime <99.95%: Automatic 5% monthly fee credit
- Single incident >4 hours: Additional 10% monthly fee credit
- **VP Engineering authorizes all SLA credits; no other approval required**

*Fixes SLA integration by defining specific calculation method and credit authorization.*

### Customer Communication for SLA Impact

**When SLA breach likely:**
```
Due to this incident, we expect to miss our monthly SLA commitment. We will automatically apply appropriate service credits to your account and provide details in our incident review.
```

---

## 10. FAILURE SCENARIOS AND DEGRADED SERVICE

### Personnel Shortages

**Insufficient engineers for rotation:**
- <4 engineers: Engineering Manager + VP Engineering cover all Sev 1 incidents
- Key engineer unavailable: Engineering Manager covers shift
- **Communication to customers: "Response times may be extended due to team coverage limitations"**

**Multiple simultaneous Sev 1 incidents:**
- Engineering Manager takes command of second incident
- **If >2 simultaneous Sev 1: Focus on incident affecting most customers first**
- **Customer communication: "Multiple critical incidents are affecting our response capacity"**

*Fixes vague failure planning by defining specific actions and communication.*

### System Failures

**Monitoring system down:**
- Manual checks every 4 hours during business hours only
- Customer reports become primary detection
- **Acknowledge monitoring limitation in customer communications**

**Communication systems down:**
- Use personal phones and backup communication channels
- **If multiple systems down: Focus on technical resolution first, communicate when systems restored**

---

## 11. IMPLEMENTATION REQUIREMENTS AND SUCCESS CRITERIA

### Pre-Implementation Checklist

**Required before starting:**
- [ ] Minimum 4 engineers committed to on-call participation
- [ ] Designated customer communication lead identified with backup
- [ ] Basic monitoring system functional (defined above)
- [ ] Incident tracking system or shared document process
- [ ] Phone tree tested for escalations

*Fixes undefined pilot success by providing clear implementation prerequisites.*

### Training Requirements

**4-hour training per engineer covering:**
- Severity classification with examples
- Communication templates and approval process
- Escalation procedures and contact methods
- Basic incident investigation techniques for your specific systems

**Competency validation:**
- Practice scenario: Engineer can classify incident severity correctly
- Practice scenario: Engineer can follow escalation procedure
- Practice scenario: Engineer can use communication templates

*Fixes training assumptions by defining specific curriculum and validation.*

### Success Metrics (3-month evaluation)

**Process Effectiveness:**
- Sev 1 response time <30 minutes: >80% of incidents
- Customer communication within 30 minutes: >90% of incidents
- Post-mortem completion within committed timeline: >90%

**Operational Sustainability:**
- On-call engineer availability: <10% shift coverage gaps
- Engineer satisfaction with on-call process: >3.5/5.0 rating
- Escalation procedures followed correctly: >95% of incidents

**Customer Impact:**
- Monthly SLA achievement: 99.95% uptime
- Customer complaints about incident communication: <5% of incidents
- Repeat incidents (same root cause): <20% of total incidents

*Fixes undefined success criteria by providing specific, measurable targets.*

### Resource Requirements

**Personnel:**
- 4-8 engineers for on-call rotation (depending on chosen coverage model)
- Designated customer communication lead with backup
- Engineering Manager availability for escalation

**Budget:**
- $200/week on-call stipend per engineer
- Comp time: 1:1 for weekend work >4 hours
- Training time: 4 hours per engineer initial + 2 hours monthly review

This implementation provides a practical incident response framework that acknowledges real operational constraints while establishing clear improvement targets based on measurable outcomes and sustainable operations.