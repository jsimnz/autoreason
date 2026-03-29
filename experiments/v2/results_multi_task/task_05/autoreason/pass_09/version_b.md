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

### Clear Classification with Objective Criteria

**Severity 1 (Critical) - ALL of these conditions must be met:**
**Response Time:** 30 minutes maximum
**Authority:** On-call engineer classifies immediately; no approval required

**Customer Impact Criteria (ALL must be met):**
- Multiple customers affected (not single customer issues)
- Core business functionality unavailable or severely degraded (>50% slower than baseline)
- Customer business operations are blocked (cannot complete primary workflows)
- Issue is confirmed to be on our platform (not customer network/configuration)

**Technical Criteria (ANY qualifies if customer impact confirmed):**
- Primary database completely inaccessible
- Core application servers completely down
- DNS/networking preventing customer access
- Security breach with confirmed unauthorized access or data exposure

*Fixes classification chaos by requiring multiple customers affected and confirmed platform issues, preventing single-customer network problems from triggering emergency response.*

**Severity 2 (High)**
**Response Time:** 2 hours maximum
**Authority:** On-call engineer classifies immediately

**Criteria (ANY qualifies):**
- Single customer completely unable to access service (confirmed platform issue)
- Performance degradation affecting multiple customers (monitoring shows >3x normal response times for >15 minutes)
- Non-core functionality unavailable (reporting, integrations, admin features) affecting multiple customers
- Error rates >5% on customer operations for >30 minutes
- Customer executive escalation with contract implications

*Fixes unmeasurable thresholds by adding time requirements and confirmation criteria.*

**Severity 3 (Medium)**
**Response Time:** Next business day
**Criteria:** All other reported issues, including single customer issues not meeting Sev 2 criteria

### Executive Escalation (Automatic Triggers)

**Engineering Manager Notification (automatic):**
- All Sev 1 incidents (immediate notification)
- Any incident where on-call engineer requests help
- Sev 1 >4 hours: Available for consultation (IC retains command)

**VP Engineering Notification (automatic):**
- Sev 1 incidents lasting >12 hours
- Customer threatens contract termination: Available within 4 business hours

---

## 3. REALISTIC COVERAGE MODEL

### Team Size Assessment and Coverage Math

**Coverage Requirements Analysis:**
- 52 weeks per year requiring coverage
- Average 3 weeks vacation + 1 week sick time = 4 weeks unavailable per person
- Effective coverage weeks per person: 48 weeks
- Engineers needed for weekly rotation: 52 ÷ 48 = **minimum 9 engineers**

**Practical Coverage Options:**

**Option A: 9+ Engineers Available**
- 1-week rotations with backup coverage
- Single timezone primary coverage during business hours
- After-hours: Best effort response within 2 hours

**Option B: 6-8 Engineers Available**
- **Recommendation: 2-week rotations with Engineering Manager participating**
- Engineering Manager takes every 6th rotation as technical IC
- Coverage gaps acknowledged: Some shifts may have delayed response

**Option C: 4-5 Engineers Available**
- **Recommendation: Business hours only coverage with emergency escalation**
- No formal after-hours on-call
- Emergency contact: Engineering Manager reachable within 4 hours for true emergencies
- Customer communication: "Standard business hours support with emergency escalation available"

**Option D: <4 Engineers Available**
- **Recommendation: Delay implementation until team growth**
- Insufficient team size for sustainable rotation

*Fixes coverage math by calculating actual availability and using 2-week rotations to reduce frequency.*

### Scheduled Coverage with Objective Handoff

**Business Hours (08:00-18:00 company primary timezone):**
- 1 engineer primary
- Backup engineer available within 2 hours

**After-Hours (if coverage available):**
- 1 engineer on-call responds within 2 hours for Sev 1, next business day for Sev 2

**Handoff Timing (Objective Criteria):**
- **Scheduled handoffs: Every 12 hours at 08:00 and 20:00 company time**
- **Emergency handoff: When on-call engineer has worked >8 consecutive hours on incidents**
- **Weekend handoffs: Friday 17:00 to Monday 08:00 (single person unless active Sev 1)**

*Fixes subjective handoff by using fixed times and objective hour limits.*

### Sustainable Compensation

**Individual Limits:**
- Maximum 1 rotation per 8 weeks (2-week rotations)
- Maximum 8 consecutive hours active incident response before mandatory handoff
- **Compensation: $200/week on-call stipend + $100/hour for actual incident work >1 hour**
- **Comp time: 1:1 for weekend/holiday work only, requires manager approval within 48 hours**

*Fixes perverse incentives by paying for actual work hours and limiting comp time to weekends/holidays only.*

---

## 4. STREAMLINED ESCALATION AND COMMUNICATION

### Communication Authority with Phone Tree Backup

**Primary Communication Authority:**
**Customer Success Manager** handles all external communication

**Phone Tree for CSM Unavailable:**
1. **VP Engineering (30-minute response required)**
2. **Engineering Manager (1-hour response required)**
3. **If both unavailable: Use holding communication only (template provided)**
4. **On-call engineer provides technical updates to internal team only**

*Fixes communication cascade by requiring response commitments and providing holding communication.*

### Incident Command Structure

**Incident Commander:**
- On-call engineer becomes IC automatically for all incidents
- IC authority: Technical decisions, resource allocation, vendor engagement
- IC handoff: At scheduled handoff times OR after 8 consecutive hours

**Escalation Triggers:**
- IC requests help: Engineering Manager joins as consultant (IC retains command)
- >4 hours Sev 1: Engineering Manager available for consultation
- >12 hours Sev 1: VP Engineering available for consultation

### Vendor Dependency Protocol

**For incidents requiring vendor engagement:**
- **AWS/Infrastructure issues: IC opens support case immediately, escalates to Business/Enterprise support**
- **Database provider issues: IC contacts vendor support, requests Engineering Manager help with vendor relationship**
- **CDN/External service issues: IC implements fallback procedures if available, communicates vendor issue to customers**
- **If vendor ETA >4 hours: Communicate realistic timeline to customers based on vendor response**

*Fixes missing vendor dependency planning by creating specific protocols for common dependencies.*

### Security Incident Communication

**Security incidents require legal consultation but cannot block communication:**
- **Legal counsel contacted immediately with 4-hour response requirement**
- **If legal unavailable after 4 hours: VP Engineering approves generic holding statement**
- **After 8 hours total: VP Engineering authorizes specific communication regardless of legal input**
- **Generic holding statement: "We are investigating a potential security issue and have implemented protective measures. We will provide updates as our investigation progresses."**

*Fixes unrealistic legal timelines by extending to 4 hours and creating automatic progression.*

---

## 5. PRACTICAL COMMUNICATION TEMPLATES

### Issue Detection Strategy

**Monitoring-Based Detection:**
- **Critical alerts: Automatic incident creation for service unavailability, error rates >10%, response times >5x baseline**
- **Warning alerts: Manual assessment required within 30 minutes**
- **Customer reports: Support team escalates if customer reports service unavailable or severely degraded**

*Fixes missing detection strategy by defining specific alert criteria and escalation paths.*

### Customer Communication Templates

#### Initial Response (Within 1 hour of confirmed issue)
**Subject: Service Issue - [Company] Platform**

```
We are investigating a service issue affecting our platform.

Issue detected: [time]
Current status: Investigating
Impact: [If known: specific services] [If unknown: Determining affected services]

We will provide an update within 2 hours.

For urgent issues: [support contact]
Status updates: [status page if available]
```

#### Regular Updates (Every 2 hours maximum)

```
Service Issue Update #[number] - [time]

Current status: [Investigating/Cause identified/Implementing fix/Monitoring]
Services affected: [Specific list]
Customer impact: [What you're experiencing]
[Include ETA only if confident in timeline]

Actions completed since last update:
- [Specific technical steps taken]

Next update by: [Time - maximum 2 hours from now]
```

#### Resolution Communication

```
Service Issue Resolved - [time]

Issue resolved at: [time]
Total duration: [time]
Cause: [Brief technical explanation if determined]

We are completing our full analysis and will share detailed findings within 2 weeks.

Thank you for your patience during this incident.
```

#### Holding Communication (When CSM unavailable)

```
Service Issue Update

We are continuing to work on the service issue reported earlier.
Our technical team is actively investigating and implementing fixes.

Full communication will resume shortly when our customer success team is available.

For urgent technical questions: [engineering manager contact]
```

*Fixes communication failure scenario by providing specific holding template.*

---

## 6. TIMEZONE HANDOFF PROCEDURES

### Structured Handoff Process

**Scheduled Handoffs (08:00 and 20:00 company time):**

```
Handoff Report - [Date/Time]

Active Incidents:
- [Incident ID]: [Status] - [Current IC] - [Next steps]

Recent Activity:
- [Incidents resolved in last 12 hours]
- [Monitoring alerts requiring attention]

Handoff Notes:
- [Any context new IC needs]
- [Vendor tickets open]
- [Customer communications pending]

Handoff Contact: [Phone number for questions next 2 hours]
```

**Active Incident Handoff:**
- **Simple incidents (clear next steps): Written handoff in incident channel**
- **Complex incidents (multiple systems, unclear cause): 10-minute phone call + written summary**
- **Outgoing IC available for questions for 2 hours after handoff**

*Fixes subjective handoff by defining simple vs complex criteria and extending availability window.*

### Cross-Timezone Coverage

**Single Timezone Teams:**
- **Primary timezone coverage: Business hours guaranteed**
- **Secondary timezone: Engineering Manager emergency contact (4-hour response)**
- **Customer communication: "Primary support hours [time zone]. Emergency escalation available outside these hours."**

*Fixes timezone assumptions by explicitly planning for single-timezone teams.*

---

## 7. POST-MORTEM PROCESS

### Realistic Timeline and Process

**Post-Incident Analysis Timeline:**
- **All incidents: Analysis completed within 2 weeks of resolution**
- **Customer communication: Results shared within 2 weeks (business days)**
- **No separate timelines by severity - single consistent process**

*Fixes arbitrary timeline complexity by using single 2-week timeline for everything.*

### Streamlined Review Process

**Post-Mortem Document (Required for Sev 1 and 2):**

```
# [Incident Title] - [Date]

## Customer Impact Summary
- Duration: [start to resolution]
- Services affected: [specific systems]
- Customer experience: [what customers saw]
- Estimated customers affected: [number or percentage]

## Timeline (Key Events Only)
- [Detection time and method]
- [Major investigation steps]
- [Resolution actions]
- [Resolution confirmation]

## Root Cause Analysis
- **Technical cause:** [What broke and why]
- **Detection gap:** [Why wasn't this caught sooner]
- **Response gap:** [What slowed down resolution]

## Action Items
- **Immediate fixes:** [Prevent exact recurrence - owner assigned, target completion within 1 sprint]
- **Monitoring improvements:** [Better detection - owner assigned, target completion within 2 sprints]
- **Process improvements:** [Better response - owner assigned, no specific timeline]
```

**Review Meeting Requirements:**
- **Sev 1: 30-minute review meeting within 1 week**
- **Sev 2: Email review with action item assignments within 1 week**
- **Action items tracked in regular sprint planning - no separate tracking required**

*Fixes bureaucratic overhead by reducing meeting time, eliminating sprint commitment requirements, and using existing planning processes.*

---

## 8. MONITORING AND ALERTING FOUNDATION

### Pre-Implementation Monitoring Requirements

**Minimum monitoring required before implementing this process:**

**Application Monitoring:**
- **Login/authentication success rates (alert if <95% for >5 minutes)**
- **Core API endpoint response times (alert if >3x baseline for >5 minutes)**
- **Database connectivity (alert immediately if connection fails)**
- **Error rates by service (alert if >5% for >5 minutes)**

**Infrastructure Monitoring:**
- **Server availability (alert immediately if unreachable)**
- **External monitoring service (UptimeRobot, Pingdom) monitoring key customer workflows**

**Alert Delivery:**
- **Primary: PagerDuty, VictorOps, or equivalent with phone/SMS**
- **Backup: Email + Slack/Teams notifications**
- **Test monthly: All alert delivery methods**

*Fixes backward monitoring requirements by specifying exact metrics and thresholds needed.*

### Monitoring Failure Response

**Primary monitoring system failure:**
- **Switch to external monitoring only (simplified alerting)**
- **Engineering Manager coordinates manual checks every 4 hours during business hours**
- **Customer reports become primary detection method**
- **Incident communication includes: "We are experiencing monitoring system issues and are using alternative detection methods"**

*Fixes impossible manual monitoring by reducing frequency and acknowledging limitations.*

---

## 9. SLA INTEGRATION AND CREDITS

### SLA Calculation Method

**Downtime Calculation:**
- **Sev 1 incidents: Count full downtime duration**
- **Sev 2 incidents: No automatic SLA impact**
- **Partial outages: Count as full downtime (conservative approach)**

*Fixes arbitrary percentage calculations by using conservative full-downtime counting.*

**Monthly SLA Calculation:**
```
Uptime % = (Total minutes in month - Total Sev 1 downtime minutes) ÷ Total minutes in month
```

**SLA Credit Process:**
- **Monthly uptime <99.95%: Automatic 10% monthly fee credit**
- **Single incident >4 hours: Additional 5% monthly fee credit**
- **Credits calculated automatically, applied to next invoice with explanation**
- **VP Engineering may approve additional credits for exceptional circumstances**

*Fixes undefined credit process by providing specific credit amounts and automatic calculation.*

### SLA Communication

**Monthly SLA reporting:**
```
Monthly Service Report - [Month]

Uptime achieved: [percentage]
SLA target: 99.95%
[If missed]: Service credit applied: [amount and calculation]

Incidents this month:
- [Brief list of Sev 1/2 incidents with duration]

Service improvements implemented:
- [Action items completed from recent incidents]
```

---

## 10. IMPLEMENTATION REQUIREMENTS

### Pre-Implementation Checklist

**Required before starting:**
- [ ] **Minimum 6 engineers committed to rotation with confirmed technical skills**
- [ ] **Customer Success Manager designated and trained on communication process**
- [ ] **Monitoring system functional with external backup**
- [ ] **Phone tree tested with successful contact of all participants**
- [ ] **Incident tracking system configured (Jira, PagerDuty, or shared process)**

*Fixes undefined implementation by specifying skill confirmation requirements.*

### Training Program

**4-hour training program per engineer:**
- **Hour 1: Severity classification with 10 examples from your systems**
- **Hour 2: Communication procedures and escalation paths**
- **Hour 3: System-specific troubleshooting led by senior engineer**
- **Hour 4: 90-minute simulated incident exercise**

**Competency Requirements:**
- **Pass severity classification quiz (4 out of 5 scenarios correct)**
- **Demonstrate escalation procedures during simulation**
- **Complete simulated incident without requiring help on basic procedures**

*Fixes unrealistic training by halving time requirement and focusing on essential skills.*

### Success Metrics (3-month evaluation)

**Response Effectiveness:**
- **Sev 1 response time <30 minutes: >80% of incidents**
- **Customer communication within 1 hour: >90% of incidents**
- **Post-mortem completion within 2 weeks: >90%**

**Operational Sustainability:**
- **Scheduled shift coverage: >95%**
- **On-call rotation compliance: <10% swaps required**
- **Engineer retention: <20% annual turnover**

*Fixes misleading metrics by using retention rate instead of satisfaction surveys and shorter evaluation period.*

**Customer Impact:**
- **Monthly SLA achievement: 99.95