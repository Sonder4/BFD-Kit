---
name: bfd-user-feedback
description: 用户反馈与状态监控技能。触发：(1)用户反馈收集请求 (2)运行状态监控 (3)错误日志记录 (4)关键词"收集反馈"、"用户反馈"、"状态监控"、"交互反馈" (5)任务完成需用户确认。禁止跳过用户确认、禁止忽略用户反馈。
---

# BFD User Feedback

## Self-Improvement Loop (Required)

- When this skill encounters a build, flash, debug, script-usage, or other workflow problem, do not stop at the local workaround after the issue is solved.
- Record the resolved issue and lesson in `BFD-Kit/.learnings/ERRORS.md` and/or `BFD-Kit/.learnings/LEARNINGS.md`; unresolved capability gaps go to `BFD-Kit/.learnings/FEATURE_REQUESTS.md`.
- Promote reusable fixes into the affected BFD-Kit asset in the same task when feasible: update the relevant `SKILL.md`, script, wrapper, or resource so the next run benefits by default.
- When a learning is promoted into a skill or script, append a short entry to `BFD-Kit/.learnings/CHANGELOG.md` and mention the improvement in the task close-out.

## 触发条件

1. 用户请求收集反馈
2. 需要监控运行状态
3. 错误日志记录请求
4. 关键词：收集反馈、用户反馈、状态监控、交互反馈
5. 任务完成需用户确认

## 调用形式

### 完整调用

```
请使用 bfd-user-feedback 技能收集用户反馈
```

### 简写调用

```
收集用户反馈
```

```
状态监控
```

```
交互反馈
```

## 用户反馈收集接口

### MCP 工具调用

使用 `mcp-feedback-enhanced` MCP 工具进行用户反馈收集：

```python
mcp_feedback_enhanced(
    title="STM32 项目反馈",
    summary="当前任务执行摘要",
    status="waiting_feedback"
)
```

### 反馈收集时机

| 场景 | 触发条件 | 反馈类型 |
|------|----------|----------|
| 任务完成 | 代码修改完成 | 确认反馈 |
| 错误发生 | 编译/运行错误 | 错误反馈 |
| 状态变更 | 重要状态变化 | 状态反馈 |
| 用户请求 | 用户主动请求 | 自由反馈 |

## 运行状态监控

### 状态类型

```python
class ProjectStatus:
    IDLE = "idle"
    BUILDING = "building"
    DEBUGGING = "debugging"
    FLASHING = "flashing"
    ERROR = "error"
    WAITING_FEEDBACK = "waiting"
```

### 状态监控流程

1. **状态检测**：检测当前项目运行状态
2. **状态记录**：记录状态变更信息
3. **状态通知**：向用户报告状态变化
4. **异常处理**：处理异常状态转换

## 错误日志记录

### 调用 build-error-logger 技能

当检测到错误时，调用 `build-error-logger` 技能记录错误：

```
请使用 build-error-logger 技能记录当前构建错误
```

### 错误记录触发条件

- 编译错误
- 链接错误
- 运行时错误
- 用户报告的错误

## 反馈数据格式

### 标准反馈格式

```json
{
    "timestamp": "2026-02-21T10:30:00Z",
    "feedback_type": "user_confirmation",
    "project_status": "building",
    "summary": "任务执行摘要",
    "details": {
        "action_taken": "代码修改",
        "files_modified": ["main.c", "config.h"],
        "result": "成功"
    },
    "user_response": null
}
```

### 反馈类型定义

| 类型 | 说明 | 用途 |
|------|------|------|
| `user_confirmation` | 用户确认 | 任务完成确认 |
| `error_report` | 错误报告 | 错误信息收集 |
| `status_update` | 状态更新 | 进度通知 |
| `user_request` | 用户请求 | 用户主动请求 |

## 工作流程

### 标准反馈收集流程

```
1. 检测触发条件
      ↓
2. 收集当前状态信息
      ↓
3. 生成反馈摘要
      ↓
4. 调用 mcp-feedback-enhanced 工具
      ↓
5. 等待用户反馈
      ↓
6. 处理用户反馈
      ↓
7. 执行后续操作（如有）
```

### 错误处理流程

```
1. 检测错误
      ↓
2. 记录错误信息
      ↓
3. 调用 build-error-logger 技能
      ↓
4. 收集用户反馈
      ↓
5. 根据反馈执行操作
```

## 禁止内容清单

**严格禁止：**

- 跳过用户确认步骤
- 忽略用户反馈内容
- 自行决定任务完成
- 隐瞒错误信息

**必须执行：**

- 每次任务完成收集用户反馈
- 如实报告所有状态
- 正确记录错误信息
- 尊重用户决策

## 目录结构

```
.trae/skills/bfd-user-feedback/
├── SKILL.md
├── scripts/
│   ├── feedback_collector.py
│   └── status_monitor.py
└── references/
    └── user-feedback-reference.md
```

## 相关技能

- **build-error-logger**: 构建错误日志记录
- **mcp-feedback-enhanced**: MCP 反馈工具

## 参考文档

详细反馈格式和示例请参考 [user-feedback-reference.md](references/user-feedback-reference.md)。
