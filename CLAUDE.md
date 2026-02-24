# CLAUDE.md

## 项目概览

- 项目名：`grok2api`
- 入口：`main.py`
- 主要 Chat 路由：`app/api/v1/chat.py`
- 主要 Chat 业务：`app/services/grok/services/chat.py`

## 运行时关键数据

- 配置：`data/config.toml`
- Token：`data/token.json`
- 默认配置：`config.defaults.toml`

## 2026-02-24 变更记录

1. 非流式 Chat 错误透传修复
- 文件：`app/services/grok/services/chat.py`
- 说明：`CollectProcessor` 在上游异常时不再吞错并返回空 `200`，改为抛出错误并返回对应失败状态。

2. OpenAI 风格 content 对象兼容
- 文件：`app/api/v1/chat.py`, `app/services/grok/services/chat.py`
- 说明：`messages[].content` 兼容对象格式（如 `{"type":"text","text":"..."}`）。

3. assistant/tool 的 null content 兼容
- 文件：`app/api/v1/chat.py`
- 说明：允许 `assistant` 和 `tool` 角色在工具调用中使用 `content: null`。

4. 工具调用历史兼容增强
- 文件：`app/api/v1/chat.py`, `app/services/grok/services/chat.py`
- 说明：
  - 新增 `tool` 角色支持。
  - `MessageItem` 保留 `tool_calls` / `tool_call_id` / `name` 字段。
  - `MessageExtractor` 增强对工具调用轨迹与 `tool` 消息的提取，降低多轮工具会话出现上下文顺序异常的概率。
