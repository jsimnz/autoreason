# Revised Notification System Design for Social App (10M MAU)

## Executive Summary

This revised proposal addresses the critical scalability, reliability, and operational challenges identified in the original design. The system is architected for real-world production demands including traffic spikes, operational complexity, and a realistic 18-month implementation timeline with adequate team scaling.

**Key Revisions:**
- Apache Kafka replaces Redis for true horizontal scaling and durability
- Proper database sharding and caching strategy for 10M+ users
- Realistic capacity planning for viral content scenarios (50x traffic spikes)
- Comprehensive failure handling and operational procedures
- Extended timeline with team scaling plan

---

## 1. Revised System Architecture

### Core Components with Proper Scaling

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   API Gateway   │    │   Notification  │
│   (Multi-AZ)    │────│   Cluster       │────│   Orchestrator  │
└─────────────────┘    │   (6 instances) │    │   (Stateless)   │
                       └─────────────────┘    └─────────────────┘
                                │                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Apache Kafka  │    │   Channel       │
                       │   (3 brokers,   │────│   Workers       │
                       │   6 partitions) │    │   (Auto-scale)  │
                       └─────────────────┘    └─────────────────┘
                                │                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │   PostgreSQL    │    │   Redis Cluster │
                       │   Cluster       │    │   (Connection   │
                       │   (Sharded)     │    │   State Cache)  │
                       └─────────────────┘    └─────────────────┘
```

### Technology Stack Rationale (Revised)

**Message Queue: Apache Kafka** 
- *Why changed*: Redis Streams cannot handle 833+ msgs/sec with durability guarantees
- True partitioning for horizontal scaling
- Built-in replication and durability
- Handles traffic spikes up to 50,000 notifications/second

**Database: Sharded PostgreSQL**
- *Why changed*: Single database becomes bottleneck at 10M users
- User preferences sharded by user_id hash
- Separate read replicas for analytics queries
- Connection pooling with PgBouncer

**Caching: Redis Cluster**
- *Why changed*: Memory requirements exceed single instance limits
- Distributed cache for user preferences and device tokens
- WebSocket connection state management
- Automatic failover and scaling

---

## 2. Realistic Capacity Planning

### Peak Load Analysis (Corrected)

```javascript
const REALISTIC_LOAD_CALCULATIONS = {
  // Viral content scenarios
  baseNotificationsPerSecond: 833,
  viralSpikeMultiplier: 50,        // Single viral post can trigger massive spikes
  peakNotificationsPerSecond: 41650,
  
  // Real-world distribution
  pushNotifications: '60%',         // 25,000/sec peak
  emailDigests: '30%',             // 12,500/sec peak  
  inAppUpdates: '80%',             // 33,000/sec peak (overlaps with push)
  smsAlerts: '0.1%',               // 42/sec peak (security only)
  
  // Connection requirements
  concurrentWebSockets: 500000,    // 5% of MAU online simultaneously
  avgConnectionDuration: '45min'
};
```

### Infrastructure Sizing (Production-Ready)

**Kafka Cluster:**
- 6 brokers (m5.xlarge) across 3 AZs
- 12 partitions for notification topic
- 7-day retention for debugging
- Handles 50,000+ messages/second

**Application Layer:**
- Gateway: 12 instances (c5.large) with auto-scaling 8-24
- Workers: 24 instances (c5.large) with auto-scaling 16-48  
- Connection managers: 8 instances (m5.xlarge) for WebSocket handling

**Database Layer:**
- 4 PostgreSQL shards (db.r5.2xlarge)
- 8 read replicas (db.r5.xlarge)
- PgBouncer connection pooling

**Redis Cluster:**
- 9 nodes (r6g.2xlarge) in cluster mode
- 64GB total memory capacity
- Handles 1M+ concurrent connections

---

## 3. Proper Database Design

### Sharded User Preferences Schema

```sql
-- Shard function
CREATE OR REPLACE FUNCTION get_shard_id(user_uuid UUID)
RETURNS INTEGER AS $$
BEGIN
    RETURN (hashtext(user_uuid::text) % 4);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Per-shard table (replicated across 4 shards)
CREATE TABLE user_notification_preferences_shard_{N} (
    user_id UUID PRIMARY KEY,
    global_enabled BOOLEAN DEFAULT true,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Indexed preference columns for fast queries
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    
    -- Specific notification type preferences
    direct_message_push BOOLEAN DEFAULT true,
    direct_message_email BOOLEAN DEFAULT false,
    post_like_push BOOLEAN DEFAULT false,
    post_like_email BOOLEAN DEFAULT true,
    security_alert_push BOOLEAN DEFAULT true,
    security_alert_email BOOLEAN DEFAULT true,
    security_alert_sms BOOLEAN DEFAULT true
);

-- Indexes for common queries
CREATE INDEX idx_user_prefs_push_enabled ON user_notification_preferences_shard_{N} (push_enabled);
CREATE INDEX idx_user_prefs_quiet_hours ON user_notification_preferences_shard_{N} (quiet_hours_start, quiet_hours_end);
```

### Device Token Management

```sql
CREATE TABLE device_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    platform VARCHAR(20) NOT NULL, -- 'ios', 'android', 'web'
    token_hash VARCHAR(64) NOT NULL UNIQUE, -- SHA256 of actual token
    encrypted_token BYTEA NOT NULL, -- AES encrypted token
    is_active BOOLEAN DEFAULT true,
    last_used TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Partition by platform for better performance
CREATE INDEX idx_device_tokens_user_platform ON device_tokens (user_id, platform) WHERE is_active = true;
CREATE INDEX idx_device_tokens_cleanup ON device_tokens (last_used) WHERE is_active = true;
```

### Deduplication Strategy

```sql
CREATE TABLE notification_dedup (
    dedup_key VARCHAR(255) PRIMARY KEY, -- hash of user_id + notification_type + source_id
    notification_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL -- TTL for cleanup
);

-- Automatic cleanup of old dedup records
CREATE INDEX idx_notification_dedup_expires ON notification_dedup (expires_at);
```

---

## 4. Scalable Channel Implementation

### 4.1 Push Notifications with Proper Error Handling

```javascript
class PushNotificationService {
  constructor() {
    this.fcmClient = new FCMClient({ 
      poolSize: 100,
      timeout: 30000 
    });
    this.apnsClient = new APNSClient({
      production: process.env.NODE_ENV === 'production',
      poolSize: 50
    });
  }

  async sendBatch(notifications) {
    const batches = this.groupByPlatform(notifications);
    
    const results = await Promise.allSettled([
      this.sendAndroidBatch(batches.android),
      this.sendIOSBatch(batches.ios)
    ]);

    return this.processResults(results, notifications);
  }

  async sendAndroidBatch(notifications) {
    const chunks = this.chunkArray(notifications, 1000); // FCM limit
    const results = [];

    for (const chunk of chunks) {
      try {
        const response = await this.fcmClient.sendMulticast({
          tokens: chunk.map(n => n.deviceToken),
          notification: this.formatFCMPayload(chunk[0]),
          android: {
            priority: 'high',
            ttl: 3600000 // 1 hour
          }
        });

        results.push(...this.processFCMResponse(response, chunk));
      } catch (error) {
        // Handle rate limiting with exponential backoff
        if (error.code === 'messaging/quota-exceeded') {
          await this.handleRateLimit(chunk);
        } else {
          results.push(...chunk.map(n => ({ 
            notificationId: n.id, 
            status: 'failed', 
            error: error.message 
          })));
        }
      }
    }

    return results;
  }

  processFCMResponse(response, notifications) {
    return response.responses.map((result, index) => {
      const notification = notifications[index];
      
      if (result.success) {
        return { 
          notificationId: notification.id, 
          status: 'delivered',
          messageId: result.messageId 
        };
      }

      // Handle specific error cases
      const errorCode = result.error?.code;
      if (errorCode === 'messaging/invalid-registration-token' || 
          errorCode === 'messaging/registration-token-not-registered') {
        // Mark token for cleanup
        this.markTokenInvalid(notification.deviceToken);
      }

      return { 
        notificationId: notification.id, 
        status: 'failed',
        error: result.error?.message,
        retryable: this.isRetryableError(errorCode)
      };
    });
  }
}
```

### 4.2 WebSocket Connection Management at Scale

```javascript
class WebSocketConnectionManager {
  constructor() {
    this.connections = new Map(); // userId -> Set of connection objects
    this.connectionPool = new Redis.Cluster([
      { host: 'redis-1', port: 6379 },
      { host: 'redis-2', port: 6379 },
      { host: 'redis-3', port: 6379 }
    ]);
    this.serverId = process.env.SERVER_ID;
  }

  async handleConnection(socket, userId) {
    // Store connection mapping in distributed cache
    const connectionKey = `conn:${userId}:${this.serverId}:${socket.id}`;
    await this.connectionPool.setex(connectionKey, 3600, JSON.stringify({
      serverId: this.serverId,
      connectedAt: Date.now(),
      lastPing: Date.now()
    }));

    // Add to local connection map
    if (!this.connections.has(userId)) {
      this.connections.set(userId, new Set());
    }
    this.connections.get(userId).add(socket);

    // Set up heartbeat
    const heartbeatInterval = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.ping();
        this.updateLastPing(connectionKey);
      } else {
        this.handleDisconnection(socket, userId);
        clearInterval(heartbeatInterval);
      }
    }, 30000);

    socket.on('close', () => {
      this.handleDisconnection(socket, userId);
      clearInterval(heartbeatInterval);
    });
  }

  async sendToUser(userId, notification) {
    // Try local connections first
    const localConnections = this.connections.get(userId);
    if (localConnections && localConnections.size > 0) {
      const payload = JSON.stringify(notification);
      localConnections.forEach(socket => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(payload);
        }
      });
      return true;
    }

    // Check if user has connections on other servers
    const connectionKeys = await this.connectionPool.keys(`conn:${userId}:*`);
    if (connectionKeys.length > 0) {
      // Publish to Redis channel for other servers to handle
      await this.connectionPool.publish(`notifications:${userId}`, JSON.stringify(notification));
      return true;
    }

    return false; // User not connected
  }

  async handleDisconnection(socket, userId) {
    // Remove from local connections
    const userConnections = this.connections.get(userId);
    if (userConnections) {
      userConnections.delete(socket);
      if (userConnections.size === 0) {
        this.connections.delete(userId);
      }
    }

    // Remove from distributed cache
    const connectionKey = `conn:${userId}:${this.serverId}:${socket.id}`;
    await this.connectionPool.del(connectionKey);
  }
}
```

### 4.3 Intelligent Email Batching

```javascript
class EmailBatchingService {
  constructor() {
    this.batchWindows = new Map(); // userId -> batch window
    this.sendGridClient = new SendGridClient();
    this.maxBatchSize = 50;
    this.batchTimeouts = {
      high: 5 * 60 * 1000,      // 5 minutes
      medium: 15 * 60 * 1000,   // 15 minutes  
      low: 4 * 60 * 60 * 1000   // 4 hours
    };
  }

  async processNotification(notification) {
    const userId = notification.userId;
    const priority = notification.priority;

    // Check if user is currently active (no batching for active users)
    const isActive = await this.isUserActive(userId);
    if (isActive && priority !== 'low') {
      return this.sendImmediate(notification);
    }

    // Add to batch window
    const batchKey = `${userId}:${priority}`;
    if (!this.batchWindows.has(batchKey)) {
      this.createBatchWindow(batchKey, priority);
    }

    const batch = this.batchWindows.get(batchKey);
    batch.notifications.push(notification);

    // Send batch if it's full or contains high priority items
    if (batch.notifications.length >= this.maxBatchSize || 
        (priority === 'high' && batch.notifications.length >= 5)) {
      await this.sendBatch(batch);
      this.batchWindows.delete(batchKey);
    }
  }

  createBatchWindow(batchKey, priority) {
    const batch = {
      notifications: [],
      createdAt: Date.now(),
      priority: priority
    };

    this.batchWindows.set(batchKey, batch);

    // Set timeout to send batch
    setTimeout(async () => {
      if (this.batchWindows.has(batchKey)) {
        const currentBatch = this.batchWindows.get(batchKey);
        if (currentBatch.notifications.length > 0) {
          await this.sendBatch(currentBatch);
        }
        this.batchWindows.delete(batchKey);
      }
    }, this.batchTimeouts[priority]);
  }

  async sendBatch(batch) {
    if (batch.notifications.length === 1) {
      return this.sendImmediate(batch.notifications[0]);
    }

    const digestContent = this.createDigest(batch.notifications);
    const userPrefs = await this.getUserPreferences(batch.notifications[0].userId);

    const emailData = {
      to: userPrefs.email,
      templateId: this.selectDigestTemplate(batch.notifications),
      dynam