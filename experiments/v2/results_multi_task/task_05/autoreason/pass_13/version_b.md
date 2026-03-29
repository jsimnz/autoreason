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

**Severity 1 (Critical) - ANY condition qualifies:**
**Response Time:** 30 minutes maximum
**Authority:** On-call engineer classifies immediately; no approval required

**Customer Impact Criteria (ANY qualifies):**
- Multiple customers affected (>5 customers or >3% of customer base, whichever is smaller)
- Core business functionality completely unavailable for any customer
- Single enterprise customer (>$50k ARR) completely unable to access core functionality
- Confirmed security breach with potential customer data exposure

**Core business functionality defined as:** Authentication, primary data access, primary business workflow completion (document processing, transaction completion, or equivalent primary use case as defined in customer contracts)

**Technical Criteria (ANY qualifies):**
- Primary database completely inaccessible
- Authentication system completely down
- Core application servers completely down preventing customer access
- Security breach requiring immediate containment

*Fixes Problem 1: Changes to ANY condition qualifies to prevent legitimate critical incidents from being under-classified. Removes contradiction between customer impact and technical criteria sections.*

**Severity 2 (High)**
**Response Time:** 2 hours maximum
**Authority:** On-call engineer classifies immediately

**Criteria (ANY qualifies):**
- Performance degradation where customer workflows take >60 seconds (measurable via application logs)
- Error rates >10% over 15-minute window on customer-facing operations
- Non-core functionality unavailable affecting multiple customers (reporting, integrations, admin features)
- Single customer executive escalation with contract implications

**Severity 3 (Medium)**
**Response Time:** Next business day
**Criteria:** All other reported issues

### Classification Review Process

**Classification can be adjusted during incident response:**
- Any team member can recommend reclassification with justification
- Engineering Manager makes final classification decision if disputed
- Customer communication acknowledges classification changes: "Based on additional investigation, we are adjusting our response level for this incident."

*Fixes Problem 3: Adds classification review process to prevent classification inflation while maintaining rapid initial response.*

### Executive Escalation (Automatic Triggers)

**Engineering Manager Notification (automatic):**
- All Sev 1 incidents (immediate notification)
- Any incident where on-call engineer requests help
- Sev 1 >4 hours: Available for consultation (IC retains command authority)

**VP Engineering Notification (automatic):**
- Sev 1 incidents lasting >8 hours
- Customer threatens contract termination: Available within next business day

*Fixes Problem 3: Removes immediate Engineering Manager joining for all 4+ hour incidents to prevent management overwhelm.*

---

## 3. REALISTIC COVERAGE MODEL

### Team Size Assessment and Sustainable Rotation Math

**Coverage calculation accounts for actual availability:**

**Current Available Engineers Assessment:**
- Count engineers willing and able to participate in on-call
- Subtract 1 engineer for vacation/sick leave at any time
- Subtract 1 additional engineer if team has <10 people total (higher impact of turnover)

**Rotation Schedule Based on Available Count:**

**7+ Available Engineers:**
- 2-week rotations
- Full business hours coverage (8:00-18:00 primary timezone)
- After-hours coverage with 2-hour response time target

**5-6 Available Engineers:**
- 3-week rotations
- Business hours coverage with Engineering Manager backup
- After-hours coverage with 4-hour response time target
- Weekend coverage: Single on-call only

**<5 Available Engineers:**
- **Recommendation: Implement business-hours-only incident response initially**
- Coverage: Monday-Friday 8:00-18:00 primary timezone
- After-hours: Customer communication sets expectation of next-business-day response
- Critical customer escalation: Engineering Manager available by phone for true emergencies

*Fixes Problem 2: Uses actual available engineer count rather than theoretical percentages. Provides realistic options including business-hours-only implementation.*

### Honest Coverage Communication

**Business Hours Coverage:**
- 1 engineer primary response
- Engineering Manager available as backup within 2 hours

**After-Hours Coverage (when available):**
- 1 engineer on-call with defined response time based on team size
- Customer communication clearly states actual response time capabilities
- No promises of coverage that cannot be consistently delivered

**Coverage Limitations:**
- Explicitly communicate coverage hours and response times to customers
- SLA calculations account for stated coverage limitations
- Contract discussions include realistic incident response capabilities

*Fixes Problem 2: Eliminates coverage gaps presented as acceptable by making coverage limitations explicit and factored into SLA calculations.*

### Sustainable Compensation

**Individual Limits:**
- 2-4 week rotations depending on team size
- Maximum 8 consecutive hours active incident response before mandatory handoff
- **Compensation: $200/week on-call stipend + comp time approval required for >2 hours incident work outside business hours**
- **Comp time requires manager approval and cannot exceed 8 hours per month per engineer**

*Fixes Problem 5: Reduces financial incentives for extending incidents. Adds approval process and caps comp time to prevent budget unpredictability and staffing chaos.*

---

## 4. STREAMLINED ESCALATION AND COMMUNICATION

### Multi-Tier Communication Authority

**Customer Communication Authority by Customer Tier:**

**Enterprise Customers (>$50k ARR):**
- **Primary: Dedicated Customer Success Manager (if available during incident)**
- **Backup: Support Team Lead**
- **After-hours: On-call engineer provides technical updates directly**

**Standard Customers:**
- **Primary: Support Team Lead**
- **Backup: On-call engineer**

*Fixes Problem 11: Removes assumption that CSMs have 20% spare capacity by making their availability conditional and providing realistic backup options.*

**Incident Command:**
- On-call engineer becomes Incident Commander automatically
- IC authority: Technical decisions, resource requests, vendor engagement
- IC handoff: After 8 hours maximum OR when IC requests relief

### Security Incident Communication

**Security incidents require legal review with realistic timelines:**
- **Suspected breach: Legal counsel notified, has 24 business hours to provide guidance**
- **If legal unavailable: Engineering Manager provides holding statement: "We are investigating a technical issue and will provide updates as information becomes available."**
- **After 48 hours: VP Engineering makes communication decision regardless of legal response**

---

## 5. INCIDENT-SPECIFIC COMMUNICATION APPROACH

### Detection and Initial Response

#### Immediate Response (Within response time target)
**Subject: Service Issue - [Company] Platform**

```
We are investigating a service issue affecting [specific services/functionality].

Issue detected: [time]
Services affected: [specific list of what customers cannot do]
Current status: [investigating cause/implementing fix/monitoring resolution]

We are actively working on resolution. Our next update will be provided when we have meaningful progress to report or within 4 hours, whichever comes first.

Status page: [URL]
Support: [contact]
```

*Fixes Problem 4: Removes specific 2-hour update promise. Commits to updates only when there's meaningful progress or at maximum 4-hour intervals.*

#### Progress Updates (When meaningful progress occurs or every 4 hours maximum)

```
Service Issue Update - [time]

Current status: [specific progress made OR "investigation continuing"]
Services still affected: [what customers still cannot do]
[Include estimated resolution ONLY if confident within 2 hours]

Actions completed since last update:
- [specific technical steps taken OR "detailed investigation ongoing"]

Next update: [when meaningful progress occurs or within 4 hours]
```

*Fixes Problem 4: Only provides estimates when confident. Acknowledges when investigation is ongoing without promising specific information.*

### Resolution Communication

```
Service Issue Resolved - [time]

Issue resolved: [time]
Total duration: [duration]
Brief description: [what was fixed]
Customers affected: [final count]

All services have been restored. We will provide a detailed incident analysis within [timeline based on customer tier and contract requirements].
```

---

## 6. SIMPLIFIED TIMEZONE HANDOFF

### State-Based Handoff Protocol

**Routine Handoff (Beginning of each shift):**
```
Handoff [Date] [Time]
Active incidents: [List with current Incident Commander]
Recent monitoring alerts: [Anything trending toward thresholds]
Handoff contact: [Primary phone for next 1 hour]
```

**Active Incident Handoff:**
- **Handoff timing: After 8 hours maximum OR when IC requests relief**
- **Handoff method: 10-minute phone call + written status in incident channel**
- **Previous IC available for questions for 1 hour after handoff**

**Cross-timezone Coverage:**
- **When no coverage available: Customer communication acknowledges response time limitations**
- **Engineering Manager available by phone for consultation during business hours only**

---

## 7. FOCUSED POST-MORTEM PROCESS

### Realistic Timeline Management

**Post-mortem timeline:**
- **All incidents: Initial findings within 2 weeks**
- **Complex incidents requiring vendor coordination: Full analysis within 4 weeks**
- **Enterprise customer contracts with specific requirements: Negotiate realistic timelines based on incident complexity**

*Fixes Problem 8: Removes unrealistic 3-day enterprise customer timeline. Acknowledges that complex incidents require more time and allows for timeline negotiation.*

### Practical Review Process

**Post-Mortem Document:**
```
# [Incident Title] - [Date]

## Customer Impact Summary
- Duration: [start to full resolution]
- Services affected: [specific functionality unavailable]
- Customer experience: [what customers could not do]
- Customers affected: [specific count and percentage]

## Timeline (Key Events Only)
- [Detection time and method]
- [Major troubleshooting steps]
- [Resolution implementation]
- [Full service restoration]

## Analysis
- Contributing factors: [known technical issues, environmental factors, or process gaps]
- Detection: [how incident was discovered and timing]
- Response effectiveness: [what worked well and what could improve]

## Next Steps
- Immediate fixes: [changes to prevent exact recurrence - with owner and target completion OR "no immediate changes identified"]
- Investigation items: [additional research needed with timeline OR "analysis complete"]
- Process improvements: [response or detection improvements with owner OR "current process adequate"]
```

*Fixes Problem 8: Removes requirement for definitive root cause determination. Acknowledges contributing factors and ongoing investigation items.*

**Review Process:**
- **All incidents: 45-minute review meeting within 2 weeks of resolution**
- **Action items: Must have owner and realistic timeline OR explicit decision that no action needed**
- **Customer communication: Send summary when complete**

---

## 8. MONITORING AND ALERTING REQUIREMENTS

### Practical Pre-Implementation Requirements

**Minimum monitoring coverage before process launch:**
- **User authentication success/failure rates**
- **Core API endpoints response time monitoring**
- **Database connectivity monitoring**
- **Application error rate monitoring**
- **Basic external service checking (login and primary workflow)**

*Fixes Problem 6: Removes customer-specific workflow monitoring requirement that is technically infeasible. Focuses on achievable monitoring basics.*

**Monitoring Infrastructure:**
- **Primary: Internal monitoring system**
- **Secondary: External service checking basic functionality**
- **Alert delivery: Email + SMS (minimum two methods)**
- **Baseline data: 2 weeks minimum before process launch**

*Fixes Problem 6: Reduces baseline data requirement from 4 weeks to 2 weeks to enable faster implementation.*

**Monitoring Failure Protocol:**
- **If primary monitoring down >30 minutes: Switch to external service alerts**
- **If all monitoring down: Customer reports become primary detection method**

---

## 9. SLA INTEGRATION AND IMPACT

### Simplified SLA Calculation Method

**Downtime Definition:**
- **Sev 1 incidents: Full downtime for duration of complete service unavailability**
- **Partial outages: Estimate impact as percentage of total customer base affected**
- **Sev 2 incidents: No SLA impact unless customer contract specifically includes performance degradation**

*Fixes Problem 7: Simplifies SLA calculation to avoid complex weighted customer-minutes calculation that is technically infeasible.*

**Monthly SLA Calculation:**
Total uptime = (Total minutes in month - downtime minutes) / Total minutes in month

**SLA Credit Process:**
- **Monthly uptime <99.95%: Service credits per contract terms**
- **Credits processed manually with next billing cycle**
- **Credit calculation requires incident impact assessment and customer notification**

*Fixes Problem 7: Removes automatic credit application that requires complex billing system integration.*

### Customer Communication for SLA Impact

**When SLA breach occurs:**
```
This incident impacted your service availability. We are reviewing the impact against our SLA commitment and will contact you regarding any applicable service credits within one week.
```

---

## 10. FAILURE SCENARIOS AND DEGRADED SERVICE

### Personnel Shortage Response

**Key personnel unavailable:**
- **Primary on-call engineer unavailable: Escalate to Engineering Manager**
- **Multiple engineers unavailable: Reduce coverage to business hours only with customer notification**
- **Engineering Manager unavailable: VP Engineering provides consultation during business hours**

### Multiple Simultaneous Incidents

**Incident prioritization:**
- **Multiple Sev 1s: Assign separate incident commanders if available, otherwise prioritize by customer revenue impact**
- **>2 simultaneous Sev 1s: Bring in all available engineers, customer communication explains situation**

### System Failures

**Communication systems down:**
- **Use personal phones for internal coordination**
- **Customer communication via direct email and phone calls**
- **Document communication delays for post-incident review**

---

## 11. IMPLEMENTATION REQUIREMENTS AND SUCCESS CRITERIA

### Pre-Implementation Checklist

**Required before starting:**
- [ ] **5+ engineers committed to on-call participation**
- [ ] **Customer communication contacts identified for enterprise accounts**
- [ ] **Basic monitoring system implemented with 2 weeks baseline data**
- [ ] **Incident tracking system configured**
- [ ] **Phone numbers collected for all participants**
- [ ] **Coverage schedule defined based on actual team size**

*Fixes Problem 6: Removes complex customer-specific monitoring and 4-week baseline requirements that block implementation.*

### Training Requirements

**8-hour training per engineer over 2 weeks covering:**
- **Week 1: System architecture, investigation techniques, communication procedures (4 hours)**
- **Week 2: Escalation procedures and incident simulation (4 hours)**

*Fixes Problem 9: Reduces training from 24 hours to 8 hours total to make resource requirements realistic.*

**Ongoing training:**
- **Monthly 1-hour session reviewing recent incidents**
- **Quarterly tabletop exercises**

**Competency validation:**
- **Successfully respond to 1 simulated incident with proper communication and escalation**

### Success Metrics (12-month evaluation)

**Process Effectiveness:**
- **Response time within target for incident severity: >70% of incidents**
- **Customer communication within response time target: >80% of incidents**
- **Post-mortem completion within stated timelines: >80%**

*Fixes Problem 10: Uses more achievable percentage targets and focuses on measurable response time rather than detection time.*

**Operational Sustainability:**
- **On-call rotation coverage maintained: <10% shift gaps**
- **Engineer participation in on-call program: >70% retention after 12 months**

*Fixes Problem 10: Removes unmeasurable customer contract renewal metric and focuses on operational metrics.*

**Customer Impact:**
- **Monthly SLA achievement: 99.95% uptime based on stated coverage model**
- **Customer escalations due to incident response: <2 per quarter**

### Resource Requirements

**Personnel:**
- **5+ engineers for on-call rotation**
- **Engineering Manager available for escalation during business hours**
- **Support team member available for customer communication**

**Budget:**
- **$200/week on-call stipend per engineer**
- **Comp time: Capped at 8 hours per engineer per month with manager approval**
- **External monitoring service: ~$50/month**

*Fixes Problem 5: Reduces stipend and caps comp time to prevent budget unpredictability.*

---