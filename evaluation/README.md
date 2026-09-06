# FieldOps Agent — Evaluation & Quality Framework (Phase 11)

本目录为 FieldOps Agent 提供可重复、可量化、全自动运行的质量评估体系（Evaluation Harness）。

---

## 一、核心设计哲学：“功能能运行” ≠ “Agent 质量合格”

在传统软件中，单元测试通过通常意味着功能交付；但在 AI Agent 系统中：
- 能够正常返回 HTTP 200，不代表 LLM 提取的业务实体准确；
- 模型填满了所有字段，可能是严重的**无中生有（Hallucination / Unsupported Field）**；
- 提示词（Prompt）做了一点微调，可能在某个 case 变好，却在另外 5 个 case 发生严重质量退化（Prompt Regression）。

因此，必须将验证体系分层清晰：

### 1. Unit Test（单元测试）
- **目标**：验证确定性代码分支、数学公式与逻辑判断；
- **环境**：本地快速运行，100% Mock 外部不可控依赖（如 LLM API、外部网络），保证 CI 极速确定性。

### 2. Integration Test（集成测试）
- **目标**：验证跨组件协作（如 FastAPI -> SQLAlchemy -> 事务排他锁 -> 数据库落库）；
- **环境**：依赖 SQLite/PostgreSQL，验证 ACID 原子性、并发争抢与 HTTP 响应码映射。

### 3. Evaluation（Agent 业务质量评估）
- **目标**：在**固定的真实场景参考数据集（Reference Dataset）**上，量化评测 Agent/LLM 的业务能力指标；
- **方法**：真实运行大模型提取与规则决策，对比预期真值（Ground Truth），产出标准量化分数（准确率、精确率、召回率、F1、幻觉率）。

---

## 二、数据集规划 (`evaluation/datasets/`)

| 数据集文件 | 案例数量 | 覆盖场景 |
| :--- | :--- | :--- |
| `parser_cases.json` | 32 | 标准工种（HVAC/Plumbing/Electrical/Networking/Appliance/Other）、缺失地点/时间、极短输入（"AC broken"）、口语化表述、多工种复合问题、紧急危险（喷火/燃气/漏水）、常规保养、负向干扰词 |
| `matching_cases.json` | 14 | 区域+技能精准单选、多技能复合满足、区域不匹配、技能不满足、缺失信息中断（`needs_location` / `needs_skill_information`）、大小写与空白规范化 |
| `scheduling_cases.json` | 11 | 前后无冲突、相邻时间边界（背靠背排班允许）、完全重叠、部分重叠、已取消预约不阻塞、跨时区（UTC vs Asia/Tokyo +09:00）自动转换 |
| `workflow_cases.json` | 5 | 正常核准流（创建预约）、缺地点中止、无匹配技师中止、调度员人工拒绝、并发抢占槽位（`needs_rescheduling` 拦截） |

---

## 三、指标定义 (Metrics Definition)

### 1. 标量字段准确率 (Scalar Accuracy)
针对 `service_type`、`urgency`、`location`、`preferred_time`：
- 进行大小写去除、首尾空白去除后的精确匹配；
- 针对 `location` 与 `preferred_time`，若真值为 `null`，模型也必须输出 `null` 才算匹配正确。

### 2. 技能集合指标 (Set-based Precision, Recall, F1)
对于 `required_skills`（如 `["HVAC", "Electrical"]`），采用集合论数学公式：
$$\text{Precision} = \frac{|\text{Expected} \cap \text{Predicted}|}{|\text{Predicted}|}$$
$$\text{Recall} = \frac{|\text{Expected} \cap \text{Predicted}|}{|\text{Expected}|}$$
$$\text{F1} = \frac{2 \times \text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$
- 当两方均为空集时，得分判定为 1.0（准确识别出无技能要求）；
- 预测出额外未提及技能会惩罚 Precision；漏提要求技能会惩罚 Recall。

### 3. 幻觉与无根据字段率 (Hallucination / Unsupported Field Rate)
当客户输入文本中**完全未提及地点或时间**时（真值标注为 `null`），若模型脑补出了具体地点或时间，即计为 1 次 Unsupported Hallucination：
$$\text{Unsupported Rate} = \frac{\text{Unsupported Location Count} + \text{Unsupported Time Count}}{\text{Total Cases} \times 2}$$
> [!IMPORTANT]
> 很多团队错误地认为“大模型把字段都填满了就是聪明”。在工单调度中，把客户没说的地点（如把未说明地点的故障当成总部所在地）脑补出来，会导致派错工单甚至巨额纠纷。

---

## 四、运行评估 (CLI Usage)

### 1. 运行 LLM Parser 语义解析评估
```bash
# 完整评估（配置 OPENAI_API_KEY 后调用真实模型）
python evaluation/run_parser_eval.py

# 开发调试（仅评测前 5 个案例）
python evaluation/run_parser_eval.py --limit 5

# 离线模拟基线验证
python evaluation/run_parser_eval.py --mock
```

### 2. 运行技师匹配规则评估 (Deterministic Matching)
```bash
python evaluation/run_matching_eval.py
```

### 3. 运行排班冲突算法评估 (Deterministic Scheduling)
```bash
python evaluation/run_scheduling_eval.py
```

### 4. 运行全链路业务工作流评估 (End-to-End Workflow)
```bash
python evaluation/run_workflow_eval.py
```

---

## 五、评测结果与失败分析报告

评测结果自动导出至 `evaluation/results/`，每次执行会输出：
- 聚合指标统计大盘（Accuracy, F1, Unsupported Rate）；
- **逐条失败案例排查明细**：打印失败的 `CASE ID`、原始用户输入、期望真值（Expected）与模型实际输出（Actual）。

### 失败归因分析指南（Failure Taxonomy）
当模型或流程未达到预期时，请遵循以下排查树，**切忌盲目扩充 Prompt**：
1. **Taxonomy Ambiguity（分类标准歧义）**：是否是多工种复合（如 AC 漏水同时涉及 HVAC 和水暖）导致归类不同？
2. **Missing Context（输入信息不足）**：用户是否只发了两个词？模型是否过度脑补？
3. **Prompt Instruction（提示词引导）**：System Prompt 是否对某些边界约束不够明确？
4. **Dataset Label Questionable（人工标注存疑）**：真值标注是否合理？
