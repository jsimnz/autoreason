# Go-to-Market Strategy: Kubernetes Config CLI Tool

## 1. Target Customer

**Primary Segment:** Platform engineers at 100-500 employee companies running 3-8 Kubernetes clusters who spend 1-2 hours daily reviewing configs in pull requests because their deployment volume (5-15 daily) outpaced their manual review capacity but isn't high enough to justify admission controller complexity.

**Pain:** Manual config reviews create deployment bottlenecks when platform engineers must validate resource limits, security contexts, and label compliance across multiple environments. Teams either slow deployments waiting for reviews or accept higher risk during busy periods.

**Budget:** Platform engineering teams at this scale have $15,000-30,000 annual tooling budgets according to Platform Engineering Survey 2023. Individual tools under $3,000 annually typically bypass procurement processes.

**Why Now:** These companies scaled beyond ad-hoc deployments but lack the volume or dedicated platform team to implement admission controllers requiring weeks of policy development and ongoing maintenance.

## 2. Pricing

**Paid Tier:** Professional Plan at $149/month per organization, priced below typical $3,000 annual procurement thresholds while capturing value from eliminating manual review bottlenecks.

**ROI Justification:** Platform engineers reviewing configs spend 90 minutes daily on validation tasks. At $140,000 loaded cost ($67/hour including benefits), manual reviews cost $100 daily. Automated validation eliminates 70% of review time, saving $70 daily ($1,540 monthly), providing 10x ROI versus $149 monthly cost.

## 3. Distribution

**Primary Channel:** Content-driven inbound through technical blog posts on platform engineering forums (Platform Engineering Slack, CNCF community, r/kubernetes) demonstrating specific policy automation workflows that platform engineers recognize as their daily manual tasks.

**Specific Tactics:** Publish weekly technical posts showing "Policy as Code" implementations for common scenarios (resource limits, security contexts, label requirements). Include working code examples using the CLI tool. Target 500 views per post based on typical engagement in platform engineering communities. Convert 2% to tool trials through embedded CLI installation instructions.

## 4. First 6 Months Milestones

**Month 2:** 200 CLI downloads from content marketing
- Success criteria: 200 unique installations with 25% weekly active usage
- Leading indicator: 500 weekly blog post views across platform engineering communities

**Month 4:** $746 Monthly Recurring Revenue
- Success criteria: 5 paying organizations at $149/month
- Leading indicator: 12% conversion from 30-day trial to paid within 45 days

**Month 6:** 15 production deployments using automated validation
- Success criteria: 15 organizations running CLI validation on 100+ configs monthly
- Leading indicator: Average customer validates 150+ configurations per month

## 5. What You Won't Do

**No admission controller features:** Avoid runtime enforcement capabilities since target platform engineers lack time to implement cluster-level policy infrastructure requiring weeks of development and ongoing maintenance overhead.

**No enterprise multi-tenancy:** Skip complex role-based access controls and team isolation features since 100-500 person companies typically have 1-2 platform engineers managing shared infrastructure rather than departmental segregation.

**No custom policy DSL:** Use existing OPA/Rego policies instead of proprietary syntax since platform engineers prefer industry-standard tools that don't create hiring constraints or vendor lock-in risks.

## 6. Biggest Risk

**Risk:** Open Policy Agent (OPA) ecosystem matures with easier-to-deploy admission controller solutions (like Gatekeeper policy templates), making pre-deployment CLI validation obsolete as platform engineers adopt runtime enforcement.

**Mitigation:** Position the tool as complementary to admission controllers for development-time feedback rather than competing with runtime enforcement. Partner with OPA ecosystem by contributing policy templates that work in both CLI and admission controller contexts.

**Metric to Watch:** Monthly downloads of Gatekeeper vs. pre-deployment validation tools on artifact registries—if Gatekeeper adoption accelerates beyond 40% month-over-month growth, pivot to become a Gatekeeper policy development tool rather than standalone validator.

**Word Count: 598 words**