# Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a scalable notification system for a social app serving 10 million monthly active users. Given the 4-engineer, 6-month constraint, we prioritize pragmatic solutions using managed services while building critical custom logic for user experience optimization.

**Key Design Principles:**
- Leverage managed services to reduce operational overhead
- Build incrementally with clear MVP boundaries
- Design for 100K+ notifications/minute peak capacity
- Ensure 99.9% delivery reliability

## 1. System Architecture Overview

### High-Level Components
```
[Notification Trigger] → [Notification Service] → [Channel Router] → [Delivery Channels]
                                ↓
[User Preferences DB] ← [Batch Processor] → [Analytics & Retry Engine]
```

### Core Infrastructure Stack
- **Message Queue:** Amazon SQS (FIFO for ordering, Standard for volume)
- **Database:** PostgreSQL (primary) + Redis (caching/rate limiting)
- **Container Platform:** AWS ECS Fargate
- **Monitoring:** DataDog
- **CDN/Edge:** CloudFlare for global delivery

**Rationale:** This stack balances reliability with team velocity. Managed services reduce operational burden while providing enterprise-grade reliability.

## 2. Delivery Channels Implementation

### 2.1 Push Notifications
**Primary Service:** Amazon SNS with platform-specific endpoints
- **iOS:** APNs integration
- **Android:** FCM integration
- **Capacity:** 50K/minute sustained, 100K/minute burst
- **Features:** Rich notifications, deep linking, badge counts

```python
class PushNotificationService:
    def __init__(self):
        self.sns_client = boto3.client('sns')
        self.rate_limiter = RedisRateLimiter(max_per_minute=50000)
    
    async def send_push(self, user_id: str, message: dict, priority: Priority):
        if not self.rate_limiter.allow(f"push:{user_id}"):
            return await self.queue_for_retry(message, delay=60)
        
        platform_arn = await self.get_user_platform_arn(user_id)
        return await self.sns_client.publish(
            TargetArn=platform_arn,
            Message=json.dumps(message),
            MessageAttributes=self._build_attributes(priority)
        )
```

### 2.2 Email
**Service:** SendGrid (primary), Amazon SES (backup)
- **Capacity:** 10K/minute sustained
- **Templates:** Transactional (immediate), Digest (batched)
- **Features:** Unsubscribe handling, bounce management

### 2.3 In-App Notifications
**Implementation:** WebSocket + REST API fallback
- **Real-time:** Socket.IO for active users
- **Persistence:** PostgreSQL with 90-day retention
- **Capacity:** 200K concurrent connections

### 2.4 SMS
**Service:** Twilio
- **Usage:** Critical notifications only (security, urgent)
- **Capacity:** 1K/minute (cost-controlled)
- **Geographic:** US/EU initially, expand based on user base

**Channel Priority Rationale:** Push notifications handle 80% of volume (highest engagement), email for digests (better conversion for re-engagement), SMS for critical security events only (cost efficiency).

## 3. Priority and Batching Logic

### 3.1 Priority Levels
```python
class Priority(Enum):
    CRITICAL = 1    # Security, safety issues - immediate
    HIGH = 2        # Direct messages, mentions - <30s
    MEDIUM = 3      # Likes, comments - <5min batched
    LOW = 4         # Weekly digests, suggestions - batched daily

class NotificationBatcher:
    def __init__(self):
        self.batch_windows = {
            Priority.CRITICAL: 0,      # No batching
            Priority.HIGH: 30,         # 30 second window
            Priority.MEDIUM: 300,      # 5 minute window  
            Priority.LOW: 86400        # Daily batching
        }
```

### 3.2 Intelligent Batching Algorithm
- **User Activity Awareness:** No batching for active users (last seen <5 min)
- **Content Aggregation:** "John and 4 others liked your post" vs individual notifications
- **Time Zone Optimization:** Schedule low-priority notifications for user's morning hours

```python
async def should_batch_notification(self, user_id: str, notification: dict) -> bool:
    user_activity = await self.get_user_activity(user_id)
    priority = notification['priority']
    
    if priority == Priority.CRITICAL:
        return False
    
    if user_activity.last_seen < timedelta(minutes=5):
        return False  # User is active, send immediately
    
    return True
```

### 3.3 Rate Limiting Strategy
- **Per-user limits:** Max 20 push/day, 3 email/day, 2 SMS/week
- **Global limits:** Respect channel provider limits
- **Intelligent backoff:** Reduce frequency for users with low engagement

## 4. User Preference Management

### 4.1 Preference Schema
```sql
CREATE TABLE user_notification_preferences (
    user_id UUID PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    
    -- Granular controls
    direct_messages JSONB DEFAULT '{"push": true, "email": true, "sms": false}',
    likes_comments JSONB DEFAULT '{"push": true, "email": false, "sms": false}',
    follower_activity JSONB DEFAULT '{"push": true, "email": true, "sms": false}',
    
    -- Timing preferences
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 4.2 Smart Defaults & Learning
- **Progressive onboarding:** Start with essential notifications only
- **Engagement-based adjustment:** Reduce frequency for users who don't interact
- **A/B testing framework:** Test optimal default settings

### 4.3 Preference API Design
```python
class PreferenceService:
    async def update_preferences(self, user_id: str, preferences: dict):
        # Validate preferences
        validated = self.validate_preferences(preferences)
        
        # Update database
        await self.db.execute(
            "UPDATE user_notification_preferences SET ... WHERE user_id = %s",
            [validated, user_id]
        )
        
        # Invalidate cache
        await self.cache.delete(f"prefs:{user_id}")
        
        # Log for analytics
        self.analytics.track("preferences_updated", user_id, preferences)
```

## 5. Infrastructure Implementation

### 5.1 Core Services Architecture

**Notification Service (2 containers)**
```yaml
# docker-compose.yml excerpt
notification-service:
  image: social-app/notification-service:latest
  environment:
    - DATABASE_URL=postgresql://...
    - REDIS_URL=redis://...
    - SQS_QUEUE_URL=https://sqs...
  resources:
    limits:
      memory: 1GB
      cpu: 0.5
  scale: 2
```

**Message Processing Pipeline:**
1. **Ingestion:** API receives notification requests → SQS Standard Queue
2. **Processing:** ECS tasks process queue → Apply user preferences → Route to channels
3. **Delivery:** Channel-specific services handle actual delivery
4. **Feedback:** Delivery status updates → Analytics pipeline

### 5.2 Database Design
**Primary Tables:**
- `notifications` (50M rows/year estimated)
- `notification_deliveries` (tracking per channel)
- `user_notification_preferences` (10M rows)
- `notification_templates` (configuration)

**Partitioning Strategy:**
```sql
-- Partition notifications by month for efficient cleanup
CREATE TABLE notifications (
    id UUID DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    type VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);
```

### 5.3 Caching Strategy
**Redis Usage:**
- User preferences (TTL: 1 hour)
- Rate limiting counters (TTL: based on limit period)
- User activity status (TTL: 10 minutes)
- Template cache (TTL: 24 hours)

```python
class NotificationCache:
    def __init__(self):
        self.redis = redis.Redis(decode_responses=True)
    
    async def get_user_preferences(self, user_id: str) -> dict:
        cached = await self.redis.get(f"prefs:{user_id}")
        if cached:
            return json.loads(cached)
        
        prefs = await self.db.fetch_preferences(user_id)
        await self.redis.setex(f"prefs:{user_id}", 3600, json.dumps(prefs))
        return prefs
```

## 6. Failure Handling & Reliability

### 6.1 Retry Strategy
**Exponential Backoff with Jitter:**
```python
class RetryHandler:
    MAX_RETRIES = 3
    BASE_DELAY = 1  # seconds
    
    async def retry_with_backoff(self, func, *args, **kwargs):
        for attempt in range(self.MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == self.MAX_RETRIES - 1:
                    await self.send_to_dead_letter_queue(func, args, kwargs, str(e))
                    raise
                
                delay = self.BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(delay)
```

### 6.2 Circuit Breaker Pattern
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
```

### 6.3 Dead Letter Queue Processing
- **SQS DLQ:** Captures permanently failed messages
- **Manual review process:** Daily review of failed notifications
- **Alerting:** PagerDuty integration for critical notification failures

### 6.4 Monitoring & Alerting
**Key Metrics:**
- Delivery success rate per channel (>99% target)
- Processing latency (p95 <30s for HIGH priority)
- Queue depth (alert if >10K messages)
- Error rates by error type

**Alerting Rules:**
```yaml
# Example DataDog monitor
- name: "High notification failure rate"
  query: "avg(last_5m):avg:notification.delivery.failure_rate{*} > 0.05"
  message: "Notification delivery failure rate is above 5%"
  escalation_message: "This is urgent - users aren't receiving notifications"
```

## 7. Implementation Timeline (6 Months)

### Month 1-2: Foundation & MVP
**Sprint 1-2: Core Infrastructure**
- Set up ECS cluster, RDS, Redis
- Implement basic notification service
- Build user preference system
- Push notification integration (iOS/Android)

**Sprint 3-4: Channel Implementation**
- Email integration (SendGrid)
- In-app notification system
- Basic batching logic
- Preference management API

**Deliverable:** MVP supporting push and email with basic user preferences

### Month 3-4: Scale & Intelligence
**Sprint 5-6: Advanced Features**
- SMS integration (Twilio)
- Intelligent batching algorithm
- Rate limiting implementation
- Circuit breaker pattern

**Sprint 7-8: Reliability**
- Comprehensive retry logic
- Dead letter queue processing
- Monitoring and alerting setup
- Load testing and optimization

**Deliverable:** Production-ready system handling 50K notifications/minute

### Month 5-6: Optimization & Launch
**Sprint 9-10: Performance**
- Database optimization and partitioning
- Caching layer optimization
- Multi-region preparation
- A/B testing framework

**Sprint 11-12: Launch Preparation**
- Security audit and fixes
- Documentation and runbooks
- Gradual rollout plan
- Performance monitoring

**Deliverable:** Full-scale system ready for 10M MAU

## 8. Key Tradeoffs & Rationale

### 8.1 Build vs. Buy Decisions
**Chose Managed Services For:**
- **Message queuing (SQS):** Reduces operational overhead vs. Kafka
- **Push delivery (SNS):** Battle-tested reliability vs. custom implementation
- **Email (SendGrid):** Deliverability expertise vs. self-managed SMTP

**Built Custom For:**
- **Batching logic:** Unique business requirements
- **User preferences:** Complex UX requirements
- **Priority management:** App-specific logic

### 8.2 Consistency vs. Performance
**Eventual consistency accepted for:**
- Preference updates (cached with TTL)
- Analytics data
- Non-critical notification delivery

**Strong consistency required for:**
- Rate limiting (Redis)
- Critical security notifications
- User opt-out preferences

### 8.3 Cost vs. Feature Tradeoffs
**Cost-optimized decisions:**
- SMS limited to critical notifications only
- Email limited to 10K/minute (vs. premium plans)
- 90-day notification retention (vs. indefinite)

**Feature investments:**
- Rich push notifications (higher engagement)
- Intelligent batching (better UX)
- Comprehensive preference controls (regulatory compliance)

## 9. Success Metrics & KPIs

### 9.1 Technical Metrics
- **Delivery Success Rate:** >99% for critical, >97% for others
- **Processing Latency:** p95 <30s for HIGH priority, <5min for MEDIUM
- **System Availability:** 99.9% uptime
- **Cost per Notification:** <$0.001 blended average

### 9.2 Business Metrics
- **User Engagement:** 15% increase in DAU through better notifications
- **Opt-out Rate:** <5% monthly churn from notification fatigue
- **Conversion Rate:** 8% CTR on promotional notifications

### 9.3 Operational Metrics
- **Mean Time to Recovery:** <15 minutes for critical issues
- **False Positive Alert Rate:** <10% of alerts
- **Team Velocity:** Maintain 80% planned story completion

This notification system design balances scalability, reliability, and team constraints while providing a foundation for future growth beyond 10M MAU. The phased implementation approach ensures value delivery throughout the 6-month timeline while building toward a robust, production-ready system.