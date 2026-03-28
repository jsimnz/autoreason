# Notification System Design for Social App (10M MAU) - Final Version

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. The design balances pragmatic technology choices for rapid development with architectural decisions that ensure reliable operation at scale. Key improvements include Apache Kafka for message queuing, optimized database partitioning, and realistic delivery targets that align with our 6-month timeline and 4-engineer team constraint.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator for all notifications
- **Apache Kafka**: Distributed message streaming platform for reliable queuing
- **Channel Handlers**: Specialized processors with per-channel circuit breakers
- **User Preference Engine**: Partitioned preference management with bitmask optimization
- **Distributed Rate Limiter**: Redis-based sliding window implementation
- **Analytics & Monitoring**: Tracks delivery rates and user engagement

### Technology Stack Decisions

**Message Queue**: Apache Kafka (Amazon MSK)
- *Rationale*: Kafka's partitioning enables horizontal scaling beyond Redis Streams' single-threaded bottleneck; MSK reduces operational overhead for our 4-person team
- *Configuration*: 12 partitions across 3 brokers, consumer groups for parallel processing
- *Tradeoff*: Slightly more complex than Redis but essential for 10M user scale

**Database**: PostgreSQL with table partitioning + Redis cache
- *Rationale*: Partition user preferences by user_id hash to distribute load; separate Redis clusters for different use cases
- *Configuration*: 16 partitions for preferences table, dedicated Redis for rate limiting
- *Tradeoff*: More setup complexity but necessary for query performance at scale

**Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- *Rationale*: Managed services reduce operational overhead for small team
- *Tradeoff*: Vendor lock-in but significant time savings

**Email**: Amazon SES
- *Rationale*: Cost-effective at scale, good deliverability, team can implement quickly
- *Tradeoff*: Less feature-rich than specialized providers but sufficient for MVP

**SMS**: Twilio
- *Rationale*: Reliable global coverage, straightforward API
- *Tradeoff*: Higher cost but premium channel justifies expense

**Rate Limiting**: Dedicated Redis cluster with sliding window algorithm
- *Rationale*: Sliding window counters prevent memory explosion from per-user TokenBucket instances
- *Tradeoff*: Additional infrastructure but essential for preventing user notification fatigue

## 2. Message Queue Architecture

### Kafka Topic Structure
```python
KAFKA_TOPICS = {
    'notifications.critical': {
        'partitions': 4,
        'replication_factor': 3,
        'retention_ms': 86400000  # 24 hours
    },
    'notifications.high': {
        'partitions': 8, 
        'replication_factor': 3,
        'retention_ms': 86400000
    },
    'notifications.medium': {
        'partitions': 12,
        'replication_factor': 3, 
        'retention_ms': 86400000
    },
    'notifications.low': {
        'partitions': 6,
        'replication_factor': 3,
        'retention_ms': 86400000
    }
}

class KafkaNotificationProducer:
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers=['kafka-1:9092', 'kafka-2:9092', 'kafka-3:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            partitioner=self._user_id_partitioner,
            batch_size=16384,  # 16KB batches for efficiency
            linger_ms=10       # Max 10ms batching delay
        )
    
    def _user_id_partitioner(self, key, all_partitions, available_partitions):
        """Partition by user_id to maintain ordering per user"""
        if key is None:
            return random.choice(available_partitions)
        return hash(key) % len(all_partitions)
```

### Consumer Group Configuration
```python
class NotificationConsumer:
    def __init__(self, consumer_group: str):
        self.consumer = KafkaConsumer(
            'notifications.critical',
            'notifications.high', 
            'notifications.medium',
            'notifications.low',
            group_id=consumer_group,
            bootstrap_servers=['kafka-1:9092', 'kafka-2:9092', 'kafka-3:9092'],
            auto_offset_reset='latest',
            enable_auto_commit=False,  # Manual commit after processing
            max_poll_records=50,       # Smaller batches for better error isolation
            consumer_timeout_ms=10000
        )
```

## 3. Database Schema

### Partitioned User Preferences
```sql
CREATE TABLE user_notification_preferences (
    user_id UUID NOT NULL,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    quiet_hours_start INTEGER DEFAULT 22,  -- Hour in user's timezone (0-23)
    quiet_hours_end INTEGER DEFAULT 8,
    timezone_offset INTEGER DEFAULT 0,     -- Minutes from UTC
    
    -- Optimized granular preferences using bitmasks
    push_categories INTEGER DEFAULT 7,     -- Bitmask: 1=DM, 2=mentions, 4=likes
    email_categories INTEGER DEFAULT 3,    -- Bitmask: 1=digest, 2=security  
    sms_categories INTEGER DEFAULT 2,      -- Bitmask: 1=security, 2=critical
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (user_id)
) PARTITION BY HASH (user_id);

-- Create 16 partitions for horizontal scaling
DO $$
BEGIN
    FOR i IN 0..15 LOOP
        EXECUTE format('CREATE TABLE user_notification_preferences_p%s PARTITION OF user_notification_preferences FOR VALUES WITH (modulus 16, remainder %s)', i, i);
    END LOOP;
END $$;

CREATE INDEX CONCURRENTLY ON user_notification_preferences (push_enabled) WHERE push_enabled = true;
CREATE INDEX CONCURRENTLY ON user_notification_preferences (email_enabled) WHERE email_enabled = true;
CREATE INDEX CONCURRENTLY ON user_notification_preferences (sms_enabled) WHERE sms_enabled = true;
```

### Notification Deduplication Table
```sql
CREATE TABLE notification_dedup (
    dedup_key VARCHAR(255) PRIMARY KEY,
    user_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Deduplication key: hash(user_id + notification_type + content_hash + date)
```

## 4. Delivery Channels Implementation

### Push Notifications with Circuit Breaker
```python
# Priority: High (real-time engagement)
# Volume: ~2M daily notifications  
# Delivery SLA: 95% within 2 minutes

class EnhancedPushNotificationHandler:
    def __init__(self):
        self.fcm_client = FCMClient()
        self.apns_client = APNsClient()
        self.circuit_breaker = ChannelCircuitBreaker('push_notifications')
        self.deduplicator = NotificationDeduplicator()
        
    async def send_batch(self, notifications: List[PushNotification]):
        if await self.circuit_breaker.is_open():
            raise CircuitBreakerOpenError("Push notification circuit breaker is open")
        
        # Filter duplicates before processing
        deduplicated = await self.deduplicator.filter_duplicates(notifications)
        
        try:
            # Batch size: 50 notifications per request (reduced for better error isolation)
            for batch in chunks(deduplicated, 50):
                await self._send_platform_batch(batch)
            
            await self.circuit_breaker.record_success()
            
        except Exception as e:
            await self.circuit_breaker.record_failure()
            raise e
```

### Email Notifications
```python
# Priority: Medium (engagement & retention)
# Volume: ~500K daily emails
# Delivery SLA: 95% within 10 minutes

class EmailHandler:
    def __init__(self):
        self.ses_client = SESClient()
        self.template_engine = JinjaTemplateEngine()
        self.circuit_breaker = ChannelCircuitBreaker('email')
        
    async def send_batch(self, notifications: List[EmailNotification]):
        if await self.circuit_breaker.is_open():
            raise CircuitBreakerOpenError("Email circuit breaker is open")
            
        # Batch size: 50 emails per SES request
        # Rate limit: 14 emails/second (SES default limit)
        for batch in chunks(notifications, 50):
            await self._send_batch_with_rate_limit(batch)
```

### SMS Notifications  
```python
# Priority: Critical (security, urgent alerts)
# Volume: ~50K daily SMS
# Delivery SLA: 95% within 2 minutes

class SMSHandler:
    def __init__(self):
        self.twilio_client = TwilioClient()
        self.circuit_breaker = ChannelCircuitBreaker('sms')
        self.rate_limiter = DistributedRateLimiter()
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

## 5. Priority and Batching Logic

### Realistic Priority Levels and SLAs
```python
class NotificationPriority(Enum):
    CRITICAL = 1    # Security alerts, payment issues
    HIGH = 2        # Direct messages, mentions  
    MEDIUM = 3      # Likes, follows, recommendations
    LOW = 4         # Weekly digests, marketing

DELIVERY_SLAS = {
    NotificationPriority.CRITICAL: {
        'target_latency': '30 seconds',
        'batch_size': 10,
        'max_delay': 10
    },
    NotificationPriority.HIGH: {
        'target_latency': '2 minutes',
        'batch_size': 50,
        'max_delay': 60
    },
    NotificationPriority.MEDIUM: {
        'target_latency': '10 minutes',
        'batch_size': 200,
        'max_delay': 300
    },
    NotificationPriority.LOW: {
        'target_latency': '4 hours',
        'batch_size': 500,
        'max_delay': 1800
    }
}
```

### Batching Strategy
```python
class BatchingEngine:
    def __init__(self):
        self.batch_configs = DELIVERY_SLAS
    
    async def process_queue(self, priority: NotificationPriority):
        config = self.batch_configs[priority]
        batch = await self.collect_batch(priority, config['batch_size'], config['max_delay'])
        await self.delivery_service.send_batch(batch)
```

## 6. Rate Limiting - Distributed Implementation

### Sliding Window Rate Limiter
```python
class DistributedRateLimiter:
    def __init__(self):
        self.redis = redis.RedisCluster(
            startup_nodes=[
                {"host": "rate-limit-redis-1", "port": "6379"},
                {"host": "rate-limit-redis-2", "port": "6379"}, 
                {"host": "rate-limit-redis-3", "port": "6379"}
            ],
            decode_responses=True,
            skip_full_coverage_check=True
        )
        
        # Conservative rate limits to prevent user fatigue
        self.limits = {
            'push': {'count': 20, 'window': 3600},      # 20 per hour
            'email': {'count': 5, 'window': 86400},     # 5 per day  
            'sms': {'count': 3, 'window': 86400}        # 3 per day
        }
    
    async def check_rate_limit(self, user_id: str, channel: str) -> bool:
        """Sliding window rate limiter using Redis sorted sets"""
        limit_config = self.limits[channel]
        key = f"rate_limit:{channel}:{user_id}"
        now = time.time()
        window_start = now - limit_config['window']
        
        pipe = self.redis.pipeline()
        
        # Remove expired entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current entries in window
        pipe.zcard(key)
        
        # Add current timestamp
        pipe.zadd(key, {str(now): now})
        
        # Set expiry
        pipe.expire(key, limit_config['window'])
        
        results = await pipe.execute()
        current_count = results[1]
        
        return current_count < limit_config['count']
```

## 7. User Preference Management - Optimized

### Simplified Preference Engine
```python
class OptimizedPreferenceEngine:
    def __init__(self):
        self.cache = RedisClient(host='preference-cache-redis')
        self.db = PostgresClient()
    
    async def should_deliver(self, notification: Notification) -> Dict[str, bool]:
        prefs = await self.get_user_preferences(notification.user_id)
        
        # Simplified channel checks using bitmasks
        channels = {
            'push': prefs.push_enabled and self._check_bitmask(prefs.push_categories, notification.category),
            'email': prefs.email_enabled and self._check_bitmask(prefs.email_categories, notification.category),
            'sms': prefs.sms_enabled and self._check_bitmask(prefs.sms_categories, notification.category)
        }
        
        # Apply quiet hours (simplified timezone handling)
        if self._in_quiet_hours(prefs) and notification.priority != NotificationPriority.CRITICAL:
            channels['push'] = False
            if notification.priority not in [NotificationPriority.CRITICAL, NotificationPriority.HIGH]:
                channels['sms'] = False
        
        return channels
    
    def _check_bitmask(self, user_categories: int, notification_category: int) -> bool:
        """Simple bitmask check for better performance"""
        return bool(user_categories & notification_category)
    
    def _in_quiet_hours(self, prefs: UserPreferences) -> bool:
        """Simplified quiet hours using user's timezone offset"""
        user_hour = (datetime.utcnow().hour + (prefs.timezone_offset // 60)) % 24
        
        if prefs.quiet_hours_start <= prefs.quiet_hours_end:
            return prefs.quiet_hours_start <= user_hour < prefs.quiet_hours_end
        else:  # Quiet hours span midnight
            return user_hour >= prefs.quiet_hours_start or user_hour < prefs.quiet_hours_end
    
    async def get_user_preferences(self, user_id: str) -> UserPreferences:
        # Longer cache TTL since preferences change infrequently
        cached = await self.cache.get(f"prefs:{user_id}")
        if cached:
            return UserPreferences.from_dict(cached)
        
        # Query partitioned table
        prefs = await self.db.get_user_preferences(user_id)
        if prefs:
            await self.cache.setex(f"prefs:{user_id}", 7200, prefs.to_dict())  #