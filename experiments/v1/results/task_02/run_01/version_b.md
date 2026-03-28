# Revised Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users with realistic infrastructure constraints. The design addresses viral content scenarios, database scalability limitations, and proper queue architecture while maintaining deliverability within a 6-month timeline and 4-engineer team.

**Key Design Revisions:**
- Hybrid database architecture with write-optimized time-series storage
- Apache Kafka for ordered, high-throughput message processing
- Proper FCM/APNS batching with token validation
- Viral content backpressure and fan-out limiting
- Multi-region deployment with preference consistency

---

## 1. System Architecture Overview

### 1.1 Revised High-Level Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   App Services  │───▶│ Notification API │───▶│ Kafka Cluster   │
│                 │    │   + Rate Limiter │    │ (3 partitions   │
└─────────────────┘    └──────────────────┘    │  per priority)  │
                                                └─────────────────┘
                                                         │
                       ┌─────────────────────────────────┼─────────────────────────────────┐
                       ▼                                 ▼                                 ▼
              ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
              │ Push Processor  │              │ Email Processor │              │ In-App Processor│
              │ (Multi-region)  │              │   (Batch Jobs)  │              │  (Real-time)    │
              └─────────────────┘              └─────────────────┘              └─────────────────┘
                       │                                 │                                 │
                       ▼                                 ▼                                 ▼
              ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
              │   FCM/APNS      │              │   SendGrid      │              │   ScyllaDB      │
              │ (Token Manager) │              │                 │              │  + WebSocket    │
              └─────────────────┘              └─────────────────┘              └─────────────────┘
```

**Fixes Problem 2 (Queue Architecture):** Kafka provides ordered processing with 100K+ TPS per partition, eliminating SQS throughput limitations.

### 1.2 Revised Technology Stack

**Message Queue:** Apache Kafka (AWS MSK)
- *Rationale:* 1M+ messages/second throughput, message ordering, exactly-once semantics
- *Configuration:* 9 partitions (3 per priority level) for horizontal scaling
- *Fixes Problem 2:* Eliminates SQS 300 TPS limitation and provides proper priority queuing

**Primary Database:** ScyllaDB for notification storage + PostgreSQL for user data
- *Rationale:* ScyllaDB handles 1M+ writes/second with automatic sharding
- *Fixes Problem 1:* Eliminates PostgreSQL write bottleneck for notification storage

**Preference Cache:** Redis Cluster with write-through caching
- *Rationale:* Immediate consistency for preference updates, eliminates thundering herd
- *Fixes Problem 1:* Removes 1-hour TTL delay and cache invalidation issues

---

## 2. Database Architecture Redesign

### 2.1 Notification Storage (ScyllaDB)

```sql
-- Time-series optimized notification storage
CREATE TABLE notifications (
    partition_key text,      -- user_id + month (e.g., "user123_202312")
    created_at timestamp,    -- Clustering key for time ordering
    notification_id uuid,
    category text,
    title text,
    body text,
    data text,              -- JSON as text for better performance
    channel_status map<text, text>, -- {"push": "sent", "email": "pending"}
    read_at timestamp,
    PRIMARY KEY (partition_key, created_at, notification_id)
) WITH CLUSTERING ORDER BY (created_at DESC);

-- Monthly partitioning prevents unbounded partition growth
-- Each user gets ~8KB of notifications per month = manageable partition size
```

**Fixes Problem 1:** Eliminates PostgreSQL scaling bottleneck with proper time-series design.

### 2.2 User Preferences (PostgreSQL + Redis)

```sql
-- Simplified preference schema for PostgreSQL
CREATE TABLE user_notification_preferences (
    user_id UUID PRIMARY KEY,
    preferences_json JSONB NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,  -- For optimistic locking
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Materialized view for fast category lookups
CREATE MATERIALIZED VIEW user_channel_preferences AS
SELECT 
    user_id,
    (preferences_json->'channels'->>'push')::boolean as push_enabled,
    (preferences_json->'channels'->>'email')::boolean as email_enabled,
    (preferences_json->'channels'->>'sms')::boolean as sms_enabled,
    preferences_json->'categories' as category_prefs
FROM user_notification_preferences;
```

```python
# Write-through cache strategy
class PreferenceManager:
    async def update_preferences(self, user_id: str, new_prefs: dict):
        # Update database first
        await self.db.execute(
            "UPDATE user_notification_preferences SET preferences_json = $1, version = version + 1 WHERE user_id = $2",
            new_prefs, user_id
        )
        
        # Immediately update cache (write-through)
        await self.redis.setex(f"prefs:{user_id}", 3600, json.dumps(new_prefs))
        
        # Refresh materialized view
        await self.db.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY user_channel_preferences")
```

**Fixes Problem 1:** Eliminates preference propagation delays and cache invalidation issues.

---

## 3. Queue Architecture with Proper Priority Handling

### 3.1 Kafka Topic Design

```python
# Kafka topic configuration
NOTIFICATION_TOPICS = {
    'notifications-critical': {
        'partitions': 3,
        'replication_factor': 3,
        'max_message_bytes': 1048576,  # 1MB
        'retention_ms': 604800000      # 7 days
    },
    'notifications-high': {
        'partitions': 3, 
        'replication_factor': 3,
        'retention_ms': 259200000      # 3 days
    },
    'notifications-medium': {
        'partitions': 3,
        'replication_factor': 3, 
        'retention_ms': 86400000       # 1 day
    }
}

class NotificationProducer:
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers=['kafka1:9092', 'kafka2:9092', 'kafka3:9092'],
            value_serializer=lambda x: json.dumps(x).encode('utf-8'),
            acks='all',  # Wait for all replicas
            retries=3,
            max_in_flight_requests_per_connection=1  # Maintain ordering
        )
    
    async def send_notification(self, notification: Notification):
        topic = f"notifications-{notification.priority.name.lower()}"
        
        # Partition by user_id for ordering per user
        partition_key = notification.user_id.encode('utf-8')
        
        await self.producer.send(
            topic, 
            value=notification.dict(),
            key=partition_key
        )
```

**Fixes Problem 2:** Provides proper priority separation and ordering guarantees.

### 3.2 Consumer Groups with Priority Processing

```python
class PriorityAwareConsumer:
    def __init__(self):
        self.consumers = {
            'critical': KafkaConsumer(
                'notifications-critical',
                group_id='notification-processors-critical',
                auto_offset_reset='earliest',
                max_poll_records=100  # Small batches for low latency
            ),
            'high': KafkaConsumer(
                'notifications-high', 
                group_id='notification-processors-high',
                max_poll_records=500
            ),
            'medium': KafkaConsumer(
                'notifications-medium',
                group_id='notification-processors-medium', 
                max_poll_records=1000
            )
        }
    
    async def process_messages(self):
        while True:
            # Process critical first, then high, then medium
            for priority in ['critical', 'high', 'medium']:
                messages = self.consumers[priority].poll(timeout_ms=100)
                if messages:
                    await self._process_batch(messages, priority)
                    self.consumers[priority].commit()
```

**Fixes Problem 4:** Implements proper priority enforcement with measurable SLAs.

---

## 4. Push Notification Batching Corrections

### 4.1 Proper FCM/APNS Batching

```python
class PushNotificationBatcher:
    def __init__(self):
        self.fcm_client = FCMClient()
        self.apns_client = APNSClient()
        
        # Correct batch limits
        self.FCM_BATCH_SIZE = 500  # FCM multicast limit
        self.APNS_CONCURRENT = 1000  # HTTP/2 concurrent streams
        
    async def send_fcm_batch(self, notifications: List[PushNotification]):
        # Group by message content for multicast efficiency
        content_groups = defaultdict(list)
        for notif in notifications:
            content_key = (notif.title, notif.body, json.dumps(notif.data, sort_keys=True))
            content_groups[content_key].append(notif.device_token)
        
        tasks = []
        for (title, body, data), tokens in content_groups.items():
            # Split tokens into FCM batch size
            for token_batch in self._chunk_list(tokens, self.FCM_BATCH_SIZE):
                valid_tokens = await self._validate_tokens(token_batch)
                if valid_tokens:
                    task = self._send_fcm_multicast(title, body, data, valid_tokens)
                    tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        await self._handle_token_failures(results)
    
    async def send_apns_batch(self, notifications: List[PushNotification]):
        # APNS has no native batching - use concurrent HTTP/2 streams
        semaphore = asyncio.Semaphore(self.APNS_CONCURRENT)
        
        async def send_single(notification):
            async with semaphore:
                return await self._send_apns_single(notification)
        
        tasks = [send_single(notif) for notif in notifications]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        await self._handle_apns_failures(results)
    
    async def _validate_tokens(self, tokens: List[str]) -> List[str]:
        # Check Redis cache for invalid tokens
        pipe = self.redis.pipeline()
        for token in tokens:
            pipe.exists(f"invalid_token:{token}")
        
        results = await pipe.execute()
        return [token for token, is_invalid in zip(tokens, results) if not is_invalid]
```

**Fixes Problem 3:** Corrects FCM batch size limits and implements proper APNS handling.

### 4.2 Token Management and Validation

```python
class DeviceTokenManager:
    def __init__(self):
        self.redis = redis.Redis()
        self.token_cache_ttl = 86400  # 24 hours
    
    async def handle_push_failure(self, token: str, error_code: str):
        if error_code in ['InvalidRegistration', 'NotRegistered', 'MismatchSenderId']:
            # Mark token as invalid
            await self.redis.setex(f"invalid_token:{token}", self.token_cache_ttl, "1")
            
            # Remove from database
            await self.db.execute(
                "UPDATE user_devices SET active = false WHERE token = $1", token
            )
    
    async def cleanup_invalid_tokens(self):
        # Daily cleanup job
        cutoff = datetime.now() - timedelta(days=30)
        await self.db.execute(
            "DELETE FROM user_devices WHERE active = false AND last_seen_at < $1", 
            cutoff
        )
```

**Fixes Problem 3:** Prevents entire batch failures due to invalid tokens.

---

## 5. Viral Content and Backpressure Handling

### 5.1 Fan-out Limiting

```python
class ViralContentHandler:
    def __init__(self):
        self.max_fanout_per_user = 50000  # Limit notifications per user per hour
        self.celebrity_threshold = 100000  # Follower count threshold
        
    async def should_process_notification(self, trigger_user_id: str, notification_type: str) -> bool:
        # Check if user is generating too many notifications
        hourly_key = f"fanout:{trigger_user_id}:{datetime.now().hour}"
        current_count = await self.redis.get(hourly_key) or 0
        
        if int(current_count) > self.max_fanout_per_user:
            # Log viral event and switch to digest mode
            await self._log_viral_event(trigger_user_id, notification_type)
            return False
        
        await self.redis.incr(hourly_key)
        await self.redis.expire(hourly_key, 3600)
        return True
    
    async def _log_viral_event(self, user_id: str, event_type: str):
        # Store viral events for digest processing
        await self.redis.zadd(
            f"viral_events:{datetime.now().date()}", 
            {f"{user_id}:{event_type}": time.time()}
        )
```

**Fixes Problem 6:** Prevents system collapse under viral content scenarios.

### 5.2 Backpressure and Circuit Breakers

```python
class BackpressureManager:
    def __init__(self):
        self.queue_depth_threshold = 10000
        self.circuit_breakers = {
            'fcm': CircuitBreaker(failure_threshold=10, recovery_timeout=60),
            'apns': CircuitBreaker(failure_threshold=10, recovery_timeout=60),
            'email': CircuitBreaker(failure_threshold=5, recovery_timeout=120)
        }
    
    async def check_system_health(self) -> bool:
        # Check Kafka consumer lag
        lag = await self._get_consumer_lag()
        if lag > self.queue_depth_threshold:
            await self._enable_backpressure()
            return False
        
        # Check circuit breaker states
        for channel, breaker in self.circuit_breakers.items():
            if breaker.state == "OPEN":
                logger.warning(f"Circuit breaker OPEN for {channel}")
        
        return True
    
    async def _enable_backpressure(self):
        # Temporarily reject low-priority notifications
        await self.redis.setex("backpressure:active", 300, "1")  # 5 minutes
        logger.warning("Backpressure enabled - dropping low priority notifications")
```

**Fixes Problem 6:** Provides system protection during overload conditions.

---

## 6. Enhanced Anti-Spam and Deduplication

### 6.1 Semantic Deduplication

```python
class SmartDeduplicator:
    def __init__(self):
        self.redis = redis.Redis()
        
    async def should_send_notification(self, user_id: str, notification: Notification) -> bool:
        # Semantic grouping for similar notifications
        semantic_key = self._generate_semantic_key(notification)
        dedup_key = f"dedup:{user_id}:{semantic_key}"