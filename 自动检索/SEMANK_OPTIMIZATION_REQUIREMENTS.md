# 两阶段检索系统优化：基于 LLM 聚类归纳的 SemRank 实现

## 📋 项目概述

### 1.1 背景
当前系统已实现基于 SemRank 思想的两阶段检索机制，但在术语提取环节存在以下问题：
- **扁平化输出**：将 Research Topics 和 Key Phrases 混在一起，缺乏粒度区分
- **简单提取**：未对相似概念进行聚类归纳，可能导致冗余（如 "LLM"、"Large Language Model" 同时出现）
- **幻觉风险**：LLM 可能生成候选论文中不存在的术语

### 1.2 优化目标
借鉴 SemRank 论文的核心思想，采用**轻量级替代方案**（不训练 Topic Classifier），通过以下方式优化：
1. **结构化输出**：明确区分 Research Topics（宏观主题）和 Key Phrases（微观短语）
2. **聚类归纳**：LLM 自动识别并合并相似概念
3. **真实约束**：所有概念必须来自首次检索的真实论文（Grounding）

### 1.3 核心思想对比

| 维度 | SemRank (原论文) | 当前实现 | 优化后实现 |
|------|-----------------|---------|-----------|
| **候选来源** | Topic Classifier + Semantic Index | 第一次检索的 40 篇论文 | 第一次检索的 40 篇论文 |
| **提取方式** | LLM 从预定义标签中选择 | LLM 自由提取 20-25 个术语 | **LLM 聚类归纳 + 结构化输出** |
| **输出结构** | 选中的标签列表 | 扁平列表 `["term1", "term2"]` | **JSON: `{topics: [], phrases: []}`** |
| **语义粒度** | 明确区分 Topics/Phrases | 混合 | **明确区分** |
| **实现成本** | 极高（需训练分类器） | 低 | **低** |

---

## 🎯 功能需求

### 2.1 两阶段检索流程（保持不变）

```
用户输入查询
    ↓
【Stage 1】初步概念提取 → QueryUnderstandingAgent.analyze()
    ↓
【Stage 2】第一次检索 → 获取 40 篇候选论文
    ↓
【Stage 3】LLM 聚类归纳 → 提取 Research Topics + Key Phrases ⭐ 优化点
    ↓
【Stage 4】构造增强查询 → 合并初始概念 + Topics + Phrases
    ↓
【Stage 5】第二次检索 → 获取 40 篇论文（使用增强查询）
    ↓
【Stage 6】最终排序 → 返回 Top 10
```

### 2.2 核心优化点：Stage 3 - LLM 聚类归纳

#### **输入**
- 候选论文列表（前 15 篇的 Title + Abstract）
- 初始查询概念

#### **处理逻辑**
1. LLM 分析候选论文的标题和摘要
2. 提取重要科学概念
3. **聚类相似概念**（例如："LLM"、"Large Language Model" → 保留 "Large Language Model"）
4. **分类为两类**：
   - **Research Topics**：宏观研究方向（最多 5 个）
     - 示例：`"Large Language Models"`, `"Information Retrieval"`, `"Agentic Retrieval"`
   - **Key Phrases**：具体技术/方法/指标（最多 10 个）
     - 示例：`"Chain-of-Thought"`, `"BLEU Score"`, `"Parameter-Efficient Fine-Tuning"`

#### **输出格式**
```json
{
  "research_topics": ["topic1", "topic2", ...],
  "key_phrases": ["phrase1", "phrase2", ...]
}
```

---

## 🛠️ 技术实现规范

### 3.1 需要修改的文件

| 文件路径 | 修改内容 | 行号范围 |
|---------|---------|---------|
| `D:\NLP_final\paper_retriever\main.py` | 更新 `TERM_EXTRACTION_PROMPT` 模板 | 第 19-40 行 |
| `D:\NLP_final\paper_retriever\main.py` | 更新 `_extract_real_terms_from_candidates` 解析逻辑 | 第 147-182 行 |
| `D:\NLP_final\paper_retriever\main.py` | （可选）优化 `_build_enhanced_query` 支持权重 | 第 263-304 行 |

### 3.2 详细修改方案

#### **修改 1：更新 Prompt 模板**

**位置**：`main.py` 第 19-40 行

**修改前**：
```python
TERM_EXTRACTION_PROMPT = """
You are a scientific terminology extractor. Your task is to extract REAL academic terms...
Output a JSON list of strings (e.g., ["transformer architecture", "bleu score"])
...
"""
```

**修改后**：
```python
TERM_EXTRACTION_PROMPT = """
You are an expert research assistant helping to improve search results. 
Below are the top-ranked papers returned by a retriever for the query: "{initial_concepts}".

Your task is to:
1. Analyze the titles and abstracts of these papers.
2. Extract and cluster the most important scientific concepts.
3. Categorize them into two groups:
   - Research Topics: High-level research areas or directions (e.g., "Large Language Models", "Information Retrieval").
   - Key Phrases: Specific techniques, methods, or metrics (e.g., "Chain-of-Thought", "BLEU Score", "Parameter-Efficient Fine-Tuning").

IMPORTANT:
- Only extract concepts that are SUPPORTED by the provided papers.
- Cluster similar concepts (e.g., "LLM", "Large Language Model" -> keep only "Large Language Model").
- Return at most 5 Research Topics and 10 Key Phrases.
- Output MUST be a valid JSON object with keys "research_topics" and "key_phrases".

Candidate Papers:
{papers_text}

Output JSON format:
{{
  "research_topics": ["topic1", "topic2", ...],
  "key_phrases": ["phrase1", "phrase2", ...]
}}
"""
```

**关键改动**：
- ✅ 明确要求**聚类相似概念**
- ✅ 明确要求**分类为 Topics 和 Phrases**
- ✅ 限制数量（最多 5 个 Topics + 10 个 Phrases）
- ✅ 输出格式改为**结构化 JSON 对象**

---

#### **修改 2：更新解析逻辑**

**位置**：`main.py` 第 147-182 行

**方法**：`_extract_real_terms_from_candidates`

**修改前**：
```python
async def _extract_real_terms_from_candidates(
    self,
    candidate_papers: List[RawPaper],
    initial_concepts: QueryConcepts
) -> List[str]:
    ...
    try:
        result = await self.llm_client.async_generate_json(prompt)
        if result and isinstance(result, list):
            terms = [str(t).lower().strip() for t in result if t and len(str(t).strip()) > 2]
            unique_terms = list(dict.fromkeys(terms))[:25]
            return unique_terms
    except Exception as e:
        logger.warning(f"LLM term extraction failed: {e}, using fallback")
    
    return self._fallback_term_extraction(candidate_papers, initial_concepts)
```

**修改后**：
```python
async def _extract_real_terms_from_candidates(
    self,
    candidate_papers: List[RawPaper],
    initial_concepts: QueryConcepts
) -> List[str]:
    """
    === SemRank Core Logic: Candidate Term Extraction with Clustering ===
    
    从候选论文中提取真实术语（类似 SemRank 的 Candidate Topics）
    支持结构化输出：Research Topics + Key Phrases
    
    Args:
        candidate_papers: 候选论文列表
        initial_concepts: 初始查询概念
    
    Returns:
        List[str]: 提取的真实术语列表（合并 Topics 和 Phrases）
    """
    if not self.llm_client.is_available:
        logger.info("LLM not available, using fallback term extraction")
        return self._fallback_term_extraction(candidate_papers, initial_concepts)
    
    # 构建术语提取 Prompt
    prompt = self._build_term_extraction_prompt(candidate_papers, initial_concepts)
    
    try:
        result = await self.llm_client.async_generate_json(prompt)
        if result and isinstance(result, dict):
            # 提取 Research Topics
            topics = [str(t).lower().strip() for t in result.get("research_topics", []) if t]
            # 提取 Key Phrases
            phrases = [str(p).lower().strip() for p in result.get("key_phrases", []) if p]
            
            # 合并并去重（Topics 优先）
            all_terms = list(dict.fromkeys(topics + phrases))
            
            logger.info(f"Extracted {len(topics)} topics and {len(phrases)} phrases")
            logger.info(f"Topics: {topics}")
            logger.info(f"Phrases: {phrases}")
            
            return all_terms[:20]  # 限制总数为 20
    except Exception as e:
        logger.warning(f"LLM term extraction failed: {e}, using fallback")
    
    # 降级到词频统计
    return self._fallback_term_extraction(candidate_papers, initial_concepts)
```

**关键改动**：
- ✅ 解析 `dict` 而非 `list`
- ✅ 分别提取 `research_topics` 和 `key_phrases`
- ✅ 添加日志记录（便于调试）
- ✅ Topics 优先于 Phrases（因为 Topics 更宏观）

---

#### **修改 3：（可选）优化 Fallback 逻辑**

**位置**：`main.py` 第 205-261 行

**方法**：`_fallback_term_extraction`

**建议**：保持现有逻辑不变（基于词频统计），因为 Fallback 场景下 LLM 不可用，无法进行聚类。

---

### 3.3 数据流示例

#### **场景：用户输入 "AI Agent 如何帮助论文检索？"**

**Stage 1: 概念提取**
```python
QueryConcepts(
    concepts=[
        QueryConcept(concept="AI Agent", synonyms=["intelligent agent", "autonomous agent"]),
        QueryConcept(concept="paper retrieval", synonyms=["literature search", "academic search"])
    ]
)
```

**Stage 2: 第一次检索**
- Semantic Scholar 返回 40 篇候选论文

**Stage 3: LLM 聚类归纳（新逻辑）**

**Prompt 输入**（前 15 篇论文的 Title + Abstract）：
```
You are an expert research assistant...
Initial Concepts: AI Agent, paper retrieval

Candidate Papers:
Paper 1:
Title: Agentic Retrieval: Enhancing Search with AI Agents
Abstract: We propose a novel framework for retrieval-augmented generation...

Paper 2:
Title: Tool Use in Large Language Models for Information Retrieval
Abstract: This paper investigates how LLMs can leverage external tools...

... (共 15 篇)
```

**LLM 输出**：
```json
{
  "research_topics": [
    "Agentic Retrieval",
    "Large Language Models",
    "Information Retrieval",
    "Retrieval-Augmented Generation",
    "AI Agents"
  ],
  "key_phrases": [
    "Tool Use",
    "Task Planning",
    "ReAct Framework",
    "Chain-of-Thought",
    "Vector Database",
    "Semantic Search",
    "Query Expansion",
    "Document Ranking",
    "Knowledge Grounding",
    "Context Window"
  ]
}
```

**解析后**：
```python
all_terms = [
    "agentic retrieval",
    "large language models",
    "information retrieval",
    "retrieval-augmented generation",
    "ai agents",
    "tool use",
    "task planning",
    "react framework",
    ...
]
```

**Stage 4: 构造增强查询**
```python
enhanced_query = '"AI Agent" OR "intelligent agent" OR "paper retrieval" OR "agentic retrieval" OR "large language models" OR "tool use" OR ...'
```

**Stage 5: 第二次检索**
- 使用增强查询重新检索 Semantic Scholar
- 返回 40 篇更精准的论文

---

## ✅ 验收标准

### 4.1 功能验收

| 测试项 | 预期结果 | 验证方法 |
|--------|---------|---------|
| **结构化输出** | LLM 返回包含 `research_topics` 和 `key_phrases` 的 JSON | 查看日志输出 |
| **聚类效果** | 相似概念被合并（如 "LLM" 和 "Large Language Model" 只保留一个） | 检查返回的术语列表 |
| **数量限制** | Topics ≤ 5，Phrases ≤ 10，总数 ≤ 20 | 统计列表长度 |
| **真实性约束** | 所有术语都能在候选论文中找到依据 | 人工抽查论文摘要 |
| **降级机制** | LLM 失败时自动切换到词频统计 Fallback | 模拟 LLM API 超时 |

### 4.2 性能验收

| 指标 | 要求 | 说明 |
|------|------|------|
| **API 调用次数** | 每次查询最多 2 次 LLM 调用 | Stage 1 概念提取 + Stage 3 术语提取 |
| **响应时间** | 单次查询 < 30 秒 | 取决于 LLM API 速度 |
| **术语提取准确率** | ≥ 80% 的术语与查询相关 | 人工评估 |

### 4.3 代码质量验收

- ✅ 所有修改有清晰的注释（标注 "SemRank Core Logic"）
- ✅ 异常处理完善（LLM 失败时自动降级）
- ✅ 日志记录完整（便于调试和监控）
- ✅ 向后兼容（不影响现有的单阶段检索模式）

---

## 🚀 实施步骤

### Step 1: 备份当前代码
```bash
cd D:\NLP_final
git add .
git commit -m "Backup before SemRank optimization"
```

### Step 2: 修改 Prompt 模板
- 文件：`main.py`
- 位置：第 19-40 行
- 操作：替换 `TERM_EXTRACTION_PROMPT` 常量

### Step 3: 修改解析逻辑
- 文件：`main.py`
- 位置：第 147-182 行
- 操作：更新 `_extract_real_terms_from_candidates` 方法

### Step 4: 测试运行
```bash
cd D:\NLP_final
python run_paper_retriever.py
```

**测试用例**：
1. 输入："大语言模型微调中的灾难性遗忘"
2. 输入："AI Agent 如何帮助论文检索？"
3. 输入："contrastive learning in computer vision"

### Step 5: 验证日志输出
检查控制台日志，确认：
- ✅ LLM 返回了结构化 JSON
- ✅ Topics 和 Phrases 被正确提取
- ✅ 术语数量符合限制

### Step 6: 人工评估结果
- 抽查返回的论文是否与查询相关
- 检查术语是否真的出现在候选论文中
- 评估聚类效果（是否有冗余术语）

---

## 📝 注意事项

### 5.1 LLM API 兼容性
- 确保使用的 LLM 支持 JSON 格式输出
- 如果使用 DeepSeek/GPT-4，建议在 Prompt 中强调 "Output ONLY valid JSON"

### 5.2 错误处理
- LLM 可能返回无效的 JSON（如缺少引号、括号不匹配）
- `llm_client.async_generate_json` 应包含 JSON 解析重试逻辑

### 5.3 性能优化
- 如果 LLM 响应过慢，可以考虑：
  - 减少候选论文数量（从 15 篇改为 10 篇）
  - 缩短摘要长度（从 200 字符改为 150 字符）

### 5.4 报告撰写建议
在项目报告中明确说明：
> "由于 SemRank 的 Topic Classifier 需要依赖 Microsoft Academic Graph（13,613 个主题标签）以及专门训练的多标签分类模型，复现成本较高，因此本项目采用了一种轻量级替代方案：利用 LLM 从 Semantic Scholar 首次返回的候选论文中提取并聚类研究主题与关键短语。该方案通过真实论文内容对 LLM 生成进行约束（Grounding），减少幻觉，同时保持高检索相关性。"

---

## 🔗 参考资料

1. **SemRank 论文**：`D:\NLP_final\SemRank.pdf`
   - Section 3.2: LLM-Guided Semantic-Based Retrieval
   - Figure 5: Prompt for Core Concept Identification

2. **当前代码实现**：
   - `D:\NLP_final\paper_retriever\main.py`
   - `D:\NLP_final\paper_retriever\agents\search_agent.py`

3. **教师建议**：
   - 利用 Semantic Scholar 返回的真实论文作为"动态语义索引"
   - LLM 进行"聚类归纳"而非"简单提取"
   - 结构化输出 Topics 和 Phrases

---

## ✨ 总结

本次优化的核心是**让 LLM 做它擅长的事**（理解、聚类、归纳），同时**用真实论文约束它**（避免幻觉）。这与 SemRank 的思想完全一致，只是实现方式更轻量、更适合课程项目。

**关键改进**：
1. ✅ 从"扁平提取"升级为"结构化归纳"
2. ✅ 从"简单罗列"升级为"聚类去重"
3. ✅ 明确区分"宏观主题"和"微观短语"

这将显著提升二次检索的质量，使返回的论文更符合用户的真实意图！🚀
