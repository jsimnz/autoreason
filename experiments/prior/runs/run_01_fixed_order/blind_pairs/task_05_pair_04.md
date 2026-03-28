# Blind Evaluation: task_05_pair_04

## Task
Design the incident response process for a B2B SaaS company with 200 enterprise customers, a 99.95% SLA, and a 15-person engineering team split across US and EU timezones. Cover: severity levels and criteria, on-call rotation, escalation paths, communication templates (internal and customer-facing), post-mortem process, and how to handle incidents that span timezone boundaries. The company has had 3 major incidents in the past quarter and customers are losing patience.

---

## Proposal X

# Incident Response Process Design for B2B SaaS Company

## Executive Summary

This comprehensive incident response framework addresses the critical need for improved reliability and customer communication following recent service disruptions. The process balances operational excellence with team sustainability for a 15-person distributed engineering team serving 200 enterprise customers with a 99.95% SLA commitment.

## 1. Severity Levels and Response Targets

### Severity 1 (Critical)
**Response Target:** 30 minutes during business hours, 1 hour outside business hours | **Resolution Target:** 4 hours | **Customer Communication:** Within 1 hour of confirmation

**Criteria:**
- Complete service outage affecting >50% of customers
- Data loss or corruption for any customer
- Security breach or suspected breach
- Payment processing completely down
- Core authentication system failure

**Examples:**
- Database cluster failure
- Primary application servers down
- Data center connectivity loss
- Critical security vulnerability being actively exploited

*Departure from Version A: Extended response time from 15 minutes to 30 minutes during business hours and 1 hour outside business hours. This allows proper assessment before response while maintaining urgency.*

### Severity 2 (High)
**Response Target:** 1 hour during business hours, 2 hours outside business hours | **Resolution Target:** 8 hours | **Customer Communication:** Within 2 hours

**Criteria:**
- Significant feature degradation affecting >25% of customers
- Performance degradation >75% slower than baseline
- Single customer complete outage (enterprise tier)
- Non-core service failure impacting user experience
- Intermittent authentication issues

**Examples:**
- API response times >5 seconds
- Reporting dashboard unavailable
- File upload/download failures
- Search functionality degraded

*Departure from Version A: Adjusted performance threshold from >50% to >75% degradation to focus on truly impactful issues.*

### Severity 3 (Medium)
**Response Target:** 4 hours during business hours, next business day outside hours | **Resolution Target:** 48 hours | **Customer Communication:** As needed

**Criteria:**
- Minor feature issues affecting <25% of customers
- Performance degradation 20-50% slower than baseline
- Non-critical integrations failing
- UI/UX issues not blocking core workflows

**Examples:**
- Email notifications delayed
- Minor UI rendering issues
- Third-party integration intermittent failures
- Non-critical reports showing incorrect data

### Severity 4 (Low)
**Response Target:** Next business day | **Resolution Target:** 72 hours | **Customer Communication:** Via regular support channels

**Criteria:**
- Cosmetic issues
- Documentation problems
- Enhancement requests mistakenly filed as incidents
- Issues affecting <5% of users with available workarounds

### Severity Classification Protocol
All incidents start as Severity 2 until properly assessed by the responding engineer within the first 30 minutes.

*Departure from Version A: Added classification protocol to prevent initial misclassification under pressure.*

## 2. Sustainable On-Call Structure

### Business Hours Coverage
- **US Team (8 engineers):** Monday-Friday 9 AM - 6 PM PST
- **EU Team (7 engineers):** Monday-Friday 9 AM - 6 PM CET
- **Overlap Period:** 1 PM - 3 PM UTC for coordination and handoffs

### After-Hours Coverage
- **Primary On-Call:** Rotating weekly between regions
- **Secondary On-Call:** Always from opposite timezone
- **Maximum Shift:** 12 hours (6 PM - 6 AM local time)
- **Compensation:** Time-off-in-lieu plus on-call stipend

*Departure from Version A: Reduced from 24-hour shifts to 12-hour shifts to ensure legal compliance and engineer sustainability.*

### Rotation Schedule
- **Frequency:** Each engineer on-call approximately every 8 weeks (US: every 8 weeks, EU: every 7 weeks)
- **Coverage Planning:** Designated backup engineers for planned leave
- **Holiday Coverage:** Voluntary overtime shifts with additional compensation

*Departure from Version A: Added explicit coverage planning for vacations and holidays.*

### On-Call Responsibilities
- Acknowledge alerts within response targets
- Perform initial incident triage and severity assessment
- Execute runbooks for common issues
- Document all actions and findings
- Escalate appropriately based on complexity and severity
- Maintain incident communication cadence

## 3. Practical Escalation Framework

### Level 1: On-Call Engineer (First hour)
- Initial response and assessment
- Execute standard runbooks
- Engage secondary on-call if needed during off-hours

### Level 2: Engineering Lead (Business hours available)
**Escalate when:**
- Issue complexity exceeds on-call engineer expertise
- Multiple systems involved requiring coordination
- Estimated resolution time exceeds SLA targets
- Standard runbooks don't resolve the issue

### Level 3: Engineering Manager (Business hours + emergency contact)
**Escalate when:**
- Cross-team coordination required
- Issue duration exceeds 4 hours
- Customer escalation received
- Resource allocation decisions needed

### Executive Notification (Not Escalation)
Engineering Manager notifies VP Engineering and CEO via email/Slack for:
- Incidents lasting >6 hours
- Incidents affecting >50% of customers
- Major customer threatening contract termination
- Potential legal/compliance implications

*Departure from Version A: Changed executive levels from escalation to notification, acknowledging limited executive availability outside business hours.*

## 4. Streamlined Communication Templates

### Internal Communication

#### Initial Alert (Slack #incidents)
```
🚨 INCIDENT ALERT - SEV [X]
Incident ID: INC-YYYY-MMDD-XXX
Impact: [One sentence describing customer experience]
Affected Systems: [list]
Owner: [Engineer name]
Status: [Investigating/Identified/Monitoring/Resolved]
Customer Comms: [Sent/Scheduled for X time/Not needed]
```

*Departure from Version A: Simplified template focusing on essential information while maintaining incident ID tracking.*

#### Status Update (Every 2 hours for Sev 1/2, every 4 hours for Sev 3/4)
```
📊 INCIDENT UPDATE - SEV [X] - [timestamp]
Incident ID: INC-YYYY-MMDD-XXX
Progress: [What we learned/tried]
Next Steps: [Immediate next action]
ETA: [if available]
Customer Update: [When next communication goes out]
```

*Departure from Version A: Reduced update frequency from 30 minutes to 2 hours for Sev 1/2 to prevent communication overload.*

### Customer-Facing Communication

#### Notification Timing
- **Sev 1:** Status page update immediately + targeted emails within 1 hour
- **Sev 2:** Status page update + email to affected customers within 2 hours  
- **Sev 3/4:** Status page update, email only if customers report issues

#### Update Frequency
- **Sev 1:** Every 2 hours until resolved
- **Sev 2:** Every 4 hours or at major milestones
- **Timing Consideration:** Updates sent during customer business hours when possible (avoid 3 AM communications unless critical)

*Departure from Version A: Reduced communication frequency and added business hours timing consideration.*

#### Initial Notification Template
**Subject:** Service Issue Notification - [Date/Time]

Dear [Customer Name],

We're experiencing an issue affecting [specific functionality]. Our engineering team is actively working on a resolution.

**Impact:** [Specific description of what customers are experiencing]
**Affected Features:** [List of impacted functionality]  
**Expected Resolution:** [Time frame or "under investigation"]

We'll update you with our progress in [timeframe]. You can monitor real-time status at: [status page URL]

We apologize for any inconvenience.

Best regards,
[Company] Support Team

*Departure from Version A: Simplified language while maintaining professional tone and essential information.*

## 5. Focused Post-Mortem Process

### Trigger Criteria
- All Severity 1 incidents
- Severity 2 incidents lasting >4 hours
- Any incident causing customer contract discussions
- Incidents revealing new failure modes or novel root causes

*Departure from Version A: Reduced trigger scope to focus on high-impact incidents while maintaining learning from novel issues.*

### Timeline
- **1 week post-resolution:** Engineering lead assigns post-mortem owner
- **2 weeks post-resolution:** Draft completed and reviewed
- **3 weeks post-resolution:** Final version published with action items
- **Monthly review:** Action items progress assessment

*Departure from Version A: Extended timeline from 72 hours to 2 weeks for draft completion to ensure quality over speed.*

### Streamlined Post-Mortem Template

#### Incident Summary
- **Incident ID:** INC-YYYY-MMDD-XXX
- **Date/Time:** [Start and end times with timezones]
- **Duration:** [Total duration]
- **Severity:** [Level and justification]
- **Customer Impact:** [Quantified impact on customers and business]

#### What Happened
Timeline of key events, decisions, and actions taken.

#### Why It Happened  
Root cause analysis focusing on system and process factors, not individual actions.

#### What We're Doing About It
3-5 specific action items with owners and realistic due dates.

#### What Went Well
Positive aspects of the response to reinforce effective practices.

*Departure from Version A: Simplified format while maintaining essential analysis components and blameless culture principles.*

## 6. Timezone Coordination

### Handoff Philosophy
**Preserve Context Over Perfect Handoffs** - Maintain incident ownership continuity when possible rather than forcing timezone-based transfers.

### Handoff Rules
- **Sev 1:** Original engineer continues until resolution or natural break point (not forced at timezone boundary)
- **Sev 2:** Handoff only if incoming engineer can take full ownership with proper context
- **Sev 3/4:** Standard timezone handoff with comprehensive status update

*Departure from Version A: Removed contradictory "never transfer Sev 1" rule that conflicted with sustainable on-call practices.*

### Handoff Documentation Template
```
INCIDENT HANDOFF - [Timestamp]
Incident: INC-YYYY-MMDD-XXX
From: [Outgoing Engineer] ([Timezone])
To: [Incoming Engineer] ([Timezone])

What's broken: [Customer impact description]
What we've tried: [Actions taken and results]
Current theory: [Working hypothesis about root cause]
Next steps: [Specific immediate actions]
Key contacts: [Stakeholders involved]
Customer status: [Last communication sent, next due]
```

*Departure from Version A: Simplified handoff template focusing on essential context transfer while maintaining operational continuity.*

### Cross-Timezone Infrastructure
- **Primary Coordination:** Slack #incidents with timezone context
- **Incident Documentation:** Shared Google Doc with real-time updates
- **Alert Escalation:** Automatic escalation to secondary region after 2 hours during off-hours
- **Status Dashboard:** Live updates visible to both teams

## 7. Implementation Timeline

### Phase 1 (Month 1): Foundation
- Deploy incident management tooling (PagerDuty with smart escalation)
- Establish sustainable on-call rotation with proper coverage planning
- Create communication templates and basic workflows
- Train all engineers on severity classification and escalation procedures

### Phase 2 (Month 2): Process Integration
- Implement customer communication workflows and templates
- Establish post-mortem process with initial incidents
- Create timezone handoff procedures and documentation
- Deploy incident tracking system and shared documentation tools

### Phase 3 (Month 3): Optimization and Metrics
- Refine severity criteria based on actual incident patterns
- Optimize alert tuning to reduce false positives
- Establish incident metrics dashboard and reporting
- Conduct first quarterly process review and adjustment

*Departure from Version A: Extended timeline from 6 weeks to 3 months to ensure sustainable implementation without overwhelming the engineering team.*

### Success Metrics
- **Response Effectiveness:** Percentage of incidents acknowledged within targets
- **Customer Impact Duration:** Time from incident start to customer service restoration
- **Communication Quality:** Time from incident confirmation to customer notification
- **Team Sustainability:** On-call engineer satisfaction and retention metrics
- **Process Improvement:** Reduction in repeat incidents and improved resolution times

*Departure from Version A: Added team sustainability metrics to ensure long-term viability of the process.*

## 8. Tool Requirements and Integration

### Essential Tooling
- **Incident Management:** PagerDuty with intelligent escalation rules
- **Communication:** Slack integration + email automation
- **Documentation:** Google Docs for incident logs with real-time collaboration
- **Tracking:** Linear or similar system for incident lifecycle management
- **Status Page:** Customer-facing real-time status updates

### Integration Philosophy
Maintain simple integrations with manual fallback procedures for tool failures during incidents.

This incident response framework provides comprehensive coverage while ensuring team sustainability and customer satisfaction. The process emphasizes effective problem-solving and clear communication over rigid compliance, enabling your distributed team to maintain service reliability while preventing burnout and operational overhead explosion.

---

## Proposal Y

# Incident Response Process Design for B2B SaaS Company

## Executive Summary

This comprehensive incident response framework addresses the critical need for improved reliability and communication following recent service disruptions. The process is designed to support a 99.95% SLA across 200 enterprise customers with a distributed 15-person engineering team spanning US and EU timezones.

## 1. Severity Levels and Criteria

### Severity 1 (Critical)
**Response Time:** 15 minutes | **Resolution Target:** 2 hours

**Criteria:**
- Complete service outage affecting >50% of customers
- Data loss or corruption for any customer
- Security breach or suspected breach
- Payment processing completely down
- Core authentication system failure

**Examples:**
- Database cluster failure
- Primary application servers down
- Data center connectivity loss
- Critical security vulnerability being actively exploited

### Severity 2 (High)
**Response Time:** 30 minutes | **Resolution Target:** 4 hours

**Criteria:**
- Significant feature degradation affecting >25% of customers
- Performance degradation >50% slower than baseline
- Single customer complete outage (enterprise tier)
- Non-core service failure impacting user experience
- Intermittent authentication issues

**Examples:**
- API response times >5 seconds
- Reporting dashboard unavailable
- File upload/download failures
- Search functionality degraded

### Severity 3 (Medium)
**Response Time:** 2 hours | **Resolution Target:** 24 hours

**Criteria:**
- Minor feature issues affecting <25% of customers
- Performance degradation 20-50% slower than baseline
- Non-critical integrations failing
- UI/UX issues not blocking core workflows

**Examples:**
- Email notifications delayed
- Minor UI rendering issues
- Third-party integration intermittent failures
- Non-critical reports showing incorrect data

### Severity 4 (Low)
**Response Time:** 4 hours | **Resolution Target:** 72 hours

**Criteria:**
- Cosmetic issues
- Documentation problems
- Enhancement requests mistakenly filed as incidents
- Issues affecting <5% of users with available workarounds

## 2. On-Call Rotation Structure

### Primary On-Call Engineer
- **US Shift:** Monday 9 AM PST - Tuesday 9 AM PST (24 hours)
- **EU Shift:** Tuesday 9 AM CET - Wednesday 9 AM CET (24 hours)
- Alternates weekly between US (8 engineers) and EU (7 engineers)

### Secondary On-Call Engineer
- Always from opposite timezone of primary
- Provides 24/7 coverage and escalation support
- Takes over during primary's sleep hours for Sev 1/2 incidents

### On-Call Responsibilities
- Monitor alerts and respond within defined timeframes
- Perform initial incident triage and severity assessment
- Execute runbooks for common issues
- Escalate appropriately based on complexity and severity
- Maintain incident communication cadence

### Rotation Schedule
```
Week 1: Primary US, Secondary EU
Week 2: Primary EU, Secondary US
Week 3: Primary US, Secondary EU
Week 4: Primary EU, Secondary US
```

## 3. Escalation Paths

### Level 1: On-Call Engineer (0-15 minutes)
- Initial response and assessment
- Execute standard runbooks
- Engage secondary on-call if needed

### Level 2: Engineering Lead (15-30 minutes)
**Escalate when:**
- Issue complexity exceeds on-call engineer expertise
- Multiple systems involved
- Estimated resolution time exceeds SLA targets
- Customer escalation received

### Level 3: Engineering Manager + Product Owner (30-45 minutes)
**Escalate when:**
- Cross-team coordination required
- Business impact assessment needed
- Customer communication strategy decisions required
- Resource allocation decisions needed

### Level 4: VP Engineering + Customer Success Director (45-60 minutes)
**Escalate when:**
- Incident affects >75% of customers
- Estimated downtime >4 hours
- Major customer threatening contract termination
- Media/PR implications

### Level 5: CEO/CTO (60+ minutes)
**Escalate when:**
- Company reputation at significant risk
- Legal/compliance implications
- Potential acquisition/partnership impact
- Board-level communication required

## 4. Communication Templates

### Internal Communication Templates

#### Initial Alert (Slack #incidents)
```
🚨 INCIDENT ALERT - SEV [X]
Incident ID: INC-YYYY-MMDD-XXX
Detected: [timestamp]
Impact: [brief description]
Affected Systems: [list]
Incident Commander: [name]
Status Page: [updated/not updated]
Bridge: [conference link if applicable]
```

#### Status Update (Every 30 min for Sev 1/2, hourly for Sev 3/4)
```
📊 INCIDENT UPDATE - SEV [X] - [timestamp]
Incident ID: INC-YYYY-MMDD-XXX
Status: [Investigating/Identified/Monitoring/Resolved]
Progress: [what's been done]
Next Steps: [immediate actions]
ETA: [if available]
Customer Comms: [sent/scheduled/not needed]
```

#### Resolution Notice
```
✅ INCIDENT RESOLVED - SEV [X]
Incident ID: INC-YYYY-MMDD-XXX
Resolved: [timestamp]
Duration: [total time]
Root Cause: [brief summary]
Customer Impact: [description]
Post-Mortem: [scheduled date/not required]
```

### Customer-Facing Communication Templates

#### Initial Notification (Sev 1/2 within 30 minutes)
**Subject:** Service Issue Notification - [Date/Time]

Dear [Customer Name],

We are currently experiencing a service issue that may impact your use of [Product Name]. 

**Impact:** [Specific description of what customers are experiencing]
**Affected Features:** [List of impacted functionality]
**Estimated Resolution:** [Time frame or "investigating"]

Our engineering team is actively working to resolve this issue. We will provide updates every 30 minutes until resolved.

You can monitor real-time status at: [status page URL]

We apologize for any inconvenience and appreciate your patience.

Best regards,
[Company] Support Team

#### Progress Update
**Subject:** Service Issue Update - [Time] - [Date]

Dear [Customer Name],

**Update on Current Service Issue:**

**Current Status:** [Brief description of progress]
**Actions Taken:** [What the team has done]
**Next Steps:** [Immediate planned actions]
**Estimated Resolution:** [Updated timeframe]

We continue to work diligently on resolution and will provide the next update within 30 minutes.

Best regards,
[Company] Support Team

#### Resolution Notice
**Subject:** Service Issue Resolved - [Date/Time]

Dear [Customer Name],

We are pleased to inform you that the service issue reported earlier has been fully resolved as of [time].

**Issue Duration:** [Total time]
**Root Cause:** [High-level explanation]
**Resolution:** [What was done to fix it]
**Prevention:** [Steps being taken to prevent recurrence]

All services are now operating normally. If you continue to experience any issues, please contact our support team immediately.

We sincerely apologize for the disruption to your business operations and appreciate your patience during this incident.

Best regards,
[Company] Leadership Team

## 5. Post-Mortem Process

### Trigger Criteria
- All Severity 1 incidents
- Severity 2 incidents lasting >2 hours
- Any incident causing customer escalation
- Incidents with novel root causes
- Near-misses that could have been Sev 1/2

### Timeline
- **24 hours post-resolution:** Post-mortem owner assigned
- **72 hours post-resolution:** Draft completed
- **1 week post-resolution:** Final version published
- **2 weeks post-resolution:** Action items review

### Post-Mortem Template

#### Incident Summary
- **Incident ID:** INC-YYYY-MMDD-XXX
- **Date/Time:** [Start and end times with timezones]
- **Duration:** [Total duration]
- **Severity:** [Level and justification]
- **Impact:** [Customer and business impact quantified]

#### Timeline
```
[Time] - Initial detection/alert
[Time] - Engineering response began
[Time] - Root cause identified
[Time] - Fix implemented
[Time] - Service restored
[Time] - Monitoring confirmed stability
```

#### Root Cause Analysis
- **Immediate Cause:** [What directly caused the incident]
- **Contributing Factors:** [Conditions that enabled the incident]
- **Root Cause:** [Underlying systemic issue]

#### Response Evaluation
- **What Went Well:** [Positive aspects of response]
- **What Could Be Improved:** [Areas for enhancement]
- **Communication Assessment:** [Internal and external communication effectiveness]

#### Action Items
| Action | Owner | Due Date | Priority | Status |
|--------|--------|----------|----------|---------|
| [Specific action] | [Name] | [Date] | [H/M/L] | [Open/In Progress/Complete] |

### Blameless Culture Guidelines
- Focus on systems and processes, not individuals
- Encourage learning and improvement
- Share lessons learned across the organization
- Celebrate good incident response practices

## 6. Timezone Boundary Incident Handling

### Handoff Protocol

#### Scheduled Handoffs (Daily at 9 AM local time)
1. **15 minutes before handoff:**
   - Outgoing on-call creates handoff summary
   - Reviews any ongoing incidents or potential issues
   - Updates monitoring dashboards

2. **Handoff call (5-10 minutes):**
   - Review system status
   - Discuss any concerns or trends
   - Transfer on-call responsibilities
   - Confirm contact information

#### Emergency Handoffs (During active incidents)
1. **Immediate notification:** Slack DM + phone call to incoming on-call
2. **Incident briefing:** 
   - Current status and actions taken
   - Immediate next steps
   - Key stakeholders involved
   - Customer communication status
3. **Seamless transition:** Incoming engineer joins incident bridge before outgoing leaves

### Follow-the-Sun Coverage Model

#### Incident Ownership Transfer
- **Sev 1:** Never transfer during active response - maintain original IC until resolution
- **Sev 2:** Transfer only at natural break points with explicit handoff
- **Sev 3/4:** Standard handoff process applies

#### Communication Continuity
- All incident updates must include timezone context
- Customer communications maintain consistent voice regardless of responder location
- Internal stakeholders receive updates appropriate to their timezone

### Cross-Timezone Collaboration Tools

#### Required Infrastructure
- **Incident Bridge:** Persistent conference line for each severity 1/2 incident
- **Shared Incident Log:** Real-time collaborative document (Google Docs/Notion)
- **Status Dashboard:** Live updates visible to both teams
- **Alert Routing:** Intelligent escalation based on time and engineer availability

#### Handoff Documentation Template
```
INCIDENT HANDOFF - [Timestamp]
Incident: INC-YYYY-MMDD-XXX
From: [Outgoing Engineer] ([Timezone])
To: [Incoming Engineer] ([Timezone])

STATUS:
- Current severity: [Level]
- Systems affected: [List]
- Customer impact: [Description]
- Actions in progress: [What's happening now]

IMMEDIATE PRIORITIES:
1. [Most urgent task]
2. [Second priority]
3. [Third priority]

CONTEXT:
- Root cause hypothesis: [Current thinking]
- Actions already tried: [What didn't work]
- Key stakeholders: [Who's involved]
- Customer communication: [Last sent, next due]

CONTACTS:
- Incident Commander: [Name/Phone]
- Engineering Lead: [Name/Phone]
- Customer Success: [Name/Phone]
```

## Implementation Timeline

### Week 1-2: Foundation
- Deploy incident management tooling (PagerDuty/Opsgenie)
- Create communication templates and workflows
- Establish on-call rotation schedule
- Set up monitoring and alerting improvements

### Week 3-4: Process Integration
- Train all engineers on new procedures
- Conduct tabletop exercises for each severity level
- Implement post-mortem template and process
- Create customer communication workflows

### Week 5-6: Optimization
- Refine escalation procedures based on initial feedback
- Optimize timezone handoff processes
- Establish metrics and reporting dashboards
- Conduct first formal process review

### Ongoing: Continuous Improvement
- Monthly process review meetings
- Quarterly tabletop exercises
- Semi-annual complete process audit
- Annual disaster recovery testing

This incident response framework provides the structure needed to restore customer confidence while supporting your distributed engineering team's operational excellence. The emphasis on clear communication, defined ownership, and continuous improvement will help prevent the reputation damage that comes with poorly managed incidents.
