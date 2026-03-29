## Critical Analysis of Original Proposal

### Major Problems Identified:

1. **Over-engineered Database Design**: The schema is unnecessarily complex for MVP delivery. Encrypted token storage, JSONB data fields, and automated partition management add months of development time that a 4-person team can't afford.

2. **Incomplete Code Implementation**: The FastAPI code cuts off mid-function and lacks the actual SQS message processing, delivery workers, and retry logic - the core functionality.

3. **Unrealistic Infrastructure Costs**: Claims $8K/month but shows $4K+ just for databases, ignoring compute, SQS, data transfer, and monitoring costs. Real cost likely $15K+/month.

4. **Missing Delivery Worker Architecture**: Shows SQS queues but no actual worker implementation for processing push notifications, emails, or SMS.

5. **No Practical Scaling Strategy**: Viral traffic handling mentions 4,350 notifications/second but provides no autoscaling configuration, queue depth monitoring, or circuit breakers.

6. **Overcomplicated User Preferences**: The preference system is too granular for MVP. "likes_from_followers_only" type features should be Phase 2.

7. **No Monitoring Implementation**: Mentions observability but provides no actual CloudWatch metrics, alarms, or dashboards.

8. **Partition Management Complexity**: Monthly partitioning with automated cleanup is premature optimization that adds operational overhead.

---

# Notification System Design for 10M MAU Social App - REVISED

## Executive Summary

This proposal delivers a **production-ready notification system** that a 4-person team can build and deploy in 6 months. The design prioritizes working functionality over premature optimization, ensuring the system handles real traffic loads while remaining operationally simple.

**Core Architecture:**
- **PostgreSQL** for user data and preferences (proven, well-understood)
- **Redis** for rate limiting and caching (simple, fast)
- **SQS** for async message processing (managed, reliable)
- **ECS Fargate** for delivery workers (auto-scaling, low-ops)

**Realistic Constraints:**
- 4 engineers × 6 months = 24 person-months total effort
- Target operational cost: $12K/month (including overhead)
- Handle 15M notifications/day with 25x viral spike capability
- 99.5% delivery success rate for critical notifications

## 1. Traffic Requirements & Channel Strategy

### Realistic Load Analysis
```
Daily Active Users: 3M (30% of 10M MAU)
Notification Generation:
- Comments: 2M/day (0.67 per user)
- Likes: 8M/day (2.67 per user) 
- Follows: 500K/day
- Messages: 4M/day
- System: 500K/day
Total: 15M/day = 174/second average

Peak Patterns:
- Daily peak (6-9pm): 5x = 870/second
- Viral events: 25x = 4,350/second for 30 minutes
- Affects up to 2M users simultaneously
```

### Channel Prioritization
```
Phase 1 (Months 1-3): Push + In-App
- Push: 70% of notifications (10.5M/day)
- In-app: 100% of notifications (15M/day)
- Focus on core user engagement

Phase 2 (Months 4-6): Email + SMS
- Email: 25% of users opted-in (3.75M/day)
- SMS: 5% of users, critical only (200K/day)
- Revenue-driving channels
```

## 2. Simplified Architecture

### Service Layout
```
┌─────────────────────────────────────────────────────────┐
│                 Application Load Balancer               │
└─────────────────┬───────────────────────────────────────┘
                  │
        ┌─────────────────────┐
        │   Notification API  │
        │   (ECS Service)     │
        │   2 tasks           │
        └─────────┬───────────┘
                  │
        ┌─────────────────────┐
        │    Amazon SQS       │
        │  notification-queue │
        │  (FIFO + DLQ)       │
        └─────────┬───────────┘
                  │
        ┌─────────────────────┐
        │  Delivery Workers   │
        │   (ECS Service)     │
        │   4 tasks           │
        └─────────┬───────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───────┐   ┌──────────┐   ┌─────────┐
│  RDS  │   │  Redis   │   │External │
│Primary│   │ Cluster  │   │Services │
└───────┘   └──────────┘   └─────────┘
```

### Technology Choices & Rationale

**PostgreSQL (RDS)**
- **Why**: Team expertise, ACID guarantees, mature ecosystem
- **Scale**: r6g.xlarge handles 1000 TPS easily
- **Cost**: $800/month vs $3K+ for DynamoDB at scale

**Redis (ElastiCache)**
- **Why**: Sub-millisecond rate limiting, session caching
- **Scale**: r6g.large handles 100K ops/second
- **Cost**: $400/month

**SQS FIFO**
- **Why**: Exactly-once delivery, dead letter queues
- **Scale**: 3000 TPS per queue (multiple queues for scaling)
- **Cost**: $200/month at 15M messages

**ECS Fargate**
- **Why**: Auto-scaling, no server management
- **Scale**: 0.25 vCPU tasks scale 0-20 based on queue depth
- **Cost**: $600/month average

## 3. Database Schema (Simplified for MVP)

```sql
-- Core users table
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255),
    phone VARCHAR(20),
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Simple notification preferences
CREATE TABLE notification_preferences (
    user_id BIGINT PRIMARY KEY REFERENCES users(id),
    
    -- Channel toggles
    push_enabled BOOLEAN DEFAULT true,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    
    -- Content type toggles (MVP set)
    comments BOOLEAN DEFAULT true,
    likes BOOLEAN DEFAULT true,
    follows BOOLEAN DEFAULT true,
    messages BOOLEAN DEFAULT true,
    
    -- Rate limiting (simple)
    max_push_hourly INTEGER DEFAULT 20,
    quiet_hours_start INTEGER DEFAULT 22, -- 22:00
    quiet_hours_end INTEGER DEFAULT 8,    -- 08:00
    
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Device tokens for push
CREATE TABLE device_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    token VARCHAR(500) NOT NULL, -- Store directly for MVP
    platform VARCHAR(20) NOT NULL,
    active BOOLEAN DEFAULT true,
    last_used TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_id, platform),
    INDEX idx_user_active (user_id, active)
);

-- Notifications table (single table for MVP)
CREATE TABLE notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    deep_link VARCHAR(500),
    data JSONB DEFAULT '{}',
    
    priority INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 4),
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    
    -- Indexes for common queries
    INDEX idx_user_created (user_id, created_at DESC),
    INDEX idx_status_priority (status, priority, created_at)
);

-- Delivery tracking (simplified)
CREATE TABLE delivery_logs (
    id BIGSERIAL PRIMARY KEY,
    notification_id BIGINT REFERENCES notifications(id),
    channel VARCHAR(20) NOT NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    attempted_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_notification (notification_id)
);
```

## 4. Complete API Implementation

### Notification API Service
```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import asyncpg
import json
import boto3
import redis
from datetime import datetime, timezone
import structlog

app = FastAPI(title="Notification API")
logger = structlog.get_logger()

class NotificationRequest(BaseModel):
    user_ids: List[int]
    type: str
    title: str
    body: str
    deep_link: Optional[str] = None
    data: dict = {}
    priority: int = 3

class NotificationService:
    def __init__(self):
        self.db_pool = None
        self.redis = redis.Redis(host='notification-cache.xxx.cache.amazonaws.com')
        self.sqs = boto3.client('sqs', region_name='us-east-1')
        self.queue_url = 'https://sqs.us-east-1.amazonaws.com/123456789/notification-queue.fifo'
    
    async def initialize(self):
        self.db_pool = await asyncpg.create_pool(
            "postgresql://user:pass@notification-db.xxx.rds.amazonaws.com/notifications",
            min_size=5, max_size=20
        )
    
    async def create_notifications(self, request: NotificationRequest):
        """Create and queue notifications"""
        
        # 1. Validate users and get preferences
        async with self.db_pool.acquire() as conn:
            user_prefs = await conn.fetch("""
                SELECT u.id, u.timezone,
                       np.push_enabled, np.email_enabled, np.sms_enabled,
                       np.comments, np.likes, np.follows, np.messages,
                       np.max_push_hourly, np.quiet_hours_start, np.quiet_hours_end
                FROM users u
                LEFT JOIN notification_preferences np ON u.id = np.user_id
                WHERE u.id = ANY($1)
            """, request.user_ids)
        
        if not user_prefs:
            raise HTTPException(404, "No valid users found")
        
        # 2. Filter by preferences and rate limits
        eligible_users = []
        for user in user_prefs:
            # Check content type preference
            if not getattr(user, request.type, True):
                continue
            
            # Check rate limiting
            rate_key = f"rate_limit:push:{user['id']}:{datetime.now().hour}"
            current_count = self.redis.get(rate_key) or 0
            if int(current_count) >= user['max_push_hourly']:
                logger.warning("Rate limited", user_id=user['id'])
                continue
            
            # Check quiet hours (simplified)
            user_hour = datetime.now().hour  # Use UTC for MVP
            if user['quiet_hours_start'] <= user_hour <= user['quiet_hours_end']:
                continue
            
            eligible_users.append(user)
        
        # 3. Create notification records
        notification_ids = []
        async with self.db_pool.acquire() as conn:
            for user in eligible_users:
                notif_id = await conn.fetchval("""
                    INSERT INTO notifications (user_id, type, title, body, deep_link, data, priority)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                """, user['id'], request.type, request.title, request.body, 
                    request.deep_link, json.dumps(request.data), request.priority)
                
                notification_ids.append(notif_id)
        
        # 4. Queue for delivery
        for notif_id in notification_ids:
            message_body = {
                'notification_id': notif_id,
                'priority': request.priority,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            self.sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
                MessageGroupId=f"priority_{request.priority}",
                MessageDeduplicationId=f"notif_{notif_id}_{int(datetime.now().timestamp())}"
            )
            
            # Update rate limiting
            for user in eligible_users:
                rate_key = f"rate_limit:push:{user['id']}:{datetime.now().hour}"
                self.redis.incr(rate_key)
                self.redis.expire(rate_key, 3600)
        
        return {
            'queued': len(notification_ids),
            'filtered': len(request.user_ids) - len(eligible_users)
        }

notification_service = NotificationService()

@app.on_event("startup")
async def startup():
    await notification_service.initialize()

@app.post("/notifications")
async def create_notification(request: NotificationRequest):
    """Create notifications for multiple users"""
    return await notification_service.create_notifications(request)

@app.get("/notifications/{user_id}")
async def get_user_notifications(user_id: int, limit: int = 20):
    """Get notification history for a user"""
    async with notification_service.db_pool.acquire() as conn:
        notifications = await conn.fetch("""
            SELECT id, type, title, body, deep_link, data, created_at, delivered_at
            FROM notifications 
            WHERE user_id = $1 
            ORDER BY created_at DESC 
            LIMIT $2
        """, user_id, limit)
        
        return [dict(n) for n in notifications]

@app.put("/preferences/{user_id}")
async def update_preferences(user_id: int, preferences: dict):
    """Update user notification preferences"""
    async with notification_service.db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO notification_preferences (user_id, push_enabled, email_enabled, comments, likes, follows, messages)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (user_id) DO UPDATE SET
                push_enabled = EXCLUDED.push_enabled,
                email_enabled = EXCLUDED.email_enabled,
                comments = EXCLUDED.comments,
                likes = EXCLUDED.likes,
                follows = EXCLUDED.follows,
                messages = EXCLUDED.messages,
                updated_at = NOW()
        """, user_id, preferences.get('push_enabled', True), preferences.get('email_enabled', True),
             preferences.get('comments', True), preferences.get('likes', True), 
             preferences.get('follows', True), preferences.get('messages', True))
    
    return {"status": "updated"}
```

### Delivery Worker Service
```python
import asyncio
import asyncpg
import boto3
import json
import httpx
from datetime import datetime
import structlog

logger = structlog.get_logger()

class DeliveryWorker:
    def __init__(self):
        self.db_pool = None
        self.sqs = boto3.client('sqs', region_name='us-east-1')
        self.queue_url = 'https://sqs.us-east-1.amazonaws.com/123456789/notification-queue.fifo'
        
        # External service clients
        self.fcm_client = httpx.AsyncClient(
            base_url="https://fcm.googleapis.com/v1/projects/your-project",
            headers={"Authorization": "Bearer YOUR_FCM_TOKEN"}
        )
        self.sendgrid_client = httpx.AsyncClient(
            base_url="https://api.sendgrid.com/v3",
            headers={"Authorization": "Bearer YOUR_SENDGRID_KEY"}
        )
    
    async def initialize(self):
        self.db_pool = await asyncpg.create_pool(
            "postgresql://user:pass