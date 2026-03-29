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

### Executive Escalation (Automatic Triggers)

**Engineering Manager Notification (automatic):**
- All Sev 1 incidents (immediate notification)
- Any incident where on-call engineer requests help
- Sev 1 >4 hours: Available for consultation (IC retains command authority)

**VP Engineering Notification (automatic):**
- Sev 1 incidents lasting >8 hours
- Customer threatens contract termination: Available within 4 business hours

---

## 3. REALISTIC COVERAGE MODEL

### Team Size Assessment and Sustainable Rotation Math

**Coverage calculation includes 20% buffer for vacation, sick leave, and training:**

**Option A: 10+ Engineers Available**
- 8+ participating after buffer
- 2-week rotations (16+ weeks between shifts)
- Full timezone coverage sustainable

**Option B: 8-9 Engineers Available**
- 6-7 participating after buffer
- 3-week rotations with Engineering Manager participating as backup
- Primary timezone coverage with acknowledged gaps

**Option C: 6-7 Engineers Available**
- 5-6 participating after buffer
- **Recommendation: 4-week rotations to achieve 20-24 weeks between shifts**
- Coverage gaps: 02:00-08:00 primary timezone with 4-hour maximum response time
- Weekend coverage: Single on-call with Engineering Manager backup

**Option D: <6 Engineers Available**
- **Recommendation: Implement business-hours-only incident response initially**
- Coverage: Monday-Friday 8:00-18:00 primary timezone
- After-hours: Customer communication sets expectation of next-business-day response
- Critical customer escalation: Engineering Manager available by phone for true emergencies

### Practical Coverage Schedule

**Business Hours (08:00-18:00 company primary timezone):**
- 1 engineer primary
- Engineering Manager available as backup consultant within 1 hour

**After-Hours Coverage (when team size permits):**
- **Primary timezone (18:00-02:00): 1 engineer on-call, responds within 1 hour for Sev 1**
- **Coverage gap (02:00-08:00): Maximum 4-hour response time for Sev 1 - communicated to customers**
- **Secondary timezone: Engineering Manager available by phone for consultation only**

### Sustainable Compensation

**Individual Limits:**
- 2-4 week rotations depending on team size
- Maximum 8 consecutive hours active incident response before mandatory handoff
- **Compensation: $500/week on-call stipend + comp time 1:1 for incident work >1 hour outside business hours**
- **Comp time automatically added to time tracking system, capped at 16 hours per engineer per month**

---

## 4. STREAMLINED ESCALATION AND COMMUNICATION

### Multi-Tier Communication Authority

**Customer Communication Authority by Customer Tier:**

**Enterprise Customers (>$50k ARR):**
- **Primary: Dedicated Customer Success Manager (if available during incident)**
- **Backup: Support Team Lead**
- **Emergency backup: VP Engineering (technical updates only)**

**Standard Customers:**
- **Primary: Support Team Lead**
- **Backup: On-call engineer**

**Incident Command:**
- On-call engineer becomes Incident Commander automatically
- IC authority: Technical decisions, resource requests, vendor engagement
- IC handoff: After 8 hours maximum OR when IC requests relief

### Security Incident Communication

**Security incidents require legal review with realistic timelines:**
- **Suspected breach: Legal counsel notified immediately, has 4 business hours to provide guidance**
- **If legal unavailable: VP Engineering provides holding statement: "We are investigating a technical issue and will provide updates as information becomes available."**
- **After 24 hours: CEO makes communication decision regardless of legal response**

---

## 5. INCIDENT-SPECIFIC COMMUNICATION APPROACH

### Detection and Initial Response

#### Immediate Response (Within response time target)
**Subject: Service Issue - [Company] Platform**

```
We are investigating a service issue affecting [specific services/functionality].

Issue detected: [time]
Services affected: [specific list of what customers cannot do]
Estimated customers affected: [number or percentage]
Current status: [investigating cause/implementing fix/monitoring resolution]

We are actively working on resolution. Our next update will be provided when we have meaningful progress to report or within 4 hours, whichever comes first.

Status page: [URL]
Support: [contact]
```

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

### Resolution Communication

```
Service Issue Resolved - [time]

Issue resolved: [time]
Total duration: [duration]
Root cause: [brief technical explanation]
Customers affected: [final count]

All services have been restored. We will conduct a full investigation and share findings within [customer-specific timeline based on contract requirements].
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
- **Previous IC available for questions for 2 hours after handoff**

**Cross-timezone Coverage:**
- **If no engineers in secondary timezone: Engineering Manager takes phone consultation role until primary timezone coverage begins**
- **Customer communication acknowledges coordination across timezones without promising specific response times**

---

## 7. FOCUSED POST-MORTEM PROCESS

### Customer-Contract-Based Timeline

**Post-mortem timeline based on customer contract requirements:**
- **Enterprise customers with <5-day requirement: 3 business days**
- **Standard contracts requiring <2-week response: 10 business days**
- **No specific contract requirement: 3 business weeks**
- **Complex incidents requiring vendor coordination: Full analysis within 4 weeks**

### Streamlined Review Process

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

## Root Cause Analysis
- Technical cause: [specific system/code/configuration failure OR "root cause investigation ongoing - interim findings"]
- Detection gap: [why wasn't this caught earlier OR "detection worked as designed"]
- Response gap: [what slowed resolution OR "response met targets"]

## Prevention Plan
- Critical fixes: [changes to prevent exact recurrence - with sprint assignment OR "no changes required"]
- Monitoring improvements: [better detection - with sprint assignment OR "monitoring adequate"]
- Process changes: [response improvements - with owner and timeline OR "process worked as designed"]

## Outstanding Investigation
[For incidents where root cause cannot be definitively determined within timeline]
- Current findings: [what is known]
- Ongoing investigation: [what is still being researched]
- Expected completion: [realistic timeline for remaining work]
```

**Review Process:**
- **All incidents: 45-minute review meeting within 1 week of resolution**
- **Prevention plan items: Must have sprint assignment and owner before post-mortem is complete OR explicit decision that no changes are needed**
- **Customer communication: Send prevention plan summary when complete**

---

## 8. MONITORING AND ALERTING REQUIREMENTS

### Specific Pre-Implementation Requirements

**Required monitoring coverage before process launch:**
- **User authentication success/failure rates >10% failure rate over 15-minute window**
- **Core API endpoints response time >baseline+500% for 10 consecutive minutes**
- **Database connection pool >80% utilization for 5 minutes**
- **Application error rates >10% over 15-minute window**
- **Basic external service checking (login and primary workflow)**

**Monitoring Infrastructure:**
- **Primary: Internal monitoring system with 1-minute check intervals**
- **Secondary: External service checking basic functionality every 3 minutes**
- **Alert delivery: Email + SMS + Slack/Teams (minimum two methods required)**
- **Historical data: 2 weeks minimum before process launch**

**Monitoring Failure Protocol:**
- **If primary monitoring down >15 minutes: Switch to external service alerts + proactive customer outreach to top 10 customers**
- **If all monitoring down: Customer reports become primary detection method - Engineering Manager coordinates proactive customer contact**

---

## 9. SLA INTEGRATION AND IMPACT

### Objective SLA Calculation Method

**Downtime Definition:**
- **Sev 1 incidents: Partial downtime calculated as (% customers affected × incident duration)**
- **Sev 2 incidents: No SLA impact unless customer contract specifically includes performance degradation**
- **Sev 3 incidents: No SLA impact**

**Monthly SLA Calculation:**
Total uptime = (Total customer-minutes available - weighted downtime customer-minutes) / Total customer-minutes available

**SLA Credit Process:**
- **Monthly uptime <99.95%: Service credits = 10% of monthly service fee**
- **Single incident >4 hours: Additional 5% credit regardless of monthly calculation**
- **Credits applied automatically to next month's invoice with incident reference**
- **No double-crediting for same incident impact**

### Customer Communication for SLA Impact

**When SLA breach occurs:**
```
This incident caused [specific impact to your service]. Based on our SLA commitment, a service credit has been automatically applied to your next invoice per your contract terms. Our incident analysis has been shared separately.
```

---

## 10. FAILURE SCENARIOS AND DEGRADED SERVICE

### Personnel Shortage Response

**Key personnel unavailable:**
- **Primary on-call engineer unavailable: Automatic escalation to backup list (3 volunteers)**
- **Multiple engineers unavailable: Reduce coverage to business hours only with customer notification**
- **Engineering Manager unavailable: VP Engineering provides consultation**
- **Multiple key people unavailable: Incident response continues with available personnel - customer communication acknowledges reduced capacity**

### Multiple Simultaneous Incidents

**Incident prioritization matrix:**
- **Multiple Sev 1s: Triage by customer count affected, then by revenue impact**
- **>3 Sev 1s: Declare major incident, bring in all available engineers, customer communication explains situation**
- **Cross-vendor incidents: Designate vendor liaison role, maintain internal incident command**

### System Failures

**Communication systems down:**
- **Use personal phone calls for internal coordination**
- **Customer communication via backup channels: Direct email, phone calls to enterprise customers**
- **Regulatory notifications: Continue via backup methods, document communication delays for post-incident review**

---

## 11. IMPLEMENTATION REQUIREMENTS AND SUCCESS CRITERIA

### Pre-Implementation Checklist

**Required before starting:**
- [ ] **6+ engineers committed to on-call participation (5+ after buffer calculation)**
- [ ] **Customer Success Managers designated for enterprise accounts and trained**
- [ ] **Support Team Lead designated for standard accounts and trained**
- [ ] **Monitoring system implemented with 2 weeks baseline data**
- [ ] **Incident tracking system configured with customer tier integration**
- [ ] **Phone numbers and backup contact methods collected for all participants**
- [ ] **SLA calculation system tested with sample data including partial outages**
- [ ] **Customer contract review completed to identify specific timeline requirements**

### Training Requirements

**16-hour training per engineer over 4 weeks covering:**
- **Week 1: System architecture and common failure modes (4 hours)**
- **Week 2: Investigation techniques using actual past incidents (4 hours)**
- **Week 3: Communication procedures with customer context (4 hours)**
- **Week 4: Full incident simulation with realistic complications (4 hours)**

**Ongoing training:**
- **Monthly 1-hour session reviewing recent incidents and new failure patterns**
- **Quarterly simulation exercises with increasing complexity**

**Competency validation:**
- **Successfully lead response to 1 simulated incident with proper communication and escalation**

### Success Metrics (12-month evaluation)

**Process Effectiveness:**
- **Sev 1 response time <30 minutes from detection: >80% of incidents**
- **Customer communication within response time target: >80% of incidents**
- **Post-mortem completion within contract timelines: >90%**

**Operational Sustainability:**
- **On-call rotation coverage: <5% shift gaps**
- **Engineer retention in on-call program: >80% after 12 months**
- **Prevention plan completion: >80% of committed items completed within assigned sprint**

**Customer Impact:**
- **Monthly SLA achievement: 99.95% uptime**
- **Customer escalations due to incident response: <2 per quarter**
- **Customer contract renewals not affected by incident response: >95%**

### Resource Requirements

**Personnel:**
- **6+ engineers for on-call rotation (after 20% buffer)**
- **Named Customer Success Managers with availability for enterprise customers**
- **Engineering Manager available for consultation**
- **VP Engineering available for escalation within 4 hours**

**Budget:**
- **$500/week on-call stipend per engineer**
- **Comp time: 1:1 for incident work >1 hour outside business hours, capped at 16 hours per engineer per month**
- **External monitoring service: ~$50/month**