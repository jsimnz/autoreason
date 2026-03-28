# Notification System Design for Social App (10M MAU) - SYNTHESIS

## Executive Summary

This proposal outlines a scalable notification system for a social app serving 10 million monthly active users. Given the 4-engineer, 6-month constraint, we adopt a pragmatic architecture using proven managed services while building only essential custom logic for competitive differentiation.

**Key Design Principles:**
- Leverage managed services to reduce operational overhead
- Build incrementally with realistic MVP boundaries  
- Design for 30K notifications/minute sustained capacity
- Ensure 95% delivery reliability with path to 99%

**Scope:** Push notifications (primary), email digests (secondary), with SMS reserved for critical security events only.

## 1. System Architecture Overview

### High-Level Components
```
[Notification API] → [SQS Standard] → [Worker Pool] → [Channel Services]
                                         ↓
[PostgreSQL] ← [Redis Cache] → [Delivery Tracking]
```

**Architecture Decision:** Uses Version B's simplified worker pool pattern instead of Version A's complex channel router, eliminating single points of failure while maintaining clear separation of concerns.

### Core Infrastructure Stack
- **Message Queue:** Amazon SQS Standard (no FIFO complexity)
- **Database:** PostgreSQL (managed RDS) + Redis (managed ElastiCache)  
- **Container Platform:** AWS ECS Fargate
- **Push Delivery:** Amazon SNS with platform endpoints
- **Email Service:** Amazon SES (not SendGrid - reduces vendor complexity)
- **Monitoring:** CloudWatch + selective DataDog for business metrics

**Rationale:** Adopts Version B's AWS-native approach to reduce vendor complexity while retaining Version A's DataDog for critical business metrics that CloudWatch cannot provide effectively.

## 2. Delivery Channels Implementation

### 2.1 Push Notifications (Primary Channel)
**Service:** Amazon SNS with comprehensive device management
- **Capacity:** 30K/minute sustained (realistic SNS limits)
- **Platforms:** iOS (APNs) and Android (FCM)
- **Features:** Basic notifications with deep linking, badge counts

```python
class PushNotificationService:
    def __init__(self):
        self.sns_client = boto3.client('sns')
        self.device_token_manager = DeviceTokenManager()
        self.rate_limiter = RedisRateLimiter(max_per_minute=30000)
    
    async def send_push(self, user_id: str, message: dict, priority: Priority):
        # Rate limiting from Version A
        if not self.rate_limiter.allow(f"push:{user_id}"):
            return await self.queue_for_retry(message, delay=60)
        
        # Device management from Version B  
        tokens = await self.device_token_manager.get_active_tokens(user_id)
        if not tokens:
            return {'status': 'no_devices'}
        
        results = []
        for token in tokens:
            try:
                response = await self.sns_client.publish(
                    TargetArn=token.platform_arn,
                    Message=json.dumps(message),
                    MessageAttributes=self._build_attributes(priority)
                )
                results.append({'token_id': token.id, 'status': 'sent'})
            except EndpointDisabledException:
                await self.device_token_manager.mark_invalid(token.id)
        
        return results
```

**Key Enhancement:** Combines Version A's rate limiting with Version B's essential device token management that was completely missing from the original.

### 2.2 Email Digests (Secondary Channel)
**Service:** Amazon SES
- **Capacity:** 10K/minute (within SES limits, higher than Version B's 5K)
- **Types:** Daily digests, weekly summaries, critical transactional emails
- **Templates:** HTML templates stored in S3 with personalization

**Rationale:** Retains Version A's higher capacity goal while using Version B's simplified SES approach. Includes critical transactional emails (password resets, security alerts) that Version B incorrectly removed.

### 2.3 SMS (Critical Events Only)
**Service:** Twilio
- **Usage:** Security alerts, account verification only
- **Capacity:** 500/minute (cost-controlled)
- **Cost Model:** $0.05/SMS × 1% of users × 2 SMS/month = $1K/month (manageable)

**Rationale:** Retains Version A's SMS capability but with Version B's cost consciousness. Critical security notifications justify the expense and regulatory compliance often requires SMS 2FA.

### 2.4 Removed Channels
- **In-app WebSocket notifications:** Deferred to Phase 2 (complexity too high for 6-month timeline)

**Rationale:** Agrees with Version B that WebSocket complexity exceeds team capacity within timeline constraints.

## 3. Priority and Batching Logic

### 3.1 Three Priority Levels (Compromise)
```python
class Priority(Enum):
    CRITICAL = 1    # Security, verification - immediate, all channels
    IMMEDIATE = 2   # Direct messages, mentions - push within 30s
    DIGEST = 3      # Likes, follows - batch for daily digest

class NotificationProcessor:
    async def process_notification(self, notification: dict):
        priority = notification['priority']
        
        if priority == Priority.CRITICAL:
            # Multi-channel delivery
            await asyncio.gather(
                self.send_push(notification),
                self.send_email(notification),
                self.send_sms(notification) if user.sms_enabled else None
            )
        elif priority == Priority.IMMEDIATE:
            return await self.send_push_now(notification)
        else:
            return await self.add_to_digest_queue(notification)
```

**Rationale:** Uses Version B's simplified approach but retains Version A's critical priority level for security events that require multi-channel delivery.

### 3.2 Simple Batching Strategy
- **Critical:** Send immediately via all enabled channels
- **Immediate:** Send via push within 30 seconds, no batching
- **Digest:** Batch daily, send via email with intelligent aggregation

```python
class DigestBatcher:
    async def create_daily_digest(self, user_id: str, date: datetime.date):
        notifications = await self.get_digest_notifications(user_id, date)
        
        # Simple aggregation: "John and 4 others liked your post"
        aggregated = self.aggregate_similar_notifications(notifications)
        
        return self.render_digest_template(user_id, aggregated)
    
    def aggregate_similar_notifications(self, notifications: List[dict]) -> List[dict]:
        grouped = defaultdict(list)
        for notif in notifications:
            key = f"{notif['type']}:{notif.get('target_id', '')}"
            grouped[key].append(notif)
        
        aggregated = []
        for group in grouped.values():
            if len(group) > 1 and group[0]['type'] in ['like', 'follow']:
                aggregated.append(self.create_aggregated_notification(group))
            else:
                aggregated.extend(group)
        
        return aggregated
```

**Rationale:** Adopts Version B's simplicity while retaining Version A's intelligent aggregation for digest notifications where it provides clear user value.

## 4. User Preference Management

### 4.1 Normalized Database Schema
```sql
-- From Version B: Normalized approach
CREATE TABLE user_notification_preferences (
    user_id UUID PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    email_address VARCHAR(255),
    timezone VARCHAR(50) DEFAULT 'UTC',
    digest_frequency VARCHAR(20) DEFAULT 'daily',
    -- From Version A: Essential timing controls
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE notification_type_preferences (
    user_id UUID,
    notification_type VARCHAR(50),
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    PRIMARY KEY (user_id, notification_type)
);
```

**Rationale:** Uses Version B's normalized approach for queryability while retaining Version A's quiet hours feature that significantly improves user experience.

### 4.2 Smart Defaults with Learning
```python
class PreferenceService:
    async def initialize_user_preferences(self, user_id: str, user_data: dict):
        # Smart defaults based on user signup context
        defaults = {
            'push_enabled': True,
            'email_enabled': True, 
            'sms_enabled': False,
            'digest_frequency': 'daily'
        }
        
        # Adjust based on signup source
        if user_data.get('signup_source') == 'mobile_app':
            defaults['digest_frequency'] = 'weekly'  # Mobile users prefer less email
        
        await self.create_user_preferences(user_id, defaults)
        
        # Progressive onboarding: start with essential notifications only
        essential_types = ['direct_message', 'security_alert']
        for notif_type in essential_types:
            await self.set_notification_type_preference(
                user_id, notif_type, push_enabled=True, email_enabled=True
            )
```

**Rationale:** Retains Version A's smart defaults concept but implements it through Version B's normalized schema, avoiding JSONB complexity.

## 5. Infrastructure Implementation

### 5.1 Realistic Database Design
```sql
-- Realistic volume: 10M MAU × 5 notifications/day = 50M/day = 18B/year
CREATE TABLE notifications (
    id BIGSERIAL,
    user_id UUID NOT NULL,
    type VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    metadata JSONB, -- Minimal JSONB use for flexible payload
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- From Version B: Essential device token management
CREATE TABLE user_device_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    platform VARCHAR(20) NOT NULL,
    token VARCHAR(500) NOT NULL,
    platform_arn VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    last_used TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, token)
);

-- From Version B: Delivery tracking for debugging
CREATE TABLE notification_deliveries (
    notification_id BIGINT,
    user_id UUID,
    channel VARCHAR(20),
    status VARCHAR(20), -- 'sent', 'delivered', 'failed'
    error_message TEXT,
    delivered_at TIMESTAMP,
    PRIMARY KEY (notification_id, channel)
) PARTITION BY RANGE (delivered_at);
```

**Rationale:** Uses Version B's realistic volume calculations and essential device token management while retaining minimal JSONB use for notification payload flexibility.

### 5.2 Two-Service Architecture
```yaml
# API Service
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

# Worker Service
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

**Rationale:** Adopts Version B's simplified two-service architecture with realistic resource allocation.

### 5.3 Intelligent Caching Strategy
```python
class NotificationCache:
    def __init__(self):
        self.redis = redis.Redis(decode_responses=True)
    
    async def get_user_preferences(self, user_id: str) -> dict:
        # Version B's shorter TTL to minimize race conditions
        cached = await self.redis.get(f"prefs:{user_id}")
        if cached:
            return json.loads(cached)
        
        prefs = await self.db.fetch_user_preferences(user_id)
        await self.redis.setex(f"prefs:{user_id}", 600, json.dumps(prefs))
        return prefs
    
    # Version A's rate limiting capability
    async def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        current = await self.redis.get(key)
        if current is None:
            await self.redis.setex(key, window, 1)
            return True
        elif int(current) < limit:
            await self.redis.incr(key)
            return True
        return False
```

**Rationale:** Uses Version B's conservative cache TTL while retaining Version A's rate limiting functionality that's essential for preventing notification spam.

## 6. Failure Handling & Reliability

### 6.1 Simplified Retry with SQS
```python
class NotificationWorker:
    async def process_message(self, message):
        try:
            notification = json.loads(message.body)
            
            # Apply rate limiting before processing
            if not await self.rate_limiter.allow(notification):
                # Requeue with delay by not deleting message
                return
            
            result = await self.send_notification(notification)
            
            # Track delivery status
            await self.track_delivery(notification['id'], result)
            
            # Success - delete message
            await self.sqs.delete_message(message)
            
        except Exception as e:
            # Let SQS handle retries automatically
            logger.error(f"Failed to process notification: {e}")
            await self.track_delivery_failure(notification.get('id'), str(e))
            raise
```

**Rationale:** Uses Version B's SQS-based retry mechanism while adding Version A's rate limiting and delivery tracking capabilities.

### 6.2 Device Token Lifecycle Management
```python
class DeviceTokenManager:
    async def handle_delivery_feedback(self, token_id: str, feedback: dict):
        """Handle push notification delivery feedback"""
        if feedback.get('error_type') in ['EndpointDisabled', 'InvalidToken']:
            await self.mark_token_inactive(token_id)
        elif feedback.get('status') == 'delivered':
            await self.update_last_used(token_id)
    
    async def cleanup_inactive_tokens(self):
        """Daily cleanup job for inactive tokens"""
        cutoff_date = datetime.now() - timedelta(days=30)
        await self.db.execute(
            "DELETE FROM user_device_tokens WHERE is_active = false AND last_used < $1",
            cutoff_date
        )
```

**Rationale:** Adopts Version B's device token management approach that was completely missing from Version A.

## 7. Implementation Timeline (6 Months)

### Month 1-2: Foundation + Device Management
**Sprint 1-2: Core Infrastructure**
- PostgreSQL setup with daily partitioning
- SQS queues and basic workers
- Device token registration and management API
- Redis caching layer

**Sprint 3-4: Push Notifications MVP**
- SNS integration for iOS/Android
- Basic notification sending pipeline
- Device token cleanup processes
- Simple rate limiting

**Deliverable:** Working push notifications with device lifecycle management

**Key Change:** Includes device token management from Sprint 1, addressing Version A's critical oversight.

### Month 3-4: Scale and Intelligence
**Sprint 5-6: User Preferences**
- Preference database schema and API
- Quiet hours implementation
- Notification type controls
- Basic delivery tracking

**Sprint 7-8: Email Digests**
- SES integration and templates
- Daily digest generation job
- Simple notification aggregation
- Email preference controls

**Deliverable:** Complete push + email system with user preference controls

**Key Change:** Realistic timeline that accounts for email integration complexity.

### Month 5-6: Production Readiness
**Sprint 9-10: Reliability & SMS**
- SMS integration for critical notifications
- Comprehensive delivery tracking
- Performance monitoring and alerting
- Load testing at 30K/minute

**Sprint 11-12: Launch Preparation**
- Security