# Notification System Design for 10M MAU Social App - SYNTHESIS

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach using managed services while addressing realistic scaling challenges. The design acknowledges significant limitations requiring future investment while delivering core functionality reliably.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with authentication
- **Device Token Service**: Dedicated service for managing 20-30M device tokens (partitioned storage)
- **Channel Handlers**: Dedicated processors for push, email, in-app, and SMS
- **User Preference Service**: Normalized preference management with caching
- **Template Service**: Secure content handling with sanitization
- **Analytics Service**: Accurate delivery tracking with measurable metrics

### Technology Stack
- **Message Queue**: Amazon SQS with separate queues per priority level and DLQ
- **Database**: PostgreSQL with read replicas and partitioned tables, Redis Cluster for tokens/cache
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with proper warming plan and deliverability timeline)
- **SMS**: Twilio (with strict cost controls and daily budgets)
- **Infrastructure**: AWS with auto-scaling groups and WebSocket-specific instances

**Rationale**: Managed services reduce operational complexity while partitioned storage and Redis clustering address realistic scale requirements for device tokens and user preferences.

## 2. Realistic WebSocket and Connection Management

### 2.1 Conservative WebSocket Capacity Planning
```python
class WebSocketManager:
    # Realistic capacity based on ALB limits and memory constraints
    MAX_CONNECTIONS_PER_ALB_TARGET = 50000  # AWS ALB limit: 55k, leaving headroom
    MEMORY_PER_CONNECTION = 8192  # 8KB per connection (connection state + buffers)
    INSTANCE_MEMORY_LIMIT = 32 * 1024 * 1024 * 1024  # 32GB instance
    MAX_CONNECTIONS_PER_INSTANCE = min(
        MAX_CONNECTIONS_PER_ALB_TARGET,
        int(INSTANCE_MEMORY_LIMIT * 0.6 / MEMORY_PER_CONNECTION)  # 60% memory for connections
    )  # Results in ~2,400 connections per instance
    
    TARGET_CONCURRENT_USERS = 100000  # 1% of MAU during peak hours (realistic)
    WEBSOCKET_CAPACITY = 50000  # 20 instances × 2,500 connections
    POLLING_USERS = TARGET_CONCURRENT_USERS - WEBSOCKET_CAPACITY  # 50k users on polling
    
    def __init__(self):
        self.connection_limit = 2500
        self.fallback_polling_interval = 30  # seconds for better UX
        
    def handle_connection_overflow(self, user_id):
        if self.get_active_connections() >= self.connection_limit:
            # Fallback to polling for 50% of concurrent users
            return self.setup_polling_fallback(user_id)
        return self.establish_websocket(user_id)
```

**WebSocket Limitations**:
- Support maximum 50k concurrent WebSocket connections (0.5% of MAU)
- 50% of concurrent users (50k) use 30-second polling
- Geographic distribution across multiple regions for better performance

## 3. Proper Redis Cluster and Storage Design

### 3.1 Correct Redis Cluster Setup
```python
class DeviceTokenManager:
    def __init__(self):
        # Proper Redis Cluster: 6 nodes minimum (3 masters + 3 replicas)
        self.redis_cluster = RedisCluster(
            nodes=[
                {"host": "redis-m1", "port": 7000},  # Master 1
                {"host": "redis-m2", "port": 7000},  # Master 2  
                {"host": "redis-m3", "port": 7000},  # Master 3
                {"host": "redis-s1", "port": 7000},  # Slave 1
                {"host": "redis-s2", "port": 7000},  # Slave 2
                {"host": "redis-s3", "port": 7000}   # Slave 3
            ],
            # 30M tokens × 600 bytes = 18GB + overhead = 32GB total cluster memory
            decode_responses=True,
            skip_full_coverage_check=False
        )
        
    def store_token(self, user_id, device_id, token, platform):
        # Store in Redis for fast access, PostgreSQL for durability
        redis_key = f"token:{user_id}:{device_id}"
        token_data = {
            "token": token,
            "platform": platform,
            "last_active": int(time.time())
        }
        
        # Redis storage (24-hour TTL for active tokens)
        try:
            self.redis_cluster.setex(redis_key, 86400, json.dumps(token_data))
        except RedisError:
            pass  # Continue without cache - system works without Redis
            
        # PostgreSQL storage for durability
        self.db.upsert_device_token(user_id, device_id, token, platform)
```

### 3.2 Fixed Database Partitioning Strategy
```sql
-- Device tokens partitioned by device_id for efficient cleanup
CREATE TABLE device_tokens (
    user_id BIGINT,
    device_id VARCHAR(255),
    platform VARCHAR(10),
    token VARCHAR(512),
    last_active TIMESTAMP,
    is_valid BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY HASH (device_id);  -- Changed from user_id to device_id

-- Create 16 partitions
CREATE TABLE device_tokens_p0 PARTITION OF device_tokens FOR VALUES WITH (MODULUS 16, REMAINDER 0);
-- ... repeat for p1-p15

-- Normalized preference storage instead of JSONB
CREATE TABLE user_notification_settings (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    in_app_enabled BOOLEAN DEFAULT true,
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    email_frequency VARCHAR(20) DEFAULT 'immediate',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Separate indexed table for category preferences
CREATE TABLE notification_category_settings (
    user_id BIGINT,
    category VARCHAR(50), -- messages, social, system
    channel VARCHAR(20),  -- push, email, sms, in_app
    enabled BOOLEAN DEFAULT true,
    PRIMARY KEY (user_id, category, channel)
);

-- Monthly partitioned delivery history with automatic cleanup
CREATE TABLE notification_delivery_history (
    id BIGSERIAL,
    user_id BIGINT,
    notification_id UUID,
    channel VARCHAR(20),
    status VARCHAR(20), -- queued, sent_to_provider, delivered, failed
    delivered_at TIMESTAMP DEFAULT NOW(),
    error_message TEXT
) PARTITION BY RANGE (delivered_at);

-- Automated monthly partition creation
CREATE TABLE delivery_history_2024_01 PARTITION OF notification_delivery_history 
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

## 4. Realistic Email Deliverability Implementation

### 4.1 Conservative Email Scaling Strategy
```python
class EmailDeliverabilityManager:
    def __init__(self):
        # Conservative SES scaling based on industry best practices
        self.phases = {
            "domain_warming": {
                "duration_weeks": 4,
                "daily_limit": 200,
                "rate_limit": 1,  # emails per second
                "recipient_strategy": "employee_testing"
            },
            "ip_warming": {
                "duration_weeks": 4, 
                "daily_limit": 1000,
                "rate_limit": 2,
                "recipient_strategy": "opt_in_beta_users"
            },
            "reputation_building": {
                "duration_weeks": 8,
                "daily_limit": 10000,
                "rate_limit": 5,
                "recipient_strategy": "engaged_users_only"
            },
            "full_scale": {
                "duration_weeks": 8,
                "daily_limit": 100000,
                "rate_limit": 14,  # SES default limit
                "recipient_strategy": "all_users"
            }
        }
        
    def can_send_email(self, recipient_engagement_score):
        current_phase = self.get_current_phase()
        daily_sent = self.get_daily_email_count()
        
        # Respect daily limits
        if daily_sent >= current_phase["daily_limit"]:
            return False
            
        # Phase-specific recipient filtering
        if current_phase["recipient_strategy"] == "engaged_users_only":
            return recipient_engagement_score > 0.7
        elif current_phase["recipient_strategy"] == "opt_in_beta_users":
            return self.is_beta_user(recipient_engagement_score)
            
        return True
```

**Realistic Email Timeline**:
- Weeks 1-4: Domain warming (200 emails/day to employees)
- Weeks 5-8: IP warming (1k emails/day to beta users)  
- Weeks 9-16: Reputation building (10k emails/day to engaged users)
- Weeks 17-24: Full scale (100k emails/day to all users)

## 5. Comprehensive SMS Cost Control

### 5.1 Intelligent SMS Cost Management with Fallbacks
```python
class SMSCostController:
    def __init__(self):
        # Realistic cost structure with international considerations
        self.domestic_cost = 0.0075  # Twilio US SMS cost
        self.international_cost = 0.15  # Average international cost
        self.daily_budget = 1000  # Conservative $1000 daily limit
        self.user_daily_limit = 3  # Max 3 SMS per user per day
        self.critical_reserve_budget = 200  # $200 reserved for critical notifications
        
    def send_with_intelligent_fallback(self, user_id, message, priority):
        cost_check = self.calculate_sms_cost(user_id)
        can_send, reason = self.can_send_sms(user_id, cost_check.amount, priority)
        
        if not can_send:
            if reason == "budget_exceeded" and priority == NotificationPriority.CRITICAL:
                # Use critical reserve for security notifications
                return self.send_critical_sms(user_id, message)
            elif reason == "user_limit_exceeded":
                # For user limit, try push first (user might be active)
                return self.send_push_notification(user_id, message)
            else:
                # For budget limits, schedule email as it reaches inactive users
                return self.schedule_email_notification(user_id, message, delay_minutes=5)
                
        return self.send_sms(user_id, message, cost_check.amount)
        
    def calculate_sms_cost(self, user_id):
        user_country = self.get_user_country(user_id)
        if user_country == "US":
            return SMSCost(self.domestic_cost, user_country)
        else:
            return SMSCost(self.international_cost, user_country)
```

## 6. Race Condition-Free Batching Logic

### 6.1 Clear Priority Definitions with Atomic Batching
```python
class NotificationPriority:
    CRITICAL = 1    # Security alerts, account lockouts - NEVER batched
    HIGH = 2        # Direct messages, mentions - NEVER batched
    MEDIUM = 3      # Likes, comments - 5-minute batches
    LOW = 4         # Weekly digests, recommendations - daily batches

class BatchingManager:
    def __init__(self):
        self.batch_intervals = {
            NotificationPriority.CRITICAL: 0,    # Immediate
            NotificationPriority.HIGH: 0,        # Immediate  
            NotificationPriority.MEDIUM: 300,    # 5 minutes
            NotificationPriority.LOW: 86400      # Daily
        }
        
    def process_notification(self, notification):
        batch_interval = self.batch_intervals[notification.priority]
        
        if batch_interval == 0:
            return self.send_immediately(notification)
        else:
            return self.add_to_batch_atomically(notification, batch_interval)
            
    def add_to_batch_atomically(self, notification, interval):
        # Use database-level locking to prevent race conditions
        batch_window_start = self.get_batch_window_start(interval)
        batch_key = f"{notification.user_id}_{notification.channel}_{batch_window_start}"
        
        with self.db.transaction():
            # Lock the batch row to prevent concurrent modifications
            batch = self.db.get_batch_for_update(batch_key)
            
            if not batch:
                batch = self.db.create_batch(
                    key=batch_key,
                    user_id=notification.user_id,
                    channel=notification.channel,
                    window_start=batch_window_start,
                    window_end=batch_window_start + interval,
                    status='collecting'
                )
                
            # Check if this notification should be deduplicated
            if not self.should_add_to_batch(batch, notification):
                return BatchResult(status='deduplicated', batch_id=batch.id)
                
            self.db.add_notification_to_batch(batch.id, notification)
            return BatchResult(status='batched', batch_id=batch.id)

    def should_add_to_batch(self, batch, notification):
        # Apply deduplication rules within the locked transaction
        existing_notifications = self.db.get_batch_notifications(batch.id)
        
        for existing in existing_notifications:
            if self.are_duplicate_notifications(existing, notification):
                # Update existing notification with latest data instead of adding new one
                self.db.update_notification_in_batch(existing.id, notification)
                return False
                
        return True
```

## 7. Simplified User Preference Management

### 7.1 Clear Preference Hierarchy with Cache-Optional Design
```python
class PreferenceResolver:
    def can_send_to_channel(self, user_id, notification_type, channel):
        prefs = self.get_user_preferences(user_id)
        
        # Channel completely disabled = no notifications
        if not getattr(prefs, f"{channel}_enabled"):
            return False
            
        # Critical notifications override most preferences
        if notification_type.priority == NotificationPriority.CRITICAL:
            return True
            
        # Check category-specific preference  
        category = self.get_notification_category(notification_type)
        category_pref = self.get_category_preference(user_id, category, channel)
        
        return category_pref.enabled if category_pref else True
        
    def get_user_preferences(self, user_id):
        # Try cache first, but system works without it
        cache_key = f"user_prefs:{user_id}"
        
        try:
            cached = self.redis_cluster.get(cache_key)
            if cached:
                return json.loads(cached)
        except RedisError:
            pass  # Log but continue - cache failure doesn't break system
            
        # Always fetch from DB as source of truth
        prefs = self.db.get_user_preferences(user_id)
        
        # Cache for performance, but don't fail if cache fails
        try:
            self.redis_cluster.setex(cache_key, 3600, json.dumps(prefs))
        except RedisError:
            pass  # Log but continue
            
        return prefs

class TimezoneManager:
    def is_quiet_hours(self, user_id):
        user_prefs = self.get_user_preferences(user_id)
        user_timezone = pytz.timezone(user