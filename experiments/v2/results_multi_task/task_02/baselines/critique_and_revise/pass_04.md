## Critical Review of Original Proposal

### Major Problems Identified:

1. **Overcomplicated Architecture for Team Size**: The proposal suggests a complex hybrid database approach and multiple specialized services that a 4-person team cannot effectively build and maintain in 6 months.

2. **Unrealistic DynamoDB Cost Assumptions**: At 450M notification records/month, DynamoDB will cost $15K+/month just for storage, plus $8K+/month for writes. The "cost-effective" claim is false.

3. **Missing Core Engineering Details**: The batching engine code is incomplete, there's no actual queue processing logic, and the failure handling is mentioned but not designed.

4. **Overengineered Database Design**: Complex bitfield preferences, multiple indexes, and denormalization that adds complexity without clear benefit for a 6-month delivery timeline.

5. **No Clear Service Boundaries**: The proposal jumps between API design, database schemas, and batching without defining clear service responsibilities.

6. **Ignores Social App Reality**: Social apps have extreme engagement inequality (1% create content, 9% engage, 90% lurk). The traffic patterns and notification needs are completely different from the assumed uniform distribution.

7. **Missing Operational Concerns**: No deployment strategy, no monitoring design, no alerting thresholds, and no disaster recovery plan.

---

# Notification System Design for 10M MAU Social App - COMPLETE REVISION

## Executive Summary

This proposal designs a pragmatic notification system for a social media platform with 10M monthly active users. The design prioritizes **delivery in 6 months with 4 engineers** over architectural perfection, while ensuring the system can handle viral traffic patterns typical of social platforms.

**Key Constraints:**
- 4 backend engineers, 6 months delivery
- Social app with viral traffic (50x spikes during trending events)
- Budget target: <$20K/month operational costs
- Must handle engagement inequality (90% passive users, 10% active creators)

**Core Design Philosophy:**
- **Simple over clever**: Use proven patterns, avoid premature optimization
- **Monolith first**: Single service that can be split later
- **Managed services**: Minimize operational overhead
- **Gradual rollout**: Ship MVP in 3 months, iterate to full feature set

## 1. Social App Traffic Reality & Requirements

### Engagement Distribution (Pareto Principle Applied)
```
User Segments:
- Super Users (1% = 100K users): 
  * Post daily, get 80% of all engagement
  * Generate 60% of notifications (viral content)
  * Need real-time delivery for monetization
  
- Active Users (9% = 900K users):
  * Post weekly, moderate engagement
  * Generate 30% of notifications
  * Expect delivery within 5 minutes
  
- Passive Users (90% = 9M users):
  * Consume content, rarely post
  * Generate 10% of notifications (mostly likes)
  * Batch delivery acceptable (hourly)
```

### Realistic Traffic Patterns
```
Normal Day (Weekday):
- 3M daily active users (30% of MAU - high for social)
- 15M notifications/day (5 per DAU)
- 174 notifications/second average
- 870 notifications/second peak (5pm-8pm)

Viral Event (2-3x per week):
- Trending hashtag, celebrity post, breaking news
- 50x traffic spike (8,700 notifications/second)
- Duration: 10-45 minutes
- Affects 40% of user base simultaneously

Weekend Patterns:
- 20% higher engagement
- More viral events
- Longer engagement sessions
```

### Channel Distribution (Data-Driven)
```
Based on social app benchmarks:

Push Notifications:
- 15% opt-in rate (most users disable quickly)
- 1.5M eligible users
- 2M daily push notifications
- Cost: ~$200/month (FCM/APNS free tier)

Email:
- 45% opt-in rate 
- 4.5M eligible users
- 6M daily emails
- Cost: ~$1,800/month (SendGrid)

In-App:
- 100% of active users
- 15M daily in-app notifications
- Cost: Storage only (~$300/month)

SMS:
- 2% opt-in rate (premium feature)
- 200K eligible users
- 100K daily SMS (high-value only)
- Cost: ~$3,000/month (Twilio)
```

## 2. Simplified System Architecture

### Single Service Architecture (MVP Approach)
```
┌─────────────────────────────────────────────────────────┐
│                Notification Service                     │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Ingestion │  │  Processing │  │   Delivery  │     │
│  │     API     │  │   Engine    │  │   Workers   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
├─────────────────────────────────────────────────────────┤
│           PostgreSQL (Single Database)                  │
└─────────────────────────────────────────────────────────┘
                              │
                    ┌─────────────────┐
                    │  External APIs  │
                    │ FCM│APNS│SendGrid│
                    └─────────────────┘
```

**Why Single Service?**
- 4 engineers can't maintain microservices effectively
- Faster development and debugging
- Easier deployment and monitoring
- Can extract services later as team grows

### Infrastructure Stack (Minimal Viable)
```
Hosting: AWS ECS Fargate
Load Balancer: AWS ALB
Database: PostgreSQL RDS (r6g.xlarge)
Cache: Redis ElastiCache (r6g.large)
Queue: AWS SQS (4 queues by priority)
Storage: S3 (templates, logs)
Monitoring: CloudWatch + PagerDuty
Deployment: GitHub Actions + Terraform
```

**Total Infrastructure Cost: ~$2,500/month**

## 3. Database Design (Single PostgreSQL)

### Why PostgreSQL Only?
- **Team Expertise**: Most engineers know PostgreSQL
- **ACID Compliance**: Critical for user preferences and delivery tracking
- **JSON Support**: Flexible notification payloads without schema complexity
- **Proven Scale**: Can handle 10M users with proper indexing
- **Cost Effective**: $800/month vs $15K+ for DynamoDB at scale

### Core Tables
```sql
-- Users and preferences (normalized for consistency)
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20),
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Simple notification preferences
CREATE TABLE user_notification_settings (
    user_id BIGINT REFERENCES users(id) PRIMARY KEY,
    
    -- Channel opt-ins
    push_enabled BOOLEAN DEFAULT false,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    
    -- Simple category controls
    comments_enabled BOOLEAN DEFAULT true,
    likes_enabled BOOLEAN DEFAULT true,
    follows_enabled BOOLEAN DEFAULT true,
    messages_enabled BOOLEAN DEFAULT true,
    
    -- Rate limiting
    daily_push_limit INTEGER DEFAULT 10,
    daily_email_limit INTEGER DEFAULT 5,
    
    -- Quiet hours
    quiet_start TIME DEFAULT '22:00',
    quiet_end TIME DEFAULT '08:00',
    
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Device tokens (simple approach)
CREATE TABLE device_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    token VARCHAR(500) NOT NULL,
    platform VARCHAR(20) NOT NULL, -- 'ios', 'android', 'web'
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_id, token),
    INDEX idx_user_active (user_id, active)
);

-- Notifications (with JSON payload for flexibility)
CREATE TABLE notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    
    -- Content
    type VARCHAR(50) NOT NULL, -- 'comment', 'like', 'follow', 'message'
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    data JSONB, -- Custom payload
    
    -- Delivery settings
    priority INTEGER DEFAULT 3, -- 1=critical, 2=high, 3=medium, 4=low
    channels TEXT[] DEFAULT '{}', -- ['push', 'email']
    
    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'delivered', 'failed'
    
    -- Timing
    created_at TIMESTAMP DEFAULT NOW(),
    scheduled_for TIMESTAMP DEFAULT NOW(),
    delivered_at TIMESTAMP,
    
    -- Indexes for common queries
    INDEX idx_user_status (user_id, status),
    INDEX idx_scheduled (scheduled_for, status),
    INDEX idx_type_created (type, created_at)
);

-- Delivery attempts (for debugging and analytics)
CREATE TABLE delivery_attempts (
    id BIGSERIAL PRIMARY KEY,
    notification_id BIGINT REFERENCES notifications(id),
    channel VARCHAR(20) NOT NULL,
    
    -- Attempt details
    attempted_at TIMESTAMP DEFAULT NOW(),
    success BOOLEAN NOT NULL,
    error_message TEXT,
    external_id VARCHAR(255), -- Provider message ID
    
    INDEX idx_notification (notification_id),
    INDEX idx_attempted (attempted_at)
);

-- Partitioning for performance (PostgreSQL 12+)
CREATE TABLE notifications_y2024m01 PARTITION OF notifications
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Auto-create monthly partitions
CREATE OR REPLACE FUNCTION create_monthly_partition()
RETURNS void AS $$
DECLARE
    start_date date;
    end_date date;
    table_name text;
BEGIN
    start_date := date_trunc('month', CURRENT_DATE);
    end_date := start_date + interval '1 month';
    table_name := 'notifications_y' || to_char(start_date, 'YYYY') || 'm' || to_char(start_date, 'MM');
    
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF notifications FOR VALUES FROM (%L) TO (%L)',
                   table_name, start_date, end_date);
END;
$$ LANGUAGE plpgsql;

-- Schedule partition creation
SELECT cron.schedule('create-partitions', '0 0 1 * *', 'SELECT create_monthly_partition()');
```

## 4. Core Service Implementation

### Notification API (FastAPI)
```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import asyncpg
import json
from datetime import datetime, timedelta

app = FastAPI(title="Notification Service")

class NotificationRequest(BaseModel):
    user_ids: List[int]
    type: str  # 'comment', 'like', 'follow', 'message'
    title: str
    body: str
    data: dict = {}
    priority: int = 3  # 1-4 scale
    channels: Optional[List[str]] = None
    scheduled_for: Optional[datetime] = None

class NotificationService:
    def __init__(self, db_pool):
        self.db = db_pool
        
    async def create_notifications(self, request: NotificationRequest) -> List[int]:
        """Create notifications for multiple users efficiently"""
        
        if len(request.user_ids) > 1000:
            raise HTTPException(400, "Maximum 1000 users per request")
        
        # Get user preferences in batch
        user_settings = await self.get_user_settings(request.user_ids)
        
        # Filter users based on preferences
        eligible_users = []
        for user_id in request.user_ids:
            settings = user_settings.get(user_id)
            if settings and self.should_send_notification(settings, request.type):
                channels = request.channels or self.get_default_channels(request.type, settings)
                eligible_users.append((user_id, channels))
        
        if not eligible_users:
            return []
        
        # Batch insert notifications
        notification_ids = []
        async with self.db.acquire() as conn:
            for user_id, channels in eligible_users:
                notification_id = await conn.fetchval("""
                    INSERT INTO notifications (user_id, type, title, body, data, priority, channels, scheduled_for)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                """, user_id, request.type, request.title, request.body, 
                    json.dumps(request.data), request.priority, channels,
                    request.scheduled_for or datetime.utcnow())
                
                notification_ids.append(notification_id)
        
        # Queue for processing
        await self.queue_notifications(notification_ids, request.priority)
        
        return notification_ids
    
    async def get_user_settings(self, user_ids: List[int]) -> dict:
        """Batch fetch user notification settings"""
        async with self.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, push_enabled, email_enabled, sms_enabled,
                       comments_enabled, likes_enabled, follows_enabled, messages_enabled,
                       daily_push_limit, daily_email_limit, quiet_start, quiet_end, timezone
                FROM user_notification_settings
                WHERE user_id = ANY($1)
            """, user_ids)
            
            return {row['user_id']: dict(row) for row in rows}
    
    def should_send_notification(self, settings: dict, notification_type: str) -> bool:
        """Check if user wants this type of notification"""
        type_enabled = settings.get(f"{notification_type}_enabled", True)
        return type_enabled
    
    def get_default_channels(self, notification_type: str, settings: dict) -> List[str]:
        """Determine which channels to use based on type and user preferences"""
        channels = []
        
        # Critical notifications always use all enabled channels
        if notification_type == 'message':
            if settings.get('push_enabled'): channels.append('push')
            if settings.get('email_enabled'): channels.append('email')
            if settings.get('sms_enabled'): channels.append('sms')
        
        # Regular notifications use smart defaults
        elif notification_type in ['comment', 'follow']:
            if settings.get('push_enabled'): channels.append('push')
            if settings.get('email_enabled'): channels.append('email')
        
        # Low-priority notifications (likes) - push only
        else:
            if settings.get('push_enabled'): channels.append('push')
        
        return channels
    
    async def queue_notifications(self, notification_ids: List[int], priority: int):
        """Queue notifications for processing based on priority"""
        import boto3
        
        sqs = boto3.client('sqs')
        queue_urls = {
            1: 'https://sqs.us-east-1.amazonaws.com/123456789/notifications-critical',
            2: 'https://sqs.us-east-1.amazonaws.com/123456789/notifications-high', 
            3: 'https://sqs.us-east-1.amazonaws.com/123456789/notifications-medium',
            4: 'https://sqs.us-east-1.amazonaws.com/123456789/notifications-low'
        }
        
        queue_url = queue_urls.get(priority, queue_urls[3])
        
        # Send in batches of 10 (SQS limit)
        for i in range(0, len(notification_ids), 10):
            batch = notification_ids[i:i+10]
            entries = []
            
            for idx, notification_id in enumerate(batch):
                entries.append({
                    'Id': str(idx),
                    'MessageBody': json.dumps({'notification