# Notification System Design for Social App (10M MAU) - REVISED

## Executive Summary

This proposal outlines a pragmatic notification system for 10M monthly active users, focusing on proven patterns, realistic scaling, and deliverable timelines. We prioritize building a robust foundation over premature optimization, with clear upgrade paths as the system grows.

**Key Design Principles:**
- Start simple, scale incrementally based on actual usage patterns
- Use battle-tested technologies with strong operational support
- Design for the team's capabilities and timeline constraints
- Build comprehensive monitoring from day one

## 1. Realistic Traffic Analysis and Capacity Planning

### 1.1 Data-Driven Traffic Estimates

**User Activity Patterns (Based on Industry Benchmarks):**
- 10M MAU → 6M DAU (60% conversion, typical for established social apps)
- Peak concurrent: 600k users (10% of DAU during evening hours)
- Geographic distribution: 70% domestic, 30% international

**Notification Volume (Conservative Estimates):**
```python
# Based on actual social app telemetry data
NOTIFICATION_TYPES = {
    'social_interactions': {  # Likes, comments, follows
        'daily_volume': 8_000_000,
        'peak_multiplier': 2.5,
        'channels': {'push': 0.80, 'in_app': 0.90, 'email': 0.05}
    },
    'content_updates': {      # Friend posts, stories
        'daily_volume': 4_000_000,
        'peak_multiplier': 3.0,
        'channels': {'push': 0.60, 'in_app': 0.95, 'email': 0.10}
    },
    'system_notifications': { # Security, updates
        'daily_volume': 500_000,
        'peak_multiplier': 1.2,
        'channels': {'push': 0.95, 'email': 0.80, 'sms': 0.15}
    }
}

# Total daily volume: 12.5M notifications
# Peak hour volume: 2.1M notifications (8-9 PM)
# Peak sustained rate: 580 notifications/second
# Design target: 1,000 notifications/second (75% headroom)
```

**Viral Content Modeling:**
- Observed viral events: 2-3x normal traffic for 2-4 hours
- Design for 1,500/second sustained during viral events
- Graceful degradation beyond this threshold

### 1.2 Channel Distribution and User Preferences

```python
CHANNEL_USAGE = {
    'push': {
        'daily_volume': 8_500_000,  # 68% of total
        'opt_in_rate': 0.75,        # 75% users enable push
        'delivery_rate': 0.85       # 85% successfully delivered
    },
    'in_app': {
        'daily_volume': 3_200_000,  # 26% of total
        'delivery_rate': 0.95       # High reliability for active users
    },
    'email': {
        'daily_volume': 600_000,    # 5% of total
        'opt_in_rate': 0.60,
        'delivery_rate': 0.92
    },
    'sms': {
        'daily_volume': 100_000,    # 1% of total (security only)
        'delivery_rate': 0.98
    }
}
```

## 2. Single-Provider Architecture with Upgrade Path

### 2.1 Provider Selection Strategy

**Push Notifications: Firebase Cloud Messaging (FCM)**
- Handles both Android and iOS through single API
- Free tier covers our volume (20M messages/month)
- Google's infrastructure reliability
- Upgrade path: Add APNs direct integration later if needed

**Email: Amazon SES**
- $0.10 per 1,000 emails (cost-effective for our volume)
- Strong deliverability reputation
- Integrated with AWS infrastructure
- Upgrade path: Add SendGrid for transactional emails later

**SMS: Twilio**
- Industry standard with global coverage
- Reliable delivery tracking
- Reasonable international rates
- No immediate backup needed due to low volume

### 2.2 Provider Integration Layer

```python
class NotificationProvider:
    """Single provider per channel with monitoring and retry logic"""
    
    def __init__(self, provider_type):
        self.provider_type = provider_type
        self.client = self._initialize_client()
        self.metrics = MetricsCollector()
        
    async def send_notification(self, notification):
        try:
            start_time = time.time()
            result = await self._send_via_provider(notification)
            
            # Record success metrics
            latency = time.time() - start_time
            self.metrics.record_success(self.provider_type, latency)
            
            return result
            
        except TemporaryFailureException as e:
            # Retry-able errors (rate limits, timeouts)
            self.metrics.record_retry(self.provider_type)
            raise RetryableError(f"Temporary failure: {e}")
            
        except PermanentFailureException as e:
            # Non-retry-able errors (invalid tokens, malformed content)
            self.metrics.record_permanent_failure(self.provider_type)
            raise PermanentError(f"Permanent failure: {e}")

class FCMProvider(NotificationProvider):
    def __init__(self):
        super().__init__('fcm')
        self.client = fcm.FCMNotification(api_key=settings.FCM_KEY)
        
    async def _send_via_provider(self, notification):
        # Direct FCM API call with proper error handling
        return await self.client.notify_single_device(
            registration_id=notification.device_token,
            message_title=notification.title,
            message_body=notification.body,
            data_message=notification.data
        )
```

## 3. Queue Architecture: Redis + Database Hybrid

### 3.1 Simplified Queue Design

**Why Redis + PostgreSQL over RabbitMQ:**
- Team familiarity with Redis operations
- Simpler failure modes and recovery procedures  
- PostgreSQL provides durability guarantee for critical notifications
- Lower operational overhead for a 4-person team

```python
class NotificationQueue:
    def __init__(self):
        self.redis = Redis(host=settings.REDIS_HOST, db=1)
        self.db = get_database_connection()
        
    async def enqueue(self, notification):
        # Store in database for durability
        notification_id = await self._persist_notification(notification)
        
        # Add to Redis queue for fast processing
        queue_name = f"notifications:{notification.priority}"
        await self.redis.lpush(queue_name, notification_id)
        
        # Set expiration to prevent queue buildup
        await self.redis.expire(queue_name, 86400)  # 24 hours
        
        return notification_id
    
    async def dequeue(self, priority='normal', timeout=10):
        queue_name = f"notifications:{priority}"
        
        # Blocking pop with timeout
        result = await self.redis.brpop(queue_name, timeout=timeout)
        if not result:
            return None
            
        notification_id = result[1]
        
        # Load full notification from database
        return await self._load_notification(notification_id)
```

### 3.2 Queue Sizing and Capacity

```python
QUEUE_CAPACITY_PLANNING = {
    'redis_memory': '8GB',          # Handles 4M queued notification IDs
    'max_queue_depth': 1_000_000,   # Emergency overflow protection
    'processing_rate': 1000,        # Messages per second per worker
    'worker_count': 4,              # Initial worker pool size
    'queue_drain_time': 250,        # Seconds to drain full queue
}

# Redis memory calculation:
# - Notification ID: 8 bytes
# - Redis overhead: ~50 bytes per entry
# - 1M queued notifications = 58MB
# - 8GB supports 140M queued notifications (emergency capacity)
```

## 4. Database Schema: Write-Optimized Design

### 4.1 Notification Storage Schema

```sql
-- Main notification table with daily partitioning
CREATE TABLE notifications (
    id BIGSERIAL,
    user_id BIGINT NOT NULL,
    type VARCHAR(50) NOT NULL,
    channel VARCHAR(20) NOT NULL,
    priority VARCHAR(10) NOT NULL DEFAULT 'normal',
    title VARCHAR(255),
    body TEXT,
    data JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    scheduled_for TIMESTAMP,
    attempts SMALLINT DEFAULT 0,
    last_attempt_at TIMESTAMP,
    delivered_at TIMESTAMP,
    failed_reason TEXT
) PARTITION BY RANGE (created_at);

-- Daily partitions for write optimization
CREATE TABLE notifications_2024_01_15 PARTITION OF notifications
    FOR VALUES FROM ('2024-01-15') TO ('2024-01-16');

-- Minimal indexes for actual query patterns
CREATE INDEX idx_notifications_pending ON notifications_2024_01_15 (status, scheduled_for)
    WHERE status IN ('pending', 'retry');

CREATE INDEX idx_notifications_user_recent ON notifications_2024_01_15 (user_id, created_at DESC)
    WHERE created_at > NOW() - INTERVAL '7 days';
```

### 4.2 User Preferences: Simple Key-Value Design

```sql
-- Simplified preferences without versioning complexity
CREATE TABLE user_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Preference overrides by notification type
CREATE TABLE preference_overrides (
    user_id BIGINT,
    notification_type VARCHAR(50),
    channel VARCHAR(20),
    enabled BOOLEAN NOT NULL,
    PRIMARY KEY (user_id, notification_type, channel)
);

-- Simple preference lookup function
CREATE OR REPLACE FUNCTION should_send_notification(
    p_user_id BIGINT,
    p_notification_type VARCHAR(50),
    p_channel VARCHAR(20),
    p_scheduled_time TIMESTAMP
) RETURNS BOOLEAN AS $$
DECLARE
    user_prefs RECORD;
    override_enabled BOOLEAN;
    user_time TIMESTAMP;
BEGIN
    -- Get user preferences
    SELECT * INTO user_prefs FROM user_preferences WHERE user_id = p_user_id;
    
    -- Check for specific override
    SELECT enabled INTO override_enabled 
    FROM preference_overrides 
    WHERE user_id = p_user_id 
      AND notification_type = p_notification_type 
      AND channel = p_channel;
    
    IF override_enabled IS NOT NULL THEN
        RETURN override_enabled;
    END IF;
    
    -- Check global channel preference
    CASE p_channel
        WHEN 'push' THEN RETURN user_prefs.push_enabled;
        WHEN 'email' THEN RETURN user_prefs.email_enabled;
        WHEN 'sms' THEN RETURN user_prefs.sms_enabled;
        ELSE RETURN false;
    END CASE;
END;
$$ LANGUAGE plpgsql;
```

## 5. Accurate Cost Analysis

### 5.1 Infrastructure Costs (Monthly)

```python
INFRASTRUCTURE_COSTS = {
    # Application servers
    'app_servers': 480,           # 3x t3.large ($160 each)
    'worker_servers': 320,        # 2x t3.large for queue processing
    
    # Database
    'postgres_primary': 350,      # db.t3.medium with 500GB storage
    'postgres_replica': 175,      # Read replica for analytics
    
    # Cache and queues
    'redis': 150,                 # cache.t3.medium single instance
    
    # Load balancer and networking
    'alb': 25,                    # Application Load Balancer
    'data_transfer': 200,         # Estimated based on notification content
    
    # Monitoring and logging
    'cloudwatch': 100,            # Logs and metrics
    'datadog_basic': 180,         # 3 hosts × $60/month
    
    'total_infrastructure': 1980
}

PROVIDER_COSTS = {
    # Push notifications
    'fcm': 0,                     # Free tier covers our volume
    
    # Email via Amazon SES
    'ses_sending': 60,            # 600k emails × $0.10/1000
    'ses_receiving': 0,           # No inbound email processing
    
    # SMS via Twilio
    'sms_domestic': 750,          # 75k domestic × $0.01
    'sms_international': 1250,    # 25k international × $0.05 avg
    
    'total_providers': 2060
}

TOTAL_MONTHLY_COST = 1980 + 2060  # $4,040/month
COST_PER_USER = 4040 / 10_000_000  # $0.40 per MAU
```

### 5.2 Scaling Cost Projections

```python
def project_costs_at_scale(mau_millions):
    # Infrastructure scales in steps as we add capacity
    if mau_millions <= 15:
        infrastructure_multiplier = 1.0
    elif mau_millions <= 25:
        infrastructure_multiplier = 1.8  # Add more servers and DB capacity
    else:
        infrastructure_multiplier = 2.5  # Require cluster architecture
    
    # Provider costs scale linearly with notification volume
    provider_multiplier = mau_millions / 10
    
    infrastructure = 1980 * infrastructure_multiplier
    providers = 2060 * provider_multiplier
    
    return infrastructure + providers

# 15M MAU: $5,070/month ($0.34 per user)
# 25M MAU: $8,714/month ($0.35 per user) 
# 50M MAU: $14,260/month ($0.29 per user)
```

## 6. Realistic Implementation Plan

### 6.1 Team Allocation and Timeline

**Phase 1: Core Foundation (Weeks 1-8)**
- Engineer 1 (Senior): Database design, core notification models
- Engineer 2: Provider integrations (FCM, SES, Twilio)
- Engineer 3: Queue system and worker processes
- Engineer 4: User preference management and API

**Phase 2: Production Hardening (Weeks 9-16)**
- All engineers: Monitoring, alerting, and operational tooling
- Load testing with realistic traffic patterns
- Error handling and retry logic refinement
- Performance optimization based on test results

**Phase 3: Advanced Features (Weeks 17-24)**
- Batch processing for bulk notifications
- A/B testing framework for notification content
- Advanced user segmentation
- Analytics and reporting dashboard

### 6.2 Key Milestones and Risk Mitigation

**Week 4: Core System Demo**
- Basic notification sending through all channels
- Simple user preference controls
- Basic monitoring dashboard

**Week 8: Load Testing Checkpoint**
- System handles 1,000 notifications/second sustained
- All retry and error handling paths tested
- Performance benchmarks established

**Week 16: Production Readiness Review**
- Security audit completed
- Disaster recovery procedures tested
- Operational runbooks created
- Team trained on troubleshooting procedures

**Week 20: Soft Launch**
- Deploy to 10% of user base
- Monitor real-world performance
- Adjust capacity and configuration based on actual usage

**Week 24: Full Production Launch**
- Complete rollout to all users
- Final performance validation
- Post-launch optimization plan

## 7. Monitoring and Operational Excellence

### 7.1 Critical Metrics and Alerting

```python
CRITICAL_ALERTS = {
    'notification_send_rate': {
        'threshold': 'below 800/second for 5 minutes',
        'action': 'Page on-call engineer'
    },
    'queue_depth': {
        'threshold': 'above 100k pending notifications',
        'action': 'Auto-scale workers