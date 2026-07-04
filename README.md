# AI文献辅助系统

基于大语言模型的学术文献处理一站式解决方案，整合论文检索、摘要生成、综述写作、文献翻译四大核心功能。

## 项目架构

```
AI文献辅助系统
├── 前端页面 (HTML/CSS/JS)
├── 主服务器 (Node.js + Express + MongoDB)
│   └── 端口: 3002
└── 后端微服务 (Python)
    ├── 论文检索服务 ────── 端口: 5002
    ├── 论文总结服务 ────── 端口: 5001
    ├── 论文翻译服务 ────── 端口: 5003
    └── 综述生成服务 ────── 端口: 8002
```

## 核心功能模块

### 1. 自动检索 (论文检索)

基于**SemRank**两阶段检索框架，实现学术论文智能检索。

- **检索模式**: 单阶段检索 / 两阶段检索（默认）
- **排序策略**: 语义相似度 + 引用热度综合排序
- **数据来源**: Semantic Scholar API
- **关键特性**: 概念匹配、多跳推理、相关性评分

**接口**: `POST /api/proxy/retrieve`

### 2. 自动总结 (论文摘要)

基于**ACL 2023 Element-aware Summarization**论文，实现论文智能摘要生成。

- **摘要模式**: 简洁摘要 / 详细摘要 / 结构化摘要（默认）
- **支持格式**: PDF、Word、HTML、TXT、Markdown
- **智能输出**: 根据论文类型自动调整输出结构
- **质量评估**: 内置摘要质量评分机制

**接口**: `POST /api/proxy/summary`

### 3. 综述生成 (DRAG框架)

基于**ACL 2025 DRAG (Debate-Augmented RAG)**框架，实现学术综述自动生成与幻觉抑制。

- **核心机制**: 多智能体辩论（支持者/挑战者/裁判）
- **两大阶段**: 检索辩论 → 应答辩论
- **关键特性**: 信息不对称设计、二次幻觉检测、引用校验

**接口**: `POST /api/full-pipeline`

### 4. 自动翻译 (DelTA框架)

基于**DelTA多级记忆**翻译框架，实现学术论文精准翻译。

- **支持格式**: PDF、Markdown、Word、TXT
- **公式保护**: LaTeX公式完整保留，不翻译
- **术语统一**: 专有名词对照记忆，全文术语一致
- **学术优化**: 符合ICLR/ACL顶会中文表达规范

**接口**: `POST /api/proxy/translate`

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | HTML5 + CSS3 + JavaScript | 单页应用，响应式设计 |
| 主服务 | Node.js + Express | API网关、代理、用户管理 |
| 数据库 | MongoDB | 用户信息、API配置存储 |
| 检索服务 | Flask + Semantic Scholar API | 论文检索 |
| 总结服务 | Flask + SiliconFlow API | 摘要生成 |
| 翻译服务 | Flask + MiniMax API | 文献翻译 |
| 综述服务 | FastAPI + Volcengine Ark API | DRAG综述生成 |

## 环境准备

### 1. 安装依赖

```bash
# 安装Python依赖
pip install -r requirements.txt

# 安装Node.js依赖
npm install
```

### 2. 配置API密钥


### 3. 配置子模块

各子模块的详细配置请参考对应目录的说明文件：

- `综述生成/config/settings.py` - DRAG框架配置
- `自动检索/.env` - 检索服务配置
- `自动总结/api.py` - 总结服务配置
- `自动翻译/translator_delta.py` - 翻译服务配置

## 启动方式

### 方式一：使用一键重启脚本（不推荐）

```bash
restart_all.bat
```

### 方式二：手动启动各服务

按顺序启动以下服务：

```bash
# 1. 启动论文检索API服务
cd 自动检索
python paper_retriever_api.py

# 2. 启动论文总结API服务
cd 自动总结
python api.py

# 3. 启动论文翻译API服务
cd ..
python translate_api.py

# 4. 启动综述生成API服务
cd 综述生成
python main.py

# 5. 启动主服务器（前端+代理）
cd ..
node server.js
```

### 方式三：使用简易启动脚本

```bash
python start_simple.py
```

## 服务端口说明

| 服务 | 端口 | 地址 |
|------|------|------|
| 主服务器（前端） | 3002 | http://localhost:3002 |
| 论文总结API | 5001 | http://localhost:5001 |
| 论文检索API | 5002 | http://localhost:5002 |
| 论文翻译API | 5003 | http://localhost:5003 |
| 综述生成API | 8002 | http://localhost:8002 |

## 前端页面

| 页面 | 功能 | 地址 |
|------|------|------|
| `index.html` | 首页导航 | http://localhost:3002/index.html |
| `retrieve.html` | 论文检索 | http://localhost:3002/retrieve.html |
| `summary.html` | 论文总结 | http://localhost:3002/summary.html |
| `review.html` | 综述生成 | http://localhost:3002/review.html |
| `translate.html` | 论文翻译 | http://localhost:3002/translate.html |

## API接口

### 主服务器代理接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/proxy/summary` | POST | 论文总结 |
| `/api/proxy/retrieve` | POST | 论文检索 |
| `/api/proxy/translate` | POST | 论文翻译 |
| `/api/health` | GET | 健康检查 |

### 用户管理接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/register` | POST | 用户注册 |
| `/api/login` | POST | 用户登录 |
| `/api/api-config` | POST | 保存API配置 |
| `/api/api-config/:userId` | GET | 获取API配置 |

## 目录结构

```
NLP/
├── 综述生成/              # DRAG综述生成模块
│   ├── api/              # FastAPI接口
│   ├── config/           # 配置文件
│   ├── core/             # 核心逻辑（摘要、综述、校验）
│   ├── llm/              # LLM客户端
│   ├── storage/          # 缓存存储
│   ├── utils/            # 工具函数
│   ├── main.py           # 启动入口
│   └── drag_framework.py # DRAG框架实现
├── 自动总结/              # 论文摘要生成模块
│   ├── api.py            # Flask API接口
│   ├── summary_agent.py  # 摘要智能体
│   └── paper_extractor.py # 论文提取器
├── 自动检索/              # 论文检索模块
│   ├── paper_retriever/  # 检索核心模块
│   │   ├── agents/       # 检索智能体
│   │   ├── models/       # 数据模型
│   │   └── utils/        # 工具函数
│   └── run_paper_retriever.py # 启动入口
├── 自动翻译/              # 论文翻译模块
│   └── translator_delta.py # DelTA翻译智能体
├── server.js             # 主服务器（Node.js）
├── package.json          # Node.js依赖配置
├── requirements.txt      # Python依赖配置
├── restart_all.bat       # 一键重启脚本
└── start_simple.py       # 简易启动脚本
```

## 参考论文

1. **DRAG框架**: Hu et al. (2025) *Removal of Hallucination on Hallucination*, ACL 2025
2. **Element-aware Summarization**: ACL 2023 Long Paper (2023.acl-long.482)
3. **SemRank**: 两阶段检索优化框架
4. **DelTA**: 多级记忆翻译框架

## 注意事项

1. **API密钥安全**: 请勿将API密钥提交到版本控制系统，使用 `.env` 文件管理
2. **网络环境**: 部分API服务需要稳定的网络连接
3. **服务依赖**: 主服务器启动前，请确保所有后端微服务已启动
4. **端口冲突**: 如果端口被占用，请修改对应配置文件中的端口号
5. **MongoDB**: 用户管理功能依赖MongoDB，如不需要可跳过安装

## 许可证

MIT License
