# Notification System Design for Social App (10M MAU)

## Executive Summary

This document presents a comprehensive notification system design for a social application serving 10 million monthly active users (MAU). The system will be delivered by a 4-person backend engineering team within 6 months, focusing on pragmatic scalability, user engagement optimization, and operational reliability.

**Business Impact:**
- Target 15-20% improvement in user engagement through intelligent notification delivery
- Support for 4 delivery channels with smart routing and fallback mechanisms  
- Horizontally scalable architecture supporting growth to 25M MAU within 18 months
- Total system cost: $0.87 per MAU per month at 10M scale

**Key Success Metrics:**
- 99.9% delivery reliability for critical notifications, 99.5% for high priority, 97% for standard
- P99 latency: <500ms critical, <2s high priority, <5s standard, <30s low priority
- 4%+ click-through rate on push notifications (industry benchmark: 2.5-4%)
- <5% unsubscribe rate across all channels
- 75%+ user satisfaction score on notification relevance

---

## 1. Requirements & Scale Analysis

### 1.1 Realistic Scale Calculations

**User Activity Profile:**
```
10M Monthly Active Users (MAU)
├── 3.2M Daily Active Users (32% DAU/MAU ratio - typical for mature social apps)
├── 480K Peak concurrent users (15% of DAU during 7-9pm local time)
├── Average 18 minutes session duration
├── 73% mobile users, 27% web/desktop users
└── Geographic distribution: 40% NA, 30% EU, 20% APAC, 10% Other
```

**Notification Volume Projections:**
```
Based on industry benchmarks for social apps:
- Average notifications per DAU: 4.2/day (conservative estimate)
- Daily notifications: 3.2M DAU × 4.2 = 13.44M/day
- Peak hour: 30% of daily volume in 3-hour evening window
- Peak throughput: (13.44M × 0.30) / (3 × 3600) = 373 notifications/second
- Burst capacity needed: 1,120 notifications/second (3x for viral events)
- Design capacity: 1,500 notifications/second (34% growth buffer)

Channel distribution (based on real-world opt-in rates):
- In-app: 100% coverage, 52% immediate visibility, 78% eventual read
- Push: 58% opt-in rate, 6.2% open rate, 1.8% click-through rate
- Email: 71% opt-in rate, 18% open rate, 2.4% click-through rate  
- SMS: 15% opt-in rate (security + critical only), 94% read rate
```

**Infrastructure Requirements:**
```
Data volumes (with 30-day retention for analytics, 7-day for operational):
├── Notification metadata: ~95GB
├── Content templates: ~18GB
├── Analytics data: ~140GB
├── User preferences: ~8GB
└── Rate limiting cache: ~5GB

Compute requirements:
├── API servers: 4 instances (400 RPS per instance capacity)
├── Worker processes: 6 instances (2 per priority tier)
├── Database: PostgreSQL primary + 2 read replicas
├── Cache: Redis cluster with 3 nodes (16GB each)
└── Queue: Amazon SQS with DLQ and batch processing
```

### 1.2 Functional Requirements

**Core Features (MVP - Months 1-4):**
1. **Multi-channel delivery** with intelligent channel selection and fallback
2. **Four-tier priority system** (Critical, High, Standard, Low) with SLA guarantees
3. **Smart batching and aggregation** with content deduplication
4. **Comprehensive user preference management** with category and channel controls
5. **Real-time delivery tracking** with webhook callbacks
6. **Template system** supporting internationalization (i18n) for 8 languages
7. **Rate limiting** with user-tier based thresholds and burst allowances
8. **A/B testing framework** for content, timing, and channel optimization

**Phase 2 Features (Months 5-6):**
- Machine learning-based send time optimization
- Advanced content personalization using user behavior
- Real-time analytics dashboard with business intelligence
- Advanced compliance features (GDPR, CCPA, CAN-SPAM)

**Non-Functional Requirements:**
- 99.95% uptime for notification API (allowing 4.4 hours downtime/year)
- Support for 500% traffic spikes during viral events or major announcements
- <50ms API response time for preference updates
- <200ms API response time for notification submission
- Multi-region deployment with automated failover
- Full audit trail for compliance requirements

---

## 2. Architecture Design

### 2.1 High-Level System Architecture

```
                    ┌─────────────────────────────────────────┐
                    │          CloudFlare CDN                 │
                    │     Global Load Balancing + DDoS        │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │            AWS ALB                      │
                    │      SSL Termination + Health Checks    │
                    └─────────────────┬───────────────────────┘
                                      │
                    ┌─────────────────▼───────────────────────┐
                    │          API Gateway (Kong)             │
                    │  Rate Limiting + Auth + Request Routing │
                    └─────────────────┬───────────────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
    ┌───────▼──────┐         ┌────────▼────────┐       ┌───────▼──────┐
    │Notification  │         │  User Prefs     │       │  Analytics   │
    │API Service   │         │  Service        │       │  Service     │
    │(4 instances) │         │  (2 instances)  │       │  (2 instances)│
    └───────┬──────┘         └─────────────────┘       └──────────────┘
            │
    ┌───────▼──────────────────────────────────────────┐
    │              Core Processing Engine               │
    ├──────────┬──────────┬──────────┬─────────────────┤
    │Priority  │Channel   │Content   │Rate Limiter &   │
    │Manager   │Router    │Processor │Batch Manager    │
    └──────────┴──────────┴──────────┴─────────────────┘
            │
    ┌───────▼──────────────────────────────────────────┐
    │                 Amazon SQS                       │
    │ ┌─────────┬─────────┬─────────┬─────────────────┐ │
    │ │Critical │High     │Standard │Low Priority     │ │
    │ │Queue    │Priority │Queue    │Batch Queue      │ │
    │ │(FIFO)   │Queue    │         │(1min batching)  │ │
    │ └─────────┴─────────┴─────────┴─────────────────┘ │
    └───────┬──────────────────────────────────────────┘
            │
    ┌───────▼──────────────────────────────────────────┐
    │              Delivery Workers                     │
    │ ┌─────────┬─────────┬─────────┬─────────────────┐ │
    │ │Push     │Email    │In-App   │SMS              │ │
    │ │Worker   │Worker   │Worker   │Worker           │ │
    │ │(2 inst) │(2 inst) │(1 inst) │(1 inst)         │ │
    │ └─────────┴─────────┴─────────┴─────────────────┘ │
    └───────┬──────────────────────────────────────────┘
            │
    ┌───────▼──────────────────────────────────────────┐
    │            External Service Integrations          │
    │ ┌─────────┬─────────┬─────────┬─────────────────┐ │
    │ │FCM/APNS │Amazon   │Redis    │Twilio           │ │
    │ │         │SES      │Pub/Sub  │                 │ │
    │ └─────────┴─────────┴─────────┴─────────────────┘ │
    └──────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────────┐
    │                Data Layer                            │
    ├──────────────┬───────────────────┬───────────────────┤
    │PostgreSQL    │Redis Cluster      │Amazon S3          │
    │Primary +     │(Cache + Sessions  │(Templates +       │
    │2 Read        │+ Rate Limiting)   │Static Assets)     │
    │Replicas      │3 Nodes, 16GB each │                   │
    └──────────────┴───────────────────┴───────────────────┘
```

### 2.2 Technology Stack & Detailed Rationale

**API Layer: Go + Gin Framework**
```
Decision Rationale:
✓ Superior performance: 2000+ RPS per instance vs 500 for Node.js
✓ Lower memory footprint: ~64MB vs ~512MB for Node.js
✓ Built-in concurrency: Goroutines ideal for I/O-heavy notification workloads
✓ Strong typing: Reduces bugs in production, critical for reliability
✓ Excellent JSON performance and HTTP handling
✓ Team learning curve: 2-3 weeks vs immediate productivity
✗ Smaller ecosystem than Node.js for some integrations
✗ Initial development velocity slower

Performance Profile:
- 2,000 RPS per instance sustained
- Memory usage: ~64MB per instance under load
- CPU utilization: ~40% at peak load
- Garbage collection pauses: <1ms
- Development velocity trade-off acceptable for 6-month timeline
```

**Message Queue: Amazon SQS + EventBridge**
```
Hybrid Approach Benefits:
✓ SQS for high-volume notification delivery (proven at scale)
✓ EventBridge for system events and complex routing
✓ Zero operational overhead - critical for 4-person team
✓ Native AWS integration and monitoring
✓ Built-in DLQ and retry mechanisms
✓ FIFO queues for critical notifications
✓ Auto-scaling and cost predictability

SQS Limitations Addressed:
- Multiple queues for different priorities overcome 3K/sec limit
- EventBridge handles complex routing patterns
- Batch processing for cost optimization

Monthly Cost: $2,100 SQS + $450 EventBridge = $2,550
vs $1,200/month for self-managed Kafka + operational overhead
Decision: Managed services - team velocity critical
```

**Database Strategy: PostgreSQL + Redis + S3**
```
PostgreSQL (Primary Store):
├── User preferences and settings (8GB)
├── Notification templates (12GB)
├── Delivery logs (30-day retention: 95GB)
├── System configuration (2GB)
└── Analytics aggregates (140GB)

Configuration:
- Instance: db.r6g.xlarge (4 vCPU, 32GB RAM)
- Read replicas: 2x db.r6g.large for analytics queries
- Backup: Automated daily snapshots, 30-day retention
- Monitoring: CloudWatch + custom dashboards

Redis Cluster (Cache + Real-time Data):
├── Active user sessions (TTL: 24 hours) - 2GB
├── Rate limiting counters (sliding window) - 1GB
├── Template cache (TTL: 4 hours) - 500MB
├── Real-time delivery status (TTL: 2 hours) - 1.5GB
├── Channel routing decisions (TTL: 1 hour) - 500MB
└── A/B test assignments (TTL: 7 days) - 1GB

Configuration:
- 3 nodes: cache.r6g.large (2 vCPU, 16GB each)
- Replication enabled with automatic failover
- Backup: Daily snapshots

Amazon S3 (Static Content):
├── Notification templates and assets
├── Email HTML templates with images
├── Backup storage for logs and analytics
└── Configuration files and deployment artifacts

Monthly Cost: $890 (RDS) + $420 (ElastiCache) + $180 (S3) = $1,490
```

**Container Platform: Amazon ECS with EC2**
```
ECS on EC2 Benefits (vs Fargate):
✓ 40% lower cost than Fargate at our scale
✓ Better resource utilization for consistent workloads
✓ More control over instance types and networking
✓ Still managed container orchestration
✗ Slightly more operational complexity
✗ Need to manage EC2 instances

Configuration:
- Instance types: c6i.xlarge (4 vCPU, 8GB) for API services
- Instance types: m6i.large (2 vCPU, 8GB) for workers
- Auto Scaling Groups with target tracking
- Application Load Balancer with health checks
- Service discovery via AWS Cloud Map

Decision: EC2-based ECS - cost savings justify operational overhead
```

**Monthly Cost Breakdown (10M MAU):**
```
Infrastructure Costs:
├── ECS on EC2 (10 instances): $1,680
├── Application Load Balancer: $25
├── RDS PostgreSQL: $890
├── ElastiCache Redis: $420
├── SQS + EventBridge: $2,550
├── CloudWatch + logging: $280
└── S3 storage: $180
Subtotal: $6,025

Third-Party Services:
├── Amazon SES: $1,340 (67M emails/month at $0.02/1000)
├── FCM: Free (Google's free tier covers our volume)
├── APNS: Free (Apple's free tier covers our volume)
├── Twilio SMS: $2,520 (210K SMS/month at $0.012 each)
├── Kong Enterprise: $300
└── CloudFlare Pro: $240
Subtotal: $4,400

Total: $10,425 = $1.04 per MAU/month
Monitoring, backups, security: $1,275
Development/staging environments: $2,100
Grand Total: $13,800 = $1.38 per MAU/month

Operations overhead (20% buffer): $2,760
Final total: $16,560 = $1.66 per MAU/month
```

---

## 3. Core System Components

### 3.1 Four-Tier Priority Classification

```go
type NotificationPriority string

const (
    CRITICAL NotificationPriority = "CRITICAL" // Security, safety, legal
    HIGH     NotificationPriority = "HIGH"     // Time-sensitive social
    STANDARD NotificationPriority = "STANDARD" // Regular interactions
    LOW      NotificationPriority = "LOW"      // Batch-able content
)

type PriorityConfig struct {
    MaxLatencyMs     int           `json:"max_latency_ms"`
    AllowedChannels  []string      `json:"allowed_channels"`
    BypassQuietHours bool          `json:"bypass_quiet_hours"`
    BypassRateLimit  bool          `json:"bypass_rate_limit"`
    RetryAttempts    int           `json:"retry_attempts"`
    SQSQueue         string        `json:"sqs_queue"`
    RequireAck       bool          `json:"require_ack"`
    BatchingEnabled  bool          `json:"batching_enabled"`
    TTLSeconds       int           `json:"ttl_seconds"`
}

var PriorityConfigs = map[NotificationPriority]PriorityConfig{
    CRITICAL: {
        MaxLatencyMs:     500,
        AllowedChannels:  []