# Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a scalable notification system design for a social app with 10M MAU, deliverable within 6 months by 4 backend engineers. The system prioritizes user engagement while respecting preferences and ensuring reliable delivery across multiple channels.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator
- **Channel Adapters**: Push, Email, In-App, SMS handlers
- **User Preference Engine**: Manages opt-in/out settings
- **Priority Queue System**: Handles batching and throttling
- **Delivery Tracking**: Success/failure monitoring

### Technology Stack
- **Message Queue**: Apache Kafka (handles 10M+ messages/day)
- **Database**: PostgreSQL (user preferences) + Redis (caching/queues)
- **Push Service**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNS)
- **Email**: SendGrid API
- **SMS**: Twilio API
- **Infrastructure**: AWS/GCP with Kubernetes

## 2. Delivery Channels Implementation

### 2.1 Push Notifications
**Primary channel for real-time engagement**

```python
# Priority: High for immediate delivery
# Batch size: 1000 notifications per batch
# Rate limit: 10,000/minute per app

class PushNotificationAdapter:
    def __init__(self):
        self.fcm_client = FCMClient()
        self.apns_client = APNSClient()
        self.batch_size = 1000
    
    def send_batch(self, notifications):
        # Split by platform
        android_batch = [n for n in notifications if n.platform == 'android']
        ios_batch = [n for n in notifications if n.platform == 'ios']
        
        # Send with exponential backoff
        self.send_fcm_batch(android_batch)
        self.send_apns_batch(ios_batch)
```

**Tradeoffs**: 
- ✅ Immediate delivery, high engagement
- ❌ Dependent on device connectivity, user can disable
- **Cost**: ~$0.50 per 1M notifications

### 2.2 Email Notifications
**Batch processing for digest and important updates**

```python
# Priority: Medium for digest, High for critical
# Batch size: 5000 emails per batch
# Rate limit: 100,000/hour (SendGrid limit)

class EmailAdapter:
    def __init__(self):
        self.sendgrid = SendGridAPIClient()
        self.batch_size = 5000
        
    def process_digest_batch(self, user_notifications):
        # Group notifications by user for digest
        user_digests = self.create_daily_digest(user_notifications)
        self.send_batch(user_digests)
```

**Tradeoffs**:
- ✅ High deliverability, detailed content possible
- ❌ Lower engagement rates (~20%), delayed delivery acceptable
- **Cost**: ~$0.95 per 1K emails

### 2.3 In-App Notifications
**Persistent notifications within app**

```python
# Priority: Low (user pulls when app opens)
# Storage: 30 days retention
# Real-time: WebSocket for active users

class InAppNotificationService:
    def store_notification(self, user_id, notification):
        # Store in PostgreSQL with 30-day TTL
        self.db.execute(
            "INSERT INTO in_app_notifications (user_id, content, created_at) VALUES (%s, %s, %s)",
            (user_id, notification.content, datetime.now())
        )
        
        # Push to active WebSocket connections
        if user_id in self.active_connections:
            self.websocket_manager.send_to_user(user_id, notification)
```

**Tradeoffs**:
- ✅ 100% delivery guarantee, rich UI possible
- ❌ Only visible when user opens app
- **Cost**: Minimal (database storage)

### 2.4 SMS Notifications
**Critical alerts only (security, urgent updates)**

```python
# Priority: Highest for critical alerts
# Rate limit: 1 SMS per user per hour for non-critical
# Cost consideration: $0.0075 per SMS

class SMSAdapter:
    def __init__(self):
        self.twilio = TwilioClient()
        self.critical_types = ['security_alert', 'account_locked']
        
    def should_send_sms(self, notification):
        return (notification.type in self.critical_types or 
                self.user_explicitly_opted_in(notification.user_id))
```

**Tradeoffs**:
- ✅ Highest deliverability, works without internet
- ❌ Expensive, character limits, regulatory restrictions
- **Cost**: ~$75K/month for 10M users (assuming 1 SMS/user/month)

## 3. Priority and Batching Logic

### 3.1 Priority Classification

```python
class NotificationPriority:
    CRITICAL = 1    # Security alerts, system issues
    HIGH = 2        # Friend requests, mentions, likes
    MEDIUM = 3      # Daily digest, recommendations
    LOW = 4         # Marketing, tips

class PriorityQueue:
    def __init__(self):
        self.queues = {
            1: [],  # Process immediately
            2: [],  # Process within 5 minutes
            3: [],  # Process within 1 hour
            4: []   # Process within 24 hours
        }
```

### 3.2 Batching Strategy

```python
class BatchProcessor:
    def __init__(self):
        self.batch_configs = {
            'push': {'size': 1000, 'timeout': 30},      # 30 seconds max wait
            'email': {'size': 5000, 'timeout': 300},    # 5 minutes max wait
            'sms': {'size': 100, 'timeout': 60},        # 1 minute max wait
            'in_app': {'size': 10000, 'timeout': 60}    # 1 minute max wait
        }
    
    def should_flush_batch(self, channel, batch):
        config = self.batch_configs[channel]
        return (len(batch) >= config['size'] or 
                time.time() - batch.created_at > config['timeout'])
```

**Batching Benefits**:
- Reduces API calls by 90%
- Improves throughput from 1K to 50K notifications/minute
- Enables digest creation for email

## 4. User Preference Management

### 4.1 Database Schema

```sql
-- User notification preferences
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    in_app_enabled BOOLEAN DEFAULT true,
    
    -- Granular preferences
    friend_requests_push BOOLEAN DEFAULT true,
    mentions_email BOOLEAN DEFAULT true,
    digest_email BOOLEAN DEFAULT true,
    marketing_email BOOLEAN DEFAULT false,
    
    -- Quiet hours (user's timezone)
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50),
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Notification type configurations
CREATE TABLE notification_types (
    type_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100),
    default_channels TEXT[], -- ['push', 'in_app']
    user_configurable BOOLEAN DEFAULT true,
    respect_quiet_hours BOOLEAN DEFAULT true
);
```

### 4.2 Preference Engine

```python
class PreferenceEngine:
    def __init__(self):
        self.cache = Redis()
        self.cache_ttl = 3600  # 1 hour
    
    def get_user_preferences(self, user_id):
        # Check cache first
        cached = self.cache.get(f"prefs:{user_id}")
        if cached:
            return json.loads(cached)
            
        # Fetch from database
        prefs = self.db.fetch_user_preferences(user_id)
        self.cache.setex(f"prefs:{user_id}", self.cache_ttl, json.dumps(prefs))
        return prefs
    
    def should_send_notification(self, user_id, notification):
        prefs = self.get_user_preferences(user_id)
        
        # Check if user opted out of this channel
        if not prefs.get(f"{notification.channel}_enabled", True):
            return False
            
        # Check quiet hours
        if self.is_quiet_hours(user_id, prefs):
            return notification.priority == NotificationPriority.CRITICAL
            
        # Check specific notification type preferences
        pref_key = f"{notification.type}_{notification.channel}"
        return prefs.get(pref_key, True)
```

### 4.3 Preference API

```python
@app.route('/api/v1/users/<user_id>/notification-preferences', methods=['PUT'])
def update_preferences(user_id):
    """
    Update user notification preferences
    Supports granular control per notification type and channel
    """
    data = request.json
    
    # Validate preferences
    valid_prefs = PreferenceValidator.validate(data)
    
    # Update database
    PreferenceService.update_user_preferences(user_id, valid_prefs)
    
    # Invalidate cache
    cache.delete(f"prefs:{user_id}")
    
    return {"status": "updated"}
```

## 5. Infrastructure Choices

### 5.1 Message Queue Architecture

**Choice: Apache Kafka**
```yaml
# Kafka Configuration
topics:
  notifications-high-priority:
    partitions: 12
    replication-factor: 3
    retention: 7d
  notifications-medium-priority:
    partitions: 6
    replication-factor: 3
    retention: 3d
  notifications-low-priority:
    partitions: 3
    replication-factor: 3
    retention: 1d
```

**Why Kafka over alternatives**:
- ✅ Handles 10M+ messages/day easily
- ✅ Built-in partitioning for parallel processing
- ✅ Message persistence for replay capability
- ❌ More complex than SQS/RabbitMQ
- **Alternative considered**: AWS SQS (simpler but less throughput)

### 5.2 Database Strategy

**Primary Database: PostgreSQL**
```sql
-- Optimized for read-heavy workload
CREATE INDEX idx_user_prefs_user_id ON user_notification_preferences(user_id);
CREATE INDEX idx_notifications_user_created ON in_app_notifications(user_id, created_at);

-- Partitioning for in-app notifications
CREATE TABLE in_app_notifications (
    id BIGSERIAL,
    user_id BIGINT,
    content JSONB,
    created_at TIMESTAMP,
    read_at TIMESTAMP
) PARTITION BY RANGE (created_at);
```

**Caching Layer: Redis**
```python
# Cache Strategy
USER_PREFERENCES_TTL = 3600  # 1 hour
NOTIFICATION_BATCH_TTL = 300  # 5 minutes
RATE_LIMIT_TTL = 3600  # 1 hour for rate limiting
```

**Tradeoffs**:
- ✅ PostgreSQL: ACID compliance, complex queries, JSON support
- ✅ Redis: Sub-millisecond reads, built-in data structures
- ❌ Two systems to maintain vs single NoSQL solution
- **Cost**: ~$2K/month for required capacity

### 5.3 Service Architecture

```yaml
# Microservices Deployment
services:
  notification-orchestrator:
    replicas: 3
    resources:
      cpu: 500m
      memory: 1Gi
    
  channel-adapters:
    push-adapter:
      replicas: 2
      resources:
        cpu: 200m
        memory: 512Mi
    email-adapter:
      replicas: 2
    sms-adapter:
      replicas: 1
    
  preference-service:
    replicas: 2
    resources:
      cpu: 300m
      memory: 512Mi
```

## 6. Failure Handling Strategy

### 6.1 Retry Logic

```python
class RetryHandler:
    def __init__(self):
        self.max_retries = {
            'push': 3,
            'email': 5,
            'sms': 3,
            'in_app': 1  # No retry needed, stored in DB
        }
        self.backoff_multiplier = 2
        self.initial_delay = 1  # second
    
    async def send_with_retry(self, adapter, notification):
        max_retries = self.max_retries[notification.channel]
        
        for attempt in range(max_retries + 1):
            try:
                result = await adapter.send(notification)
                self.log_success(notification, attempt)
                return result
                
            except TemporaryError as e:
                if attempt < max_retries:
                    delay = self.initial_delay * (self.backoff_multiplier ** attempt)
                    await asyncio.sleep(delay)
                    continue
                else:
                    self.handle_permanent_failure(notification, e)
                    
            except PermanentError as e:
                self.handle_permanent_failure(notification, e)
                break
```

### 6.2 Dead Letter Queue

```python
class DeadLetterHandler:
    def __init__(self):
        self.dlq_topic = "notifications-failed"
        self.max_dlq_retention = 30  # days
    
    def handle_failed_notification(self, notification, error):
        failed_notification = {
            'original_notification': notification,
            'error': str(error),
            'failed_at': datetime.utcnow(),
            'retry_count': notification.get('retry_count', 0)
        }
        
        # Send to DLQ for manual investigation
        self.kafka_producer.send(self.dlq_topic, failed_notification)
        
        # Alert if failure rate exceeds threshold
        if self.get_failure_rate() > 0.05:  # 5% threshold
            self.alert_service.send_alert("High notification failure rate detected")
```

### 6.3 Circuit Breaker Pattern

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpenError()
        
        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
    
    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
```

### 6.4 Monitoring and Alerting

```python
# Key Metrics to Monitor
NOTIFICATION_METRICS = {
    'delivery_rate': {
        'target': 0.95,  # 95% delivery rate
        'alert_threshold': 0.90
    },
    'processing_latency': {
        'target_p95': 30,  # seconds
        'alert_threshold': 60
    },
    'queue_depth': {
        'target': 1000,
        'alert_threshold': 10000
    },
    'error_rate': {
        'target': 0.02,  # 2% error rate
        'alert_threshold': 0.05
    }
}
```

## 7. Implementation Timeline (6 