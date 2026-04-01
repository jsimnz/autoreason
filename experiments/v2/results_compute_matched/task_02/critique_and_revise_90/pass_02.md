## Critical Review of Proposal

### Major Problems Identified:

1. **Broken Aggregation Strategy**: The notification aggregation logic using Redis with 5-minute windows will lose data during service restarts and doesn't handle edge cases like users liking/unliking posts.

2. **Missing Rate Limiting**: No protection against notification spam - a viral post could generate millions of notifications and overwhelm the system.

3. **Unrealistic Database Design**: Single PostgreSQL instance can't handle 50M writes/day (578 writes/second) plus reads. No sharding or partitioning strategy.

4. **FCM Rate Limits Ignored**: FCM has strict rate limits (2,500 QPS per project) that aren't accounted for in the 2,200/second peak calculation.

5. **Redis Single Point of Failure**: Using Redis Streams for queuing without persistence or clustering creates data loss risk.

6. **No Delivery Tracking**: Claims to track delivery but doesn't explain how to handle FCM delivery receipts or failed deliveries at scale.

7. **Cost Analysis Missing**: Ignores compute, database, Redis, and monitoring costs - only mentions provider API costs.

8. **Timezone Handling Broken**: Quiet hours logic doesn't account for users traveling or changing timezones frequently.

9. **Template System Too Rigid**: Hard-coded templates can't handle internationalization or dynamic social contexts.

10. **Missing Critical Features**: No deduplication, no notification history cleanup, no analytics for optimization.

---

# Revised: Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a **production-ready** notification system for a social app with 10M MAU, deliverable in 6 months by 4 backend engineers. The design emphasizes reliability, cost control, and operational simplicity while handling real-world social app notification patterns.

**Key Design Principles:**
- Database-first architecture for reliability
- Built-in rate limiting and spam protection
- Gradual rollout strategy
- Clear operational procedures

## 1. Realistic Scale Analysis & Constraints

### Traffic Projections
```
10M MAU = ~2M DAU (20% DAU/MAU for growing social app)
Peak concurrent users: ~400K (20% of DAU)
Notification events per DAU: 15-25 (likes, comments, follows, posts)
Total daily events: 40M
Peak hourly: 6M events (15% of daily volume)
Peak per-second: 1,667 events

After aggregation and filtering: ~20M final notifications/day
Peak delivery rate: ~800 notifications/second
```

### Channel Distribution & Delivery Rates
- **Push**: 70% attempt rate, 60% actual delivery (device offline, uninstalled apps)
- **In-App**: 100% storage, ~40% viewed (when users open app)
- **Email**: 15% of users opt-in, daily digest only
- **SMS**: Security events only, <1K/month

### Budget Constraints (Realistic for Series A)
- **Total monthly budget**: $15K
- **Infrastructure**: $8K (compute, database, monitoring)
- **Third-party APIs**: $7K (FCM free, SendGrid $500, Twilio $500, misc $6K buffer)

## 2. Database-First Architecture

### Core Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   App Events    │───▶│  Notification    │───▶│   Delivery      │
│   (API calls)   │    │   Processor      │    │   Workers       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                          │
                              ▼                          ▼
                       ┌──────────────┐         ┌─────────────────┐
                       │  PostgreSQL  │         │ FCM/SendGrid/   │
                       │  (Clustered) │         │    Twilio       │
                       └──────────────┘         └─────────────────┘
```

### Database Schema (Production-Ready)
```sql
-- Partitioned by month for performance
CREATE TABLE notifications (
    id BIGSERIAL,
    user_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    content JSONB NOT NULL,
    aggregation_key VARCHAR(200), -- For grouping similar notifications
    priority INTEGER DEFAULT 3, -- 1=critical, 2=high, 3=normal
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scheduled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE notifications_2024_01 PARTITION OF notifications 
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Delivery tracking
CREATE TABLE notification_deliveries (
    notification_id BIGINT,
    channel VARCHAR(20), -- 'push', 'email', 'sms', 'in_app'
    status VARCHAR(20), -- 'pending', 'sent', 'delivered', 'failed', 'clicked'
    provider_id VARCHAR(200), -- FCM message ID, SendGrid message ID, etc.
    error_message TEXT,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivered_at TIMESTAMP,
    PRIMARY KEY (notification_id, channel)
);

-- User preferences with versioning
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT false, -- Opt-in only
    quiet_hours_start INTEGER, -- 0-23, in user's local time
    quiet_hours_end INTEGER,
    timezone VARCHAR(50) DEFAULT 'UTC',
    version INTEGER DEFAULT 1, -- For preference change tracking
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Rate limiting per user
CREATE TABLE user_notification_limits (
    user_id BIGINT,
    date DATE,
    push_count INTEGER DEFAULT 0,
    email_count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, date)
);

-- Device tokens with health tracking
CREATE TABLE user_devices (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    device_token VARCHAR(255) NOT NULL,
    platform VARCHAR(20) NOT NULL, -- 'ios', 'android', 'web'
    is_active BOOLEAN DEFAULT true,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    failure_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_notifications_user_created ON notifications(user_id, created_at);
CREATE INDEX idx_notifications_scheduled ON notifications(scheduled_at) WHERE scheduled_at > created_at;
CREATE INDEX idx_notifications_aggregation ON notifications(user_id, aggregation_key, created_at) WHERE aggregation_key IS NOT NULL;
CREATE INDEX idx_deliveries_status ON notification_deliveries(status, attempted_at);
CREATE INDEX idx_devices_user_active ON user_devices(user_id) WHERE is_active = true;
```

## 3. Smart Aggregation & Rate Limiting

### Database-Based Aggregation (Reliable)
```python
class NotificationAggregator:
    def __init__(self, db_pool):
        self.db = db_pool
        self.aggregation_window = 600  # 10 minutes
        
    def process_event(self, user_id, event_type, context):
        """Process incoming event with smart aggregation"""
        
        # Check rate limits first
        if not self.check_rate_limit(user_id, event_type):
            self.log_rate_limited(user_id, event_type)
            return None
            
        # Generate aggregation key for similar notifications
        agg_key = self.generate_aggregation_key(event_type, context)
        
        # Try to find existing notification to aggregate with
        existing_id = self.find_aggregatable_notification(user_id, agg_key)
        
        if existing_id:
            return self.update_aggregated_notification(existing_id, context)
        else:
            return self.create_new_notification(user_id, event_type, context, agg_key)
    
    def find_aggregatable_notification(self, user_id, agg_key):
        """Find recent notification that can be aggregated"""
        if not agg_key:
            return None
            
        cutoff_time = datetime.utcnow() - timedelta(seconds=self.aggregation_window)
        
        result = self.db.fetchone("""
            SELECT id FROM notifications 
            WHERE user_id = %s 
            AND aggregation_key = %s 
            AND created_at > %s 
            AND scheduled_at > NOW()  -- Not yet sent
            ORDER BY created_at DESC 
            LIMIT 1
        """, (user_id, agg_key, cutoff_time))
        
        return result['id'] if result else None
    
    def update_aggregated_notification(self, notification_id, new_context):
        """Update existing notification with new data"""
        
        # Get current notification
        current = self.db.fetchone("""
            SELECT content FROM notifications WHERE id = %s
        """, (notification_id,))
        
        current_content = current['content']
        
        # Merge contexts
        updated_content = self.merge_notification_content(current_content, new_context)
        
        # Update notification
        self.db.execute("""
            UPDATE notifications 
            SET content = %s, scheduled_at = %s
            WHERE id = %s
        """, (json.dumps(updated_content), datetime.utcnow() + timedelta(seconds=30), notification_id))
        
        return notification_id
    
    def generate_aggregation_key(self, event_type, context):
        """Generate key for grouping similar notifications"""
        
        if event_type == 'post_like':
            return f"post_like:{context['post_id']}"
        elif event_type == 'post_comment':
            return f"post_comment:{context['post_id']}"
        elif event_type == 'user_follow':
            return None  # Don't aggregate follows
        elif event_type == 'friend_request':
            return None  # Don't aggregate friend requests
        else:
            return None

class RateLimiter:
    def __init__(self, db_pool):
        self.db = db_pool
        self.limits = {
            'push': {'daily': 50, 'hourly': 10},
            'email': {'daily': 1, 'hourly': 1},
            'sms': {'daily': 3, 'hourly': 2}
        }
    
    def check_rate_limit(self, user_id, channel):
        """Check if user has exceeded rate limits"""
        today = date.today()
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        # Get current counts
        daily_count = self.db.fetchone("""
            SELECT COALESCE(SUM(CASE WHEN channel = %s THEN 1 ELSE 0 END), 0) as count
            FROM notification_deliveries nd
            JOIN notifications n ON nd.notification_id = n.id
            WHERE n.user_id = %s AND DATE(nd.attempted_at) = %s
        """, (channel, user_id, today))['count']
        
        hourly_count = self.db.fetchone("""
            SELECT COALESCE(COUNT(*), 0) as count
            FROM notification_deliveries nd
            JOIN notifications n ON nd.notification_id = n.id
            WHERE n.user_id = %s AND nd.channel = %s AND nd.attempted_at > %s
        """, (user_id, channel, hour_ago))['count']
        
        limits = self.limits.get(channel, {'daily': 100, 'hourly': 20})
        
        return (daily_count < limits['daily'] and hourly_count < limits['hourly'])
```

## 4. Delivery Channels (Production Implementation)

### 4.1 Push Notifications with FCM Rate Limiting
```python
class PushDeliveryService:
    def __init__(self):
        self.fcm = FCMClient()
        self.rate_limiter = TokenBucket(rate=2000, capacity=2000)  # FCM limit: 2,500 QPS
        self.batch_size = 500
        self.retry_delays = [60, 300, 1800, 7200]  # Exponential backoff
        
    def deliver_batch(self, notifications):
        """Deliver batch of push notifications with rate limiting"""
        
        # Group by device tokens
        device_batches = self.group_by_devices(notifications)
        
        results = []
        for batch in device_batches:
            if not self.rate_limiter.consume(len(batch['tokens'])):
                # Rate limited - schedule for later
                self.schedule_retry(batch['notifications'], delay=60)
                continue
                
            try:
                response = self.send_fcm_batch(batch)
                self.process_fcm_response(batch, response)
                results.extend(response.responses)
                
            except Exception as e:
                self.handle_batch_failure(batch, e)
                
        return results
    
    def send_fcm_batch(self, batch):
        """Send batch to FCM with proper error handling"""
        
        messages = []
        for notification in batch['notifications']:
            message = Message(
                token=notification['device_token'],
                notification=Notification(
                    title=notification['title'],
                    body=notification['body']
                ),
                data=notification.get('data', {}),
                android=AndroidConfig(
                    priority='high',
                    ttl=timedelta(hours=24)
                ),
                apns=APNSConfig(
                    payload=APNSPayload(
                        aps=Aps(
                            badge=notification.get('badge_count'),
                            sound='default'
                        )
                    )
                )
            )
            messages.append(message)
            
        return self.fcm.send_all(messages)
    
    def process_fcm_response(self, batch, response):
        """Process FCM response and update delivery status"""
        
        for idx, (notification, result) in enumerate(zip(batch['notifications'], response.responses)):
            if result.success:
                self.update_delivery_status(
                    notification['id'], 'push', 'sent', 
                    provider_id=result.message_id
                )
            else:
                error_code = result.exception.code if result.exception else 'unknown'
                
                if error_code in ['NOT_FOUND', 'INVALID_ARGUMENT']:
                    # Invalid token - mark device as inactive
                    self.deactivate_device_token(notification['device_token'])
                    self.update_delivery_status(
                        notification['id'], 'push', 'failed',
                        error_message=f'Invalid token: {error_code}'
                    )
                elif error_code == 'QUOTA_EXCEEDED':
                    # Rate limited - retry later
                    self.schedule_retry([notification], delay=300)
                else:
                    # Temporary error - retry
                    self.schedule_retry([notification], delay=60)

class TokenBucket:
    def __init__(self, rate, capacity):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = threading.Lock()
    
    def consume(self, tokens_needed):
        with self.lock:
            now = time.time()
            # Add tokens based on elapsed time
            self.tokens = min(
                self.capacity, 
                self.tokens + (now - self.last_update) * self.rate
            )
            self.last_update = now
            
            if self.tokens >= tokens_needed:
                self.tokens -= tokens_needed
                return True
            return False
```

### 4.2 Email Delivery with Proper Batching
```python
class EmailDeliveryService:
    def __init__(self):
        self.sendgrid = SendGridAPIClient()
        self.batch_size = 1000  # SendGrid limit
        self.template