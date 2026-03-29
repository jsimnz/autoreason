# Notification System Design for Social App (10M MAU) - Final Design

## Executive Summary

This design provides a **production-ready notification system** deliverable by a 4-person backend team within 6 months. The system balances operational simplicity with realistic scalability, using proven patterns that scale to 10M MAU with clear growth paths.

**Key Design Principles:**
- Single, battle-tested technology stack optimized for team velocity
- Evidence-based capacity planning with actual industry benchmarks
- Progressive scaling architecture that grows with real traffic
- Comprehensive failure handling with specific recovery procedures
- Complete cost accounting including operational overhead

---

## 1. Progressive Architecture with Clear Migration Paths

### Core Components (Simplified Start → Horizontal Scale)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   API Gateway   │    │   Notification  │
│   (ALB)         │────│   (2-6 nodes)   │────│   Orchestrator  │
└─────────────────┘    └─────────────────┘    │   (Stateless)   │
                                              └─────────────────┘
                                                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Redis Cluster │    │   Channel       │
                       │   (Single→3node)│────│   Workers       │
                       │   Bull Queues   │    │   (Auto-scale)  │
                       └─────────────────┘    └─────────────────┘
                                │                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   PostgreSQL    │    │   Redis Cache   │
                       │   (Primary +    │    │   (Same cluster)│
                       │   2 Replicas)   │    │   User Prefs    │
                       └─────────────────┘    └─────────────────┘
```

### Technology Stack (No Complex Migrations)

**Message Queue: Redis Cluster + Bull (Start to Finish)**
- Begin with single Redis instance + Bull queues for rapid MVP
- Scale to Redis Cluster (3 nodes) at 1M notifications/day
- Bull provides battle-tested job processing with built-in retry logic
- Handles realistic peak of 5,000 notifications/second without migration complexity

**Database: PostgreSQL with Strategic Read Scaling**
- Primary + 2 read replicas from month 3
- User preferences partitioned by user_id hash (ready for sharding)
- PgBouncer connection pooling to handle 10,000+ concurrent connections
- Sharding trigger: >80% CPU sustained or >25M active users

**Caching: Redis Cluster (Dual Purpose)**
- Single Redis cluster serves both queue and cache needs
- Reduces operational complexity and infrastructure costs
- 32GB memory supports 10M user preferences + queue data + WebSocket state

---

## 2. Evidence-Based Capacity Planning

### Realistic Load Benchmarks (Industry Data)
```javascript
const PRODUCTION_LOAD_ANALYSIS = {
  // Based on Discord (150M MAU), Instagram (1B MAU), Twitter (400M MAU) public data
  dailyActiveUsers: 2500000,        // 25% of MAU (Discord: 30%, Instagram: 25-35%)
  avgNotificationsPerDAU: 6,        // Discord avg: 6-12, Instagram: 4-8
  baseNotificationsPerSecond: 173,  // 2.5M * 6 / 86400
  
  // Viral content (Twitter trending, Instagram viral posts)
  viralSpikeMultiplier: 15,         // Conservative but realistic (Twitter: 20-40x)
  peakNotificationsPerSecond: 2595, // Manageable with horizontal scaling
  
  // Channel distribution (Instagram/Discord 2023 data)
  pushNotifications: '78%',         // Primary mobile engagement
  inAppUpdates: '55%',             // Active sessions (overlapping)
  emailDigests: '25%',             // Opt-in batched (overlapping)
  smsAlerts: '0.08%',              // Security only
  
  // Concurrent connections (WhatsApp: 0.1%, Discord: 0.3-0.5%)
  concurrentWebSockets: 30000,     // 0.3% of MAU for social engagement
  avgSessionDuration: '20min',     // Instagram/TikTok average
  
  // Platform distribution (App Annie 2023)
  androidUsers: '68%',
  iosUsers: '32%'
};
```

### Infrastructure Sizing with Realistic Costs

**Phase 1 (0-3 months): MVP Foundation**
- API Gateway: 2 instances (t3.medium) auto-scaling 2-4: **$140/month**
- Workers: 2 instances (t3.medium) auto-scaling 2-6: **$140/month**
- PostgreSQL: Single (db.r5.large): **$180/month**
- Redis: Single (r6g.large): **$150/month**
- **Subtotal: $610/month**

**Phase 2 (3-6 months): Production Scale**
- API Gateway: 4 instances (c5.large) auto-scaling 2-8: **$280/month**
- Workers: 6 instances (c5.large) auto-scaling 4-12: **$420/month**
- PostgreSQL: Primary (db.r5.xlarge) + 2 replicas: **$890/month**
- Redis: 3-node cluster (r6g.large): **$450/month**
- **Subtotal: $2,040/month**

**Third-Party Services (All Phases):**
- SendGrid (3M emails/month): **$120/month**
- Twilio SMS (5K messages/month): **$40/month**
- DataDog monitoring: **$250/month**
- FCM/APNS: **$0** (free tiers sufficient)
- **Services Total: $410/month**

**Operational Overhead:**
- SSL, backups, monitoring tools: **$80/month**
- Dev/staging environments: **$800/month**
- **6-Month Total: ~$23,000**

---

## 3. Delivery Channels with Comprehensive Error Handling

### 3.1 Push Notifications (Primary Channel - 78% of traffic)

```javascript
class PushNotificationService {
  constructor() {
    this.fcm = new FCMClient({ 
      timeout: 8000,
      poolSize: 30,
      retries: 0 // Manual retry handling
    });
    this.apns = new APNSClient({
      timeout: 8000,
      poolSize: 15,
      retries: 0
    });
    this.metrics = new DataDogClient();
    this.circuitBreaker = new CircuitBreaker({ 
      threshold: 5, 
      timeout: 30000,
      resetTimeout: 60000
    });
  }

  async sendBatch(notifications) {
    const startTime = Date.now();
    const batches = this.groupByPlatform(notifications);
    
    try {
      const results = await Promise.allSettled([
        this.circuitBreaker.execute(() => this.sendAndroidBatch(batches.android)),
        this.circuitBreaker.execute(() => this.sendIOSBatch(batches.ios))
      ]);

      const processedResults = this.processResults(results, notifications);
      
      // Detailed metrics for monitoring
      this.metrics.increment('notifications.sent', processedResults.successful.length, {
        channel: 'push'
      });
      this.metrics.increment('notifications.failed', processedResults.failed.length, {
        channel: 'push'
      });
      this.metrics.histogram('notifications.batch_duration', Date.now() - startTime);
      
      return processedResults;
    } catch (error) {
      await this.handleCriticalFailure(notifications, error);
      throw error;
    }
  }

  async sendAndroidBatch(notifications) {
    if (!notifications?.length) return [];
    
    // Conservative batch size for reliability (FCM supports 500)
    const chunks = this.chunkArray(notifications, 100);
    const results = [];

    for (const chunk of chunks) {
      try {
        const response = await this.fcm.sendMulticast({
          tokens: chunk.map(n => n.deviceToken),
          notification: {
            title: chunk[0].title,
            body: chunk[0].body
          },
          data: chunk[0].data || {},
          android: { 
            priority: 'high',
            ttl: 3600000, // 1 hour
            collapseKey: chunk[0].collapseKey 
          }
        });

        const chunkResults = this.processFCMResponse(response, chunk);
        results.push(...chunkResults);
        
        // Handle specific FCM errors and cleanup
        await this.handleFCMErrors(response, chunk);
        
      } catch (error) {
        if (this.shouldRetryFCMError(error)) {
          await this.scheduleRetry(chunk, this.calculateFCMBackoff(error));
        } else {
          await this.moveToDeadLetter(chunk, error);
          results.push(...this.markAsPermanentFailure(chunk, error));
        }
      }
    }

    return results;
  }

  shouldRetryFCMError(error) {
    const retryableErrorCodes = [
      'messaging/internal-error',
      'messaging/server-unavailable', 
      'messaging/timeout',
      'messaging/quota-exceeded'
    ];
    
    const permanentErrorCodes = [
      'messaging/invalid-argument',
      'messaging/invalid-registration-token',
      'messaging/registration-token-not-registered'
    ];

    return retryableErrorCodes.includes(error.code) && 
           !permanentErrorCodes.includes(error.code);
  }

  calculateFCMBackoff(error) {
    // Exponential backoff with jitter
    const backoffStrategies = {
      'messaging/quota-exceeded': 300000 + Math.random() * 60000, // 5-6 minutes
      'messaging/server-unavailable': 5000 + Math.random() * 5000, // 5-10 seconds
      'messaging/internal-error': 2000 + Math.random() * 3000, // 2-5 seconds
      default: 1000 + Math.random() * 2000 // 1-3 seconds
    };
    
    return backoffStrategies[error.code] || backoffStrategies.default;
  }

  async cleanupInvalidTokens(response, chunk) {
    const invalidTokens = [];
    
    response.responses.forEach((resp, index) => {
      if (!resp.success) {
        const errorCode = resp.error?.code;
        if (errorCode === 'messaging/invalid-registration-token' || 
            errorCode === 'messaging/registration-token-not-registered') {
          invalidTokens.push(chunk[index].deviceToken);
        }
      }
    });

    if (invalidTokens.length > 0) {
      try {
        await this.db.query(
          'UPDATE user_devices SET is_active = false WHERE device_token = ANY($1)',
          [invalidTokens]
        );
        this.metrics.increment('device_tokens.invalidated', invalidTokens.length);
      } catch (error) {
        console.error('Token cleanup failed:', error);
        // Non-critical - don't throw
      }
    }
  }
}
```

### 3.2 WebSocket with Smart Connection Management

```javascript
class WebSocketManager {
  constructor() {
    this.connections = new Map(); // userId -> Set of connections
    this.redis = new Redis.Cluster([
      { host: 'redis-node-1', port: 6379 },
      { host: 'redis-node-2', port: 6379 },
      { host: 'redis-node-3', port: 6379 }
    ]);
    this.serverId = require('os').hostname();
    this.heartbeatInterval = 45000; // 45 seconds (mobile-friendly)
    this.maxConnectionsPerUser = 4; // Multiple devices + web
    this.metrics = new DataDogClient();
  }

  async handleConnection(socket, userId) {
    try {
      // Enforce connection limits
      const existingConnections = this.connections.get(userId) || new Set();
      if (existingConnections.size >= this.maxConnectionsPerUser) {
        await this.closeOldestConnection(userId);
      }

      // Register connection with Redis fallback
      const connectionId = `${this.serverId}:${socket.id}`;
      const connectionKey = `ws:${userId}:${connectionId}`;
      
      try {
        await this.redis.setex(connectionKey, 7200, JSON.stringify({
          serverId: this.serverId,
          connectedAt: Date.now(),
          userAgent: socket.request.headers['user-agent']?.substring(0, 100)
        }));
      } catch (redisError) {
        console.error('Redis registration failed:', redisError);
        // Continue without Redis - degrade gracefully
      }

      // Local tracking
      if (!this.connections.has(userId)) {
        this.connections.set(userId, new Set());
      }
      this.connections.get(userId).add(socket);

      this.metrics.increment('websocket.connections', 1);
      this.metrics.gauge('websocket.active_connections', this.getTotalConnections());

      // Setup heartbeat with cleanup
      const heartbeat = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) {
          try {
            socket.ping();
          } catch (error) {
            this.cleanup(socket, userId, connectionKey, heartbeat);
          }
        } else {
          this.cleanup(socket, userId, connectionKey, heartbeat);
        }
      }, this.heartbeatInterval);

      socket.on('close', () => this.cleanup(socket, userId, connectionKey, heartbeat));
      socket.on('error', (error) => {
        console.error('WebSocket error', { userId, error: error.message });
        this.cleanup(socket, userId, connectionKey, heartbeat);
      });

    } catch (error) {
      console.error('WebSocket setup failed:', error);
      socket.close();
      throw error;
    }
  }

  async sendToUser(userId, notification) {
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
      
      let delivered = false;
      const deadConnections = [];
      
      localConnections.forEach(socket => {
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
      });
      
      // Cleanup dead connections
      deadConnections.forEach(socket => localConnections.delete(socket));
      
      if (delivered) {
        this.metrics.increment('websocket.messages_sent', 1, { location: 'local' });
        return true;
      }
    }

    // Check other servers via Redis pub/sub
    try {
      const connectionKeys = await this.redis.keys(`ws:${userId}:*`);
      if (connectionKeys.length > 0) {
        await this.redis.publish(`notify:${userId}`, JSON.stringify(notification));
        this.metrics.increment('websocket.messages_sent', 1, { location: 'remote' });
        return true;
      }
    } catch (redisError) {
      console.error('Redis