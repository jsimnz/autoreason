# Notification System Design for Social App (10M MAU) - Final Version

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 6-month timeline and 4-engineer team constraint, we prioritize MVP functionality with built-in scalability hooks while addressing critical infrastructure bottlenecks that would emerge at scale.

**Key Design Decisions:**
- **Hybrid queue architecture:** SQS for development velocity + Kafka migration path for scale
- **Strategic database split:** PostgreSQL for preferences + time-series optimized storage for notifications
- **Corrected push batching:** Proper FCM multicast (500/batch) and APNS concurrent streams
- **Viral content protection:** Fan-out limiting and backpressure mechanisms
- **Phased rollout:** Push notifications and in-app delivery first, email/SMS follow

---

## 1. System Architecture Overview

### 1.1 High-Level Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   App Services  │───▶│ Notification API │───▶│  SQS Queues     │
│                 │    │   + Rate Limiter │    │ (Priority-based) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                       ┌─────────────────────────────────┼─────────────────────────────────┐
                       ▼                                 ▼                                 ▼
              ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
              │ Push Processor  │              │ Email Processor │              │ In-App Processor│
              │ (Token Manager) │              │   (Batch Jobs)  │              │  (Real-time)    │
              └─────────────────┘              └─────────────────┘              └─────────────────┘
                       │                                 │                                 │
                       ▼                                 ▼                                 ▼
              ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
              │   FCM/APNS      │              │   SendGrid      │              │   PostgreSQL    │
              │ (Proper Batch)  │              │                 │              │  + WebSocket    │
              └─────────────────┘              └─────────────────┘              └─────────────────┘
```

### 1.2 Technology Stack Selection

**Message Queue:** AWS SQS with Kafka Migration Path
- *Rationale:* SQS provides immediate development velocity for 4-engineer team
- *Scale Path:* Design allows migration to Kafka when throughput exceeds 50K notifications/minute
- *Implementation:* Separate queues per priority (critical-notifications, high-notifications, etc.)

```python
# Queue abstraction for future Kafka migration
class NotificationQueue:
    def __init__(self, queue_type: str = "sqs"):
        if queue_type == "sqs":
            self.backend = SQSQueue()
        elif queue_type == "kafka":
            self.backend = KafkaQueue()
    
    async def send_message(self, notification: Notification, priority: Priority):
        return await self.backend.send_message(notification, priority)
```

**Database Architecture:** PostgreSQL + ScyllaDB Migration Path
- *Phase 1:* PostgreSQL for all data (simpler for team)
- *Phase 2:* Migrate notification storage to ScyllaDB when write load exceeds 10K notifications/second
- *Rationale:* Avoid operational complexity early while designing for scale

**Push Services:** Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNS)
- *Corrected Implementation:* Proper batch sizes and token management
- *FCM:* 500 notifications per multicast (not 1000 as in Version A)
- *APNS:* Concurrent HTTP/2 streams (not batching)

---

## 2. Corrected Push Notification Implementation

### 2.1 Proper FCM Batching

```python
class PushProcessor:
    def __init__(self):
        self.fcm_client = FCMClient(api_key=settings.FCM_KEY)
        self.apns_client = APNSClient(cert_path=settings.APNS_CERT)
        self.FCM_MULTICAST_LIMIT = 500  # Correct FCM limit
        self.APNS_CONCURRENT_LIMIT = 1000  # HTTP/2 streams
        
    async def process_push_batch(self, notifications: List[PushNotification]):
        android_notifications = [n for n in notifications if n.platform == 'android']
        ios_notifications = [n for n in notifications if n.platform == 'ios']
        
        await asyncio.gather(
            self._send_fcm_multicast(android_notifications),
            self._send_apns_concurrent(ios_notifications)
        )
    
    async def _send_fcm_multicast(self, notifications: List[PushNotification]):
        # Group by message content for efficient multicast
        content_groups = defaultdict(list)
        for notif in notifications:
            content_key = (notif.title, notif.body, json.dumps(notif.data, sort_keys=True))
            content_groups[content_key].append(notif.device_token)
        
        tasks = []
        for (title, body, data), tokens in content_groups.items():
            # Validate tokens before sending
            valid_tokens = await self._filter_invalid_tokens(tokens)
            
            # Send in proper FCM multicast batches
            for token_batch in self._chunk_list(valid_tokens, self.FCM_MULTICAST_LIMIT):
                task = self.fcm_client.send_multicast(
                    tokens=token_batch,
                    notification={"title": title, "body": body},
                    data=json.loads(data)
                )
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        await self._handle_fcm_failures(results)
    
    async def _send_apns_concurrent(self, notifications: List[PushNotification]):
        # APNS doesn't support batching - use concurrent HTTP/2 streams
        semaphore = asyncio.Semaphore(self.APNS_CONCURRENT_LIMIT)
        
        async def send_single(notification):
            async with semaphore:
                try:
                    return await self.apns_client.send_notification(
                        token=notification.device_token,
                        payload=notification.to_apns_payload()
                    )
                except APNSError as e:
                    if e.status in ['410', '400']:  # Invalid token
                        await self._mark_token_invalid(notification.device_token)
                    raise
        
        tasks = [send_single(notif) for notif in notifications]
        await asyncio.gather(*tasks, return_exceptions=True)
```

**Key Corrections from Version A:**
- FCM batch size corrected to 500 (not 1000)
- APNS uses concurrent streams, not batching
- Token validation prevents batch failures
- Proper error handling and token cleanup

### 2.2 Device Token Management

```python
class DeviceTokenManager:
    def __init__(self, redis_client, db_pool):
        self.redis = redis_client
        self.db = db_pool
    
    async def _filter_invalid_tokens(self, tokens: List[str]) -> List[str]:
        # Check Redis cache for known invalid tokens
        pipe = self.redis.pipeline()
        for token in tokens:
            pipe.exists(f"invalid_token:{token}")
        
        cache_results = await pipe.execute()
        return [token for token, is_invalid in zip(tokens, cache_results) if not is_invalid]
    
    async def _mark_token_invalid(self, token: str):
        # Cache invalid token for 24 hours
        await self.redis.setex(f"invalid_token:{token}", 86400, "1")
        
        # Update database
        await self.db.execute(
            "UPDATE user_devices SET active = false WHERE token = $1", token
        )
```

---

## 3. Database Architecture with Scale Path

### 3.1 Phase 1: PostgreSQL-First (Months 1-4)

```sql
-- Notification storage optimized for PostgreSQL
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    data JSONB,
    channel_status JSONB DEFAULT '{}', -- {"push": "sent", "email": "pending"}
    read_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
) PARTITION BY RANGE (created_at);

-- Monthly partitions for performance
CREATE TABLE notifications_2024_01 PARTITION OF notifications
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Indexes for common queries
CREATE INDEX idx_notifications_user_unread 
ON notifications(user_id, created_at) 
WHERE read_at IS NULL;

CREATE INDEX idx_notifications_cleanup
ON notifications(expires_at)
WHERE expires_at IS NOT NULL;
```

### 3.2 Phase 2: ScyllaDB Migration Path (Month 5+)

```sql
-- ScyllaDB schema for high-write scenarios
CREATE TABLE notifications_timeseries (
    partition_key text,      -- user_id + month (e.g., "user123_202401")
    created_at timestamp,    -- Clustering key for time ordering
    notification_id uuid,
    title text,
    body text,
    category text,
    data text,              -- JSON as text for performance
    channel_status map<text, text>,
    read_at timestamp,
    PRIMARY KEY (partition_key, created_at, notification_id)
) WITH CLUSTERING ORDER BY (created_at DESC);
```

```python
# Database abstraction for migration
class NotificationStorage:
    def __init__(self, storage_type: str = "postgresql"):
        if storage_type == "postgresql":
            self.backend = PostgreSQLStorage()
        elif storage_type == "scylladb":
            self.backend = ScyllaDBStorage()
    
    async def store_notification(self, notification: Notification):
        return await self.backend.store_notification(notification)
```

**Migration Trigger:** When PostgreSQL write load exceeds 10K notifications/second or storage exceeds 1TB.

---

## 4. Viral Content and Backpressure Protection

### 4.1 Fan-out Limiting

```python
class ViralContentProtection:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.MAX_FANOUT_PER_HOUR = 50000  # Per user
        self.CELEBRITY_THRESHOLD = 100000  # Follower count
        
    async def should_process_notification(self, trigger_user_id: str, recipient_count: int) -> bool:
        # Check hourly fan-out limit
        hour_key = f"fanout:{trigger_user_id}:{datetime.now().strftime('%Y%m%d%H')}"
        current_fanout = int(await self.redis.get(hour_key) or 0)
        
        if current_fanout + recipient_count > self.MAX_FANOUT_PER_HOUR:
            await self._log_viral_event(trigger_user_id, recipient_count)
            return False
        
        # Increment counter
        await self.redis.incrby(hour_key, recipient_count)
        await self.redis.expire(hour_key, 3600)
        return True
    
    async def _log_viral_event(self, user_id: str, blocked_count: int):
        logger.warning(f"Viral content blocked: user {user_id}, {blocked_count} notifications")
        # Store for analytics and potential digest processing
        await self.redis.zadd(
            f"viral_events:{datetime.now().date()}", 
            {f"{user_id}:{blocked_count}": time.time()}
        )
```

### 4.2 System Backpressure

```python
class BackpressureManager:
    def __init__(self, cloudwatch_client):
        self.cloudwatch = cloudwatch_client
        self.QUEUE_DEPTH_THRESHOLD = 10000
        
    async def check_system_health(self) -> dict:
        # Check SQS queue depths
        queue_depths = await self._get_queue_depths()
        total_depth = sum(queue_depths.values())
        
        if total_depth > self.QUEUE_DEPTH_THRESHOLD:
            await self._enable_backpressure()
            return {"healthy": False, "reason": "queue_overload", "depth": total_depth}
        
        return {"healthy": True, "queue_depth": total_depth}
    
    async def _enable_backpressure(self):
        # Drop low-priority notifications temporarily
        await self.redis.setex("backpressure:active", 300, "1")  # 5 minutes
        
        # Alert monitoring
        await self.cloudwatch.put_metric_data(
            Namespace='NotificationSystem',
            MetricData=[{
                'MetricName': 'BackpressureActivated',
                'Value': 1,
                'Unit': 'Count'
            }]
        )
```

---

## 5. Priority and Batching Logic (Enhanced)

### 5.1 Priority Classification with SLAs

```python
class NotificationPriority(Enum):
    CRITICAL = 1     # Security alerts, payment issues
    HIGH = 2         # Direct messages, mentions  
    MEDIUM = 3       # Likes, comments, follows
    LOW = 4          # Weekly digests, recommendations

# Enhanced priority configuration
PRIORITY_CONFIG = {
    NotificationPriority.CRITICAL: {
        'max_delay_seconds': 5,
        'batch_size': 100,
        'retry_attempts': 5,
        'sqs_queue': 'notifications-critical',
        'bypass_backpressure': True
    },
    NotificationPriority.HIGH: {
        'max_delay_seconds': 30,
        'batch_size': 500,
        'retry_attempts': 3,
        'sqs_queue': 'notifications-high',
        'bypass_backpressure': False
    },
    NotificationPriority.MEDIUM: {
        'max_delay_seconds': 300,
        'batch_size': 1000,
        'retry_attempts': 2,
        'sqs_queue': 'notifications-medium',
        'bypass_backpressure': False
    },
    NotificationPriority.LOW: {
        'max_delay_seconds': 1800,
        'batch_size': 2000,
        'retry_attempts': 1,
        'sqs_queue': 'notifications-low',
        'bypass_backpressure': False
    }
}
```

### 5.2 Enhanced Deduplication

```python
class NotificationDeduplicator:
    def __init__(self, redis_client):
        self.redis = redis_client
        
    async def should_send_notification(self, user_id: str, category: str, content_hash: str) -> bool:
        # Semantic deduplication for similar content
        dedup_key = f"dedup:{user_id}:{category}:{content_hash}"
        
        # Different deduplication windows by category
        dedup_windows = {
            'likes': 1800,      # 30 minutes for likes
            'comments': 3600,   # 1 hour for comments
            'follows': 7200,    # 2 hours for follows
            'messages': 0       # No deduplication for messages
        }
        
        window = dedup_windows.get(category, 3600)  # Default 1 hour
        if window == 0:
            return True
        
        exists = await self.