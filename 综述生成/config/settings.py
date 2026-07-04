"""
应用配置管理

DRAG框架配置说明（ACL 2025 - 2025.acl-long.770）：
DRAG（Debate-Augmented RAG）通过多智能体辩论机制抑制综述幻觉，
包含检索辩论和应答辩论两大阶段，配合信息不对称设计解决二次幻觉问题。
"""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """应用配置"""

    # API配置
    api_key: str = "04781532-63f2-4cce-a096-74538d16965c"
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

    # 模型配置 - 该API Key仅可访问 deepseek-v4-pro-260425
    lite_model: str = "deepseek-v4-pro-260425"
    pro_model: str = "deepseek-v4-pro-260425"

    # 并发控制
    max_concurrent_requests: int = 3
    max_retries: int = 5
    initial_retry_delay: float = 1.0

    # 文件路径
    papers_dir: Path = Path(__file__).parent.parent / "local_papers"
    cache_dir: Path = Path(__file__).parent.parent / "cache"
    output_dir: Path = Path(__file__).parent.parent / "output"

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8002

    # ==================== DRAG框架配置（ACL 2025） ====================
    # 参考论文：Hu et al. (2025) Removal of Hallucination on Hallucination, ACL 2025 Long Paper
    # 论文Figure 2框架：检索辩论(Retrieval Debate) → 应答辩论(Response Debate) → 三方智能体协同

    # DRAG开关：启用/禁用DRAG辩论增强机制
    drag_enable: bool = True
    drag_switch: bool = True  # 主开关，与drag_enable联动

    # 检索辩论阶段配置（Retrieval Debate）
    retrieval_debate_rounds: int = 3  # 检索辩论轮次上限
    retrieval_convergence_threshold: float = 0.85  # 检索辩论收敛阈值ε

    # 应答辩论阶段配置（Response Debate）
    response_debate_rounds: int = 3  # 应答辩论轮次上限
    response_convergence_threshold: float = 0.80  # 应答辩论收敛阈值ε

    # 三方智能体配置（Proponent/Opponent/Judge）
    agent_count: int = 3  # 智能体数量（支持者/挑战者/裁判各1）
    proponent_model: str = "deepseek-v4-pro-260425"  # 支持者智能体模型
    opponent_model: str = "deepseek-v4-pro-260425"  # 挑战者智能体模型
    judge_model: str = "deepseek-v4-pro-260425"  # 裁判智能体模型

    # 信息不对称配置（Asymmetry Design）
    asymmetry_enabled: bool = True  # 启用信息不对称机制
    opponent_knowledge: str = "hallucination_checklist"  # 挑战者持有幻觉检测清单

    # 查询扩充策略（Query Expansion for Multi-hop）
    query_expansion_enabled: bool = True  # 启用多跳查询扩充
    max_query_pool_size: int = 5  # 查询池最大容量

    # 二次幻觉检测配置（Second-order Hallucination）
    second_hallucination_detection: bool = True  # 启用二次幻觉检测
    hallucination_threshold: float = 0.15  # 幻觉判定阈值

    # 证据池配置（Evidence Pool）
    max_evidence_pool_size: int = 20  # 最大证据池容量
    evidence_retention_threshold: float = 0.6  # 证据保留阈值

    # 收敛判定配置
    epsilon: float = 0.05  # 收敛判定小量阈值ε
    max_debate_turns: int = 6  # 最大辩论总轮次

    # DRAG性能优化
    cache_debate_results: bool = True  # 缓存辩论结果
    parallel_debate: bool = False  # 并行辩论模式（实验性）

    class Config:
        env_file = ".env"


settings = Settings()

# 确保目录存在
settings.cache_dir.mkdir(exist_ok=True)
settings.output_dir.mkdir(exist_ok=True)
settings.papers_dir.mkdir(exist_ok=True)
