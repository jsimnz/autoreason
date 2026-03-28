# Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users with a 4-engineer team over 6 months. The design prioritizes rapid delivery, user experience, and operational simplicity while accommodating future growth to 50M+ MAU.

**Key Design Decisions:**
- Event-driven architecture using Apache Kafka for reliability and scale
- Redis-based batching and rate limiting for cost optimization
- PostgreSQL for user preferences with Redis caching
- Gradual rollout strategy minimizing risk with existing infrastructure

## 1. System Architecture Overview

### Core Components
```
User Action → API Gateway → Notification Service → Channel Handlers → External Services
                ↓              ↓                      ↓
            Event Bus ←→ Batch Processor ←→ Preference Engine
```

**Technology Stack:**
- **Message Queue:** Apache Kafka (proven at scale, team familiar)
- **Cache Layer:** Redis Cluster (sub-ms latency for preferences)
- **Database:** PostgreSQL (ACID compliance for user data)
- **API Gateway:** Existing infrastructure (cost savings)
- **Monitoring:** Prometheus + Grafana (existing tooling)

### Infrastructure Sizing
- **Kafka:** 3 brokers, 6 partitions per topic (handles 100K msg/sec)
- **Redis:** 3-node cluster with replication (99.9% availability)
- **PostgreSQL:** Primary + 2 read replicas (handles 10K queries/sec)
- **Notification Service:** 4 instances behind load balancer

## 2. Delivery Channels Implementation

### Push Notifications
**Provider:** Firebase Cloud Messaging (FCM) + Apple Push Notification (APN)
- **Rationale:** Free tier covers 10M users, mature SDKs
- **Rate Limits:** 1M/minute per project (well above our needs)
- **Implementation:** 
  ```python
  class PushNotificationHandler:
      def __init__(self):
          self.fcm_client = FCMClient()
          self.apn_client = APNClient()
          self.rate_limiter = RateLimiter(10000, 60)  # 10K/min
  ```

### Email Notifications  
**Provider:** SendGrid (primary), Amazon SES (backup)
- **Cost Analysis:** SendGrid: $14.95/month for 50K emails, scales linearly
- **Rate Limits:** 10K emails/hour (sufficient for digest emails)
- **Templates:** Pre-built responsive templates for 5 core notification types

### In-App Notifications
**Implementation:** WebSocket connections with fallback polling
- **Connection Management:** Redis-backed session store
- **Persistence:** PostgreSQL table with 30-day retention
- **Real-time Delivery:** <100ms latency for active users

### SMS Notifications
**Provider:** Twilio (premium notifications only)
- **Cost Constraint:** $0.0075/SMS limits to critical notifications
- **Use Cases:** Security alerts, payment confirmations only
- **Volume Estimate:** <10K SMS/month

## 3. Priority and Batching Logic

### Priority Classification
```python
class NotificationPriority(Enum):
    CRITICAL = 1    # Security, payments - immediate
    HIGH = 2        # Friend requests, mentions - 1min batch
    MEDIUM = 3      # Likes, comments - 5min batch  
    LOW = 4         # Digest emails - hourly batch
```

### Batching Strategy
**Time-based Batching:**
- Critical: No batching (immediate delivery)
- High: 1-minute windows (max 100 notifications/user)
- Medium: 5-minute windows (max 500 notifications/user)
- Low: 1-hour windows (unlimited)

**Implementation:**
```python
class BatchProcessor:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.batch_sizes = {
            Priority.HIGH: (60, 100),    # (seconds, max_count)
            Priority.MEDIUM: (300, 500),
            Priority.LOW: (3600, float('inf'))
        }
    
    def add_to_batch(self, user_id, notification, priority):
        key = f"batch:{priority}:{user_id}:{current_window()}"
        self.redis.lpush(key, notification.serialize())
        self.redis.expire(key, self.batch_sizes[priority][0])
```

### Smart Batching Features
- **Deduplication:** Identical notifications within 1 hour merged
- **Content Summarization:** "John and 5 others liked your post"
- **Channel Optimization:** Push for immediate, email for batched

## 4. User Preference Management

### Preference Schema
```sql
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    channel_preferences JSONB NOT NULL DEFAULT '{}',
    frequency_settings JSONB NOT NULL DEFAULT '{}',
    quiet_hours JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Example data structure
{
  "channels": {
    "push": {"likes": true, "comments": true, "mentions": true},
    "email": {"digest": "weekly", "security": true},
    "sms": {"security": true}
  },
  "frequency": {
    "push_max_per_hour": 10,
    "email_digest_day": "sunday"
  },
  "quiet_hours": {
    "start": "22:00",
    "end": "08:00",
    "timezone": "America/New_York"
  }
}
```

### Caching Strategy
- **Redis Cache:** 30-minute TTL for active user preferences
- **Cache Warming:** Pre-load preferences for users with recent activity
- **Fallback:** Default permissive settings if cache/DB unavailable

### Preference API
```python
class PreferenceManager:
    def should_send(self, user_id: int, notification_type: str, 
                   channel: str) -> bool:
        prefs = self.get_cached_preferences(user_id)
        
        # Check channel enablement
        if not prefs.get('channels', {}).get(channel, {}).get(notification_type, True):
            return False
            
        # Check quiet hours
        if self.is_quiet_hours(user_id, prefs):
            return notification_type in ['security', 'critical']
            
        # Check frequency limits
        return self.check_frequency_limit(user_id, channel, prefs)
```

## 5. Infrastructure Choices & Rationale

### Message Queue: Apache Kafka
**Why Kafka over alternatives:**
- **vs RabbitMQ:** Better throughput (100K+ msg/sec vs 20K)
- **vs AWS SQS:** Cost savings ($2K/month vs $5K at scale)
- **vs Redis Pub/Sub:** Persistence and replay capabilities
- **Team Expertise:** 2 engineers have production Kafka experience

**Configuration:**
- 3 brokers for fault tolerance
- Replication factor: 3
- Retention: 7 days (replay capability for debugging)
- Partitioning: By user_id hash (even load distribution)

### Database: PostgreSQL + Redis
**Why not NoSQL:**
- ACID transactions critical for user preferences
- Complex queries for analytics and debugging
- Team expertise in PostgreSQL optimization
- JSON columns provide NoSQL flexibility where needed

**Scaling Plan:**
- Read replicas for preference lookups
- Connection pooling (PgBouncer)
- Partition large tables by user_id ranges at 25M+ users

### Deployment Strategy
**Phase 1 (Month 1-2):** Core notification service + push notifications
**Phase 2 (Month 3-4):** Email integration + batching logic  
**Phase 3 (Month 5-6):** SMS integration + advanced preferences + monitoring

## 6. Failure Handling & Reliability

### Retry Logic
```python
class RetryHandler:
    def __init__(self):
        self.retry_config = {
            'push': {'max_retries': 3, 'backoff': 'exponential'},
            'email': {'max_retries': 5, 'backoff': 'linear'},
            'sms': {'max_retries': 2, 'backoff': 'exponential'}
        }
    
    def handle_failure(self, notification, channel, error):
        if self.is_permanent_failure(error):
            self.log_and_discard(notification, error)
            return
            
        if notification.retry_count < self.retry_config[channel]['max_retries']:
            delay = self.calculate_backoff(notification.retry_count, channel)
            self.schedule_retry(notification, delay)
        else:
            self.send_to_dlq(notification)
```

### Dead Letter Queue (DLQ)
- **Storage:** Kafka topic with 30-day retention
- **Monitoring:** Alert when DLQ size > 1000 messages
- **Recovery:** Manual replay tool for systematic failures

### Circuit Breaker Pattern
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
```

### Health Monitoring
**SLA Targets:**
- Push notification delivery: 99.5% within 30 seconds
- Email delivery: 99.9% within 5 minutes  
- System uptime: 99.9% (4.3 hours downtime/month)

**Key Metrics:**
- Delivery success rate by channel
- End-to-end latency (p95, p99)
- Queue depth and processing rate
- Error rate by error type

### Disaster Recovery
- **Cross-region Kafka replication** (implemented in Month 4)
- **Database backup strategy:** Point-in-time recovery with 4-hour RTO
- **Preference data backup:** Daily snapshots to S3
- **Runbook:** Automated failover procedures documented

## 7. Resource Allocation & Timeline

### Team Allocation (4 Engineers)
**Engineer 1 (Senior):** Architecture, Kafka setup, deployment pipeline
**Engineer 2 (Mid-level):** Push notification service, mobile integration
**Engineer 3 (Mid-level):** Email/SMS services, external API integrations  
**Engineer 4 (Junior):** Preference management, caching layer, testing

### 6-Month Timeline
**Month 1:**
- Kafka cluster setup and basic notification service
- Push notification MVP with FCM/APN integration
- Basic user preference schema

**Month 2:**
- Batching logic implementation
- In-app notification system
- Monitoring and alerting setup

**Month 3:**
- Email notification service (SendGrid integration)
- Advanced preference management UI
- Load testing and performance optimization

**Month 4:**
- SMS notification service (Twilio integration)
- Circuit breaker and retry logic
- Cross-region disaster recovery setup

**Month 5:**
- Smart batching features (deduplication, summarization)
- Advanced analytics and reporting
- Performance optimization based on production data

**Month 6:**
- Final testing and documentation
- Production rollout to 100% of users
- Post-launch monitoring and bug fixes

### Cost Analysis
**Monthly Operating Costs (at 10M MAU):**
- Kafka cluster (3 m5.large): $450
- Redis cluster (3 m5.large): $450
- PostgreSQL (1 m5.xlarge + 2 replicas): $800
- SendGrid (2M emails): $300
- Twilio SMS (10K messages): $75
- **Total Infrastructure:** ~$2,100/month

**Development Costs:**
- 4 engineers × 6 months × $150K annual = $300K
- Infrastructure setup and testing: $25K
- **Total Project Cost:** $325K

## 8. Key Tradeoffs & Decisions

### Build vs Buy Analysis
**Decision: Build core system, buy delivery services**
- **Rationale:** Control over business logic, cost optimization at scale
- **Alternative Considered:** Twilio SendGrid Email API (estimated $50K/year)
- **Why Rejected:** Limited customization, vendor lock-in concerns

### Consistency vs Performance
**Decision: Eventual consistency for non-critical notifications**
- **Tradeoff:** Some notifications may be delayed during failures
- **Mitigation:** Critical notifications (security) get immediate processing
- **Alternative:** Strong consistency would require 3x infrastructure cost

### Monolith vs Microservices
**Decision: Single notification service with pluggable handlers**
- **Rationale:** 4-engineer team, 6-month timeline favor simplicity
- **Future Migration:** Architecture supports service extraction when team grows

### Data Storage Strategy  
**Decision: PostgreSQL for preferences, Kafka for events, Redis for caching**
- **Alternative Considered:** All-NoSQL with DynamoDB
- **Why Rejected:** Team expertise, complex queries, transaction requirements

## 9. Success Metrics & Monitoring

### Business Metrics
- **Engagement:** 15% increase in daily active users
- **Retention:** 20% improvement in 7-day user retention
- **Revenue:** 10% increase in conversion from notifications

### Technical Metrics
- **Reliability:** 99.5% delivery success rate
- **Performance:** <30 second delivery for push, <5 minute for email
- **Scalability:** Handle 2x traffic spikes without degradation

### Monitoring Dashboard
- Real-time delivery rates by channel
- Queue depths and processing rates
- Error rates with automated alerting
- User preference change patterns

This notification system design provides a robust foundation for 10M MAU with clear scaling paths to 50M+ users. The phased approach minimizes risk while delivering value incrementally, and the technology choices balance proven reliability with team expertise and budget constraints.