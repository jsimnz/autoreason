# Notification System Design for Social App (10M MAU)

## Executive Summary

This design provides a **pragmatic, production-ready** notification system for a social app with 10M MAU, deliverable by a 4-person backend team within 6 months. The system balances operational simplicity with realistic scalability requirements, prioritizing **incremental scaling** over premature optimization while handling viral content spikes effectively.

**Key Design Principles:**
- Simplified technology stack optimized for team productivity
- Evidence-based capacity planning with realistic traffic patterns
- Progressive architecture that scales with actual growth
- Comprehensive failure handling and monitoring from day one
- User-centric preference management with smart defaults

---

## 1. System Architecture

### Core Components (Progressive Complexity)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   API Gateway   │    │   Notification  │
│   (ALB)         │────│   (2-6 nodes)   │────│   Orchestrator  │
└─────────────────┘    └─────────────────┘    │   (Stateless)   │
                                              └─────────────────┘
                                                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Redis Streams │    │   Channel       │
                       │   (Single→      │────│   Workers       │
                       │   Cluster)      │    │   (Auto-scale)  │
                       └─────────────────┘    └─────────────────┘
                                │                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   PostgreSQL    │    │   Redis Cache   │
                       │   (Single→      │    │   (Single→      │
                       │   Sharded)      │    │   Cluster)      │
                       └─────────────────┘    └─────────────────┘
```

### Technology Stack Rationale

**Message Queue: Redis Streams with Clear Migration Path**
- Start with single Redis instance + Bull queues for rapid development
- Migrate to Redis Streams clustering at 50M+ notifications/day
- Clear path to Kafka at 100M+ MAU scale
- Handles realistic peak loads of 1,000-5,000 notifications/second

**Database: PostgreSQL with Planned Sharding**
- Single instance with read replicas for first 6 months
- User preferences partitioned by date, ready for sharding
- Sharding trigger: >25M active users or sustained >80% CPU
- Connection pooling with PgBouncer from day one

**Caching: Redis with Progressive Clustering**
- Single Redis instance initially (sufficient for 10M users)
- Cluster migration when memory exceeds 32GB or traffic patterns demand it
- User preferences, device tokens, and WebSocket state management

---

## 2. Realistic Capacity Planning

### Evidence-Based Load Analysis
```javascript
const REALISTIC_LOAD_CALCULATIONS = {
  // Conservative estimates based on Discord, Slack, Instagram data
  dailyActiveUsers: 2500000,        // 25% of MAU (realistic for social apps)
  avgNotificationsPerUser: 5,       // Includes all channels
  baseNotificationsPerSecond: 347,  // 2.5M * 5 / 86400 = 144 avg, 2.5x peak
  
  // Viral content handling (TikTok/Twitter viral post analysis)
  viralSpikeMultiplier: 8,          // Realistic but manageable
  peakNotificationsPerSecond: 2776, // Still within single-server capacity
  
  // Channel distribution (mobile-first social app)
  pushNotifications: '80%',         // Primary engagement channel
  inAppUpdates: '60%',             // Active users only (overlapping)
  emailDigests: '30%',             // Daily/weekly batches (overlapping)
  smsAlerts: '0.1%',               // Security only
  
  // Connection requirements (WhatsApp benchmark: 0.1-0.3% concurrent)
  concurrentWebSockets: 25000,     // 0.25% of MAU realistic for social app
  avgSessionDuration: '18min'       // Typical social media session
};
```

### Infrastructure Sizing (Conservative with Growth Path)

**Phase 1 (0-3 months): MVP Foundation**
- API Gateway: 2 instances (t3.medium) with auto-scaling 2-4
- Workers: 2 instances (t3.medium) with auto-scaling 2-6
- PostgreSQL: Single instance (db.r5.large) + 1 read replica
- Redis: Single instance (r6g.large)
- **Cost: ~$800/month**

**Phase 2 (3-6 months): Production Scale**
- API Gateway: 4 instances with auto-scaling 2-8
- Workers: 6 instances with auto-scaling 4-12
- PostgreSQL: (db.r5.xlarge) + 2 read replicas
- Redis: Upgrade to (r6g.xlarge) or 3-node cluster
- **Cost: ~$1,600/month**

**Phase 3 (6+ months): High Scale**
- API Gateway: 6 instances with auto-scaling 4-12
- Workers: 12 instances with auto-scaling 6-24
- PostgreSQL: 4 shards (db.r5.large each) + read replicas
- Redis: 3-node cluster + separate cache cluster
- **Cost: ~$3,200/month**

**Scaling Triggers:**
- Database CPU >75% sustained for 10 minutes → Vertical scaling
- Queue depth >500 for 5 minutes → Add workers
- Redis memory >80% → Upgrade or cluster
- API response time >200ms p95 → Horizontal scaling

---

## 3. Delivery Channels Implementation

### 3.1 Push Notifications (Primary Channel - 80% of traffic)

```javascript
class PushNotificationService {
  constructor() {
    this.fcm = new FCMClient({ 
      timeout: 5000,
      poolSize: 20,
      retries: 3
    });
    this.apns = new APNSClient({ 
      timeout: 5000,
      poolSize: 10,
      retries: 3
    });
    this.circuitBreaker = new CircuitBreaker({ 
      threshold: 5, 
      timeout: 30000,
      resetTimeout: 60000
    });
  }

  async sendBatch(notifications) {
    const batches = this.groupByPlatform(notifications);
    
    try {
      const results = await Promise.allSettled([
        this.circuitBreaker.execute(() => this.sendAndroidBatch(batches.android)),
        this.circuitBreaker.execute(() => this.sendIOSBatch(batches.ios))
      ]);

      return this.processResults(results, notifications);
    } catch (error) {
      await this.handleBatchFailure(notifications, error);
      throw error;
    }
  }

  async sendAndroidBatch(notifications) {
    if (!notifications?.length) return [];
    
    // Conservative batch size for reliability
    const chunks = this.chunkArray(notifications, 100);
    const results = [];

    for (const chunk of chunks) {
      try {
        const response = await this.fcm.sendMulticast({
          tokens: chunk.map(n => n.deviceToken),
          notification: this.formatPayload(chunk[0]),
          android: { 
            priority: 'high',
            ttl: 3600000,
            collapseKey: chunk[0].collapseKey 
          }
        });

        results.push(...this.processFCMResponse(response, chunk));
        
        // Clean up invalid tokens
        await this.cleanupInvalidTokens(response, chunk);
        
      } catch (error) {
        if (this.isRetryableError(error)) {
          await this.scheduleRetry(chunk, this.calculateBackoff(error));
        } else {
          results.push(...this.markAsFailed(chunk, error));
        }
      }
    }

    return results;
  }

  isRetryableError(error) {
    const retryableCodes = [
      'messaging/internal-error',
      'messaging/server-unavailable',
      'messaging/timeout',
      'messaging/quota-exceeded'
    ];
    return retryableCodes.includes(error.code);
  }

  calculateBackoff(error) {
    // Exponential backoff with jitter
    const baseDelay = error.code === 'messaging/quota-exceeded' ? 60000 : 1000;
    const jitter = Math.random() * 1000;
    return baseDelay + jitter;
  }
}
```

### 3.2 WebSocket Connections (Real-time Updates)

```javascript
class WebSocketManager {
  constructor() {
    this.connections = new Map(); // userId -> Set of connections
    this.redis = new Redis({ /* single instance config */ });
    this.serverId = process.env.SERVER_ID || require('os').hostname();
    this.heartbeatInterval = 30000;
    this.maxConnectionsPerUser = 3; // Prevent abuse
  }

  async handleConnection(socket, userId) {
    // Enforce connection limits
    const existingConnections = this.connections.get(userId) || new Set();
    if (existingConnections.size >= this.maxConnectionsPerUser) {
      this.closeOldestConnection(userId);
    }

    // Register connection locally and in Redis
    const connectionKey = `ws:${userId}:${this.serverId}:${socket.id}`;
    await this.redis.setex(connectionKey, 7200, JSON.stringify({
      serverId: this.serverId,
      connectedAt: Date.now(),
      userAgent: socket.request.headers['user-agent']
    }));

    if (!this.connections.has(userId)) {
      this.connections.set(userId, new Set());
    }
    this.connections.get(userId).add(socket);

    // Setup heartbeat
    const heartbeat = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.ping();
      } else {
        this.cleanup(socket, userId, connectionKey, heartbeat);
      }
    }, this.heartbeatInterval);

    socket.on('close', () => this.cleanup(socket, userId, connectionKey, heartbeat));
    socket.on('error', (error) => {
      console.error('WebSocket error', { userId, error: error.message });
      this.cleanup(socket, userId, connectionKey, heartbeat);
    });
  }

  async sendToUser(userId, notification) {
    // Try local connections first (most common case)
    const localConnections = this.connections.get(userId);
    if (localConnections?.size > 0) {
      const payload = JSON.stringify({
        ...notification,
        timestamp: Date.now()
      });
      
      let sent = false;
      localConnections.forEach(socket => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(payload);
          sent = true;
        }
      });
      
      if (sent) return true;
    }

    // Check other servers (for horizontal scaling)
    const connectionKeys = await this.redis.keys(`ws:${userId}:*`);
    if (connectionKeys.length > 0) {
      await this.redis.publish(`notify:${userId}`, JSON.stringify(notification));
      return true;
    }

    return false; // User offline
  }

  cleanup(socket, userId, connectionKey, heartbeat) {
    clearInterval(heartbeat);
    
    const userConnections = this.connections.get(userId);
    if (userConnections) {
      userConnections.delete(socket);
      if (userConnections.size === 0) {
        this.connections.delete(userId);
      }
    }
    
    this.redis.del(connectionKey).catch(err => 
      console.error('Failed to cleanup Redis connection key', err)
    );
  }
}
```

### 3.3 Email with Smart Batching

```javascript
class EmailBatchingService {
  constructor() {
    this.sendGridClient = new SendGridClient();
    this.batchWindows = new Map(); // userId -> batch data
    this.batchTimeouts = {
      immediate: 0,                 // Security alerts
      high: 10 * 60 * 1000,        // 10 minutes
      medium: 60 * 60 * 1000,      // 1 hour  
      low: 24 * 60 * 60 * 1000     // Daily digest
    };
  }

  async processNotification(notification) {
    const { userId, priority, type } = notification;
    
    // Immediate send for critical notifications
    if (type === 'security_alert' || priority === 'immediate') {
      return this.sendImmediate(notification);
    }
    
    // Skip batching for active users on high-priority notifications
    if (priority === 'high' && await this.isUserActive(userId)) {
      return this.sendImmediate(notification);
    }

    // Add to batch
    this.addToBatch(userId, notification);
  }

  addToBatch(userId, notification) {
    const batchKey = `${userId}:${notification.priority}`;
    
    if (!this.batchWindows.has(batchKey)) {
      this.createBatchWindow(batchKey, notification.priority);
    }

    const batch = this.batchWindows.get(batchKey);
    batch.notifications.push(notification);

    // Send if batch is full (prevent memory issues)
    if (batch.notifications.length >= 20) {
      this.flushBatch(batchKey);
    }
  }

  async sendDigest(userId, notifications) {
    const userEmail = await this.getUserEmail(userId);
    if (!userEmail) return { success: false, reason: 'no_email' };
    
    const digestContent = this.createDigest(notifications);
    
    try {
      const result = await this.sendGridClient.send({
        to: userEmail,
        templateId: 'd-digest-template-id',
        dynamicTemplateData: {
          ...digestContent,
          unsubscribeUrl: `${process.env.APP_URL}/unsubscribe/${userId}`
        },
        customArgs: { 
          batch_size: notifications.length.toString(),
          user_id: userId
        },
        asm: { groupId: 12345 } // Unsubscribe group
      });

      return { success: true, messageId: result[0].messageId };
    } catch (error) {
      console.error('Email send failed', { userId, error: error.message });
      return { success: false, reason: error.message };
    }
  }

  async isUserActive(userId) {
    // Check if user has been active in last 30 minutes
    const lastActive = await this.redis.get(`active:${userId}`);
    return lastActive && (Date.now() - parseInt(lastActive)) < 1800000;
  }
}
```

### 3.4 SMS (Critical Alerts Only)

```javascript
class SMSService {
  constructor() {
    this.twilioClient = new TwilioClient({
      accountSid: process.env.TWILIO_ACCOUNT_SID,
      authToken: process.env.TWILIO_AUTH_TOKEN
    });
    this.allowedTypes = new Set([
      'security_alert', 
      'password_reset', 
      'account_verification',
      'login_attempt'
    ]);
    this.rateLimiter = new Map(); // userId -> timestamps[]
    this.maxSMSPerHour = 3;
  }

  async send(notification) {
    if (!this.allowedTypes.has(notification.type)) {
      throw new Error(`SMS not permitted for notification type: ${notification.type}`);
    }

    // Rate limiting
    if (!await this.checkRateLimit(notification.userId)) {
      throw new Error('SMS rate limit exceeded');
    }

    const phoneNumber = await this.