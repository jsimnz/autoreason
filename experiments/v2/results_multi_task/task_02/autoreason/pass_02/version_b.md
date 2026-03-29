# Notification System Design for 10M MAU Social App (REVISED)

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach that can handle scale while acknowledging significant limitations that will require future investment.

## 1. System Architecture Overview (Addressing Scaling Reality)

### Core Components
- **Notification Service**: Central orchestrator with authentication
- **Device Token Service**: Dedicated service for managing 20-30M device tokens
- **Channel Handlers**: Dedicated processors for push, email, in-app, and SMS
- **User Preference Service**: Simplified preference management
- **Template Service**: Secure content handling with sanitization
- **Analytics Service**: Accurate delivery tracking

### Technology Stack
- **Message Queue**: Amazon SQS with separate queues per priority level
- **Database**: PostgreSQL with read replicas for preferences, Redis Cluster for tokens/cache
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with proper warming plan)
- **SMS**: Twilio (with strict cost controls)
- **Infrastructure**: AWS with auto-scaling groups and WebSocket-specific instances

**Problem Fixed**: Addresses "Fundamental Scaling Assumptions Are Wrong" by properly sizing token storage and WebSocket infrastructure.

## 2. Device Token and WebSocket Management (Addressing Scale Reality)

### 2.1 Device Token Storage at Scale
```sql
-- Partitioned table for 30M+ device tokens
CREATE TABLE device_tokens (
    user_id BIGINT,
    device_id VARCHAR(255),
    platform VARCHAR(10),
    token VARCHAR(512),
    last_active TIMESTAMP,
    is_valid BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY HASH (user_id);

-- Create 16 partitions to distribute load
CREATE TABLE device_tokens_p0 PARTITION OF device_tokens FOR VALUES WITH (MODULUS 16, REMAINDER 0);
-- ... repeat for p1-p15
```

**Redis Cluster Configuration**:
```python
# Distributed token storage across Redis cluster
class DeviceTokenManager:
    def __init__(self):
        self.redis_cluster = RedisCluster(
            nodes=[
                {"host": "redis-1", "port": 7000},
                {"host": "redis-2", "port": 7000},
                {"host": "redis-3", "port": 7000}
            ]
        )
    
    def store_token(self, user_id, device_id, token):
        key = f"token:{user_id}:{device_id}"
        self.redis_cluster.setex(key, 86400 * 30, token)  # 30-day TTL
```

**Problem Fixed**: Addresses "Device Token Management is Severely Underestimated" by using partitioned tables and Redis clustering.

### 2.2 Limited WebSocket Strategy
```python
# Realistic WebSocket capacity planning
class WebSocketManager:
    MAX_CONNECTIONS_PER_INSTANCE = 5000  # Conservative estimate
    TARGET_CONCURRENT_USERS = 100000     # 1% of MAU, not 10%
    REQUIRED_INSTANCES = 20               # 100k / 5k per instance
    
    def __init__(self):
        self.connection_limit = 5000
        self.fallback_polling_interval = 30  # seconds
```

**WebSocket Limitation Strategy**:
- Support maximum 100k concurrent WebSocket connections (1% of MAU)
- Aggressive fallback to 30-second polling for additional users
- Clear user communication about real-time limitations

**Problem Fixed**: Addresses "WebSocket Connection Math Doesn't Work" by setting realistic limits and fallback strategies.

## 3. Database Design That Can Actually Scale

### 3.1 Simplified Preference Schema
```sql
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
    email_frequency VARCHAR(20) DEFAULT 'immediate', -- immediate, daily, weekly
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Separate table for category preferences
CREATE TABLE notification_category_settings (
    user_id BIGINT,
    category VARCHAR(50), -- messages, social, system
    channel VARCHAR(20),  -- push, email, sms, in_app
    enabled BOOLEAN DEFAULT true,
    PRIMARY KEY (user_id, category, channel)
);
```

**Problem Fixed**: Addresses "JSONB Preference Storage Won't Scale" by using normalized tables with indexed columns.

### 3.2 Redis as Cache, Not Critical Path
```python
class PreferenceService:
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour
        
    def get_user_preferences(self, user_id):
        # Try cache first, but system works without it
        cache_key = f"user_prefs:{user_id}"
        cached = redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
            
        # Always fetch from DB as source of truth
        prefs = self.db.get_user_preferences(user_id)
        
        # Cache for performance, but don't fail if cache fails
        try:
            redis.setex(cache_key, self.cache_ttl, json.dumps(prefs))
        except RedisError:
            pass  # Log but continue
            
        return prefs
```

**Problem Fixed**: Addresses "Redis as 'Cache Layer' Is Actually Critical Path" by making Redis optional for performance, not correctness.

### 3.3 Delivery History with Partitioning
```sql
-- Monthly partitioned delivery history
CREATE TABLE notification_delivery_history (
    id BIGSERIAL,
    user_id BIGINT,
    notification_id UUID,
    channel VARCHAR(20),
    status VARCHAR(20),
    delivered_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (delivered_at);

-- Create monthly partitions with automatic cleanup
CREATE TABLE delivery_history_2024_01 PARTITION OF notification_delivery_history 
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

**Problem Fixed**: Addresses "30-Day Delivery History Storage" by using monthly partitions with automated cleanup.

## 4. Channel-Specific Realistic Implementation

### 4.1 SMS Cost Controls
```python
class SMSCostController:
    def __init__(self):
        self.daily_budget = 1000  # $1000 daily limit
        self.user_daily_limit = 3  # Max 3 SMS per user per day
        self.cost_per_sms = 0.05  # Conservative estimate
        
    def can_send_sms(self, user_id):
        daily_spend = self.get_daily_spend()
        if daily_spend >= self.daily_budget:
            return False, "Daily budget exceeded"
            
        user_count = self.get_user_daily_count(user_id)
        if user_count >= self.user_daily_limit:
            return False, "User daily limit exceeded"
            
        return True, None
        
    def send_with_fallback(self, user_id, message):
        can_send, reason = self.can_send_sms(user_id)
        if not can_send:
            # Fallback to push notification
            return self.send_push_notification(user_id, message)
        return self.send_sms(user_id, message)
```

**Problem Fixed**: Addresses "SMS Cost Explosion" with strict daily budgets and per-user limits.

### 4.2 Email Deliverability Plan
```python
class EmailDeliverabilityManager:
    def __init__(self):
        # SES sending limits start low and require gradual increase
        self.current_daily_limit = 200
        self.current_rate_limit = 1  # emails per second
        self.target_daily_limit = 100000  # Will take months to reach
        
    def can_send_email(self):
        daily_sent = self.get_daily_email_count()
        return daily_sent < self.current_daily_limit
        
    def request_limit_increase(self):
        # Automated process to request SES limit increases
        # Based on bounce/complaint rates and sending history
        if self.get_bounce_rate() < 0.05 and self.get_complaint_rate() < 0.001:
            return self.submit_ses_limit_increase_request()
```

**Deliverability Timeline**:
- Month 1: 200 emails/day (testing only)
- Month 2: 1,000 emails/day (limited user testing)
- Month 3: 10,000 emails/day (gradual rollout)
- Month 4-6: Scale to 100k+ emails/day through SES reputation building

**Problem Fixed**: Addresses "Email Deliverability Reality" with realistic SES scaling timeline.

### 4.3 APNs Certificate Management
```python
class APNSCertificateManager:
    def __init__(self):
        self.cert_expiry_warning_days = 30
        
    def check_certificate_expiry(self):
        cert_expiry = self.get_certificate_expiry_date()
        days_until_expiry = (cert_expiry - datetime.now()).days
        
        if days_until_expiry <= self.cert_expiry_warning_days:
            self.send_alert_to_team()
            
    def rotate_certificate(self, new_cert_path):
        # Blue-green deployment for certificate rotation
        self.deploy_new_cert_to_staging()
        self.validate_staging_notifications()
        self.deploy_new_cert_to_production()
```

**Problem Fixed**: Addresses "APNs Certificate Management" with automated monitoring and rotation procedures.

## 5. Simplified Priority and Batching Logic

### 5.1 Clear Priority Definitions
```python
class NotificationPriority:
    CRITICAL = 1    # Security alerts, account lockouts - NEVER batched
    HIGH = 2        # Direct messages, mentions - NEVER batched  
    MEDIUM = 3      # Likes, comments - 5-minute batches
    LOW = 4         # Weekly digests, recommendations - daily batches

class BatchingRules:
    def get_delivery_strategy(self, priority):
        if priority <= NotificationPriority.HIGH:
            return "immediate"
        elif priority == NotificationPriority.MEDIUM:
            return "5_minute_batch"
        else:
            return "daily_batch"
```

**Problem Fixed**: Addresses "5-Minute Batching Windows Are Arbitrary" by clearly defining which notifications get batched and why.

### 5.2 Explicit Deduplication Rules
```python
class DeduplicationManager:
    def __init__(self):
        self.dedup_rules = {
            "like": {"window_minutes": 60, "max_notifications": 1},
            "comment": {"window_minutes": 30, "max_notifications": 3},
            "follow": {"window_minutes": 1440, "max_notifications": 1}  # 24 hours
        }
    
    def should_send_notification(self, user_id, notification_type, content_id):
        rule = self.dedup_rules.get(notification_type)
        if not rule:
            return True  # No dedup rule = always send
            
        recent_count = self.get_recent_notification_count(
            user_id, notification_type, content_id, rule["window_minutes"]
        )
        
        return recent_count < rule["max_notifications"]
```

**Problem Fixed**: Addresses "Deduplication Without Clear Rules" by defining specific business logic for each notification type.

## 6. Realistic Preference Management

### 6.1 Simplified Timezone Handling
```python
class TimezoneManager:
    def is_quiet_hours(self, user_id):
        user_prefs = self.get_user_preferences(user_id)
        user_timezone = pytz.timezone(user_prefs.timezone)
        user_time = datetime.now(user_timezone).time()
        
        start = user_prefs.quiet_hours_start
        end = user_prefs.quiet_hours_end
        
        # Handle overnight quiet hours (e.g., 22:00 to 08:00)
        if start > end:
            return user_time >= start or user_time <= end
        else:
            return start <= user_time <= end
            
    def apply_quiet_hours_rule(self, user_id, notification):
        # Critical notifications ignore quiet hours
        if notification.priority == NotificationPriority.CRITICAL:
            return True
            
        return not self.is_quiet_hours(user_id)
```

**Problem Fixed**: Addresses "Quiet Hours Across Timezones" by using individual user timezones and clear override rules for critical notifications.

### 6.2 Simplified Preference UI Logic
```python
class PreferenceResolver:
    def can_send_to_channel(self, user_id, notification_type, channel):
        prefs = self.get_user_preferences(user_id)
        
        # Channel completely disabled = no notifications
        if not getattr(prefs, f"{channel}_enabled"):
            return False
            
        # Check category-specific preference
        category = self.get_notification_category(notification_type)
        category_pref = self.get_category_preference(user_id, category, channel)
        
        return category_pref.enabled if category_pref else True
```

**Problem Fixed**: Addresses "Category vs Channel Preference Conflicts" by implementing clear hierarchy: channel-level settings override category-level settings.

## 7. Proper Monitoring and Alerting

### 7.1 Measurable Delivery Metrics
```python
class DeliveryMetrics:
    def track_notification_attempt(self, notification_id, channel, status):
        # Track at multiple stages for accurate measurement
        stages = {
            "queued": "Notification added to queue",
            "processed": "Picked up by worker",
            "sent_to_provider": "Sent to FCM/APNs/SES/Twilio",
            "provider_accepted": "Provider returned success",
            "delivered": "Provider confirmed delivery (where available)",
            "failed": "Failed at any stage"
        }
        
        self.metrics_client.increment(f"notification.{channel}.{status}")
        self.store_delivery_event(notification_id, channel, status, datetime.now())
        
    def calculate_delivery_rate(self, channel, time_window_hours=24):
        total_sent = self.get_metric_count(f"notification.{channel}.sent_to_provider", time_window_hours)
        total_failed = self.get_metric_count(f"notification.{channel}.failed", time_window_hours)
        
        if total_sent == 0:
            return 0
            
        return ((total_sent - total_failed) / total_sent) * 100
```

**Problem Fixed**: Addresses "'Delivery Rate >98%' Is Unmeasurable" by defining specific tracking points and calculation methods.

### 7.2 Failed Delivery Recovery
```python
class FailedDeliveryHandler:
    def handle_permanent_failure(self, notification, error):
        if notification.priority == NotificationPriority.CRITICAL:
            # Critical notifications require manual intervention
            self.escalate_to_support_team(notification, error)
            
            # Try alternative channels for critical notifications
            if notification.channel == "push":
                self.retry_via_email(notification)
            elif notification.channel == "email":
                self.retry_via_sms(notification)
                
        else:
            # Non-critical failures are logged but not retried
            self.log_failure(notification, error)
            self.update_user_delivery_stats(notification.user_id, "failed")
```

**Problem Fixed**: Addresses "No Failed Delivery Recovery Strategy" by implementing channel fallback for critical notifications and proper escalation procedures.

## 8. Security and Compliance

### 8.1 Authentication and