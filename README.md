# FieldOps Agent

## 项目简介

FieldOps Agent 是一个面向现场服务运营场景（Field Service Operations）的 AI Agent 项目。
当前处于 **Phase 18: Production Hardening + Load / Failure Testing**，建立了完整的性能基准测试体系（Locust）、高仿真零 API 成本 FakeLLM 故障注入引擎、Redis 分布式限流器（Fail-Open/Fail-Closed 分级熔断容错）、数据库连接池监控与饱和度告警、Prometheus AlertRules 规则库、请求体安全守卫以及全套高并发场景鲁棒性验证（幂等防穿透、技师排他防超买、Webhooks 去重、连接池耗尽恢复等）。

## 当前技术栈

- **Python**: 3.11+
- **FastAPI**: 轻量现代 Web 框架（提供 `/health`、`/auth/*`、`/metrics`、`/service-requests/*`、`/intake/fake-email`、`/intake/webhook`、`/appointments/{id}/notifications`、`/appointments/{id}/integrations` 等全功能 RESTful API）
- **Inbound Intake Layer**:
  - `InboundServiceRequest`：统一归一化内部数据传输对象 (DTO)
  - `InboundRequestService`：跨渠道统一入口与事件跟踪服务
  - `WebInboundAdapter` / `FakeEmailInboundAdapter` / `WebhookInboundAdapter`：多源渠道数据适配器
  - `InboundEvent`：渠道级幂等存储与哈希冲突比对（复合唯一约束 `(source, external_message_id)`）
- **LangGraph**: 状态图工作流编排引擎（`StateGraph`, `interrupt`, `Command(resume=...)`, 状态持久化 Checkpoint）
- **Celery**: 5.4+ 分布式任务队列（支持延迟倒计时 `countdown`、指数退避重试、Late ACK 保证 At-least-once 交付）
- **Redis**: 7（作为 Celery Message Broker 消息中间件）
- **Transactional Outbox**: 事务发件箱模式（PostgreSQL 作为业务 Source of Truth，数据库事务内原子记录 `outbox_events`，由后台 Polling Publisher 解耦投递至 Redis）
- **External Integration Layer**:
  - `CalendarClient` (ABC) / `FakeCalendarClient`：日历事件同步与取消抽象，支持提供商侧幂等与瞬时/永久故障模拟
  - `EmailClient` (ABC) / `FakeEmailClient`：确认邮件渲染与投递抽象，强绑定 PostgreSQL 真实客户邮箱
  - `IntegrationRecord`：外部提供商资源映射与同步状态持久化（`pending`, `synced`, `failed`, `cancelled`）
- **Domain & Application Services**:
  - `TechnicianMatchingService`：技师技能与区域确定性匹配
  - `SchedulingService`：排班防冲突与候选时间槽切分
  - `AppointmentProposalService`：确定性方案推荐（最早时间优先、技师 ID 决胜）
  - `AppointmentService`：最终预约创建、二次冲突复检、事务内 OutboxEvent 生成与生命周期管理
- **Observability**: Prometheus 客户端指标打点、分布式上下文追踪 (`trace_integration_operation`)、Token 成本核算
- **Security & RBAC**: JWT 认证、Role-Based 访问控制 (ADMIN, DISPATCHER, TECHNICIAN, VIEWER)
- **OpenAI API**: 官方原生结构化输出（`client.beta.chat.completions.parse`）
- **Pydantic**: 强类型数据校验与契约约束
- **SQLAlchemy**: 2.x 现代化 ORM 模型与数据库引擎（行级排他锁、事务隔离）
- **Alembic**: 数据库版本化迁移管理（支持 PostgreSQL `btree_gist` 排他排除约束及异步任务表）
- **PostgreSQL**: 16（通过 Docker Compose 容器化运行业务数据）
- **Docker Compose**: 容器编排（PostgreSQL 16 + Redis 7）


---

## LangGraph 工作流架构 (Phase 9 Workflow)

```text
       START
         ↓
   [parse_request]               <-- 调用 LLM Parser 提取语义信息
         ↓
  [validate_request]             <-- 确定性 Python 规则校验 (硬约束防穿透)
         ↓
   (Conditional Edge 1)
     /         \
 [validated]  [needs_information]
    /             \
   ↓               ↓
[persist_service_request]       END (非法请求直接终止，绝不写入数据库)
   ↓
[match_technicians]             <-- 确定性规则初筛符合技能与区域的候选技师
   ↓
   (Conditional Edge 2)
     /         \
 [ready]      [needs_location / no_technician]
    /             \
   ↓               ↓
[check_schedule]                END (无候选技师时安全退出)
   ↓
   (Conditional Edge 3)
     /         \
 [options_ready]  [no_available_slots / needs_clarification]
    /             \
   ↓               ↓
[build_appointment_proposal]    END (排班冲突或时间不清时不生成建议)
   ↓
[human_review]                  <-- 官方 native interrupt() 挂起工作流，持久化 Checkpoint
   ↓
(Waiting for Operator Approval) <-- HTTP 响应 waiting_for_approval，释放连接
   ↓
(POST /service-requests/{id}/approval)
   ↓
[Resume Workflow via Command]   <-- 传入 approve 或 reject
   ↓
   (Conditional Edge 4)
     /         \
 [approved]   [rejected]
    /             \
   ↓               ↓
[finalize_appointment]  [handle_rejection]
(二次冲突复检/原子入库)    (更新工单状态/记录审计)
   ↓                       ↓
  END                     END
```

---

## 最终预约创建与一致性保障 (Final Appointment Creation)

### 1. 为什么排班检查（Schedule Check）后还要二次检查？
在 Phase 7 的 `check_schedule` 节点中，系统所做的查询仅代表**“在执行检查的那一瞬间该时段空闲”**。
从生成预约提议（Proposal）、挂起等待调度员审核（Waiting for Operator Review），到调度员点击确认（Approval）之间，可能间隔数分钟乃至数小时。
在这一时间差内，存在典型的 **TOCTOU（Time-of-Check to Time-of-Use）并发竞态风险**：其他调度员或并发请求可能已将该技师的相同时间段预约占满。
如果调度员审核通过后不进行二次冲突检查直接执行 SQL INSERT，系统将产生毁灭性的**双重预约（Double Booking）**。

### 2. 双层并发防御体系 (Dual-Layer Concurrency Defense)
为解决高并发与跨时间差下的排班一致性问题，系统实现了双层防御：

1. **应用层事务锁与二次冲突复检 (Application Re-check & Row Lock)**：
   - 调度员点击审批恢复后，`AppointmentService.finalize_appointment` 开启单原子数据库事务；
   - 对目标技师行加悲观排他锁（`SELECT ... FOR UPDATE`），串行化对该技师的并发写入请求；
   - 调用与 Phase 7 完全统一的时间重叠公式（`existing_start < proposed_end AND existing_end > proposed_start`）再次检索有效阻塞预约；
   - 若发现已被抢占，**坚决不创建 Appointment**，将 `ServiceRequest.status` 变更为 `"needs_rescheduling"`，写入冲突审计日志并返回，避免盲目插入。

2. **数据库级排他排除约束 (Database Exclusion Constraint)**：
   - 普通的关系型 `UNIQUE(technician_id, start_time)` 无法防御重叠区间（如 13:00-15:00 与 14:00-16:00 起始时间不同但依然物理冲突）；
   - 通过 Alembic 数据库迁移在 PostgreSQL 中引入 `btree_gist` 扩展，为 `appointments` 表建立 GIST 排他排除约束：
     ```sql
     ALTER TABLE appointments
     ADD CONSTRAINT exclude_overlapping_appointments
     EXCLUDE USING gist (
         technician_id WITH =,
         tstzrange(start_time, end_time) WITH &&
     )
     WHERE (status IN ('scheduled', 'confirmed', 'in_progress'));
     ```
   - 作为数据库内核级兜底底线，即使应用层发生未预见的极端竞态，PostgreSQL 也会直接拒绝冲突的 INSERT，触发 IntegrityError 后由服务层捕获并平稳回滚。

### 3. 业务事务的绝对原子性 (Transaction Atomicity)
严禁将工单更新、预约创建与审计日志拆分为多个孤立提交。所有操作必须包裹在同一个原子事务中：
```text
BEGIN TRANSACTION
  ├─ 幂等性检查 (若当前 service_request 已存在有效预约，直接幂等返回)
  ├─ 锁定技师资源 (SELECT ... FOR UPDATE)
  ├─ 二次冲突检测 (Final Conflict Recheck)
  │    ├─ [冲突发生] -> UPDATE service_requests status='needs_rescheduling'
  │    │                INSERT audit_logs action='appointment.conflict'
  │    │                COMMIT -> 返回 conflict 结果
  │    └─ [无冲突]   -> INSERT appointments status='scheduled'
  │                     UPDATE service_requests status='scheduled'
  │                     INSERT audit_logs action='appointment.created'
  │                     COMMIT -> 返回 appointment_id 成功结果
  └─ [任一步骤失败] -> ROLLBACK (绝不在数据库中留下悬挂状态或孤立记录)
```

---

## 环境变量配置

在 `.env` 中配置相关参数（参见 `.env.example`）：

```ini
DATABASE_URL=postgresql+psycopg://fieldops:fieldops@localhost:5432/fieldops
APP_ENV=development
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini
BUSINESS_TIMEZONE=Asia/Tokyo
DEFAULT_APPOINTMENT_DURATION_MINUTES=120
DEFAULT_SLOT_STEP_MINUTES=60
CHECKPOINT_DB_PATH=checkpoints.sqlite
```

---

## 本地标准启动与使用步骤

### 1. 启动数据库与迁移

```bash
# 启动 PostgreSQL
docker compose up -d postgres

# 执行数据库迁移（自动启用 btree_gist 并增加排他约束）
alembic upgrade head

# 填充初始种子数据
python scripts/seed.py
```

### 2. 启动 FastAPI 应用

```bash
uvicorn fieldops.main:app --reload --app-dir src
```

---

## 完整调用流程示例

### 步骤 1：客户提交需求（自动流转并挂起）

```bash
curl -X POST "http://127.0.0.1:8000/service-requests" \
     -H "Content-Type: application/json" \
     -d '{
       "customer_name": "Alice Smith",
       "email": "alice@example.com",
       "phone": "090-1234-5678",
       "message": "My AC stopped working in Shinjuku, need someone tomorrow afternoon."
     }'
```

**响应示例 (HTTP 201 Created，状态挂起等待审核)**：
```json
{
  "request_id": "8f8b88d3-5775-4d7a-b51c-8f430ff2c499",
  "customer_id": 1,
  "service_request_id": 1,
  "service_type": "HVAC",
  "urgency": "high",
  "location": "Shinjuku",
  "required_skills": ["HVAC"],
  "preferred_time": "tomorrow afternoon",
  "candidate_technician_ids": [1],
  "matching_status": "matched",
  "scheduling_status": "schedule_options_ready",
  "appointment_proposal": {
    "technician_id": 1,
    "technician_name": "Ken Tanaka",
    "start_time": "2026-09-05T15:00:00+09:00",
    "end_time": "2026-09-05T17:00:00+09:00",
    "service_request_id": 1
  },
  "approval_status": "pending",
  "human_review_required": true,
  "workflow_status": "waiting_for_approval"
}
```

### 步骤 2：调度员审批通过（二次复检无冲突，原子入库）

```bash
curl -X POST "http://127.0.0.1:8000/service-requests/8f8b88d3-5775-4d7a-b51c-8f430ff2c499/approval" \
     -H "Content-Type: application/json" \
     -d '{
       "decision": "approve",
       "reason": null
     }'
```

**响应示例 (HTTP 200 OK，预约成功创建)**：
```json
{
  "request_id": "8f8b88d3-5775-4d7a-b51c-8f430ff2c499",
  "service_request_id": 1,
  "workflow_status": "appointment_created",
  "approval_status": "approved",
  "approval_reason": null,
  "appointment_proposal": {
    "technician_id": 1,
    "technician_name": "Ken Tanaka",
    "start_time": "2026-09-05T15:00:00+09:00",
    "end_time": "2026-09-05T17:00:00+09:00",
    "service_request_id": 1
  },
  "appointment_id": 12,
  "appointment_status": "scheduled",
  "finalization_status": "completed",
  "conflict_detected": false
}
```

### 步骤 2 替代路径 A：审批期间发生冲突（二次复检拦截，优雅降级）

若该时段被其他人抢先占用，审批接口平稳降级：
```json
{
  "request_id": "8f8b88d3-5775-4d7a-b51c-8f430ff2c499",
  "service_request_id": 1,
  "workflow_status": "needs_rescheduling",
  "approval_status": "approved",
  "appointment_id": null,
  "appointment_status": null,
  "finalization_status": "conflict",
  "conflict_detected": true
}
```

### 步骤 2 替代路径 B：调度员审批拒绝

```bash
curl -X POST "http://127.0.0.1:8000/service-requests/8f8b88d3-5775-4d7a-b51c-8f430ff2c499/approval" \
     -H "Content-Type: application/json" \
     -d '{
       "decision": "reject",
       "reason": "Customer called to cancel"
     }'
```

**响应示例 (HTTP 200 OK，工单标记拒绝)**：
```json
{
  "request_id": "8f8b88d3-5775-4d7a-b51c-8f430ff2c499",
  "service_request_id": 1,
  "workflow_status": "rejected",
  "approval_status": "rejected",
  "approval_reason": "Customer called to cancel",
  "appointment_id": null,
  "finalization_status": "rejected",
  "conflict_detected": false
}
```

```

---

## 可靠性工程架构 (Phase 10 Reliability Engineering)

生产环境中存在瞬态网络中断、LLM 超时、客户端网络重试及重复提交。Phase 10 通过明确的工程原则保障系统行为完全可控：

### 1. 核心原则：Retry 与 Idempotency 的本质区别
- **Retry（重试）**：操作失败后再次尝试执行。适用于**瞬态基础设施故障**（Transient Failures，如 LLM 超时、HTTP 429、网络瞬断）。盲目重试非幂等操作会导致严重的副作用叠加（如重复创建客户、重复工单、重复扣费）。
- **Idempotency（幂等性）**：多次重复执行同一个操作，产生的业务结果和副作用与执行一次完全相同。它是安全进行重试的先决条件。

### 2. 请求幂等防护机制 (Idempotency Engine)
在 `POST /service-requests` 入口接入 `Idempotency-Key` 标头与双层防护：
1. **规范化载荷哈希校验 (Request Hash)**：
   - 将客户端请求体递归排序并剔除格式差异生成 Canonical JSON，计算 SHA-256 哈希值；
   - 相同 Key 但载荷 Hash 不一致时，立即返回 `HTTP 409 Conflict`，拒绝非法篡改；
2. **状态记录与并发互斥 (Database Unique Constraint)**：
   - 持久化至 PostgreSQL `idempotency_records` 表，数据库强制执行 `UNIQUE (key, operation)`；
   - 首次请求插入 `status = "processing"` 状态记录，并发相同请求直接被数据库唯一约束与行状态拦截，杜绝竞态启动两个重复工作流；
   - 执行成功后原子写入 `status = "completed"` 及缓存的响应 Payload。后续网络重试直接命中并返回首次执行的业务数据，无任何二次副作用。

### 3. 瞬态重试与超时控制 (Retry with Backoff & Timeout)
- **超时保护**：通过配置中心集中管理 `LLM_TIMEOUT_SECONDS = 30.0`，杜绝因外部 Provider 挂起导致的线程池耗尽。
- **选择性退避重试**：
  - **允许重试**：`APITimeoutError`、`RateLimitError (429)`、`InternalServerError (5xx)`、网络连接重置。
  - **绝不重试**：参数验证错误（400）、鉴权失败（401）、模型语义拒绝（Refusal）、结构化解析无效（Schema Invalidation）、业务时段冲突、调度员拒绝。
  - **策略**：最大重试 3 次，采用带抖动的指数退避算法（Exponential Backoff + Jitter）：
    $$\text{delay} = \min(\text{max\_delay}, \text{base\_delay} \times 2^{\text{attempt}-1}) + \text{jitter}$$

### 4. 统一异常分类与 HTTP 状态映射 (Error Taxonomy)
在 `src/fieldops/core/exceptions.py` 中建立明确的异常体系：
- `ValidationError`（HTTP 400）：客户端输入有误，`retryable = False`
- `ResourceNotFoundError`（HTTP 404）：工单或工作流线程不存在，`retryable = False`
- `ConflictError` / `DuplicateRequestError`（HTTP 409）：预约时段冲突、幂等性冲突，`retryable = False`
- `LLMServiceError` / `LLMTimeoutError`（HTTP 503）：上游模型暂时不可用，`retryable = True`
- `DatabaseOperationError` / `WorkflowStateError`（HTTP 500）：内部未捕获或基础设施故障

### 5. 工作流失败可控状态 (Workflow Failure State)
当 LLM 最终重试依然耗尽时，**坚决不使用虚假的 Fallback 默认值（如擅自设定 service_type="Other" 瞒报继续）**。
系统将工作流状态标记为可信的明确状态：
- `workflow_status = "llm_failed"`
- `error_code = "llm_timeout" / "structured_output_invalid" / "model_refusal"`
- `failed_step = "parse_request"`
- `retryable = True / False`
并在条件边安全阻断后续流转，确保数据真实可审计。

### 6. 结构化日志、Correlation ID 与敏感脱敏
- 统一使用 `request_id` 贯穿 HTTP 接入、LLM 解析、数据入库、技师匹配、排班计算与最终确认的全生命周期；
- 记录关键操作耗时 `duration_ms`；
- 日志脱敏脱除客户敏感数据：邮箱脱敏（`a***e@example.com`）、电话脱敏（`********5678`），截断过长原始客户文本，杜绝密钥泄露。

---

## 质量评估体系 (Phase 11 Evaluation & Agent Quality)

为了摆脱“看几个 Case 觉得输出差不多”的主观评估误区，Phase 11 建立了量化、可追溯的评测套件，覆盖四个核心维度：

### 1. 评测执行命令
```bash
# 1. 运行技师匹配确定性评测 (目标 100%)
python evaluation/run_matching_eval.py

# 2. 运行排班区间冲突评测 (目标 100%)
python evaluation/run_scheduling_eval.py

# 3. 运行端到端工作流业务路径评测 (目标 100%)
python evaluation/run_workflow_eval.py

# 4. 运行大模型意图提取评测 (需配置 OPENAI_API_KEY，或添加 --mock 离线验证)
python evaluation/run_parser_eval.py
```

### 2. 评测基线结果 (Evaluation Baseline)

| 评估维度 | 数据集样本数 | 核心指标 | 达成基线 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
| **Technician Matching** | 14 | 候选集完全匹配率 (Exact Set Acc) | **100.0%** | 确定性业务规则 |
| **Scheduling Engine** | 11 | 时段冲突检测准确率 (Conflict Acc) | **100.0%** | 确定性时间区间算法 |
| **Business Workflow** | 5 | 任务完成率 (Task Completion Rate) | **100.0%** | 状态机业务路径 |
| **Workflow State** | 5 | 终态准确率 (Final State Acc) | **100.0%** | 核准/拒绝/冲突/信息缺失 |
| **LLM Parser (Mock/Baseline)**| 32 | 技能识别 F1 分数 (Skills F1) | **1.0** | 集合论 Precision/Recall |
| **LLM Parser (Mock/Baseline)**| 32 | 幻觉率 (Unsupported Field Rate) | **0.0%** | 严禁脑补未提供地点/时间 |

---

## 自动化测试

运行 pytest 运行完整单元与集成测试套件：

```bash
python -m pytest -v
```

测试覆盖（共 **180 项自动化测试全部通过**）：
- `test_intake.py`（19 项新测试）：Web / Fake Email / Webhook 适配器归一化、Webhook 不受支持事件类型校验（400）、Web 接口回归与 InboundEvent 自动落库、Web 端 Idempotency-Key 兼容缓存与冲突检测、Fake Email 模拟邮件接入全流程、Fake Email 重复投递幂等与单条记录保护、Fake Email 相同 ID 不同 Payload 409 冲突拦截、Fake Email 生产环境守卫（403）、Webhook 密钥认证与缺失/错误拦截（401）、Webhook 幂等与哈希冲突、端到端全流程排班审核流转、LLM 失败事件失败标记与审计追踪
- `test_integrations.py`（21 项）：Fake Calendar 确定性 ID 与提供商幂等、Calendar 事件取消状态机、故障注入（瞬时重试与永久阻断）、数据库幂等防重写、已取消预约守卫、模板真实数据渲染、数据库收件人强绑定安全校验、非法邮箱拦截、并发同步单条记录约束、Worker 崩溃提供商幂等恢复、Outbox 自动派发日历与邮件、Outbox 取消事件派发、集成状态查询 API 与 404 处理
- `test_observability.py`（21 项）：Prometheus 指标收集（状态转换、耗时分布、LLM Token 与成本计数器）、Trace 上下文注入与提取、日志脱敏与脱敏过滤器
- `test_async_jobs.py`（11 项）：事务发件箱原子性提交与回滚隔离、Publisher 轮询派发与 Redis 断网容错、Task 幂等防护、已取消预约状态守卫（`skipped`）、任务指数退避重试与最大重试超限处理、售后回访任务流、提醒时间窗口数学规则计算、通知查询与状态管理 API
- `test_evaluation_metrics.py`（7 项）：技能集合 Precision/Recall/F1 计算、空集边界处理、标量大小写无关比对、未提及字段幻觉判定
- `test_idempotency.py`（5 项）：首次请求记录生成、相同 Key 相同 Payload 缓存命中无副作用、相同 Key 不同 Payload 409 冲突拦截、并发处理拦截、无 Header 正常通行
- `test_reliability.py`（11 项）：LLM 瞬时超时二次重试成功、连续超时捕获 llm_failed 明确终止、400 永久错误阻断重试、Structured Output 无效安全退出、400/404/409/503 状态码映射、邮箱/电话敏感脱敏
- `test_appointment_finalization.py`（9 项）：事务原子性与并发排他
- `test_human_in_the_loop.py`（12 项）：方案确定性排序、挂起恢复、跨实例状态恢复
- `test_scheduling.py`（14 项）：时间冲突算法 9 大边界
- `test_technician_matching.py`（14 项）：技能与区域规则匹配
- `test_persistence.py`（8 项）：客户与工单落库
- `test_agent_workflow.py`（11 项）：状态机各节点与条件边
- `test_repositories.py`（6 项）：仓储基础层与种子数据
- `test_parser.py`（9 项）：结构化提取与边界
- `test_health.py`（2 项）：服务探活

---

## 统一入站接入层架构 (Inbound Request Intake Architecture - Phase 16)

### 1. 核心架构与数据流向

FieldOps Agent 实现了渠道无关的统一入站接入层，任何外部渠道（Web、模拟邮件、Webhook、未来 CRM 等）均先经过适配器归一化，再由统一应用服务承接入库，下游透明驱动同一个 LangGraph 核心工作流：

```text
Different Channels (Web Form, Fake Email, Webhook)
       │
       ▼
Inbound Adapters (WebAdapter, FakeEmailAdapter, WebhookAdapter)
       │ (Normalize external payloads into unified DTO)
       ▼
InboundServiceRequest (Normalized internal Schema)
       │
       ▼
InboundRequestService (Channel-side Idempotency & Lifecycle)
       │
       ▼
InboundEvent (PostgreSQL: received -> processing -> completed / failed)
       │
       ▼
FieldOps Application Workflow (LangGraph Engine)
       │
       ▼
ServiceRequest -> Matching -> Scheduling -> Human Approval
```

### 2. 核心设计原则与边界

1. **为什么需要 Inbound Adapter（适配器模式）？**
   - 避免多渠道代码膨胀：若每个渠道各自编写一套解析、入库、启动 LangGraph 的逻辑，会导致代码极度冗余与维护困难。
   - 关注点分离：适配器只负责**外部 Payload -> 内部统一契约**的结构转换与基本清洗，严禁在适配器内执行业务逻辑、排班计算或数据库事务。
2. **多源双轨幂等防御体系**：
   - **Web API**：保留并兼容 Phase 10 的 `Idempotency-Key` 标头与缓存机制。
   - **Email / Webhook**：通过 `inbound_events` 表中的复合唯一键 `UniqueConstraint("source", "external_message_id")` 进行物理防重。
   - **内容哈希冲突检测（SHA-256 Hash Conflict）**：若相同的 `external_message_id` 携带了不同的 Payload，系统拒绝盲目返回缓存，而是立即识别为篡改或逻辑冲突并返回 `HTTP 409 Conflict`。
3. **低耦合短事务边界**：
   - 先以短事务持久化 `InboundEvent(status='received')`，并记录 `inbound.received` 审计日志；
   - 在事务外部执行完整的 LangGraph 状态图工作流，避免长耗时的 LLM 调用导致数据库连接被长时间占用；
   - 工作流执行完毕后，以独立事务更新 `InboundEvent` 状态为 `completed`（记录 `service_request_id`）或 `failed`（记录 `error_summary`）。
4. **安全与生产环境防护网**：
   - **Webhook 安全**：强制请求携带 `X-Webhook-Secret` 标头比对，未授权直接拒绝（HTTP 401 Unauthorized）。*(注：在接入真实生产提供商如 GitHub/Stripe 时，建议升级为基于 HMAC 的签名验证机制)*。
   - **Fake Email 生产守卫**：`/intake/fake-email` 受 `ENABLE_FAKE_INTAKE` 与 `APP_ENV == "production"` 双重守卫，在生产环境中默认强制禁用（HTTP 403 Forbidden）。

---

## 部署与 CI/CD 架构 (Deployment & CI/CD Foundation - Phase 17)

### 1. 多容器生产级拓扑 (Multi-Service Docker Compose)

系统通过统一的多目标 `Dockerfile` 实现构建层最大化复用，在 `docker-compose.yml` 中编排 7 个核心服务：

```text
                           [ Client Requests ]
                                    │
                                    ▼
                         [ fieldops-api:8000 ]
                        (uvicorn 2 workers, non-root)
                        ├── Liveness Probe:  /health
                        └── Readiness Probe: /ready
                                    │
           ┌────────────────────────┼────────────────────────┐
           ▼                                                 ▼
 [ fieldops-postgres:5432 ]                        [ fieldops-redis:6379 ]
 (PostgreSQL 16 + Healthcheck)                     (Redis 7-alpine + Healthcheck)
 ├── Business State of Truth                       ├── Celery Message Broker
 ├── Shared LangGraph Checkpoints                  └── Celery Result Backend
 └── Named Volume: postgres_data                             │
           ▲                                                 │
           │                                                 │
           ├────────────────────────┬────────────────────────┤
           │                        │                        │
 [ fieldops-worker ]       [ fieldops-beat ]                 │
 (Celery Async Worker)    (Celery Periodic Beat)             │
           ▲                                                 │
           │                                                 │
 [ fieldops-prometheus:9090 ] ◄──────────────────────────────┘
           │ (Scrapes /metrics on fieldops-api)
           ▼
 [ fieldops-grafana:3000 ]
```

### 2. 无状态 API 与共享检查点升级 (Stateless API & Shared PostgresSaver)

- **为什么单机 SQLite 无法满足生产部署？**
  在多副本容器化部署（Multi-Replica API）或滚动更新（Rolling Restart）场景下，若使用本地 SQLite 存储 Checkpoint：
  1. **分脑与恢复失败**：请求由 Replica A 接入并在 Human Review 处中断（`interrupt`），当调度员在几分钟后调用 `/approval` 接口时，若流量被路由至 Replica B，Replica B 无法读取 Replica A 本地容器内的 SQLite 文件，导致报错 `WorkflowNotFoundError`。
  2. **数据丢失**：容器重启或重新调度时，未挂载卷的容器内部 SQLite 数据会随容器销毁而丢失。
- **PostgreSQL 共享检查点架构**：
  - 引入官方 `PostgresSaver`（基于 `psycopg_pool.ConnectionPool`）。
  - 设置 `CHECKPOINTER_BACKEND=postgres` 时，所有 API 副本共享存储于 PostgreSQL 中的 Checkpoints 表结构。任何副本均可在收到审核操作时，无缝恢复并推进中断的工作流。
  - 本地测试模式下支持 `CHECKPOINTER_BACKEND=sqlite` 或 `db_path=":memory:"`，兼顾开发测试的极致轻量与生产的高并发高可用。

### 3. 健康检查语义分离 (Liveness vs Readiness Probes)

| 探针 | 端点 | 检查范围 | 失败行为与编排器决策 |
| :--- | :--- | :--- | :--- |
| **存活探针 (Liveness)** | `GET /health` | 仅验证 Python 运行时与 FastAPI 事件循环是否正常响应，**绝不访问外部网络或数据库**。 | 若失败返回超时/非200，表明进程假死/死锁，Docker / K8s 立即重启该容器。 |
| **就绪探针 (Readiness)**| `GET /ready` | 检查关键依赖：PostgreSQL（核心，失败则 503）、Redis（降级，失败返回 200 degraded）。 | 若返回 503，流量网关（Nginx / ALB / Ingress）**停止分发业务流量**至该实例，但**绝不触发容器重启**，防止雪崩。 |

### 4. 独立数据库迁移策略 (Zero-Downtime Migration Strategy)

- **绝对禁止在 API / Worker 启动阶段执行迁移**：
  - 若多个 API 副本同时启动并执行 `alembic upgrade head`，将产生数据库 DDL 锁争用、死锁、甚至表结构破坏风险。
  - 迁移耗时较长时会导致 API 启动超时被探针直接杀死。
- **标准预部署迁移命令**：
  ```bash
  # 1. 启动基础存储服务并等待就绪
  docker compose up -d postgres redis
  
  # 2. 独立运行一次性数据迁移容器
  docker compose run --rm api alembic upgrade head
  
  # 3. 启动应用主服务
  docker compose up -d
  ```
- **Expand / Contract（双向兼容）模式**：
  - **Expand 阶段**：新增列或表（允许为 NULL 或有默认值），发布新版 API 代码。
  - **Transition 阶段**：数据双写/回填，旧版和新版代码均能正常读写。
  - **Contract 阶段**：全量升级完成后，在后续迁移中下线废弃字段或添加 NOT NULL 约束。

### 5. 持续集成与交付流水线 (GitHub Actions CI/CD Pipeline)

在 `.github/workflows/ci.yml` 中建立了完整的自动化检验体系，每次 PR 或主分支提交均自动执行：
1. **Runner & Services**：`ubuntu-latest` 搭配真实的 PostgreSQL 16 与 Redis 7 容器化服务。
2. **代码规范与类型检查**：`ruff check` 与 `ruff format --check`。
3. **单元与集成测试**：`pytest tests/ -v`（涵盖 207 项严苛测试用例）。
4. **数据库迁移校验**：针对真实 PostgreSQL 运行 `alembic upgrade head` 与 `scripts/seed.py`。
5. **确定性 Agent 质量评估**：自动运行 `run_workflow_eval.py`、`run_matching_eval.py`、`run_scheduling_eval.py`，基线劣化自动报警阻断合并。
6. **安全合规扫描**：`pip-audit` 检测第三方依赖库已知 CVE 漏洞。
7. **容器构建验证**：`docker build -t fieldops-agent:ci .` 验证多阶段缓存与镜像健康。

---

## 生产加固与性能测试体系 (Phase 18: Production Hardening & Load Testing)

### 1. 自动化性能测试与 Locust 压测套件 (`performance/`)
- **零真实 LLM API 成本规范**：压测阶段**绝对禁止调用真实商业 LLM API**。压测环境配置 `LOAD_TEST_MODE=true` 或 `LLM_PROVIDER=fake`，由高性能确定性 `FakeLLM` 引擎承载，杜绝 token 账单爆炸与上游供应商 TPM/RPM 限制。
- **高仿真故障注入能力**：`FakeLLM` 支持通过 API/代码注入 `fail_first_n`（模拟瞬时超时与重试）、`delay_seconds`（模拟慢响应风暴）、`permanent_failure`（模拟供应商全面宕机）。
- **Locust 场景覆盖**：
  - `read_api_load.py`：高并发只读路由吞吐测试（`/technicians`, `/service-requests`, `/health`）。
  - `service_request_load.py`：工单受理、FakeLLM 解析、入库与事务发件箱全流程写入负载测试。
  - `idempotency_load.py`：高频相同/相异 Key 并发轰炸，验证精准去重与冲突判定。
  - `appointment_conflict_load.py`：针对同一技师时段高并发抢占预约，验证行级锁排他与 0 超买超卖。

### 2. 分级分布式限流机制 (Rate Limiter)
- **Redis 滑动窗口计数**：通过 Redis Pipeline 实现微秒级原子操作，过期时间自动收敛。
- **Fail-Closed vs Fail-Open 架构决策**：
  - **认证入口 (`/auth/login`)**：采用 **Fail-Closed** 策略。当 Redis 宕机不可用时，直接拒绝登录请求（返回 503 / 429），杜绝撞库黑产攻击穿透至数据库。
  - **公开业务入口 (`POST /service-requests`)**：采用 **Fail-Open** 策略。当 Redis 宕机时，降级放行合法客户的报修请求，由 PostgreSQL 事务锁和数据库主库兜底，优先保障真实业务转化率。

### 3. 连接池调优与 Prometheus 饱和度监控
- **SQLAlchemy 生产连接池参数**：配置 `DB_POOL_SIZE`（默认 20）、`DB_MAX_OVERFLOW`（默认 30）、`DB_POOL_TIMEOUT`（默认 30s）。
- **指标实时打点**：在 `/metrics` 中导出 `db_pool_size`、`db_pool_checkedin`、`db_pool_checkedout`、`db_pool_overflow` 仪表盘指标。
- **Prometheus 告警规则**：在 `prometheus_alert_rules.yml` 中定义了连接池耗尽（`DbPoolSaturationHigh`）、Outbox 积压（`OutboxBacklogHigh`）、API 错误率超标（`HighHttp5xxRate`）、延迟劣化（`HighHttpLatencyP95`）等核心生产级告警规则。

### 4. 边界防御与安全守卫
- **请求体超长拦截**：配置 `MAX_REQUEST_MESSAGE_LENGTH = 2000` 字符。超过长度阈值的消息或畸形 JSON 在 FastAPI 路由层毫秒级快速返回 `422 Unprocessable Entity`，防止 LLM Prompt 注入和内存拒绝服务攻击（Denial of Service）。
- **安全数据重置工具**：`scripts/reset_performance_db.py` 内置生产数据库名称防御检测，防止误删生产数据。

---

## 跨角色集成与端到端业务闭环 (Phase 23: Cross-Role Integration + E2E Business Flow)

### 1. 三端统一业务架构
FieldOps Agent 在 Phase 23 实现了 Customer Portal、Operator Dashboard 与 Admin Console 的业务闭环：
- **Single Source of Truth**：以 PostgreSQL / SQLite 为事实核心，LangGraph Checkpoint 为工作流执行态，TanStack Query 驱动角色化 Projection。
- **Zero Dual-State Guarantee**：工单与预约双状态原子事务强绑定。取消或完成时，`ServiceRequest` 与 `Appointment` 始终在单一数据库事务内完成状态流转，杜绝“工单已取消而预约仍有效”的背离。
- **Policy Version Attribution**：工单创建时自动快照当时的 `dispatch_policy_version`、`sla_policy_version` 与 `sla_deadline`。管理员在 Admin Console 激活 v2 策略后，仅影响后续新工单，历史工单数据与 SLA 考核指标绝不被静默篡改。
- **Role-Specific Projections**：
  - **Customer Portal**：展示脱敏且安抚性的友好状态（如 `"Scheduling your visit"`, `"We are reviewing your request"`），过滤所有内部调度分值与技师排查细节。
  - **Operator Dashboard**：查看完整算法推荐依据、SLA 倒计时钟、多因素打分可解释性（Explainability）及 HITL 决策控件。
  - **Admin Console**：系统监控、技师技能与区域治理、调度策略版本回滚、未决升级统计（`open_escalations_count`）、只读审计日志检索。

### 2. 完整 10 步端到端业务闭环 (5~8 分钟面试演示流程)
参见完整演示指南：[`docs/demo.md`](docs/demo.md) 与状态模型：[`docs/status-model.md`](docs/status-model.md)。

```text
Admin 配置技师与策略
       ↓
Customer 多轮对话提报 (AC Fault)
       ↓
Agent 追问补齐 (Location & Time)
       ↓
Customer 确认工单 (Draft -> ServiceRequest)
       ↓
Operator 查看可解释性推荐并审批
       ↓
预约原子落库 (Appointment Booked + Outbox Event)
       ↓
Customer 查看预约技师与时间窗口
       ↓
系统审计轨迹与 Outbox 异步任务解耦
       ↓
Operator 标记上门服务完成
       ↓
Customer 查看最终完成状态 (Service completed)
```

### 3. 一键运行跨角色 E2E 自动化测试与验证脚本
```bash
# 1. 运行 Phase 23 核心跨角色端到端测试套件 (10 项全场景覆盖)
pytest tests/test_cross_role_e2e.py -v

# 2. 运行完整跨角色业务回归测试 (38 项全部通过)
pytest tests/test_cross_role_e2e.py tests/test_conversation_agent.py tests/test_customer_portal.py tests/test_admin_console.py -v

# 3. 运行无需人工干预的自动化真实 10 步演示脚本
python scripts/verify_phase23.py

# 4. 运行前端自动化测试 (36 项通过) 与生产构建
cd frontend && npm test -- --run && npm run build
```

---

## Phase 24: Service Lifecycle Completion (工单与预约全生命周期闭环)

在 Phase 24 中，FieldOps Agent 实现了从预约创建到上门履约的完整生命周期闭环，彻底摆脱了此前仅覆盖“创建与预约”阶段的局限，建立了统一的状态机引擎与严格的并发/幂等防护体系。详情参见：[`docs/service-lifecycle.md`](docs/service-lifecycle.md)。

### 1. 核心架构与设计原则
- **集中式生命周期状态引擎 (`ServiceLifecycleService`)**：
  将状态跃迁逻辑（Start, Complete, Cancel, Reschedule, Reassign）集中收敛于统一服务层，杜绝在各 API 路由中散落 `if status == ...`。
- **Zero Dual-State Guarantee**：
  `ServiceRequest` 与 `Appointment` 的状态迁移在单个数据库事务内强一致同步。预约进入 `in_progress` 或 `completed` 时，工单状态立即可见同步。
- **历史不可变替换链 (Replacement Chain)**：
  改约时不直接覆盖原有预约。原预约标记为 `cancelled` 并保存 `replaced_by_appointment_id`，新预约通过 `rescheduled_from_appointment_id` 反向追溯历史，保留完整的改约审计轨迹。
- **并发与竞态防护 (Race & Concurrency Protection)**：
  - **Double Complete Idempotency**：重复触发完成操作安全幂等，返回 HTTP 200 且绝不产生重复的 Outbox 事件或 Follow-up 消息。
  - **Complete vs Cancel Race**：已完成的工单严禁取消，后续取消操作统一拦截并返回 HTTP 409 Conflict (`AppointmentAlreadyCompletedError`)。
  - **Customer Guardrail**：客户严禁在线取消或改约处于 `in_progress`（技师已上门检修中）的服务，返回 HTTP 409 Conflict (`RequestNotCancellableError`)。
- **动态角色权限矩阵 (Dynamic Capabilities)**：
  后端基于实体当前状态与请求者角色，在返回数据中动态计算 `capabilities` 标志（`can_start`, `can_complete`, `can_cancel`, `can_reschedule`, `can_reassign`），前端界面精准展示可用操作按钮。

### 2. 自动化测试与验证
```bash
# 1. 运行 Phase 24 服务生命周期单元与转换规则测试 (7 项)
pytest tests/test_service_lifecycle.py -v

# 2. 运行 Phase 24 并发竞态与幂等性保护测试 (5 项)
pytest tests/test_lifecycle_concurrency.py -v

# 3. 运行完整跨角色与生命周期自动化测试套件 (50 项全部通过)
python -m pytest tests/test_cross_role_e2e.py tests/test_conversation_agent.py tests/test_customer_portal.py tests/test_admin_console.py tests/test_service_lifecycle.py tests/test_lifecycle_concurrency.py -v

# 4. 运行无需人工干预的 Phase 24 全生命周期真实流程验证脚本
python scripts/verify_phase24.py

# 5. 运行前端构建与测试
cd frontend && npm test -- --run && npm run build
```

---

## Phase 25: Real External Integration (Google Calendar)

在 Phase 25 中，FieldOps Agent 将外部集成层从纯内存的 `FakeCalendarClient` 升级为支持真实 Google 日历双向同步的 `GoogleCalendarClient`。通过适配器模式（Hexagonal Architecture），在未修改任何领域模型、工作流节点、预约生命周期及 Transactional Outbox 核心架构的前提下，完成了真正的第三方云服务对接。详情参见：[`docs/adr/0004-google-calendar-integration.md`](docs/adr/0004-google-calendar-integration.md)。

### 1. 核心架构与设计原则
- **严格适配器隔离 (Hexagonal Adapter Pattern)**：
  业务层（`AppointmentService`, `ServiceLifecycleService`, `LangGraph`）完全不感知 Google API，禁止直接 import `googleapiclient`。仅通过抽象契约 `CalendarClient` 与纯 Python DTO（`CalendarEventCreate`, `CalendarEventResult`）进行交互。
- **PostgreSQL 核心业务事实优先 (Failure Isolation)**：
  Google Calendar 故障（限流 429、服务中断 503、网络超时）绝不会回滚或影响 PostgreSQL 中已成立的预约事实。所有外部同步均由 Transactional Outbox + Celery 异步重试保证最终一致性。
- **提供商侧幂等与关联防护 (Provider-Side Idempotency via Correlation)**：
  使用 Google Calendar 私有扩展属性 `extendedProperties.private.fieldops_appointment_id`。在执行 `events.insert()` 前优先通过 `events.list(privateExtendedProperty=...)` 检索已存在的有效事件。即使用户在创建成功后、本地 DB 提交前发生 Worker 崩溃（Crash-after-provider-success），重试时也会精准重用已有事件，实现 0 重复日历日程。
- **幂等删除与全生命周期同步**：
  - **创建**：生成包含脱敏摘要与时区（`Asia/Tokyo`）的日历事件（`sendUpdates="none"` 避免测试外发邮件干扰）。
  - **取消**：调用 `events.delete`，遇到 HTTP 404/410 视为幂等成功。
  - **改期**：旧预约的日历事件取消，新预约创建独立日历事件，保留完整的历史审计链路。
- **轻量状态对齐巡检 (`CalendarReconciliationService`)**：
  定期或按需检测本地 `IntegrationRecord` 与 Google 日历真实状态差异（`unsynced_local`, `missing_remote`, `cancelled_appointment_active_remote`），支持一键自动修复对齐。

---

### 2. Google Calendar 配置指南 (Setup Guide)

#### 推荐认证方式：Google Cloud Service Account (服务账号)
为适用于无浏览器界面的后端独立后台服务（Server-to-Server），推荐使用服务账号方案：
1. 在 Google Cloud Console 创建项目并启用 **Google Calendar API**。
2. 在 **IAM & Admin > Service Accounts** 下创建服务账号，并生成 JSON Key（下载保存）。
3. **创建专用测试日历**：在 Google 日历中创建一个专门的测试日历（如 `FieldOps Staging Calendar`），进入该日历的“设置与共享”，在“与特定人员共享”中添加该服务账号邮箱，并授予 **“更改活动” (Make changes to events)** 权限。
4. 获取该日历的 **日历 ID**（通常为 `xxx@group.calendar.google.com` 或个人邮箱）。

#### 环境变量配置 (`.env` 或 Docker 环境变量)
```bash
# 激活 Google Calendar Provider (默认为 fake)
CALENDAR_PROVIDER=google

# 目标 Google 日历 ID
GOOGLE_CALENDAR_ID=your-test-calendar-id@group.calendar.google.com

# 方式 A：服务账号 JSON 文件路径 (挂载至容器或本地文件系统)
GOOGLE_SERVICE_ACCOUNT_FILE=/secrets/google-service-account.json

# 方式 B：直接通过环境变量传入服务账号 JSON 内容 (适用于云端无状态容器)
# GOOGLE_CREDENTIALS_JSON='{"type": "service_account", ...}'

# 方式 C：OAuth2 Refresh Token (个人开发者日历方案)
# GOOGLE_OAUTH_CLIENT_ID=your-client-id
# GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
# GOOGLE_OAUTH_REFRESH_TOKEN=your-refresh-token

# 开启离线模拟模式 (不发起真实网络请求，适合快速调试)
# GOOGLE_CALENDAR_DRY_RUN=true
```

> [!CAUTION]
> **安全守卫规范**：
> - 严禁将 `*.json` 密钥文件或 Refresh Token 提交至 Git 仓库。
> - 严禁在 Docker 构建阶段将密钥 `COPY` 入镜像。
> - Admin 控制台在展示日历信息时自动进行掩码脱敏（如 `us***@group.calendar.google.com`），绝不向前端返回密钥内容。

---

### 3. 自动化测试与验证

```bash
# 1. 运行 Phase 25 单元测试 (13 项全部通过)
pytest tests/test_google_calendar_unit.py -v

# 2. 运行 Phase 25 集成与并发故障测试 (8 项全部通过)
pytest tests/test_google_calendar_integration.py -v

# 3. 运行完整跨角色与外部集成自动化测试套件 (72 项全部通过)
python -m pytest tests/test_google_calendar_unit.py tests/test_google_calendar_integration.py tests/test_service_lifecycle.py tests/test_lifecycle_concurrency.py tests/test_cross_role_e2e.py tests/test_conversation_agent.py tests/test_customer_portal.py tests/test_admin_console.py -v

# 4. 运行全自动化独立验证脚本
python scripts/verify_phase25.py

# 5. 运行前端测试 (36 项通过) 与生产打包
cd frontend && npm test -- --run && npm run build
```

---

## 阶段说明与边界

**当前 Phase 25 明确完成内容**：
- ✅ 真实 Google Calendar API v3 适配器集成 (`GoogleCalendarClient`)。
- ✅ 生产环境防错守卫 (`ALLOW_FAKE_INTEGRATIONS_IN_PRODUCTION`)。
- ✅ 基于私有扩展属性的提供商侧关联与防重幂等 (`extendedProperties.private`)。
- ✅ 日历全生命周期管理（创建同步、404 幂等取消、改期历史分离同步）。
- ✅ 轻量巡检对齐服务 (`CalendarReconciliationService`) 与 Admin 控制台管理接口。

**当前 Phase 25 明确未实现的内容**：
- ❌ Gmail / SendGrid / SMTP 真实邮件发送（保持 FakeEmailClient 抽象）。
- ❌ Salesforce / HubSpot / Twilio / Slack / Microsoft Graph 对接。
- ❌ 评价与打分系统（Review / Rating System）。
- ❌ 在线支付与结算发票（Payments / Invoicing）。
- ❌ Kubernetes Helm Chart 与生产网格环境。








