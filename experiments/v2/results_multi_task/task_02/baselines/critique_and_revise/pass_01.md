## Critical Review of Original Proposal

### Major Problems Identified:

1. **Unrealistic Scale Assumptions**: 10M MAU with 5% engagement = 500K daily notifications, not the calculated 50K/minute peak
2. **Inadequate Database Design**: Single PostgreSQL instance won't handle 10M users; JSONB preferences lack proper indexing strategy
3. **Missing Critical Components**: No rate limiting, delivery status tracking, or proper user segmentation
4. **Oversimplified Batching**: No deduplication logic, merge strategies, or intelligent grouping
5. **Insufficient Monitoring**: Missing business metrics and user experience tracking
6. **Security Gaps**: No authentication, authorization, or data protection measures
7. **Cost Analysis Missing**: No consideration of actual operational costs at scale
8. **Template Management Underspecified**: No versioning, A/B testing, or localization strategy

---

# Notification System Design for 10M MAU Social App

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users (2M daily active users) across multiple delivery channels. The system handles 2.5M notifications daily with 15K/minute peak loads. Given the 4-engineer, 6-month constraint, we use a phased approach prioritizing reliability and core functionality while building foundations for advanced features.

## 1. System Architecture Overview

### Core Components
- **Notification Gateway**: API entry point with authentication and rate limiting
- **Notification Orchestrator**: Central routing and preference resolution
- **Channel Processors**: Specialized handlers for each delivery channel
- **Preference Engine**: Advanced user preference management with real-time updates
- **Template Engine**: Multi-language template management with A/B testing
- **Analytics Pipeline**: Real-time metrics and user engagement tracking
- **Delivery Tracker**: Status monitoring and retry coordination

### Technology Stack
- **Message Queue**: Amazon SQS with FIFO queues for ordering + DLQ
- **Database**: 
  - PostgreSQL cluster (read replicas) for preferences/templates/history
  - Redis cluster for caching and real-time data
  - DynamoDB for delivery tracking (high write volume)
- **Push**: Firebase Cloud Messaging + Apple Push Notification Service
- **Email**: Amazon SES with dedicated IP pools
- **SMS**: Twilio with fallback to AWS SNS
- **Infrastructure**: AWS with Kubernetes for auto-scaling

## 2. Scale Planning & Capacity

### Traffic Estimates
```
10M MAU → 2M DAU (20% conversion)
Average: 2.5M notifications/day = 29 notifications/second
Peak: 15K notifications/minute = 250 notifications/second
Channel distribution: Push 60%, Email 25%, In-app 10%, SMS 5%
```

### Infrastructure Sizing
- **Notification processors**: 8-12 instances (25 notif/sec each)
- **Database**: Primary + 2 read replicas
- **Redis**: 3-node cluster (high availability)
- **Queue capacity**: 100K message visibility timeout

## 3. Enhanced Database Design

### User Preferences (PostgreSQL)
```sql
-- Partitioned by user_id hash for horizontal scaling
CREATE TABLE notification_preferences (
    user_id BIGINT NOT NULL,
    channel VARCHAR(20) NOT NULL,
    category VARCHAR(50) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    settings JSONB DEFAULT '{}',
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, channel, category)
) PARTITION BY HASH (user_id);

-- Optimized indexes
CREATE INDEX idx_prefs_user_enabled ON notification_preferences (user_id) 
WHERE enabled = true;
CREATE INDEX idx_prefs_channel_category ON notification_preferences (channel, category);

-- Global user settings
CREATE TABLE user_notification_settings (
    user_id BIGINT PRIMARY KEY,
    global_enabled BOOLEAN DEFAULT true,
    frequency_cap INTEGER DEFAULT 50, -- max notifications per day
    last_notification_sent TIMESTAMP,
    notification_count_today INTEGER DEFAULT 0,
    reset_date DATE DEFAULT CURRENT_DATE,
    timezone VARCHAR(50) DEFAULT 'UTC'
);
```

### Delivery Tracking (DynamoDB)
```json
{
  "notification_id": "notif_12345_user_67890",
  "user_id": 67890,
  "channel": "push",
  "status": "delivered", // pending, delivered, failed, read
  "attempts": 1,
  "created_at": "2024-01-15T10:30:00Z",
  "delivered_at": "2024-01-15T10:30:02Z",
  "error_code": null,
  "metadata": {
    "device_token": "abc123",
    "template_id": "friend_request",
    "campaign_id": "social_2024_q1"
  },
  "ttl": 1736936400 // 30 days from creation
}
```

## 4. Advanced Channel Implementation

### 4.1 Push Notifications with Intelligence
```python
class PushProcessor:
    def __init__(self):
        self.fcm_client = FCMClient()
        self.apns_client = APNSClient()
        self.device_manager = DeviceTokenManager()
        
    async def send_notification(self, notification):
        user_devices = await self.device_manager.get_active_devices(
            notification.user_id
        )
        
        # Smart device selection
        target_device = self.select_optimal_device(user_devices, notification)
        
        # Adaptive payload based on device capabilities
        payload = self.build_adaptive_payload(notification, target_device)
        
        try:
            result = await self.deliver_to_device(target_device, payload)
            await self.track_delivery(notification.id, result)
            
            # Update device token validity
            if result.success:
                await self.device_manager.mark_successful(target_device.token)
            else:
                await self.handle_delivery_failure(target_device, result)
                
        except Exception as e:
            await self.handle_exception(notification, e)
    
    def select_optimal_device(self, devices, notification):
        # Prefer most recently active device
        # Consider device type (phone vs tablet) based on notification type
        # Factor in delivery success rate
        active_devices = [d for d in devices if d.last_seen > 
                         datetime.now() - timedelta(days=7)]
        
        if not active_devices:
            return devices[0] if devices else None
            
        return max(active_devices, key=lambda d: (
            d.last_seen.timestamp(),
            d.success_rate,
            1 if d.device_type == 'phone' else 0.5
        ))
```

### 4.2 Email with Deliverability Optimization
```python
class EmailProcessor:
    def __init__(self):
        self.ses_client = SESClient()
        self.reputation_manager = ReputationManager()
        self.template_engine = TemplateEngine()
        
    async def send_email(self, notification):
        # Check sender reputation and adjust sending rate
        reputation = await self.reputation_manager.get_reputation()
        if reputation.bounce_rate > 0.05:  # 5% threshold
            await self.throttle_sending(notification)
            
        # Personalized send time optimization
        optimal_time = await self.get_optimal_send_time(notification.user_id)
        if datetime.now() < optimal_time:
            await self.schedule_for_later(notification, optimal_time)
            return
            
        # Render template with user context
        rendered = await self.template_engine.render(
            template_id=notification.template_id,
            user_id=notification.user_id,
            variables=notification.variables
        )
        
        # Send with tracking
        result = await self.ses_client.send_email(
            to=notification.email,
            subject=rendered.subject,
            html_body=rendered.html,
            text_body=rendered.text,
            tracking_id=notification.id
        )
        
        await self.track_delivery(notification.id, result)
```

## 5. Intelligent Batching & Deduplication

### 5.1 Smart Batching Logic
```python
class IntelligentBatcher:
    def __init__(self):
        self.batch_windows = {
            Priority.CRITICAL: 0,      # No batching
            Priority.HIGH: 30,         # 30 seconds
            Priority.MEDIUM: 300,      # 5 minutes
            Priority.LOW: 1800         # 30 minutes
        }
        
    async def process_batch(self, notifications):
        # Group by user and apply deduplication
        user_batches = self.group_by_user(notifications)
        
        for user_id, user_notifications in user_batches.items():
            # Apply user-specific frequency capping
            capped_notifications = await self.apply_frequency_cap(
                user_id, user_notifications
            )
            
            # Merge similar notifications
            merged = self.merge_similar_notifications(capped_notifications)
            
            # Apply final delivery logic
            for notification in merged:
                await self.deliver_notification(notification)
    
    def merge_similar_notifications(self, notifications):
        """Merge similar notifications to reduce noise"""
        merged = {}
        
        for notif in notifications:
            merge_key = f"{notif.type}_{notif.source_id}"
            
            if merge_key not in merged:
                merged[merge_key] = notif
            else:
                # Merge logic based on notification type
                existing = merged[merge_key]
                if notif.type == 'likes':
                    existing.count += notif.count
                    existing.actors.extend(notif.actors)
                elif notif.type == 'comments':
                    existing.latest_comment = notif.content
                    existing.comment_count += 1
                    
        return list(merged.values())
```

### 5.2 Advanced Deduplication
```python
class DeduplicationEngine:
    def __init__(self):
        self.redis = RedisClient()
        
    async def should_send(self, notification):
        """Complex deduplication logic"""
        
        # Check for exact duplicates (24-hour window)
        duplicate_key = self.generate_duplicate_key(notification)
        if await self.redis.exists(duplicate_key):
            return False
            
        # Check for similar notifications (content-based)
        similar_key = self.generate_similarity_key(notification)
        similar_count = await self.redis.get(similar_key) or 0
        
        if int(similar_count) >= self.get_similarity_threshold(notification.type):
            return False
            
        # Mark as sent
        await self.redis.setex(duplicate_key, 86400, "1")  # 24 hours
        await self.redis.incr(similar_key)
        await self.redis.expire(similar_key, 3600)  # 1 hour window
        
        return True
    
    def generate_duplicate_key(self, notification):
        return f"dup:{notification.user_id}:{notification.type}:{hashlib.md5(notification.content.encode()).hexdigest()}"
    
    def generate_similarity_key(self, notification):
        return f"sim:{notification.user_id}:{notification.type}:{notification.source_id}"
```

## 6. User Preference Engine

### 6.1 Dynamic Preference Resolution
```python
class PreferenceEngine:
    def __init__(self):
        self.cache = RedisClient()
        self.db = PostgreSQLClient()
        self.ml_engine = MLPreferenceEngine()
        
    async def should_deliver(self, user_id, notification):
        """Multi-layered preference checking"""
        
        # Layer 1: Global user settings
        user_settings = await self.get_user_settings(user_id)
        if not user_settings.global_enabled:
            return False, "globally_disabled"
            
        # Layer 2: Frequency capping
        if await self.exceeds_frequency_cap(user_id, user_settings):
            return False, "frequency_capped"
            
        # Layer 3: Channel and category preferences
        prefs = await self.get_preferences(user_id, notification.channel, 
                                         notification.category)
        if not prefs.enabled:
            return False, "preference_disabled"
            
        # Layer 4: Quiet hours
        if await self.is_quiet_hours(user_id, notification.channel):
            return False, "quiet_hours"
            
        # Layer 5: ML-based user engagement prediction
        engagement_score = await self.ml_engine.predict_engagement(
            user_id, notification
        )
        if engagement_score < 0.1:  # Low engagement threshold
            return False, "low_engagement_predicted"
            
        return True, "allowed"
    
    async def get_optimal_channel(self, user_id, notification_type):
        """AI-driven channel selection"""
        user_history = await self.get_user_engagement_history(user_id)
        
        # Calculate engagement rates by channel for this user
        channel_scores = {}
        for channel in ['push', 'email', 'in_app']:
            channel_scores[channel] = self.calculate_channel_score(
                user_history, channel, notification_type
            )
            
        # Return channel with highest predicted engagement
        return max(channel_scores.items(), key=lambda x: x[1])[0]
```

### 6.2 Smart Defaults and Learning
```python
class SmartDefaults:
    def __init__(self):
        self.user_profiler = UserProfiler()
        
    async def initialize_user_preferences(self, user_id, signup_context):
        """Set intelligent defaults based on user behavior patterns"""
        
        profile = await self.user_profiler.analyze_signup_context(signup_context)
        
        # Base preferences on user type
        if profile.user_type == 'power_user':
            defaults = self.get_power_user_defaults()
        elif profile.user_type == 'casual':
            defaults = self.get_casual_user_defaults()
        else:
            defaults = self.get_standard_defaults()
            
        # Adjust for timezone and inferred schedule
        defaults = self.adjust_for_timezone(defaults, profile.timezone)
        
        await self.save_preferences(user_id, defaults)
        
    def get_power_user_defaults(self):
        return {
            'push': {'enabled': True, 'categories': ['all']},
            'email': {'enabled': True, 'frequency': 'immediate'},
            'in_app': {'enabled': True},
            'sms': {'enabled': False}  # Opt-in only
        }
```

## 7. Template Engine with A/B Testing

### 7.1 Advanced Template Management
```python
class TemplateEngine:
    def __init__(self):
        self.template_store = TemplateStore()
        self.ab_testing = ABTestingEngine()
        self.personalizer = PersonalizationEngine()
        
    async def render(self, template_id, user_id, variables):
        """Render personalized template with A/B testing"""
        
        # Get active template variant for user
        template_variant = await self.ab_testing.get_variant(
            template_id, user_id
        )
        
        # Load template with localization
        user_locale = await self.get_user_locale(user_id)
        template = await self.template_store.get_template(
            template_variant, user_locale
        )
        
        # Apply personalization
        personalized_variables = await self.personalizer.enhance_variables(
            user_id, variables
        )
        
        # Render with Jinja2
        rendered = template.render(**personalized_variables)
        
        # Track which variant was shown
        await self.ab_testing.track_impression(
            template_variant, user_id
        )
        
        return rendered
```

### 7.2 Template Schema
```sql
CREATE TABLE notification_templates (
    template_id VARCHAR(100),
    variant VARCHAR(50) DEFAULT 'control',
    locale VARCHAR(10) DEFAULT 'en',