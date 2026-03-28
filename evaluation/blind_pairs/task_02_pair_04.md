# Blind Evaluation: task_02_pair_04

## Task
Design the notification system for a social app with 10M MAU. Cover: delivery channels (push, email, in-app, SMS), priority and batching logic, user preference management, infrastructure choices, and failure handling. The team has 4 backend engineers and 6 months. Be specific about tradeoffs you're making and why.

---

## Proposal X

# Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 6-month timeline and 4-engineer team constraint, we prioritize MVP functionality with built-in scalability hooks over complex features like ML-based optimization.

**Key Design Decisions:**
- Event-driven architecture using AWS SQS/SNS for reliability
- PostgreSQL for user preferences with Redis caching for performance
- Phased rollout prioritizing push notifications and in-app delivery
- Conservative batching and rate limiting to ensure stability

---

## 1. System Architecture Overview

### 1.1 High-Level Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   App Services  │───▶│ Notification API │───▶│  Queue System   │
│                 │    │                  │    │   (SQS/SNS)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                       ┌─────────────────────────────────┼─────────────────────────────────┐
                       ▼                                 ▼                                 ▼
              ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
              │ Push Processor  │              │ Email Processor │              │ In-App Processor│
              │                 │              │                 │              │                 │
              └─────────────────┘              └─────────────────┘              └─────────────────┘
                       │                                 │                                 │
                       ▼                                 ▼                                 ▼
              ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
              │   FCM/APNS      │              │   SendGrid      │              │   WebSocket     │
              │                 │              │                 │              │   + Database    │
              └─────────────────┘              └─────────────────┘              └─────────────────┘
```

### 1.2 Technology Stack Selection

**Message Queue:** AWS SQS + SNS
- *Rationale:* Proven reliability, managed service reduces operational overhead
- *Tradeoff:* Higher cost vs. self-managed Kafka, but acceptable given team size

**Database:** PostgreSQL (primary) + Redis (cache)
- *Rationale:* Team likely familiar with PostgreSQL, Redis provides sub-100ms preference lookups
- *Tradeoff:* Single database vs. microservice-per-domain approach (too complex for timeline)

**Push Services:** Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNS)
- *Rationale:* Industry standard, handles device management complexity
- *Tradeoff:* Vendor lock-in vs. custom solution (custom not feasible in timeline)

---

## 2. Delivery Channels Implementation

### 2.1 Priority Order & Timeline

**Phase 1 (Months 1-3):** Push Notifications + In-App
**Phase 2 (Months 4-5):** Email Integration  
**Phase 3 (Month 6):** SMS (basic implementation)

### 2.2 Channel-Specific Implementation

#### Push Notifications
```python
# Push processor service
class PushProcessor:
    def __init__(self):
        self.fcm_client = FCMClient(api_key=settings.FCM_KEY)
        self.apns_client = APNSClient(cert_path=settings.APNS_CERT)
        self.batch_size = 1000  # FCM supports up to 1000 per batch
        
    async def process_push_batch(self, notifications: List[PushNotification]):
        # Group by platform for efficient batching
        android_notifications = [n for n in notifications if n.platform == 'android']
        ios_notifications = [n for n in notifications if n.platform == 'ios']
        
        await asyncio.gather(
            self._send_fcm_batch(android_notifications),
            self._send_apns_batch(ios_notifications)
        )
```

**Delivery SLA:** 95% delivered within 30 seconds
**Batch Size:** 1,000 notifications per batch (FCM limit)
**Rate Limiting:** 10,000 notifications/minute per app to avoid provider throttling

#### In-App Notifications
```sql
-- In-app notifications table
CREATE TABLE in_app_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    data JSONB,
    read_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- Index for efficient user queries
CREATE INDEX idx_in_app_notifications_user_unread 
ON in_app_notifications(user_id, created_at) 
WHERE read_at IS NULL;
```

**Storage Duration:** 30 days for read notifications, 90 days for unread
**Real-time Delivery:** WebSocket connections with fallback to polling every 30 seconds

#### Email (Phase 2)
- **Provider:** SendGrid (reliability + analytics)
- **Template System:** SendGrid Dynamic Templates
- **Batch Size:** 10,000 emails per batch
- **Unsubscribe:** Automatic handling via SendGrid + preference sync

#### SMS (Phase 3)
- **Provider:** Twilio
- **Use Cases:** Critical alerts only (security, urgent social events)
- **Rate Limiting:** 1 SMS per user per hour maximum
- **Cost Control:** $0.02/SMS budget cap at 50,000 SMS/month

---

## 3. Priority and Batching Logic

### 3.1 Priority Classification

```python
class NotificationPriority(Enum):
    CRITICAL = 1     # Security alerts, payment issues
    HIGH = 2         # Direct messages, mentions
    MEDIUM = 3       # Likes, comments, follows
    LOW = 4          # Weekly digests, recommendations

# Processing order and SLAs
PRIORITY_CONFIG = {
    NotificationPriority.CRITICAL: {
        'max_delay_seconds': 5,
        'batch_size': 100,
        'retry_attempts': 5
    },
    NotificationPriority.HIGH: {
        'max_delay_seconds': 30,
        'batch_size': 500,
        'retry_attempts': 3
    },
    NotificationPriority.MEDIUM: {
        'max_delay_seconds': 300,
        'batch_size': 1000,
        'retry_attempts': 2
    },
    NotificationPriority.LOW: {
        'max_delay_seconds': 1800,
        'batch_size': 2000,
        'retry_attempts': 1
    }
}
```

### 3.2 Batching Strategy

**Time-based Batching:**
- Critical: Process immediately
- High: 30-second windows
- Medium: 5-minute windows  
- Low: 30-minute windows

**Size-based Batching:**
- Trigger processing when batch reaches 80% of max size
- Prevents memory issues and provides predictable processing

**Anti-spam Logic:**
```python
class NotificationDeduplicator:
    def __init__(self, redis_client):
        self.redis = redis_client
        
    async def should_send_notification(self, user_id: str, category: str, content_hash: str) -> bool:
        # Prevent duplicate notifications within 1 hour
        key = f"notif_dedup:{user_id}:{category}:{content_hash}"
        exists = await self.redis.exists(key)
        
        if not exists:
            await self.redis.setex(key, 3600, "1")  # 1 hour expiry
            return True
        return False
```

---

## 4. User Preference Management

### 4.1 Database Schema

```sql
-- User notification preferences
CREATE TABLE user_notification_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id),
    
    -- Channel preferences
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    in_app_enabled BOOLEAN DEFAULT true,
    
    -- Category preferences (JSONB for flexibility)
    category_preferences JSONB DEFAULT '{
        "direct_messages": {"push": true, "email": true, "sms": false},
        "mentions": {"push": true, "email": true, "sms": false},
        "likes": {"push": true, "email": false, "sms": false},
        "follows": {"push": true, "email": false, "sms": false},
        "comments": {"push": true, "email": false, "sms": false},
        "security": {"push": true, "email": true, "sms": true}
    }'::jsonb,
    
    -- Quiet hours (user timezone)
    quiet_hours_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Device tokens for push notifications
CREATE TABLE user_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    platform VARCHAR(20) NOT NULL, -- 'ios', 'android', 'web'
    token VARCHAR(500) NOT NULL,
    active BOOLEAN DEFAULT true,
    last_seen_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 4.2 Caching Strategy

```python
class PreferenceCache:
    def __init__(self, redis_client, db_pool):
        self.redis = redis_client
        self.db = db_pool
        self.cache_ttl = 3600  # 1 hour
        
    async def get_user_preferences(self, user_id: str) -> UserPreferences:
        # Try cache first
        cache_key = f"user_prefs:{user_id}"
        cached = await self.redis.get(cache_key)
        
        if cached:
            return UserPreferences.parse_raw(cached)
            
        # Fallback to database
        prefs = await self._fetch_from_db(user_id)
        await self.redis.setex(cache_key, self.cache_ttl, prefs.json())
        return prefs
```

### 4.3 Preference API

```python
# RESTful preference management
@router.put("/users/{user_id}/notification-preferences")
async def update_preferences(
    user_id: UUID,
    preferences: UserPreferenceUpdate,
    current_user: User = Depends(get_current_user)
):
    # Authorization check
    if current_user.id != user_id:
        raise HTTPException(status_code=403)
    
    # Update database
    await preference_service.update_preferences(user_id, preferences)
    
    # Invalidate cache
    await preference_cache.invalidate(user_id)
    
    return {"status": "updated"}
```

---

## 5. Infrastructure Choices

### 5.1 AWS Infrastructure

```yaml
# Infrastructure as Code (Terraform)
resource "aws_sqs_queue" "notification_queue" {
  name = "notification-processing"
  
  # Dead letter queue for failed messages
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notification_dlq.arn
    maxReceiveCount     = 3
  })
  
  # Message retention
  message_retention_seconds = 1209600  # 14 days
  
  # Visibility timeout allows processing time
  visibility_timeout_seconds = 300  # 5 minutes
}

resource "aws_sns_topic" "notification_fanout" {
  name = "notification-events"
}
```

### 5.2 Deployment Architecture

**Container Strategy:** Docker + AWS ECS Fargate
- *Rationale:* Managed container orchestration, auto-scaling
- *Tradeoff:* Higher cost vs. EC2, but reduces operational complexity

**Database Hosting:** AWS RDS PostgreSQL Multi-AZ
- *Configuration:* db.r5.xlarge (4 vCPU, 32GB RAM)
- *Rationale:* Managed service with automatic failover
- *Scaling Plan:* Read replicas for notification preference lookups

**Redis Configuration:** AWS ElastiCache
- *Configuration:* cache.r6g.large (2 vCPU, 13GB RAM)
- *Replication:* Primary + 1 replica for high availability

### 5.3 Monitoring and Observability

```python
# Custom metrics for business monitoring
class NotificationMetrics:
    def __init__(self, cloudwatch_client):
        self.cloudwatch = cloudwatch_client
        
    async def record_delivery_attempt(self, channel: str, success: bool, latency_ms: int):
        await self.cloudwatch.put_metric_data(
            Namespace='NotificationSystem',
            MetricData=[
                {
                    'MetricName': 'DeliveryAttempts',
                    'Dimensions': [
                        {'Name': 'Channel', 'Value': channel},
                        {'Name': 'Success', 'Value': str(success)}
                    ],
                    'Value': 1,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'DeliveryLatency',
                    'Dimensions': [{'Name': 'Channel', 'Value': channel}],
                    'Value': latency_ms,
                    'Unit': 'Milliseconds'
                }
            ]
        )
```

**Key Metrics to Track:**
- Delivery success rate by channel (target: >95%)
- End-to-end latency (target: <30s for high priority)
- Queue depth and processing rate
- User engagement rates by notification type

---

## 6. Failure Handling and Resilience

### 6.1 Retry Logic

```python
class NotificationRetryHandler:
    def __init__(self):
        self.max_retries = {
            NotificationPriority.CRITICAL: 5,
            NotificationPriority.HIGH: 3,
            NotificationPriority.MEDIUM: 2,
            NotificationPriority.LOW: 1
        }
        
    async def process_with_retry(self, notification: Notification):
        max_attempts = self.max_retries[notification.priority]
        
        for attempt in range(1, max_attempts + 1):
            try:
                await self._send_notification(notification)
                return  # Success
                
            except RetryableError as e:
                if attempt == max_attempts:
                    await self._send_to_dlq(notification, str(e))
                    return
                    
                # Exponential backoff: 2^attempt seconds
                await asyncio.sleep(2 ** attempt)
                
            except NonRetryableError as e:
                await self._send_to_dlq(notification, str(e))
                return
```

### 6.2 Circuit Breaker Pattern

```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError()
                
        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
            

---

## Proposal Y

# Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 6-month timeline and 4-engineer team constraint, we prioritize MVP functionality with built-in scalability hooks over complex features like ML-based optimization.

**Key Design Decisions:**
- Event-driven architecture using AWS SQS/SNS for reliability
- PostgreSQL for user preferences with Redis caching for performance
- Phased rollout prioritizing push notifications and in-app delivery
- Conservative batching and rate limiting to ensure stability

---

## 1. System Architecture Overview

### 1.1 High-Level Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   App Services  │───▶│ Notification API │───▶│  Queue System   │
│                 │    │                  │    │   (SQS/SNS)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                       ┌─────────────────────────────────┼─────────────────────────────────┐
                       ▼                                 ▼                                 ▼
              ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
              │ Push Processor  │              │ Email Processor │              │ In-App Processor│
              │                 │              │                 │              │                 │
              └─────────────────┘              └─────────────────┘              └─────────────────┘
                       │                                 │                                 │
                       ▼                                 ▼                                 ▼
              ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
              │   FCM/APNS      │              │   SendGrid      │              │   WebSocket     │
              │                 │              │                 │              │   + Database    │
              └─────────────────┘              └─────────────────┘              └─────────────────┘
```

### 1.2 Technology Stack Selection

**Message Queue:** AWS SQS + SNS
- *Rationale:* Proven reliability, managed service reduces operational overhead
- *Tradeoff:* Higher cost vs. self-managed Kafka, but acceptable given team size

**Database:** PostgreSQL (primary) + Redis (cache)
- *Rationale:* Team likely familiar with PostgreSQL, Redis provides sub-100ms preference lookups
- *Tradeoff:* Single database vs. microservice-per-domain approach (too complex for timeline)

**Push Services:** Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNS)
- *Rationale:* Industry standard, handles device management complexity
- *Tradeoff:* Vendor lock-in vs. custom solution (custom not feasible in timeline)

---

## 2. Delivery Channels Implementation

### 2.1 Priority Order & Timeline

**Phase 1 (Months 1-3):** Push Notifications + In-App
**Phase 2 (Months 4-5):** Email Integration  
**Phase 3 (Month 6):** SMS (basic implementation)

### 2.2 Channel-Specific Implementation

#### Push Notifications
```python
# Push processor service
class PushProcessor:
    def __init__(self):
        self.fcm_client = FCMClient(api_key=settings.FCM_KEY)
        self.apns_client = APNSClient(cert_path=settings.APNS_CERT)
        self.batch_size = 1000  # FCM supports up to 1000 per batch
        
    async def process_push_batch(self, notifications: List[PushNotification]):
        # Group by platform for efficient batching
        android_notifications = [n for n in notifications if n.platform == 'android']
        ios_notifications = [n for n in notifications if n.platform == 'ios']
        
        await asyncio.gather(
            self._send_fcm_batch(android_notifications),
            self._send_apns_batch(ios_notifications)
        )
```

**Delivery SLA:** 95% delivered within 30 seconds
**Batch Size:** 1,000 notifications per batch (FCM limit)
**Rate Limiting:** 10,000 notifications/minute per app to avoid provider throttling

#### In-App Notifications
```sql
-- In-app notifications table
CREATE TABLE in_app_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    data JSONB,
    read_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- Index for efficient user queries
CREATE INDEX idx_in_app_notifications_user_unread 
ON in_app_notifications(user_id, created_at) 
WHERE read_at IS NULL;
```

**Storage Duration:** 30 days for read notifications, 90 days for unread
**Real-time Delivery:** WebSocket connections with fallback to polling every 30 seconds

#### Email (Phase 2)
- **Provider:** SendGrid (reliability + analytics)
- **Template System:** SendGrid Dynamic Templates
- **Batch Size:** 10,000 emails per batch
- **Unsubscribe:** Automatic handling via SendGrid + preference sync

#### SMS (Phase 3)
- **Provider:** Twilio
- **Use Cases:** Critical alerts only (security, urgent social events)
- **Rate Limiting:** 1 SMS per user per hour maximum
- **Cost Control:** $0.02/SMS budget cap at 50,000 SMS/month

---

## 3. Priority and Batching Logic

### 3.1 Priority Classification

```python
class NotificationPriority(Enum):
    CRITICAL = 1     # Security alerts, payment issues
    HIGH = 2         # Direct messages, mentions
    MEDIUM = 3       # Likes, comments, follows
    LOW = 4          # Weekly digests, recommendations

# Processing order and SLAs
PRIORITY_CONFIG = {
    NotificationPriority.CRITICAL: {
        'max_delay_seconds': 5,
        'batch_size': 100,
        'retry_attempts': 5
    },
    NotificationPriority.HIGH: {
        'max_delay_seconds': 30,
        'batch_size': 500,
        'retry_attempts': 3
    },
    NotificationPriority.MEDIUM: {
        'max_delay_seconds': 300,
        'batch_size': 1000,
        'retry_attempts': 2
    },
    NotificationPriority.LOW: {
        'max_delay_seconds': 1800,
        'batch_size': 2000,
        'retry_attempts': 1
    }
}
```

### 3.2 Batching Strategy

**Time-based Batching:**
- Critical: Process immediately
- High: 30-second windows
- Medium: 5-minute windows  
- Low: 30-minute windows

**Size-based Batching:**
- Trigger processing when batch reaches 80% of max size
- Prevents memory issues and provides predictable processing

**Anti-spam Logic:**
```python
class NotificationDeduplicator:
    def __init__(self, redis_client):
        self.redis = redis_client
        
    async def should_send_notification(self, user_id: str, category: str, content_hash: str) -> bool:
        # Prevent duplicate notifications within 1 hour
        key = f"notif_dedup:{user_id}:{category}:{content_hash}"
        exists = await self.redis.exists(key)
        
        if not exists:
            await self.redis.setex(key, 3600, "1")  # 1 hour expiry
            return True
        return False
```

---

## 4. User Preference Management

### 4.1 Database Schema

```sql
-- User notification preferences
CREATE TABLE user_notification_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id),
    
    -- Channel preferences
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    in_app_enabled BOOLEAN DEFAULT true,
    
    -- Category preferences (JSONB for flexibility)
    category_preferences JSONB DEFAULT '{
        "direct_messages": {"push": true, "email": true, "sms": false},
        "mentions": {"push": true, "email": true, "sms": false},
        "likes": {"push": true, "email": false, "sms": false},
        "follows": {"push": true, "email": false, "sms": false},
        "comments": {"push": true, "email": false, "sms": false},
        "security": {"push": true, "email": true, "sms": true}
    }'::jsonb,
    
    -- Quiet hours (user timezone)
    quiet_hours_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Device tokens for push notifications
CREATE TABLE user_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    platform VARCHAR(20) NOT NULL, -- 'ios', 'android', 'web'
    token VARCHAR(500) NOT NULL,
    active BOOLEAN DEFAULT true,
    last_seen_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 4.2 Caching Strategy

```python
class PreferenceCache:
    def __init__(self, redis_client, db_pool):
        self.redis = redis_client
        self.db = db_pool
        self.cache_ttl = 3600  # 1 hour
        
    async def get_user_preferences(self, user_id: str) -> UserPreferences:
        # Try cache first
        cache_key = f"user_prefs:{user_id}"
        cached = await self.redis.get(cache_key)
        
        if cached:
            return UserPreferences.parse_raw(cached)
            
        # Fallback to database
        prefs = await self._fetch_from_db(user_id)
        await self.redis.setex(cache_key, self.cache_ttl, prefs.json())
        return prefs
```

### 4.3 Preference API

```python
# RESTful preference management
@router.put("/users/{user_id}/notification-preferences")
async def update_preferences(
    user_id: UUID,
    preferences: UserPreferenceUpdate,
    current_user: User = Depends(get_current_user)
):
    # Authorization check
    if current_user.id != user_id:
        raise HTTPException(status_code=403)
    
    # Update database
    await preference_service.update_preferences(user_id, preferences)
    
    # Invalidate cache
    await preference_cache.invalidate(user_id)
    
    return {"status": "updated"}
```

---

## 5. Infrastructure Choices

### 5.1 AWS Infrastructure

```yaml
# Infrastructure as Code (Terraform)
resource "aws_sqs_queue" "notification_queue" {
  name = "notification-processing"
  
  # Dead letter queue for failed messages
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notification_dlq.arn
    maxReceiveCount     = 3
  })
  
  # Message retention
  message_retention_seconds = 1209600  # 14 days
  
  # Visibility timeout allows processing time
  visibility_timeout_seconds = 300  # 5 minutes
}

resource "aws_sns_topic" "notification_fanout" {
  name = "notification-events"
}
```

### 5.2 Deployment Architecture

**Container Strategy:** Docker + AWS ECS Fargate
- *Rationale:* Managed container orchestration, auto-scaling
- *Tradeoff:* Higher cost vs. EC2, but reduces operational complexity

**Database Hosting:** AWS RDS PostgreSQL Multi-AZ
- *Configuration:* db.r5.xlarge (4 vCPU, 32GB RAM)
- *Rationale:* Managed service with automatic failover
- *Scaling Plan:* Read replicas for notification preference lookups

**Redis Configuration:** AWS ElastiCache
- *Configuration:* cache.r6g.large (2 vCPU, 13GB RAM)
- *Replication:* Primary + 1 replica for high availability

### 5.3 Monitoring and Observability

```python
# Custom metrics for business monitoring
class NotificationMetrics:
    def __init__(self, cloudwatch_client):
        self.cloudwatch = cloudwatch_client
        
    async def record_delivery_attempt(self, channel: str, success: bool, latency_ms: int):
        await self.cloudwatch.put_metric_data(
            Namespace='NotificationSystem',
            MetricData=[
                {
                    'MetricName': 'DeliveryAttempts',
                    'Dimensions': [
                        {'Name': 'Channel', 'Value': channel},
                        {'Name': 'Success', 'Value': str(success)}
                    ],
                    'Value': 1,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'DeliveryLatency',
                    'Dimensions': [{'Name': 'Channel', 'Value': channel}],
                    'Value': latency_ms,
                    'Unit': 'Milliseconds'
                }
            ]
        )
```

**Key Metrics to Track:**
- Delivery success rate by channel (target: >95%)
- End-to-end latency (target: <30s for high priority)
- Queue depth and processing rate
- User engagement rates by notification type

---

## 6. Failure Handling and Resilience

### 6.1 Retry Logic

```python
class NotificationRetryHandler:
    def __init__(self):
        self.max_retries = {
            NotificationPriority.CRITICAL: 5,
            NotificationPriority.HIGH: 3,
            NotificationPriority.MEDIUM: 2,
            NotificationPriority.LOW: 1
        }
        
    async def process_with_retry(self, notification: Notification):
        max_attempts = self.max_retries[notification.priority]
        
        for attempt in range(1, max_attempts + 1):
            try:
                await self._send_notification(notification)
                return  # Success
                
            except RetryableError as e:
                if attempt == max_attempts:
                    await self._send_to_dlq(notification, str(e))
                    return
                    
                # Exponential backoff: 2^attempt seconds
                await asyncio.sleep(2 ** attempt)
                
            except NonRetryableError as e:
                await self._send_to_dlq(notification, str(e))
                return
```

### 6.2 Circuit Breaker Pattern

```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError()
                
        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
            
