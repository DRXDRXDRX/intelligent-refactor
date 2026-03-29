# 智能代码重构系统 (Intelligent Refactor Gemini)

本系统旨在构建一个**语义安全、可控可验证**的智能代码重构平台，面向 JavaScript/TypeScript/React 项目，实现从自然语言需求到精确代码变更的端到端自动化。

## 架构总览
系统采用 **Lead Agent 主从协同架构**，包含以下核心服务：
- **LangGraph Server (核心运行时)**：系统的心脏，基于 LangGraph 构建。负责全局任务编排与用户交互管理，托管 Lead Agent 及四类专业子智能体（Planner、Analyzer、Refactorer、Validator）。
- **Gateway API (网关服务)**：基于 FastAPI 构建的轻量级 RESTful 服务，作为前端与核心运行时之间的桥梁。
- **Rewrite Engine (代码重写引擎)**：基于 Node.js 构建的独立微服务，负责将 RefactorIR 中间表示翻译为精确的 AST 原子操作。
- **Sandbox Provider (沙箱提供器)**：为每个重构任务提供隔离的执行环境（本地沙箱基于 Git worktree，容器化沙箱基于 Docker）。
- **Nginx (反向代理)**：作为系统的统一入口。

## 核心技术栈
- LLM 推理: GPT-4o / Claude 3.5 Sonnet
- Agent 编排框架: LangGraph (Python)
- 后端网关: FastAPI (Python)
- 后端 RPC 通信: Connect RPC
- Schema 格式: JSON Schema
- AST 解析与操作: SWC, ts-morph, Babel, recast
- 状态持久化: PostgreSQL + SQLAlchemy
- 消息队列: Redis
- 沙箱环境: Git worktree, Docker
