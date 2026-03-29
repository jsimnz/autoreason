# Notification System Design for 10M MAU Social App (REVISED)

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a simplified but robust architecture that can handle realistic social app notification volumes while avoiding complex features that would overwhelm the small team.

## 1. System Architecture Overview

### Core Components
- **Notification API**: Handles notification creation and preference management
- **Queue Processors**: Priority-based workers for different notification types
- **Channel Handlers**: Dedicated processors for push, email, in-app, and SMS
- **Preference Cache Layer**: Redis-based caching with PostgreSQL persistence
- **Token Management Service**: Handles device token lifecycle

### Technology Stack
- **Message Queue**: Amazon SQS Standard (separate queues by priority)
- **Database**: PostgreSQL for core data, Redis for caching and real-time queues
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (after domain verification and reputation building)
- **SMS**: Twilio with strict cost controls
- **Infrastructure**: AWS with managed auto-scaling

## 2. Realistic Capacity Planning

**Problem Fixed**: Addresses fundamental scaling math errors

### Actual Volume Estimates
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

## 3. Simplified In-App Notification Strategy

**Problem Fixed**: Eliminates WebSocket scalability issues and race conditions

### Polling-Based Approach
```python
# Simple polling endpoint - no WebSockets
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
```

### In-App Storage Strategy
```python
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

**Rationale**: Polling is simpler, more reliable, and easier to debug. 30-second intervals provide acceptable user experience while avoiding thundering herd problems.

## 4. Redesigned Preference System

**Problem Fixed**: Eliminates preference resolution performance bottlenecks

### Flattened Preference Schema
```sql
-- Separate table for each preference type for better performance
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

CREATE INDEX idx_preferences_push ON notification_preferences(user_id) 
WHERE push_enabled = true;

-- Category-specific preferences
CREATE TABLE category_preferences (
    user_id BIGINT,
    category VARCHAR(50), -- 'messages', 'social', 'system'
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT false,
    sms_enabled BOOLEAN DEFAULT false,
    PRIMARY KEY (user_id, category)
);
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
```

## 5. Push Token Management System

**Problem Fixed**: Implements proper push token lifecycle management

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
    
    def cleanup_old_tokens(self):
        """Daily job to remove old inactive tokens"""
        self.db.execute("""
            DELETE FROM device_tokens 
            WHERE is_active = false 
            AND updated_at < NOW() - INTERVAL '30 days'
        """)
    
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

## 6. Simplified Queue Architecture

**Problem Fixed**: Eliminates batching race conditions and ordering issues

### Priority-Based Queue System
```python
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
        
        # Delete successful messages from queue
        if successful:
            self.delete_messages_bulk(successful)
            
        # Failed messages automatically return to queue for retry
        return len(successful), len(failed)
```

## 7. Email Delivery with Rate Limiting

**Problem Fixed**: Addresses SES rate limits and reputation management

### Email Service Implementation
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
    
    def can_send_email(self):
        """Check if we can send more emails today"""
        limits = redis.get('ses_limits')
        if not limits:
            self.check_sending_limits()
            limits = redis.get('ses_limits')
            
        data = json.loads(limits)
        return data['sent_today'] < (data['daily_quota'] * 0.9)  # 90% safety margin
    
    def send_email_batch(self, emails):
        """Send emails with rate limiting"""
        if not self.can_send_email():
            raise Exception("Daily email quota exceeded")
        
        sent_count = 0
        rate_limit_key = 'email_rate_limit'
        
        for email in emails:
            # Rate limiting using Redis
            current_count = redis.get(rate_limit_key) or 0
            if int(current_count) >= self.rate_limit:
                time.sleep(1)  # Wait for next second
                redis.delete(rate_limit_key)
            
            try:
                self.ses_client.send_email(**email)
                redis.incr(rate_limit_key)
                redis.expire(rate_limit_key, 1)  # Reset every second
                sent_count += 1
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'Throttling':
                    time.sleep(1)
                    continue
                else:
                    raise
                    
        return sent_count
```

### Email Authentication Setup
```python
# Required DNS records for email reputation
EMAIL_DOMAIN_CONFIG = {
    'domain': 'notifications.yourapp.com',
    'required_records': [
        {
            'type': 'TXT',
            'name': '@',
            'value': 'v=spf1 include:amazonses.com ~all'
        },
        {
            'type': 'TXT', 
            'name': '_dmarc',
            'value': 'v=DMARC1; p=quarantine; rua=mailto:dmarc@yourapp.com'
        }
        # DKIM records generated by SES
    ]
}
```

## 8. SMS Cost Controls

**Problem Fixed**: Implements strict SMS cost and fraud controls

### SMS Service with Cost Management
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
            logger.warning("Monthly SMS budget exceeded")
            return False, "Monthly budget exceeded"
        
        # Check user daily limit
        user_key = f"sms_user_daily:{user_id}:{datetime.now().strftime('%Y-%m-%d')}"
        user_daily_count = int(redis.get(user_key) or 0)
        
        if user_daily_count >= self.user_daily_limit:
            logger.warning(f"User {user_id} exceeded daily SMS limit")
            return False, "Daily limit exceeded"
        
        # Check for suspicious patterns (same number multiple times)
        phone_key = f"sms_phone_hourly:{phone_number}:{datetime.now().strftime('%Y-%m-%d-%H')}"
        phone_hourly_count = int(redis.get(phone_key) or 0)
        
        if phone_hourly_count >= 3:  # Max 3 SMS per phone per hour
            logger.warning(f"Phone {phone_number} exceeded hourly limit")
            return False, "Phone hourly limit exceeded"
            
        return True, "OK"
    
    def send_sms(self, user_id, phone_number, message):
        """Send SMS with cost tracking"""
        can_send, reason = self.can_send_sms(user_id, phone_number)
        
        if not can_send:
            raise Exception(f"Cannot send SMS: {reason}")
        
        try:
            # Estimate cost based on destination
            estimated_cost = self.estimate_sms_cost(phone_number)
            
            message = self.twilio_client.messages.create(
                body=message,
                from_='+1234567890',  # Your Twilio number
                to=phone_number
            )
            
            # Track costs and limits
            self.track_sms_usage(user_id, phone_number, estimated_cost)
            
            return message.sid
            
        except