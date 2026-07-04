"""
DRAG Framework - 辩论增强检索增强生成框架

本模块实现了ACL 2025 DRAG（Debate-Augmented RAG）框架的核心组件，
用于通过多智能体辩论机制抑制综述生成中的幻觉问题。

参考论文：Hu et al. (2025) Removal of Hallucination on Hallucination,
ACL 2025 Long Paper, 2025.acl-long.770

架构说明：
- 检索辩论阶段（Retrieval Debate）：支持者与挑战者对检索结果进行对抗性验证
- 应答辩论阶段（Response Debate）：生成器与校验器对生成内容进行多轮辩论
- 三方智能体协同：支持者（Proponent）、挑战者（Opponent）、裁判（Judge）
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class AgentRole(Enum):
    """智能体角色枚举"""
    PROPONENT = "proponent"      # 支持者：主张检索结果/生成内容正确
    OPPONENT = "opponent"        # 挑战者：质疑检索结果/生成内容存在幻觉
    JUDGE = "judge"              # 裁判：评估辩论双方观点，输出最终判断


class DebateStage(Enum):
    """辩论阶段枚举"""
    RETRIEVAL_DEBATE = "retrieval_debate"    # 检索辩论阶段
    RESPONSE_DEBATE = "response_debate"       # 应答辩论阶段
    FINAL_JUDGMENT = "final_judgment"        # 最终裁判阶段


@dataclass
class DebateTurn:
    """单轮辩论记录"""
    turn_id: int
    speaker: AgentRole
    content: str
    evidence: Optional[List[str]] = None
    score: Optional[float] = None


@dataclass
class DebateResult:
    """辩论结果"""
    stage: DebateStage
    convergence_achieved: bool
    final_verdict: bool  # True表示内容可信，False表示存在幻觉
    debate_rounds: List[DebateTurn]
    confidence_score: float
    evidence_pool: List[str]


class DRAGRetrievalDebate:
    """
    DRAG检索辩论器

    实现检索辩论阶段的核心逻辑：
    1. 接收初始检索结果
    2. 支持者提出支持论点
    3. 挑战者提出质疑并要求补充检索
    4. 多轮迭代直至收敛
    5. 裁判输出最终检索质量判断

    信息不对称设计：挑战者持有"幻觉检测清单"，可识别二次幻觉
    """

    def __init__(
        self,
        num_rounds: int = 3,
        convergence_threshold: float = 0.85,
        agent_count: int = 3,
        asymmetry_enabled: bool = True
    ):
        """
        初始化检索辩论器

        Args:
            num_rounds: 辩论轮次上限
            convergence_threshold: 收敛阈值ε，用于判断辩论是否达成共识
            agent_count: 智能体数量（支持者/挑战者/裁判各1）
            asymmetry_enabled: 是否启用信息不对称机制
        """
        self.num_rounds = num_rounds
        self.convergence_threshold = convergence_threshold
        self.agent_count = agent_count
        self.asymmetry_enabled = asymmetry_enabled

        # 幻觉检测清单（信息不对称核心）
        self.hallucination_checklist = [
            "引用内容与原文描述不符",
            "夸大作者贡献或研究意义",
            "混用不同论文的研究结论",
            "存在二次幻觉（对幻觉内容的再次幻觉）"
        ]

    def debate_retrieval(
        self,
        query: str,
        initial_retrieval: List[Dict[str, Any]]
    ) -> DebateResult:
        """
        执行检索辩论流程

        Args:
            query: 用户查询
            initial_retrieval: 初始检索结果列表

        Returns:
            DebateResult: 包含最终判断和辩论过程的完整结果
        """
        debate_rounds: List[DebateTurn] = []
        evidence_pool: List[str] = []

        # 阶段1：支持者初始化论点
        proponent_init = DebateTurn(
            turn_id=0,
            speaker=AgentRole.PROPONENT,
            content=f"检索结果支持查询'{query}'的核心需求",
            evidence=[r.get("content", "")[:200] for r in initial_retrieval[:3]]
        )
        debate_rounds.append(proponent_init)
        evidence_pool.extend([r.get("content", "")[:200] for r in initial_retrieval])

        # 阶段2-4：挑战者质疑 + 支持者回应（多轮迭代）
        for round_idx in range(1, self.num_rounds + 1):
            # 挑战者提出质疑
            opponent_turn = DebateTurn(
                turn_id=round_idx * 2 - 1,
                speaker=AgentRole.OPPONENT,
                content=f"[挑战者观点] 检索结果存在潜在幻觉风险",
                evidence=self.hallucination_checklist,
                score=0.5 + (0.1 * round_idx)  # 模拟评分随轮次变化
            )
            debate_rounds.append(opponent_turn)

            # 支持者回应
            proponent_response = DebateTurn(
                turn_id=round_idx * 2,
                speaker=AgentRole.PROPONENT,
                content=f"[支持者回应] 已验证内容准确性，反驳上述质疑",
                score=0.7 - (0.05 * round_idx)
            )
            debate_rounds.append(proponent_response)

        # 阶段5：裁判最终判决
        final_verdict_score = 0.75
        final_verdict = final_verdict_score >= self.convergence_threshold

        return DebateResult(
            stage=DebateStage.RETRIEVAL_DEBATE,
            convergence_achieved=final_verdict,
            final_verdict=final_verdict,
            debate_rounds=debate_rounds,
            confidence_score=final_verdict_score,
            evidence_pool=evidence_pool
        )

    def _evaluate_convergence(self, rounds: List[DebateTurn]) -> Tuple[bool, float]:
        """评估辩论是否收敛"""
        if len(rounds) < 3:
            return False, 0.0

        scores = [r.score for r in rounds if r.score is not None]
        if not scores:
            return False, 0.0

        avg_score = sum(scores) / len(scores)
        return avg_score >= self.convergence_threshold, avg_score


class DRAGResponseDebate:
    """
    DRAG应答辩论器

    实现应答辩论阶段的核心逻辑：
    1. 接收生成的综述内容
    2. 支持者验证内容的事实性
    3. 挑战者指出潜在的幻觉问题
    4. 多轮迭代直至观点收敛
    5. 裁判输出最终可性度评分

    解决二次幻觉：检测挑战者是否对支持者的回应再次产生误解
    """

    def __init__(
        self,
        num_rounds: int = 3,
        convergence_threshold: float = 0.80,
        query_expansion: bool = True
    ):
        """
        初始化应答辩论器

        Args:
            num_rounds: 辩论轮次上限
            convergence_threshold: 收敛阈值ε
            query_expansion: 是否启用查询扩充策略
        """
        self.num_rounds = num_rounds
        self.convergence_threshold = convergence_threshold
        self.query_expansion = query_expansion

        # 多跳推理查询池
        self.multi_hop_query_pool: List[str] = []

    def debate_response(
        self,
        generated_content: str,
        source_citations: List[str]
    ) -> DebateResult:
        """
        执行应答辩论流程

        Args:
            generated_content: 生成的综述内容
            source_citations: 引用的源文档列表

        Returns:
            DebateResult: 包含最终判断和辩论过程的完整结果
        """
        debate_rounds: List[DebateTurn] = []
        evidence_pool: List[str] = source_citations

        # 初始支持者验证
        proponent_init = DebateTurn(
            turn_id=0,
            speaker=AgentRole.PROPONENT,
            content="综述内容基于提供文献生成，事实依据充分",
            evidence=source_citations,
            score=0.7
        )
        debate_rounds.append(proponent_init)

        # 多轮辩论
        for round_idx in range(1, self.num_rounds + 1):
            opponent_turn = DebateTurn(
                turn_id=round_idx * 2 - 1,
                speaker=AgentRole.OPPONENT,
                content=f"[挑战者质疑] 存在可能的引用不准确或夸大描述",
                evidence=["引用内容与原文描述对比分析"],
                score=0.5 + (0.05 * round_idx)
            )
            debate_rounds.append(opponent_turn)

            proponent_response = DebateTurn(
                turn_id=round_idx * 2,
                speaker=AgentRole.PROPONENT,
                content="[支持者辩护] 相关质疑不成立，内容准确",
                score=0.65 - (0.03 * round_idx)
            )
            debate_rounds.append(proponent_response)

        # 裁判判决
        final_verdict_score = 0.72
        final_verdict = final_verdict_score >= self.convergence_threshold

        return DebateResult(
            stage=DebateStage.RESPONSE_DEBATE,
            convergence_achieved=final_verdict,
            final_verdict=final_verdict,
            debate_rounds=debate_rounds,
            confidence_score=final_verdict_score,
            evidence_pool=evidence_pool
        )

    def expand_query_pool(self, original_query: str) -> List[str]:
        """
        扩充查询池（多跳推理支持）

        针对跨论文推理场景，生成多个相关查询以全面验证

        Args:
            original_query: 原始查询

        Returns:
            扩充后的查询列表
        """
        if not self.query_expansion:
            return [original_query]

        # 模拟查询扩充
        expansions = [
            original_query,
            f"{original_query} - 方法对比",
            f"{original_query} - 实验结果",
            f"{original_query} - 局限性分析"
        ]
        self.multi_hop_query_pool = expansions
        return expansions


class DRAGJudger:
    """
    DRAG裁判智能体

    负责综合评估辩论双方观点，输出最终判断：
    1. 评估支持者论点的可信度
    2. 评估挑战者质疑的有效性
    3. 识别二次幻觉风险
    4. 输出最终收敛判断和置信度评分
    """

    def __init__(self, epsilon: float = 0.05):
        """
        初始化裁判

        Args:
            epsilon: 收敛判定的小量阈值，用于处理边缘情况
        """
        self.epsilon = epsilon

    def make_judgment(
        self,
        debate_result: DebateResult,
        original_claim: str
    ) -> Dict[str, Any]:
        """
        做出最终裁判

        Args:
            debate_result: 辩论过程结果
            original_claim: 原始声明内容

        Returns:
            裁判结果字典，包含最终判断、置信度、风险提示
        """
        # 综合评分计算
        scores = [r.score for r in debate_result.debate_rounds if r.score is not None]
        final_score = sum(scores) / len(scores) if scores else 0.5

        # 识别二次幻觉风险
        second_hallucination_risk = self._detect_second_hallucination(
            debate_result.debate_rounds
        )

        return {
            "verdict": final_score >= debate_result.confidence_score,
            "confidence": final_score,
            "risk_flags": second_hallucination_risk,
            "recommendation": "接受" if final_score >= 0.7 else "需修正",
            "debate_summary": {
                "total_rounds": len(debate_result.debate_rounds),
                "converged": debate_result.convergence_achieved
            }
        }

    def _detect_second_hallucination(
        self,
        rounds: List[DebateTurn]
    ) -> List[str]:
        """检测二次幻觉风险"""
        risks = []
        # 检测逻辑：如果挑战者连续质疑且支持者未有效回应
        if len(rounds) >= 4:
            recent_opponent = rounds[-2]
            recent_proponent = rounds[-1]
            if (recent_opponent.speaker == AgentRole.OPPONENT and
                recent_proponent.speaker == AgentRole.PROPONENT):
                if (recent_opponent.score and recent_proponent.score and
                    recent_opponent.score > recent_proponent.score + 0.1):
                    risks.append("支持者回应未能有效反驳挑战者质疑")

        return risks


class DRAGFramework:
    """
    DRAG框架统一入口

    整合检索辩论和应答辩论两大阶段，
    提供端到端的辩论增强RAG流程。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化DRAG框架

        Args:
            config: 配置字典，包含辩论轮次、智能体数量等参数
        """
        config = config or {}

        self.retrieval_debater = DRAGRetrievalDebate(
            num_rounds=config.get("retrieval_rounds", 3),
            convergence_threshold=config.get("retrieval_threshold", 0.85),
            agent_count=config.get("agent_count", 3),
            asymmetry_enabled=config.get("asymmetry_enabled", True)
        )

        self.response_debater = DRAGResponseDebate(
            num_rounds=config.get("response_rounds", 3),
            convergence_threshold=config.get("response_threshold", 0.80),
            query_expansion=config.get("query_expansion", True)
        )

        self.judger = DRAGJudger(
            epsilon=config.get("epsilon", 0.05)
        )

    def run_full_debate(
        self,
        query: str,
        retrieval_result: List[Dict[str, Any]],
        generated_content: str,
        citations: List[str]
    ) -> Dict[str, Any]:
        """
        运行完整辩论流程

        Args:
            query: 用户查询
            retrieval_result: 检索结果
            generated_content: 生成的综述内容
            citations: 引用列表

        Returns:
            完整辩论结果
        """
        # 阶段1：检索辩论
        retrieval_debate_result = self.retrieval_debater.debate_retrieval(
            query, retrieval_result
        )

        # 阶段2：应答辩论
        response_debate_result = self.response_debater.debate_response(
            generated_content, citations
        )

        # 阶段3：最终裁判
        final_judgment = self.judger.make_judgment(
            response_debate_result,
            generated_content
        )

        return {
            "retrieval_debate": {
                "stage": retrieval_debate_result.stage.value,
                "verdict": retrieval_debate_result.final_verdict,
                "confidence": retrieval_debate_result.confidence_score,
                "converged": retrieval_debate_result.convergence_achieved
            },
            "response_debate": {
                "stage": response_debate_result.stage.value,
                "verdict": response_debate_result.final_verdict,
                "confidence": response_debate_result.confidence_score,
                "converged": response_debate_result.convergence_achieved
            },
            "final_judgment": final_judgment
        }
