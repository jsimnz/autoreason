# Notification System Design for Social App (10M MAU)

## Executive Summary

This design provides a production-ready notification system for a social app with 10M MAU, deliverable by a 4-person backend team within 6 months. The system balances scalability, reliability, and operational simplicity while handling realistic traffic patterns including viral content spikes.

**Key Design Principles:**
- Pragmatic technology choices for team size and timeline
- Horizontal scalability for 10M+ users with traffic spike handling
- User-centric preference management with smart defaults
- Comprehensive failure handling and monitoring
- Cost-effective infrastructure with clear scaling path

---

## 1. System Architecture

### Core Components
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   API Gateway   │    │   Notification  │
│   (ALB)         │────│   Cluster       │────│   Orchestrator  │
└─────────────────┘    │   (4-8 nodes)   │    │   (Stateless)   │
                       └─────────────────┘    └─────────────────┘
                                │                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Redis Streams │    │   Channel       │
                       │   (Clustered)   │────│   Workers       │
                       │   + Kafka Ready │    │   (Auto-scale)  │
                       └─────────────────┘    └─────────────────┘
                                │                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   PostgreSQL    │    │   Redis Cluster │
                       │   (Sharded)     │    │   (Preferences  │
                       │   + Read Replicas│    │   & Sessions)   │
                       └─────────────────┘    └─────────────────┘
```

### Technology Stack Rationale

**Message Queue: Redis Streams with Kafka Migration Path**
- Start with Redis Streams for rapid development (6-month timeline)
- Built-in persistence and consumer groups
- Clear migration path to Kafka when scale demands (18+ months)
- Handles 2,000+ msgs/sec reliably with proper clustering

**Database: Sharded PostgreSQL**
- User preferences sharded by user_id hash (4 shards initially)
- Read replicas for analytics and preference lookups
- Connection pooling with PgBouncer

**Caching: Redis Cluster**
- Distributed cache for user preferences and device tokens
- WebSocket connection state management
- Automatic failover and horizontal scaling

**Application Layer: Node.js**
- Team familiarity enables rapid development
- Excellent async I/O for notification workloads
- Rich ecosystem for third-party integrations

---

## 2. Capacity Planning and Scaling

### Peak Load Analysis
```javascript
const REALISTIC_LOAD_CALCULATIONS = {
  // Normal operations
  dailyActiveUsers: 3000000,        // 30% of MAU
  avgNotificationsPerUser: 8,       
  baseNotificationsPerSecond: 833,
  
  // Viral content scenarios (Instagram/TikTok viral posts)
  viralSpikeMultiplier: 20,         // Conservative but realistic
  peakNotificationsPerSecond: 16660,
  
  // Channel distribution
  pushNotifications: '70%',         // ~11,662/sec peak
  emailDigests: '40%',             // ~6,664/sec peak (overlapping)
  inAppUpdates: '90%',             // ~14,994/sec peak
  smsAlerts: '0.1%',               // ~17/sec peak
  
  // Connection requirements  
  concurrentWebSockets: 300000,    // 3% of MAU online simultaneously
  avgSessionDuration: '25min'
};
```

### Infrastructure Sizing

**Phase 1 (0-6 months): MVP Scale**
- Gateway: 4 instances (c5.large) with auto-scaling 2-8
- Workers: 8 instances (c5.large) with auto-scaling 4-16
- Redis Streams: 3-node cluster (r6g.large)
- PostgreSQL: 2 shards (db.r5.large) + 2 read replicas
- **Cost: ~$1,800/month**

**Phase 2 (6-18 months): Production Scale**
- Gateway: 8 instances with auto-scaling 4-16
- Workers: 16 instances with auto-scaling 8-32
- Migration to Kafka (3 brokers, m5.large)
- PostgreSQL: 4 shards (db.r5.xlarge) + 4 read replicas
- **Cost: ~$4,200/month**

---

## 3. Delivery Channels Implementation

### 3.1 Push Notifications (Primary Channel)

```javascript
class PushNotificationService {
  constructor() {
    this.fcmClient = new FCMClient({ poolSize: 50 });
    this.apnsClient = new APNSClient({ poolSize: 25 });
    this.circuitBreaker = new CircuitBreaker({ threshold: 5, timeout: 60000 });
  }

  async sendBatch(notifications) {
    const batches = this.groupByPlatform(notifications);
    
    const results = await Promise.allSettled([
      this.circuitBreaker.execute(() => this.sendAndroidBatch(batches.android)),
      this.circuitBreaker.execute(() => this.sendIOSBatch(batches.ios))
    ]);

    return this.processResults(results, notifications);
  }

  async sendAndroidBatch(notifications) {
    const chunks = this.chunkArray(notifications, 500); // Conservative FCM limit
    const results = [];

    for (const chunk of chunks) {
      try {
        const response = await this.fcmClient.sendMulticast({
          tokens: chunk.map(n => n.deviceToken),
          notification: this.formatPayload(chunk[0]),
          android: { priority: 'high', ttl: 3600000 }
        });

        results.push(...this.processFCMResponse(response, chunk));
      } catch (error) {
        if (error.code === 'messaging/quota-exceeded') {
          await this.scheduleRetry(chunk, this.calculateBackoff());
        } else {
          results.push(...this.markAsFailed(chunk, error));
        }
      }
    }

    return results;
  }
}
```

**Key Features:**
- Firebase Cloud Messaging (FCM) for Android
- Apple Push Notification Service (APNS) for iOS
- Circuit breaker pattern for external service protection
- Automatic device token cleanup for invalid tokens
- Rich notifications with custom actions

### 3.2 WebSocket Connections (Real-time Channel)

```javascript
class WebSocketManager {
  constructor() {
    this.connections = new Map(); // userId -> Set of connections
    this.redis = new Redis.Cluster([/* cluster config */]);
    this.serverId = process.env.SERVER_ID;
  }

  async handleConnection(socket, userId) {
    // Store connection in local map and distributed cache
    const connectionKey = `ws:${userId}:${this.serverId}:${socket.id}`;
    await this.redis.setex(connectionKey, 3600, JSON.stringify({
      serverId: this.serverId,
      connectedAt: Date.now()
    }));

    if (!this.connections.has(userId)) {
      this.connections.set(userId, new Set());
    }
    this.connections.get(userId).add(socket);

    // Heartbeat management
    const heartbeat = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.ping();
      } else {
        this.cleanup(socket, userId, connectionKey, heartbeat);
      }
    }, 30000);

    socket.on('close', () => this.cleanup(socket, userId, connectionKey, heartbeat));
  }

  async sendToUser(userId, notification) {
    // Try local connections first
    const localConnections = this.connections.get(userId);
    if (localConnections?.size > 0) {
      const payload = JSON.stringify(notification);
      localConnections.forEach(socket => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(payload);
        }
      });
      return true;
    }

    // Check other servers via Redis
    const connectionKeys = await this.redis.keys(`ws:${userId}:*`);
    if (connectionKeys.length > 0) {
      await this.redis.publish(`notify:${userId}`, JSON.stringify(notification));
      return true;
    }

    return false; // User offline
  }
}
```

### 3.3 Email with Smart Batching

```javascript
class EmailBatchingService {
  constructor() {
    this.sendGridClient = new SendGridClient();
    this.batchWindows = new Map();
    this.batchTimeouts = {
      high: 5 * 60 * 1000,      // 5 minutes
      medium: 15 * 60 * 1000,   // 15 minutes
      low: 4 * 60 * 60 * 1000   // 4 hours
    };
  }

  async processNotification(notification) {
    const { userId, priority } = notification;
    
    // Skip batching for active users on high-priority notifications
    if (priority === 'high' && await this.isUserActive(userId)) {
      return this.sendImmediate(notification);
    }

    // Add to batch
    const batchKey = `${userId}:${priority}`;
    this.addToBatch(batchKey, notification);
  }

  addToBatch(batchKey, notification) {
    if (!this.batchWindows.has(batchKey)) {
      this.createBatchWindow(batchKey, notification.priority);
    }

    const batch = this.batchWindows.get(batchKey);
    batch.notifications.push(notification);

    // Send if batch is full
    if (batch.notifications.length >= 50) {
      this.flushBatch(batchKey);
    }
  }

  async sendDigest(notifications) {
    const userEmail = await this.getUserEmail(notifications[0].userId);
    const digestContent = this.createDigest(notifications);
    
    return this.sendGridClient.send({
      to: userEmail,
      templateId: 'digest-template',
      dynamicTemplateData: digestContent,
      customArgs: { batch_size: notifications.length.toString() }
    });
  }
}
```

### 3.4 SMS (Critical Only)

```javascript
class SMSService {
  constructor() {
    this.twilioClient = new TwilioClient();
    this.allowedTypes = new Set(['security_alert', 'password_reset', 'account_verification']);
  }

  async send(notification) {
    if (!this.allowedTypes.has(notification.type)) {
      throw new Error(`SMS not allowed for type: ${notification.type}`);
    }

    const phoneNumber = await this.getUserPhoneNumber(notification.userId);
    if (!phoneNumber) {
      throw new Error('User has no verified phone number');
    }

    return this.twilioClient.messages.create({
      to: phoneNumber,
      body: this.formatSMSMessage(notification),
      from: process.env.TWILIO_PHONE_NUMBER
    });
  }
}
```

---

## 4. User Preference Management

### 4.1 Sharded Preferences Schema

```sql
-- Shard function for even distribution
CREATE OR REPLACE FUNCTION get_user_shard(user_uuid UUID)
RETURNS INTEGER AS $$
BEGIN
    RETURN (hashtext(user_uuid::text) % 4);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Preferences table (replicated across 4 shards)
CREATE TABLE user_notification_preferences_shard_{N} (
    user_id UUID PRIMARY KEY,
    global_enabled BOOLEAN DEFAULT true,
    
    -- Channel preferences
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    
    -- Notification type preferences (denormalized for performance)
    direct_message_push BOOLEAN DEFAULT true,
    direct_message_email BOOLEAN DEFAULT false,
    post_mention_push BOOLEAN DEFAULT true,
    post_mention_email BOOLEAN DEFAULT true,
    post_like_push BOOLEAN DEFAULT false,
    post_like_email BOOLEAN DEFAULT true,
    security_alert_all BOOLEAN DEFAULT true,
    
    -- Quiet hours
    quiet_hours_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME DEFAULT '22:00:00',
    quiet_hours_end TIME DEFAULT '08:00:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX idx_user_prefs_push ON user_notification_preferences_shard_{N} (push_enabled);
CREATE INDEX idx_user_prefs_quiet ON user_notification_preferences_shard_{N} (quiet_hours_enabled, quiet_hours_start, quiet_hours_end);
```

### 4.2 Preference Engine with Caching

```javascript
class PreferenceEngine {
  constructor() {
    this.cache = new Redis.Cluster([/* config */]);
    this.cacheTTL = 3600; // 1 hour
  }

  async shouldSendNotification(userId, notification, channel) {
    const prefs = await this.getPreferences(userId);
    
    // Global disable check
    if (!prefs.global_enabled) return false;
    
    // Channel-specific check
    if (!prefs[`${channel}_enabled`]) return false;
    
    // Notification type check
    const typeKey = `${notification.type}_${channel}`;
    if (prefs[typeKey] === false) return false;
    
    // Quiet hours check (except for security alerts)
    if (prefs.quiet_hours_enabled && notification.type !== 'security_alert') {
      if (this.isQuietHours(prefs)) return false;
    }
    
    return true;
  }

  async getPreferences(userId) {
    // Try cache first
    const cacheKey = `prefs:${userId}`;
    const cached = await this.cache.get(cacheKey);
    if (cached) return JSON.parse(cached);

    // Load from database
    const shard = this.getShardForUser(userId);
    const prefs = await this.loadFromShard(shard, userId);
    
    // Cache for future requests
    await this.cache.setex(cacheKey, this.cacheTTL, JSON.stringify(prefs));
    
    return prefs;
  }

  isQuietHours(prefs) {
    if (!prefs.quiet_hours_enabled) return false;
    
    const now = new Date();
    const userTime = new Date(now.toLocaleString("en-US", {timeZone: prefs.timezone}));
    const currentTime = userTime.toTimeString().slice(0, 5);
    
    const start = prefs.quiet_hours_start;
    const end = prefs.quiet_hours_end;
    
    if (start <= end) {
      return currentTime >= start && currentTime <= end;
    } else {
      // Crosses midnight
      return currentTime >= start || currentTime <= end;
    }
  }
}
```

### 4.3 Smart Onboarding Flow

```javascript
class OnboardingManager {
  constructor() {
    this.progressiveSteps = {
      step1: {
        title: "Essential Notifications",
        types: ['direct_message', 'security_alert'],
        description: "Stay connected and secure"
      },
      step2: {
        title: "Social Updates", 
        types: ['post_mention', 'friend_request'],
        description: "Know when people interact with you"
      },
      step3: {
        title: "Discovery & Engagement",