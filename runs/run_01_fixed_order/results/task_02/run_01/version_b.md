# Revised Notification System Design for Social App (10M MAU)

## Executive Summary

This revised proposal addresses critical scalability and architectural issues identified in the original design. Key changes include adopting Apache Kafka for message queuing, implementing proper database partitioning, redesigning rate limiting for scale, and establishing realistic delivery targets that align with resource constraints and team capacity.

## 1. System Architecture Overview - REVISED

### Core Components
- **Notification Service**: Central orchestrator (unchanged)
- **Apache Kafka**: Distributed message streaming platform (CHANGED)
- **Channel Handlers**: Specialized processors with per-channel circuit breakers (ENHANCED)
- **User Preference Engine**: Partitioned preference management (ENHANCED)
- **Distributed Rate Limiter**: Redis-based sliding window implementation (CHANGED)
- **Analytics & Monitoring**: Asynchronous event collection (ENHANCED)

### Technology Stack Decisions - REVISED

**Message Queue**: Apache Kafka (MSK)
- *Problem Fixed*: Redis Streams single-threaded bottleneck and lack of horizontal scaling
- *Rationale*: Kafka partitions enable horizontal scaling; MSK reduces operational overhead
- *Configuration*: 12 partitions across 3 brokers for notification topics

**Database**: PostgreSQL with table partitioning + Redis for rate limiting only
- *Problem Fixed*: Preference table scalability and Redis resource contention
- *Rationale*: Partition preferences by user_id hash; separate Redis for rate limiting
- *Configuration*: 16 partitions for user preferences table

**Rate Limiting**: Dedicated Redis cluster with sliding window algorithm
- *Problem Fixed*: Memory explosion from per-user TokenBucket instances
- *Rationale*: Sliding window counters in Redis with TTL-based cleanup
- *Configuration*: 3-node Redis cluster dedicated to rate limiting

## 2. Message Queue Architecture - NEW

### Kafka Topic Structure
```python
# Problem Fixed: Single-stream bottleneck and lack of proper partitioning strategy
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
            batch_size=16384,  # 16KB batches
            linger_ms=10       # Max 10ms batching delay
        )
    
    def _user_id_partitioner(self, key, all_partitions, available_partitions):
        """Partition by user_id to maintain ordering per user"""
        if key is None:
            return random.choice(available_partitions)
        return hash(key) % len(all_partitions)
    
    async def send_notification(self, notification: Notification):
        topic = f"notifications.{notification.priority.name.lower()}"
        await self.producer.send(
            topic, 
            value=notification.to_dict(),
            key=notification.user_id
        )
```

### Consumer Group Configuration
```python
# Problem Fixed: Proper scaling and failure handling for queue processing
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
            max_poll_records=100,      # Process in smaller batches
            consumer_timeout_ms=10000
        )
    
    async def process_messages(self):
        for message in self.consumer:
            try:
                notification = Notification.from_dict(json.loads(message.value))
                await self.process_notification(notification)
                self.consumer.commit()  # Commit only after successful processing
            except Exception as e:
                logger.error(f"Failed to process notification: {e}")
                # Message stays uncommitted and will be redelivered
```

## 3. Database Schema - REVISED

### Partitioned User Preferences
```sql
-- Problem Fixed: Single table scalability for 10M users
CREATE TABLE user_notification_preferences (
    user_id UUID NOT NULL,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true, 
    sms_enabled BOOLEAN DEFAULT false,
    quiet_hours_start INTEGER DEFAULT 22,  -- Hour in user's timezone (0-23)
    quiet_hours_end INTEGER DEFAULT 8,
    timezone_offset INTEGER DEFAULT 0,     -- Minutes from UTC
    
    -- Simplified granular preferences (reduce query complexity)
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

-- Indexes on each partition
CREATE INDEX CONCURRENTLY ON user_notification_preferences (push_enabled) WHERE push_enabled = true;
CREATE INDEX CONCURRENTLY ON user_notification_preferences (email_enabled) WHERE email_enabled = true;
CREATE INDEX CONCURRENTLY ON user_notification_preferences (sms_enabled) WHERE sms_enabled = true;
```

### Notification Deduplication Table
```sql
-- Problem Fixed: Missing deduplication logic
CREATE TABLE notification_dedup (
    dedup_key VARCHAR(255) PRIMARY KEY,
    user_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Create monthly partitions with automatic cleanup
CREATE TABLE notification_dedup_current PARTITION OF notification_dedup 
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Deduplication key: hash(user_id + notification_type + content_hash + date)
```

## 4. Rate Limiting - REDESIGNED

### Distributed Sliding Window Rate Limiter
```python
# Problem Fixed: Memory explosion and lack of persistence for rate limits
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
    
    async def increment_counter(self, user_id: str, channel: str):
        """Called after successful notification delivery"""
        # Counter already incremented in check_rate_limit
        pass
```

## 5. Channel Handlers with Circuit Breakers - ENHANCED

### Per-Channel Circuit Breaker Implementation
```python
# Problem Fixed: Single circuit breaker causing total channel failure
class ChannelCircuitBreaker:
    def __init__(self, channel: str, failure_threshold: int = 10, timeout: int = 300):
        self.channel = channel
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.redis_key = f"circuit_breaker:{channel}"
        self.redis = redis.Redis(host='monitoring-redis')
    
    async def is_open(self) -> bool:
        state = await self.redis.hgetall(self.redis_key)
        if not state:
            return False
            
        failure_count = int(state.get('failure_count', 0))
        last_failure = float(state.get('last_failure_time', 0))
        
        if failure_count >= self.failure_threshold:
            if time.time() - last_failure > self.timeout:
                # Reset circuit breaker
                await self.redis.delete(self.redis_key)
                return False
            return True
        return False
    
    async def record_success(self):
        await self.redis.delete(self.redis_key)
    
    async def record_failure(self):
        pipe = self.redis.pipeline()
        pipe.hincrby(self.redis_key, 'failure_count', 1)
        pipe.hset(self.redis_key, 'last_failure_time', time.time())
        pipe.expire(self.redis_key, self.timeout * 2)
        await pipe.execute()

class EnhancedPushNotificationHandler:
    def __init__(self):
        self.fcm_client = FCMClient()
        self.apns_client = APNsClient() 
        self.circuit_breaker = ChannelCircuitBreaker('push_notifications')
        self.deduplicator = NotificationDeduplicator()
        
    async def send_batch(self, notifications: List[PushNotification]):
        # Problem Fixed: Circuit breaker now per-channel, not global
        if await self.circuit_breaker.is_open():
            raise CircuitBreakerOpenError("Push notification circuit breaker is open")
        
        # Problem Fixed: Added deduplication
        deduplicated = await self.deduplicator.filter_duplicates(notifications)
        
        try:
            # Smaller batch sizes for better error isolation
            for batch in chunks(deduplicated, 50):  # Reduced from 100
                await self._send_platform_batch(batch)
            
            await self.circuit_breaker.record_success()
            
        except Exception as e:
            await self.circuit_breaker.record_failure()
            raise e
```

### Realistic Delivery SLAs
```python
# Problem Fixed: Unrealistic SLAs that contradict batching logic
REVISED_DELIVERY_SLAS = {
    NotificationPriority.CRITICAL: {
        'target_latency': '30 seconds',  # Reduced from immediate
        'batch_size': 10,                # Increased from 1 for efficiency
        'max_delay': 10                  # Max batching delay in seconds
    },
    NotificationPriority.HIGH: {
        'target_latency': '2 minutes',   # Increased from 30 seconds  
        'batch_size': 50,                # Reduced from 100
        'max_delay': 60
    },
    NotificationPriority.MEDIUM: {
        'target_latency': '10 minutes',  # Increased from 5 minutes
        'batch_size': 200,               # Reduced from 500
        'max_delay': 300
    },
    NotificationPriority.LOW: {
        'target_latency': '4 hours',     # Increased from 1 hour
        'batch_size': 500,               # Reduced from 1000
        'max_delay': 1800
    }
}
```

## 6. Preference Engine - OPTIMIZED

### Simplified Preference Logic
```python
# Problem Fixed: Complex preference queries and timezone calculations
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
        
        # Simplified quiet hours check (no timezone conversion)
        if self._in_quiet_hours(prefs) and notification.priority != NotificationPriority.CRITICAL:
            channels['push'] = False
            # SMS still allowed for high priority in quiet hours
            if notification.priority not in [NotificationPriority.CRITICAL, NotificationPriority.HIGH]:
                channels['sms'] = False
        
        return channels
    
    def _check_bitmask(self, user_categories: int, notification_category: int) -> bool:
        """Simple bitmask check instead of complex boolean logic"""
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
        
        # Use prepared statement for partitioned table
        prefs = await self.db.execute_prepared(
            "get_user_preferences", 
            [user_id]
        )
        
        if prefs:
            await self.cache.setex(f"prefs:{user_id}", 7200, prefs.to_dict())  # 2 hour cache