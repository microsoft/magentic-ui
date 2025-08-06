# Magentic-UI API 接口文档

## 概述

Magentic-UI 是一个用于与 Web 代理交互的应用程序。本文档描述了 Magentic-UI 后端提供的所有 API 接口。

**基础 URL**: `http://localhost:8081/api`  
**API 版本**: 通过 `/api/version` 端点获取

## 通用响应格式

所有 API 响应都遵循以下格式：

```json
{
  "status": true,
  "data": {...},
  "message": "操作成功"
}
```

错误响应格式：

```json
{
  "status": false,
  "error": "错误代码",
  "message": "错误描述"
}
```

## 1. 会话管理 (Sessions)

### 1.1 获取用户会话列表

**GET** `/api/sessions/`

**查询参数**:
- `user_id` (string, 必需): 用户ID

**响应示例**:
```json
{
  "status": true,
  "data": [
    {
      "id": 1,
      "user_id": "user123",
      "title": "我的会话",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 1.2 获取特定会话

**GET** `/api/sessions/{session_id}`

**路径参数**:
- `session_id` (integer, 必需): 会话ID

**查询参数**:
- `user_id` (string, 必需): 用户ID

**响应示例**:
```json
{
  "status": true,
  "data": {
    "id": 1,
    "user_id": "user123",
    "title": "我的会话",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

### 1.3 创建新会话

**POST** `/api/sessions/`

**请求体**:
```json
{
  "user_id": "user123",
  "title": "新会话标题"
}
```

**响应示例**:
```json
{
  "status": true,
  "data": {
    "id": 2,
    "user_id": "user123",
    "title": "新会话标题",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

### 1.4 更新会话

**PUT** `/api/sessions/{session_id}`

**路径参数**:
- `session_id` (integer, 必需): 会话ID

**查询参数**:
- `user_id` (string, 必需): 用户ID

**请求体**:
```json
{
  "user_id": "user123",
  "title": "更新后的标题"
}
```

**响应示例**:
```json
{
  "status": true,
  "data": {
    "id": 1,
    "user_id": "user123",
    "title": "更新后的标题",
    "updated_at": "2024-01-01T00:00:00Z"
  },
  "message": "Session updated successfully"
}
```

### 1.5 删除会话

**DELETE** `/api/sessions/{session_id}`

**路径参数**:
- `session_id` (integer, 必需): 会话ID

**查询参数**:
- `user_id` (string, 必需): 用户ID

**响应示例**:
```json
{
  "status": true,
  "message": "Session deleted successfully"
}
```

### 1.6 获取会话运行历史

**GET** `/api/sessions/{session_id}/runs`

**路径参数**:
- `session_id` (integer, 必需): 会话ID

**查询参数**:
- `user_id` (string, 必需): 用户ID

**响应示例**:
```json
{
  "status": true,
  "data": {
    "runs": [
      {
        "id": "1",
        "created_at": "2024-01-01T00:00:00Z",
        "status": "COMPLETED",
        "task": "搜索最新论文",
        "team_result": {...},
        "messages": [...],
        "input_request": null
      }
    ]
  }
}
```

## 2. 运行管理 (Runs)

### 2.1 创建运行

**POST** `/api/runs/`

**请求体**:
```json
{
  "session_id": 1,
  "user_id": "user123"
}
```

**响应示例**:
```json
{
  "status": true,
  "data": {
    "run_id": "1"
  }
}
```

### 2.2 获取运行详情

**GET** `/api/runs/{run_id}`

**路径参数**:
- `run_id` (integer, 必需): 运行ID

**响应示例**:
```json
{
  "status": true,
  "data": {
    "id": 1,
    "session_id": 1,
    "status": "ACTIVE",
    "task": "搜索最新论文",
    "team_result": {...},
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

### 2.3 获取运行消息

**GET** `/api/runs/{run_id}/messages`

**路径参数**:
- `run_id` (integer, 必需): 运行ID

**响应示例**:
```json
{
  "status": true,
  "data": [
    {
      "id": 1,
      "run_id": 1,
      "config": {
        "source": "user",
        "content": "搜索最新论文",
        "type": "TextMessage"
      },
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 2.4 下载文件

**GET** `/api/runs/download`

**查询参数**:
- `file_path` (string, 必需): 文件路径，相对于 `/app/workspace/` 目录

**响应**: 文件下载响应

## 3. WebSocket 通信

### 3.1 WebSocket 连接

**WebSocket** `/api/ws/runs/{run_id}`

**路径参数**:
- `run_id` (integer, 必需): 运行ID

### 3.2 客户端消息格式

#### 启动任务
```json
{
  "type": "start",
  "task": "搜索最新论文",
  "files": [],
  "team_config": {...},
  "settings_config": {...}
}
```

#### 停止任务
```json
{
  "type": "stop",
  "reason": "用户请求停止"
}
```

#### 输入响应
```json
{
  "type": "input_response",
  "response": "用户输入内容"
}
```

#### 暂停任务
```json
{
  "type": "pause"
}
```

#### 恢复任务
```json
{
  "type": "resume"
}
```

#### 心跳检测
```json
{
  "type": "ping"
}
```

### 3.3 服务器消息格式

#### 系统消息
```json
{
  "type": "system",
  "status": "connected",
  "is_reconnection": false,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### 任务状态
```json
{
  "type": "task_status",
  "status": "ACTIVE",
  "task": "搜索最新论文",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### 代理消息
```json
{
  "type": "message",
  "data": {
    "source": "web_surfer",
    "content": "消息内容",
    "type": "TextMessage"
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### 任务结果
```json
{
  "type": "result",
  "data": {
    "status": "completed",
    "result": "任务完成结果"
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### 输入请求
```json
{
  "type": "input_request",
  "input_type": "text_input",
  "data": "请输入内容"
}
```

#### 错误消息
```json
{
  "type": "error",
  "error": "错误描述",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### 心跳响应
```json
{
  "type": "pong",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 4. 计划管理 (Plans)

### 4.1 获取用户计划列表

**GET** `/api/plans/`

**查询参数**:
- `user_id` (string, 必需): 用户ID

**响应示例**:
```json
{
  "status": true,
  "data": [
    {
      "id": 1,
      "user_id": "user123",
      "task": "搜索论文",
      "steps": [...],
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 4.2 获取特定计划

**GET** `/api/plans/{plan_id}`

**路径参数**:
- `plan_id` (integer, 必需): 计划ID

**查询参数**:
- `user_id` (string, 必需): 用户ID

**响应示例**:
```json
{
  "status": true,
  "data": {
    "id": 1,
    "user_id": "user123",
    "task": "搜索论文",
    "steps": [
      {
        "title": "步骤1",
        "details": "详细描述",
        "agent_name": "web_surfer"
      }
    ],
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

### 4.3 创建计划

**POST** `/api/plans/`

**请求体**:
```json
{
  "user_id": "user123",
  "task": "搜索论文",
  "steps": [
    {
      "title": "步骤1",
      "details": "详细描述",
      "agent_name": "web_surfer"
    }
  ]
}
```

**响应示例**:
```json
{
  "status": true,
  "data": {
    "id": 1,
    "user_id": "user123",
    "task": "搜索论文",
    "steps": [...],
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

### 4.4 更新计划

**PUT** `/api/plans/{plan_id}`

**路径参数**:
- `plan_id` (integer, 必需): 计划ID

**查询参数**:
- `user_id` (string, 必需): 用户ID

**请求体**:
```json
{
  "user_id": "user123",
  "task": "更新后的任务",
  "steps": [...]
}
```

**响应示例**:
```json
{
  "status": true,
  "data": {
    "id": 1,
    "user_id": "user123",
    "task": "更新后的任务",
    "steps": [...]
  },
  "message": "Plan updated successfully"
}
```

### 4.5 删除计划

**DELETE** `/api/plans/{plan_id}`

**路径参数**:
- `plan_id` (integer, 必需): 计划ID

**查询参数**:
- `user_id` (string, 必需): 用户ID

**响应示例**:
```json
{
  "status": true,
  "data": {...}
}
```

### 4.6 从会话学习计划

**POST** `/api/plans/learn_plan`

**请求体**:
```json
{
  "session_id": 1,
  "user_id": "user123"
}
```

**响应示例**:
```json
{
  "status": true,
  "data": {
    "planId": 1
  },
  "message": "Plan created successfully"
}
```

## 5. 团队管理 (Teams)

### 5.1 获取用户团队列表

**GET** `/api/teams/`

**查询参数**:
- `user_id` (string, 必需): 用户ID

**响应示例**:
```json
{
  "status": true,
  "data": [
    {
      "id": 1,
      "user_id": "user123",
      "name": "我的团队",
      "config": {...},
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 5.2 获取特定团队

**GET** `/api/teams/{team_id}`

**路径参数**:
- `team_id` (integer, 必需): 团队ID

**查询参数**:
- `user_id` (string, 必需): 用户ID

**响应示例**:
```json
{
  "status": true,
  "data": {
    "id": 1,
    "user_id": "user123",
    "name": "我的团队",
    "config": {...},
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

### 5.3 创建团队

**POST** `/api/teams/`

**请求体**:
```json
{
  "user_id": "user123",
  "name": "新团队",
  "config": {...}
}
```

**响应示例**:
```json
{
  "status": true,
  "data": {
    "id": 1,
    "user_id": "user123",
    "name": "新团队",
    "config": {...},
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

### 5.4 删除团队

**DELETE** `/api/teams/{team_id}`

**路径参数**:
- `team_id` (integer, 必需): 团队ID

**查询参数**:
- `user_id` (string, 必需): 用户ID

**响应示例**:
```json
{
  "status": true,
  "message": "Team deleted successfully"
}
```

## 6. 设置管理 (Settings)

### 6.1 获取用户设置

**GET** `/api/settings/`

**查询参数**:
- `user_id` (string, 必需): 用户ID

**响应示例**:
```json
{
  "status": true,
  "data": {
    "id": 1,
    "user_id": "user123",
    "config": {
      "theme": "dark",
      "language": "zh-CN"
    },
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

### 6.2 更新用户设置

**PUT** `/api/settings/`

**请求体**:
```json
{
  "user_id": "user123",
  "config": {
    "theme": "light",
    "language": "en-US"
  }
}
```

**响应示例**:
```json
{
  "status": true,
  "data": {
    "id": 1,
    "user_id": "user123",
    "config": {
      "theme": "light",
      "language": "en-US"
    },
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

## 7. 组件验证 (Validation)

### 7.1 验证组件配置

**POST** `/api/validate/`

**请求体**:
```json
{
  "component": {
    "component_type": "ChatCompletionClient",
    "provider": "autogen_ext.models.openai.OpenAIChatCompletionClient",
    "config": {
      "model": "gpt-4",
      "api_key": "your-api-key"
    }
  }
}
```

**响应示例**:
```json
{
  "is_valid": true,
  "errors": [],
  "warnings": [
    {
      "field": "version",
      "error": "Component version not specified",
      "suggestion": "Consider adding a version to ensure compatibility"
    }
  ]
}
```

## 8. 系统接口

### 8.1 获取 API 版本

**GET** `/api/version`

**响应示例**:
```json
{
  "status": true,
  "message": "Version retrieved successfully",
  "data": {
    "version": "1.0.0"
  }
}
```

### 8.2 健康检查

**GET** `/api/health`

**响应示例**:
```json
{
  "status": true,
  "message": "Service is healthy"
}
```

## 错误代码

| HTTP 状态码 | 错误描述 |
|-------------|----------|
| 400 | 请求参数错误 |
| 404 | 资源未找到 |
| 500 | 服务器内部错误 |

## 注意事项

1. **认证**: 当前版本未实现用户认证，所有接口都需要通过 `user_id` 参数传递用户标识
2. **WebSocket 重连**: 支持 WebSocket 连接断开后重连，任务会继续执行
3. **文件下载**: 文件下载接口限制在 workspace 目录内，防止路径遍历攻击
4. **组件验证**: 验证接口会检查组件配置的有效性和可实例化性
5. **计划学习**: 从会话学习计划功能需要配置相应的 AI 模型客户端

## 开发环境

- **Python 版本**: 3.10+
- **框架**: FastAPI
- **WebSocket**: 支持实时双向通信
- **数据库**: 支持多种数据库后端
- **文档**: 自动生成 Swagger/OpenAPI 文档 