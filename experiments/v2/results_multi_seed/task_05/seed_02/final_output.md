# Practical Incident Response Framework for B2B SaaS Company

## Executive Summary

This framework establishes a sustainable incident response process designed for a 15-person engineering team supporting 200 enterprise customers with a 99.95% SLA commitment. The system addresses current capacity constraints while providing realistic coverage, clear decision authority, and differentiated response based on business impact.

## 1. Business-Aligned Severity Classification

### Severity 1 - Critical Business Impact
**Criteria (ANY ONE triggers Severity 1):**
- Core platform unavailable for >10% of Enterprise tier customers
- Authentication system down preventing customer access
- Data corruption or loss affecting any customer data
- Active security breach with confirmed or suspected data exposure
- Payment processing completely unavailable
- Any issue affecting customers with >$100K ARR

**Business Impact:** High revenue risk, potential SLA breach, executive escalation likely
**Response Time:** 15 minutes acknowledgment
**Resolution Target:** 2 hours (extendable with CTO approval)
**Customer Communication:** Every 30 minutes during business hours, every 2 hours overnight

### Severity 2 - Significant Business Impact  
**Criteria:**
- Core functionality degraded for >25% of any customer tier
- Complete outage for customers representing <$50K total ARR
- Performance degradation >5x normal with no workaround
- Security incident with no confirmed data exposure
- Payment processing partially unavailable

**Business Impact:** Moderate revenue risk, customer satisfaction impact
**Response Time:** 30 minutes acknowledgment
**Resolution Target:** 4 hours
**Customer Communication:** Every 2 hours during business hours

### Severity 3 - Limited Business Impact
**Criteria:**
- Non-core features unavailable with workarounds available
- Performance issues affecting user experience but core functions operational
- Issues affecting <10% of customer base with minimal business impact

**Business Impact:** Low revenue risk, manageable customer impact
**Response Time:** 2 hours acknowledgment
**Resolution Target:** 8 hours during business hours
**Customer Communication:** Once at start, once at resolution

### Severity 4 - Minimal Business Impact
**Criteria:**
- Cosmetic issues, minor bugs with easy workarounds
- Documentation or UI issues
- Enhancement requests

**Business Impact:** No revenue risk
**Response Time:** Next business day
**Resolution Target:** Next sprint
**Customer Communication:** None required

## 2. Realistic Coverage Model for 15-Person Team

### Team Structure
- **On-Call Pool:** 8 engineers (5 US Eastern, 3 EU Central)
- **Engineering Managers:** 2 (1 US, 1 EU) - technical backup only
- **Development Focus:** 5 engineers remain dedicated to feature work
- **CTO:** Final escalation point

### Coverage Schedule

**US Coverage (11 PM CET - 11 AM CET)**
- Primary: 1 US engineer (weekly rotation)
- Secondary: Engineering Manager (US) - 30-minute response for Severity 1 only

**EU Coverage (11 AM CET - 11 PM CET)**
- Primary: 1 EU engineer (weekly rotation)  
- Secondary: Engineering Manager (EU) - 30-minute response for Severity 1 only

**Overlap Period (11 AM - 1 PM CET and 9-11 PM CET)**
- Both regions available for handoffs and high-severity incidents
- Scheduled maintenance and deployments occur during overlap

### Sustainable Rotation
- **Rotation:** 1 week on-call, 7 weeks off (8-person pool)
- **Annual On-Call:** ~6.5 weeks per engineer (12.5% time allocation)
- **Vacation Coverage:** Minimum 2 weeks notice, paid coverage swap or external contractor
- **Sick Day Protocol:** Immediate escalation to Engineering Manager, contractor backup if >24 hours

### External Contractor Backup
- **Provider:** Contracted DevOps firm with 4-hour response SLA
- **Trigger:** Primary and secondary unavailable, or Severity 1 lasting >2 hours
- **Access:** Read-only monitoring access, escalation authority only
- **Cost:** $200/hour, pre-approved monthly budget of $2,000

## 3. Incident Command Structure

### Incident Commander Role
**For Severity 1 and 2 incidents lasting >1 hour:**
- **Role:** Single decision-making authority during incident
- **Assignment:** Engineering Manager becomes IC, primary engineer focuses on technical resolution
- **Authority:** Resource allocation, customer communication approval, vendor engagement
- **Handoff:** IC role transfers between Engineering Managers during timezone changes

### Escalation Authority Matrix

**Level 1: Primary On-Call Engineer**
- **Authority:** Standard fixes, service restarts, known workarounds, Severity 3/4 customer communication
- **Duration Limit:** 1 hour for Severity 1/2 before automatic escalation
- **Decision:** Technical troubleshooting approach only

**Level 2: Engineering Manager (Incident Commander)**
- **Authority:** Multi-engineer coordination, Severity 1/2 customer communication, vendor engagement
- **Escalation Trigger:** Severity 1 >1 hour OR any customer executive contact OR security incident
- **Decision:** Resource allocation, timeline estimates, customer communication strategy

**Level 3: CTO**
- **Authority:** Public statements, SLA credits, architectural decisions, legal/compliance coordination
- **Auto-Escalation:** Severity 1 >2 hours OR security incident OR customer CEO contact
- **Decision:** Business continuity, external communication, emergency spending authorization

### Security Incident Protocol
**Immediate Actions (within 15 minutes):**
1. CTO notification (regardless of time)
2. Affected systems isolated (not restored)
3. Incident Commander assigned
4. Legal counsel notification initiated
5. Evidence preservation procedures activated

**No customer communication until legal review completed** (maximum 2 hours)

## 4. Realistic SLA and Incident Budgeting

### Mathematical SLA Alignment
- **99.95% monthly uptime = 21.6 minutes downtime allowance**
- **Incident Budget Allocation:**
  - Planned maintenance: 10 minutes (46% of budget)
  - Unplanned incidents: 11.6 minutes (54% of budget)
  - Emergency buffer: Reserve 20% monthly (4.3 minutes)

### Incident Time Budgeting
- **Target:** Maximum 1 Severity 1 incident per month at 1.5 hours average
- **Severity 2 Budget:** 6 minutes monthly (multiple smaller incidents)
- **SLA Breach Protocol:** CTO approval required for any incident projected to exceed remaining monthly budget

### SLA Credit Framework
- **Automatic Credits:** Any month exceeding 99.95% uptime
- **Credit Calculation:** Pro-rated based on actual downtime vs. SLA commitment
- **Approval Authority:** CTO for all credits >$1,000, Engineering Manager for smaller credits

## 5. Timezone-Aware Incident Management

### Smart Handoff Protocol

**Scheduled Handoff Times:**
- **EU to US:** 9 PM CET (3 PM EST) - during US business hours
- **US to EU:** 9 AM CET (3 AM EST) - during EU early hours

**Flexible Handoff Rules:**
- **No Active Incidents:** Standard Slack handoff with system status
- **Active Severity 3/4:** Standard handoff, incoming engineer takes over
- **Active Severity 1/2:** Outgoing engineer remains on call until natural break point or resolution
- **Handoff During Crisis:** Engineering Manager coordinates, both engineers remain engaged

**Critical Incident Continuity:**
For Severity 1 incidents crossing timezone boundaries:
1. Outgoing engineer provides 15-minute detailed briefing (voice + written)
2. Outgoing engineer remains available for 2 hours post-handoff (paid overtime)
3. Engineering Manager from incoming timezone takes Incident Commander role
4. Customer communication continues uninterrupted with timezone-appropriate timing

### Handoff Documentation

**Standard Handoff:**
```
🔄 SHIFT HANDOFF - [Date] [Outgoing TZ] → [Incoming TZ]

SYSTEM STATUS: [Green/Yellow/Red] - [Brief description]
MONITORING ALERTS: [Any active alerts or patterns]
CUSTOMER ISSUES: [Open support escalations]
SCHEDULED WORK: [Any planned activities next 12 hours]

Handoff confirmed: [Timestamp] [Incoming engineer acknowledgment]
```

**Active Incident Handoff:**
```
🚨 INCIDENT HANDOFF - [Severity] [ID] - [Duration]

CURRENT STATUS:
Impact: [Customer-facing impact description]
Working theory: [Current hypothesis]
Next critical step: [Specific action with timeline]

ACTIONS COMPLETED:
[Timestamp] [Action] [Result]
[Most recent 3-5 actions]

CUSTOMER COMMUNICATION:
Last update: [Time sent] [Summary]
Next update due: [Time] [Who responsible]
Escalations: [Any customer/executive contacts]

RESOURCES ENGAGED:
Additional engineers: [Names and roles]
External vendors: [Any engaged]
Management: [Who is aware]

HANDOFF METHOD: [Voice call completed] [Written summary confirmed]
CONTINUATION PLAN: [Outgoing engineer availability]
```

## 6. Customer-Centric Communication Strategy

### Communication Ownership and Approval
- **Content Creation:** Incident Commander writes all customer communications
- **Approval Chain:** Engineering Manager approves all external communications
- **Distribution:** Customer Success team sends approved messages
- **Timing Coordination:** Communications sent in customer business hours when possible

### Enhanced Communication Templates

#### Severity 1 Initial Notification
```
Subject: [URGENT] Service Impact Notification - [Customer-Friendly Description]

We are experiencing a service issue affecting [specific functionality] that began at [time in customer timezone].

IMMEDIATE IMPACT TO YOUR ACCOUNT:
• [Specific features unavailable to this customer]
• [Workarounds available, if any]
• [Data safety confirmation]

OUR RESPONSE:
• Senior engineering team actively investigating
• Incident Commander: [Name and role]
• Next update: [Specific time in customer timezone]
• Real-time status: [URL]

URGENT SUPPORT: [Direct phone number and email for this incident]

We sincerely apologize for this disruption and are working to resolve this as quickly as possible.

[Customer Success Manager Name]
Reference ID: [Incident ID]
```

#### Resolution with Accountability
```
Subject: [RESOLVED] Service Issue - [Brief Description]

The service issue affecting [functionality] has been fully resolved as of [time in customer timezone].

INCIDENT SUMMARY:
• Total impact duration: [X hours Y minutes]
• Root cause: [Customer-friendly technical explanation]
• Your data: [Confirmation of data integrity]

OUR ACCOUNTABILITY:
• This incident was caused by [honest explanation]
• We take full responsibility for the impact to your business
• Detailed analysis will be provided within 48 hours

PREVENTION MEASURES:
• [Specific technical improvement with completion date]
• [Process change with owner and timeline]

If this incident impacted your business operations, please contact your Customer Success Manager to discuss appropriate remediation.

Thank you for your patience during this incident.

[Customer Success Manager Name]
```

### Communication Timing Matrix
- **Severity 1 Initial:** Within 30 minutes of detection
- **Severity 1 Updates:** Every 30 minutes during customer business hours, every 2 hours overnight
- **Severity 2 Initial:** Within 1 hour of detection
- **Severity 2 Updates:** Every 2 hours during customer business hours
- **All Severities:** Resolution notice within 15 minutes of resolution

## 7. Efficient Post-Mortem Process

### Post-Mortem Requirements
**Mandatory:**
- All Severity 1 incidents
- Any Severity 2 lasting >2 hours
- Any incident with customer executive escalation
- Any security incident
- Customer-requested analysis (any severity)

**Optional but Recommended:**
- Severity 2 incidents with interesting technical lessons
- Near-miss incidents that could have been Severity 1

### Realistic Timeline
- **4 hours post-resolution:** Initial internal timeline and action items identified
- **24 hours:** Internal post-mortem completed
- **48 hours:** Customer-facing summary available for affected enterprise customers
- **1 week:** All action items assigned with owners and due dates

### Streamlined Post-Mortem Template

#### Internal Post-Mortem (Engineering Focus)
1. **Executive Summary** (2-3 sentences)
   - What broke, how long, customer impact, root cause

2. **Timeline** (Key events only)
   - Detection method and time
   - Major investigation steps
   - Resolution actions
   - Customer communication sent

3. **Root Cause**
   - Technical root cause
   - Why existing monitoring didn't catch it
   - Process gaps that contributed

4. **Action Items** (Maximum 5)
   - High-impact prevention measures only
   - Specific owners and realistic due dates
   - Success criteria defined

#### Customer-Facing Summary (Business Focus)
```
INCIDENT ANALYSIS - [Date] - [Brief Description]

WHAT HAPPENED:
[Customer-friendly explanation of the technical issue and business impact]

DURATION AND IMPACT:
• Total time: [X hours]  
• Functionality affected: [Specific to customer]
• Data impact: [Confirmation of data safety]

ROOT CAUSE:
[Honest, understandable explanation without excessive technical detail]

PREVENTION MEASURES:
• [Specific improvement #1] - Complete by [date]
• [Specific improvement #2] - Complete by [date]  
• [Process improvement] - Effective immediately

We take full responsibility for this incident. If you experienced business impact, please contact [Customer Success Manager] to discuss appropriate remediation.

Engineering Leadership Team
```

## 8. Success Metrics and Continuous Improvement

### Primary Metrics (Monthly Review)
- **SLA Compliance:** Actual uptime vs. 99.95% target
- **MTTA:** Mean time to acknowledge (target: <15 min Severity 1, <30 min Severity 2)
- **MTTR:** Mean time to resolution (target: <2 hours Severity 1, <4 hours Severity 2)
- **Customer Impact:** Number of customers affected by unplanned downtime
- **Escalation Rate:** Percentage of incidents requiring CTO involvement

### Secondary Metrics (Quarterly Review)
- **Engineer Wellness:** On-call satisfaction survey and rotation feedback
- **Post-Mortem Effectiveness:** Action item completion rate and repeat incident analysis
- **Customer Satisfaction:** Post-incident feedback from affected enterprise customers
- **Communication Quality:** Customer feedback on incident communication timeliness and clarity

### Continuous Improvement Process
- **Weekly:** Engineering Manager reviews all incidents for immediate process improvements
- **Monthly:** Full team retrospective on incident trends and response effectiveness  
- **Quarterly:** CTO review of metrics with action plan for systemic improvements
- **Annually:** Complete framework review with customer feedback integration

### Resource Planning
- **On-Call Compensation:** $500/week on-call stipend + overtime for extended incidents
- **Contractor Budget:** $2,000/month for backup coverage
- **Training Budget:** $5,000/year for incident response and reliability training
- **Tool Budget:** $10,000/year for monitoring and incident management platform improvements

This framework provides a mathematically sound, operationally realistic foundation that can maintain your 99.95% SLA commitment while supporting sustainable team practices and clear customer accountability.