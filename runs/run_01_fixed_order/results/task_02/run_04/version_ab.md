# Notification System Design for Social App (10M MAU)

## Executive Summary

This proposal outlines a scalable notification system for a social app with 10M MAU, designed for delivery within 6 months by 4 backend engineers. The system prioritizes reliability, user experience, and operational simplicity while managing infrastructure costs. Key design decisions favor proven technologies over cutting-edge solutions to ensure delivery within timeline and resource constraints.

## 1. System Architecture Overview

### Core Components
- **Notification Service API** - Event ingestion with authentication and routing
- **Channel Processors** - Delivery-specific logic for each channel
- **Preference Engine** - User settings and filtering with proper caching
- **Queue System** - Multi-tier processing with Redis
- **WebSocket Manager** - Connection pooling for real-time delivery
- **Analytics & Monitoring** - Delivery tracking and system health

### Technology Stack
- **Primary Database**: PostgreSQL cluster with read replicas (leveraging existing team expertise)
- **Queue System**: Redis Cluster for queues + separate Redis for cache
- **Caching**: Dedicated Redis instance for preferences and WebSocket sessions
- **WebSocket**: Socket.io with Redis adapter for clustering
- **External Services**: 
  - Push: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
  - Email: SendGrid Pro
  - SMS: Twilio

**Rationale**: Leveraging existing team PostgreSQL expertise reduces learning curve. Separate Redis instances eliminate single points of failure while maintaining operational simplicity.

## 2. Delivery Channels Implementation

### 2.1 Push Notifications
**Technology**: FCM + APNs with proper rate limiting and batching

**Scaling Strategy**:
- FCM batching: 1000 notifications per API call
- Connection pooling for APNs with 5 concurrent connections
- Device token sharding using consistent hashing

**Implementation**:
```javascript
class PushNotificationProcessor {
  constructor() {
    this.fcmClient = this.initializeFCM();
    this.apnsProvider = this.initializeAPNS();
    this.batchSize = 1000; // FCM limit
    this.rateLimiter = new TokenBucket(1000, 60); // Conservative rate
  }

  async processBatch(notifications) {
    const { androidNotifications, iosNotifications } = this.groupByPlatform(notifications);
    
    const results = await Promise.allSettled([
      this.sendToFCM(androidNotifications),
      this.sendToAPNS(iosNotifications)
    ]);
    
    return this.handleResults(results);
  }

  async sendToFCM(notifications) {
    const batches = this.chunk(notifications, this.batchSize);
    const results = [];
    
    for (const batch of batches) {
      await this.rateLimiter.consume(1);
      try {
        const response = await this.fcmClient.sendMulticast({
          tokens: batch.map(n => n.deviceToken),
          notification: batch[0].payload // Assuming same payload per batch
        });
        results.push({ success: true, response });
      } catch (error) {
        results.push({ success: false, error, batch });
        await this.handleFCMError(error, batch);
      }
    }
    return results;
  }
}
```

**Token Management**:
- Remove invalid tokens after 3 consecutive failures
- Maintain token blacklist in Redis
- Retry logic: 3 attempts with exponential backoff (1s, 5s, 25s)

### 2.2 In-App Notifications with WebSocket Management
**Storage**: PostgreSQL partitioned table with 90-day retention

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

-- Monthly partitions with automated cleanup
CREATE TABLE in_app_notifications_2024_01 PARTITION OF in_app_notifications
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE INDEX idx_user_notifications ON in_app_notifications_2024_01 (user_id, created_at DESC);
```

**WebSocket Architecture**:
```javascript
class WebSocketManager {
  constructor() {
    this.io = require('socket.io')(server, {
      adapter: require('socket.io-redis')({
        host: 'redis-websocket',
        port: 6379
      })
    });
    this.connectionMap = new Map(); // userId -> socketId mapping
  }

  async routeNotification(userId, notification) {
    const localSocket = this.connectionMap.get(userId);
    if (localSocket) {
      localSocket.emit('notification', notification);
      return true;
    }
    
    // Broadcast to all servers via Redis adapter
    this.io.to(`user_${userId}`).emit('notification', notification);
    return false;
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

### 2.3 Email and SMS
**Email**: SendGrid with template system and proper error handling
**SMS**: Twilio with cost controls (5 SMS per user per day)

**Error Handling Strategy**:
```javascript
class EmailProcessor {
  async processBatch(emailNotifications) {
    const batches = this.chunk(emailNotifications, 1000);
    
    for (const batch of batches) {
      try {
        await this.sendgrid.send(batch);
      } catch (error) {
        if (error.code === 429) { // Rate limited
          await this.requeueWithDelay(batch, 60000);
        } else if (error.code >= 500) { // Server error
          await this.requeueWithDelay(batch, 5000);
        }
        // 400 errors are permanent failures - log and drop
      }
    }
  }
}
```

## 3. Priority and Batching Logic

### 3.1 Priority Levels
1. **Critical** (0-30 seconds): Security alerts, account issues - no batching
2. **High** (0-5 minutes): Direct messages, mentions, friend requests  
3. **Medium** (5-30 minutes): Likes, comments, group activity
4. **Low** (30 minutes - 2 hours): Weekly digests, recommendations

### 3.2 Redis-Based Batching System
**Queue Structure**: Separate Redis lists per priority level with time-based processing

```javascript
class NotificationBatcher {
  constructor() {
    this.redis = new Redis.Cluster([
      { host: 'redis-queue-1', port: 6379 },
      { host: 'redis-queue-2', port: 6379 }
    ]);
    this.batchIntervals = {
      critical: 0,      // Process immediately
      high: 30000,      // 30 seconds
      medium: 300000,   // 5 minutes  
      low: 1800000      // 30 minutes
    };
    this.batchSizes = {
      high: 100,
      medium: 500,
      low: 2000
    };
  }

  async addNotification(notification, priority) {
    if (priority === 'critical') {
      return this.processImmediately(notification);
    }
    
    await this.redis.lpush(`notifications:${priority}`, JSON.stringify({
      ...notification,
      timestamp: Date.now()
    }));
  }

  async processBatch(priority) {
    const batchSize = this.batchSizes[priority];
    const notifications = await this.redis.lrange(`notifications:${priority}`, 0, batchSize - 1);
    
    if (notifications.length === 0) return;
    
    // Remove processed items
    await this.redis.ltrim(`notifications:${priority}`, notifications.length, -1);
    
    // Process the batch
    const parsedNotifications = notifications.map(n => JSON.parse(n));
    await this.sendToBatchProcessor(priority, parsedNotifications);
  }
}
```

**Batch Processing Rules**:
- Critical: Process immediately, no batching
- High: Every 30 seconds OR 100 notifications
- Medium: Every 5 minutes OR 500 notifications
- Low: Every 30 minutes OR 2000 notifications

## 4. User Preference Management

### 4.1 Simplified Preference Service
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
    await this.cacheRedis.setex(`prefs:${userId}`, this.cacheTTL, JSON.stringify(preferences));
    return preferences;
  }
}
```

### 4.2 Database Schema
```sql
CREATE TABLE user_notification_preferences (
  user_id INTEGER PRIMARY KEY,
  preferences JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Frequency tracking for rate limiting
CREATE TABLE notification_frequency_tracking (
  user_id INTEGER,
  channel VARCHAR(20),
  date DATE,
  count INTEGER DEFAULT 0,
  PRIMARY KEY (user_id, channel, date)
);
```

**Preference Structure**:
```json
{
  "channel_preferences": {
    "push": true,
    "email": true,
    "sms": false,
    "in_app": true
  },
  "category_preferences": {
    "social_interactions": {"push": true, "email": false},
    "security": {"push": true, "email": true, "sms": true},
    "marketing": {"push": false, "email": true}
  },
  "quiet_hours": {
    "enabled": true,
    "start": "22:00",
    "end": "08:00",
    "timezone": "America/New_York"
  },
  "frequency_limits": {
    "push_daily": 20,
    "email_daily": 5,
    "sms_daily": 2
  }
}
```

## 5. Infrastructure Choices and Scaling

### 5.1 Realistic Resource Requirements
**Initial Setup** (handles 2-3M MAU):
- 3x API servers (4 vCPU, 8GB RAM) - $600/month
- 2x WebSocket servers (2 vCPU, 4GB RAM) - $200/month  
- 2x Queue processors (2 vCPU, 4GB RAM) - $200/month
- PostgreSQL cluster (8 vCPU, 32GB RAM) - $800/month
- Redis cluster (2 instances: 4 vCPU, 16GB RAM each) - $800/month

**Scaling to 10M MAU**:
- 8x API servers - $1,600/month
- 4x WebSocket servers - $400/month
- 6x Queue processors - $600/month
- PostgreSQL + 2 read replicas - $1,600/month
- Redis cluster (4 instances) - $1,600/month

### 5.2 Cost Optimization
**External Services**:
- Push Notifications: Free (FCM/APNs)
- SendGrid Pro: ~$600/month (1M emails)
- Twilio SMS: ~$750/month (50k messages)

**Infrastructure** (at 10M MAU):
- Compute: $6,200/month
- Storage: $200/month
- Bandwidth: $200/month

**Total Monthly Cost**: $7,950/month at full scale

**Justification**: More realistic than Version A's $3,300 estimate, accounts for proper redundancy and scaling requirements while remaining cost-effective.

### 5.3 Performance Targets
- **Throughput**: 5,000 notifications/second peak (realistic for 4-engineer team)
- **Latency**: 
  - Critical: <30 seconds
  - High: <5 minutes
  - Medium/Low: Best effort
- **Reliability**: 99.5% delivery success rate (achievable target)

## 6. Failure Handling and Reliability

### 6.1 Circuit Breaker and Retry Logic
```javascript
class CircuitBreaker {
  constructor(failureThreshold = 10, resetTimeout = 60000) {
    this.failureThreshold = failureThreshold;
    this.resetTimeout = resetTimeout;
    this.state = 'CLOSED'; // CLOSED, OPEN, HALF_OPEN
    this.failureCount = 0;
    this.lastFailureTime = null;
  }

  async execute(operation) {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastFailureTime > this.resetTimeout) {
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

  onSuccess() {
    this.failureCount = 0;
    this.state = 'CLOSED';
  }

  onFailure() {
    this.failureCount++;
    this.lastFailureTime = Date.now();
    if (this.failureCount >= this.failureThreshold) {
      this.state = 'OPEN';
    }
  }
}
```

### 6.2 Dead Letter Queue
```javascript
async function processWithRetry(notification, attempt = 0) {
  const retryDelays = [1000, 5000, 25000]; // 1s, 5s, 25s
  
  try {
    return await deliverNotification(notification);
  } catch (error) {
    if (attempt < retryDelays.length && isRetryableError(error)) {
      await delay(retryDelays[attempt]);
      return processWithRetry(notification, attempt + 1);
    }
    
    // Send to dead letter queue
    await redis.lpush('dead_letter_queue', JSON.stringify({
      notification,
      error: error.message,
      attempts: attempt + 1,
      timestamp: Date.now()
    }));
    
    throw error;
  }
}
```

### 6.3 Authentication and Security
```javascript
// JWT-based service authentication
async function authenticate(req, res, next) {
  const token = req.headers.authorization?.split(' ')[1];
  if (!token) {
    return res.status(401).json({ error: 'No token provided' });
  }

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.serviceId = decoded.serviceId;
    next();
  } catch (error) {
    return res.status(401).json({ error: 'Invalid token' });
  }
}

// Rate limiting per service
const rateLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 1000, // requests per window
  keyGenerator: (req) => req.serviceId
});
```