# Notification System Design for Social App (10M MAU) - Final Version

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users with a 4-engineer team over 6 months. The design prioritizes rapid delivery, user experience, and operational simplicity while accommodating future growth to 50M+ MAU.

**Key Design Decisions:**
- PostgreSQL-based queue system for operational simplicity with team expertise
- Managed AWS services (SES/SNS) for delivery channels to reduce operational overhead  
- User-context-aware batching focused on experience rather than arbitrary time windows
- Conservative 6-month timeline with realistic milestones and adequate testing

## 1. System Architecture Overview

### Core Components
```
User Action → API Gateway → Notification Service → Channel Router → Managed Services (SES/SNS/FCM)
                ↓              ↓                      ↓
         PostgreSQL Queue → Preference Service → Analytics Pipeline
```

**Technology Stack:**
- **Queue System:** PostgreSQL-based with proper indexing (team expertise, ACID guarantees)
- **Database:** PostgreSQL with read replicas (proven scalability patterns)
- **Email Service:** AWS SES (managed service, predictable costs at $0.10/1000 emails)
- **Push Service:** AWS SNS + FCM/APN (managed infrastructure, token management)
- **Monitoring:** CloudWatch + Prometheus hybrid (existing AWS + detailed metrics)

### Infrastructure Sizing (Realistic Calculations)
**Notification Volume Estimates:**
- 10M MAU × 50 notifications/user/month = 500M notifications/month
- Peak: 20,000 notifications/second during high-activity periods
- Email: 50M/month (digest + transactional), SMS: 100K/month (critical only)

**Monthly Operating Costs:**
- AWS SES: $500/month (50M emails at $0.10/1000)
- PostgreSQL RDS (m5.xlarge + 2 replicas): $800/month
- Application servers (2 m5.large): $200/month
- AWS SNS: $50/month (push notifications)
- Twilio SMS: $75/month (critical only)
- **Total Infrastructure:** ~$1,625/month

## 2. Queue System Design

### PostgreSQL-Based Queue Implementation
*Rationale: Avoids Kafka operational complexity while leveraging team PostgreSQL expertise*

```sql
CREATE TABLE notification_queue (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    channel VARCHAR(20) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 3,
    payload JSONB NOT NULL,
    scheduled_at TIMESTAMP NOT NULL DEFAULT NOW(),
    attempts INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    
    INDEX idx_queue_processing (status, scheduled_at, priority),
    INDEX idx_user_notifications (user_id, created_at),
    INDEX idx_retry_processing (status, attempts, scheduled_at)
);

-- Partition by month for performance at scale
CREATE TABLE notification_queue_y2024m01 PARTITION OF notification_queue
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

**Queue Processor with Batching:**
```python
class NotificationQueueProcessor:
    def __init__(self, db_pool):
        self.db = db_pool
        self.batch_size = 100
        
    def process_batch(self):
        with self.db.get_connection() as conn:
            notifications = conn.execute("""
                UPDATE notification_queue 
                SET status = 'processing', processed_at = NOW()
                WHERE id IN (
                    SELECT id FROM notification_queue 
                    WHERE status = 'pending' 
                    AND scheduled_at <= NOW()
                    ORDER BY priority ASC, created_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING *
            """, (self.batch_size,))
            
            for notification in notifications:
                self.process_notification(notification)
```

## 3. Delivery Channel Implementation

### Push Notifications via AWS SNS
*Rationale: Managed service handles token validation, rotation, and platform differences*

```python
class PushNotificationService:
    def __init__(self):
        self.sns_client = boto3.client('sns')
        self.platform_applications = {
            'ios': 'arn:aws:sns:us-east-1:123456789:app/APNS/MyApp',
            'android': 'arn:aws:sns:us-east-1:123456789:app/GCM/MyApp'
        }
        self.rate_limiter = RateLimiter(10000, 60)  # 10K/min per AWS limits
    
    def send_notification(self, user_id: int, message: str, data: dict):
        if not self.rate_limiter.allow_request():
            raise RateLimitExceeded("Push notification rate limit exceeded")
            
        device_tokens = self.get_user_devices(user_id)
        
        for device in device_tokens:
            try:
                endpoint_arn = self.get_or_create_endpoint(device)
                
                payload = {
                    'default': message,
                    'APNS': json.dumps({
                        'aps': {'alert': message, 'badge': 1, 'sound': 'default'},
                        'custom_data': data
                    }),
                    'GCM': json.dumps({
                        'notification': {'title': 'MyApp', 'body': message},
                        'data': data
                    })
                }
                
                self.sns_client.publish(
                    TargetArn=endpoint_arn,
                    MessageStructure='json',
                    Message=json.dumps(payload)
                )
                
            except ClientError as e:
                if 'EndpointDisabled' in str(e):
                    self.disable_device_token(device.token)
                else:
                    raise
```

### Email via AWS SES with Templates
*Rationale: Managed service with predictable costs and built-in deliverability features*

```python
class EmailNotificationService:
    def __init__(self):
        self.ses_client = boto3.client('ses')
        self.templates = {
            'digest': 'weekly-digest-template',
            'security': 'security-alert-template', 
            'social': 'social-notification-template'
        }
        self.rate_limiter = RateLimiter(14, 1)  # AWS SES default: 14 emails/second
    
    def send_templated_email(self, user_id: int, template_name: str, 
                           template_data: dict):
        if not self.rate_limiter.allow_request():
            raise RateLimitExceeded("Email rate limit exceeded")
            
        user = self.get_user(user_id)
        
        self.ses_client.send_templated_email(
            Source='notifications@myapp.com',
            Destination={'ToAddresses': [user.email]},
            Template=self.templates[template_name],
            TemplateData=json.dumps(template_data),
            ConfigurationSetName='notification-tracking'
        )
```

### SMS via Twilio (Critical Only)
*Rationale: High cost limits to security alerts and payment confirmations*

```python
class SMSNotificationService:
    def __init__(self):
        self.twilio_client = Client(account_sid, auth_token)
        self.cost_per_sms = 0.0075  # $0.0075 per SMS
        
    def send_sms(self, user_id: int, message: str):
        # Only allow critical notification types
        if not self.is_critical_notification(message):
            raise ValueError("SMS limited to critical notifications only")
            
        user = self.get_user(user_id)
        if not user.phone_verified:
            raise ValueError("User phone not verified for SMS")
            
        self.twilio_client.messages.create(
            body=message,
            from_='+1234567890',
            to=user.phone_number
        )
```

## 4. Smart Batching Strategy

### User-Context-Aware Batching
*Rationale: Batching based on user activity and notification importance, not arbitrary time windows*

```python
class SmartBatcher:
    def __init__(self, db_pool, redis_client):
        self.db = db_pool
        self.redis = redis_client
    
    def should_batch_notification(self, user_id: int, notification_type: str) -> bool:
        # Never batch critical notifications
        if notification_type in ['security_alert', 'payment_failed', 'friend_request']:
            return False
            
        # Check if user is currently active (last seen < 5 minutes)
        last_activity = self.redis.get(f"user_activity:{user_id}")
        if last_activity and (time.time() - float(last_activity)) < 300:
            return False  # Send immediately to active users
        
        # Check recent notification volume to prevent spam
        recent_count = self.redis.get(f"notification_count:{user_id}:hour")
        if recent_count and int(recent_count) > 10:
            return True  # Start batching if user getting too many notifications
        
        # Batch low-priority social notifications
        return notification_type in ['like', 'comment', 'follow']
    
    def create_digest_notification(self, user_id: int, notifications: List[dict]) -> dict:
        # Group similar notifications
        grouped = defaultdict(list)
        for notif in notifications:
            key = f"{notif['type']}_{notif.get('content_id', 'general')}"
            grouped[key].append(notif)
        
        # Create smart summaries
        summaries = []
        for group in grouped.values():
            if len(group) == 1:
                summaries.append(group[0]['message'])
            else:
                summaries.append(self.create_summary_message(group))
        
        return {
            'type': 'digest',
            'message': f"You have {len(summaries)} new notifications",
            'summaries': summaries[:5],  # Limit to prevent overwhelming
            'total_count': len(notifications)
        }
    
    def create_summary_message(self, notifications: List[dict]) -> str:
        """Create intelligent summaries like 'John and 5 others liked your post'"""
        if not notifications:
            return ""
            
        notification_type = notifications[0]['type']
        if notification_type == 'like':
            if len(notifications) == 1:
                return f"{notifications[0]['actor_name']} liked your post"
            elif len(notifications) == 2:
                return f"{notifications[0]['actor_name']} and {notifications[1]['actor_name']} liked your post"
            else:
                return f"{notifications[0]['actor_name']} and {len(notifications)-1} others liked your post"
        
        # Add more summarization logic for other types
        return f"{len(notifications)} new {notification_type} notifications"
```

## 5. User Preference Management

### Simplified Preference Schema
*Rationale: Single source of truth with clear indexing strategy*

```sql
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    email_frequency VARCHAR(20) DEFAULT 'immediate', -- immediate, daily, weekly
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_user_prefs_lookup (user_id, push_enabled, email_enabled)
);

CREATE TABLE notification_type_preferences (
    user_id BIGINT,
    notification_type VARCHAR(50),
    channel VARCHAR(20),
    enabled BOOLEAN DEFAULT true,
    PRIMARY KEY (user_id, notification_type, channel),
    FOREIGN KEY (user_id) REFERENCES user_notification_preferences(user_id)
);
```

### Preference Service with Redis Caching
*Rationale: Keep Redis for performance but ensure consistency with short TTL*

```python
class PreferenceService:
    def __init__(self, db_pool, redis_client):
        self.db = db_pool
        self.redis = redis_client
        self.cache_ttl = 300  # 5 minutes - short TTL for consistency
    
    def should_send_notification(self, user_id: int, notification_type: str, 
                                channel: str) -> tuple[bool, str]:
        # Try cache first
        cache_key = f"prefs:{user_id}:{notification_type}:{channel}"
        cached_result = self.redis.get(cache_key)
        if cached_result:
            return json.loads(cached_result)
        
        # Fallback to database
        with self.db.get_connection() as conn:
            result = conn.execute("""
                SELECT 
                    p.push_enabled, p.email_enabled, p.sms_enabled,
                    p.quiet_hours_start, p.quiet_hours_end, p.timezone,
                    p.email_frequency,
                    COALESCE(ntp.enabled, true) as type_enabled
                FROM user_notification_preferences p
                LEFT JOIN notification_type_preferences ntp 
                    ON p.user_id = ntp.user_id 
                    AND ntp.notification_type = %s 
                    AND ntp.channel = %s
                WHERE p.user_id = %s
            """, (notification_type, channel, user_id))
            
            if not result:
                decision = (True, "default_allow")  # Permissive default
            else:
                prefs = result[0]
                decision = self._evaluate_preferences(prefs, notification_type, channel)
            
            # Cache the result
            self.redis.setex(cache_key, self.cache_ttl, json.dumps(decision))
            return decision
    
    def _evaluate_preferences(self, prefs, notification_type: str, channel: str) -> tuple[bool, str]:
        # Check channel enabled
        channel_enabled = getattr(prefs, f"{channel}_enabled", False)
        if not channel_enabled:
            return False, "channel_disabled"
        
        # Check notification type enabled
        if not prefs.type_enabled:
            return False, "type_disabled"
        
        # Check quiet hours (except for critical notifications)
        if self.is_quiet_hours(prefs):
            if notification_type not in ['security_alert', 'payment_failed']:
                return False, "quiet_hours"
        
        return True, "allowed"
```

## 6. Failure Handling & Reliability

### Retry Logic with Exponential Backoff
*Rationale: Simple, proven pattern without over-engineering*

```python
class RetryHandler:
    def __init__(self, db_pool):
        self.db = db_pool
        self.max_retries = {
            'push': 3,
            'email': 5,
            'sms': 2
        }
    
    def handle_failure(self, notification_id: int, error: Exception):
        with self.db.get_connection() as conn:
            result = conn.execute(
                "SELECT attempts, channel FROM notification_queue WHERE id = %s",
                (notification_id,)
            )
            
            if not result:
                return
            
            attempts, channel = result[0]
            max_attempts = self.max_retries.get(channel, 3)
            
            if self.is_permanent_failure(error):
                conn.execute(
                    "UPDATE notification_queue SET status = 'failed' WHERE id = %s",
                    (notification_id,)
                )
                
            elif attempts >= max_attempts:
                conn.execute(
                    "UPDATE notification_queue SET status = 'failed' WHERE id = %s",
                    (notification_id,)
                )
                
            else:
                #