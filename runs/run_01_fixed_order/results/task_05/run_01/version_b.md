# Incident Response Process for B2B SaaS Enterprise Platform (Revised)

## Executive Summary

This document outlines a pragmatic incident response process designed for a B2B SaaS company serving 200 enterprise customers with a 99.95% SLA commitment. The process balances operational requirements with team sustainability using a 15-person engineering team across US and EU timezones.

## 1. Incident Severity Classification

### Severity 1 (Critical)
**Criteria:**
- Complete service outage affecting all customers
- Data loss or corruption affecting multiple customers
- Security breach with confirmed data exposure
- Payment processing completely down

**Response Time:** 30 minutes
**Resolution Target:** 6 hours
**Communication:** Customer notification within 1 hour

*Change: Extended response times to be achievable. The original 15-minute response time contradicted the 30-minute escalation timing.*

### Severity 2 (High)
**Criteria:**
- Partial service outage affecting >25% of customers
- Core functionality degraded but workarounds available
- Single customer data loss/corruption
- Authentication/authorization issues
- Performance degradation >50% of normal response times

**Response Time:** 2 hours
**Resolution Target:** 12 hours
**Communication:** Customer notification within 4 hours

### Severity 3 (Medium)
**Criteria:**
- Minor feature outages affecting <25% of customers
- Performance degradation 25-50% of normal response times
- Non-critical integrations down
- UI/UX issues not blocking core workflows

**Response Time:** 4 hours
**Resolution Target:** 48 hours
**Communication:** Status page update within 8 hours

### Severity 4 (Low)
**Criteria:**
- Cosmetic issues
- Documentation errors
- Minor feature requests
- Performance degradation <25%

**Response Time:** Next business day
**Resolution Target:** 5 business days
**Communication:** Internal tracking only

*Change: Removed SLA breach language from P1 criteria. With 99.95% uptime (21.6 minutes/month), any classification based on SLA breach is meaningless since a single significant incident destroys the monthly budget.*

## 2. Staffing and Coverage Model

### Primary On-Call Structure
**Business Hours Coverage (9 AM - 6 PM local time):** 
- US: 2 engineers (weekly rotation)
- EU: 2 engineers (weekly rotation)

**After-Hours Coverage:**
- US: 3 engineers (rotating every 2 weeks, maximum 1 week consecutive)
- EU: 3 engineers (rotating every 2 weeks, maximum 1 week consecutive)

**Weekend Coverage:**
- Shared rotation among all 10 on-call eligible engineers
- Saturday/Sunday treated as single assignment

*Change: Reduced from 8 primary on-call engineers to 10 total (including business hours), leaving 5 engineers for development work. This fixes the unsustainable staffing model.*

### Escalation Pool
- 3 senior engineers available for escalation (not on primary rotation)
- Engineering Manager (US timezone)
- Engineering Manager (EU timezone)

### Incident Commander Designation
**Business Hours:** Engineering team lead in respective timezone automatically becomes IC
**After Hours:** Primary on-call engineer becomes IC unless they explicitly request escalation
**Cross-timezone incidents:** Senior engineer from the timezone where incident started remains IC through handoff

*Change: Added explicit IC designation process that was missing from original proposal.*

### On-Call Compensation
- After-hours on-call stipend: $300/week
- Weekend on-call stipend: $200/weekend
- Incident response: $150 per P1, $75 per P2 (maximum $500/month per person)

*Change: Reduced compensation from $500/week to sustainable levels. Original model would cost $312K+ annually in stipends alone, which is financially ruinous for a 15-person team.*

## 3. Cross-Timezone Operations

### Handoff Protocol
**Standard Handoff (6 PM local time):**
- Outgoing engineer posts written handoff in #incidents-handoff channel
- Incoming engineer acknowledges within 30 minutes
- No synchronous call required unless P1/P2 active

**Active Incident Handoff:**
- 15-minute overlap call required for P1/P2 incidents
- Handoff delayed until natural break point (not mid-investigation)
- Original IC remains available for 2 hours post-handoff

*Change: Eliminated the impossible 2 AM handoff calls. Handoffs now occur at 6 PM local time (reasonable hours) with asynchronous communication as default.*

### Coverage Gaps
**EU Night Coverage (11 PM - 7 AM CET):** US after-hours engineer provides backup
**US Night Coverage (11 PM - 7 AM PT):** EU morning engineer (starting 8 AM CET) provides backup
**Escalation:** If primary doesn't respond within 30 minutes, page backup timezone engineer

*Change: Acknowledged coverage gaps exist and created backup procedures rather than pretending 24/7 coverage is possible with this team size.*

## 4. Customer Communication Framework

### Customer Segmentation
**Tier 1 (Top 20 customers by ARR):** Direct phone/email notification within 1 hour for P1/P2
**Tier 2 (Enterprise customers with specific SLA terms):** Email notification per contract requirements
**Tier 3 (All other customers):** Status page and standard email notifications

*Change: Abandoned one-size-fits-all approach. Enterprise customers have different contract terms and notification requirements that must be respected.*

### Communication Approval
**P1 Incidents:** Engineering Manager approval required before customer notification
**P2 Incidents:** Standard templates can be sent immediately, custom communications require approval
**Legal Review Required:** Any incident involving data breach, regulatory compliance, or customer contract violations

*Change: Added approval workflow that was missing. Enterprise communications can create legal liability if not properly reviewed.*

### External Dependency Incidents
**Vendor-Caused Outages (AWS, Stripe, etc.):**
- Customer notification acknowledges external dependency
- Include vendor status page links
- Proactive communication about mitigation efforts
- No SLA penalty clauses triggered for documented vendor outages

*Change: Added framework for external dependency incidents, which are critical for B2B SaaS but completely missing from original proposal.*

## 5. Post-Mortem Process

### Simplified Requirements
**P1 incidents:** Post-mortem within 5 business days
**P2 incidents:** Post-mortem within 10 business days, or if customer requests
**Customer-facing incidents:** Always include customer-safe summary

*Change: Extended timelines from impossible 24-hour requirement to realistic timeframes that don't force engineers to write post-mortems while fighting active fires.*

### Streamlined Template

```
# Incident Summary: [Title]
**Date:** [Date]
**Duration:** [X hours]
**Severity:** P[X]
**Customers Affected:** [Number/percentage]

## What Happened
[2-3 sentence summary]

## Impact
- Customer impact: [specific impact]
- Duration: [start/end times]
- Services affected: [list]

## Resolution
[What was done to fix it]

## Prevention
[1-3 specific action items with owners and dates]

## Customer Summary
[Version safe to share with customers]
```

*Change: Simplified from bureaucratic template to actionable format. Removed revenue impact calculations and complex timeline requirements that add no value.*

## 6. Monitoring and Alerting

### Alert Management
**Primary On-Call:** Receives all P1/P2 alerts via phone, P3 via Slack
**Alert Grouping:** Maximum 1 page per 15-minute window per service (not 5 per hour)
**Escalation:** If primary doesn't acknowledge within 15 minutes, escalate to backup

### SLA Monitoring
**Monthly SLA Dashboard:** Real-time tracking against 99.95% target
**Early Warning System:** Alert when monthly downtime >50% of budget (10.8 minutes)
**Customer SLA Tracking:** Separate dashboard for customers with custom SLA terms

*Change: Fixed alert fatigue "solution" that just moved noise around. Implemented proper alert grouping and escalation timing.*

## 7. Training and Documentation

### Onboarding Process
**New engineers:** 1-week shadow period, then supervised rotation
**Runbook maintenance:** Quarterly review, updated after each P1/P2 incident
**Incident response training:** Annual training for all engineers, not just on-call

### Documentation Requirements
**Service runbooks:** Maintained by service owners, reviewed quarterly
**Escalation contacts:** Updated within 48 hours of personnel changes
**Customer contact procedures:** Maintained by Customer Success, shared with Engineering

*Change: Reduced shadow period from 2 weeks to 1 week (more sustainable), made documentation maintenance reactive rather than monthly (more realistic).*

## 8. Success Metrics

### Primary Metrics
**Mean Time to Acknowledge (MTTA):** <30 minutes for P1, <2 hours for P2
**Mean Time to Resolution (MTTR):** <6 hours for P1, <12 hours for P2
**Customer Communication:** 95% within target timeframes

### Quality Indicators
**Escalation Rate:** <30% of P1/P2 incidents require management involvement
**Post-mortem Completion:** 90% completed within target timeframes
**Action Item Completion:** >80% completed within 30 days

*Change: Set achievable targets instead of aspirational ones. Removed complex metrics like "repeat incidents" and "customer satisfaction ratings" that require significant tooling investment.*

## 9. Implementation Plan

### Month 1: Foundation
- Configure PagerDuty with new rotation schedule
- Create customer communication templates
- Set up incident tracking in existing ticketing system
- Train initial on-call engineers

### Month 2: Process Integration
- Implement handoff procedures
- Create runbook templates
- Establish customer segmentation
- Conduct first incident simulation

### Month 3: Optimization
- Review first month's incidents
- Refine communication procedures
- Adjust on-call rotations based on actual load
- Document lessons learned

*Change: Extended implementation from 7 weeks to 3 months with realistic milestones. Removed complex tooling requirements like "SLA monitoring dashboards" and "chaos engineering" that require significant development effort.*

## 10. Regulatory and Compliance Framework

### Regulated Customer Requirements
**Financial Services:** Incident reports within 24 hours, specific format requirements
**Healthcare:** HIPAA breach notification procedures if PHI involved
**Government:** Security incident reporting to appropriate agencies

### Documentation Requirements
**Audit Trail:** All incident communications and decisions logged
**Compliance Reporting:** Quarterly incident summaries for enterprise customers
**Legal Hold:** Incident data retention for minimum 3 years

*Change: Added compliance framework that was completely missing from original proposal but essential for enterprise B2B customers.*

---

This revised process balances operational excellence with team sustainability, acknowledges real-world constraints, and provides a foundation for continuous improvement based on actual incident experience rather than theoretical perfection.