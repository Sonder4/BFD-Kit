# 用户反馈参考文档

本文档提供 STM32 用户反馈技能的详细参考信息。

## 反馈数据格式详解

### 完整反馈数据结构

```json
{
    "timestamp": "2026-02-21T10:30:00+08:00",
    "feedback_type": "user_confirmation",
    "project_name": "RC2026_h7",
    "project_status": "building",
    "summary": "代码修改完成，请确认",
    "details": {
        "action_taken": "修改 GPIO 配置",
        "files_modified": [
            "Core/Src/gpio.c",
            "Core/Inc/gpio.h"
        ],
        "result": "成功",
        "build_status": "passed"
    },
    "user_response": null,
    "metadata": {
        "skill_version": "1.0.0",
        "toolchain": "ARM-GCC"
    }
}
```

### 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `timestamp` | string | 是 | ISO 8601 格式时间戳 |
| `feedback_type` | string | 是 | 反馈类型枚举值 |
| `project_name` | string | 是 | 项目名称 |
| `project_status` | string | 否 | 当前项目状态 |
| `summary` | string | 是 | 反馈摘要 |
| `details` | object | 否 | 详细信息字典 |
| `user_response` | string/null | 否 | 用户响应内容 |
| `metadata` | object | 否 | 元数据字典 |

## 反馈类型详解

### user_confirmation - 用户确认

用于任务完成后的确认请求。

```json
{
    "feedback_type": "user_confirmation",
    "summary": "GPIO 配置修改完成",
    "details": {
        "action_taken": "修改 GPIO 引脚配置",
        "files_modified": ["gpio.c", "gpio.h"],
        "result": "成功"
    }
}
```

**使用场景：**
- 代码修改完成
- 配置更新完成
- 文件操作完成

### error_report - 错误报告

用于报告错误信息。

```json
{
    "feedback_type": "error_report",
    "summary": "编译错误报告",
    "details": {
        "error_type": "compilation_error",
        "error_message": "undefined reference to 'HAL_Init'",
        "affected_files": ["main.c"],
        "error_count": 3,
        "warning_count": 5
    }
}
```

**使用场景：**
- 编译错误
- 链接错误
- 运行时错误
- 配置错误

### status_update - 状态更新

用于通知项目状态变化。

```json
{
    "feedback_type": "status_update",
    "summary": "构建进度更新",
    "details": {
        "previous_status": "idle",
        "current_status": "building",
        "progress": 50,
        "message": "正在编译 Core 模块..."
    }
}
```

**使用场景：**
- 构建进度更新
- 烧录进度更新
- 调试状态变化

### user_request - 用户请求

用于记录用户主动发起的请求。

```json
{
    "feedback_type": "user_request",
    "summary": "用户请求添加新功能",
    "details": {
        "request_type": "feature_add",
        "description": "添加 UART DMA 接收功能",
        "priority": "high"
    }
}
```

**使用场景：**
- 功能请求
- 问题报告
- 配置修改请求

## MCP 工具调用示例

### 基本调用

```python
result = mcp_feedback_enhanced(
    title="STM32 项目反馈",
    summary="代码修改完成，请确认是否继续",
    status="waiting_feedback"
)
```

### 带详细信息的调用

```python
result = mcp_feedback_enhanced(
    title="RC2026_h7 - 构建完成",
    summary="""
## 构建结果

- 编译状态: 成功
- 警告数量: 2
- 修改文件: 3

请确认是否继续烧录。
""",
    status="waiting_feedback"
)
```

## 状态转换图

```
                    ┌─────────┐
                    │  IDLE   │
                    └────┬────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
    ┌───────────┐  ┌───────────┐  ┌───────────┐
    │ BUILDING  │  │ DEBUGGING │  │ FLASHING  │
    └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
          │              │              │
          └──────────────┼──────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
    ┌───────────┐  ┌───────────┐  ┌────────────────┐
    │   ERROR   │  │  WAITING  │  │     IDLE       │
    └───────────┘  │  FEEDBACK │  └────────────────┘
                   └───────────┘
```

## 与 build-error-logger 技能集成

### 错误记录流程

```
1. 检测到错误
      ↓
2. 创建 error_report 反馈
      ↓
3. 调用 build-error-logger 技能
      ↓
4. 记录错误日志
      ↓
5. 收集用户反馈
      ↓
6. 根据反馈执行操作
```

### 集成示例

```python
error_feedback = create_error_feedback(
    collector=collector,
    error_type="compilation_error",
    error_message="undefined reference to 'main'",
    affected_files=["startup_stm32h743xx.s"]
)

mcp_feedback_enhanced(
    title="编译错误",
    summary="检测到编译错误，已记录到错误日志",
    status="error"
)
```

## 最佳实践

### 反馈时机

1. **任务开始前**：通知用户即将执行的操作
2. **任务进行中**：定期更新进度状态
3. **任务完成后**：请求用户确认
4. **错误发生时**：立即报告并请求反馈

### 反馈内容

1. **简洁明了**：摘要控制在 100 字以内
2. **信息完整**：详细信息放在 details 字段
3. **格式规范**：使用标准 JSON 格式
4. **时间准确**：使用 ISO 8601 时间格式

### 错误处理

1. **立即报告**：错误发生时立即通知用户
2. **记录完整**：保留完整的错误信息
3. **提供上下文**：包含相关的项目状态信息
4. **等待反馈**：不要自行决定后续操作

## 附录

### 相关文件

| 文件 | 说明 |
|------|------|
| `SKILL.md` | 技能定义文件 |
| `scripts/feedback_collector.py` | 反馈收集脚本 |
| `scripts/status_monitor.py` | 状态监控脚本 |

### 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0 | 2026-02-21 | 初始版本 |
