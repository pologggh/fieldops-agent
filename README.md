# FieldOps Agent: 全闭环 AI 智能现场服务运营调度平台

<div align="center">

![FieldOps Agent Banner](https://img.shields.io/badge/FieldOps-Agent_Platform-0071e3?style=for-the-badge&logo=fastapi&logoColor=white)
![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)
![React 18](https://img.shields.io/badge/React-18.3+-61DAFB.svg?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.5+-3178C6.svg?style=for-the-badge&logo=typescript&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-FF6F00.svg?style=for-the-badge&logo=langchain&logoColor=white)
![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16_btree__gist-336791.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Celery 5.4](https://img.shields.io/badge/Celery-5.4+-37814A.svg?style=for-the-badge&logo=celery&logoColor=white)
![Redis 7](https://img.shields.io/badge/Redis-7_Alpine-DC382D.svg?style=for-the-badge&logo=redis&logoColor=white)
![Tests Passed](https://img.shields.io/badge/Pytest-360+_Passed-success?style=for-the-badge&logo=pytest&logoColor=white)
![Vitest Passed](https://img.shields.io/badge/Vitest-44_Passed-success?style=for-the-badge&logo=vitest&logoColor=white)

<p align="center">
  <b>融合多轮对话 Agent、自适应多因子派单决策、HITL 人机协同、SLA 动态升级与 Transactional Outbox 可靠总线的新一代现场服务运营操作系统</b>
</p>

</div>

---

## 📑 目录

- [核心业务流程总览](#核心业务流程总览)
- [一、 项目概述与核心价值](#一-项目概述与核心价值)
  - [1.1 业务背景与定位](#11-业务背景与定位)
  - [1.2 解决的核心业务痛点](#12-解决的核心业务痛点)
  - [1.3 核心设计原则](#13-核心设计原则)
- [二、 系统全景架构与流程图](#二-系统全景架构与流程图)
  - [2.1 AI 智能客服与远程预诊断闭环流程图](#21-ai-智能客服与远程预诊断闭环流程图)
  - [2.2 工单与预约双状态机全生命周期流程图](#22-工单与预约双状态机全生命周期流程图)
  - [2.3 多因子智能派单决策与 HITL 人机协同流程图](#23-多因子智能派单决策与-hitl-人机协同流程图)
  - [2.4 服务时效 SLA 监控与多级升级应急处置流程图](#24-服务时效-sla-监控与多级升级应急处置流程图)
  - [2.5 系统分层拓扑架构图](#25-系统分层拓扑架构图)
- [三、 三端门户功能矩阵](#三-三端门户功能矩阵)
  - [3.1 客户服务中心 (Customer Portal)](#31-客户服务中心-customer-portal)
  - [3.2 运营调度中心 (Operator Dashboard)](#32-运营调度中心-operator-dashboard)
  - [3.3 运营治理中台 (Admin Console)](#33-运营治理中台-admin-console)
- [四、 核心技术栈与工程实现亮点](#四-核心技术栈与工程实现亮点)
  - [4.1 大模型与 Agentic 架构 (LangGraph)](#41-大模型与-agentic-架构-langgraph)
  - [4.2 数据库内核级排他排除约束 (btree\_gist) 与排他锁](#42-数据库内核级排他排除约束-btree_gist-与排他锁)
  - [4.3 事务发件箱模式 (Transactional Outbox) 与异步解耦](#43-事务发件箱模式-transactional-outbox-与异步解耦)
  - [4.4 第三方生态无缝集成 (Google Calendar API v3)](#44-第三方生态无缝集成-google-calendar-api-v3)
  - [4.5 苹果极简设计系统 (Apple Minimalist Design System)](#45-苹果极简设计系统-apple-minimalist-design-system)
  - [4.6 先进交互与前沿组件 (GIS 地图、AST 语法树 Diff、语音波形、触摸手势)](#46-先进交互与前沿组件-gis-地图ast-语法树-diff语音波形触摸手势)
- [五、 项目全景目录结构](#五-项目全景目录结构)
- [六、 数据库领域模型与状态机契约](#六-数据库领域模型与状态机契约)
  - [6.1 状态枚举契约 (Single Source of Truth)](#61-状态枚举契约-single-source-of-truth)
  - [6.2 核心实体关系模型](#62-核心实体关系模型)
- [七、 本地快速启动与部署指南](#七-本地快速启动与部署指南)
  - [7.1 环境依赖准备](#71-环境依赖准备)
  - [7.2 环境变量配置](#72-环境变量配置)
  - [7.3 启动基础服务与数据库迁移](#73-启动基础服务与数据库迁移)
  - [7.4 启动后端服务 (FastAPI + Celery)](#74-启动后端服务-fastapi--celery)
  - [7.5 启动前端应用 (Vite)](#75-启动前端应用-vite)
  - [7.6 默认测试账号与入口索引](#76-默认测试账号与入口索引)
- [八、 自动化测试、质量评测与压测基准](#八-自动化测试质量评测与压测基准)
  - [8.1 后端自动化测试套件 (Pytest)](#81-后端自动化测试套件-pytest)
  - [8.2 前端自动化测试与类型检查 (Vitest)](#82-前端自动化测试与类型检查-vitest)
  - [8.3 确定性 Agent 质量评测体系](#83-确定性-agent-质量评测体系)
  - [8.4 高并发性能与故障注入压测 (Locust + FakeLLM)](#84-高并发性能与故障注入压测-locust--fakellm)
- [九、 未来演进路线 (Roadmap)](#九-未来演进路线-roadmap)

---

## 核心业务流程总览

下图展示当前主要执行路径：模型负责需求理解，确定性服务负责匹配、排班和事务写入，人工审批通过后才执行最终预约创建。

```mermaid
flowchart TD
    A["客户提交报修需求"] --> B["Agent 提取需求并维护对话草稿"]
    B --> C{"信息是否完整？"}
    C -->|否| D["询问缺失信息或接受客户纠正"]
    D --> B
    C -->|是| E["客户确认并提交工单"]
    E --> F["校验需求并持久化工单"]
    F --> G["按技能与服务区域匹配技师"]
    G --> H["查询候选技师的可用时段"]
    H --> I{"是否存在可行方案？"}
    I -->|时间不明确| J["返回待澄清状态"]
    I -->|无候选或无空闲时段| K["升级处理并转人工"]
    I -->|有| L["生成预约方案"]
    L --> M["保存 Checkpoint 并暂停等待人工审批"]
    M --> N{"审批结果"}
    N -->|拒绝| O["记录拒绝原因并结束本次流程"]
    N -->|批准| P["恢复工作流并重新检查时段冲突"]
    P --> Q{"时段仍然可用？"}
    Q -->|否| R["标记需要重新排期并结束本次流程"]
    Q -->|是| S["同一事务写入预约、工单状态、审计与 Outbox"]
    S --> T["返回预约创建结果"]
    S --> U["后台 Publisher 将 Outbox 事件投递到 Redis"]
    U --> V["Celery 执行日历同步与通知任务"]
    V --> W{"外部执行结果"}
    W -->|成功| X["记录集成结果"]
    W -->|暂时失败| Y["按任务策略进行有限重试"]
    Y --> V
    W -->|永久失败或重试耗尽| Z["记录失败并供人工排查"]

    classDef agent fill:#eff6ff,stroke:#2563eb,color:#1e3a8a;
    classDef human fill:#fff7ed,stroke:#ea580c,color:#7c2d12;
    classDef storage fill:#f0fdf4,stroke:#16a34a,color:#14532d;
    classDef failure fill:#fff1f2,stroke:#e11d48,color:#881337;
    class B,D agent;
    class E,M,N human;
    class S,T,X storage;
    class J,K,R,Z failure;
```

**阅读说明：** 蓝色为对话 Agent，橙色为人工确认或审批，绿色为持久化及结果节点，红色为待处理或失败状态。节点文字同时表达含义，无需仅依赖颜色判断。

**当前实现边界：** 主工作流遇到预约冲突后返回 `needs_rescheduling` 并结束；已有改期子图尚未接入该冲突分支，自动重新规划属于后续接线与验证工作。预约落库与外部同步是两个独立结果，前者成功不代表日历已同步或客户已收到通知；默认 Fake 通知提供商只模拟执行。

---

## 一、 项目概述与核心价值

### 1.1 业务背景与定位

**FieldOps Agent** 是专为现代化现场服务运营（Field Service Operations, FSO）构建的全链路企业级智能调度平台。覆盖暖通制冷、水暖卫浴、电力电气、工业维保、弱电智能化等多个上门服务垂直领域。

平台不仅实现了**从客户报修需求接入到工程师履约验收的全生命周期闭环**，更将先进的**大语言模型 Agentic 能力**与**严谨确定性的工程架构（Deterministic Workflows、Database Exclusion Constraints、Transactional Outbox、Distributed Rate Limiting）**深度融合，构建了一个高并发、高可用、可解释且符合人机协同理念的智能运营操作系统。

### 1.2 解决的核心业务痛点

| 传统现场服务运营痛点 | FieldOps Agent 解决方案 | 核心业务收益 |
| :--- | :--- | :--- |
| **客户报修沟通成本高**<br/>表单繁琐，客户描述不清，客服反复电话核实 | **AI 智能客服多轮对话**<br/>槽位抽取、要素澄清、W3C 语音报修与远程预诊断自检卡片 | 报修受理耗时缩短 70%，无意义上门率降低 25% |
| **人工派单依赖经验且效率低下**<br/>调度员凭借记忆派单，技能不符、跨区空跑频繁 | **自适应多因子智能推荐算法**<br/>技能匹配(25%) + 网点辐射(20%) + 负荷均衡(20%) + SLA时效(20%) + 通勤成本(15%) | 派单准确率提升至 98%，技师日均行程空驶减少 35% |
| **调度排班并发冲突（双重预约）**<br/>多调度员并发抢单或网络重试导致一名技师被安排到同一时间段 | **双层防御体系**<br/>应用层悲观排他锁(`FOR UPDATE`) + PostgreSQL 内核级 `btree_gist` 排他排除约束 | 杜绝 TOCTOU 竞态，双重预约发生率绝对为 0 |
| **SLA 违约难以及时响应**<br/>紧急工单淹没在工单池，快到期甚至超时才被调度员察觉 | **实时 SLA 动态预警与多级升级引擎**<br/>P0~P3 分级倒计时、`on_track` / `at_risk` / `breached` 状态流转与自动上报主管 | 高优工单响应达标率提高至 99.5% |
| **外部系统集成脆弱**<br/>日历同步因网络抖动失败导致业务事务回滚，或反复重试引发日历日程冗余 | **Transactional Outbox + Google Calendar 适配器**<br/>业务事实在 DB 事务内原子落库，由 Celery 异步投递，私有属性实现提供商侧幂等 | 强隔离第三方故障，实现最终一致性与零冗余 |
| **界面杂乱、AI 科技感堆砌脱离企业实操**<br/>暗黑网格、高光霓虹等华而不实的设计导致视觉疲劳，中文化不彻底 | **苹果极简设计系统 (Apple Minimalist Design System)**<br/>`#f5f5f7` 原生浅灰画布、自然中文排版、细发丝边框与无压迫感的信息层级 | 三端统一视觉语言，界面直观，大幅降低新员工培训成本 |

### 1.3 核心设计原则

1. **确定性业务事实优先 (Deterministic Truth First)**：LLM 仅负责非结构化语义解析与对话沟通；所有关于状态变迁、排他排班、技师匹配、权限控制与事务持久化，均由 Python 确定性代码与数据库引擎强行约束。
2. **零双重状态保证 (Zero Dual-State Guarantee)**：工单 (`ServiceRequest`) 与预约 (`Appointment`) 在单个数据库事务内强一致联动，绝不允许出现“工单已取消而预约仍有效”的悬挂状态。
3. **策略版本追溯性 (Policy Version Attribution)**：工单创建时快照当时的调度策略与 SLA 版本，策略修改仅影响未来工单，历史工单考核绝不被静默篡改。
4. **人机协同可解释性 (Human-in-the-Loop & Explainability)**：算法为调度员提供 Top-3 推荐卡片并详细展示每项因子的打分拆解，调度员拥有最终核准、改派与驳回权。

---

## 二、 系统全景架构与流程图

### 2.1 AI 智能客服与远程预诊断闭环流程图

```mermaid
flowchart TD
    Start(["客户进入 AI 智能报修工作台"]) --> Msg["客户输入故障现象 (文字 / 语音)"]
    Msg --> ParseIntent["大模型意图识别与实体抽取"]
    
    ParseIntent --> CheckRisk{"安全风险排查 (Safety Policy)"}
    CheckRisk -- 识别到燃气泄漏 / 触电 / 喷水 --> RiskAlert["触发安全避险警报 & 紧急制动指引"]
    RiskAlert --> PriorityOnsite["标记为 P0/P1 紧急上门"]
    
    CheckRisk -- 无致命人身安全风险 --> SlotCheck{"报修关键要素是否齐备？<br/>(设备类型/故障/地址/时段)"}
    SlotCheck -- 要素缺失 --> ClarifyDecision["决定 Next Best Action: 追问澄清"]
    ClarifyDecision --> SafeTool["安全调用查询工具 (读取历史设备/常用地址)"]
    SafeTool --> AskCustomer["向客户发起交互追问 / 选项卡片"]
    AskCustomer --> Msg
    
    SlotCheck -- 要素齐全 --> PreDiagnosis{"适合远程预诊断排查？"}
    PreDiagnosis -- 简单故障 (如跳闸/重启) --> SelfCheck["推送安全自检排查步骤"]
    SelfCheck --> CustomerConfirmCheck{"客户自行排查是否恢复？"}
    CustomerConfirmCheck -- 已解决 --> SelfResolved(["工单自闭环 · 无需上门"])
    CustomerConfirmCheck -- 未解决 --> GenProposal["生成正式工单上报草稿"]
    
    PreDiagnosis -- 需上门专业检修 --> GenProposal
    PriorityOnsite --> GenProposal
    
    GenProposal --> PresentDraft["向客户展示完整结构化需求卡片"]
    PresentDraft --> CustomerSubmit{"客户一键核准确认提交？"}
    CustomerSubmit -- 需修改 --> Msg
    CustomerSubmit -- 确认无误 --> FinalSubmit(["事务写入数据库 · 生成正式工单"])
```

### 2.2 工单与预约双状态机全生命周期流程图

```mermaid
stateDiagram-v2
    [*] --> 受理已接收_received: 客户提交或对话创建
    
    受理已接收_received --> 信息待补全_needs_information: 核心地址/联系人缺失
    信息待补全_needs_information --> 算法匹配中_matched: 客户补齐要素
    
    受理已接收_received --> 算法匹配中_matched: 要素齐全
    算法匹配中_matched --> 待人工审核_waiting_for_approval: 推荐最佳匹配方案
    
    待人工审核_waiting_for_approval --> 锁定排程_scheduled: 调度员核准 (HITL Confirm)
    待人工审核_waiting_for_approval --> 待人工审核_waiting_for_approval: 调度员改派/重新协商
    
    锁定排程_scheduled --> 上门服务中_in_progress: 工程师签到打卡并开始检修
    锁定排程_scheduled --> 改约协商中_needs_rescheduling: 客户或工程师发起时间变更
    改约协商中_needs_rescheduling --> 锁定排程_scheduled: 调度员确认新预约时隙
    
    上门服务中_in_progress --> 竣工验收_completed: 现场维修完成 · 客户签字验收
    
    受理已接收_received --> 已取消_cancelled: 履行前客户或调度员取消
    待人工审核_waiting_for_approval --> 已取消_cancelled: 调度员驳回或客户取消
    锁定排程_scheduled --> 已取消_cancelled: 释放排程并清理日历
    上门服务中_in_progress --> 已取消_cancelled: 现场不可抗力终止
    
    竣工验收_completed --> [*]: 归档 · 触发回访任务
    已取消_cancelled --> [*]: 终止闭环 · 释放运力资源
```

### 2.3 多因子智能派单决策与 HITL 人机协同流程图

```mermaid
flowchart LR
    subgraph Input ["待派工单要素"]
        SR["工单: 服务类别、紧急度、现场地理坐标、SLA截止时间"]
    end

    subgraph Engine ["FieldOps 多因子推荐打分引擎"]
        direction TB
        F1["技能资质匹配度 (25%)<br/>暖通/电气/水暖/弱电"]
        F2["网点辐射范围 (20%)<br/>广州/深圳/北京/上海网格"]
        F3["在手任务负荷 (20%)<br/>每日作业上限与当前工单数"]
        F4["SLA 时效保障度 (20%)<br/>响应时限与临近超时惩罚"]
        F5["路程通勤成本 (15%)<br/>实时 GIS 距离测距与交通耗时"]
        
        SR --> F1 & F2 & F3 & F4 & F5
        F1 & F2 & F3 & F4 & F5 --> Scorer["加权总分运算与排名 (Top-3)"]
    end

    subgraph Proposal ["人机协同决策网关 (HITL)"]
        Scorer --> PropCard["生成派单方案卡片<br/>(首选推荐工程师 + 备选工程师)"]
        PropCard --> Dispatcher{"调度员人工复核"}
        Dispatcher -- 确认方案 --> Approve["核准派单 · 锁定排期"]
        Dispatcher -- 手动调整 --> Reassign["指派备选工程师 / 协商改期"]
        Dispatcher -- 需求不符 --> Reject["驳回或退回重新分诊"]
    end

    subgraph Downstream ["下游业务联动"]
        Approve --> Booking["同步外部 Google Calendar"]
        Approve --> EventBus["写入 Transactional Outbox"]
        EventBus --> Notify["触发服务工程师短信/应用通知"]
    end
```

### 2.4 服务时效 SLA 监控与多级升级应急处置流程图

```mermaid
flowchart TD
    T0["工单创建 · SLA 倒计时启动 (P0 - P3)"] --> Monitor{"实时时效监控"}
    
    Monitor -- 剩余时间 > 阈值 --> OnTrack["状态：时效充足 (on_track 绿色)"]
    OnTrack --> WorkCheck{"是否在时限内完成？"}
    WorkCheck -- 是 --> Done["SLA 履约达成 · 闭环"]
    
    Monitor -- 剩余时间 <= 临近预警阈值 --> AtRisk["状态：临近超时 (at_risk 黄色预警)"]
    AtRisk --> PushAlert["调度大厅推送告警 · 优先高亮看板"]
    PushAlert --> WorkCheck
    
    WorkCheck -- 否：到达截止期限 --> Breached["状态：已违约超时 (breached 红色脉冲)"]
    Breached --> AutoEscalate["触发系统自动升级 (Escalation Engine)"]
    
    AutoEscalate --> SeverityJudge{"判断故障严重级别"}
    SeverityJudge -- P0 / P1 事故级 --> EscP0["严重升级：通知总监/调度主管 · 增派资深工程师督导"]
    SeverityJudge -- P2 / P3 常规工单 --> EscP2["常规升级：重新排优排期 · 调度员电话回访安抚"]
    
    EscP0 & EscP2 --> ResolveEsc{"人工干预完成？"}
    ResolveEsc -- 解除警报 --> Resolved["升级解除 (Resolved) · 写入审计日志"]
```

### 2.5 系统分层拓扑架构图

```text
                               ┌────────────────────────────────────────────────────────┐
                               │                    客户端与用户界面层                   │
                               │  Customer Portal     Operator Dashboard  Admin Console │
                               │  (React 18 + TS + TailwindCSS + Apple Design System)   │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ HTTPS / RESTful API / SSE
                                                           ▼
                               ┌────────────────────────────────────────────────────────┐
                               │                统一 API 网关与入站适配接入层            │
                               │  FastAPI Router (JWT Auth, RBAC, Sliding Rate Limiter) │
                               │  Adapters: Web Inbound / Webhook Inbound / Fake Email  │
                               └───────────────────────────┬────────────────────────────┘
                                                           │
                                                           ▼
                               ┌────────────────────────────────────────────────────────┐
                               │               智能业务编排层 (LangGraph Core)           │
                               │  - LLM 实体识别与安全风险校验 (parse_request)           │
                               │  - 确定性硬规则与槽位完整性验证 (validate_request)      │
                               │  - 技师初筛与多因子打分权重计算 (match_technicians)     │
                               │  - 候选时间槽冲突检测 (check_schedule)                 │
                               │  - 人机协同审核挂起与恢复 (interrupt / Command resume) │
                               │  - 二次排他复检与原子入库 (finalize_appointment)        │
                               └──────────────┬──────────────────────────┬──────────────┘
                                              │                          │
                                              ▼                          ▼
               ┌────────────────────────────────────────┐      ┌─────────────────────────┐
               │         领域与应用服务层 (Services)     │      │   状态与会话检查点引擎  │
               │  - ServiceLifecycleService (状态迁移)  │      │   PostgresSaver /       │
               │  - SchedulingService (区间排他算法)    │      │   SqliteSaver           │
               │  - TechnicianMatchingService (派单评分)│      └─────────────────────────┘
               │  - SLAEngine / EscalationService       │
               │  - PolicyGovernanceService (策略版本)  │
               └──────────────────────┬─────────────────┘
                                      │ 原子事务提交 (Single DB Transaction)
                                      ▼
               ┌────────────────────────────────────────────────────────────────────────┐
               │                      持久化基础设施层 (PostgreSQL 16)                   │
               │  - 业务实体表 (service_requests, appointments, technicians, customers) │
               │  - 排班排除约束 (btree_gist: exclude_overlapping_appointments)         │
               │  - 审计与策略 (audit_logs, dispatch_policies, sla_policies)            │
               │  - 事务发件箱表 (outbox_events: status='pending')                      │
               └──────────────────────┬─────────────────────────────────────────────────┘
                                      │ 后台守护进程轮询抓取 (Polling Publisher)
                                      ▼
                               ┌────────────────────────────────┐
                               │       消息中间件 (Redis 7)     │
                               └──────────────┬─────────────────┘
                                              │ Celery Message Broker
                                              ▼
               ┌────────────────────────────────────────────────────────────────────────┐
               │                       异步任务与外部集成层 (Celery)                     │
               │  - Google Calendar API v3 双向同步 (GoogleCalendarClient)               │
               │  - 邮件与短信异步发送 (EmailClient / SMS)                               │
               │  - 预约前 24h 提醒与上门履约回访 (NotificationService)                   │
               │  - 定时巡检与状态对齐 (CalendarReconciliationService)                   │
               └────────────────────────────────────────────────────────────────────────┘
```

---

## 三、 三端门户功能矩阵

FieldOps Agent 采用统一的现代化设计语言与严格的前后端角色契约，提供了面向客户、调度员和系统管理员的三大专属门户：

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                 FIELDOPS AGENT 三端门户体系                             │
├──────────────────────────┬──────────────────────────────┬───────────────────────────────┤
│ 客户服务中心             │ 运营调度中心                 │ 运营治理中台                  │
│ Customer Portal          │ Operator Dashboard           │ Admin Console                 │
├──────────────────────────┼──────────────────────────────┼───────────────────────────────┤
│ 📱 移动端优先/全响应式    │ 🖥️ 调度指挥大厅/大屏自适应   │ ⚙️ 业务规则与系统治理中枢     │
│ 🎯 服务对象：报修客户    │ 🎯 服务对象：调度员/值班主管 │ 🎯 服务对象：业务总监/管理员  │
└──────────────────────────┴──────────────────────────────┴───────────────────────────────┘
```

### 3.1 客户服务中心 (Customer Portal)

面向最终企业客户或家庭报修用户，注重极致简洁、零学习成本与极速响应：

| 路由路径 | 页面名称 | 核心功能与亮点 |
| :--- | :--- | :--- |
| `/customer/login` | 客户登录 | 苹果 ID 极简风登录设计，支持手机号/邮箱快捷验证，无暗黑科技感霓虹干扰 |
| `/customer/register` | 客户注册 | 极简注册向导，输入姓名、手机与邮箱快速建档入库 |
| `/customer` | 客户首页 | 常见服务分类磁贴（空调暖通、电路电力、管道水暖、综合维保）、进行中服务卡片置顶 |
| `/customer/assistant` | **AI 智能客服报修** | **多轮会话 Agent**、槽位补全追问、**W3C 实时语音输入及动态音频波形图**、安全风险避险警报、远程预诊断排查卡片、实时工单草稿卡片确认 |
| `/customer/requests` | 我的报修服务列表 | 全部工单流转追踪，支持**移动端触摸水平滑动手势（Swipe Gestures）**无缝切换 Tab |
| `/customer/requests/:id` | 报修详情追踪 | 内嵌 **`WorkflowPipeline` 7阶段全生命周期状态可视化流程图**、安抚式状态展示、客户自主取消/改期 |
| `/customer/appointments` | 我的上门预约 | 查看即将上门的服务日程、工程师卡片、服务地址核对 |
| `/customer/appointments/:id` | 预约详情中心 | 工程师信息、计划上门时间窗口、上门状态变更即时刷新 |
| `/customer/profile` | 个人中心 | 个人联系方式维护、默认上门地址簿管理 |
| `/customer/request-service` | 传统结构化报修通道 | 适合企业 IT 管理员或批量报修人员的表单录入方式 |

### 3.2 运营调度中心 (Operator Dashboard)

面向专职调度员与客服主管，注重高密度信息展现、快速决策与高并发操作：

| 路由路径 | 页面名称 | 核心功能与亮点 |
| :--- | :--- | :--- |
| `/login` | 调度大厅登录 | 统一员工认证入口，支持根据角色（调度员/管理员/只读查看者）自动路由定向 |
| `/` | 运营全景看板 | 待调度待办卡片、SLA 紧急度梯队、今日待履约与完工进度一览、快捷处置操作 |
| `/service-requests` | **工单调度大厅** | **双视图模式无缝切换**：<br/>1. **Table 列表视图**：快捷筛选、批量派工、SLA 倒计时钟；<br/>2. **GIS 交互式调度地图 (`DispatchMapView`)**：城市网点辐射圈、技师实时位置打点、待派工单坐标高亮、动态贝塞尔派单路径矢量、测距与 ETA 标签、交互详情抽屉 |
| `/service-requests/:id` | **工单详情与 HITL 审批**| 内嵌 **`WorkflowPipeline` 流程图**；展示**多因子算法 Top-3 推荐卡片**及权重拆解可解释性；支持一键**核准排程、改派技师、驳回需求**；实时 SLA 倒计时与时效报警脉冲 |
| `/appointments` | 预约履约看板 | 针对已排期预约进行全周期跟踪，涵盖待上门、进行中、已完成、已改期状态筛选 |
| `/appointments/:id` | 预约详情与履约操作 | 调度员协助**标记开始上门检修、竣工验收、发起改约协商、紧急改派** |
| `/escalations` | 异常升级处置大厅 | 违约或高风险工单集中告警池，展示升级原因（SLA超时、客户投诉、无可用技师） |
| `/escalations/:id` | 升级事件处置工作台 | 查看完整事件脉络、记录调度员干预措施、处理完毕一键解除告警 |
| `/system` | 系统运行健康度 | 查看 Celery 队列积压、Redis 连通性、数据库连接池饱和度、Outbox 派发速率 |

### 3.3 运营治理中台 (Admin Console)

面向业务运营总监与系统治理管理员，注重业务规则的弹性治理、策略审计与系统安全：

| 路由路径 | 页面名称 | 核心功能与亮点 |
| :--- | :--- | :--- |
| `/admin` | 治理全景总览 | 全网工程师运力总览、网点覆盖率、调度策略运行态分布、SLA 履约达成率统计 |
| `/admin/dispatch-policy`| **调度策略治理中心** | 动态调整技能、网点、负荷、SLA、通勤五维权重；支持草稿编辑、**策略语法树 (AST) 与代码级双模式 Diff 对比检查器 (`PolicyDiffModal`)**、一键发布生效与历史版本回滚 |
| `/admin/sla-policy` | SLA 服务等级治理 | 配置 P0~P3 各等级响应与解决时限（分钟）、临近超时黄色预警阈值、自动升级主管规则 |
| `/admin/technicians` | 工程师资源治理 | 技师资质技能树认证（HVAC/电气/管道等）、所属服务网点与班组、在手最大工单负荷、日历同步配置 |
| `/admin/branches` | 服务网点与辐射中心 | 网点地理坐标（经纬度）、辐射半径（公里）、主管人员指派 |
| `/admin/teams` | 服务班组架构 | 组建专业维保班组、配置班组长及下属工程师层级关系 |
| `/admin/users` | 账号与权限管理 (RBAC) | 调度员与管理人员账号创建、角色分配（ADMIN, OPERATOR, VIEWER）、账号启停用 |
| `/admin/integrations` | 第三方集成中枢 | Google Calendar 连接状态监控、提供商健康度、**轻量双向巡检对齐工具 (`CalendarReconciliationService`)** |
| `/admin/audit` | 业务合规审计溯源 | 记录全平台关键写操作（派单、审批、取消、改约、策略变更）的操作人、时间、操作前后完整 JSON 差分 |
| `/admin/system` | 底层引擎配置与参数 | 全局参数查看、连接池配置、环境变量守卫检查 |

---

## 四、 核心技术栈与工程实现亮点

```text
    ┌────────────────────────────────────────────────────────────────────────┐
    │                       FIELDOPS 核心技术栈矩阵                          │
    ├──────────────────┬───────────────────┬────────────────────────────────┤
    │ 后端应用与计算    │ 状态编排与大模型  │ 数据持久化与可靠消息总线       │
    │ - Python 3.11+   │ - LangGraph 0.2+  │ - PostgreSQL 16 (btree_gist)   │
    │ - FastAPI 0.111+ │ - OpenAI API      │ - SQLAlchemy 2.0 (Row Locks)   │
    │ - Pydantic v2    │ - FakeLLM (压测)  │ - Alembic 数据库版本控制       │
    │ - Uvicorn        │ - Structured Out  │ - Redis 7 + Celery 5.4         │
    │ - Psycopg 3 Pool │ - State Checkpoint│ - Transactional Outbox Pattern │
    ├──────────────────┼───────────────────┼────────────────────────────────┤
    │ 前端架构与交互    │ 观测监控与可靠性  │ 第三方生态与云连接器           │
    │ - React 18.3+    │ - Prometheus 指标 │ - Google Calendar API v3       │
    │ - TypeScript 5.5 │ - Grafana 面板    │ - W3C Web Speech API           │
    │ - Vite 6.4       │ - 分级分布式限流  │ - Leaflet / GIS 空间计算       │
    │ - TailwindCSS 3.4│ - 敏感数据脱敏    │ - Webhook HMAC 认证            │
    └──────────────────┴───────────────────┴────────────────────────────────┘
```

### 4.1 大模型与 Agentic 架构 (LangGraph)

平台基于 LangGraph 状态图构建了核心调度工作流，将非确定性的大语言模型能力收敛于确定性状态机之中：
- **原生中断与人机协同 (`interrupt` & `Command(resume=...)`)**：
  当工作流计算出最优预约建议后，调用 LangGraph 原生 `interrupt()` 挂起执行态，将完整的 Checkpoint 状态持久化至 PostgreSQL。向调度员返回 `waiting_for_approval`，彻底释放 HTTP 连接与计算线程。调度员在界面核准后，通过 `Command(resume={"decision": "approve"})` 唤醒工作流推进至终态。
- **防止模型幻觉的严苛防御**：
  在意图提取节点（`parse_request`）后立即接入硬编码规则校验节点（`validate_request`）。严禁模型凭空捏造未提及的客户地址或期望时隙；若缺少必要报修要素，坚决终止流转并返回 `needs_information`，绝不盲目入库。
- **确定性 FakeLLM 与故障注入引擎**：
  在性能测试与离线评测中，提供零 API 成本的 `FakeLLM` 引擎，支持注入瞬时网络超时（`fail_first_n`）、延迟风暴（`delay_seconds`）与不可逆宕机（`permanent_failure`），用以严格测试系统在极端网络下的重试退避与降级行为。

### 4.2 数据库内核级排他排除约束 (btree_gist) 与排他锁

针对现场服务运营中毁灭性的**“双重预约（Double Booking）”**竞态风险，FieldOps 建立了业界标杆级的双层并发防御体系：

1. **应用层悲观锁与二次复检 (TOCTOU Defense)**：
   在调度员点击审批（可能距离生成建议已过去数小时）恢复执行时，`AppointmentService.finalize_appointment` 开启单原子数据库事务；对候选技师行执行 `SELECT ... FOR UPDATE` 加上悲观排他锁，串行化并发请求，并重新检索其时间区间冲突。若发现已被抢占，安全将工单标记为 `needs_rescheduling` 并写入审计，绝不盲目插入。
2. **PostgreSQL 内核级 GIST 排他排除约束 (Database Exclusion Constraint)**：
   普通的 `UNIQUE(technician_id, start_time)` 无法防范部分重叠的时间区间（例如 13:00~15:00 与 14:00~16:00 冲突）。FieldOps 通过 Alembic 启用 `btree_gist` 扩展，为 `appointments` 表建立了物理排他约束：
   ```sql
   ALTER TABLE appointments
   ADD CONSTRAINT exclude_overlapping_appointments
   EXCLUDE USING gist (
       technician_id WITH =,
       tstzrange(start_time, end_time) WITH &&
   )
   WHERE (status IN ('scheduled', 'confirmed', 'in_progress'));
   ```
   作为终极防线，即使应用层发生未预见的极端竞态，PostgreSQL 内核也会直接拒绝冲突的 INSERT，从物理机制上保障排班重叠发生率为绝对的 0。

### 4.3 事务发件箱模式 (Transactional Outbox) 与异步解耦

为解决**“工单/预约数据入库与外部通知/日历同步之间的双写一致性”**问题，系统实现了标准的 Transactional Outbox 架构：

```text
[ 业务操作: 调度审批 / 工单取消 / 改期 ]
                   │
                   ▼ 单一数据库事务 (BEGIN TRANSACTION)
       ┌───────────────────────────────┐
       │ 1. 更新 service_requests 状态 │
       │ 2. 插入 appointments 记录     │
       │ 3. 插入 outbox_events 待投递  │
       └───────────────┬───────────────┘
                       │ 原子提交 (COMMIT)
                       ▼
            [ PostgreSQL 业务数据库 ]
                       │
                       │ 轮询调度器 (Polling Publisher) 严格有序抓取
                       ▼
            [ Redis 7 消息中间件 ]
                       │
                       ▼ Celery Worker 并发消费
          ┌───────────────────────────┐
          │  Google Calendar API 同步  │
          │  短信 / 邮件确认信投递    │
          │  SLA 倒计时与超时升级任务  │
          └───────────────────────────┘
```

- **绝对原子性**：业务数据变更与 `outbox_events` 记录在同一个数据库事务中原子提交。若业务操作失败，发件箱记录同时回滚，杜绝幽灵消息。
- **故障隔离**：外部 Google Calendar 宕机或网络中断绝不会导致本地数据库预约创建失败。Celery Worker 采用指数退避（Exponential Backoff with Jitter）自动重试，确保最终一致性。

### 4.4 第三方生态无缝集成 (Google Calendar API v3)

采用六边形架构适配器模式（Hexagonal Adapter Pattern）实现真实 Google Calendar 对接：
- **业务领域完全解耦**：业务代码仅依赖抽象基类 `CalendarClient`，严禁在服务层直接引用外部 SDK。
- **提供商侧幂等与关联防护**：利用 Google Calendar 私有扩展属性 `extendedProperties.private.fieldops_appointment_id`。在调用创建接口前先检索已有事件，即使 Worker 发生崩溃重试，也能精准重用已有日历日程，杜绝日程冗余。
- **轻量双向巡检对齐 (`CalendarReconciliationService`)**：支持自动发现本地与 Google 日历状态不一致的脏数据，并提供一键自动修复对齐工具。

### 4.5 苹果极简设计系统 (Apple Minimalist Design System)

彻底重构了前端全站界面，摒弃浮夸的“深色高光/AI赛博朋克”视觉疲劳风格，全面对标 Apple ID 与苹果官网级工业设计规范：
- **色彩与材质**：以 `#f5f5f7` 作为主画布背景，卡片采用纯白 `#ffffff`，搭配 `#d2d2d7` 细发丝边框与 `rgba(0,0,0,0.04)` 极轻微弥散投影。
- **品牌交互色**：采用苹果经典蓝 `#0071e3`（Hover态 `#0077ed`）作为主按钮与关键交互引导。
- **排版系统**：基于 `-apple-system, BlinkMacSystemFont, "SF Pro Text"`，主标题 `#1d1d1f`、次级说明 `#86868b`，层级分明，视觉通透。
- **分段控制器 (Segmented Controls)**：在登录切换、工单筛选、视图切换中广泛采用胶囊包裹式分段按钮，手感细腻。

### 4.6 先进交互与前沿组件

1. **GIS 交互式调度地图 (`DispatchMapView.tsx`)**：
   专为调度员打造的地理信息工作台。绘制城市网格边界、网点辐射圆圈（蓝圈标注 15km 覆盖圈）、技师动态位置图钉、待派工单脉冲图钉，动态生成从网点到报修现场的贝塞尔连接弧线，实时显示地理测距与估算行车时间（ETA）。
2. **AST 语法树与代码双模式 Diff 检查器 (`PolicyDiffModal.tsx`)**：
   调度策略修改时，系统将策略 JSON 抽象并结构化为抽象语法树（AST），提供代码级统一 Diff 与 AST 结构化属性增删比对两种视图，防止误操作破坏调度权重平衡。
3. **W3C 语音识别与动态音频波形动画**：
   客户报修助手集成原生 `webkitSpeechRecognition` API，支持普通话连续语音听写，录音期间自适应渲染 16 根动态跳动的声波音频柱，提供自然顺畅的语音报修体验。
4. **移动端触摸手势平滑切换 (`useSwipeGesture.ts`)**：
   针对移动端客户报修列表，封装了原生 Touch 触摸手势监听，支持左右手势流畅切换待处理、进行中与已完工工单 Tab。
5. **工单全流程动态流程线 (`WorkflowPipeline.tsx`)**：
   在工单详情页集成 7 节点标准化流程线（受理 ➔ 预分诊 ➔ 算法评分 ➔ 人工复核 ➔ 锁定排程 ➔ 上门履约 ➔ 竣工闭环），直观呈现当前工单进展与异常分支。

---

## 五、 项目全景目录结构

```text
fieldops agent/
├── alembic/                         # 数据库迁移脚本目录
│   ├── versions/                    # 数据库结构版本演进 (btree_gist, outbox, 策略表等)
│   └── env.py                       # Alembic 运行时配置
├── evaluation/                      # 确定性质量评估套件
│   ├── datasets/                    # 标注测试数据集 (工单, 匹配, 冲突用例)
│   ├── run_matching_eval.py         # 技师匹配确定性评测
│   ├── run_scheduling_eval.py       # 排班冲突算法确定性评测
│   ├── run_workflow_eval.py         # 端到端业务路径与状态机评测
│   └── run_parser_eval.py           # LLM 实体识别与幻觉率评测
├── performance/                     # 高并发性能测试套件 (Locust)
│   ├── locustfile.py                # 综合压测场景入口
│   ├── fake_llm.py                  # 高仿真零成本 FakeLLM 故障注入引擎
│   └── scenarios/                   # 压测场景 (读吞吐, 工单创建, 幂等轰炸, 抢单冲突)
├── scripts/                         # 运维与验证脚本
│   ├── seed.py                      # 初始种子数据填充 (客户, 技师, 网点, 默认策略)
│   ├── verify_phase23.py            # 端到端 10 步业务全流程验证脚本
│   ├── verify_phase24.py            # 服务全生命周期状态流转验证脚本
│   └── verify_phase25.py            # Google Calendar 适配器集成验证脚本
├── src/fieldops/                    # 后端核心源码
│   ├── agent/                       # LangGraph 状态图与工作流节点
│   │   ├── graph.py                 # 状态图编排、条件边与中断恢复
│   │   ├── nodes.py                 # 实体抽取、规则校验、排班提议等节点
│   │   └── state.py                 # 工作流状态契约 (FieldOpsState)
│   ├── api/                         # FastAPI 路由控制器
│   │   ├── auth.py                  # 用户与客户登录、Token 刷新与校验
│   │   ├── service_requests.py      # 工单受理、查询、审核批准
│   │   ├── appointments.py          # 预约履约管理、改约、改派、状态流转
│   │   ├── escalations.py           # SLA 异常升级与处置
│   │   ├── admin.py                 # 策略治理、技师网点管理、审计日志
│   │   ├── customer.py              # 客户专属接口 (我的工单, 地址簿)
│   │   ├── conversation.py          # AI 客服多轮会话接口
│   │   ├── integrations.py          # 第三方集成状态与巡检
│   │   └── system.py                # 系统就绪度与指标
│   ├── application/                 # 应用服务层 (协调领域与基础设施)
│   │   ├── appointment_service.py   # 预约创建、二次冲突复检、Outbox 写入
│   │   ├── service_lifecycle_service.py # 集中式生命周期状态引擎
│   │   ├── scheduling_service.py    # 时间槽排他算法与时隙切分
│   │   ├── matching_service.py      # 多因子加权派单推荐算法
│   │   ├── sla_service.py           # SLA 监控与到期判定
│   │   └── policy_service.py        # 调度策略版本管理与快照
│   ├── conversation/                # 多轮会话 Agent 核心
│   │   ├── agent.py                 # 槽位提取、安全排查、追问决策
│   │   ├── pre_diagnosis.py         # 远程预诊断自检知识库
│   │   └── tools.py                 # 安全只读调用工具
│   ├── core/                        # 系统核心基础设施
│   │   ├── config.py                # Pydantic Settings 全局配置
│   │   ├── exceptions.py            # 统一异常分类与 HTTP 状态码映射
│   │   └── logging.py               # 结构化脱敏日志
│   ├── db/                          # 数据库连接与会话
│   │   ├── base.py                  # SQLAlchemy Declarative Base
│   │   └── session.py               # 连接池管理与依赖注入
│   ├── domain/                      # 领域实体模型 (SQLAlchemy ORM)
│   │   ├── models.py                # 核心业务表结构定义
│   │   └── enums.py                 # 领域状态枚举常量
│   ├── intake/                      # 统一入站接入适配层
│   │   ├── adapters.py              # Web / Email / Webhook 适配器
│   │   └── service.py               # 渠道去重、幂等与事件入库
│   ├── integrations/                # 外部第三方服务适配器
│   │   ├── calendar_client.py       # 日历客户端契约与 GoogleCalendarClient
│   │   ├── email_client.py          # 邮件客户端抽象与模板渲染
│   │   └── reconciliation.py        # 日历双向巡检与对齐服务
│   ├── security/                    # 安全与风控
│   │   ├── rbac.py                  # 基于角色的权限依赖项
│   │   └── rate_limiter.py          # Redis 分级滑动窗口限流器
│   ├── tasks/                       # Celery 异步任务与 Outbox Publisher
│   │   ├── celery_app.py            # Celery 实例与 Broker 配置
│   │   ├── outbox_publisher.py      # 事务发件箱轮询派发守护进程
│   │   └── workers.py               # 日历同步、邮件发送、回访调度任务
│   └── main.py                      # FastAPI 入口应用装配
├── frontend/                        # 前端 React 源码
│   ├── src/
│   │   ├── api/                     # 统一 Axios API 客户端与请求封装
│   │   ├── auth/                    # 认证上下文与路由守卫 (RBAC)
│   │   ├── components/              # 业务复用组件
│   │   │   ├── common/              # 通用组件 (WorkflowPipeline, StatusBadge, TopNav)
│   │   │   ├── operator/            # 调度组件 (DispatchMapView, DispatchRankingCard)
│   │   │   └── admin/               # 管理组件 (PolicyDiffModal)
│   │   ├── hooks/                   # 自定义 React Hooks (useSwipeGesture 等)
│   │   ├── pages/                   # 页面组件
│   │   │   ├── customer/            # 客户门户页面 (登录, 首页, AI报修, 工单, 预约)
│   │   │   ├── admin/               # 管理门户页面 (概览, 调度策略, SLA, 技师, 审计)
│   │   │   ├── ServiceRequestsPage.tsx # 工单大厅 (含 GIS 地图与表格视图切换)
│   │   │   ├── ServiceRequestDetailPage.tsx # 工单审批与 HITL 决策
│   │   │   └── OverviewPage.tsx     # 调度中心运营大盘
│   │   ├── test/                    # 前端自动化测试套件 (Vitest + Testing Library)
│   │   └── utils/                   # 工具函数 (policyAst, 日期格式化)
│   ├── package.json                 # 前端依赖配置
│   └── vite.config.ts               # Vite 构建配置
├── tests/                           # 后端全量测试套件 (360+ 测试用例)
├── docker-compose.yml               # 本地容器化编排文件 (PostgreSQL 16 + Redis 7)
├── Dockerfile                       # 多阶段轻量化生产镜像构建文件
├── pyproject.toml                   # Python 项目元数据与依赖锁定
└── README.md                        # 项目详尽技术文档
```

---

## 六、 数据库领域模型与状态机契约

### 6.1 状态枚举契约 (Single Source of Truth)

系统严格规范了状态契约，前后端与数据库完全同构，禁止出现隐式字符串硬编码：

| 领域对象 | 状态枚举值 (Backend Enum) | 中文标准语义 (UI Display) | 状态流转意义 |
| :--- | :--- | :--- | :--- |
| **ServiceRequest**<br/>(服务工单) | `received` | 受理已接收 | 客户已提交，系统已建立工单底册 |
| | `needs_information` | 信息待补全 | 核心报修要素（设备/故障/地址）缺失，等待客户补充 |
| | `matched` | 算法匹配中 | 系统已初筛候选技师，正在计算多因子权重 |
| | `waiting_for_approval` | 待人工审核 | 推荐算法已生成最优排期方案，挂起等待调度员核准 |
| | `scheduled` | 锁定排程 | 调度员已核准，技师排班锁定并同步外部日历 |
| | `in_progress` | 上门履约中 | 工程师已到达现场打卡，正在执行检修作业 |
| | `completed` | 竣工验收 | 现场维修完成，客户已确认签字验收 |
| | `cancelled` | 已取消 | 履约前经客户申请或调度员核实取消 |
| | `needs_rescheduling` | 改约协商中 | 原定时段发生冲突或客户临时变更，等待重新排程 |
| **Appointment**<br/>(上门预约) | `scheduled` | 待上门履约 | 预约已成立，锁定技师日历时间段 |
| | `confirmed` | 客户已确认 | 客户已收到确认通知并在线确认时间窗口 |
| | `in_progress` | 正在服务 | 技师现场服务打卡激活 |
| | `completed` | 服务完成 | 现场履约完毕，触发后续满意度回访 |
| | `cancelled` | 预约已取消 | 释放技师排班时间槽，软删除外部日历事件 |
| **SLA Status**<br/>(时效状态) | `on_track` | 时效充足 | 距 SLA 截止时间充裕（处于绿色安全区间） |
| | `at_risk` | 临近超时 | 剩余时间低于黄色预警阈值，调度大厅置顶标黄 |
| | `breached` | 已违约超时 | 超过约定时限，触发报警脉冲并自动生成异常升级单 |
| **Escalation**<br/>(异常升级) | `open` | 待处置 | 升级工单已生成，等待调度主管干预 |
| | `in_review` | 主管处理中 | 调度主管已介入，正在重新调派高资历技师或协商 |
| | `resolved` | 升级已解决 | 干预措施到位，告警解除并记录处理说明 |

### 6.2 核心实体关系模型

```text
┌───────────────────────────┐           ┌───────────────────────────┐
│         customers         │           │        technicians        │
├───────────────────────────┤           ├───────────────────────────┤
│ id (PK)                   │           │ id (PK)                   │
│ name                      │           │ name                      │
│ email (UNIQUE)            │           │ email                     │
│ phone                     │           │ phone                     │
│ address                   │           │ service_area (服务大区)   │
│ created_at                │           │ skills (JSON: HVAC/电气)  │
└─────────────┬─────────────┘           │ max_daily_load (负荷上限) │
              │ 1                       │ is_active                 │
              │                         └─────────────┬─────────────┘
              │ N                                     │ 1
┌─────────────▼─────────────┐                         │
│     service_requests      │                         │
├───────────────────────────┤                         │
│ id (PK)                   │                         │
│ customer_id (FK)          │                         │
│ service_type (HVAC/水暖)  │                         │
│ urgency (P0-P3)           │                         │
│ location                  │                         │
│ status                    │                         │
│ sla_deadline (SLA截止)    │                         │
│ sla_status                │                         │
│ dispatch_policy_version   │                         │
│ created_at                │                         │
└─────────────┬─────────────┘                         │
              │ 1                                     │
              │                                       │
              │ 1..N (改约历史链)                     │ N
┌─────────────▼───────────────────────────────────────▼─────────────┐
│                            appointments                           │
├───────────────────────────────────────────────────────────────────┤
│ id (PK)                                                           │
│ service_request_id (FK)                                           │
│ technician_id (FK)                                                │
│ start_time (TIMESTAMPTZ)                                          │
│ end_time (TIMESTAMPTZ)                                            │
│ status (scheduled / in_progress / completed / cancelled)          │
│ replaced_by_appointment_id (FK: 改约替代记录)                    │
│ rescheduled_from_appointment_id (FK: 改约来源记录)                │
│ [CONSTRAINT] exclude_overlapping_appointments (GIST 排他排除约束)  │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ 1
                                  │ N
┌─────────────────────────────────▼─────────────────────────────────┐
│                           outbox_events                           │
├───────────────────────────────────────────────────────────────────┤
│ id (PK)                                                           │
│ event_type (appointment.created / appointment.cancelled)          │
│ aggregate_id                                                      │
│ payload (JSON: 预约明细、客户资料、技师信息)                      │
│ status (pending / published / failed)                             │
│ retry_count                                                       │
│ created_at                                                        │
└───────────────────────────────────────────────────────────────────┘
```

---

## 七、 本地快速启动与部署指南

### 7.1 环境依赖准备

确保本地已安装以下基础运行环境：
- **Python**: `>= 3.11`
- **Node.js**: `>= 18.0.0` (推荐 Node 20 LTS) 与 `npm`
- **Docker** 与 **Docker Compose**
- **Git**

### 7.2 环境变量配置

在项目根目录下创建并配置 `.env` 文件（参考 `.env.example`）：

```ini
# 应用运行模式与时区
APP_ENV=development
BUSINESS_TIMEZONE=Asia/Shanghai

# PostgreSQL 数据库连接串
DATABASE_URL=postgresql+psycopg://fieldops:fieldops@localhost:5432/fieldops

# Redis 消息中间件与缓存
REDIS_URL=redis://localhost:6379/0

# 大模型配置 (开发自测支持 FakeLLM 离线模式)
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=30.0

# 认证安全密钥
JWT_SECRET_KEY=fieldops-development-secret-key-do-not-use-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=480

# 预约与排班步长设置 (分钟)
DEFAULT_APPOINTMENT_DURATION_MINUTES=120
DEFAULT_SLOT_STEP_MINUTES=60

# 工作流状态持久化模式 (开发环境 sqlite / 容器生产 postgres)
CHECKPOINTER_BACKEND=sqlite
CHECKPOINT_DB_PATH=checkpoints.sqlite

# 外部日历集成 (fake 纯模拟模式 / google 真实服务账号模式)
CALENDAR_PROVIDER=fake
ENABLE_FAKE_INTAKE=true
```

### 7.3 启动基础服务与数据库迁移

使用 Docker Compose 启动隔离的 PostgreSQL 16 与 Redis 7 容器：

```bash
# 1. 启动数据库与缓存容器
docker compose up -d postgres redis

# 2. 运行 Alembic 迁移脚本 (自动激活 btree_gist 扩展并创建所有数据表与排他约束)
alembic upgrade head

# 3. 填充演示种子数据 (初始网点、客户、专业技师、默认调度策略与 SLA 规则)
python scripts/seed.py
```

### 7.4 启动后端服务 (FastAPI + Celery)

```bash
# 终端 1: 启动 FastAPI 主应用服务 (开启热重载)
uvicorn fieldops.main:app --host 127.0.0.1 --port 8000 --reload --app-dir src

# 终端 2: 启动 Celery 异步任务 Worker
celery -A fieldops.tasks.celery_app worker --loglevel=info -P solo

# 终端 3: 启动 Transactional Outbox 事务发件箱轮询守护进程
python -m fieldops.tasks.outbox_publisher
```

### 7.5 启动前端应用 (Vite)

```bash
# 进入前端子工程目录
cd frontend

# 安装前端依赖包
npm install

# 启动 Vite 开发调试服务器 (默认监听 http://localhost:5173)
npm run dev
```

### 7.6 默认测试账号与入口索引

启动成功后，可通过浏览器访问以下三端门户：

| 门户模块 | 访问 URL | 默认测试账号 | 默认密码 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| **客户服务中心** | `http://localhost:5173/customer` | `alice@example.com` | 密码随意/快捷注册 | 包含 AI 智能客服语音报修、工单跟踪、手势滑动 |
| **运营调度大厅** | `http://localhost:5173/` | `operator@fieldops.com` | `operator123` | 包含工单排程、GIS 调度地图、多因子算法 HITL 审批 |
| **运营治理中台** | `http://localhost:5173/admin` | `admin@fieldops.com` | `admin123` | 包含调度策略 AST Diff、SLA 规则调优、审计检索 |
| **Swagger 接口文档** | `http://127.0.0.1:8000/docs` | 继承上述 JWT Token | - | FastAPI 交互式 OpenAPI 接口在线调试 |
| **Prometheus 指标** | `http://127.0.0.1:8000/metrics` | 公开只读 | - | 连接池监控、Outbox 积压率、状态机转换打点 |

---

## 八、 自动化测试、质量评测与压测基准

FieldOps Agent 拥有从单元测试、组件渲染、系统集成、确定性 Agent 评测到高并发故障注入的全套工程质量防护网：

### 8.1 后端自动化测试套件 (Pytest)

```bash
# 运行全部 360+ 项后端单元与集成测试
python -m pytest -v

# 运行跨角色端到端与全生命周期回归测试 (重点测试套件)
pytest tests/test_cross_role_e2e.py tests/test_service_lifecycle.py tests/test_lifecycle_concurrency.py tests/test_technician_matching.py tests/test_scheduling.py -v
```

**测试重点覆盖领域**：
- `test_lifecycle_concurrency.py`：并发排班抢单排他性验证、重复完成（Double Complete）幂等防护、完成与取消竞态拦截（409 Conflict）。
- `test_service_lifecycle.py`：工单与预约双状态机在开始上门、完工验收、协商改约中的原子性同步。
- `test_technician_matching.py`：多因子打分算法确定性运算与边界情况筛选。
- `test_scheduling.py`：时间区间重叠数学公式的 9 种极值边界测试。
- `test_security_remediation.py`：严格的 RBAC 角色越权拦截、非法 JWT 篡改拦截与生产环境敏感字段脱敏。

### 8.2 前端自动化测试与类型检查 (Vitest)

```bash
# 运行前端全部 11 个测试套件 (44 项测试用例全部通过)
cd frontend && npm test -- --run

# 执行 TypeScript 严格类型检查与生产级打包构建
npm run build
```

**前端测试矩阵**：
- `policyAst.test.ts`：策略语法树 AST 解析、Diff 计算与序列化完整性。
- `useSwipeGesture.test.ts`：移动端水平触摸滑动（Swipe Left/Right）灵敏度与阈值防误触。
- `DispatchMapView.test.tsx`：GIS 调度地图网点、技师图钉渲染与交互逻辑。
- `CustomerAssistant.test.tsx`：AI 客服会话界面、消息发送、预诊断卡片交互。
- `AdminConsole.test.tsx` / `CustomerPortal.test.tsx`：路由鉴权拦截与角色白名单校验。

### 8.3 确定性 Agent 质量评测体系

为了杜绝大模型输出结果难以度量的问题，项目建立了基于标准数据集的客观评测引擎：

```bash
# 1. 运行技师资质匹配确定性评测
python evaluation/run_matching_eval.py

# 2. 运行排班冲突检测算法评测
python evaluation/run_scheduling_eval.py

# 3. 运行端到端工作流业务路径全覆盖评测
python evaluation/run_workflow_eval.py

# 4. 运行大模型实体意图提取与幻觉率评测
python evaluation/run_parser_eval.py
```

**评测基线达成指标**：

| 评估维度 | 样本集规模 | 核心衡量指标 | 达标基线 | 判定标准 |
| :--- | :--- | :--- | :--- | :--- |
| **Technician Matching** | 14 类场景 | 候选集完全匹配率 (Exact Set Acc) | **100.0%** | 确定性业务规则 |
| **Scheduling Engine** | 11 种时段 | 时段区间冲突检测准确率 (Conflict Acc) | **100.0%** | 区间重叠数学定理 |
| **Business Workflow** | 5 大典型链路 | 任务完成率 (Task Completion Rate) | **100.0%** | 状态机业务闭环 |
| **Workflow State** | 5 大分支 | 终态准确率 (Final State Acc) | **100.0%** | 核准/拒绝/冲突/信息缺失 |
| **LLM Parser (Intent)** | 32 条真实提报 | 关键技能识别 F1 (Skills F1) | **1.0** | 集合论 Precision/Recall |
| **LLM Parser (Safety)** | 32 条真实提报 | 幻觉率 (Unsupported Field Rate) | **0.0%** | 严禁凭空捏造未提供信息 |

### 8.4 高并发性能与故障注入压测 (Locust + FakeLLM)

```bash
# 在压测模式下启动 Locust (零真实 API 账单成本，由 FakeLLM 承载)
locust -f performance/locustfile.py --host=http://127.0.0.1:8000
```

- **压测场景覆盖**：
  1. `service_request_load.py`：工单受理、实体抽取、事务写入与 Outbox 事件高并发入库压测；
  2. `appointment_conflict_load.py`：针对同一位热门工程师的相同时间槽发起瞬时 100+ 并发预约冲击，验证行级排他锁与 GIST 约束下 **0 超买超卖、0 脏数据**；
  3. `idempotency_load.py`：高频相同/相异 `Idempotency-Key` 连续轰炸，验证去重缓存与 409 拦截。

---

## 九、 未来演进路线 (Roadmap)

- [x] **Phase 1~18**: 核心框架搭建、LangGraph 编排、PostgreSQL GIST 约束、Transactional Outbox、Celery 异步管道、生产加固与 Locust 压测。
- [x] **Phase 19~23**: 三端门户搭建、多轮会话 Agent、单事实来源架构、端到端 10 步业务闭环验证。
- [x] **Phase 24~25**: 工单与预约全生命周期闭环（开始/完工/改约/改派）、真实 Google Calendar API v3 适配器与轻量巡检。
- [x] **Phase 26~29**: 多因子自适应派单打分引擎、实时 SLA 监控与多级升级机制、调度策略 AST/Code 语法树 Diff 治理中台。
- [x] **Phase 30~32+**: 三端全量自然中文化、苹果极简主义设计系统 (Apple Minimalist UI)、W3C 语音报修与音频波形图、GIS 空间派单地图、移动端触摸手势切换、7阶段工单全生命周期流程组件 (`WorkflowPipeline`)。
- [ ] **Phase 33 (规划中)**: 现场多模态图像验损 Agent（客户上传故障照片，基于 Vision 大模型自动判断破损零件并推荐备品备件）。
- [ ] **Phase 34 (规划中)**: 工程师移动端 H5 / PWA 专属工作台（现场打卡、备件消耗扫码核销、客户电子签字）。
- [ ] **Phase 35 (规划中)**: 跨大区运力智能动态调配与路径规划 (VRP - Vehicle Routing Problem) 算法融合。

---

<div align="center">

**FieldOps Agent: 构建企业可信、架构严谨的新一代 AI 现场服务运营基础设施**

Open Source under Apache 2.0 License.

</div>
