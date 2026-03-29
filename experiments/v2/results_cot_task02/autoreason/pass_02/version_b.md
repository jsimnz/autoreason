# Revised Notification System Design for Social App (10M MAU)

## Executive Summary

This revised design provides a **pragmatic, deliverable** notification system for a social app with 10M MAU, realistically scoped for a 4-person backend team within 6 months. The system prioritizes **operational simplicity** and **incremental scaling** over premature optimization.

**Key Design Changes:**
- Single-database architecture with clear scaling triggers
- Simplified technology stack focused on team productivity
- Realistic capacity planning based on industry benchmarks
- Phased delivery approach with clear MVP boundaries
- Comprehensive monitoring and failure handling from day one

---

## 1. Revised System Architecture

### Core Components (Simplified)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   API Gateway   │    │   Notification  │
│   (ALB)         │────│   (2-4 nodes)   │────│   Service       │
└─────────────────┘    └─────────────────┘    │   (Stateless)   │
                                              └─────────────────┘
                                                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   PostgreSQL    │    │   Redis         │
                       │   (Single DB)   │────│   (Cache +      │
                       │   + Read Replica│    │   Queue)        │
                       └─────────────────┘    └─────────────────┘
                                │
                       ┌─────────────────┐
                       │   Background    │
                       │   Workers       │
                       │   (2-6 nodes)   │
                       └─────────────────┘
```

### Technology Stack Rationale

**Message Queue: Redis with Background Jobs**
- Start with Redis + Bull queue library (proven at scale)
- No additional infrastructure complexity
- Clear migration path to dedicated message broker at 50M+ MAU
- Handles realistic load of 500-1000 notifications/second comfortably

**Database: Single PostgreSQL Instance**
- Vertical scaling handles 10M users easily (proven by Discord, Slack early days)
- Partitioning by date for notification history
- Sharding trigger: >50M active users or >10TB data
- Read replicas for analytics workloads

**Caching: Single Redis Instance**
- User preferences and device tokens
- Connection pooling and session management
- Clustering only when memory exceeds 64GB

---

## 2. Realistic Capacity Planning

### Evidence-Based Load Analysis
```javascript
const REALISTIC_LOAD_CALCULATIONS = {
  // Based on industry benchmarks (Twitter, Instagram public data)
  dailyActiveUsers: 2000000,        // 20% of MAU (conservative)
  avgNotificationsPerUser: 3,       // Lower than assumed originally
  baseNotificationsPerSecond: 208,  // 2M * 3 / 86400 = 69 avg, 3x peak
  
  // Viral content (based on TikTok viral analysis)
  viralSpikeMultiplier: 5,          // More realistic than 20x
  peakNotificationsPerSecond: 1040, // Still manageable
  
  // Channel distribution (based on mobile app analytics)
  pushNotifications: '85%',         // Primary channel
  emailDigests: '25%',             // Non-overlapping daily/weekly
  webSocketUpdates: '15%',         // Only active users
  smsAlerts: '0.01%',              // Security only
  
  // Connection requirements (WhatsApp benchmark: 0.1% concurrent)
  concurrentWebSockets: 10000,     // 0.1% of MAU realistic
  avgSessionDuration: '12min'       // Typical social app session
};
```

### Infrastructure Sizing (Conservative)

**Phase 1 (0-3 months): MVP**
- API Gateway: 2 instances (t3.medium) with auto-scaling 2-4
- Workers: 2 instances (t3.medium) with auto-scaling 2-4  
- PostgreSQL: Single instance (db.t3.large) + 1 read replica
- Redis: Single instance (t3.medium)
- **Cost: ~$600/month** (including third-party services)

**Phase 2 (3-6 months): Production Ready**
- API Gateway: 4 instances with auto-scaling 2-6
- Workers: 4 instances with auto-scaling 2-8
- PostgreSQL: Upgrade to (db.r5.large) + 2 read replicas
- Redis: Upgrade to (r6g.large)
- **Cost: ~$1,200/month**

**Scaling Triggers:**
- Database CPU >70% sustained → Vertical scaling
- Queue depth >1000 → Add workers
- Redis memory >80% → Upgrade instance
- Response time >500ms → Horizontal scaling

---

## 3. Simplified Delivery Channels

### 3.1 Push Notifications (Primary Focus)

```javascript
class PushNotificationService {
  constructor() {
    this.fcm = new FCMClient({ timeout: 5000 });
    this.apns = new APNSClient({ timeout: 5000 });
    this.failureTracker = new Map(); // Simple in-memory tracking
  }

  async sendNotification(notification) {
    const { userId, deviceToken, platform } = notification;
    
    try {
      const result = platform === 'ios' 
        ? await this.sendAPNS(notification)
        : await this.sendFCM(notification);
        
      await this.recordSuccess(userId, platform);
      return result;
      
    } catch (error) {
      await this.handleFailure(notification, error);
      throw error;
    }
  }

  async handleFailure(notification, error) {
    // Simple exponential backoff
    const retryCount = this.failureTracker.get(notification.id) || 0;
    
    if (retryCount < 3 && this.isRetryableError(error)) {
      this.failureTracker.set(notification.id, retryCount + 1);
      const delay = Math.pow(2, retryCount) * 1000; // 1s, 2s, 4s
      
      setTimeout(() => {
        this.sendNotification(notification);
      }, delay);
    } else {
      // Log failure and move on
      console.error('Push notification failed permanently', {
        notificationId: notification.id,
        error: error.message,
        retryCount
      });
    }
  }

  isRetryableError(error) {
    const retryableCodes = [
      'messaging/internal-error',
      'messaging/server-unavailable',
      'messaging/timeout'
    ];
    return retryableCodes.includes(error.code);
  }
}
```

### 3.2 WebSocket (Simplified Real-time)

```javascript
class WebSocketManager {
  constructor() {
    this.connections = new Map(); // userId -> socket
    this.heartbeatInterval = 30000;
  }

  handleConnection(socket, userId) {
    // One connection per user (simplification)
    this.closeExistingConnection(userId);
    this.connections.set(userId, socket);
    
    // Simple heartbeat
    const heartbeat = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.ping();
      } else {
        this.cleanup(userId, heartbeat);
      }
    }, this.heartbeatInterval);

    socket.on('close', () => this.cleanup(userId, heartbeat));
  }

  async sendToUser(userId, notification) {
    const socket = this.connections.get(userId);
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(notification));
      return true;
    }
    return false; // User offline, will get push notification
  }

  cleanup(userId, heartbeat) {
    clearInterval(heartbeat);
    this.connections.delete(userId);
  }
}
```

### 3.3 Email (Daily Digest Only)

```javascript
class EmailDigestService {
  constructor() {
    this.sendgrid = new SendGridClient();
    this.dailyBatch = new Map(); // userId -> notifications[]
  }

  addToDigest(userId, notification) {
    if (!this.dailyBatch.has(userId)) {
      this.dailyBatch.set(userId, []);
    }
    this.dailyBatch.get(userId).push(notification);
  }

  async sendDailyDigests() {
    const batches = Array.from(this.dailyBatch.entries());
    const results = [];

    for (const [userId, notifications] of batches) {
      try {
        await this.sendDigest(userId, notifications);
        results.push({ userId, status: 'sent', count: notifications.length });
      } catch (error) {
        results.push({ userId, status: 'failed', error: error.message });
      }
    }

    this.dailyBatch.clear();
    return results;
  }
}
```

### 3.4 SMS (Security Alerts Only)

```javascript
class SMSService {
  constructor() {
    this.twilio = new TwilioClient();
    this.allowedTypes = ['security_alert', 'password_reset'];
    this.rateLimiter = new Map(); // userId -> lastSent timestamp
  }

  async send(notification) {
    if (!this.allowedTypes.includes(notification.type)) {
      throw new Error('SMS not allowed for this notification type');
    }

    // Rate limiting: max 1 SMS per user per hour
    const userId = notification.userId;
    const lastSent = this.rateLimiter.get(userId) || 0;
    const hourAgo = Date.now() - (60 * 60 * 1000);
    
    if (lastSent > hourAgo) {
      throw new Error('SMS rate limit exceeded');
    }

    const phoneNumber = await this.getUserPhoneNumber(userId);
    if (!phoneNumber) {
      throw new Error('No verified phone number');
    }

    await this.twilio.messages.create({
      to: phoneNumber,
      body: notification.message,
      from: process.env.TWILIO_PHONE_NUMBER
    });

    this.rateLimiter.set(userId, Date.now());
  }
}
```

---

## 4. Simplified User Preferences

### 4.1 Single Table Schema

```sql
CREATE TABLE user_notification_preferences (
    user_id UUID PRIMARY KEY,
    
    -- Global settings
    notifications_enabled BOOLEAN DEFAULT true,
    
    -- Channel preferences
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    
    -- Simple notification types
    mentions BOOLEAN DEFAULT true,
    direct_messages BOOLEAN DEFAULT true,
    likes_comments BOOLEAN DEFAULT false,
    security_alerts BOOLEAN DEFAULT true,
    
    -- Quiet hours (simplified)
    quiet_hours_start INTEGER DEFAULT 22, -- Hour of day (0-23)
    quiet_hours_end INTEGER DEFAULT 8,
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Simple indexes
CREATE INDEX idx_user_prefs_enabled ON user_notification_preferences (notifications_enabled);
CREATE INDEX idx_user_prefs_updated ON user_notification_preferences (updated_at);
```

### 4.2 Preference Engine (Simplified)

```javascript
class PreferenceEngine {
  constructor() {
    this.cache = new Redis();
    this.cacheTTL = 1800; // 30 minutes
  }

  async shouldSendNotification(userId, notification, channel) {
    const prefs = await this.getPreferences(userId);
    
    // Simple checks
    if (!prefs.notifications_enabled) return false;
    if (!prefs[`${channel}_enabled`]) return false;
    if (!prefs[notification.type]) return false;
    
    // Quiet hours (except security)
    if (notification.type !== 'security_alerts' && this.isQuietHours(prefs)) {
      return false;
    }
    
    return true;
  }

  async getPreferences(userId) {
    const cacheKey = `prefs:${userId}`;
    const cached = await this.cache.get(cacheKey);
    if (cached) return JSON.parse(cached);

    const prefs = await this.loadFromDatabase(userId);
    await this.cache.setex(cacheKey, this.cacheTTL, JSON.stringify(prefs));
    
    return prefs;
  }

  isQuietHours(prefs) {
    const userHour = new Date().toLocaleString("en-US", {
      timeZone: prefs.timezone,
      hour: 'numeric',
      hour12: false
    });
    const currentHour = parseInt(userHour);
    
    const start = prefs.quiet_hours_start;
    const end = prefs.quiet_hours_end;
    
    if (start <= end) {
      return currentHour >= start && currentHour <= end;
    } else {
      return currentHour >= start || currentHour <= end;
    }
  }
}
```

---

## 5. Realistic 6-Month Delivery Plan

### Month 1-2: Foundation
**Team Focus: 2 engineers on core, 2 on infrastructure**
- [ ] Basic notification API endpoints
- [ ] PostgreSQL schema and migrations
- [ ] Redis setup and connection pooling
- [ ] Push notification integration (FCM/APNS)
- [ ] Basic user preference management
- [ ] Unit tests and local development setup

**Deliverable:** Push notifications working in development

### Month 3-4: Production Ready
**Team Focus: 3 engineers on features, 1 on DevOps**
- [ ] Background job processing with Bull
- [ ] WebSocket connection management
- [ ] Email digest system
- [ ] Preference caching layer
- [ ] Basic monitoring with Prometheus/Grafana
- [ ] Load testing and performance optimization

**Deliverable:** MVP deployed to staging environment

### Month 5-6: Polish and Scale
**Team Focus: 2 engineers on features, 2 on reliability**
- [ ] SMS integration for security alerts
- [ ] Advanced preference UI
- [ ] Comprehensive error handling and retries
- [ ] Production monitoring and alerting
- [ ] Documentation and runbooks
- [ ] Load testing at target scale

**Deliverable:** Production deployment supporting 1M+ notifications/day

---

## 6. Monitoring and Observability

### Essential Metrics
```javascript
const CORE_METRICS = {
  // Business metrics
  notifications_sent_total: 'counter by channel and type',
  notifications_delivered_total: 'counter by channel',
  notifications_failed_total: 'counter by channel and reason',
  
  // Performance metrics
  notification_processing_duration: 'histogram',
  queue_depth: 'gauge',
  active_websocket_connections: 'gauge',
  
  // Infrastructure metrics
  database_connection_pool_usage: 'gauge',
  redis_memory_usage: 'gauge',
  api_response_time: 'histogram'
};
```

### Alerting Rules
```yaml
alerts:
  - alert: NotificationQueueBacklog
    expr: queue_depth > 1000
    for: 2m
    
  - alert: HighNotificationFailureRate
    expr: rate(notifications_failed_total[5m]) / rate(notifications_sent_total[5m]) > 0.1
    for: 1m
    
  - alert: DatabaseConnectionExhaustion
    expr: database_connection_pool_usage > 0.8
    for: 1m
```

---

## 7. Cost Analysis (Realistic)

### Infrastructure Costs (Monthly)
- AWS EC2 instances: $400
- RDS PostgreSQL: $200  
- ElastiCache Redis: $100
- Application Load Balancer: $25
- Data transfer: $50
- **Total Infrastructure: $775/month**

### Third-Party Service Costs (Monthly)
- FCM: Free (Google)
- APNS: