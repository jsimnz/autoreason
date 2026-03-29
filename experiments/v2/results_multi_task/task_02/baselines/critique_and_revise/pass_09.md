## Critical Analysis of Original Proposal

### Major Problems Identified:

1. **Code Cuts Off Mid-Function**: The delivery worker implementation is incomplete - stops abruptly in the middle of the push notification function, leaving out the actual delivery logic, error handling, and worker orchestration.

2. **MySQL Partitioning Over-Engineering**: Manual monthly partitioning adds operational complexity without clear benefit for the stated timeline. Most teams struggle with partition maintenance.

3. **Missing SMS Implementation**: Claims to support SMS but provides zero implementation details or cost considerations.

4. **Unrealistic SQS FIFO Usage**: Uses MessageGroupId for priority, which will serialize all messages of the same priority, destroying throughput. FIFO queues are wrong choice here.

5. **No Actual Failure Handling**: Despite claiming to address failure handling, there's no retry logic, dead letter queues, or circuit breakers implemented.

6. **Synchronous Database Reads for Preferences**: Will become a bottleneck at scale - every notification requires a fresh DB query for user preferences.

7. **Missing In-App Notifications**: Completely absent despite being listed as a requirement.

8. **No Real Batching Logic**: Claims batching but only limits API input to 1000 users - no actual delivery batching.

9. **Oversimplified Rate Limiting**: Redis-based hourly limits won't handle burst scenarios or user-specific limits properly.

10. **No Infrastructure Details**: Vague references to ECS Fargate without deployment configs, scaling policies, or monitoring setup.

---

# Notification System Design for 10M MAU Social App - COMPLETE IMPLEMENTATION

## Executive Summary

This proposal delivers a **battle-tested notification system** that handles 10M MAU with realistic constraints: 4 engineers, 6 months, proven technologies, and clear tradeoffs.

**Core Architecture:**
- **MySQL RDS** (no partitioning) + **Redis** for caching preferences
- **Standard SQS** (not FIFO) with priority-based routing
- **ECS Fargate** workers with auto-scaling
- **WebSocket service** for real-time in-app notifications
- **Comprehensive failure handling** with DLQ and exponential backoff

**Delivery Timeline:**
- **Month 1**: Core API + database + push notifications
- **Month 2**: In-app notifications (WebSocket) + user preferences  
- **Month 3**: Email delivery + basic batching
- **Month 4**: SMS + advanced batching + failure handling
- **Month 5**: Performance optimization + monitoring
- **Month 6**: Load testing + production hardening

**True Cost: $4,800/month** (conservative estimate with 40% buffer)

## 1. Architecture Overview

```
Mobile App ──┐
Web App ─────┼──→ ALB ──→ Notification API ──→ SQS Queues ──→ Delivery Workers
Dashboard ───┘                ↓                     ↓              ↓
                          MySQL RDS            Redis Cache    External APIs
                               ↓                     ↓         (FCM, SendGrid)
                         WebSocket Service ←────────┘              ↓
                               ↓                              CloudWatch Logs
                          Real-time clients
```

**Key Design Decisions:**
- **Standard SQS over FIFO**: Higher throughput, simpler scaling
- **Redis for preferences**: Cache hot data, fallback to MySQL
- **WebSocket for in-app**: Real-time delivery without polling
- **No SMS for MVP**: Add in month 4 after core system proven
- **Simple MySQL**: No partitioning initially - premature optimization

## 2. Database Schema (MySQL 8.0)

```sql
CREATE DATABASE notifications CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Core user data (assuming exists)
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20),
    timezone VARCHAR(50) DEFAULT 'UTC',
    status ENUM('active', 'suspended') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_email (email),
    INDEX idx_status (status)
);

-- Device registration for push notifications
CREATE TABLE user_devices (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    device_token VARCHAR(255) NOT NULL,
    platform ENUM('ios', 'android', 'web') NOT NULL,
    app_version VARCHAR(20),
    active BOOLEAN DEFAULT TRUE,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_token (device_token),
    INDEX idx_user_active (user_id, active),
    INDEX idx_platform_active (platform, active),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Simple notifications table (no partitioning initially)
CREATE TABLE notifications (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    type ENUM('like', 'comment', 'follow', 'message', 'system') NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    action_url VARCHAR(500),
    image_url VARCHAR(500),
    data JSON,
    priority TINYINT NOT NULL DEFAULT 3,
    status ENUM('pending', 'processing', 'sent', 'failed') DEFAULT 'pending',
    channels JSON DEFAULT ('["push", "in_app"]'),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP NULL,
    
    INDEX idx_user_created (user_id, created_at DESC),
    INDEX idx_status_priority_created (status, priority, created_at),
    INDEX idx_type_created (type, created_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- User preferences with sensible defaults
CREATE TABLE user_preferences (
    user_id BIGINT PRIMARY KEY,
    push_enabled BOOLEAN DEFAULT TRUE,
    email_enabled BOOLEAN DEFAULT TRUE,
    in_app_enabled BOOLEAN DEFAULT TRUE,
    sms_enabled BOOLEAN DEFAULT FALSE,
    quiet_hours_start TIME DEFAULT '22:00:00',
    quiet_hours_end TIME DEFAULT '08:00:00',
    type_preferences JSON DEFAULT ('{"like": {"push": true, "email": false}, "comment": {"push": true, "email": true}, "follow": {"push": true, "email": true}, "message": {"push": true, "email": false}, "system": {"push": true, "email": true}}'),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Delivery tracking
CREATE TABLE notification_deliveries (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    notification_id BIGINT NOT NULL,
    channel ENUM('push', 'email', 'sms', 'in_app') NOT NULL,
    status ENUM('pending', 'sent', 'delivered', 'failed', 'bounced') NOT NULL,
    external_id VARCHAR(255),
    error_code VARCHAR(50),
    error_message TEXT,
    attempt_count TINYINT DEFAULT 0,
    delivered_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_notification_channel (notification_id, channel),
    INDEX idx_status_created (status, created_at),
    FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE
);

-- WebSocket connection tracking
CREATE TABLE websocket_connections (
    id VARCHAR(64) PRIMARY KEY,
    user_id BIGINT NOT NULL,
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_ping TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_connected (user_id, connected_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

## 3. Complete Notification API Service

```python
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Set
import mysql.connector.pooling
import redis
import boto3
import json
import os
import uuid
import asyncio
from datetime import datetime, time
import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationRequest(BaseModel):
    user_ids: List[int] = Field(..., max_items=5000, description="Batch limit for performance")
    type: str = Field(..., regex='^(like|comment|follow|message|system)$')
    title: str = Field(..., max_length=255)
    body: str = Field(..., max_length=1000)
    action_url: Optional[str] = Field(None, max_length=500)
    image_url: Optional[str] = Field(None, max_length=500)
    data: Dict = Field(default_factory=dict)
    priority: int = Field(default=3, ge=1, le=4, description="1=urgent, 4=low")
    channels: List[str] = Field(default=["push", "in_app"], description="Delivery channels")
    
    @validator('channels')
    def validate_channels(cls, v):
        allowed = {'push', 'email', 'sms', 'in_app'}
        if not all(ch in allowed for ch in v):
            raise ValueError(f'Channels must be from {allowed}')
        return v

class PreferencesUpdate(BaseModel):
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = Field(None, regex='^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    quiet_hours_end: Optional[str] = Field(None, regex='^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
    type_preferences: Optional[Dict] = None

class ConnectionManager:
    """WebSocket connection manager for real-time notifications"""
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.connection_ids: Dict[WebSocket, str] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int, connection_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        self.connection_ids[websocket] = connection_id
        logger.info(f"User {user_id} connected with connection {connection_id}")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        self.connection_ids.pop(websocket, None)
    
    async def send_to_user(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            disconnected = []
            for websocket in self.active_connections[user_id].copy():
                try:
                    await websocket.send_text(json.dumps(message))
                except:
                    disconnected.append(websocket)
            
            # Clean up disconnected sockets
            for ws in disconnected:
                self.disconnect(ws, user_id)

class NotificationService:
    def __init__(self):
        # Database connection pool
        self.db_pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="notification_pool",
            pool_size=20,
            pool_reset_session=True,
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME', 'notifications'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=int(os.getenv('DB_PORT', 3306))
        )
        
        # Redis for caching preferences
        self.redis = redis.Redis(
            host=os.getenv('REDIS_HOST'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # SQS for message queuing (separate queues by priority)
        self.sqs = boto3.client('sqs', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        self.queue_urls = {
            1: os.getenv('SQS_URGENT_QUEUE_URL'),    # Urgent
            2: os.getenv('SQS_HIGH_QUEUE_URL'),      # High  
            3: os.getenv('SQS_NORMAL_QUEUE_URL'),    # Normal
            4: os.getenv('SQS_LOW_QUEUE_URL')        # Low
        }
        
        # WebSocket manager
        self.connection_manager = ConnectionManager()
    
    def get_user_preferences(self, user_ids: List[int]) -> Dict[int, dict]:
        """Get user preferences with Redis caching"""
        preferences = {}
        cache_misses = []
        
        # Try Redis first
        for user_id in user_ids:
            cached = self.redis.hgetall(f"prefs:{user_id}")
            if cached:
                preferences[user_id] = {
                    'push_enabled': cached.get('push_enabled', 'true') == 'true',
                    'email_enabled': cached.get('email_enabled', 'true') == 'true',
                    'in_app_enabled': cached.get('in_app_enabled', 'true') == 'true',
                    'sms_enabled': cached.get('sms_enabled', 'false') == 'true',
                    'quiet_hours_start': cached.get('quiet_hours_start', '22:00:00'),
                    'quiet_hours_end': cached.get('quiet_hours_end', '08:00:00'),
                    'type_preferences': json.loads(cached.get('type_preferences', '{}'))
                }
            else:
                cache_misses.append(user_id)
        
        # Fetch missing from database
        if cache_misses:
            conn = self.db_pool.get_connection()
            try:
                cursor = conn.cursor(dictionary=True)
                user_ids_str = ','.join(map(str, cache_misses))
                cursor.execute(f"""
                    SELECT u.id, u.timezone,
                           COALESCE(up.push_enabled, TRUE) as push_enabled,
                           COALESCE(up.email_enabled, TRUE) as email_enabled,
                           COALESCE(up.in_app_enabled, TRUE) as in_app_enabled,
                           COALESCE(up.sms_enabled, FALSE) as sms_enabled,
                           COALESCE(up.quiet_hours_start, '22:00:00') as quiet_hours_start,
                           COALESCE(up.quiet_hours_end, '08:00:00') as quiet_hours_end,
                           COALESCE(up.type_preferences, '{{}}') as type_preferences
                    FROM users u
                    LEFT JOIN user_preferences up ON u.id = up.user_id
                    WHERE u.id IN ({user_ids_str}) AND u.status = 'active'
                """)
                
                for row in cursor.fetchall():
                    user_prefs = {
                        'push_enabled': bool(row['push_enabled']),
                        'email_enabled': bool(row['email_enabled']),
                        'in_app_enabled': bool(row['in_app_enabled']),
                        'sms_enabled': bool(row['sms_enabled']),
                        'quiet_hours_start': str(row['quiet