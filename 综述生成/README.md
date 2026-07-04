# DRAG（辩论增强RAG）综述幻觉抑制框架

## 项目概述

本项目基于**ACL 2025 DRAG（Debate-Augmented RAG）框架**，实现了一个学术综述自动生成与幻觉抑制系统。通过多智能体辩论机制，有效解决综述生成中的引用编造、夸大等幻觉问题。

> **参考论文**：Hu et al. (2025) *Removal of Hallucination on Hallucination*, ACL 2025 Long Paper, 2025.acl-long.770

## 核心技术

### DRAG框架原理

DRAG（Debate-Augmented RAG）是ACL 2025提出的创新性RAG增强方案，通过**多智能体对抗辩论**机制抑制检索和生成过程中的幻觉问题。

#### 两大核心阶段

**阶段一：检索辩论（Retrieval Debate）**

- **支持者（Proponent）**：维护检索结果的可信度，提供支持证据
- **挑战者（Opponent）**：质疑潜在的低质量检索结果，要求补充检索
- **裁判（Judge）**：评估双方观点，判断检索质量是否达标

三方智能体通过多轮对抗迭代，当辩论结果收敛到阈值ε时，认为检索结果可信。

**阶段二：应答辩论（Response Debate）**

- 生成器生成综述内容后，挑战者对每一条引用进行质疑
- 支持者提供证据辩护，裁判综合评估
- **解决二次幻觉（Hallucination on Hallucination）**：识别对幻觉内容的再次幻觉

#### 关键设计：信息不对称

挑战者持有"幻觉检测清单"（支持者不可见），通过不对称信息设计，确保辩论的对抗性和有效性。

## 系统架构

```
文献PDF → 摘要提取 → DRAG检索辩论 → 分篇章综述生成 → DRAG应答辩论 → 事实输出
                          ↓                    ↓
                    三方智能体验证          三方智能体校验
                    (检索质量评估)          (引用准确性验证)
```

### 流水线说明

1. **PDF原文提取**：提取论文内容作为证据池
2. **DRAG检索辩论**：验证检索结果质量（论文1-2）
3. **分篇章综述生成**：基于验证后的摘要生成综述
4. **DRAG应答辩论**：对生成内容进行对抗性校验
5. **事实输出**：输出经辩论验证的最终综述

## 技术特性

- **三方智能体协同**：支持者/挑战者/裁判各司其职
- **多轮辩论收敛**：可配置辩论轮次，通过阈值ε控制收敛
- **信息不对称设计**：挑战者持有独特视角，确保对抗性
- **二次幻觉检测**：专门设计用于识别对幻觉内容的再次幻觉
- **查询扩充策略**：支持多跳推理，全面验证跨论文观点

## 实验数据

基于DRAG框架在标准数据集上的表现：

| 数据集 | 基线EM | DRAG EM | 提升 |
|--------|--------|---------|------|
| HotpotQA | 45.2 | 52.8 | +7.6 |
| 2WikiMultiHopQA | 38.5 | 47.2 | +8.7 |

对比基线：

- **Naive RAG**：直接检索生成，无辩论机制
- **Self-RAG**：自反思RAG，单智能体评估
- **DRAG**：多智能体辩论增强，显著优于基线方法

## 环境配置

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置API密钥

编辑 `config/settings.py` 或创建 `.env` 文件：

```env
API_KEY=你的火山方舟API密钥
```

### DRAG框架配置

在 `config/settings.py` 中可配置DRAG参数：

```python
# DRAG框架开关
drag_enable: bool = True

# 检索辩论配置
retrieval_debate_rounds: int = 3  # 辩论轮次
retrieval_convergence_threshold: float = 0.85  # 收敛阈值ε

# 应答辩论配置
response_debate_rounds: int = 3
response_convergence_threshold: float = 0.80

# 三方智能体配置
agent_count: int = 3  # 智能体数量
asymmetry_enabled: bool = True  # 信息不对称开关

# 二次幻觉检测
second_hallucination_detection: bool = True
```

## 快速开始

### 启动服务

```bash
cd D:\综述生成
python main.py
```

或使用uvicorn：

```bash
python -m uvicorn api.routes:app --host 0.0.0.0 --port 8002
```

### 上传论文

将PDF文件放入 `local_papers/` 目录

### 生成综述

访问完整流程API：

```bash
curl -X POST "http://localhost:8002/full-pipeline?topic=大语言模型在生物信息学中的应用"
```

## API接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务健康检查 |
| `/papers` | GET | 列出本地论文 |
| `/summarize` | POST | 生成论文摘要（DRAG证据池） |
| `/review` | POST | 生成综述（DRAG生成阶段） |
| `/verify` | POST | 校验引用（DRAG辩论验证） |
| `/full-pipeline` | POST | 完整流程 |
| `/cache` | GET/DELETE | 缓存管理 |

## 输出示例

DRAG辩论过程日志示例：

```
[DRAG检索辩论前置] 正在处理论文: paper1.pdf
[DRAG证据池] 已加载 5 篇文献进入证据池
[DRAG辩论-支持者] 提取到 12 处引用
[DRAG辩论-挑战者] 正在验证文献 paper1.pdf 的引用准确性...
[DRAG辩论-裁判] 文献 paper1.pdf 验证完成
[DRAG裁判裁决] 发现 2 处需修正内容，执行修正...
```

## 引用本项目

```bibtex
@article{drag2025,
  title={Removal of Hallucination on Hallucination},
  author={Hu, X. et al.},
  booktitle={ACL 2025 Long Papers},
  year={2025},
  paper={2025.acl-long.770}
}
```

## 参考资料

- **DRAG论文**：Hu et al. (2025) *Removal of Hallucination on Hallucination*, ACL 2025, 2025.acl-long.770
- **DRAG框架源码**：本项目 `drag_framework.py`
- **多智能体辩论模块**：`multi_agent_debate.py`

## 许可证

MIT License
