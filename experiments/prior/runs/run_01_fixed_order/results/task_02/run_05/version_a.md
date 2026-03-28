# Notification System Design for 10M MAU Social App

## Executive Summary

This proposal outlines a scalable notification system supporting 10 million monthly active users with a 4-engineer team over 6 months. The design prioritizes reliability, user experience, and operational simplicity while making strategic tradeoffs to meet resource constraints.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator for all notifications
- **Channel Handlers**: Dedicated processors for each delivery channel
- **User Preference Service**: Manages user notification settings
- **Queue System**: Handles batching and priority routing
- **Analytics Service**: Tracks delivery metrics and user engagement

### Technology Stack Decisions

**Message Queue**: Amazon SQS + DLQ
- *Rationale*: Managed service reduces operational overhead for small team
- *Tradeoff*: Higher per-message cost vs. self-managed Kafka, but eliminates infrastructure management

**Database**: PostgreSQL primary + Redis cache
- *Rationale*: Team likely familiar with PostgreSQL; Redis for high-frequency preference lookups
- *Tradeoff*: Single database vs. microservices approach for faster initial development

**Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- *Rationale*: Direct integration reduces complexity vs. third-party aggregators
- *Tradeoff*: Platform-specific handling vs. unified API for better control and cost

## 2. Delivery Channels Implementation

### Push Notifications (Primary Channel)
```yaml
Implementation:
  - FCM for Android
  - APNs for iOS
  - Device token management in PostgreSQL
  - Retry logic: 3 attempts with exponential backoff

Capacity Planning:
  - Peak: 50K notifications/minute
  - Daily volume: 2M push notifications
  - Token refresh handling: Daily batch job
```

### In-App Notifications
```yaml
Implementation:
  - WebSocket connections for real-time delivery
  - Fallback to REST API polling (30-second intervals)
  - Message persistence: 30 days in PostgreSQL

Technical Details:
  - Connection pooling: 10K concurrent WebSocket connections
  - Message format: JSON with read/unread status
  - Offline message queue per user (max 100 messages)
```

### Email Notifications
```yaml
Implementation:
  - Amazon SES for delivery
  - Template system using Handlebars
  - Bounce/complaint handling via SES webhooks

Constraints:
  - Daily digest only (not real-time)
  - Maximum 1 email per user per day
  - Unsubscribe handling with one-click compliance
```

### SMS (Limited Implementation)
```yaml
Implementation:
  - Amazon SNS for delivery
  - US/Canada only initially
  - Critical notifications only (security alerts, password resets)

Rationale:
  - High cost limits usage to essential notifications
  - Regulatory compliance complexity deferred
```

## 3. Priority and Batching Logic

### Priority Levels
```yaml
CRITICAL (0-30 seconds):
  - Security alerts
  - Account lockouts
  - Payment failures
  - Direct messages from verified accounts

HIGH (0-5 minutes):
  - Direct messages
  - Mentions
  - Live event notifications
  - Friend requests

MEDIUM (5-60 minutes):
  - Likes on posts
  - Comments on posts
  - New followers
  - Group invitations

LOW (1-24 hours):
  - Trending content suggestions
  - Weekly digest
  - Feature announcements
```

### Batching Strategy
```python
# Pseudo-code for batching logic
class NotificationBatcher:
    def batch_notifications(self, notifications):
        batches = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': []
        }
        
        for notification in notifications:
            priority = self.determine_priority(notification)
            batches[priority].append(notification)
            
            # Batch size limits
            if len(batches[priority]) >= self.get_batch_size(priority):
                self.process_batch(batches[priority], priority)
                batches[priority] = []
    
    def get_batch_size(self, priority):
        return {
            'critical': 1,      # Immediate processing
            'high': 100,        # Small batches for speed
            'medium': 1000,     # Larger batches for efficiency
            'low': 5000         # Maximum efficiency
        }[priority]
```

## 4. User Preference Management

### Preference Categories
```yaml
Channel Preferences:
  - Push: enabled/disabled per notification type
  - Email: daily digest on/off
  - In-app: always enabled (non-configurable)
  - SMS: opt-in only for critical

Timing Preferences:
  - Quiet hours: 10 PM - 8 AM local time
  - Weekend notifications: enabled/disabled
  - Frequency caps: max 10 push notifications per day

Content Preferences:
  - Social interactions: likes, comments, follows
  - Content discovery: trending, recommendations
  - System notifications: security, updates
```

### Implementation
```sql
-- User preferences table schema
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_digest_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    max_daily_push INTEGER DEFAULT 10,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Notification type preferences
CREATE TABLE notification_type_preferences (
    user_id BIGINT,
    notification_type VARCHAR(50),
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    PRIMARY KEY (user_id, notification_type)
);
```

### Preference Processing Logic
```python
class PreferenceManager:
    def should_send_notification(self, user_id, notification_type, channel):
        # Check global preferences
        user_prefs = self.get_user_preferences(user_id)
        if not user_prefs.is_channel_enabled(channel):
            return False
            
        # Check quiet hours
        if self.is_quiet_hours(user_prefs.timezone):
            return notification_type == 'CRITICAL'
            
        # Check daily limits
        if self.daily_limit_reached(user_id, channel):
            return notification_type in ['CRITICAL', 'HIGH']
            
        # Check type-specific preferences
        return user_prefs.is_type_enabled(notification_type, channel)
```

## 5. Infrastructure Choices

### Deployment Architecture
```yaml
Production Environment:
  - AWS ECS Fargate for container orchestration
  - Application Load Balancer with health checks
  - RDS PostgreSQL Multi-AZ (db.r5.xlarge)
  - ElastiCache Redis cluster (cache.r5.large)
  - CloudWatch for monitoring and alerting

Development/Staging:
  - Smaller instance sizes (50% of production capacity)
  - Single AZ deployment for cost optimization
  - Shared Redis instance
```

### Scaling Strategy
```yaml
Horizontal Scaling:
  - Auto-scaling groups: 2-10 ECS tasks
  - Scale triggers: CPU > 70% or SQS queue depth > 1000
  - Database read replicas for preference lookups

Vertical Scaling:
  - Database: Start with db.r5.large, scale to db.r5.xlarge
  - Cache: Start with cache.r5.medium, scale to cache.r5.large
```

### Cost Optimization
```yaml
Monthly Infrastructure Costs (estimated):
  - ECS Fargate: $400-800
  - RDS PostgreSQL: $300-600
  - ElastiCache: $150-300
  - SQS: $50-100
  - SES: $10-50
  - Total: $910-1,850/month

Cost Controls:
  - Reserved instances for predictable workloads
  - Spot instances for batch processing
  - Automated resource scheduling (dev environments)
```

## 6. Failure Handling and Reliability

### Retry Mechanisms
```yaml
Push Notifications:
  - Retry attempts: 3
  - Backoff: exponential (1s, 4s, 16s)
  - Dead letter queue after final failure
  - Device token cleanup for invalid tokens

Email Notifications:
  - SES handles retries automatically
  - Bounce handling: disable email for hard bounces
  - Complaint handling: immediate unsubscribe

In-App Notifications:
  - WebSocket reconnection: automatic with exponential backoff
  - Message persistence: 30 days for offline users
  - Fallback to REST polling if WebSocket fails
```

### Circuit Breaker Implementation
```python
class NotificationCircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpenException()
        
        try:
            result = func(*args, **kwargs)
            self.reset()
            return result
        except Exception as e:
            self.record_failure()
            raise e
```

### Monitoring and Alerting
```yaml
Key Metrics:
  - Notification delivery rate by channel
  - Processing latency by priority level
  - Queue depth and processing rate
  - Error rates by notification type
  - User engagement rates

Alert Thresholds:
  - Delivery rate < 95%: Warning
  - Delivery rate < 90%: Critical
  - Queue depth > 10,000: Warning
  - Processing latency > 5 minutes: Critical
  - Error rate > 5%: Warning
```

## 7. Implementation Roadmap

### Phase 1 (Months 1-2): Core Infrastructure
- [ ] Basic notification service with PostgreSQL
- [ ] Push notification implementation (FCM/APNs)
- [ ] In-app notification system
- [ ] Basic user preference management
- [ ] SQS queue implementation

### Phase 2 (Months 3-4): Enhanced Features
- [ ] Email notification system
- [ ] Priority and batching logic
- [ ] Advanced user preferences
- [ ] Basic analytics and monitoring
- [ ] Retry mechanisms and error handling

### Phase 3 (Months 5-6): Production Readiness
- [ ] SMS notification implementation
- [ ] Circuit breaker patterns
- [ ] Comprehensive monitoring and alerting
- [ ] Performance optimization
- [ ] Load testing and capacity planning
- [ ] Documentation and runbooks

## 8. Key Tradeoffs and Rationale

### Managed Services vs. Self-Hosted
**Decision**: Use managed services (SQS, SES, RDS)
**Rationale**: 4-engineer team cannot maintain custom infrastructure
**Tradeoff**: Higher operational costs vs. reduced complexity

### Single Database vs. Microservices
**Decision**: Single PostgreSQL database with service separation
**Rationale**: Faster development with familiar technology
**Tradeoff**: Potential scaling bottleneck vs. development velocity

### Real-time vs. Near Real-time
**Decision**: Near real-time for most notifications (5-minute batches)
**Rationale**: Balances user experience with system efficiency
**Tradeoff**: Slight delay vs. resource optimization

### Feature Scope
**Decision**: Limited SMS implementation, no advanced ML personalization
**Rationale**: Focus on core functionality with small team
**Tradeoff**: Reduced feature set vs. reliable core system

## 9. Success Metrics

### Technical Metrics
- 99.9% uptime for notification service
- 95% delivery rate across all channels
- <5 minute processing latency for high-priority notifications
- <1% error rate for notification processing

### Business Metrics
- 40% push notification opt-in rate
- 15% email open rate for digests
- 25% click-through rate for actionable notifications
- <2% unsubscribe rate monthly

This design provides a solid foundation for a notification system that can scale to 10M MAU while being implementable by a 4-engineer team in 6 months. The focus on managed services and proven technologies ensures reliability while the modular design allows for future enhancements as the team and requirements grow.