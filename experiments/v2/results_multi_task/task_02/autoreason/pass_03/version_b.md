# Notification System Design for 10M MAU Social App - REVISED

## Executive Summary

This proposal outlines a scalable notification system supporting 10M monthly active users across multiple delivery channels. Given the 4-engineer, 6-month constraint, we focus on a pragmatic MVP approach using managed services while addressing realistic scaling challenges. The design acknowledges significant limitations requiring future investment while delivering core functionality reliably.

## 1. System Architecture Overview

### Core Components
- **Notification Service**: Central orchestrator with authentication
- **Device Token Service**: Dedicated service for managing 20-30M device tokens (partitioned storage)
- **Channel Handlers**: Dedicated processors for push, email, in-app, and SMS
- **User Preference Service**: Normalized preference management with caching
- **Template Service**: Secure content handling with sanitization
- **Analytics Service**: Accurate delivery tracking with measurable metrics

### Technology Stack
- **Message Queue**: Amazon SQS with separate queues per priority level and DLQ
- **Database**: PostgreSQL with read replicas and partitioned tables, Redis Cluster for tokens/cache
- **Push Notifications**: Firebase Cloud Messaging (FCM) + Apple Push Notification Service (APNs)
- **Email**: Amazon SES (with proper warming plan and deliverability timeline)
- **SMS**: Twilio (with strict cost controls and daily budgets)
- **Infrastructure**: AWS with auto-scaling groups and WebSocket-specific instances

**Rationale**: Managed services reduce operational complexity while partitioned storage and Redis clustering address realistic scale requirements for device tokens and user preferences.

## 2. Realistic WebSocket and Connection Management

**FIXES PROBLEM 1: Unrealistic WebSocket scaling math**

### 2.1 Conservative WebSocket Capacity Planning
```python
class WebSocketManager:
    # Realistic capacity based on ALB limits and memory constraints
    MAX_CONNECTIONS_PER_ALB_TARGET = 50000  # AWS ALB limit: 55k, leaving headroom
    MEMORY_PER_CONNECTION = 8192  # 8KB per connection (connection state + buffers)
    INSTANCE_MEMORY_LIMIT = 32 * 1024 * 1024 * 1024  # 32GB instance
    MAX_CONNECTIONS_PER_INSTANCE = min(
        MAX_CONNECTIONS_PER_ALB_TARGET,
        int(INSTANCE_MEMORY_LIMIT * 0.6 / MEMORY_PER_CONNECTION)  # 60% memory for connections
    )  # Results in ~2,400 connections per instance
    
    TARGET_CONCURRENT_USERS = 500000  # 5% of MAU during peak hours
    WEBSOCKET_CAPACITY = 50000  # 20 instances × 2,400 connections
    POLLING_USERS = TARGET_CONCURRENT_USERS - WEBSOCKET_CAPACITY  # 450k users on polling
    
    def __init__(self):
        self.connection_limit = 2400
        self.fallback_polling_interval = 15  # seconds for better UX
        
    def handle_connection_overflow(self, user_id):
        if self.get_active_connections() >= self.connection_limit:
            # Fallback to polling for 90% of concurrent users
            return self.setup_polling_fallback(user_id)
        return self.establish_websocket(user_id)

    def distribute_connections(self):
        # Use consistent hashing to distribute users across instances
        return ConsistentHashRing(self.get_available_instances())
```

**WebSocket Limitations**:
- Support maximum 50k concurrent WebSocket connections (1% of MAU)
- 90% of concurrent users (450k) use 15-second polling
- Geographic distribution across multiple regions for better performance

## 3. Proper Redis Cluster and Storage Design

**FIXES PROBLEM 2: Redis cluster configuration and Problem 3: Database partitioning flaws**

### 3.1 Correct Redis Cluster Setup
```python
class DeviceTokenManager:
    def __init__(self):
        # Proper Redis Cluster: 6 nodes minimum (3 masters + 3 replicas)
        self.redis_cluster = RedisCluster(
            nodes=[
                {"host": "redis-m1", "port": 7000},  # Master 1
                {"host": "redis-m2", "port": 7000},  # Master 2  
                {"host": "redis-m3", "port": 7000},  # Master 3
                {"host": "redis-s1", "port": 7000},  # Slave 1
                {"host": "redis-s2", "port": 7000},  # Slave 2
                {"host": "redis-s3", "port": 7000}   # Slave 3
            ],
            # 30M tokens × 600 bytes = 18GB + overhead = 32GB total cluster memory
            decode_responses=True,
            skip_full_coverage_check=False
        )
        
    def store_token(self, user_id, device_id, token, platform):
        # Store in Redis for fast access, PostgreSQL for durability
        redis_key = f"token:{user_id}:{device_id}"
        token_data = {
            "token": token,
            "platform": platform,
            "last_active": int(time.time())
        }
        
        # Redis storage (24-hour TTL for active tokens)
        try:
            self.redis_cluster.setex(redis_key, 86400, json.dumps(token_data))
        except RedisError:
            pass  # Continue without cache
            
        # PostgreSQL storage for durability
        self.db.upsert_device_token(user_id, device_id, token, platform)
```

### 3.2 Fixed Database Partitioning Strategy
```sql
-- Device tokens partitioned by device_id for efficient cleanup
CREATE TABLE device_tokens (
    user_id BIGINT,
    device_id VARCHAR(255),
    platform VARCHAR(10),
    token VARCHAR(512),
    last_active TIMESTAMP,
    is_valid BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY HASH (device_id);  -- Changed from user_id to device_id

-- Create 16 partitions
CREATE TABLE device_tokens_p0 PARTITION OF device_tokens FOR VALUES WITH (MODULUS 16, REMAINDER 0);
-- ... repeat for p1-p15

-- Delivery history partitioned by user_id for efficient user queries
CREATE TABLE notification_delivery_history (
    id BIGSERIAL,
    user_id BIGINT,
    notification_id UUID,
    channel VARCHAR(20),
    status VARCHAR(20),
    delivered_at TIMESTAMP DEFAULT NOW(),
    error_message TEXT
) PARTITION BY HASH (user_id);  -- Changed from time-based to user-based

CREATE TABLE delivery_history_p0 PARTITION OF notification_delivery_history FOR VALUES WITH (MODULUS 8, REMAINDER 0);
-- ... repeat for p1-p7

-- Separate time-based table for analytics (different access pattern)
CREATE TABLE delivery_analytics (
    delivered_at TIMESTAMP,
    channel VARCHAR(20),
    status VARCHAR(20),
    count INTEGER,
    PRIMARY KEY (delivered_at, channel, status)
) PARTITION BY RANGE (delivered_at);

-- Foreign key constraints for data integrity
ALTER TABLE notification_delivery_history 
ADD CONSTRAINT fk_delivery_user 
FOREIGN KEY (user_id) REFERENCES users(id);
```

## 4. Realistic Email Deliverability Implementation

**FIXES PROBLEM 4: Unrealistic email deliverability timeline**

### 4.1 Conservative Email Scaling Strategy
```python
class EmailDeliverabilityManager:
    def __init__(self):
        # Conservative SES scaling based on industry best practices
        self.phases = {
            "domain_warming": {
                "duration_weeks": 8,
                "daily_limit": 50,
                "rate_limit": 1,  # emails per second
                "recipient_strategy": "employee_testing"
            },
            "ip_warming": {
                "duration_weeks": 6, 
                "daily_limit": 1000,
                "rate_limit": 2,
                "recipient_strategy": "opt_in_beta_users"
            },
            "reputation_building": {
                "duration_weeks": 8,
                "daily_limit": 10000,
                "rate_limit": 5,
                "recipient_strategy": "engaged_users_only"
            },
            "full_scale": {
                "duration_weeks": 4,
                "daily_limit": 100000,
                "rate_limit": 14,  # SES default limit
                "recipient_strategy": "all_users"
            }
        }
        
    def can_send_email(self, recipient_engagement_score):
        current_phase = self.get_current_phase()
        daily_sent = self.get_daily_email_count()
        
        # Respect daily limits
        if daily_sent >= current_phase["daily_limit"]:
            return False
            
        # Phase-specific recipient filtering
        if current_phase["recipient_strategy"] == "engaged_users_only":
            return recipient_engagement_score > 0.7
        elif current_phase["recipient_strategy"] == "opt_in_beta_users":
            return self.is_beta_user(recipient_engagement_score)
            
        return True
        
    def monitor_deliverability_metrics(self):
        # Critical metrics that affect SES reputation
        bounce_rate = self.get_bounce_rate()
        complaint_rate = self.get_complaint_rate()
        
        # SES thresholds: <5% bounce rate, <0.1% complaint rate
        if bounce_rate > 0.03 or complaint_rate > 0.05:
            self.pause_email_sending()
            self.alert_operations_team()
```

**Realistic Email Timeline**:
- Weeks 1-8: Domain warming (50 emails/day to employees)
- Weeks 9-14: IP warming (1k emails/day to beta users)  
- Weeks 15-22: Reputation building (10k emails/day to engaged users)
- Weeks 23-26: Full scale (100k emails/day to all users)

## 5. Improved SMS Cost Control and Fallback Strategy

**FIXES PROBLEM 5: Inadequate SMS cost control**

### 5.1 Comprehensive SMS Cost Management
```python
class SMSCostController:
    def __init__(self):
        # Realistic cost structure with international considerations
        self.domestic_cost = 0.0075  # Twilio US SMS cost
        self.international_cost = 0.15  # Average international cost
        self.daily_budget = 500  # Conservative $500 daily limit
        self.user_daily_limit = 2  # Max 2 SMS per user per day
        self.critical_reserve_budget = 100  # $100 reserved for critical notifications
        
    def send_with_intelligent_fallback(self, user_id, message, priority):
        cost_check = self.calculate_sms_cost(user_id)
        can_send, reason = self.can_send_sms(user_id, cost_check.amount, priority)
        
        if not can_send:
            if reason == "budget_exceeded" and priority == NotificationPriority.CRITICAL:
                # Use critical reserve for security notifications
                return self.send_critical_sms(user_id, message)
            elif reason == "user_limit_exceeded":
                # For user limit, still try push (user might be active)
                return self.send_push_notification(user_id, message)
            else:
                # For budget limits, schedule email as it reaches inactive users
                return self.schedule_email_notification(user_id, message, delay_minutes=5)
                
        return self.send_sms(user_id, message, cost_check.amount)
        
    def calculate_sms_cost(self, user_id):
        user_country = self.get_user_country(user_id)
        if user_country == "US":
            return SMSCost(self.domestic_cost, user_country)
        else:
            return SMSCost(self.international_cost, user_country)
            
    def can_send_sms(self, user_id, cost, priority):
        # Check daily budget
        today_spent = self.get_daily_spend()
        available_budget = self.daily_budget - today_spent
        
        if priority == NotificationPriority.CRITICAL:
            available_budget += self.critical_reserve_budget
            
        if cost > available_budget:
            return False, "budget_exceeded"
            
        # Check user daily limit
        user_sms_today = self.get_user_daily_sms_count(user_id)
        if user_sms_today >= self.user_daily_limit:
            return False, "user_limit_exceeded"
            
        return True, "approved"
```

## 6. Race Condition-Free Batching Logic

**FIXES PROBLEM 6: Batching logic race conditions**

### 6.1 Atomic Batching with Proper Synchronization
```python
class BatchingManager:
    def __init__(self):
        self.batch_intervals = {
            NotificationPriority.CRITICAL: 0,    # Immediate
            NotificationPriority.HIGH: 0,        # Immediate  
            NotificationPriority.MEDIUM: 300,    # 5 minutes
            NotificationPriority.LOW: 86400      # Daily
        }
        
    def process_notification(self, notification):
        batch_interval = self.batch_intervals[notification.priority]
        
        if batch_interval == 0:
            return self.send_immediately(notification)
        else:
            return self.add_to_batch_atomically(notification, batch_interval)
            
    def add_to_batch_atomically(self, notification, interval):
        # Use database-level locking to prevent race conditions
        batch_window_start = self.get_batch_window_start(interval)
        batch_key = f"{notification.user_id}_{notification.channel}_{batch_window_start}"
        
        with self.db.transaction():
            # Lock the batch row to prevent concurrent modifications
            batch = self.db.get_batch_for_update(batch_key)
            
            if not batch:
                batch = self.db.create_batch(
                    key=batch_key,
                    user_id=notification.user_id,
                    channel=notification.channel,
                    window_start=batch_window_start,
                    window_end=batch_window_start + interval,
                    status='collecting'
                )
                
            # Check if this notification should be deduplicated
            if not self.should_add_to_batch(batch, notification):
                return BatchResult(status='deduplicated', batch_id=batch.id)
                
            self.db.add_notification_to_batch(batch.id, notification)
            return BatchResult(status='batched', batch_id=batch.id)
            
    def should_add_to_batch(self, batch, notification):
        # Apply deduplication rules within the locked transaction
        existing_notifications = self.db.get_batch_notifications(batch.id)
        
        for existing in existing_notifications:
            if self.are_duplicate_notifications(existing, notification):
                # Update existing notification with latest data instead of adding new one
                self.db.update_notification_in_batch(existing.id, notification)
                return False
                
        return True
        
    def process_batch_window(self, batch_window_start):
        # Process all batches that should be sent in this window
        batches = self.db.get_batches_for_window(batch_window_start)
        
        for batch in batches:
            with self.db.transaction():
                # Lock batch to prevent race conditions with new notifications
                locked_batch = self.db.get_batch_for_update(batch.id)
                if locked_batch.status != 'collecting':
                    continue
                    
                self.db.update_batch_status(batch.id, 'processing')
                
            # Process outside the transaction to avoid long locks
            self.send_batch_notifications(batch.id)
            self.db.update_batch_status(batch.id, 'sent')
```

## 7. Simplified and Clear Preference Management

**FIXES PROBLEM 7: Overly complex preference resolution**

### 7.1 Clear Preference Hierarchy with Precedence Rules