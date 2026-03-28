# Revised Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a pragmatic notification system supporting 10M monthly active users with a 4-engineer team over 6 months. The design prioritizes operational simplicity, realistic costs, and proven patterns while delivering core functionality reliably.

**Key Design Decisions:**
- Database-backed queue system using PostgreSQL for simplicity and team expertise
- AWS SES + SNS for managed delivery services to reduce operational overhead
- Minimal batching focused on user experience rather than arbitrary time windows
- Conservative timeline with realistic milestones and adequate buffer time

## 1. System Architecture Overview

### Core Components
```
User Action → API Gateway → Notification Service → Channel Router → Managed Services (SES/SNS/FCM)
                ↓              ↓                      ↓
         PostgreSQL Queue → Preference Service → Analytics Pipeline
```

**Technology Stack:**
- **Queue System:** PostgreSQL-based (team expertise, ACID guarantees) - *Fixes Problem #2: Kafka overkill*
- **Database:** PostgreSQL with proper indexing (proven scalability patterns) - *Fixes Problem #5: Database design*
- **Email Service:** AWS SES (managed service, predictable costs) - *Fixes Problem #1: Cost analysis*
- **Push Service:** AWS SNS + FCM/APN (managed infrastructure) - *Fixes Problem #6: Push implementation*
- **Monitoring:** CloudWatch + custom dashboards (existing AWS integration)

### Infrastructure Sizing (Realistic Calculations)
**Notification Volume Estimates:**
- 10M MAU × 30 notifications/user/month = 300M notifications/month
- Peak: 15,000 notifications/second during high-activity periods
- Email: 50M/month (digest + transactional), SMS: 100K/month (critical only)

**AWS SES Costs:** $500/month (50M emails at $0.10/1000) - *Fixes Problem #1: Unrealistic cost analysis*
**Infrastructure:** 2 m5.large instances ($200/month), RDS PostgreSQL ($400/month)
**Total Monthly Cost:** ~$1,100/month

## 2. Queue System Design

### PostgreSQL-Based Queue Implementation
*Fixes Problem #2: Kafka operational complexity*

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
```

**Queue Processor:**
```python
class NotificationQueueProcessor:
    def __init__(self, db_pool):
        self.db = db_pool
        self.batch_size = 100
        
    def process_batch(self):
        # Simple SQL-based queue processing
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
*Fixes Problem #6: Push notification oversimplification*

```python
class PushNotificationService:
    def __init__(self):
        self.sns_client = boto3.client('sns')
        self.platform_applications = {
            'ios': 'arn:aws:sns:us-east-1:123456789:app/APNS/MyApp',
            'android': 'arn:aws:sns:us-east-1:123456789:app/GCM/MyApp'
        }
    
    def send_notification(self, user_id: int, message: str, data: dict):
        device_tokens = self.get_user_devices(user_id)
        
        for device in device_tokens:
            try:
                # SNS handles token validation and rotation
                endpoint_arn = self.create_platform_endpoint(device)
                
                payload = {
                    'default': message,
                    'APNS': json.dumps({
                        'aps': {'alert': message, 'badge': 1},
                        'custom_data': data
                    }),
                    'GCM': json.dumps({
                        'data': {'message': message, **data}
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
*Fixes Problem #1: Cost analysis and Problem #8: Missing production requirements*

```python
class EmailNotificationService:
    def __init__(self):
        self.ses_client = boto3.client('ses')
        self.templates = {
            'digest': 'weekly-digest-template',
            'security': 'security-alert-template',
            'social': 'social-notification-template'
        }
    
    def send_templated_email(self, user_id: int, template_name: str, 
                           template_data: dict):
        user = self.get_user(user_id)
        
        # Rate limiting per user
        if not self.check_email_rate_limit(user_id):
            raise RateLimitExceeded(f"Email rate limit exceeded for user {user_id}")
        
        self.ses_client.send_templated_email(
            Source='notifications@myapp.com',
            Destination={'ToAddresses': [user.email]},
            Template=self.templates[template_name],
            TemplateData=json.dumps(template_data),
            ConfigurationSetName='notification-tracking'  # For analytics
        )
```

## 4. Smart Batching Strategy

### User-Context-Aware Batching
*Fixes Problem #3: Batching logic UX disasters*

```python
class SmartBatcher:
    def __init__(self, db_pool, redis_client):
        self.db = db_pool
        self.redis = redis_client
    
    def should_batch_notification(self, user_id: int, notification_type: str) -> bool:
        # Check if user is currently active (last seen < 5 minutes)
        last_activity = self.redis.get(f"user_activity:{user_id}")
        if last_activity and (time.time() - float(last_activity)) < 300:
            return False  # Send immediately to active users
        
        # Check if this is a critical notification
        if notification_type in ['security_alert', 'payment_failed', 'friend_request']:
            return False  # Never batch critical notifications
        
        # Check recent notification volume
        recent_count = self.redis.get(f"notification_count:{user_id}:hour")
        if recent_count and int(recent_count) > 10:
            return True  # Start batching if user getting too many notifications
        
        return notification_type in ['like', 'comment', 'follow']
    
    def create_digest_notification(self, user_id: int, notifications: List[dict]) -> dict:
        # Group similar notifications
        grouped = {}
        for notif in notifications:
            key = f"{notif['type']}_{notif.get('content_id', 'general')}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(notif)
        
        # Create summary messages
        summaries = []
        for group in grouped.values():
            if len(group) == 1:
                summaries.append(group[0]['message'])
            else:
                # Smart summarization
                summaries.append(self.create_summary_message(group))
        
        return {
            'type': 'digest',
            'message': f"You have {len(summaries)} new notifications",
            'summaries': summaries[:5],  # Limit to prevent overwhelming
            'total_count': len(notifications)
        }
```

## 5. User Preference Management

### Simplified Preference Schema
*Fixes Problem #5: Database design scaling issues and Problem #14: Consistency nightmares*

```sql
-- Separate table for each preference type for better indexing
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
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Separate table for granular notification type preferences
CREATE TABLE notification_type_preferences (
    user_id BIGINT,
    notification_type VARCHAR(50),
    channel VARCHAR(20),
    enabled BOOLEAN DEFAULT true,
    PRIMARY KEY (user_id, notification_type, channel),
    FOREIGN KEY (user_id) REFERENCES user_notification_preferences(user_id)
);
```

### Preference Service with Single Source of Truth
*Fixes Problem #14: Multi-layer caching consistency*

```python
class PreferenceService:
    def __init__(self, db_pool):
        self.db = db_pool
        # No Redis caching - keep it simple and consistent
    
    def should_send_notification(self, user_id: int, notification_type: str, 
                                channel: str) -> tuple[bool, str]:
        with self.db.get_connection() as conn:
            # Single query to get all relevant preferences
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
                return True, "default_allow"  # Permissive default for new users
            
            prefs = result[0]
            
            # Check channel enabled
            channel_enabled = getattr(prefs, f"{channel}_enabled", False)
            if not channel_enabled:
                return False, "channel_disabled"
            
            # Check notification type enabled
            if not prefs.type_enabled:
                return False, "type_disabled"
            
            # Check quiet hours
            if self.is_quiet_hours(prefs):
                if notification_type not in ['security_alert', 'payment_failed']:
                    return False, "quiet_hours"
            
            return True, "allowed"
    
    def is_quiet_hours(self, prefs) -> bool:
        if not prefs.quiet_hours_start or not prefs.quiet_hours_end:
            return False
        
        # Simple timezone handling - convert to UTC for comparison
        user_tz = pytz.timezone(prefs.timezone)
        now_utc = datetime.utcnow()
        user_time = now_utc.replace(tzinfo=pytz.UTC).astimezone(user_tz).time()
        
        return prefs.quiet_hours_start <= user_time <= prefs.quiet_hours_end
```

## 6. Failure Handling & Reliability

### Simple Retry Logic with Exponential Backoff
*Fixes Problem #10: Circuit breaker misapplication*

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
            # Get current attempt count
            result = conn.execute(
                "SELECT attempts, channel FROM notification_queue WHERE id = %s",
                (notification_id,)
            )
            
            if not result:
                return
            
            attempts, channel = result[0]
            max_attempts = self.max_retries.get(channel, 3)
            
            if self.is_permanent_failure(error):
                # Mark as failed permanently
                conn.execute(
                    "UPDATE notification_queue SET status = 'failed' WHERE id = %s",
                    (notification_id,)
                )
                self.log_permanent_failure(notification_id, error)
                
            elif attempts >= max_attempts:
                # Exceeded retry limit
                conn.execute(
                    "UPDATE notification_queue SET status = 'failed' WHERE id = %s",
                    (notification_id,)
                )
                
            else:
                # Schedule retry with exponential backoff
                delay_seconds = (2 ** attempts) * 60  # 1min, 2min, 4min, etc.
                retry_time = datetime.utcnow() + timedelta(seconds=delay_seconds)
                
                conn.execute("""
                    UPDATE notification_queue 
                    SET status = 'pending', attempts = attempts + 1, 
                        scheduled_at = %s
                    WHERE id = %s
                """, (retry_time, notification_id))
    
    def is_permanent_failure(self, error: Exception) -> bool:
        # Define permanent failures that shouldn't be retried
        permanent_errors = [
            'InvalidParameterValue',  # Bad email address
            'MessageRejected',        # Spam/blocked
            'EndpointDisabled'        # Invalid device token
        ]
        return any(err in str(error) for err in permanent_errors)
```

## 7. Realistic Timeline & Team Allocation

### 8-Month Timeline with Buffer Time
*Fixes Problem #7: Unrealistic timeline*

**Team Allocation:**
- **Senior Engineer (Lead):** Architecture, database design, deployment
- **Mid-level Engineer 1:** Push notification service, mobile SDK integration
- **Mid-level Engineer 2:** Email/SMS services, AWS integrations
- **Junior Engineer:** Preference management, basic web UI, testing support

### Phased Delivery Schedule

**Month 1-2: Foundation**
- PostgreSQL queue system setup and testing
- Basic notification service with database integration
- Push notification service (SNS integration only)
- Simple preference management (boolean flags only)

**Month 3-4: Core Features**
- Email service integration (AWS SES)
- Basic batching logic for non-critical notifications
- Preference management UI
- Monitoring and alerting setup

**Month 5-6: Enhanced Features**  
- SMS integration for critical notifications
- Smart batching with user activity detection
- Retry logic and failure handling
- Performance optimization

**Month 7: Production Preparation**
- Security audit and penetration testing
- Load testing with realistic traffic patterns
- Documentation and runbooks
- Staged rollout preparation (5% → 25% → 100%)

**Month 8: Rollout & Stabilization**
- Production rollout with monitoring
- Bug fixes and performance tuning
- Post-launch optimization
- Team knowledge transfer

## 8. Monitoring & Success Metrics

### Actionable Monitoring Strategy
*Fixes Problem #13: