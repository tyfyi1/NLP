# 技术文档 - DRAG辩论增强综述生成系统

## 1. 项目背景

### 1.1 问题陈述

在学术综述自动生成任务中，大语言模型容易产生两类幻觉问题：

1. **一次幻觉**：模型在生成过程中编造不存在的引用或夸大论文贡献
2. **二次幻觉（Hallucination on Hallucination）**：对已幻觉内容的再次错误理解和引用

### 1.2 解决方案

本项目基于**ACL 2025 DRAG框架**（2025.acl-long.770），通过多智能体辩论机制有效抑制上述问题。

## 2. DRAG框架详解

### 2.1 框架概述

DRAG（Debate-Augmented RAG）是一种创新的RAG增强方案，其核心思想是通过**对抗性辩论**机制，让多个智能体对检索和生成结果进行交叉验证。

### 2.2 检索辩论阶段（Retrieval Debate）

**目标**：验证检索结果的质量，确保进入生成阶段的证据可靠。

**三方智能体分工**：

| 智能体 | 角色 | 职责 |
|--------|------|------|
| 支持者 | Proponent | 维护检索结果可信度，提供支持证据 |
| 挑战者 | Opponent | 质疑低质量检索，要求补充证据 |
| 裁判 | Judge | 评估辩论结果，判定是否收敛 |

**辩论流程**：

```
1. 支持者发起初始论点：检索结果支持查询Q
2. 挑战者提出质疑：指出潜在的幻觉风险
3. 支持者反驳辩护：提供证据支持论点
4. 裁判评估：根据双方论点判定置信度
5. 迭代直到收敛（置信度 >= ε）
```

### 2.3 应答辩论阶段（Response Debate）

**目标**：对生成的综述内容进行对抗性验证，识别引用错误。

**辩论流程**：

```
1. 生成器产出综述内容
2. 挑战者质疑每条引用的准确性
3. 支持者提供原文证据辩护
4. 裁判评估是否存在幻觉
5. 对幻觉内容进行标记和修正
```

### 2.4 信息不对称设计

DRAG的核心创新之一是**信息不对称**：

- **挑战者**持有"幻觉检测清单"（支持者不可见）
- 支持者需要提供充分证据说服持有不同视角的挑战者
- 这种设计确保了辩论的真正对抗性

### 2.5 二次幻觉检测

二次幻觉是DRAG专门解决的问题：

1. 挑战者检测支持者回应中是否有新的未验证声明
2. 如果支持者回应引入新说法，挑战者要求进一步验证
3. 迭代直到所有声明都有原文依据

## 3. 系统架构

### 3.1 整体架构

```
┌─────────────┐
│  PDF原文    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 摘要提取     │ ← DRAG证据池构建
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ DRAG检索辩论 │ ← 三方智能体验证
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 综述生成    │ ← DRAG应答辩论生成
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ DRAG应答辩论 │ ← 三方智能体校验
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 修正综述    │
└─────────────┘
```

### 3.2 核心模块

| 模块 | 文件 | 说明 |
|------|------|------|
| DRAG框架核心 | `drag_framework.py` | DRAG检索辩论、应答辩论、裁判实现 |
| 多智能体辩论 | `multi_agent_debate.py` | 三方智能体协同机制 |
| 摘要生成器 | `core/summarizer.py` | DRAG前置证据池构建 |
| 综述生成器 | `core/reviewer.py` | DRAG应答辩论综述生成 |
| 引用校验器 | `core/verifier.py` | DRAG应答辩论校验 |

## 4. DRAG核心模块伪代码

### 4.1 DRAG检索辩论伪代码

```python
class DRAGRetrievalDebate:
    def debate_retrieval(self, query, retrieval_result):
        """
        DRAG检索辩论流程

        输入: query(查询), retrieval_result(检索结果)
        输出: DebateResult(辩论结果)
        """
        # 初始化辩论状态
        evidence_pool = []
        debate_rounds = []

        # 阶段1：支持者初始化论点
        proponent_init = Proponent.generate_argument(
            query, retrieval_result
        )
        evidence_pool.extend(retrieval_result)
        debate_rounds.append(proponent_init)

        # 阶段2-4：多轮对抗辩论
        for round in range(1, max_rounds + 1):
            # 挑战者质疑
            opponent_challenge = Opponent.challenge(
                evidence_pool,
                hallucination_checklist  # 信息不对称
            )
            debate_rounds.append(opponent_challenge)

            # 支持者辩护
            proponent_defense = Proponent.defend(
                opponent_challenge,
                evidence_pool
            )
            debate_rounds.append(proponent_defense)

            # 裁判评估
            judge_verdict = Judge.evaluate(debate_rounds)

            # 检查收敛
            if judge_verdict.confidence >= epsilon:
                break

        # 最终裁判
        return Judge.final_verdict(debate_rounds)
```

### 4.2 DRAG应答辩论伪代码

```python
class DRAGResponseDebate:
    def debate_response(self, content, citations):
        """
        DRAG应答辩论流程

        输入: content(生成内容), citations(引用列表)
        输出: DebateResult(辩论结果)
        """
        debate_rounds = []

        # 初始验证
        proponent_verification = Proponent.verify(content, citations)
        debate_rounds.append(proponent_verification)

        # 多轮辩论
        for round in range(1, max_rounds + 1):
            # 挑战者质疑引用准确性
            opponent_challenge = Opponent.challenge_citations(
                content,
                citations,
                hallucination_rules
            )
            debate_rounds.append(opponent_challenge)

            # 支持者辩护
            proponent_defense = Proponent.defend_citations(
                opponent_challenge,
                citations
            )
            debate_rounds.append(proponent_defense)

            # 二次幻觉检测
            if SecondHallucinationDetector.detect(
                proponent_defense
            ):
                # 挑战者对辩护内容再次质疑
                opponent.second_order_challenge()

        # 裁判判决
        return Judge.final_judgment(debate_rounds)
```

### 4.3 三方智能体协同伪代码

```python
class MultiAgentDebateOrchestrator:
    def start_debate(self, topic, content):
        """
        协调三方智能体辩论
        """
        # 初始化
        proponent = ProponentAgent()
        opponent = OpponentAgent()
        judge = JudgeAgent()

        # 辩论循环
        for round in range(1, max_rounds):
            # 支持者发言
            prop_arg = proponent.generate_response(content, [])

            # 挑战者发言
            opp_arg = opponent.generate_response(content, [prop_arg])

            # 裁判评价
            judge_comment = judge.generate_response(
                content, [prop_arg], [opp_arg]
            )

            # 记录辩论
            judge.record_debate_round(round, prop_arg, opp_arg, judge_comment)

            # 检查收敛
            if judge.is_converged():
                break

        # 最终判决
        return judge.final_verdict(proponent.strength, opponent.strength)
```

## 5. 配置说明

### 5.1 DRAG配置参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `drag_enable` | 是否启用DRAG框架 | True |
| `retrieval_debate_rounds` | 检索辩论轮次 | 3 |
| `retrieval_convergence_threshold` | 检索辩论收敛阈值ε | 0.85 |
| `response_debate_rounds` | 应答辩论轮次 | 3 |
| `response_convergence_threshold` | 应答辩论收敛阈值ε | 0.80 |
| `agent_count` | 智能体数量 | 3 |
| `asymmetry_enabled` | 信息不对称开关 | True |
| `second_hallucination_detection` | 二次幻觉检测开关 | True |
| `epsilon` | 收敛判定小量阈值 | 0.05 |

### 5.2 配置示例

```python
# DRAG检索辩论配置
retrieval_debate_rounds = 3
retrieval_convergence_threshold = 0.85

# DRAG应答辩论配置
response_debate_rounds = 3
response_convergence_threshold = 0.80

# 信息不对称配置
asymmetry_enabled = True
opponent_knowledge = "hallucination_checklist"

# 二次幻觉检测
second_hallucination_detection = True
hallucination_threshold = 0.15
```

## 6. 适配改造说明

### 6.1 综述场景适配

针对文献综述多跳跨论文推理场景的改造：

1. **查询扩充策略**：将单一查询扩展为多跳查询池，覆盖跨论文观点验证
2. **辩论轮次调整**：综述场景需更多轮次确保全面验证
3. **证据池管理**：支持跨论文证据关联和检索

### 6.2 参数调优建议

| 场景 | retrieval_debate_rounds | response_debate_rounds |
|------|-------------------------|------------------------|
| 简单综述（3-5篇） | 2-3 | 2-3 |
| 中等综述（5-10篇） | 3-4 | 3-4 |
| 复杂综述（10篇以上） | 4-5 | 4-5 |

## 7. 参考文献

1. **Hu et al. (2025)**. *Removal of Hallucination on Hallucination*. ACL 2025 Long Paper, 2025.acl-long.770.

2. **Asai et al. (2024)**. *Self-RAG: Learning to Retrieve, Generate, and Critique*. ACL 2024.

3. **Lewis et al. (2020)**. *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS 2020.
