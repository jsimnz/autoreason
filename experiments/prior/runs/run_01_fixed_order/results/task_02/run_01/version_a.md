# Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 6-month timeline and 4-engineer team constraint, we prioritize pragmatic infrastructure choices and phased delivery to ensure reliable operation while maintaining development velocity.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator for all notifications
- **Channel Handlers**: Specialized processors for each delivery method
- **User Preference Engine**: Manages opt-in/opt-out rules
- **Priority Queue System**: Handles batching and rate limiting
- **Analytics & Monitoring**: Tracks delivery rates and user engagement

### Technology Stack Decisions

**Message Queue**: Redis Streams + Redis Cluster
- *Rationale*: Team likely familiar with Redis; handles 10M scale with proper clustering
- *Tradeoff*: Less sophisticated than Kafka but faster to implement and operate

**Database**: PostgreSQL primary + Redis cache
- *Rationale*: Mature ecosystem, team expertise, handles complex preference queries
- *Tradeoff*: May need read replicas for scale but simpler than distributed databases

**Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- *Rationale*: Managed services reduce operational overhead
- *Tradeoff*: Vendor lock-in but significant time savings

**Email**: Amazon SES
- *Rationale*: Cost-effective at scale, good deliverability
- *Tradeoff*: Less feature-rich than specialized providers like SendGrid

**SMS**: Twilio
- *Rationale*: Reliable global coverage, straightforward API
- *Tradeoff*: Higher cost but premium channel justifies expense

## 2. Delivery Channels Implementation

### Push Notifications
```python
# Priority: High (real-time engagement)
# Volume: ~2M daily notifications
# Delivery SLA: 95% within 30 seconds

class PushNotificationHandler:
    def __init__(self):
        self.fcm_client = FCMClient()
        self.apns_client = APNsClient()
        self.rate_limiter = TokenBucket(rate=10000/hour)
    
    async def send_batch(self, notifications: List[PushNotification]):
        # Batch size: 100 notifications per request
        for batch in chunks(notifications, 100):
            await self._send_platform_batch(batch)
```

### Email Notifications
```python
# Priority: Medium (engagement & retention)
# Volume: ~500K daily emails
# Delivery SLA: 95% within 5 minutes

class EmailHandler:
    def __init__(self):
        self.ses_client = SESClient()
        self.template_engine = JinjaTemplateEngine()
        
    async def send_batch(self, notifications: List[EmailNotification]):
        # Batch size: 50 emails per SES request
        # Rate limit: 14 emails/second (SES default limit)
```

### In-App Notifications
```python
# Priority: Low (persistent, user-initiated)
# Volume: ~1M daily notifications
# Delivery: Real-time via WebSocket + polling fallback

class InAppHandler:
    def __init__(self):
        self.websocket_manager = WebSocketManager()
        self.postgres_client = PostgresClient()
    
    async def deliver(self, notification: InAppNotification):
        # Store in database for persistence
        await self.postgres_client.store_notification(notification)
        # Attempt real-time delivery
        await self.websocket_manager.send_to_user(notification.user_id, notification)
```

### SMS Notifications
```python
# Priority: Critical (security, urgent alerts)
# Volume: ~50K daily SMS
# Delivery SLA: 95% within 2 minutes

class SMSHandler:
    def __init__(self):
        self.twilio_client = TwilioClient()
        self.rate_limiter = TokenBucket(rate=100/second)
```

## 3. Priority and Batching Logic

### Priority Levels
```python
class NotificationPriority(Enum):
    CRITICAL = 1    # Security alerts, payment issues (immediate)
    HIGH = 2        # Direct messages, mentions (within 30s)
    MEDIUM = 3      # Likes, follows, recommendations (within 5 min)
    LOW = 4         # Weekly digests, marketing (within 1 hour)
```

### Batching Strategy
```python
class BatchingEngine:
    def __init__(self):
        self.batch_configs = {
            NotificationPriority.CRITICAL: BatchConfig(size=1, max_delay=0),
            NotificationPriority.HIGH: BatchConfig(size=100, max_delay=30),
            NotificationPriority.MEDIUM: BatchConfig(size=500, max_delay=300),
            NotificationPriority.LOW: BatchConfig(size=1000, max_delay=3600)
        }
    
    async def process_queue(self, priority: NotificationPriority):
        config = self.batch_configs[priority]
        batch = await self.collect_batch(priority, config.size, config.max_delay)
        await self.delivery_service.send_batch(batch)
```

### Rate Limiting Implementation
```python
class RateLimiter:
    def __init__(self):
        # Per-channel rate limits to prevent overwhelming users
        self.limits = {
            'push': TokenBucket(rate=10/hour, burst=5),
            'email': TokenBucket(rate=3/day, burst=2),
            'sms': TokenBucket(rate=5/day, burst=3)
        }
    
    async def check_user_rate_limit(self, user_id: str, channel: str) -> bool:
        user_bucket = await self.get_user_bucket(user_id, channel)
        return user_bucket.consume(1)
```

## 4. User Preference Management

### Preference Schema
```sql
CREATE TABLE user_notification_preferences (
    user_id UUID PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- Granular preferences
    push_direct_messages BOOLEAN DEFAULT true,
    push_mentions BOOLEAN DEFAULT true,
    push_likes BOOLEAN DEFAULT false,
    email_digest BOOLEAN DEFAULT true,
    email_marketing BOOLEAN DEFAULT false,
    sms_security BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_prefs_channels ON user_notification_preferences 
    (push_enabled, email_enabled, sms_enabled);
```

### Preference Engine
```python
class PreferenceEngine:
    def __init__(self):
        self.cache = RedisClient()
        self.db = PostgresClient()
    
    async def should_deliver(self, notification: Notification) -> Dict[str, bool]:
        prefs = await self.get_user_preferences(notification.user_id)
        
        # Check global channel preferences
        channels = {}
        channels['push'] = prefs.push_enabled and self._check_category_pref(prefs, 'push', notification.category)
        channels['email'] = prefs.email_enabled and self._check_category_pref(prefs, 'email', notification.category)
        channels['sms'] = prefs.sms_enabled and self._check_category_pref(prefs, 'sms', notification.category)
        
        # Apply quiet hours
        if self._in_quiet_hours(prefs):
            if notification.priority != NotificationPriority.CRITICAL:
                channels['push'] = False
                channels['sms'] = False
        
        return channels
    
    async def get_user_preferences(self, user_id: str) -> UserPreferences:
        # Try cache first
        cached = await self.cache.get(f"prefs:{user_id}")
        if cached:
            return UserPreferences.from_dict(cached)
        
        # Fallback to database
        prefs = await self.db.get_user_preferences(user_id)
        await self.cache.setex(f"prefs:{user_id}", 3600, prefs.to_dict())
        return prefs
```

### Preference Management API
```python
@app.post("/api/v1/users/{user_id}/notification-preferences")
async def update_preferences(user_id: str, preferences: PreferenceUpdate):
    # Validate preferences
    validated_prefs = await validate_preferences(preferences)
    
    # Update database
    await db.update_user_preferences(user_id, validated_prefs)
    
    # Invalidate cache
    await cache.delete(f"prefs:{user_id}")
    
    return {"status": "success"}

@app.get("/api/v1/users/{user_id}/notification-preferences")
async def get_preferences(user_id: str):
    prefs = await preference_engine.get_user_preferences(user_id)
    return prefs.to_api_response()
```

## 5. Infrastructure Architecture

### Core Services Deployment
```yaml
# docker-compose.yml for development/staging
version: '3.8'
services:
  notification-service:
    image: social-app/notification-service
    replicas: 3
    environment:
      - REDIS_CLUSTER_NODES=redis-1:6379,redis-2:6379,redis-3:6379
      - DATABASE_URL=postgresql://user:pass@postgres:5432/notifications
    resources:
      limits:
        memory: 1GB
        cpu: 0.5
  
  redis-cluster:
    image: redis:7-alpine
    deploy:
      replicas: 3
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf
  
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: notifications
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

### Production Infrastructure (AWS)
```terraform
# Simplified Terraform configuration
resource "aws_ecs_cluster" "notification_cluster" {
  name = "notification-system"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_service" "notification_service" {
  name            = "notification-service"
  cluster         = aws_ecs_cluster.notification_cluster.id
  task_definition = aws_ecs_task_definition.notification_task.arn
  desired_count   = 3
  
  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
  }
}

resource "aws_elasticache_replication_group" "redis_cluster" {
  replication_group_id         = "notification-redis"
  description                  = "Redis cluster for notifications"
  
  num_cache_clusters         = 3
  node_type                 = "cache.r6g.large"
  port                      = 6379
  parameter_group_name      = "default.redis7"
  
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
}
```

### Scaling Considerations
- **Horizontal scaling**: ECS auto-scaling based on CPU/memory utilization
- **Database scaling**: Read replicas for preference lookups, connection pooling
- **Redis scaling**: Cluster mode with 3 master nodes, 6 total nodes for redundancy
- **Queue scaling**: Redis Streams with consumer groups for parallel processing

## 6. Failure Handling & Reliability

### Retry Mechanisms
```python
class RetryHandler:
    def __init__(self):
        self.max_retries = {
            'push': 3,
            'email': 5,
            'sms': 3,
            'in_app': 2
        }
        self.backoff_strategy = ExponentialBackoff(base=2, max_delay=300)
    
    async def send_with_retry(self, notification: Notification, channel: str):
        for attempt in range(self.max_retries[channel]):
            try:
                result = await self.channel_handlers[channel].send(notification)
                await self.analytics.record_success(notification, channel, attempt + 1)
                return result
            except RetryableError as e:
                if attempt == self.max_retries[channel] - 1:
                    await self.dead_letter_queue.send(notification, channel, str(e))
                    await self.analytics.record_failure(notification, channel, str(e))
                    break
                
                delay = self.backoff_strategy.calculate_delay(attempt)
                await asyncio.sleep(delay)
            except NonRetryableError as e:
                await self.dead_letter_queue.send(notification, channel, str(e))
                await self.analytics.record_failure(notification, channel, str(e))
                break
```

### Dead Letter Queue Processing
```python
class DeadLetterProcessor:
    def __init__(self):
        self.dlq = RedisQueue("notification_dlq")
        self.alert_service = AlertService()
    
    async def process_failed_notifications(self):
        while True:
            failed_batch = await self.dlq.get_batch(100)
            
            for failed_notification in failed_batch:
                # Log for debugging
                logger.error(f"Failed notification: {failed_notification}")
                
                # Alert if critical notification failed
                if failed_notification.priority == NotificationPriority.CRITICAL:
                    await self.alert_service.send_alert(
                        f"Critical notification failed: {failed_notification.id}"
                    )
                
                # Store in database for manual review
                await self.db.store_failed_notification(failed_notification)
            
            await asyncio.sleep(60)  # Process every minute
```

### Circuit Breaker Pattern
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
                raise CircuitBreakerOpenError("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
```

### Monitoring & Alerting
```python
class NotificationMetrics:
    def __init__(self):
        self.prometheus = PrometheusClient()
        self.datadog = DatadogClient()
    
    def record_notification_sent(self, channel: str, priority: str, success: bool):
        self.prometheus.increment('notifications_sent_total', 
                                tags={'channel': channel, 'priority': priority, 'success': success})
    
    def record_delivery_latency(self, channel: str, latency_ms: int):
        self.prometheus.histogram('notification_delivery_latency_ms', 
                                latency_ms, tags={'channel': channel})
    
    def record_queue_depth(self, priority: str, depth: int):
        self.prometheus.gauge('notification_queue_depth', depth, tags={'priority': priority})

# Alert thresholds
ALERTS = {
    'high_failure_rate': 'notifications_sent_total{success="false"} / notifications_sent_total > 0.05',
    'queue_backup': '