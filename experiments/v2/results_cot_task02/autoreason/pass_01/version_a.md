# Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a scalable notification system design for a social app with 10M monthly active users, deliverable by a 4-person backend team within 6 months. The system prioritizes user engagement while respecting preferences and ensuring reliable delivery across multiple channels.

**Key Design Principles:**
- Horizontal scalability to handle 10M+ users
- Channel-agnostic architecture for future extensibility
- User-centric preference management
- Graceful degradation under load
- Cost-effective infrastructure choices

---

## 1. System Architecture Overview

### Core Components
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Notification  │    │   Preference    │    │   Delivery      │
│   Gateway       │    │   Service       │    │   Workers       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Message       │    │   User          │    │   Channel       │
│   Queue         │    │   Preferences   │    │   Adapters      │
│   (Redis)       │    │   DB            │    │   (Push/Email)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Technology Stack Rationale
- **API Gateway**: Node.js/Express (team familiarity, fast development)
- **Message Queue**: Redis Streams (simpler than Kafka for this scale, built-in persistence)
- **Database**: PostgreSQL primary + Redis cache (ACID compliance + performance)
- **Worker Processes**: Node.js (consistency across stack)
- **Infrastructure**: AWS (managed services reduce operational overhead)

**Tradeoff**: Choosing Redis over Kafka sacrifices some advanced features but significantly reduces operational complexity for a 4-person team.

---

## 2. Delivery Channels Implementation

### 2.1 Push Notifications
**Primary Channel** - Highest engagement rates (~20-25%)

```javascript
// Push notification adapter
class PushAdapter {
  async send(notification) {
    const payload = {
      title: notification.title,
      body: notification.body,
      data: notification.metadata,
      badge: await this.getBadgeCount(notification.userId)
    };
    
    // Use FCM for Android, APNS for iOS
    return this.platformService.send(notification.deviceTokens, payload);
  }
}
```

**Implementation Details:**
- Firebase Cloud Messaging (FCM) for Android
- Apple Push Notification Service (APNS) for iOS
- Device token management with automatic cleanup of invalid tokens
- Rich notifications with images/actions for high-priority messages

### 2.2 Email Notifications
**Batch Channel** - Lower cost, higher information density

```javascript
// Email batching logic
class EmailBatcher {
  async processBatch(userId, notifications, timeWindow = '1hour') {
    const template = this.selectTemplate(notifications);
    const digestContent = this.createDigest(notifications);
    
    return {
      to: await this.getUserEmail(userId),
      template: template,
      content: digestContent,
      unsubscribeToken: this.generateToken(userId)
    };
  }
}
```

**Implementation Details:**
- SendGrid for delivery (99%+ deliverability, good analytics)
- Smart batching: Group similar notifications into digest emails
- Template system for different notification types
- One-click unsubscribe compliance

### 2.3 In-App Notifications
**Real-time Channel** - Immediate feedback, no external dependencies

```javascript
// WebSocket connection manager
class InAppNotifier {
  async sendRealTime(userId, notification) {
    const connections = this.connectionManager.getUserConnections(userId);
    const payload = {
      id: notification.id,
      type: notification.type,
      data: notification.data,
      timestamp: Date.now()
    };
    
    connections.forEach(conn => conn.send(JSON.stringify(payload)));
  }
}
```

**Implementation Details:**
- WebSocket connections with automatic reconnection
- Notification bell with unread count
- Persistent notification center with pagination
- Real-time updates using Socket.IO

### 2.4 SMS (Limited Use)
**Emergency Channel** - High cost, reserved for critical notifications

```javascript
// SMS adapter with cost controls
class SMSAdapter {
  async send(notification) {
    // Only for account security and critical alerts
    if (!this.isCriticalNotification(notification.type)) {
      throw new Error('SMS reserved for critical notifications');
    }
    
    return this.twilioClient.send({
      to: notification.phoneNumber,
      body: this.formatSMS(notification)
    });
  }
}
```

**Cost Control**: SMS limited to security alerts, password resets, and account verification only.

---

## 3. Priority and Batching Logic

### 3.1 Priority Classification

```javascript
const PRIORITY_LEVELS = {
  CRITICAL: 0,    // Security alerts, immediate delivery
  HIGH: 1,        // Direct messages, mentions, immediate delivery  
  MEDIUM: 2,      // Likes, comments, 15-minute batching
  LOW: 3          // Weekly digest, daily batching
};

class PriorityManager {
  classifyNotification(type, context) {
    const rules = {
      'security_alert': PRIORITY_LEVELS.CRITICAL,
      'direct_message': PRIORITY_LEVELS.HIGH,
      'post_mention': PRIORITY_LEVELS.HIGH,
      'post_like': PRIORITY_LEVELS.MEDIUM,
      'friend_request': PRIORITY_LEVELS.MEDIUM,
      'weekly_summary': PRIORITY_LEVELS.LOW
    };
    
    return rules[type] || PRIORITY_LEVELS.MEDIUM;
  }
}
```

### 3.2 Batching Strategy

**Time-based Batching Windows:**
- Critical: Immediate (< 30 seconds)
- High: Immediate for first, 5-minute window for subsequent
- Medium: 15-minute batching window
- Low: Daily/weekly digest

**Smart Batching Logic:**
```javascript
class NotificationBatcher {
  async shouldBatch(notification, existingBatch) {
    // Don't batch different types
    if (notification.type !== existingBatch.type) return false;
    
    // Don't batch if user is currently active
    if (await this.isUserActive(notification.userId)) return false;
    
    // Batch similar notifications from same source
    return notification.sourceId === existingBatch.sourceId;
  }
}
```

**Tradeoff**: Aggressive batching reduces notification fatigue but may delay some updates. We prioritize user experience over immediate delivery for non-critical notifications.

---

## 4. User Preference Management

### 4.1 Preference Schema

```sql
CREATE TABLE user_notification_preferences (
  user_id UUID PRIMARY KEY,
  channel_preferences JSONB NOT NULL DEFAULT '{}',
  quiet_hours JSONB,
  notification_types JSONB NOT NULL DEFAULT '{}',
  global_enabled BOOLEAN DEFAULT true,
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Example preference structure
{
  "channels": {
    "push": {"enabled": true, "quiet_hours": true},
    "email": {"enabled": true, "frequency": "daily"},
    "sms": {"enabled": false}
  },
  "types": {
    "direct_message": {"push": true, "email": false},
    "post_like": {"push": false, "email": true},
    "security_alert": {"push": true, "email": true, "sms": true}
  },
  "quiet_hours": {
    "enabled": true,
    "start": "22:00",
    "end": "08:00",
    "timezone": "America/New_York"
  }
}
```

### 4.2 Preference Engine

```javascript
class PreferenceEngine {
  async shouldSendNotification(userId, notification, channel) {
    const prefs = await this.getPreferences(userId);
    
    // Check global settings
    if (!prefs.global_enabled) return false;
    
    // Check channel-specific settings
    if (!prefs.channels[channel]?.enabled) return false;
    
    // Check notification type settings
    if (!prefs.types[notification.type]?.[channel]) return false;
    
    // Check quiet hours
    if (this.isQuietHours(prefs.quiet_hours)) {
      return notification.priority === PRIORITY_LEVELS.CRITICAL;
    }
    
    return true;
  }
}
```

### 4.3 Smart Defaults and Onboarding

```javascript
// Progressive preference disclosure
const ONBOARDING_FLOW = {
  step1: ['direct_message', 'security_alert'],  // Essential only
  step2: ['post_mention', 'friend_request'],    // Social features
  step3: ['post_like', 'weekly_summary']        // Engagement features
};

class OnboardingManager {
  async initializeUserPreferences(userId, step = 1) {
    const defaultPrefs = this.getStepDefaults(step);
    await this.savePreferences(userId, defaultPrefs);
  }
}
```

**User Experience Features:**
- Progressive disclosure during onboarding
- One-click "Notify me less" option
- Smart suggestions based on usage patterns
- Bulk preference management for power users

---

## 5. Infrastructure Design

### 5.1 AWS Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Application   │    │   Notification  │    │   Delivery      │
│   Load Balancer │────│   Gateway       │────│   Workers       │
│   (ALB)         │    │   (ECS)         │    │   (ECS)         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Redis         │    │   External      │
                       │   ElastiCache   │    │   Services      │
                       │   (Message      │    │   (FCM, APNS,   │
                       │   Queue)        │    │   SendGrid)     │
                       └─────────────────┘    └─────────────────┘
                                │
                       ┌─────────────────┐
                       │   RDS           │
                       │   PostgreSQL    │
                       │   (User Prefs   │
                       │   & Analytics)  │
                       └─────────────────┘
```

### 5.2 Scaling Strategy

**Horizontal Scaling:**
- Auto Scaling Groups for ECS services
- Redis Cluster mode for message queue partitioning
- Read replicas for PostgreSQL

**Capacity Planning:**
```javascript
// Peak load calculations for 10M MAU
const PEAK_CALCULATIONS = {
  dailyActiveUsers: 3000000,      // 30% of MAU
  avgNotificationsPerUser: 8,     // Conservative estimate
  peakHourMultiplier: 3,          // 3x average during peak
  
  peakNotificationsPerSecond: () => {
    return (3000000 * 8 * 3) / (24 * 3600); // ~833 notifications/second
  }
};
```

**Infrastructure Sizing:**
- Gateway: 4 ECS tasks (t3.medium) behind ALB
- Workers: 8 ECS tasks (t3.medium) with auto-scaling 4-16
- Redis: r6g.xlarge cluster (3 nodes)
- PostgreSQL: db.t3.large with 2 read replicas

### 5.3 Cost Optimization

**Monthly Cost Estimate:**
- ECS compute: ~$400/month
- Redis ElastiCache: ~$300/month  
- RDS PostgreSQL: ~$250/month
- Data transfer: ~$100/month
- External services (SendGrid, etc.): ~$200/month
- **Total: ~$1,250/month** ($0.125 per MAU)

**Cost Controls:**
- Aggressive email batching to reduce SendGrid costs
- SMS restricted to security alerts only
- Intelligent retry policies to minimize waste
- Resource auto-scaling based on demand

---

## 6. Failure Handling and Reliability

### 6.1 Failure Scenarios and Responses

```javascript
class FailureHandler {
  async handleDeliveryFailure(notification, channel, error) {
    switch (error.type) {
      case 'RATE_LIMIT':
        return this.scheduleRetry(notification, this.calculateBackoff(error));
        
      case 'INVALID_TOKEN':
        await this.cleanupDeviceToken(notification.deviceToken);
        return this.tryFallbackChannel(notification);
        
      case 'SERVICE_UNAVAILABLE':
        return this.queueForRetry(notification, '5m');
        
      case 'PERMANENT_FAILURE':
        return this.logAndDiscard(notification, error);
    }
  }
}
```

### 6.2 Retry Strategy

**Exponential Backoff with Jitter:**
```javascript
class RetryManager {
  calculateBackoff(attempt, baseDelay = 1000, maxDelay = 300000) {
    const exponential = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
    const jitter = exponential * 0.1 * Math.random();
    return exponential + jitter;
  }
  
  async scheduleRetry(notification, delay) {
    if (notification.retryCount >= this.getMaxRetries(notification.priority)) {
      return this.sendToDeadLetter(notification);
    }
    
    await this.redis.zadd(
      'retry_queue', 
      Date.now() + delay, 
      JSON.stringify(notification)
    );
  }
}
```

**Retry Limits by Priority:**
- Critical: 5 retries over 1 hour
- High: 3 retries over 30 minutes  
- Medium: 2 retries over 15 minutes
- Low: 1 retry after 5 minutes

### 6.3 Circuit Breaker Pattern

```javascript
class CircuitBreaker {
  constructor(threshold = 5, timeout = 60000) {
    this.failureThreshold = threshold;
    this.resetTimeout = timeout;
    this.state = 'CLOSED'; // CLOSED, OPEN, HALF_OPEN
    this.failureCount = 0;
  }
  
  async execute(operation) {
    if (this.state === 'OPEN') {
      if (Date.now() > this.nextAttempt) {
        this.state = 'HALF_OPEN';
      } else {
        throw new Error('Circuit breaker is OPEN');
      }
    }
    
    try {
      const result = await operation();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }
}
```

### 6.4 Monitoring and Alerting

**Key Metrics:**
```javascript
const MONITORING_METRICS = {
  delivery_rate: 'notifications_delivered / notifications_sent',
  latency_p95: '95th percentile delivery time',
  error_rate: 'failed_deliveries / total_attempts',
  queue_depth: 'pending notifications in queue',
  user_engagement: 'click_through_rate by channel'
};
```

**Alert Thresholds:**
- Delivery rate < 95% (5-minute window)
- P95 latency > 30 seconds
- Error rate > 5%
- Queue depth > 10,000 messages

---

## 7. Implementation Timeline (6 Months)

### Phase 1: Foundation (Months 1-2)
**Team Split: 2 engineers on core system, 2 on channels**

- Core notification gateway and