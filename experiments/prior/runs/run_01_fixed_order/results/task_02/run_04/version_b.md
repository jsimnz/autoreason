# Revised Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a scalable notification system for a social app with 10M MAU, designed for delivery within 12 months by 6 backend engineers. The system prioritizes reliability and operational simplicity while acknowledging the significant technical complexity required to handle 10M users. Key design decisions favor proven patterns and include proper failure handling, realistic resource planning, and phased scaling approaches.

## 1. System Architecture Overview

### Core Components
- **Notification Service API** - Event ingestion with authentication
- **Channel Processors** - Dedicated services per delivery channel
- **Preference Service** - Cached user settings with database persistence
- **Queue System** - Multi-tier processing with Redis Cluster
- **WebSocket Manager** - Connection pooling for real-time delivery
- **Analytics & Monitoring** - Comprehensive observability

### Technology Stack
- **Primary Database**: PostgreSQL cluster with read replicas
- **Queue System**: Redis Cluster with separate instances for queues and cache
- **Caching**: Dedicated Redis instance for preferences
- **Message Bus**: Redis Streams for internal service communication
- **WebSocket**: Socket.io with Redis adapter for clustering
- **External Services**: 
  - Push: Firebase Cloud Messaging (FCM) Premium + Apple Push Notification Service (APNs)
  - Email: SendGrid Pro
  - SMS: Twilio with multiple provider fallback

**Problem Fixed**: Single point of failure eliminated by separating queue and cache Redis instances.

## 2. Delivery Channels Implementation

### 2.1 Push Notifications

**Problem Fixed**: FCM rate limiting and scaling issues addressed with premium tier and proper batching.

**Technology**: FCM Premium (500 requests/minute per project) + APNs with multiple app instances for load distribution

**Scaling Strategy**:
- 5 separate FCM projects for load distribution (2,500 requests/minute total)
- Device token sharding across projects using consistent hashing
- APNs connection pooling with 10 concurrent connections

**Implementation**:
```javascript
// Push notification processor with proper batching
class PushNotificationProcessor {
  constructor() {
    this.fcmClients = this.initializeFCMClients(5); // 5 projects
    this.batchSize = 500; // FCM limit
    this.rateLimiter = new TokenBucket(2500, 60); // 2500/minute
  }

  async processBatch(notifications) {
    const deviceGroups = this.shardByProject(notifications);
    const results = await Promise.allSettled(
      deviceGroups.map(group => this.sendToFCM(group))
    );
    return this.handleResults(results);
  }

  shardByProject(notifications) {
    return notifications.reduce((groups, notification) => {
      const projectIndex = this.getProjectIndex(notification.userId);
      groups[projectIndex] = groups[projectIndex] || [];
      groups[projectIndex].push(notification);
      return groups;
    }, {});
  }
}
```

**Cost Impact**: FCM Premium: ~$1,500/month, APNs: Free

### 2.2 In-App Notifications with WebSocket Management

**Problem Fixed**: WebSocket architecture fully specified with connection management and routing.

**Architecture**:
```javascript
// WebSocket connection manager
class WebSocketManager {
  constructor() {
    this.io = require('socket.io')(server, {
      adapter: require('socket.io-redis')({
        host: 'redis-websocket-cluster',
        port: 6379
      })
    });
    this.connectionMap = new Map(); // userId -> socketId mapping
  }

  async routeNotification(userId, notification) {
    // Check if user is connected to this server
    const localSocket = this.connectionMap.get(userId);
    if (localSocket) {
      localSocket.emit('notification', notification);
      return true;
    }
    
    // Broadcast to all servers via Redis adapter
    this.io.to(`user_${userId}`).emit('notification', notification);
    return false; // Don't know if delivered
  }

  handleConnection(socket) {
    const userId = this.authenticateSocket(socket);
    if (!userId) {
      socket.disconnect();
      return;
    }
    
    socket.join(`user_${userId}`);
    this.connectionMap.set(userId, socket);
    
    socket.on('disconnect', () => {
      this.connectionMap.delete(userId);
    });
  }
}
```

**Database Schema**:
```sql
-- Partitioned by month for efficient cleanup
CREATE TABLE in_app_notifications (
  id BIGSERIAL,
  user_id INTEGER NOT NULL,
  type VARCHAR(50) NOT NULL,
  title VARCHAR(255) NOT NULL,
  content TEXT,
  data JSONB,
  read_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE in_app_notifications_2024_01 PARTITION OF in_app_notifications
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Index for user queries
CREATE INDEX idx_user_notifications ON in_app_notifications_2024_01 (user_id, created_at DESC);
```

### 2.3 Email and SMS with Proper Error Handling

**Problem Fixed**: External service dependencies properly handled with different retry strategies per provider.

**Email Implementation**:
```javascript
class EmailProcessor {
  constructor() {
    this.sendgrid = require('@sendgrid/mail');
    this.sendgrid.setApiKey(process.env.SENDGRID_API_KEY);
    this.rateLimiter = new TokenBucket(1000, 60); // SendGrid limit
  }

  async processBatch(emailNotifications) {
    const batches = this.chunk(emailNotifications, 1000);
    const results = [];
    
    for (const batch of batches) {
      await this.rateLimiter.consume(1);
      try {
        const result = await this.sendgrid.send(batch);
        results.push({ success: true, batch, result });
      } catch (error) {
        results.push({ success: false, batch, error });
        await this.handleSendGridError(error, batch);
      }
    }
    return results;
  }

  async handleSendGridError(error, batch) {
    if (error.code === 429) { // Rate limited
      await this.requeueWithDelay(batch, 60000); // 1 minute delay
    } else if (error.code >= 500) { // Server error
      await this.requeueWithDelay(batch, 5000); // 5 second delay
    }
    // 400 errors are permanent failures, log and drop
  }
}
```

## 3. Queue System and Batching Logic

**Problem Fixed**: Queue batching logic completely redesigned to work with Redis capabilities.

### 3.1 Queue Architecture
```javascript
// Time-based batching using Redis Streams
class NotificationBatcher {
  constructor() {
    this.redis = new Redis.Cluster([
      { host: 'redis-queue-1', port: 6379 },
      { host: 'redis-queue-2', port: 6379 },
      { host: 'redis-queue-3', port: 6379 }
    ]);
    this.batchIntervals = {
      critical: 0,      // No batching
      high: 30000,      // 30 seconds
      medium: 300000,   // 5 minutes
      low: 1800000      // 30 minutes
    };
    this.startBatchProcessors();
  }

  async addNotification(notification, priority) {
    if (priority === 'critical') {
      return this.processImmediately(notification);
    }
    
    // Add to Redis Stream for time-based batching
    await this.redis.xadd(
      `batch:${priority}`,
      '*',
      'notification', JSON.stringify(notification),
      'timestamp', Date.now()
    );
  }

  startBatchProcessors() {
    Object.entries(this.batchIntervals).forEach(([priority, interval]) => {
      if (interval > 0) {
        setInterval(() => this.processBatch(priority), interval);
      }
    });
  }

  async processBatch(priority) {
    const cutoffTime = Date.now() - this.batchIntervals[priority];
    
    // Read all notifications older than cutoff
    const stream = await this.redis.xrange(
      `batch:${priority}`,
      '-',
      cutoffTime
    );
    
    if (stream.length === 0) return;
    
    const notifications = stream.map(entry => 
      JSON.parse(entry[1].notification)
    );
    
    // Process the batch
    await this.sendToBatchProcessor(priority, notifications);
    
    // Remove processed items
    const lastId = stream[stream.length - 1][0];
    await this.redis.xtrim(`batch:${priority}`, 'MINID', lastId);
  }
}
```

## 4. User Preference Management

**Problem Fixed**: Database query load reduced with proper caching strategy and simplified preference logic.

### 4.1 Preference Service
```javascript
class PreferenceService {
  constructor() {
    this.cacheRedis = new Redis({ host: 'redis-cache' });
    this.db = new PostgreSQL(/* connection config */);
    this.cacheTTL = 3600; // 1 hour
  }

  async getUserPreferences(userId) {
    // Try cache first
    const cached = await this.cacheRedis.get(`prefs:${userId}`);
    if (cached) {
      return JSON.parse(cached);
    }

    // Fallback to database
    const prefs = await this.db.query(
      'SELECT preferences FROM user_notification_preferences WHERE user_id = $1',
      [userId]
    );

    const preferences = prefs.rows[0]?.preferences || this.getDefaultPreferences();
    
    // Cache for future use
    await this.cacheRedis.setex(
      `prefs:${userId}`,
      this.cacheTTL,
      JSON.stringify(preferences)
    );

    return preferences;
  }

  // Simplified preference structure
  getDefaultPreferences() {
    return {
      channels: {
        push: true,
        email: true,
        sms: false,
        in_app: true
      },
      categories: {
        social: { push: true, email: false },
        security: { push: true, email: true, sms: true },
        marketing: { push: false, email: true }
      },
      quiet_hours: {
        enabled: false,
        start: "22:00",
        end: "08:00",
        timezone: "UTC"
      },
      frequency_limits: {
        push_daily: 20,
        email_daily: 5,
        sms_daily: 2
      }
    };
  }
}
```

### 4.2 Database Schema
```sql
-- Simplified preference storage
CREATE TABLE user_notification_preferences (
  user_id INTEGER PRIMARY KEY,
  preferences JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for preference queries (though mostly cached)
CREATE INDEX idx_user_prefs_updated ON user_notification_preferences (updated_at DESC);

-- Frequency tracking table
CREATE TABLE notification_frequency_tracking (
  user_id INTEGER,
  channel VARCHAR(20),
  date DATE,
  count INTEGER DEFAULT 0,
  PRIMARY KEY (user_id, channel, date)
);
```

## 5. Infrastructure and Resource Planning

**Problem Fixed**: Realistic resource requirements calculated with proper cost estimates.

### 5.1 Compute Resources

**Phase 1** (0-2M MAU):
- 4x API servers (4 vCPU, 8GB RAM) - $800/month
- 2x WebSocket servers (2 vCPU, 4GB RAM) - $200/month
- 3x Queue processors (4 vCPU, 8GB RAM) - $600/month
- PostgreSQL cluster (16 vCPU, 64GB RAM) - $1,200/month
- Redis cluster (3 nodes, 8 vCPU, 32GB RAM total) - $900/month

**Phase 2** (2M-10M MAU):
- 12x API servers - $2,400/month
- 6x WebSocket servers - $600/month
- 10x Queue processors - $2,000/month
- PostgreSQL cluster + 3 read replicas - $2,400/month
- Redis cluster (6 nodes) - $1,800/month

### 5.2 Realistic Cost Estimates

**External Services**:
- FCM Premium (5 projects): $1,500/month
- SendGrid Pro (2M emails/month): $800/month
- Twilio SMS (100k messages/month): $750/month

**Infrastructure** (Phase 2):
- Compute: $9,200/month
- Storage: $400/month
- Bandwidth: $300/month
- Monitoring/Logging: $500/month

**Total Monthly Cost at 10M MAU**: $13,450/month

**Problem Fixed**: Cost estimates include all necessary components and scale properly.

### 5.3 Memory Calculations

**Redis Cache Requirements**:
- User preferences: 10M users × 2KB avg = 20GB
- WebSocket session data: 500K concurrent × 1KB = 500MB
- Frequency tracking: 10M users × 100 bytes = 1GB
- **Total Cache**: ~25GB (use 32GB with overhead)

**Redis Queue Requirements**:
- Queue depth: 100K notifications × 2KB avg = 200MB
- Processing buffers: 500MB
- **Total Queue**: ~1GB (use 4GB for bursts)

**Problem Fixed**: Actual memory requirements calculated and provisioned.

## 6. Authentication and Security

**Problem Fixed**: Security implementation specified.

### 6.1 API Authentication
```javascript
// JWT-based service authentication
class NotificationAPI {
  constructor() {
    this.jwtSecret = process.env.JWT_SECRET;
    this.rateLimiter = new Map(); // IP-based rate limiting
  }

  async authenticate(req, res, next) {
    const token = req.headers.authorization?.split(' ')[1];
    if (!token) {
      return res.status(401).json({ error: 'No token provided' });
    }

    try {
      const decoded = jwt.verify(token, this.jwtSecret);
      req.serviceId = decoded.serviceId;
      req.permissions = decoded.permissions;
      next();
    } catch (error) {
      return res.status(401).json({ error: 'Invalid token' });
    }
  }

  async rateLimit(req, res, next) {
    const key = req.ip;
    const now = Date.now();
    const windowMs = 60000; // 1 minute
    const maxRequests = 1000;

    const requests = this.rateLimiter.get(key) || [];
    const validRequests = requests.filter(time => now - time < windowMs);
    
    if (validRequests.length >= maxRequests) {
      return res.status(429).json({ error: 'Rate limit exceeded' });
    }

    validRequests.push(now);
    this.rateLimiter.set(key, validRequests);
    next();
  }
}
```

### 6.2 Device Token Validation
```javascript
async function validateDeviceToken(token, platform) {
  // Check token format
  if (platform === 'ios' && !token.match(/^[a-f0-9]{64}$/)) {
    throw new Error('Invalid iOS device token format');
  }
  
  if (platform === 'android' && token.length < 140) {
    throw new Error('Invalid Android device token format');
  }

  // Check against blacklist
  const isBlacklisted = await redis.sismember('blacklisted_tokens', token);
  if (isBlacklisted) {
    throw new Error('Device token is blacklisted');
  }

  return true;
}
```

## 7. Failure Handling and Monitoring

**Problem Fixed**: