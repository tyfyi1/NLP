# 自动总结模块 (Auto Summary Module)

## 功能介绍

该模块提供论文自动总结功能，通过调用大模型API实现单篇论文的摘要生成。

### 主要特性

- **支持中英文论文**：无论输入是中文还是英文，输出都是中文摘要
- **数字保真度高**：实验数据、年份、模型名称严格忠实原文
- **智能结构输出**：根据论文类型自动选择输出部分
  - 研究论文：输出完整5部分（背景、方法、实验、结论、关键词）
  - 综述论文：自动省略实验结果部分
- **支持三种摘要模式**：
  - 简洁摘要（simple）：快速生成300-500字的核心内容总结
  - 详细摘要（detailed）：500-800字详细总结
  - 结构化摘要（structured）：结构化输出，包含研究背景、方法、结果、结论、关键词

### 使用模型

默认使用 **THUDM/GLM-4-9B-0414**（智谱AI）：
- 硅基流动免费模型（9B以下永久免费）
- 长文本处理能力优于 Qwen2.5-7B
- 数字、专有名词保真度高
- 中英文摘要质量稳定

也可指定使用 `Qwen/Qwen2.5-7B-Instruct` 等其他模型。

### 参考论文

基于 ACL 2023 顶会论文：
- **论文名称**：Element-aware Summarization with Large Language Models: Expert-aligned Evaluation and Chain-of-Thought Method
- **会议**：ACL 2023（CCF-A类顶会）
- **链接**：https://aclanthology.org/2023.acl-long.482.pdf

## 目录结构

```
auto_summary/
├── summary_agent.py      # 核心智能体实现
├── paper_extractor.py    # 论文提取器（支持PDF/Word/HTML/TXT/Markdown）
├── api.py                # Flask API接口
├── README.md             # 使用说明
└── AGENT_DESIGN.md       # 智能体设计文档
```

## 安装依赖

```bash
pip install requests flask pdfplumber python-docx beautifulsoup4
```

## 使用方法

### 摘要类型说明

本智能体支持三种摘要类型，**默认使用结构化摘要（structured）**：

| 类型 | 参数值 | 输出格式 | 字数 | 适用场景 |
|------|--------|---------|------|---------|
| 简洁摘要 | `simple` | 一段话 | 300-500字 | 快速浏览，了解论文大意 |
| 详细摘要 | `detailed` | 详细段落 | 500-800字 | 需要更多细节 |
| 结构化摘要 | `structured` | 【研究背景】【核心方法】等分段 | 1000-2000字 | 正式报告、论文整理（**默认**） |

**智能结构输出**：结构化摘要会根据论文类型自动调整：
- 研究论文：输出完整5部分（背景、方法、实验、结论、关键词）
- 综述论文：自动省略实验结果部分（因为综述通常没有原创实验）

### 方式1：直接调用智能体

```python
from auto_summary.summary_agent import SummaryAgent

# 创建智能体
agent = SummaryAgent(api_key="your-api-key")

# 默认生成结构化摘要（不需要指定参数）
text = "论文内容..."
summary = agent.summarize(text)

# 也可以手动指定摘要类型
simple_summary = agent.summarize(text, summary_type="simple")
detailed_summary = agent.summarize(text, summary_type="detailed")
structured_summary = agent.summarize(text, summary_type="structured")

# 多阶段总结
results = agent.multi_stage_summarize(text)

# 质量评估
quality = agent.assess_quality(text, summary)
```

### 方式2：先提取论文再总结

```python
from auto_summary.summary_agent import SummaryAgent
from auto_summary.paper_extractor import PaperExtractor

# 创建提取器和智能体
extractor = PaperExtractor(max_chars=15000)
agent = SummaryAgent(api_key="your-api-key")

# 提取论文文本（支持PDF/Word/HTML/TXT/Markdown）
text = extractor.extract_from_file("paper.pdf")

# 生成摘要
summary = agent.summarize(text, summary_type="structured")
print(summary)
```

### 方式3：通过API接口调用

1. 设置环境变量：
```bash
export SILICONFLOW_API_KEY="your-api-key"
```

2. 启动API服务：
```bash
python auto_summary/api.py
```

3. 调用API：
```bash
curl -X POST http://localhost:5001/api/summary \
  -H "Content-Type: application/json" \
  -d '{
    "text": "论文内容...",
    "type": "structured"
  }'
```

### API接口说明

#### POST /api/summary

生成论文摘要

**请求参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| text | string | 是 | 论文内容 |
| type | string | 否 | 摘要类型：`simple`(默认)、`detailed` 或 `structured` |
| max_tokens | int | 否 | 最大输出长度，默认1024 |

**返回结果：**
```json
{
  "success": true,
  "summary": "生成的摘要内容",
  "quality": 0.95,
  "message": "成功"
}
```

#### GET /api/health

健康检查接口

#### GET /api/info

获取智能体信息

## 配置说明

### 环境变量

- `SILICONFLOW_API_KEY`: 硅基流动API密钥

### API密钥获取

1. 访问 https://cloud.siliconflow.cn/
2. 注册账号并登录
3. 在控制台获取API密钥

## 示例输出

### 简洁摘要

```
本文提出了一种基于知识蒸馏和结构化剪枝的大型语言模型压缩方法。实验结果表明，该方法在GLUE基准测试集上保持了95%以上的性能，同时模型参数量减少了60%，推理速度提升了3倍。该研究为大型语言模型的轻量化部署提供了有效的解决方案。
```

### 结构化摘要

```
【研究背景】
大型语言模型在自然语言处理任务中表现出色，但需要大量计算资源，限制了其在资源受限环境中的应用。

【核心方法】
本研究提出了一种新的模型压缩方法，通过知识蒸馏和结构化剪枝相结合的方式，在保持模型性能的同时显著减小模型规模。

【实验结果】
在GLUE基准测试集上保持了95%以上的性能，同时模型参数量减少了60%，推理速度提升了3倍。

【主要结论】
该研究为大型语言模型的轻量化部署提供了有效的解决方案，具有重要的实际应用价值。

【关键词】
大型语言模型，模型压缩，知识蒸馏，结构化剪枝
```

## 性能指标

| 指标 | 数值 |
|------|------|
| 平均处理时间 | ~17秒/篇 |
| 成功率 | 100% |
| 平均质量分数 | 0.94/1.0 |
| 支持语言 | 中文、英文 |
| 支持格式 | PDF、Word(.docx)、HTML、TXT、Markdown |

## 测试

运行测试脚本：

```bash
python auto_summary/test_final_performance.py
```

## 注意事项

1. 确保API密钥有效且有足够的调用额度
2. 论文内容不宜过长，建议控制在15000字符以内
3. 网络请求可能受网络环境影响，建议设置合理的超时时间
4. 扫描件PDF需要额外安装Tesseract OCR引擎