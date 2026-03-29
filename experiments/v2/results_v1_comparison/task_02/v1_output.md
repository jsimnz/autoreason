# Notification System Design for Social App (10M MAU) - SYNTHESIS

## Executive Summary

This proposal outlines a scalable notification system design for a social app with 10M MAU, deliverable within 6 months by 4 backend engineers. The system prioritizes reliable delivery at scale while managing costs, ensuring regulatory compliance, and maintaining high user engagement through intelligent batching and preference management.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with horizontal scaling
- **Channel Adapters**: Push, Email, In-App, SMS handlers with circuit breakers
- **User Preference Engine**: Distributed preference management with conflict resolution
- **Priority Queue System**: Multi-tier queuing with intelligent batching
- **Delivery Tracking**: Success/failure monitoring with deduplication
- **Device Token Manager**: Token validation and cleanup service

### Technology Stack
- **Message Queue**: Apache Kafka (36 partitions across 3 brokers minimum)
- **Database**: PostgreSQL (sharded across 4 instances) + Redis Cluster (6 nodes)
- **Push Service**: FCM + APNS with systematic token management
- **Email**: SendGrid + Amazon SES (dual provider for 99.9% uptime)
- **SMS**: Twilio + AWS SNS (dual provider with cost controls)
- **Infrastructure**: AWS with EKS, estimated $12K/month operational cost

## 2. Capacity Planning and Scaling

### 2.1 Realistic Load Calculations

```python
# Evidence-based notification volume calculations
DAILY_NOTIFICATIONS_PER_USER = {
    'high_engagement_users': 12,  # 20% of users (social interactions)
    'medium_engagement_users': 4,  # 60% of users (periodic updates)
    'low_engagement_users': 1     # 20% of users (critical only)
}

# Daily volume: (10M * 0.2 * 12) + (10M * 0.6 * 4) + (10M * 0.2 * 1) = 50M notifications/day
# Peak hour multiplier: 2.5x = 125M notifications during peak
# Required throughput: 1,450 notifications/second average, 3,625 peak
```

### 2.2 Kafka Cluster Optimization

```yaml
# Kafka Configuration - Optimized for 6-month delivery
brokers: 3  # Sufficient for initial scale, expandable to 6
topics:
  notifications-critical:
    partitions: 6
    max_throughput: 1000_msg/sec
  notifications-high:
    partitions: 12
    max_throughput: 2000_msg/sec
  notifications-medium:
    partitions: 8
    max_throughput: 1000_msg/sec
  notifications-low:
    partitions: 4
    max_throughput: 500_msg/sec

# Total capacity: 4,500 msg/sec (handles 3,625 peak with 24% headroom)
```

## 3. Delivery Channels Implementation

### 3.1 Push Notifications with Token Management

```python
class PushNotificationAdapter:
    def __init__(self):
        self.fcm_client = FCMClient()
        self.apns_client = APNSClient()
        self.batch_size = 1000
        self.token_manager = DeviceTokenManager()
    
    async def send_batch_with_validation(self, notifications):
        # Validate tokens before sending
        valid_notifications = []
        for notification in notifications:
            if await self.token_manager.is_token_valid(notification.device_token):
                valid_notifications.append(notification)
            else:
                await self.token_manager.remove_invalid_token(notification.device_token)
        
        # Split by platform and send
        android_batch = [n for n in valid_notifications if n.platform == 'android']
        ios_batch = [n for n in valid_notifications if n.platform == 'ios']
        
        results = await asyncio.gather(
            self.send_fcm_batch(android_batch),
            self.send_apns_batch(ios_batch)
        )
        
        # Update token validity based on results
        await self.token_manager.process_delivery_results(results)
        return results
```

**Tradeoffs**: 
- ✅ 95% delivery rate with token validation, immediate engagement
- ❌ Dependent on device connectivity, 5% invalid token overhead
- **Cost**: ~$0.50 per 1M notifications + token management overhead

### 3.2 Email with Multi-Provider Strategy

```python
class EmailDeliveryManager:
    def __init__(self):
        self.providers = {
            'sendgrid': SendGridClient(),
            'ses': AmazonSESClient()
        }
        self.batch_size = 5000
        self.reputation_threshold = 0.90
    
    async def send_email_batch(self, emails):
        primary_provider = await self.get_best_provider()
        
        try:
            # Create digest emails for better engagement
            digest_emails = self.create_user_digests(emails)
            results = await self.providers[primary_provider].send_batch(digest_emails)
            await self.update_provider_reputation(primary_provider, results)
            return results
            
        except ProviderError:
            # Automatic failover
            secondary = 'ses' if primary_provider == 'sendgrid' else 'sendgrid'
            return await self.providers[secondary].send_batch(digest_emails)
    
    def create_user_digests(self, notifications):
        """Group notifications by user for better email experience"""
        user_groups = defaultdict(list)
        for notif in notifications:
            user_groups[notif.user_id].append(notif)
        
        digests = []
        for user_id, user_notifs in user_groups.items():
            if len(user_notifs) > 1:
                digest = self.create_digest_email(user_id, user_notifs)
                digests.append(digest)
            else:
                digests.extend(user_notifs)
        return digests
```

**Tradeoffs**:
- ✅ 99.5% deliverability with dual providers, digest reduces email fatigue
- ❌ Delayed delivery acceptable (within 1 hour), digest complexity
- **Cost**: ~$0.85 per 1K emails with dual provider overhead

### 3.3 SMS with Intelligent Cost Management

```python
class SMSCostManager:
    def __init__(self):
        self.monthly_budget = 25000  # $25K realistic budget
        self.cost_per_sms = 0.0075
        self.critical_types = ['security_alert', 'account_locked', 'payment_failed']
        
    async def should_send_sms(self, notification):
        current_spend = await self.get_monthly_spend()
        
        if current_spend >= self.monthly_budget * 0.9:  # 90% budget threshold
            return notification.type in self.critical_types
            
        # Smart criteria: critical alerts OR explicit user opt-in
        return (notification.type in self.critical_types or 
                await self.user_has_sms_preference(notification.user_id, notification.type))
    
    async def estimate_realistic_monthly_cost(self):
        """Conservative SMS cost estimation"""
        security_alerts = 10_000_000 * 0.02 * self.cost_per_sms  # $1,500
        payment_critical = 10_000_000 * 0.01 * self.cost_per_sms  # $750
        user_opt_ins = 10_000_000 * 0.03 * 1.5 * self.cost_per_sms  # $3,375
        return security_alerts + payment_critical + user_opt_ins  # ~$5,625/month
```

**Tradeoffs**:
- ✅ Highest deliverability (99.9%), works without internet
- ❌ Most expensive channel, regulatory restrictions
- **Cost**: ~$5,625/month with intelligent filtering (vs $75K without)

## 4. Priority and Intelligent Batching Logic

### 4.1 Dynamic Priority Classification

```python
class IntelligentPriorityEngine:
    def __init__(self):
        self.priority_rules = {
            'security_alert': NotificationPriority.CRITICAL,
            'friend_request': NotificationPriority.HIGH,
            'like': NotificationPriority.MEDIUM,
            'marketing': NotificationPriority.LOW
        }
        self.user_engagement_cache = Redis()
    
    async def calculate_dynamic_priority(self, notification):
        base_priority = self.priority_rules.get(notification.type, NotificationPriority.MEDIUM)
        
        # Adjust priority based on user engagement
        user_engagement = await self.get_user_engagement_score(notification.user_id)
        
        if user_engagement > 0.8 and base_priority == NotificationPriority.MEDIUM:
            return NotificationPriority.HIGH  # Boost for engaged users
        elif user_engagement < 0.2 and base_priority == NotificationPriority.HIGH:
            return NotificationPriority.MEDIUM  # Reduce for disengaged users
            
        return base_priority
```

### 4.2 Intelligent Batching with Deduplication

```python
class SmartBatchProcessor:
    def __init__(self):
        self.batch_configs = {
            'push': {'size': 1000, 'timeout': 30, 'dedup_window': 300},
            'email': {'size': 5000, 'timeout': 300, 'dedup_window': 3600},
            'sms': {'size': 100, 'timeout': 60, 'dedup_window': 3600}
        }
        self.deduplicator = NotificationDeduplicator()
    
    async def process_batch(self, channel, notifications):
        # Deduplicate notifications within batch
        unique_notifications = []
        for notif in notifications:
            if await self.deduplicator.should_send_notification(notif):
                unique_notifications.append(notif)
        
        # Smart batching based on user timezone for better engagement
        if channel == 'email':
            timezone_batches = self.group_by_optimal_send_time(unique_notifications)
            for batch in timezone_batches:
                await self.send_batch(channel, batch)
        else:
            await self.send_batch(channel, unique_notifications)
    
    def group_by_optimal_send_time(self, notifications):
        """Group email notifications by user timezone for optimal send times"""
        timezone_groups = defaultdict(list)
        
        for notif in notifications:
            user_tz = notif.user_timezone or 'UTC'
            optimal_hour = self.get_optimal_send_hour(user_tz)
            timezone_groups[optimal_hour].append(notif)
            
        return list(timezone_groups.values())
```

## 5. User Preference Management with Conflict Resolution

### 5.1 Sharded Database Architecture

```sql
-- Distributed across 4 PostgreSQL shards for 2.5M users each
-- Shard selection: user_id % 4

CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    preferences JSONB NOT NULL DEFAULT '{}',
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1,  -- Optimistic locking
    
    -- Compliance tracking
    consent_timestamp TIMESTAMP,
    consent_ip_address INET
);

-- Performance indexes
CREATE INDEX idx_user_prefs_updated ON user_notification_preferences(updated_at);
CREATE INDEX idx_user_prefs_timezone ON user_notification_preferences(timezone);
CREATE INDEX idx_user_prefs_consent ON user_notification_preferences(consent_timestamp);
```

### 5.2 Atomic Preference Updates

```python
class PreferenceEngine:
    def __init__(self):
        self.redis_cluster = RedisCluster(nodes=6)
        self.cache_ttl = 1800  # 30 minutes for consistency
        self.db_shards = [PostgreSQLConnection(f"shard_{i}") for i in range(4)]
    
    async def update_preferences_atomic(self, user_id, new_prefs):
        """Atomic update with optimistic locking and cache invalidation"""
        shard_id = user_id % 4
        cache_key = f"prefs:{user_id}"
        
        async with self.db_shards[shard_id].transaction():
            # Get current version for optimistic locking
            current = await self.db_shards[shard_id].fetch_one(
                "SELECT version FROM user_notification_preferences WHERE user_id = %s FOR UPDATE",
                (user_id,)
            )
            
            if not current:
                # Create new preference record
                await self.db_shards[shard_id].execute(
                    """INSERT INTO user_notification_preferences 
                       (user_id, preferences, consent_timestamp, consent_ip_address) 
                       VALUES (%s, %s, NOW(), %s)""",
                    (user_id, json.dumps(new_prefs), new_prefs.get('consent_ip'))
                )
            else:
                # Update existing with version check
                result = await self.db_shards[shard_id].execute(
                    """UPDATE user_notification_preferences 
                       SET preferences = %s, version = version + 1, updated_at = NOW()
                       WHERE user_id = %s AND version = %s""",
                    (json.dumps(new_prefs), user_id, current['version'])
                )
                
                if result.rowcount == 0:
                    raise ConcurrentUpdateError("Preferences modified by another process")
            
            # Invalidate cache after successful database update
            await self.redis_cluster.delete(cache_key)
    
    async def should_send_with_preferences(self, user_id, notification):
        """Check user preferences with quiet hours and engagement context"""
        prefs = await self.get_user_preferences(user_id)
        
        # Check channel enabled
        if not prefs.get(f"{notification.channel}_enabled", True):
            return False
        
        # Check quiet hours (respects user timezone)
        if self.is_quiet_hours(user_id, prefs) and notification.priority != NotificationPriority.CRITICAL:
            return False
            
        # Check specific notification type preferences
        type_pref = prefs.get(f"{notification.type}_{notification.channel}")
        return type_pref if type_pref is not None else True
```

## 6. Failure Handling and Reliability

### 6.1 Circuit Breaker with Adaptive Recovery

```python
class AdaptiveCircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.base_timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'
        self.consecutive_successes = 0
    
    async def call_with_protection(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            # Adaptive timeout based on failure history
            timeout = self.base_timeout * (2 ** min(self.failure_count - self.failure_threshold, 4))
            
            if time.time() - self.last_failure_time > timeout:
                self.state = 'HALF_OPEN'
                self.consecutive_successes = 0
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker open for {timeout}s")
        
        try:
            result = await func(*args, **kwargs)
            await self.on_success()
            return result
        except Exception as e:
            await self.on_failure()
            raise
    
    async def on_success(self):
        if self.state == 'HALF_OPEN':
            self.consecutive_successes += 1
            if self.consecutive_succ