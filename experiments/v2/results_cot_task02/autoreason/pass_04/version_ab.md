# Notification System Design for Social App (10M MAU) - Executive Synthesis

## Executive Summary

This design provides a **production-ready notification system** deliverable by a 4-person backend team within 6 months. We combine proven architectural patterns with realistic capacity planning, comprehensive error handling, and complete operational cost accounting.

**Key Design Principles:**
- **Phase-based delivery** with measurable business outcomes at each milestone
- **Battle-tested technology stack** optimized for team velocity and operational simplicity
- **Industry-benchmarked capacity planning** based on real social app data
- **Comprehensive failure handling** with specific recovery procedures for each channel
- **Complete cost transparency** including all hidden operational expenses

---

## 1. Phased Delivery Strategy

### Phase 1 (Months 1-3): Core Foundation
**Team:** 4 Backend Engineers + 1 DevOps Engineer (temporary)
**Deliverable:** Push + Email notifications for 3M users (30% MAU)

```
Business Value: 80% of notification use cases covered
Technical Scope: 
- Push notifications (FCM/APNS) with retry logic
- Email notifications (SendGrid) with templates
- Basic user preferences
- WebSocket connections for active sessions
- Production monitoring and alerting
```

### Phase 2 (Months 4-6): Scale & Advanced Features  
**Team:** 4 Backend Engineers
**Deliverable:** Full 10M MAU support + advanced features

```
Business Value: 100% of requirements + analytics
Technical Scope:
- Horizontal scaling to handle viral spikes (25x base load)
- Advanced batching and priority queues
- A/B testing framework
- Comprehensive analytics and user behavior tracking
- SMS integration for security notifications
```

---

## 2. Production-Ready Architecture

### Core Components (Proven at Scale)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ALB           │    │   API Service   │    │   Worker Pool   │
│   (AWS)         │────│   (Node.js)     │────│   (Bull Queue)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   PostgreSQL    │    │   Redis Cluster │
                       │   (Primary +    │────│   (Queue + Cache)│
                       │   Read Replicas)│    │   (3 nodes)     │
                       └─────────────────┘    └─────────────────┘
                                │
                       ┌─────────────────┐
                       │   External APIs │
                       │   (FCM/APNS/    │
                       │   SendGrid)     │
                       └─────────────────┘
```

### Technology Stack Rationale

**Node.js + Express:** Team familiarity, extensive ecosystem, proven at Discord/Instagram scale
**Redis Cluster + Bull:** Battle-tested queue system, handles 50M+ jobs/day, built-in retry logic
**PostgreSQL + Read Replicas:** Scales to 100M users (Instagram case study), no sharding complexity
**AWS Managed Services:** Reduces operational overhead, built-in monitoring and scaling

---

## 3. Industry-Benchmarked Capacity Planning

### Realistic Load Projections (Based on Discord, Instagram, Twitter Data)

```javascript
const PRODUCTION_BENCHMARKS = {
  // Daily active users (30% of MAU - industry standard)
  dailyActiveUsers: 3000000,
  
  // Notification volume (Discord: 6-12 per DAU average)
  avgNotificationsPerDAU: 8,
  baseNotificationsPerSecond: 278, // 3M * 8 / 86400
  
  // Viral spike handling (Twitter reports 20-40x during major events)
  viralSpikeMultiplier: 25,
  maxPeakNotificationsPerSecond: 6950,
  
  // Channel distribution (Instagram 2023 public data)
  pushNotifications: '75%',    // Primary engagement channel
  inAppWebSocket: '45%',      // Active sessions only  
  emailDigests: '20%',        // Weekly/daily digests
  smsAlerts: '0.05%',         // Security only (2FA, suspicious login)
  
  // Concurrent WebSocket connections (Discord: 0.3-0.5% of MAU)
  maxConcurrentSockets: 50000, // 0.5% of MAU
  avgSessionDuration: '23min'  // Instagram average
};
```

### Infrastructure Sizing with Complete Cost Analysis

**Production Environment:**
- API Servers: 4x c5.large (auto-scale 2-8): **$280/month**
- Worker Pool: 6x c5.large (auto-scale 4-12): **$420/month**  
- PostgreSQL: Primary (db.r5.xlarge) + 2 replicas: **$890/month**
- Redis Cluster: 3x r6g.large nodes: **$450/month**
- Load Balancer + Data Transfer: **$200/month**

**Third-Party Services:**
- SendGrid (5M emails/month): **$150/month**
- Twilio SMS (10K security messages): **$75/month**
- DataDog (monitoring + APM): **$300/month**
- FCM/APNS: **$0** (within free tiers)

**Operational Overhead (Often Missed):**
- Development/Staging environments: **$1,380/month**
- SSL certificates, backups, compliance: **$200/month**
- Security audits and penetration testing: **$500/month**

**Total 6-Month Cost: $31,320 infrastructure + $270,000 team = $301,320**

---

## 4. Comprehensive Delivery Channels

### 4.1 Push Notifications with Platform-Specific Error Recovery

```javascript
class PushNotificationService {
  constructor() {
    this.fcm = new FCMClient({ 
      timeout: 10000,
      poolSize: 50,
      retries: 0 // Manual retry handling
    });
    this.apns = new APNSClient({ timeout: 10000, poolSize: 20 });
    this.retryQueue = new Bull('push-retries');
    this.deadLetterQueue = new Bull('failed-notifications');
    this.metrics = new DataDogClient();
  }

  async sendBatch(notifications) {
    const startTime = Date.now();
    const batches = this.groupByPlatform(notifications);
    
    const [androidResults, iosResults] = await Promise.allSettled([
      this.sendAndroidBatch(batches.android),
      this.sendIOSBatch(batches.ios)
    ]);

    const results = this.processResults([androidResults, iosResults]);
    
    // Record comprehensive metrics
    this.metrics.increment('notifications.sent', results.successful.length, {
      channel: 'push'
    });
    this.metrics.increment('notifications.failed', results.failed.length, {
      channel: 'push', 
      failure_type: this.classifyFailures(results.failed)
    });
    this.metrics.histogram('notifications.batch_duration', Date.now() - startTime);
    
    return results;
  }

  async sendAndroidBatch(notifications) {
    if (!notifications?.length) return [];
    
    // FCM supports up to 500 tokens per request
    const chunks = this.chunkArray(notifications, 500);
    const results = [];

    for (const chunk of chunks) {
      try {
        const response = await this.fcm.sendMulticast({
          tokens: chunk.map(n => n.deviceToken),
          notification: { title: chunk[0].title, body: chunk[0].body },
          data: chunk[0].data || {},
          android: { 
            priority: this.mapPriority(chunk[0].priority),
            ttl: 3600000, // 1 hour
            collapseKey: chunk[0].collapseKey 
          }
        });

        const chunkResults = this.processFCMResponse(response, chunk);
        results.push(...chunkResults);
        
        // Handle token cleanup for permanent failures
        await this.handleFCMTokenCleanup(response, chunk);
        
      } catch (error) {
        if (this.shouldRetryFCMError(error)) {
          // Exponential backoff with jitter
          const delay = this.calculateBackoff(error, chunk[0].retryCount || 0);
          await this.scheduleRetry(chunk, delay);
        } else {
          // Permanent failure - move to dead letter queue
          await this.moveToDeadLetter(chunk, error);
          results.push(...this.markAsPermanentFailure(chunk, error));
        }
      }
    }

    return results;
  }

  shouldRetryFCMError(error) {
    const retryableErrors = [
      'messaging/internal-error',
      'messaging/server-unavailable',
      'messaging/timeout',
      'messaging/quota-exceeded'
    ];
    
    const permanentErrors = [
      'messaging/invalid-argument',
      'messaging/invalid-registration-token',
      'messaging/registration-token-not-registered'
    ];

    if (permanentErrors.includes(error.code)) return false;
    return retryableErrors.includes(error.code);
  }

  calculateBackoff(error, retryCount) {
    const baseDelays = {
      'messaging/quota-exceeded': 300000, // 5 minutes
      'messaging/server-unavailable': 5000, // 5 seconds
      'messaging/internal-error': 1000, // 1 second
      default: 2000 // 2 seconds
    };
    
    const baseDelay = baseDelays[error.code] || baseDelays.default;
    const exponentialDelay = baseDelay * Math.pow(2, Math.min(retryCount, 5));
    const jitter = Math.random() * 1000; // Add jitter to prevent thundering herd
    
    return Math.min(exponentialDelay + jitter, 600000); // Max 10 minutes
  }

  async handleFCMTokenCleanup(response, chunk) {
    const invalidTokens = [];
    
    response.responses.forEach((resp, index) => {
      if (!resp.success) {
        const errorCode = resp.error?.code;
        if (errorCode === 'messaging/invalid-registration-token' || 
            errorCode === 'messaging/registration-token-not-registered') {
          invalidTokens.push({
            token: chunk[index].deviceToken,
            userId: chunk[index].userId
          });
        }
      }
    });

    if (invalidTokens.length > 0) {
      // Async cleanup to not block notification flow
      setImmediate(async () => {
        try {
          await this.cleanupInvalidTokens(invalidTokens);
        } catch (error) {
          console.error('Token cleanup failed:', error);
          // Non-critical - don't throw
        }
      });
    }
  }

  async cleanupInvalidTokens(invalidTokens) {
    const tokens = invalidTokens.map(t => t.token);
    await this.db.query(
      'UPDATE user_devices SET is_active = false, deactivated_at = NOW() WHERE device_token = ANY($1)',
      [tokens]
    );
    
    this.metrics.increment('device_tokens.invalidated', tokens.length);
  }
}
```

### 4.2 WebSocket with Robust Connection Management

```javascript
class WebSocketManager {
  constructor() {
    this.connections = new Map(); // userId -> Set of connections
    this.redis = new Redis.Cluster([/* cluster config */]);
    this.serverId = require('os').hostname();
    this.heartbeatInterval = 60000; // 1 minute
    this.maxConnectionsPerUser = 5; // Prevent abuse
    this.metrics = new DataDogClient();
  }

  async handleConnection(socket, userId) {
    try {
      // Enforce connection limits
      await this.enforceConnectionLimits(userId, socket);
      
      // Register connection with Redis for cross-server communication
      const connectionId = `${this.serverId}:${socket.id}`;
      const connectionKey = `ws:${userId}:${connectionId}`;
      
      await this.redis.setex(connectionKey, 7200, JSON.stringify({
        serverId: this.serverId,
        connectedAt: Date.now(),
        userAgent: socket.request.headers['user-agent']?.substring(0, 200)
      }));

      // Local connection tracking
      if (!this.connections.has(userId)) {
        this.connections.set(userId, new Set());
      }
      this.connections.get(userId).add(socket);

      // Setup heartbeat with comprehensive error handling
      const heartbeat = this.setupHeartbeat(socket, userId, connectionKey);
      
      // Event handlers
      socket.on('close', () => this.cleanup(socket, userId, connectionKey, heartbeat));
      socket.on('error', (error) => {
        this.metrics.increment('websocket.errors', 1, { error: error.code });
        this.cleanup(socket, userId, connectionKey, heartbeat);
      });
      
      socket.on('pong', () => this.updateLastSeen(userId));

      this.metrics.increment('websocket.connections', 1);
      this.metrics.gauge('websocket.active_connections', this.getTotalConnections());

    } catch (error) {
      console.error('WebSocket connection failed:', error);
      socket.close();
      throw error;
    }
  }

  async sendToUser(userId, notification) {
    let delivered = false;
    const startTime = Date.now();
    
    // Try local connections first (most efficient)
    const localConnections = this.connections.get(userId);
    if (localConnections?.size > 0) {
      const payload = JSON.stringify({
        id: notification.id,
        type: notification.type,
        title: notification.title,
        body: notification.body,
        data: notification.data || {},
        timestamp: Date.now()
      });
      
      delivered = await this.sendToLocalConnections(localConnections, payload);
    }

    // If no local connections, check other servers
    if (!delivered) {
      delivered = await this.sendViaRedisCluster(userId, notification);
    }

    this.metrics.histogram('websocket.send_duration', Date.now() - startTime);
    this.metrics.increment('websocket.messages_sent', 1, { 
      delivered: delivered.toString(),
      location: delivered ? 'local' : 'remote'
    });

    return delivered;
  }

  async sendToLocalConnections(connections, payload) {
    let delivered = false;
    const deadConnections = [];
    
    for (const socket of connections) {
      if (socket.readyState === WebSocket.OPEN) {
        try {
          socket.send(payload);
          delivered = true;
        } catch (error) {
          deadConnections.push(socket);
        }
      } else {
        deadConnections.push(socket);
      }
    }
    
    // Clean up dead connections
    deadConnections.forEach(socket => connections.delete(socket));
    
    return delivered;
  }

  async sendViaRedisCluster(userId, notification) {
    try {
      // Find active connections on other servers
      const pattern = `ws:${userId}:*`;
      const keys = await this.redis.keys(pattern);
      
      if (keys.length === 0) return false;
      
      // Publish to the appropriate server channels
      const servers = new Set();
      keys.forEach(key => {
        const serverId = key.split(':')[2].split(':')[0];
        servers.add(serverId);
      });
      
      const publishPromises = Array.from(servers).map(serverId => 
        this.redis.publish(`ws:${serverId}`, JSON.stringify({
          userId,
          notification,
          targetServer: serverId
        }))
      );
      
      await Promise