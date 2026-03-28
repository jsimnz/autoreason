# Notification System Design for 10M MAU Social App (REVISED)

## Executive Summary

This proposal outlines a notification system architecture capable of handling 10M monthly active users generating 75M notifications daily at peak, with a 4-engineer team over 6 months. The design prioritizes data durability, realistic scaling, and operational simplicity while acknowledging the substantial infrastructure requirements for this scale.

## 1. System Architecture Overview

### Core Components
- **Notification API**: Rate-limited ingestion layer with authentication
- **Message Broker**: Durable message queuing with Apache Kafka
- **Channel Workers**: Specialized processors for each delivery channel  
- **Preference Cache**: High-performance preference lookup layer
- **Monitoring Stack**: Comprehensive observability and alerting

### Technology Stack Rationale
- **Message Queue**: Apache Kafka (durability, throughput, team can learn)
- **Primary Database**: PostgreSQL (ACID compliance, complex queries)
- **Cache Layer**: Redis Cluster (preference caching, session storage)
- **API Framework**: Go (performance, concurrency, static typing)
- **Infrastructure**: AWS managed services with multi-AZ deployment

**Problem Fixed**: #2 (Redis as primary queue), #1 (realistic technology choices)

## 2. Realistic Scale Requirements & Capacity Planning

### 2.1 Actual Volume Calculations
**Daily notification volume for 10M MAU social app:**
- Conservative estimate: 7.5 notifications per daily active user
- Daily active users (30% of MAU): 3M users  
- **Peak daily volume: 75M notifications**
- **Peak rate: 1,200 notifications/second (during evening hours)**
- **Storage: 2TB/year for notification history and user data**

**Problem Fixed**: #1 (fundamentally broken scaling math)

### 2.2 Infrastructure Sizing (Realistic)
**Production Environment:**
- **Application servers**: 8 instances (8 cores, 32GB RAM each)
- **Kafka cluster**: 6 brokers (4 cores, 16GB RAM, 1TB SSD each)  
- **PostgreSQL**: Primary + 3 read replicas (16 cores, 64GB RAM each)
- **Redis cluster**: 6 nodes (8 cores, 32GB RAM each)
- **Total monthly cost: $12,000-15,000**

**Problem Fixed**: #1 (unrealistic infrastructure sizing), #9 (fictional cost estimates)

## 3. Durable Message Queue Architecture

### 3.1 Kafka Topic Design
```yaml
topics:
  notifications-critical:
    partitions: 12
    replication-factor: 3
    retention: 24h
  notifications-high:
    partitions: 24  
    replication-factor: 3
    retention: 12h
  notifications-normal:
    partitions: 48
    replication-factor: 3
    retention: 6h
  notifications-low:
    partitions: 24
    replication-factor: 3
    retention: 2h
```

### 3.2 Producer Implementation with Proper Error Handling
```go
type NotificationProducer struct {
    producer sarama.SyncProducer
    topics   map[Priority]string
}

func (np *NotificationProducer) SendNotification(ctx context.Context, notif *Notification) error {
    topic := np.topics[notif.Priority]
    
    // Serialize notification
    data, err := json.Marshal(notif)
    if err != nil {
        return fmt.Errorf("serialization failed: %w", err)
    }
    
    msg := &sarama.ProducerMessage{
        Topic:     topic,
        Key:       sarama.StringEncoder(notif.UserID),
        Value:     sarama.ByteEncoder(data),
        Headers:   []sarama.RecordHeader{{Key: []byte("priority"), Value: []byte(notif.Priority.String())}},
        Timestamp: time.Now(),
    }
    
    partition, offset, err := np.producer.SendMessage(msg)
    if err != nil {
        return fmt.Errorf("kafka send failed: %w", err)
    }
    
    // Log successful enqueue
    log.Info("notification enqueued", 
        "partition", partition, "offset", offset, "user_id", notif.UserID)
    return nil
}
```

**Problem Fixed**: #2 (Redis durability issues), #6 (race conditions in batching)

## 4. High-Performance Preference Management

### 4.1 Cached Preference Architecture
```go
type PreferenceService struct {
    cache      *redis.ClusterClient
    db         *sql.DB
    cacheExpiry time.Duration
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
    if err != nil && err != redis.Nil {
        return nil, fmt.Errorf("pipeline exec failed: %w", err)
    }
    
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
            // Warm cache asynchronously
            go ps.warmCache(userID, prefs)
        }
    }
    
    return result, nil
}
```

### 4.2 Optimized Database Schema
```sql
-- Separate table for hot preference data
CREATE TABLE user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    quiet_hours_start TIME DEFAULT '22:00:00',
    quiet_hours_end TIME DEFAULT '08:00:00',
    timezone VARCHAR(50) DEFAULT 'UTC',
    email_frequency VARCHAR(20) DEFAULT 'immediate', -- immediate, daily, weekly
    last_email_sent TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Separate table for category preferences (normalized)
CREATE TABLE user_category_preferences (
    user_id BIGINT,
    category VARCHAR(50),
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT false,
    sms_enabled BOOLEAN DEFAULT false,
    PRIMARY KEY (user_id, category),
    FOREIGN KEY (user_id) REFERENCES user_notification_preferences(user_id)
);

-- Indexes for performance
CREATE INDEX idx_prefs_updated_at ON user_notification_preferences(updated_at);
CREATE INDEX idx_category_prefs_user_id ON user_category_preferences(user_id);

-- Bulk load query optimization
CREATE INDEX idx_prefs_user_ids ON user_notification_preferences USING HASH(user_id);
```

**Problem Fixed**: #3 (PostgreSQL preference scaling), #11 (unworkable preference model)

## 5. Channel Implementation with Proper Error Handling

### 5.1 Push Notification Handler with Realistic FCM Integration
```go
type PushNotificationHandler struct {
    fcmClient    *messaging.Client
    apnsClient   *apns2.Client
    tokenService *DeviceTokenService
    badgeService *BadgeCountService
}

func (pnh *PushNotificationHandler) ProcessBatch(ctx context.Context, notifications []*Notification) error {
    // Group by user for badge count optimization
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
    
    // Process in parallel with rate limiting
    semaphore := make(chan struct{}, 10) // Max 10 concurrent FCM calls
    var wg sync.WaitGroup
    var mu sync.Mutex
    var errors []error
    
    for userID, userNotifications := range userGroups {
        wg.Add(1)
        go func(uid string, notifs []*Notification) {
            defer wg.Done()
            semaphore <- struct{}{}
            defer func() { <-semaphore }()
            
            if err := pnh.sendToUser(ctx, uid, notifs, badgeCounts[uid]); err != nil {
                mu.Lock()
                errors = append(errors, fmt.Errorf("user %s: %w", uid, err))
                mu.Unlock()
            }
        }(userID, userNotifications)
    }
    
    wg.Wait()
    
    if len(errors) > 0 {
        return fmt.Errorf("batch processing had %d errors: %v", len(errors), errors[0])
    }
    
    return nil
}

func (pnh *PushNotificationHandler) sendToUser(ctx context.Context, userID string, notifications []*Notification, badgeCount int) error {
    tokens, err := pnh.tokenService.GetValidTokens(ctx, userID)
    if err != nil {
        return fmt.Errorf("failed to get device tokens: %w", err)
    }
    
    if len(tokens) == 0 {
        return nil // No devices registered
    }
    
    // Use the most recent notification for the push content
    latestNotif := notifications[len(notifications)-1]
    
    message := &messaging.MulticastMessage{
        Notification: &messaging.Notification{
            Title: latestNotif.Title,
            Body:  latestNotif.Body,
        },
        Data: map[string]string{
            "notification_id": latestNotif.ID,
            "user_id":         userID,
            "count":           strconv.Itoa(len(notifications)),
        },
        Android: &messaging.AndroidConfig{
            Priority: "high",
            TTL:      time.Hour,
        },
        APNS: &messaging.APNSConfig{
            Payload: &messaging.APNSPayload{
                Aps: &messaging.Aps{
                    Badge: &badgeCount,
                },
            },
        },
        Tokens: tokens,
    }
    
    response, err := pnh.fcmClient.SendMulticast(ctx, message)
    if err != nil {
        return fmt.Errorf("FCM send failed: %w", err)
    }
    
    // Handle token cleanup for failed sends
    if response.FailureCount > 0 {
        go pnh.handleFailedTokens(userID, tokens, response.Responses)
    }
    
    return nil
}
```

**Problem Fixed**: #4 (broken push notification implementation), #5 (badge count performance)

### 5.2 Scalable WebSocket Architecture
```go
type WebSocketManager struct {
    connections sync.Map // map[userID]*websocket.Conn
    redis       *redis.ClusterClient
    maxConns    int
    connCount   int64
}

func (wsm *WebSocketManager) HandleConnection(w http.ResponseWriter, r *http.Request) {
    // Rate limiting check
    if atomic.LoadInt64(&wsm.connCount) >= int64(wsm.maxConns) {
        http.Error(w, "Connection limit exceeded", http.StatusTooManyRequests)
        return
    }
    
    userID := r.Header.Get("X-User-ID")
    if userID == "" {
        http.Error(w, "Missing user ID", http.StatusUnauthorized)
        return
    }
    
    conn, err := wsm.upgrader.Upgrade(w, r, nil)
    if err != nil {
        log.Error("WebSocket upgrade failed", "error", err)
        return
    }
    
    atomic.AddInt64(&wsm.connCount, 1)
    defer atomic.AddInt64(&wsm.connCount, -1)
    
    // Store connection with cleanup
    wsm.connections.Store(userID, conn)
    defer wsm.connections.Delete(userID)
    
    // Subscribe to user's notification channel
    pubsub := wsm.redis.Subscribe(context.Background(), fmt.Sprintf("notifications:%s", userID))
    defer pubsub.Close()
    
    // Handle messages
    ch := pubsub.Channel()
    for msg := range ch {
        if err := conn.WriteMessage(websocket.TextMessage, []byte(msg.Payload)); err != nil {
            log.Error("WebSocket write failed", "user_id", userID, "error", err)
            break
        }
    }
}

// Separate service for WebSocket message distribution
func (wsm *WebSocketManager) SendToUser(userID string, notification *Notification) error {
    data, err := json.Marshal(notification)
    if err != nil {
        return fmt.Errorf("marshal failed: %w", err)
    }
    
    // Publish to Redis for distribution across all app instances
    return wsm.redis.Publish(context.Background(), 
        fmt.Sprintf("notifications:%s", userID), string(data)).Err()
}
```

**Problem Fixed**: #5 (WebSocket scaling issues), #7 (missing load balancing)

## 6. Robust Failure Handling & Circuit Breakers

### 6.1 Dead Letter Queue Processing
```go
type DeadLetterProcessor struct {
    consumer    sarama.Consumer
    producer    sarama.SyncProducer
    retryTopic  string
    maxRetries  int
}

func (dlp *DeadLetterProcessor) ProcessDeadLetters(ctx context.Context) error {
    partitionConsumer, err := dlp.consumer.ConsumePartition("dead-letter-queue", 0, sarama.OffsetOldest)
    if err != nil {
        return fmt.Errorf("failed to create partition consumer: %w", err)
    }
    defer partitionConsumer.Close()
    
    for {
        select {
        case message := 