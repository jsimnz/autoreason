# Notification System Design for 10M MAU Social App

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we prioritize a simplified but robust architecture that can handle realistic social app notification volumes while avoiding complex features that would overwhelm the small team. We use managed services to minimize operational overhead while maintaining reliability and user experience.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator for all notifications
- **Channel Handlers**: Dedicated processors for push, email, in-app, and SMS
- **User Preference Service**: Manages notification settings and delivery rules
- **Template Service**: Handles notification content and localization
- **Token Management Service**: Handles device token lifecycle
- **Analytics Service**: Tracks delivery metrics and user engagement

### Technology Stack
- **Message Queue**: Amazon SQS Standard (separate queues by priority)
- **Database**: PostgreSQL for core data, Redis for caching and real-time queues
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (after domain verification and reputation building)
- **SMS**: Twilio with strict cost controls
- **Infrastructure**: AWS with managed auto-scaling

**Rationale**: Managed services reduce operational complexity, allowing the small team to focus on business logic rather than infrastructure management.

## 2. Realistic Capacity Planning

### Volume Estimates
- **Daily Active Users**: ~3M (30% of 10M MAU)
- **Notifications per DAU**: 8-12 daily average for social apps
- **Total Daily Volume**: 24M-36M notifications
- **Peak Hour Volume**: 4M-6M notifications (6x average during evening hours)
- **Peak Minute Volume**: 70K-100K notifications

### Infrastructure Sizing
```python
# Realistic capacity calculations
PEAK_NOTIFICATIONS_PER_MINUTE = 100_000
NOTIFICATIONS_PER_WORKER_PER_SECOND = 50  # Conservative estimate
REQUIRED_WORKERS = (PEAK_NOTIFICATIONS_PER_MINUTE / 60) / NOTIFICATIONS_PER_WORKER_PER_SECOND
# = 100,000/60/50 = ~35 workers minimum

# Add 50% buffer for spikes and maintenance
TOTAL_WORKERS_NEEDED = 50
```

## 3. Delivery Channels

### 3.1 Push Notifications
```json
{
  "channel": "push",
  "payload": {
    "title": "New message from John",
    "body": "Hey, are you free tonight?",
    "data": {
      "type": "message",
      "conversation_id": "12345",
      "sender_id": "67890"
    },
    "badge_count": 3
  }
}
```

**Implementation**: 
- FCM for Android, APNs for iOS
- Device token management with automatic cleanup of invalid tokens
- Rich notifications with images/actions for engagement

### 3.2 Email with Rate Limiting
```python
class EmailService:
    def __init__(self):
        self.ses_client = boto3.client('ses')
        self.daily_quota = 200  # Start with SES sandbox limit
        self.rate_limit = 1     # 1 email per second initially
        
    def check_sending_limits(self):
        """Check current SES quotas and adjust"""
        response = self.ses_client.get_send_quota()
        
        self.daily_quota = response['Max24HourSend']
        self.rate_limit = response['MaxSendRate']
        
        # Cache limits for 1 hour
        redis.setex('ses_limits', 3600, json.dumps({
            'daily_quota': self.daily_quota,
            'rate_limit': self.rate_limit,
            'sent_today': response['SentLast24Hours']
        }))
```

**Email Authentication Setup**:
- Amazon SES with bounce/complaint handling
- SPF, DKIM, and DMARC records for deliverability
- HTML templates with fallback text versions
- Unsubscribe links with one-click compliance

### 3.3 In-App Notifications (Polling-Based)

**Simplified Polling Approach**:
```python
# Simple polling endpoint - no WebSockets for initial version
@app.route('/api/notifications/poll')
def poll_notifications():
    user_id = get_current_user_id()
    since = request.args.get('since', 0)
    
    # Get from Redis sorted set (timestamp-based)
    notifications = redis.zrangebyscore(
        f"user_notifications:{user_id}",
        since,
        "+inf",
        withscores=True,
        start=0,
        num=50  # Limit to prevent large responses
    )
    
    return {
        'notifications': notifications,
        'poll_interval': 30,  # 30 seconds
        'has_more': len(notifications) == 50
    }

# Store in Redis with automatic expiration
class InAppNotificationStore:
    def add_notification(self, user_id, notification):
        key = f"user_notifications:{user_id}"
        score = notification['timestamp']
        
        # Add to sorted set
        redis.zadd(key, {json.dumps(notification): score})
        
        # Keep only last 100 notifications per user
        redis.zremrangebyrank(key, 0, -101)
        
        # Expire after 7 days
        redis.expire(key, 604800)
```

**Rationale**: Polling is simpler, more reliable, and easier to debug than WebSockets. 30-second intervals provide acceptable user experience while avoiding thundering herd problems. Can upgrade to WebSocket later.

### 3.4 SMS with Cost Controls
```python
class SMSService:
    def __init__(self):
        self.twilio_client = Client(account_sid, auth_token)
        self.monthly_budget = 1000  # $1000 monthly SMS budget
        self.user_daily_limit = 5   # Max 5 SMS per user per day
        
    def can_send_sms(self, user_id, phone_number):
        """Check if SMS can be sent within budget and limits"""
        
        # Check monthly budget
        month_key = f"sms_budget:{datetime.now().strftime('%Y-%m')}"
        monthly_spent = float(redis.get(month_key) or 0)
        
        if monthly_spent >= self.monthly_budget:
            return False, "Monthly budget exceeded"
        
        # Check user daily limit
        user_key = f"sms_user_daily:{user_id}:{datetime.now().strftime('%Y-%m-%d')}"
        user_daily_count = int(redis.get(user_key) or 0)
        
        if user_daily_count >= self.user_daily_limit:
            return False, "Daily limit exceeded"
        
        return True, "OK"
```

## 4. Priority and Batching Logic

### Priority-Based Queue System
```python
class Priority(Enum):
    CRITICAL = 1    # Security alerts, account issues
    HIGH = 2        # Direct messages, mentions
    MEDIUM = 3      # Likes, comments, friend requests  
    LOW = 4         # Weekly digests, recommendations

# Separate SQS queues by priority - no complex batching
QUEUE_CONFIG = {
    'critical': {
        'queue_name': 'notifications-critical',
        'workers': 10,
        'batch_size': 1,  # Process immediately
        'visibility_timeout': 30
    },
    'high': {
        'queue_name': 'notifications-high', 
        'workers': 20,
        'batch_size': 10,
        'visibility_timeout': 60
    },
    'medium': {
        'queue_name': 'notifications-medium',
        'workers': 15,
        'batch_size': 50,
        'visibility_timeout': 120
    },
    'low': {
        'queue_name': 'notifications-low',
        'workers': 5,
        'batch_size': 100,
        'visibility_timeout': 300
    }
}

class NotificationProcessor:
    def process_batch(self, messages):
        """Process batch of messages with proper error handling"""
        successful = []
        failed = []
        
        # Load all user preferences in bulk
        user_ids = [msg['user_id'] for msg in messages]
        preferences = self.preference_service.load_preferences_bulk(user_ids)
        
        for message in messages:
            try:
                if self.should_deliver(message, preferences):
                    self.deliver_notification(message)
                    successful.append(message)
            except Exception as e:
                logger.error(f"Failed to process notification {message['id']}: {e}")
                failed.append(message)
        
        return len(successful), len(failed)
```

**Tradeoff**: Separate queues by priority eliminate complex batching logic and ordering issues, while still allowing batch processing for efficiency.

## 5. User Preference Management

### Flattened Preference Schema
```sql
-- Main preferences table for better performance
CREATE TABLE notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Category-specific preferences
CREATE TABLE category_preferences (
    user_id BIGINT,
    category VARCHAR(50), -- 'messages', 'social', 'system'
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT false,
    sms_enabled BOOLEAN DEFAULT false,
    PRIMARY KEY (user_id, category)
);

CREATE INDEX idx_preferences_push ON notification_preferences(user_id) 
WHERE push_enabled = true;
```

### Bulk Preference Loading
```python
class PreferenceService:
    def load_preferences_bulk(self, user_ids):
        """Load preferences for multiple users in single query"""
        # Use Redis pipeline for bulk operations
        pipe = redis.pipeline()
        
        for user_id in user_ids:
            cache_key = f"prefs:{user_id}"
            pipe.get(cache_key)
            
        cached_results = pipe.execute()
        
        # Find cache misses
        missing_users = []
        preferences = {}
        
        for i, result in enumerate(cached_results):
            user_id = user_ids[i]
            if result:
                preferences[user_id] = json.loads(result)
            else:
                missing_users.append(user_id)
        
        # Bulk load missing preferences from database
        if missing_users:
            db_prefs = self.db.get_preferences_bulk(missing_users)
            
            # Cache the results
            pipe = redis.pipeline()
            for user_id, prefs in db_prefs.items():
                cache_key = f"prefs:{user_id}"
                pipe.setex(cache_key, 3600, json.dumps(prefs))
                preferences[user_id] = prefs
            pipe.execute()
            
        return preferences

    def should_deliver(self, user_id, notification_type, channel):
        prefs = self.get_user_preferences(user_id)
        
        # Check channel enabled
        if not prefs[f'{channel}_enabled']:
            return False
            
        # Check category preferences
        category = self.get_notification_category(notification_type)
        category_prefs = self.get_category_preferences(user_id, category)
        if not category_prefs.get(f'{channel}_enabled', True):
            return False
            
        # Check quiet hours for push notifications
        if channel == 'push' and self.is_quiet_hours(prefs):
            return False
            
        return True
```

### Default Settings Strategy
- **Opt-in for SMS**: High cost, potential spam concerns
- **Opt-out for push/email**: Better engagement, user can disable
- **Always enabled for critical**: Security notifications override preferences

## 6. Push Token Management System

### Token Storage and Management
```sql
CREATE TABLE device_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    token VARCHAR(255) NOT NULL,
    platform VARCHAR(10) NOT NULL, -- 'ios', 'android'
    app_version VARCHAR(20),
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(token, platform)
);

CREATE INDEX idx_device_tokens_user_active ON device_tokens(user_id) 
WHERE is_active = true;
```

### Token Cleanup Strategy
```python
class TokenManager:
    def handle_invalid_tokens(self, failed_tokens):
        """Mark tokens as inactive when push fails"""
        if not failed_tokens:
            return
            
        # Bulk update invalid tokens
        self.db.execute("""
            UPDATE device_tokens 
            SET is_active = false, 
                updated_at = NOW()
            WHERE token = ANY(%s)
        """, [failed_tokens])
        
        # Remove from cache
        pipe = redis.pipeline()
        for token in failed_tokens:
            pipe.delete(f"token:{token}")
        pipe.execute()
    
    def get_user_tokens(self, user_id):
        """Get all active tokens for a user"""
        cache_key = f"user_tokens:{user_id}"
        cached = redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
            
        tokens = self.db.query("""
            SELECT token, platform FROM device_tokens 
            WHERE user_id = %s AND is_active = true
            AND last_used_at > NOW() - INTERVAL '90 days'
        """, [user_id])
        
        redis.setex(cache_key, 1800, json.dumps(tokens))  # 30 min cache
        return tokens
```

## 7. Failure Handling & Reliability

### Retry Strategy with Circuit Breaker
```python
class RetryPolicy:
    def __init__(self):
        self.max_attempts = 3
        self.backoff_multiplier = 2
        self.initial_delay = 1  # second
        
    def should_retry(self, attempt, error):
        if attempt >= self.max_attempts:
            return False
            
        # Don't retry client errors
        if isinstance(error, ClientError):
            return False
            
        return True
        
    def get_delay(self, attempt):
        return self.initial_delay * (self.backoff_multiplier ** attempt)

class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        
    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpenError()
                
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
```

### Dead Letter Queue Handling
- Failed notifications after 3 attempts go to DLQ
- Daily DLQ processing job for manual investigation
- Alerts for DLQ depth > 1000 messages

## 8. Implementation Timeline (6 months)

### Month 1-2: Core Infrastructure
- Set up SQS queues and basic notification service
- Implement flattened user preference storage and management
- Basic push notification delivery with token management (FCM/APNs)

### Month 3-4: Multi-Channel Support
- Email delivery with SES integration and rate limiting
- In-app notifications with polling approach
- SMS delivery with Twilio and cost controls
- Template management system

### Month 5: Advanced Features
-