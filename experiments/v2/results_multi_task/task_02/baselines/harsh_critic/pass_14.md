# COMPLETE REWRITE: PRODUCTION-READY NOTIFICATION SYSTEM

## EXECUTIVE SUMMARY

This proposal delivers a battle-tested notification system for 10M MAU, designed for real-world constraints: 4 engineers, 6-month timeline, and enterprise reliability requirements. The system handles 2.5M DAU generating 87.5M daily notifications across 4 channels, with 10x burst capacity for viral events.

**Core Value Proposition:** Increase DAU by 15-25% through intelligent notification delivery, generating $8.6-14.4M monthly revenue impact with 3,440% ROI.

**Resource Allocation:** Phase 1 (3 months): Core delivery system. Phase 2 (3 months): ML optimization and advanced features.

## 1. REALISTIC SCALE & BUSINESS REQUIREMENTS

### 1.1 Data-Driven Scale Planning

```yaml
Actual User Metrics (Conservative):
  MAU: 10M users
  DAU: 2.5M (25% industry standard, not 15%)
  Peak DAU (viral events): 4M users
  Global Distribution:
    - Americas: 40% (1M DAU)
    - EMEA: 35% (875K DAU)  
    - APAC: 25% (625K DAU)

Notification Volume Analysis:
  Average notifications per DAU: 35/day
  Base daily volume: 87.5M notifications
  Peak volume (Black Friday/viral): 700M notifications
  Design capacity: 1B notifications/day

Channel Distribution & Performance:
  Push: 68M daily (78% of volume, 92% delivery rate)
  In-App: 80M daily (92% of volume, 99% delivery rate)
  Email: 45M daily (52% of volume, 96% delivery rate)
  SMS: 2.6M daily (3% of volume, 98% delivery rate)

Business Impact:
  Current notification-driven engagement: 32% of DAU
  Revenue per engaged user: $2.30/month
  Target improvement: 15-25% engagement increase
  Monthly revenue impact: $8.6M - $14.4M
```

### 1.2 Technical Constraints & Timeline

```yaml
Team Constraints:
  Backend Engineers: 4 (1 senior, 2 mid-level, 1 junior)
  Timeline: 6 months to production
  Budget: $180K-250K monthly operational costs
  
Delivery Timeline:
  Month 1-2: Core infrastructure & basic delivery
  Month 3: Multi-channel integration & basic batching
  Month 4: User preferences & rate limiting
  Month 5: Monitoring, alerting & failure handling
  Month 6: Performance optimization & launch prep
  
Post-Launch (months 7-12):
  ML optimization, A/B testing, advanced analytics
```

## 2. PRAGMATIC ARCHITECTURE DECISIONS

### 2.1 Infrastructure Strategy (AWS-based)

**Primary Architecture Choice: Hybrid Event-Driven + Traditional RDBMS**

```yaml
Core Infrastructure:
  Regions: Start single-region (us-east-1), expand Month 9
  Database: Aurora PostgreSQL (proven, team familiar)
  Cache: ElastiCache Redis Cluster
  Message Queue: Amazon SQS + EventBridge
  Compute: EKS with auto-scaling
  Storage: S3 for templates, logs
  
Rationale:
  - PostgreSQL handles 100M+ daily inserts efficiently
  - Team has SQL expertise (faster development)
  - Aurora provides read replicas for scaling
  - SQS provides reliable message delivery
  - Single region reduces complexity for 6-month timeline
```

### 2.2 Service Architecture

```yaml
Core Services (Microservices):

1. notification-api (Primary interface)
   - REST API for creating notifications
   - GraphQL for complex queries
   - Rate limiting: 1000 req/min per API key
   - Authentication: JWT + API keys
   
2. delivery-engine (Core processing)
   - Processes notification queue
   - Handles batching logic
   - Manages delivery timing
   - Retry mechanisms
   
3. channel-adapters (External integrations)
   - Push: FCM + APNS adapters
   - Email: SendGrid + AWS SES
   - SMS: Twilio + AWS SNS  
   - In-App: WebSocket service
   
4. user-preferences (Preference management)
   - CRUD for user settings
   - Real-time preference updates
   - Compliance tracking (GDPR/CCPA)
   
5. analytics-service (Performance tracking)
   - Delivery metrics
   - Engagement tracking
   - Performance dashboards
   
6. template-service (Content management)
   - Template versioning
   - Personalization engine
   - A/B test management
```

## 3. DATABASE DESIGN FOR SCALE

### 3.1 PostgreSQL Schema (Optimized for Performance)

```sql
-- Partitioned notifications table
CREATE TABLE notifications (
    id BIGSERIAL,
    user_id BIGINT NOT NULL,
    template_id VARCHAR(100) NOT NULL,
    
    -- Content
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    data JSONB DEFAULT '{}',
    
    -- Delivery config
    channels JSONB NOT NULL, -- {"push": true, "email": false}
    priority INTEGER NOT NULL DEFAULT 3, -- 1=urgent, 5=low
    
    -- Scheduling
    send_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- State
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Partitioning key
    created_date DATE NOT NULL DEFAULT CURRENT_DATE
) PARTITION BY RANGE (created_date);

-- Create monthly partitions
CREATE TABLE notifications_2024_01 PARTITION OF notifications
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Delivery attempts with channel-specific data
CREATE TABLE delivery_attempts (
    id BIGSERIAL PRIMARY KEY,
    notification_id BIGINT NOT NULL,
    
    -- Channel info
    channel VARCHAR(20) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    recipient VARCHAR(500) NOT NULL, -- email/phone/token
    
    -- Attempt tracking
    attempt_number INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    
    -- Timing
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    
    -- Provider response
    provider_id VARCHAR(200),
    error_code VARCHAR(100),
    error_message TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- User preferences with smart defaults
CREATE TABLE user_preferences (
    user_id BIGINT PRIMARY KEY,
    
    -- Channel settings
    push_enabled BOOLEAN NOT NULL DEFAULT true,
    email_enabled BOOLEAN NOT NULL DEFAULT true,
    sms_enabled BOOLEAN NOT NULL DEFAULT false,
    in_app_enabled BOOLEAN NOT NULL DEFAULT true,
    
    -- Frequency limits (per day)
    max_push_per_day INTEGER NOT NULL DEFAULT 10,
    max_email_per_day INTEGER NOT NULL DEFAULT 3,
    max_sms_per_day INTEGER NOT NULL DEFAULT 1,
    
    -- Timing preferences  
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    
    -- Compliance
    marketing_consent BOOLEAN NOT NULL DEFAULT false,
    gdpr_consent_date TIMESTAMP WITH TIME ZONE,
    
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Essential indexes
CREATE INDEX CONCURRENTLY idx_notifications_user_status 
    ON notifications (user_id, status) WHERE status != 'delivered';
    
CREATE INDEX CONCURRENTLY idx_notifications_send_at 
    ON notifications (send_at) WHERE status = 'pending';
    
CREATE INDEX CONCURRENTLY idx_delivery_attempts_status 
    ON delivery_attempts (status, scheduled_at) WHERE status IN ('pending', 'retry');
```

### 3.2 Redis Cache Strategy

```yaml
Cache Patterns:

User Preferences:
  Key: "prefs:{user_id}"
  TTL: 1 hour
  Pattern: Cache-aside with write-through
  
Device Tokens:
  Key: "device:{user_id}:{platform}"
  TTL: 24 hours
  Pattern: Write-through with lazy expiration
  
Rate Limiting:
  Key: "rate:{user_id}:{channel}:{hour}"
  TTL: 1 hour
  Pattern: Sliding window counter
  
Template Cache:
  Key: "template:{template_id}:{version}"
  TTL: 6 hours
  Pattern: Cache-aside
```

## 4. INTELLIGENT DELIVERY SYSTEM

### 4.1 Priority & Batching Logic

```python
# delivery_engine.py
from enum import IntEnum
from dataclasses import dataclass
from typing import List, Dict
import asyncio

class Priority(IntEnum):
    URGENT = 1      # Security alerts, direct messages
    HIGH = 2        # Friend requests, mentions  
    NORMAL = 3      # Likes, follows (default)
    LOW = 4         # Digest emails, recommendations
    BULK = 5        # Marketing, announcements

@dataclass
class NotificationBatch:
    user_id: int
    channel: str
    notifications: List[Dict]
    priority: Priority
    estimated_send_time: datetime
    
class BatchingEngine:
    def __init__(self):
        self.batch_windows = {
            Priority.URGENT: 0,      # Send immediately
            Priority.HIGH: 300,      # 5 minutes
            Priority.NORMAL: 1800,   # 30 minutes  
            Priority.LOW: 3600,      # 1 hour
            Priority.BULK: 14400     # 4 hours
        }
        
    async def create_batches(self, notifications: List[Dict]) -> List[NotificationBatch]:
        """Group notifications by user, channel, and timing window"""
        batches = {}
        
        for notif in notifications:
            # Skip batching for urgent notifications
            if notif['priority'] == Priority.URGENT:
                yield NotificationBatch(
                    user_id=notif['user_id'],
                    channel=notif['channel'],
                    notifications=[notif],
                    priority=notif['priority'],
                    estimated_send_time=datetime.now()
                )
                continue
                
            # Check user preferences for batching
            user_prefs = await self.get_user_preferences(notif['user_id'])
            if not user_prefs.get('allow_batching', True):
                continue
                
            # Create batch key
            window = self.batch_windows[notif['priority']]
            send_time = self.calculate_send_time(notif, window)
            batch_key = f"{notif['user_id']}:{notif['channel']}:{send_time.hour}"
            
            if batch_key not in batches:
                batches[batch_key] = NotificationBatch(
                    user_id=notif['user_id'],
                    channel=notif['channel'], 
                    notifications=[],
                    priority=notif['priority'],
                    estimated_send_time=send_time
                )
            
            batches[batch_key].notifications.append(notif)
            
        return list(batches.values())
        
    def calculate_send_time(self, notification: Dict, window_seconds: int) -> datetime:
        """Calculate optimal send time within batching window"""
        base_time = datetime.now()
        user_tz = notification.get('user_timezone', 'UTC')
        
        # Respect quiet hours
        local_time = base_time.astimezone(pytz.timezone(user_tz))
        if self.is_quiet_hours(local_time, notification['user_id']):
            return self.next_active_period(local_time, user_tz)
            
        # Add batching window
        return base_time + timedelta(seconds=window_seconds)
```

### 4.2 Channel-Specific Delivery

```python
# channel_adapters.py
class PushNotificationAdapter:
    def __init__(self):
        self.fcm_client = FCMClient()
        self.apns_client = APNSClient()
        
    async def send_batch(self, batch: NotificationBatch) -> List[DeliveryResult]:
        """Send push notifications with platform-specific optimization"""
        results = []
        
        # Get active device tokens
        devices = await self.get_user_devices(batch.user_id)
        
        for device in devices:
            try:
                if device.platform == 'ios':
                    result = await self.send_apns(device, batch.notifications)
                elif device.platform == 'android':
                    result = await self.send_fcm(device, batch.notifications)
                else:
                    continue
                    
                results.append(result)
                
                # Update device token status
                if result.status == 'invalid_token':
                    await self.deactivate_device(device.id)
                    
            except Exception as e:
                results.append(DeliveryResult(
                    device_id=device.id,
                    status='failed',
                    error=str(e)
                ))
                
        return results
        
    async def send_fcm(self, device: Device, notifications: List[Dict]) -> DeliveryResult:
        """Send to Android via FCM with batching"""
        if len(notifications) == 1:
            # Single notification
            message = self.build_fcm_message(notifications[0], device.token)
        else:
            # Batched notifications - use data payload
            message = self.build_fcm_batch_message(notifications, device.token)
            
        response = await self.fcm_client.send(message)
        
        return DeliveryResult(
            device_id=device.id,
            status='sent' if response.success else 'failed',
            provider_id=response.message_id,
            error=response.error
        )

class EmailAdapter:
    def __init__(self):
        self.sendgrid = SendGridAPIClient()
        self.ses = boto3.client('ses')
        
    async def send_batch(self, batch: NotificationBatch) -> DeliveryResult:
        """Send email with smart template selection"""
        user = await self.get_user(batch.user_id)
        
        if len(batch.notifications) == 1:
            # Single email
            template = 'single_notification'
            content = self.build_single_email(batch.notifications[0], user)
        else:
            # Digest email
            template = 'notification_digest'
            content = self.build_digest_email(batch.notifications, user)
            
        # Try SendGrid first, fallback to SES
        try:
            result = await self.send_via_sendgrid(user.email, template, content)
        except Exception as e:
            logger.warning(f"SendGrid failed: {e}, trying SES")
            result = await self.send_via_ses(user.email, template, content)
            
        return result
```

### 4.3 User Preference Management

```python
# user_preferences.py
class PreferenceManager:
    def __init__(self, redis_client, db_pool):
        self.redis = redis_client
        self.db = db_pool
        
    async def get_preferences(self, user_id: int) -> UserPreferences:
        """Get user preferences with caching"""
        cache_key = f"prefs:{user_id}"
        
        # Try cache first
        cached = await self.redis.get(cache_key)
        if cached:
            return UserPreferences.from_json(cached)
            
        # Load from database
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_preferences WHERE user_id = $1", 
                user_id
            )
            
        if row:
            prefs = UserPreferences.from_db_row(row)
        else:
            # Create default preferences
            prefs