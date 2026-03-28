# Blind Evaluation: task_05_pair_01

## Task
Design the incident response process for a B2B SaaS company with 200 enterprise customers, a 99.95% SLA, and a 15-person engineering team split across US and EU timezones. Cover: severity levels and criteria, on-call rotation, escalation paths, communication templates (internal and customer-facing), post-mortem process, and how to handle incidents that span timezone boundaries. The company has had 3 major incidents in the past quarter and customers are losing patience.

---

## Proposal X

# Incident Response Process for B2B SaaS Company
## Comprehensive Implementation Guide

---

## Executive Summary

This incident response process is designed specifically for a B2B SaaS company serving 200 enterprise customers with a 99.95% SLA commitment. Given the recent 3 major incidents and customer patience concerns, this process balances rapid response capabilities with sustainable operations, clear communication, and systematic improvement.

**Key Features:**
- Sustainable 24/7 coverage with realistic but aggressive response times
- Business-impact focused severity classification aligned to SLA commitments
- Efficient communication workflows separating customer and internal communications
- Streamlined post-mortem process with appropriate customer transparency

---

## 1. Incident Severity Levels and Criteria

### Severity 1 (Critical)
**Response Time:** 20 minutes
**Resolution Target:** 4 hours (best effort)
**Criteria:**
- Complete service outage affecting any customers
- Data loss or corruption affecting any customer
- Security breach or suspected breach
- Payment processing failure affecting any customers
- Any issue affecting customers with explicit 99.95% SLA commitments

**Examples:**
- Database cluster failure
- Authentication service down
- Data center outage
- Critical security vulnerability exploitation

*Justification: 20 minutes balances Version A's aggressive 15 minutes (unrealistic) with Version B's conservative 30 minutes. For enterprise SaaS with 99.95% SLA, 20 minutes is achievable with proper tooling while still demonstrating urgency. Added "best effort" language and SLA-specific criteria from Version B to address complexity variations.*

### Severity 2 (High)
**Response Time:** 45 minutes
**Resolution Target:** 8 hours (best effort)
**Criteria:**
- Significant service degradation affecting multiple customers
- Core feature unavailable but workarounds exist
- Performance degradation preventing normal usage
- Integration failures with critical customer systems

**Examples:**
- API response times >10 seconds consistently
- Report generation failures
- Third-party integration outages (Salesforce, etc.)
- Significant UI/UX issues in core workflows

*Justification: 45 minutes splits the difference between Version A's 30 minutes and Version B's 60 minutes, maintaining urgency while being realistic. Removed percentage-based criteria from Version A as they create classification conflicts when customer count varies.*

### Severity 3 (Medium)
**Response Time:** 2 hours (business hours), 4 hours (off-hours)
**Resolution Target:** 24 hours
**Criteria:**
- Minor service disruption affecting limited customers
- Non-critical feature unavailable
- Performance issues not affecting core functionality
- Cosmetic issues in secondary features

### Severity 4 (Low)
**Response Time:** 8 hours (business hours only)
**Resolution Target:** 72 hours
**Criteria:**
- Individual customer issues
- Documentation errors
- Minor cosmetic issues
- Enhancement requests logged as incidents

*Justification: Kept Version A's aggressive timeline for Sev 3/4 during business hours but added Version B's off-hours protection. This maintains customer service levels while preventing engineer burnout.*

---

## 2. On-Call Rotation Structure

### Team Distribution
**Minimum Required:** 18 engineers
- **US Team:** 11 engineers (PST/EST coverage)
- **EU Team:** 7 engineers (CET coverage)

*Justification: Version B's 20-engineer minimum is ideal but may be unrealistic for immediate implementation. 18 engineers allows sustainable 2.5-week rotations with vacation coverage, addressing Version B's sustainability concerns while being more achievable than the original 15.*

### Rotation Schedule

#### Primary On-Call (24/7 Coverage)
- **Rotation Length:** 2 weeks per engineer (with vacation adjustments)
- **US Primary:** Monday 6 AM PST - Friday 6 PM PST + weekend rotation
- **EU Primary:** Monday 6 AM CET - Friday 6 PM CET + weekend rotation

#### Secondary On-Call (Escalation Support)
- **Availability:** Business hours with 45-minute response time for Sev 1/2
- **Rotation Length:** 1 week per engineer
- **Scope:** Technical guidance and escalation support

*Justification: Kept Version A's secondary coverage concept but adopted Version B's realistic response time expectations. 45 minutes balances availability with sustainability.*

### Backup Coverage
- **Backup Primary:** Available within 90 minutes if primary non-responsive
- **Holiday Coverage Pool:** Volunteer rotation for local holidays
- **Emergency Contacts:** Engineering managers for escalation beyond team

*Justification: Added Version B's backup coverage system to address single points of failure while maintaining Version A's comprehensive coverage goals.*

---

## 3. Escalation Paths

### Tier 1: Initial Response (0-20 minutes)
**Responder:** Primary On-Call Engineer
**Actions:**
- Acknowledge incident within 20 minutes
- Assess severity and business impact
- Begin initial investigation
- Notify Secondary On-Call for Sev 1 within 30 minutes

### Tier 2: Technical Escalation (30-60 minutes)
**Triggered by:**
- Sev 1 with no clear resolution path after 45 minutes
- Sev 2 requiring specialized expertise
- Cross-system impact identified

**Responders:**
- Secondary On-Call Engineer
- Relevant Tech Lead (for specialized systems)
- Engineering Manager notification for Sev 1

*Justification: Kept Version A's proactive escalation approach but extended timelines per Version B to be realistic. Added specialized expertise criteria to improve resolution effectiveness.*

### Tier 3: Management Escalation (1-2 hours)
**Triggered by:**
- Sev 1 not resolved within 90 minutes
- Customer executive escalation
- Multiple simultaneous Sev 1 incidents

**Responders:**
- Engineering Manager (decision authority)
- VP of Engineering (for extended Sev 1)
- Customer Success Manager (for customer communication)

*Justification: Kept Version A's management involvement but delayed timing per Version B. Clarified decision authority to address escalation confusion.*

### Cross-Timezone Emergency Protocol
**For Sev 1 incidents during off-hours:**
1. Primary attempts resolution for 60 minutes
2. If unresolved, automated notification to cross-timezone backup
3. Cross-timezone backup provides guidance within 45 minutes
4. Incident ownership transfers only if primary becomes unavailable

*Justification: Combined Version A's comprehensive cross-timezone support with Version B's realistic expectations and clarified ownership transfer rules.*

---

## 4. Communication Framework

### 4.1 Internal Communications

#### Incident Declaration (Slack)
```
🚨 SEV [X] INCIDENT 🚨
ID: INC-YYYYMMDD-XXX
Primary: @engineer-name
Impact: [Brief business impact]
Affected: [Customer scope]
Status: Investigating
War Room: #incident-[ID]
Next Update: [Time]
```

*Justification: Kept Version A's comprehensive initial alert but streamlined format per Version B to reduce overhead while maintaining necessary information.*

#### Status Updates
- **Sev 1:** Every 30 minutes
- **Sev 2:** Every 60 minutes
- **Format:** Brief progress and next steps only

*Justification: More frequent than Version B but less than Version A's 15-minute updates. Balances stakeholder needs with responder focus.*

#### Handoff Process
**Daily Handoffs:**
- Written summary in Slack #incident-handoff
- 10-minute sync call for active incidents only
- Cross-timezone backup notification for Sev 1

*Justification: Kept Version A's structured approach but made synchronous calls conditional per Version B to reduce burden while maintaining quality for critical incidents.*

### 4.2 Customer Communications

#### Customer Notification Strategy
- **Sev 1:** Status page update within 45 minutes, email to affected customers
- **Sev 2:** Status page update within 90 minutes, email if >4 hour duration
- **Update Frequency:** Every 90 minutes for Sev 1, every 3 hours for Sev 2

*Justification: More aggressive than Version B but less than Version A. Customer research shows 90-minute initial notification meets expectations while allowing proper assessment.*

#### Communication Ownership
- **Status Page:** Incident responder updates
- **Customer Emails:** Customer Success team manages
- **Executive Escalations:** Customer Success Manager handles

*Justification: Adopted Version B's separation of concerns to reduce responder burden while maintaining Version A's comprehensive customer coverage.*

#### Customer Communication Templates
*Kept Version A's detailed templates as they provide necessary structure for customer-facing communications, but assigned execution to Customer Success team per Version B's resource optimization.*

---

## 5. Post-Mortem Process

### 5.1 Post-Mortem Requirements
**Mandatory for:**
- All Severity 1 incidents
- Severity 2 incidents >6 hours duration
- Any incident with customer executive escalation

**Optional for:**
- Other Severity 2 incidents (brief lessons learned)
- Near-miss incidents with learning value

*Justification: More selective than Version A but broader than Version B. 6-hour threshold captures significant Sev 2 incidents while avoiding overhead for minor issues.*

### 5.2 Timeline Requirements
- **Owner Assigned:** Within 36 hours of resolution
- **Draft Completed:** Within 4 business days
- **Internal Review:** Within 6 business days
- **Customer Version:** Within 7 business days (when required)
- **Action Items Assigned:** Within 7 business days

*Justification: Faster than Version B but more realistic than Version A. Maintains urgency while allowing proper analysis.*

### 5.3 Post-Mortem Template

*Justification: Used Version A's comprehensive template structure but streamlined sections per Version B to reduce preparation time while maintaining analytical value.*

```markdown
# Post-Mortem: [Incident Title]
**Incident ID:** INC-YYYY-MMDD-XXX
**Date:** [Date]
**Author:** [Name]
**Severity:** [Level]

## Executive Summary
[2-3 sentence summary of incident, impact, and resolution]

## Incident Details
- **Detection:** [When first detected]
- **Start:** [Actual start time]
- **Resolution:** [Service restored]
- **Duration:** [Total time]

## Impact Assessment
- **Customers Affected:** [Count and business scope]
- **Services Impacted:** [List]
- **SLA Impact:** [Against 99.95% target]

## Timeline
| Time (UTC) | Event | Actions |
|------------|-------|---------|
| [Time] | [Event] | [Actions] |

## Root Cause Analysis
### Primary Cause
[Detailed technical explanation]

### Contributing Factors
1. [Factor with explanation]
2. [Factor with explanation]

## Action Items
| Action | Owner | Priority | Due Date |
|--------|-------|----------|----------|
| [Action] | [Name] | [P0/P1/P2] | [Date] |

## Prevention Measures
### Immediate (1 week)
- [Specific measure]

### Short-term (1 month)
- [Specific measure]

### Long-term (1 quarter)
- [Specific measure]
```

#### Customer-Facing Post-Mortem
*Used Version B's streamlined customer template to reduce preparation overhead while maintaining transparency.*

---

## 6. Cross-Timezone Operations

### 6.1 Handoff Strategy

#### Daily Handoffs
**EU to US (6 PM CET / 9 AM PST):**
- Written handoff summary required
- 10-minute sync call for active incidents
- Contact verification for escalations

**US to EU (6 PM PST / 3 AM CET+1):**
- Overnight summary documented
- EU reviews at start of day
- Emergency contacts updated

*Justification: Kept Version A's structured approach but made sync calls conditional per Version B to reduce burden while maintaining quality for active incidents.*

#### Emergency Cross-Timezone Support
**Activation:** Sev 1 with no progress after 60 minutes or primary non-responsive
**Response:** 45-minute response time expectation
**Support:** Guidance and expertise (ownership remains with primary timezone)

*Justification: Combined Version A's comprehensive support with Version B's realistic expectations and clear ownership rules.*

### 6.2 Holiday and Coverage Planning

- **Local holidays:** Volunteer rotation within timezone
- **Major holidays:** Extended response times (30 min for Sev 1)
- **Vacation planning:** 1-week advance notice required
- **Emergency backup:** Engineering Manager contact list

*Justification: Added Version B's realistic holiday planning while maintaining Version A's commitment to coverage.*

---

## 7. Tools and Implementation

### 7.1 Primary Tools
- **Incident Management:** PagerDuty with escalation policies
- **Communication:** Slack with backup email
- **Documentation:** Confluence
- **Status Page:** StatusPage.io

### 7.2 Backup Communication Plan
**Tool failure scenarios:**
1. **Slack outage:** Email distribution + phone tree
2. **PagerDuty outage:** Direct phone alerts + manual escalation
3. **Network issues:** Mobile hotspot requirements for on-call
4. **Complete failure:** Engineering Manager emergency contacts

*Justification: Added Version B's comprehensive backup plan to address tool dependencies that Version A didn't consider.*

---

## 8. Implementation Requirements

### 8.1 Immediate Actions (Weeks 1-2)
- Recruit 3 additional engineers to reach 18-person minimum
- Configure PagerDuty escalation policies
- Train team on severity classifications and response times
- Establish Customer Success communication workflows

### 8.2 Process Validation (Months 1-3)
- Monthly incident simulation exercises
- Response time metrics monitoring
- Customer communication feedback collection
- Process adjustment based on actual incident patterns

### 8.3 Success Metrics
- **Response Time:** 90% of incidents acknowledged within target
- **Resolution:** 75% of Sev 1 incidents resolved within 4 hours
- **Team Sustainability:** <20% annual on-call engineer turnover
- **Customer Satisfaction:** Incident communication >3.8/5.0

*Justification: Set realistic but aggressive targets that balance Version A's customer focus with Version B's sustainability concerns.*

---

This synthesis maintains Version A's comprehensive approach and customer focus while incorporating Version B's critical sustainability and operational reality improvements. Every change from Version A addresses specific operational risks while preserving the high service level required for enterprise SaaS customers.

---

## Proposal Y

# Incident Response Process for B2B SaaS Company
## Complete Implementation Guide

---

## Executive Summary

This incident response process is designed specifically for a B2B SaaS company serving 200 enterprise customers with a 99.95% SLA commitment. Given the recent 3 major incidents and customer patience concerns, this process prioritizes rapid response, clear communication, and systematic improvement.

**Key Features:**
- 24/7 coverage with US/EU timezone handoffs
- 4-tier severity classification aligned to business impact
- Automated escalation and communication workflows
- Structured post-mortem process with customer transparency

---

## 1. Incident Severity Levels and Criteria

### Severity 1 (Critical)
**Response Time:** 15 minutes
**Resolution Target:** 4 hours
**Criteria:**
- Complete service outage affecting >50% of customers
- Data loss or corruption affecting any customer
- Security breach or suspected breach
- Payment processing failure affecting multiple customers

**Examples:**
- Database cluster failure
- Authentication service down
- Data center outage
- Critical security vulnerability exploitation

### Severity 2 (High)
**Response Time:** 30 minutes
**Resolution Target:** 8 hours
**Criteria:**
- Significant service degradation affecting >25% of customers
- Core feature unavailable but workarounds exist
- Performance degradation >50% of normal levels
- Integration failures with critical customer systems

**Examples:**
- API response times >10 seconds
- Report generation failures
- Third-party integration outages (Salesforce, etc.)
- Significant UI/UX issues in core workflows

### Severity 3 (Medium)
**Response Time:** 2 hours
**Resolution Target:** 24 hours
**Criteria:**
- Minor service disruption affecting <25% of customers
- Non-critical feature unavailable
- Performance issues not affecting core functionality
- Cosmetic issues in secondary features

**Examples:**
- Export functionality issues
- Minor UI bugs
- Secondary feature performance issues
- Non-critical notification delays

### Severity 4 (Low)
**Response Time:** 8 hours
**Resolution Target:** 72 hours
**Criteria:**
- Individual customer issues
- Documentation errors
- Minor cosmetic issues
- Enhancement requests logged as incidents

---

## 2. On-Call Rotation Structure

### Team Distribution
**US Team:** 8 engineers (PST/EST coverage)
**EU Team:** 7 engineers (CET coverage)

### Rotation Schedule

#### Primary On-Call (24/7 Coverage)
- **US Primary:** Monday 6 AM PST - Friday 6 PM PST
- **EU Primary:** Monday 6 AM CET - Friday 6 PM CET
- **Weekend Coverage:** Alternating US/EU weekly

#### Secondary On-Call (Escalation Support)
- **US Secondary:** Always available during US business hours
- **EU Secondary:** Always available during EU business hours
- **Cross-timezone Secondary:** Available for Sev 1/2 incidents

### Handoff Process
**Daily Handoffs at:**
- 9 AM CET (EU → US overlap begins)
- 6 PM CET (EU → US full handoff)
- 9 AM PST (US → EU overlap begins)
- 6 PM PST (US → EU preparation)

**Handoff Requirements:**
- 15-minute sync call
- Written summary in Slack #incident-handoff
- Active incident status review
- Escalation contact confirmation

---

## 3. Escalation Paths

### Tier 1: Initial Response (0-15 minutes)
**Responder:** Primary On-Call Engineer
**Actions:**
- Acknowledge incident within 5 minutes
- Assess severity and impact
- Begin initial investigation
- Notify Secondary On-Call if Sev 1/2

### Tier 2: Technical Escalation (15-30 minutes)
**Triggered by:**
- No progress on Sev 1 after 15 minutes
- Primary unable to identify root cause for Sev 2
- Cross-system impact identified

**Responders:**
- Secondary On-Call Engineer
- Relevant Tech Lead (Platform/Frontend/Backend)
- Engineering Manager (for Sev 1)

### Tier 3: Management Escalation (30-60 minutes)
**Triggered by:**
- Sev 1 not resolved within 1 hour
- Sev 2 with customer escalation
- Multiple simultaneous incidents

**Responders:**
- VP of Engineering
- CTO (for extended Sev 1)
- Customer Success Manager
- CEO (for company-threatening incidents)

### Cross-Timezone Escalation Protocol
**For incidents spanning timezone boundaries:**
1. Immediate Slack notification to both timezone channels
2. Emergency phone call to cross-timezone Secondary
3. Mandatory 30-minute overlap during handoff
4. Detailed incident documentation in shared workspace

---

## 4. Communication Templates

### 4.1 Internal Communications

#### Sev 1 Initial Alert (Slack)
```
🚨 SEV 1 INCIDENT DECLARED 🚨
Incident ID: INC-YYYY-MMDD-001
Primary: @engineer-name
Time: [UTC timestamp]
Impact: [Brief description]
Affected: [Customer count/percentage]
Status: Investigating
Next Update: [15 minutes from now]
War Room: #incident-[ID]
```

#### Engineering Manager Notification
```
Subject: SEV [X] Incident - [Brief Description] - INC-[ID]

Incident Details:
- Severity: [Level]
- Start Time: [UTC]
- Impact: [Description]
- Customers Affected: [Number/Percentage]
- Primary Responder: [Name]
- Current Status: [Status]
- ETA for Next Update: [Time]

Actions Required:
- [If escalation needed]
- [Resource allocation needs]

Incident Room: #incident-[ID]
```

#### Cross-Timezone Handoff Template
```
Subject: Incident Handoff - INC-[ID] - [Status]

Incident Summary:
- ID: INC-[ID]
- Severity: [Level]
- Duration: [Time elapsed]
- Current Status: [Status]
- Root Cause: [Known/Suspected/Unknown]

Actions Taken:
1. [Action 1 - Time - Result]
2. [Action 2 - Time - Result]

Next Steps:
1. [Next action - Owner - Timeline]
2. [Follow-up action - Owner - Timeline]

Handoff Confirmation:
- New Primary: [Name - Timezone]
- Briefing Completed: [Yes/No - Time]
- Customer Notifications Sent: [Yes/No - Last sent]

Customer Impact:
- Affected Count: [Number]
- Key Accounts: [List if any]
- Escalations: [Any customer escalations]
```

### 4.2 Customer-Facing Communications

#### Initial Incident Notification
```
Subject: Service Alert - [Brief Description] - [Date]

Dear [Customer Name],

We are currently experiencing [brief description of issue] that may impact your use of [Product Name]. 

Impact: [Specific impact description]
Affected Services: [List of affected services]
Started: [Time in customer's timezone]
Current Status: Our engineering team is actively investigating

We are working to resolve this as quickly as possible and will provide updates every [30 minutes for Sev 1, 1 hour for Sev 2].

For real-time updates, please visit our status page: [URL]

We apologize for any inconvenience and appreciate your patience.

Best regards,
[Company] Support Team

Reference: INC-[ID]
```

#### Progress Update Template
```
Subject: Update - Service Alert - [Brief Description] - [Date]

Dear [Customer Name],

Update on the service issue reported at [time]:

Current Status: [Detailed status]
Progress Made: [What has been accomplished]
Next Steps: [What we're doing next]
Estimated Resolution: [If known, or "continuing to investigate"]

Impact Update: [Any changes to impact]

Next update scheduled for: [Time in customer timezone]

Reference: INC-[ID]
Status Page: [URL]

Best regards,
[Company] Support Team
```

#### Resolution Notification
```
Subject: Resolved - Service Alert - [Brief Description] - [Date]

Dear [Customer Name],

The service issue that began at [start time] has been resolved as of [resolution time].

Resolution Summary:
- Issue: [Brief description]
- Root Cause: [High-level explanation]
- Resolution: [What was done to fix it]
- Total Duration: [Duration]

Preventive Measures:
We are implementing the following measures to prevent recurrence:
1. [Measure 1]
2. [Measure 2]

Post-Mortem: A detailed post-mortem report will be available within 5 business days at [URL] for Enterprise customers.

We sincerely apologize for the disruption and appreciate your patience during this incident.

Best regards,
[Company] Support Team

Reference: INC-[ID]
```

#### Customer Success Escalation Template
```
Subject: Personal Follow-up - Recent Service Issue - [Customer Name]

Dear [Customer Contact],

I wanted to personally follow up on the service issue that affected your account on [date].

Impact to Your Account:
- [Specific impact to their usage]
- [Any data/work affected]
- [Mitigation steps taken]

Your Specific Resolution:
- [Any customer-specific actions taken]
- [Verification steps completed]
- [Additional monitoring implemented]

Next Steps:
1. [Any required customer actions]
2. [Our follow-up commitments]
3. [Escalation path if issues persist]

I'm available for a call to discuss this incident and any concerns you may have. Please let me know a convenient time.

Best regards,
[CSM Name]
[Contact Information]
```

---

## 5. Post-Mortem Process

### 5.1 Post-Mortem Triggers
**Mandatory for:**
- All Severity 1 incidents
- Severity 2 incidents lasting >4 hours
- Any incident with customer escalation
- Incidents affecting >50 enterprise customers

**Optional but Recommended for:**
- Severity 2 incidents with novel root causes
- Near-miss incidents (caught before customer impact)
- Incidents revealing process gaps

### 5.2 Timeline Requirements
- **Post-Mortem Owner Assigned:** Within 24 hours of resolution
- **Draft Completed:** Within 3 business days
- **Internal Review:** Within 5 business days
- **Customer Version Published:** Within 5 business days
- **Action Items Assigned:** Within 7 business days

### 5.3 Post-Mortem Template

#### Internal Post-Mortem Document

```markdown
# Post-Mortem: [Incident Title]
**Incident ID:** INC-YYYY-MMDD-XXX
**Date:** [Date]
**Author:** [Name]
**Reviewers:** [Names]

## Executive Summary
[2-3 sentence summary of what happened, impact, and resolution]

## Incident Details
- **Detection Time:** [When we first knew about it]
- **Start Time:** [When the issue actually began]
- **Resolution Time:** [When service was restored]
- **Total Duration:** [Duration]
- **Severity:** [Level and justification]

## Impact Assessment
- **Customers Affected:** [Number and percentage]
- **Enterprise Customers Affected:** [Specific count]
- **Services Impacted:** [List]
- **SLA Impact:** [Calculation against 99.95% target]
- **Revenue Impact:** [If calculable]

## Timeline
| Time (UTC) | Event | Actions Taken |
|------------|-------|---------------|
| [Time] | [Event] | [Actions] |

## Root Cause Analysis
### Primary Root Cause
[Detailed explanation of the primary cause]

### Contributing Factors
1. [Factor 1 - explanation]
2. [Factor 2 - explanation]

### Why Analysis (5 Whys)
1. Why did [incident] occur? [Answer]
2. Why did [answer 1]? [Answer]
3. Why did [answer 2]? [Answer]
4. Why did [answer 3]? [Answer]
5. Why did [answer 4]? [Answer]

## What Went Well
- [Positive aspect 1]
- [Positive aspect 2]

## What Went Poorly
- [Issue 1]
- [Issue 2]

## Action Items
| Action | Owner | Priority | Due Date | Status |
|--------|-------|----------|----------|--------|
| [Action] | [Name] | [P0/P1/P2] | [Date] | [Status] |

## Prevention Measures
### Immediate (Within 1 week)
- [Measure 1]
- [Measure 2]

### Short-term (Within 1 month)
- [Measure 1]
- [Measure 2]

### Long-term (Within 1 quarter)
- [Measure 1]
- [Measure 2]

## Lessons Learned
1. [Lesson 1]
2. [Lesson 2]
```

#### Customer-Facing Post-Mortem Template

```markdown
# Incident Report: [Customer-Friendly Title]
**Date:** [Date]
**Reference:** INC-[ID]

## What Happened
On [date] at [time], we experienced [brief, non-technical description of the issue] that impacted [description of customer impact].

## Timeline
- **[Time]:** Issue began
- **[Time]:** Issue detected and response initiated
- **[Time]:** Customer notification sent
- **[Time]:** [Key milestone]
- **[Time]:** Service fully restored

## Root Cause
[Customer-appropriate explanation of what caused the issue, avoiding technical jargon]

## Resolution
[What we did to fix the issue]

## Impact
- **Duration:** [Total time]
- **Affected Customers:** [Percentage, not absolute numbers]
- **Services Impacted:** [List]

## Prevention Measures
To prevent this type of incident from recurring, we are implementing:

1. **[Measure 1]** - [Customer-benefit explanation] - *Complete by [date]*
2. **[Measure 2]** - [Customer-benefit explanation] - *Complete by [date]*
3. **[Measure 3]** - [Customer-benefit explanation] - *Complete by [date]*

## Our Commitment
We understand the impact this incident had on your operations. We are committed to:
- Implementing the prevention measures outlined above
- Continuing to invest in our infrastructure reliability
- Maintaining transparent communication during any future incidents

If you have questions about this incident or would like to discuss the impact on your specific account, please contact your Customer Success Manager or reach out to support@[company].com.
```

### 5.4 Post-Mortem Review Process

#### Internal Review (Days 1-3)
1. **Technical Review:** Engineering team validates technical accuracy
2. **Process Review:** Engineering Manager reviews response effectiveness
3. **Communication Review:** Customer Success reviews customer communications
4. **Action Item Review:** Product/Engineering prioritize and assign action items

#### Stakeholder Review (Days 4-5)
1. **Executive Review:** VP Engineering/CTO approve findings and commitments
2. **Customer Success Review:** Finalize customer-facing version
3. **Legal/Compliance Review:** Ensure no regulatory issues (if applicable)

#### Publication and Follow-up
1. **Customer Version Published:** On status page and sent to affected customers
2. **Internal Sharing:** Engineering all-hands discussion
3. **Action Item Tracking:** Weekly reviews until completion
4. **Effectiveness Review:** 30-day follow-up on prevention measures

---

## 6. Cross-Timezone Incident Management

### 6.1 Timezone Coverage Strategy

#### Business Hours Definition
- **US Coverage:** 6 AM PST - 6 PM EST (15 hours)
- **EU Coverage:** 6 AM CET - 6 PM CET (12 hours)
- **Overlap Period:** 9 AM - 12 PM CET / 12 AM - 3 AM PST (3 hours)

#### Handoff Protocols

##### Planned Handoffs (Daily)
**EU to US (6 PM CET / 9 AM PST):**
```
Handoff Checklist:
□ Active incidents reviewed and documented
□ Monitoring alerts status confirmed
□ Customer escalations status updated
□ On-call contact information verified
□ Any pending deployments communicated
□ Infrastructure maintenance windows noted
```

**US to EU (6 PM PST / 3 AM CET+1):**
```
Handoff Checklist:
□ Overnight incidents summary prepared
□ Any customer communications sent logged
□ System status verified and documented
□ Escalation contacts updated for EU hours
□ Any urgent follow-ups documented
□ Infrastructure changes implemented noted
```

##### Emergency Handoffs
**Criteria for Emergency Cross-Timezone Activation:**
-
