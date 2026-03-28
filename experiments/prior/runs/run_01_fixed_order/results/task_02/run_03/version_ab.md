# Notification System Design for 10M MAU Social App

## Executive Summary

This proposal outlines a notification system architecture capable of handling 10M monthly active users generating 22.5M notifications daily at peak, with a 4-engineer team over 6 months. The design prioritizes reliability, realistic scaling, and operational simplicity while making pragmatic technology choices that balance functionality with implementation complexity.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestration layer with rate limiting
- **Channel Handlers**: Specialized handlers for each delivery channel
- **Queue System**: Apache Kafka for durability with Redis for caching
- **User Preference Service**: Centralized preference management with caching
- **Analytics & Monitoring**: Delivery tracking and system health

### Technology Stack Rationale
- **Message Queue**: Apache Kafka (durability, throughput, handles 10M scale)
- **Primary Database**: PostgreSQL (team familiarity, ACID compliance for preferences)
- **Cache Layer**: Redis Cluster (preference caching, WebSocket scaling)
- **API Framework**: Go (performance, concurrency, team can learn effectively)
- **Infrastructure**: AWS managed services to reduce operational overhead

**Rationale for changes from Version A**: Kafka provides the durability and throughput needed for 10M users while remaining learnable for the team. Go offers better performance characteristics for high-throughput notification processing.

## 2. Realistic Scale Requirements & Capacity Planning

### 2.1 Volume Calculations
**Daily notification volume for 10M MAU social app:**
- Social apps average: 2.5 notifications per daily active user
- Daily active users (30% of MAU): 3M users
- **Peak daily volume: 22.5M notifications**
- **Peak rate: 400 notifications/second (during evening hours)**
- **Storage: 500GB/year for notification history**

### 2.2 Infrastructure Sizing
**Production Environment:**
- **Application servers**: 4 instances (8 cores, 32GB RAM each)
- **Kafka cluster**: 3 brokers (4 cores, 16GB RAM, 500GB SSD each)
- **PostgreSQL**: Primary + 2 read replicas (8 cores, 32GB RAM each)
- **Redis cluster**: 3 nodes (4 cores, 16GB RAM each)
- **Total monthly cost: $4,500-6,000**

**Rationale**: More realistic projections based on actual social app usage patterns, while maintaining sufficient headroom for growth.

## 3. Durable Message Queue Architecture

### 3.1 Kafka Topic Design
```yaml
topics:
  notifications-critical:
    partitions: 6
    replication-factor: 3
    retention: 24h
  notifications-high:
    partitions: 12
    replication-factor: 3
    retention: 12h
  notifications-normal:
    partitions: 24
    replication-factor: 3
    retention: 6h
  notifications-low:
    partitions: 12
    replication-factor: 3
    retention: 2h
```

### 3.2 Producer Implementation
```go
type NotificationProducer struct {
    producer sarama.SyncProducer
    topics   map[Priority]string
}

func (np *NotificationProducer) SendNotification(ctx context.Context, notif *Notification) error {
    topic := np.topics[notif.Priority]
    
    data, err := json.Marshal(notif)
    if err != nil {
        return fmt.Errorf("serialization failed: %w", err)
    }
    
    msg := &sarama.ProducerMessage{
        Topic:     topic,
        Key:       sarama.StringEncoder(notif.UserID),
        Value:     sarama.ByteEncoder(data),
        Timestamp: time.Now(),
    }
    
    partition, offset, err := np.producer.SendMessage(msg)
    if err != nil {
        return fmt.Errorf("kafka send failed: %w", err)
    }
    
    return nil
}
```

**Rationale**: Kafka provides the durability guarantees needed at this scale, while the implementation remains straightforward for the team to maintain.

## 4. Delivery Channels Implementation

### 4.1 Push Notifications with Proper Error Handling
**Technology**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)

```go
type PushNotificationHandler struct {
    fcmClient    *messaging.Client
    tokenService *DeviceTokenService
    badgeService *BadgeCountService
}

func (pnh *PushNotificationHandler) ProcessBatch(ctx context.Context, notifications []*Notification) error {
    userGroups := make(map[string][]*Notification)
    for _, notif := range notifications {
        userGroups[notif.UserID] = append(userGroups[notif.UserID], notif)
    }
    
    // Bulk load badge counts to avoid N+1 queries
    userIDs := make([]string, 0, len(userGroups))
    for userID := range userGroups {
        userIDs = append(userIDs, userID)
    }
    
    badgeCounts, err := pnh.badgeService.GetBadgeCountsBulk(ctx, userIDs)
    if err != nil {
        return fmt.Errorf("failed to load badge counts: %w", err)
    }
    
    // Process with controlled concurrency
    semaphore := make(chan struct{}, 10)
    var wg sync.WaitGroup
    
    for userID, userNotifications := range userGroups {
        wg.Add(1)
        go func(uid string, notifs []*Notification) {
            defer wg.Done()
            semaphore <- struct{}{}
            defer func() { <-semaphore }()
            
            pnh.sendToUser(ctx, uid, notifs, badgeCounts[uid])
        }(userID, userNotifications)
    }
    
    wg.Wait()
    return nil
}
```

**Capacity**: 300K push notifications/day peak
**Latency SLA**: <30 seconds for high priority, <5 minutes for normal

### 4.2 Email Notifications
**Technology**: SendGrid (99.9% deliverability, robust API)

**Implementation Strategy**:
- Batch processing for digest emails (daily/weekly summaries)
- Transactional emails for immediate actions
- Template management with personalization
- Bounce/spam handling with automatic list hygiene

**Volume**: 150K emails/day, 15K transactional emails/day

### 4.3 In-App Notifications with Redis Pub/Sub
```go
type WebSocketManager struct {
    connections sync.Map
    redis       *redis.ClusterClient
    maxConns    int
}

func (wsm *WebSocketManager) SendToUser(userID string, notification *Notification) error {
    data, err := json.Marshal(notification)
    if err != nil {
        return fmt.Errorf("marshal failed: %w", err)
    }
    
    // Publish to Redis for distribution across instances
    return wsm.redis.Publish(context.Background(), 
        fmt.Sprintf("notifications:%s", userID), string(data)).Err()
}
```

**Capacity**: 30K concurrent connections

### 4.4 SMS Notifications
**Technology**: Twilio (reliability + global reach)

**Usage**: Critical notifications only (security alerts, payment issues)
- Volume: 3K SMS/day maximum
- Cost optimization: Strict filtering and user opt-in required

## 5. High-Performance User Preference Management

### 5.1 Optimized Database Schema
```sql
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME DEFAULT '22:00:00',
    quiet_hours_end TIME DEFAULT '08:00:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    email_frequency VARCHAR(20) DEFAULT 'immediate',
    last_email_sent TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_category_preferences (
    user_id BIGINT,
    category VARCHAR(50),
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT false,
    sms_enabled BOOLEAN DEFAULT false,
    PRIMARY KEY (user_id, category)
);

CREATE INDEX idx_prefs_updated_at ON user_notification_preferences(updated_at);
CREATE INDEX idx_prefs_user_ids ON user_notification_preferences USING HASH(user_id);
```

### 5.2 Cached Preference Service
```go
type PreferenceService struct {
    cache *redis.ClusterClient
    db    *sql.DB
}

func (ps *PreferenceService) GetPreferences(ctx context.Context, userID string) (*UserPreferences, error) {
    // Try cache first
    cacheKey := fmt.Sprintf("prefs:%s", userID)
    cached, err := ps.cache.Get(ctx, cacheKey).Result()
    if err == nil {
        var prefs UserPreferences
        if json.Unmarshal([]byte(cached), &prefs) == nil {
            return &prefs, nil
        }
    }
    
    // Cache miss - load from database
    prefs, err := ps.loadFromDB(ctx, userID)
    if err != nil {
        return nil, fmt.Errorf("db load failed: %w", err)
    }
    
    // Warm cache asynchronously
    go ps.warmCache(userID, prefs)
    
    return prefs, nil
}

func (ps *PreferenceService) BulkLoadPreferences(ctx context.Context, userIDs []string) (map[string]*UserPreferences, error) {
    // Use Redis pipeline for bulk operations
    pipe := ps.cache.Pipeline()
    
    var cmds []*redis.StringCmd
    for _, userID := range userIDs {
        cacheKey := fmt.Sprintf("prefs:%s", userID)
        cmds = append(cmds, pipe.Get(ctx, cacheKey))
    }
    
    _, err := pipe.Exec(ctx)
    result := make(map[string]*UserPreferences)
    var missedUsers []string
    
    for i, cmd := range cmds {
        val, err := cmd.Result()
        if err == redis.Nil {
            missedUsers = append(missedUsers, userIDs[i])
            continue
        }
        
        var prefs UserPreferences
        if json.Unmarshal([]byte(val), &prefs) == nil {
            result[userIDs[i]] = &prefs
        }
    }
    
    // Load cache misses from database
    if len(missedUsers) > 0 {
        dbPrefs, err := ps.bulkLoadFromDB(ctx, missedUsers)
        if err != nil {
            return nil, fmt.Errorf("bulk db load failed: %w", err)
        }
        
        for userID, prefs := range dbPrefs {
            result[userID] = prefs
            go ps.warmCache(userID, prefs)
        }
    }
    
    return result, nil
}
```

## 6. Priority and Batching Logic

### 6.1 Priority Levels
```go
type Priority int

const (
    CRITICAL Priority = iota // Security, payments - immediate delivery
    HIGH                     // Direct messages, mentions - <1 minute  
    NORMAL                   // Likes, follows - <15 minutes
    LOW                      // Digest, recommendations - batched processing
)
```

### 6.2 Kafka Consumer with Batching
```go
type NotificationConsumer struct {
    consumer      sarama.ConsumerGroup
    batchSize     int
    batchTimeout  time.Duration
    handlers      map[string]ChannelHandler
}

func (nc *NotificationConsumer) processBatch(notifications []*Notification) error {
    // Group by channel for efficient processing
    channelGroups := make(map[string][]*Notification)
    for _, notif := range notifications {
        for _, channel := range notif.Channels {
            channelGroups[channel] = append(channelGroups[channel], notif)
        }
    }
    
    var wg sync.WaitGroup
    for channel, channelNotifs := range channelGroups {
        if handler, exists := nc.handlers[channel]; exists {
            wg.Add(1)
            go func(ch string, notifs []*Notification) {
                defer wg.Done()
                handler.ProcessBatch(context.Background(), notifs)
            }(channel, channelNotifs)
        }
    }
    
    wg.Wait()
    return nil
}
```

## 7. Failure Handling & Reliability

### 7.1 Circuit Breaker Implementation
```go
type CircuitBreaker struct {
    failureThreshold int
    timeout          time.Duration
    failureCount     int
    lastFailureTime  time.Time
    state           string // CLOSED, OPEN, HALF_OPEN
    mutex           sync.RWMutex
}

func (cb *CircuitBreaker) Call(operation func() error) error {
    cb.mutex.RLock()
    state := cb.state
    cb.mutex.RUnlock()
    
    if state == "OPEN" {
        if time.Since(cb.lastFailureTime) > cb.timeout {
            cb.setState("HALF_OPEN")
        } else {
            return fmt.Errorf("circuit breaker is OPEN")
        }
    }
    
    err := operation()
    if err != nil {
        cb.onFailure()
        return err
    }
    
    cb.onSuccess()
    return nil
}
```

### 7.2 Dead Letter Queue Processing
- Failed notifications after 3 retries → Kafka DLQ topic
- Separate consumer for DLQ with exponential backoff
- Manual review dashboard for persistent failures
- Automatic retry after external service recovery

## 8. Infrastructure Choices & Scaling

### 8.1 Service Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   API Gateway   │────│ Notification API │────│  Preference DB  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                       ┌────────┴────────┐
                       │ Kafka Cluster   │
                       └────────┬────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
┌───────▼──────┐    ┌───────────▼────┐    ┌─────────────▼──┐
│ Push Handler │    │ Email Handler  │    │ SMS Handler    │
└──────────────┘    └────────────────┘    └────────────────┘
```

### 8.2 Scaling Strategy
**Phase 1 (Months 1-3)**: Single region, managed services
- 2 application servers (8 cores, 32GB RAM each)
- 3-node Kafka cluster (managed MSK)
- 1 PostgreSQL instance with 1 read replica
- 3-node Redis cluster

**Phase 2 (Months 4-6)**: Horizontal scaling
- Load balancer + 4 application servers
- Scale Kafka partitions
- Additional PostgreSQL read replicas

**Capacity Planning**:
- Peak load: 400 notifications/second
- Storage: 500GB/year for notification history
- Queue depth: 10K messages maximum

## 9. Implementation Timeline (6 Months)

### Month 1-2: Foundation
- **Week 1-2**: Core notification service and Kafka setup
- **Week 3-4**: Push notification handler with FCM integration
- **Week 5-6**: User preferences with Redis caching
- **Week 7-8**: Priority queues and basic batching

### Month 3-4: Channel Expansion
- **Week 9-10**: Email notification handler with SendGrid
- **Week 11-12**: SMS notification handler (Twilio)
- **Week 13-14**: WebSocket implementation for in-app notifications
- **Week 15-16**: Advanced preference management and UI

### Month