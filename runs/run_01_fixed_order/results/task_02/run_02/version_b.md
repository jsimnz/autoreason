# Notification System Design for Social App (10M MAU) - REVISED

## Executive Summary

This proposal outlines a scalable notification system for a social app serving 10 million monthly active users. Given the 4-engineer, 6-month constraint, we focus on a simplified architecture using proven patterns while building only essential custom logic.

**Key Design Principles:**
- Minimize technology stack complexity for 4-person team
- Build for realistic scale: 50K notifications/minute sustained
- Accept eventual consistency for better performance
- Design for operational simplicity over feature richness

**Revised Scope:** Core push notifications + email digests only. SMS and advanced batching features deferred to post-launch.

## 1. Simplified System Architecture

### High-Level Components
```
[Notification API] → [SQS Standard] → [Worker Pool] → [Channel Services]
                                         ↓
[PostgreSQL] ← [Redis Cache] → [Delivery Tracking]
```

**Fixes Problem:** Eliminates single-point-of-failure "Channel Router" by using simple worker pool pattern with SQS Standard queues.

### Reduced Infrastructure Stack
- **Message Queue:** Amazon SQS Standard only (no FIFO)
- **Database:** PostgreSQL (managed RDS) 
- **Cache:** Single Redis instance (managed ElastiCache)
- **Containers:** ECS Fargate (2 services max)
- **Monitoring:** CloudWatch (AWS native)

**Fixes Problem:** Reduces from 12+ technologies to 6 core services manageable by 4 engineers.

## 2. Realistic Delivery Channels

### 2.1 Push Notifications Only
**Implementation:** Direct AWS SNS integration
- **Capacity:** 30K/minute sustained (realistic for SNS limits)
- **Platforms:** iOS (APNs) and Android (FCM) only
- **Features:** Basic notifications with deep links (no rich notifications initially)

```python
class PushNotificationService:
    def __init__(self):
        self.sns_client = boto3.client('sns')
        self.device_token_manager = DeviceTokenManager()
    
    async def send_push(self, user_id: str, message: dict):
        # Get valid device tokens for user
        tokens = await self.device_token_manager.get_active_tokens(user_id)
        if not tokens:
            return {'status': 'no_devices'}
        
        results = []
        for token in tokens:
            try:
                response = await self.sns_client.publish(
                    TargetArn=token.platform_arn,
                    Message=json.dumps(message)
                )
                results.append({'token_id': token.id, 'status': 'sent'})
            except EndpointDisabledException:
                await self.device_token_manager.mark_invalid(token.id)
        
        return results
```

**Fixes Problem:** Includes device token management that was completely missing from original proposal.

### 2.2 Email Digests Only
**Service:** Amazon SES (not SendGrid - reduces vendor complexity)
- **Capacity:** 5K/minute (within SES free tier limits)
- **Type:** Daily/weekly digests only (no transactional email)
- **Templates:** Simple HTML templates stored in S3

**Fixes Problem:** Eliminates real-time email delivery that created capacity misalignment. Focuses on proven digest use case.

### 2.3 Removed Channels
- **In-App Notifications:** Deferred (WebSocket complexity too high for timeline)
- **SMS:** Removed (cost prohibitive at scale)

**Fixes Problem:** Eliminates unrealistic WebSocket connection claims and SMS cost explosion.

## 3. Simplified Priority System

### 3.1 Two Priority Levels Only
```python
class Priority(Enum):
    IMMEDIATE = 1   # Direct messages, mentions - send now
    DIGEST = 2      # Everything else - batch for daily digest

class NotificationProcessor:
    async def process_notification(self, notification: dict):
        if notification['priority'] == Priority.IMMEDIATE:
            return await self.send_push_now(notification)
        else:
            return await self.add_to_digest_queue(notification)
```

**Fixes Problem:** Eliminates contradictory batching vs. real-time goals. Clear separation of immediate vs. batched notifications.

### 3.2 No Complex Batching
- **Immediate notifications:** Send via push within 30 seconds
- **Digest notifications:** Batch daily, send via email
- **No intelligent batching:** Users can opt out of digest entirely

**Fixes Problem:** Removes complex batching logic that created performance bottlenecks and contradictory requirements.

## 4. Simplified User Preferences

### 4.1 Normalized Schema (No JSONB)
```sql
CREATE TABLE user_notification_preferences (
    user_id UUID PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_digest_enabled BOOLEAN DEFAULT true,
    email_address VARCHAR(255),
    timezone VARCHAR(50) DEFAULT 'UTC',
    digest_frequency VARCHAR(20) DEFAULT 'daily', -- daily, weekly, never
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Separate table for granular controls
CREATE TABLE notification_type_preferences (
    user_id UUID,
    notification_type VARCHAR(50), -- 'direct_message', 'like', 'comment', 'follow'
    push_enabled BOOLEAN DEFAULT true,
    digest_enabled BOOLEAN DEFAULT true,
    PRIMARY KEY (user_id, notification_type)
);
```

**Fixes Problem:** Eliminates JSONB anti-pattern that prevented efficient querying for bulk operations.

### 4.2 Simple Preference API
```python
class PreferenceService:
    async def update_notification_preference(self, user_id: str, notification_type: str, 
                                           push_enabled: bool, digest_enabled: bool):
        await self.db.execute("""
            INSERT INTO notification_type_preferences 
            (user_id, notification_type, push_enabled, digest_enabled)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, notification_type) 
            DO UPDATE SET push_enabled = $3, digest_enabled = $4
        """, user_id, notification_type, push_enabled, digest_enabled)
        
        # Cache invalidation
        await self.cache.delete(f"prefs:{user_id}")
```

**Fixes Problem:** Provides simple, queryable preference system without JSONB complexity.

## 5. Realistic Database Design

### 5.1 Proper Scaling Estimates
**Realistic Volume Calculation:**
- 10M MAU × 5 notifications/user/day = 50M notifications/day
- 18.25B notifications/year (not 50M as originally claimed)
- Daily partitioning required, not monthly

```sql
-- Partitioned by day for efficient cleanup
CREATE TABLE notifications (
    id BIGSERIAL,
    user_id UUID NOT NULL,
    type VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    INDEX idx_user_created (user_id, created_at DESC),
    INDEX idx_type_created (type, created_at DESC)
) PARTITION BY RANGE (created_at);

-- Device token management (missing from original)
CREATE TABLE user_device_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    platform VARCHAR(20) NOT NULL, -- 'ios', 'android'
    token VARCHAR(500) NOT NULL,
    platform_arn VARCHAR(500), -- SNS endpoint ARN
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    last_used TIMESTAMP DEFAULT NOW(),
    INDEX idx_user_active (user_id, is_active),
    UNIQUE(token)
);
```

**Fixes Problem:** Addresses missing device token management and provides realistic volume estimates with proper indexing.

### 5.2 Delivery Tracking
```sql
CREATE TABLE notification_deliveries (
    notification_id BIGINT,
    user_id UUID,
    channel VARCHAR(20), -- 'push', 'email'
    status VARCHAR(20), -- 'sent', 'delivered', 'failed', 'bounced'
    error_message TEXT,
    delivered_at TIMESTAMP,
    PRIMARY KEY (notification_id, channel)
) PARTITION BY RANGE (delivered_at);
```

**Fixes Problem:** Adds missing delivery status tracking for debugging and analytics.

## 6. Simplified Infrastructure

### 6.1 Two-Service Architecture
```yaml
# Notification API Service
notification-api:
  image: social-app/notification-api:latest
  environment:
    - DATABASE_URL=postgresql://...
    - REDIS_URL=redis://...
    - SQS_QUEUE_URL=https://sqs...
  resources:
    limits:
      memory: 2GB
      cpu: 1.0
  scale: 2

# Notification Worker Service  
notification-worker:
  image: social-app/notification-worker:latest
  environment:
    - DATABASE_URL=postgresql://...
    - REDIS_URL=redis://...
    - SQS_QUEUE_URL=https://sqs...
  resources:
    limits:
      memory: 2GB
      cpu: 1.0
  scale: 4
```

**Fixes Problem:** Realistic resource allocation and eliminates unrealistic WebSocket connection claims.

### 6.2 Processing Pipeline
1. **API Service:** Receives requests → Validates → Writes to SQS Standard
2. **Worker Pool:** 4 workers poll SQS → Process notifications → Send via channels
3. **No Circuit Breakers:** Use SQS dead letter queues for failed messages

**Fixes Problem:** Eliminates complex circuit breaker patterns that add operational overhead.

### 6.3 Caching Strategy (Simplified)
```python
class NotificationCache:
    def __init__(self):
        self.redis = redis.Redis(decode_responses=True)
    
    async def get_user_preferences(self, user_id: str) -> dict:
        # Cache user preferences for 10 minutes only
        cached = await self.redis.get(f"prefs:{user_id}")
        if cached:
            return json.loads(cached)
        
        prefs = await self.db.fetch_user_preferences(user_id)
        await self.redis.setex(f"prefs:{user_id}", 600, json.dumps(prefs))
        return prefs
```

**Fixes Problem:** Reduces cache TTL from 1 hour to 10 minutes to minimize race conditions with preference updates.

## 7. Failure Handling (Simplified)

### 7.1 SQS-Based Retry
```python
class NotificationWorker:
    async def process_message(self, message):
        try:
            notification = json.loads(message.body)
            await self.send_notification(notification)
            await self.sqs.delete_message(message)
        except Exception as e:
            # Let SQS handle retries with exponential backoff
            # After max retries, message goes to DLQ automatically
            logger.error(f"Failed to process notification: {e}")
            raise
```

**Fixes Problem:** Uses SQS built-in retry mechanism instead of custom exponential backoff logic.

### 7.2 Device Token Cleanup
```python
class DeviceTokenManager:
    async def handle_invalid_token(self, token_id: str, error_type: str):
        if error_type in ['EndpointDisabled', 'InvalidToken']:
            await self.db.execute(
                "UPDATE user_device_tokens SET is_active = false WHERE id = $1",
                token_id
            )
```

**Fixes Problem:** Handles device token lifecycle that was completely missing from original proposal.

## 8. Revised Implementation Timeline

### Month 1-2: Core Foundation
**Sprint 1-2: Basic Infrastructure**
- PostgreSQL setup with partitioning
- SQS queues and workers
- Device token registration API
- Basic push notification sending

**Sprint 3-4: User Preferences**
- Preference database schema
- Preference management API
- Redis caching layer
- Basic notification API

**Deliverable:** Push notifications working for registered devices

**Fixes Problem:** Realistic MVP definition that includes prerequisite device token management.

### Month 3-4: Scale and Reliability  
**Sprint 5-6: Delivery Tracking**
- Notification delivery status tracking
- Device token cleanup processes
- SQS dead letter queue handling
- Basic monitoring with CloudWatch

**Sprint 7-8: Email Digests**
- SES integration
- Daily digest generation job
- Email template system
- Digest preference controls

**Deliverable:** Complete push + email digest system

**Fixes Problem:** Allocates proper time for delivery tracking and email integration complexity.

### Month 5-6: Production Readiness
**Sprint 9-10: Performance & Monitoring**
- Database performance tuning
- Load testing with realistic volumes
- Comprehensive monitoring and alerting
- Runbook documentation

**Sprint 11-12: Launch Preparation**
- Security review and fixes
- Gradual rollout plan (1% → 10% → 100%)
- Team training and handoff documentation
- Cost monitoring and optimization

**Deliverable:** Production-ready system handling 30K notifications/minute

**Fixes Problem:** Includes proper testing phases and gradual rollout instead of jumping to full scale.

## 9. Team Allocation (4 Engineers)

### 9.1 Role Specialization
- **Engineer 1:** Backend API + Database (PostgreSQL expert)
- **Engineer 2:** Worker services + SQS integration (Queue processing expert)  
- **Engineer 3:** Push notifications + Device management (Mobile platform expert)
- **Engineer 4:** Email digests + DevOps (AWS/Infrastructure expert)

**Fixes Problem:** Realistic specialization instead of expecting all engineers to master 12+ technologies.

### 9.2 DevOps Allocation
- **25% of Engineer 4's time:** Infrastructure management
- **Managed services:** RDS, ElastiCache, SQS (reduce operational overhead)
- **Simple monitoring:** CloudWatch only (no DataDog complexity)

**Fixes Problem:** Explicit DevOps resource allocation that was missing from original proposal.

## 10. Realistic Success Metrics

### 10.1 Technical Metrics
- **Delivery Success Rate:** >95% (not 99% which is unrealistic initially)
- **Processing Latency:** p95 <60s for immediate notifications
- **System Availability:** 99% uptime (not 99.9% for initial launch)
- **Cost per Notification:** <$0.01 (includes realistic SMS removal)

### 10.2 Simplified Business Metrics
- **Push Notification Opt-in Rate:** >70% of DAU
- **Email Digest Open Rate:** >20%
- **User Complaint Rate:** <2% monthly

**Fixes Problem:** Realistic metrics that don't contradict system design constraints.

## 11. Key Tradeoffs Made

### 11.1 Removed Features
- **SMS notifications:** Cost prohibitive ($10M+ annually)
- **In-app real-time:** WebSocket complexity too high
- **Rich push notifications:** Implementation complexity
- **Intelligent batching:** Algorithm complexity

**Fixes Problem:** Eliminates features that created cost explosions and unrealistic technical complexity.

### 11.2 Accepted Limitations
- **Email delivery:** 5K/minute max (SES limits)
- **Push notifications:** 30K/minute max (realistic capacity)
- **Preference changes:** Up to 10-minute delay (cache TTL)
- **Digest frequency:** Daily minimum (no hourly digests)

**Fixes Problem:** Sets realistic capacity expectations that align with chosen infrastructure.

### 11.3 Technology Simplifications
- **Single Redis instance:** No clustering complexity
- **PostgreSQL only:** No multi-database complexity  
- **CloudWatch monitoring:** No external monitoring services
- **SQS Standard:** No ordering guarantees needed

**Fixes Problem:** Reduces operational complexity to manageable level for 4-person team.

This revised proposal addresses the fundamental scalability issues, unrealistic performance claims, and team resource constraints while delivering a functional notification system that can realistically be built and operated by 4 engineers in 6 months.