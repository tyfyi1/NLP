"""
Multi-Agent Debate Module - 多智能体辩论模块

本模块实现DRAG框架下的三方智能体协同机制：
- Proponent Agent（支持者）：主张检索结果或生成内容正确可信
- Opponent Agent（挑战者）：质疑并识别潜在的幻觉问题
- Judge Agent（裁判）：综合评估双方观点，输出最终判断

每个智能体具备独立的推理能力和角色定位，通过对抗性辩论迭代收敛。

参考论文：Hu et al. (2025) Removal of Hallucination on Hallucination,
ACL 2025 Long Paper, 2025.acl-long.770
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import time


class AgentType(Enum):
    """智能体类型枚举"""
    PROPONENT = "proponent"    # 支持者：维护内容可信度
    OPPONENT = "opponent"      # 挑战者：识别幻觉风险
    JUDGE = "judge"           # 裁判：综合评判


class MessageType(Enum):
    """消息类型枚举"""
    ARGUMENT = "argument"           # 论点消息
    EVIDENCE = "evidence"           # 证据消息
    CHALLENGE = "challenge"         # 质疑消息
    REBUTTAL = "rebuttal"           # 反驳消息
    VERDICT = "verdict"             # 裁判消息


@dataclass
class AgentMessage:
    """智能体消息"""
    sender: AgentType
    receiver: AgentType  # 可以是特定智能体或广播
    type: MessageType
    content: str
    evidence: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    round_id: int = 0


@dataclass
class AgentState:
    """智能体状态"""
    agent_type: AgentType
    belief_score: float = 0.5  # 置信度评分
    evidence_pool: List[str] = field(default_factory=list)
    argument_history: List[str] = field(default_factory=list)
    challenges_received: int = 0
    rebuttals_made: int = 0


class BaseAgent(ABC):
    """智能体基类"""

    def __init__(self, agent_type: AgentType, name: str = ""):
        self.agent_type = agent_type
        self.name = name or agent_type.value
        self.state = AgentState(agent_type=agent_type)
        self.message_queue: List[AgentMessage] = []

    @abstractmethod
    def generate_response(
        self,
        context: str,
        opponent_arguments: List[str]
    ) -> str:
        """生成智能体响应"""
        pass

    @abstractmethod
    def evaluate_evidence(self, evidence: List[str]) -> float:
        """评估证据可信度"""
        pass

    def receive_message(self, message: AgentMessage):
        """接收消息"""
        self.message_queue.append(message)
        self._update_state(message)

    def _update_state(self, message: AgentMessage):
        """更新智能体状态"""
        if message.type == MessageType.CHALLENGE:
            self.state.challenges_received += 1
        elif message.type == MessageType.REBUTTAL:
            self.state.rebuttals_made += 1


class ProponentAgent(BaseAgent):
    """
    支持者智能体

    职责：
    - 维护检索结果和生成内容可信度
    - 提供支持论点的证据
    - 回应挑战者的质疑
    - 辩护原始内容的准确性
    """

    def __init__(self, name: str = "Proponent"):
        super().__init__(AgentType.PROPONENT, name)
        self.initial_confidence: float = 0.7

    def generate_response(
        self,
        context: str,
        opponent_arguments: List[str]
    ) -> str:
        """生成支持者响应"""
        # 如果有挑战，首先回应挑战
        if opponent_arguments:
            challenge = opponent_arguments[-1]
            rebuttal = f"[支持者反驳] 针对'{challenge[:50]}...'的质疑，"
            rebuttal += "我方认为相关证据充分，具体理由如下："
            rebuttal += "1. 所引用内容与原文表述一致；"
            rebuttal += "2. 研究方法和结论描述准确；"
            rebuttal += "3. 未发现夸大或编造情况。"
            self.state.argument_history.append(rebuttal)
            return rebuttal
        else:
            # 初始论点
            argument = "[支持者论点] 内容基于提供的文献资料，"
            argument += "引用准确，论述客观，符合学术规范。"
            self.state.argument_history.append(argument)
            return argument

    def evaluate_evidence(self, evidence: List[str]) -> float:
        """评估证据可信度（高置信度）"""
        if not evidence:
            return 0.5
        # 支持者对证据给予较高评分
        return min(0.9, 0.7 + 0.05 * len(evidence))

    def initial_claim(self, content: str, citations: List[str]) -> str:
        """发起初始主张"""
        self.state.evidence_pool.extend(citations)
        claim = f"[支持者主张] 以下内容基于{citations}等文献，"
        claim += "论述有据，观点可信。"
        self.state.argument_history.append(claim)
        return claim


class OpponentAgent(BaseAgent):
    """
    挑战者智能体

    职责：
    - 识别并质疑潜在的幻觉内容
    - 要求提供补充证据
    - 追踪可能存在的二次幻觉
    - 维护"幻觉检测清单"

    信息不对称设计：挑战者持有支持者看不到的检测规则
    """

    # 幻觉检测规则（信息不对称核心）
    HALLUCINATION_RULES = [
        "引用内容与原文描述严重不符",
        "作者贡献被夸大或移花接木",
        "研究局限性被刻意淡化",
        "不同论文结论被混淆使用",
        "对质疑的回应存在逻辑漏洞"
    ]

    def __init__(self, name: str = "Opponent"):
        super().__init__(AgentType.OPPONENT, name)
        self.challenge_intensity: float = 0.6

    def generate_response(
        self,
        context: str,
        proponent_arguments: List[str]
    ) -> str:
        """生成挑战者响应"""
        challenge = "[挑战者质疑] 我方对上述内容的可信度存在疑虑，"
        challenge += "具体质疑如下：\n"

        # 模拟质疑生成
        if "引用" in context.lower():
            challenge += "- 引用内容是否与原文精确匹配？\n"
        if "方法" in context.lower():
            challenge += "- 研究方法的描述是否准确？\n"
        if "结论" in context.lower():
            challenge += "- 结论是否被夸大或误读？\n"

        challenge += "请提供更详细的证据支持。"

        self.state.argument_history.append(challenge)
        self.state.belief_score = max(0.3, self.state.belief_score - 0.1)
        return challenge

    def evaluate_evidence(self, evidence: List[str]) -> float:
        """评估证据可信度（严格标准）"""
        if not evidence:
            return 0.3
        # 挑战者对证据要求更严格
        return min(0.6, 0.3 + 0.03 * len(evidence))

    def detect_hallucination(self, content: str) -> List[str]:
        """检测幻觉内容"""
        detected_risks = []

        # 模拟幻觉检测
        if any(keyword in content for keyword in ["声称", "宣称", "表明"]):
            # 进一步检查是否有原文支持
            detected_risks.append("可能存在声称但无实证的观点")

        if "首次" in content or "第一次" in content:
            detected_risks.append("需验证'首次'说法准确性")

        if "最" in content and any(w in content for w in ["好", "优", "强", "高"]):
            detected_risks.append("最高级描述需谨慎核实")

        return detected_risks

    def check_second_hallucination(
        self,
        original_content: str,
        proponent_rebuttal: str
    ) -> bool:
        """检测二次幻觉（对幻觉内容的再次幻觉）"""
        # 如果支持者回应时引入了新的未验证说法
        new_claims = [w for w in ["因此", "可见", "证明", "表明"]
                      if w in proponent_rebuttal]
        return len(new_claims) > 0


class JudgeAgent(BaseAgent):
    """
    裁判智能体

    职责：
    - 聆听双方辩论
    - 评估论点可信度
    - 追踪辩论轮次
    - 判断是否达成收敛
    - 输出最终裁判结果
    """

    def __init__(self, name: str = "Judge", convergence_threshold: float = 0.8):
        super().__init__(AgentType.JUDGE, name)
        self.convergence_threshold = convergence_threshold
        self.debate_history: List[Dict[str, Any]] = []

    def generate_response(
        self,
        context: str,
        proponent_arguments: List[str],
        opponent_arguments: List[str]
    ) -> str:
        """生成裁判响应"""
        # 评估当前辩论状态
        proponent_strength = len(proponent_arguments) * 0.1
        opponent_strength = len(opponent_arguments) * 0.1

        score_diff = proponent_strength - opponent_strength

        if abs(score_diff) < 0.2:
            verdict = "[裁判] 双方观点势均力敌，建议继续辩论。"
        elif score_diff > 0:
            verdict = "[裁判] 支持者论点更具说服力，"
            verdict += f"置信度评估为 {0.6 + score_diff:.2f}。"
        else:
            verdict = "[裁判] 挑战者质疑更有依据，"
            verdict += f"内容可信度为 {0.5 + score_diff:.2f}。"

        return verdict

    def evaluate_evidence(self, evidence: List[str]) -> float:
        """评估证据可信度（中立标准）"""
        if not evidence:
            return 0.5
        return 0.4 + 0.05 * len(evidence)

    def record_debate_round(
        self,
        round_id: int,
        proponent_arg: str,
        opponent_arg: str,
        judge_comment: str
    ):
        """记录辩论轮次"""
        self.debate_history.append({
            "round_id": round_id,
            "proponent": proponent_arg,
            "opponent": opponent_arg,
            "judge": judge_comment,
            "timestamp": time.time()
        })

    def is_converged(self) -> bool:
        """判断辩论是否收敛"""
        if len(self.debate_history) < 2:
            return False

        # 检查最近轮次的裁判意见一致性
        if len(self.debate_history) >= 2:
            recent = self.debate_history[-1]["judge"]
            previous = self.debate_history[-2]["judge"]
            # 简化的收敛判断：裁判意见变化不大
            return recent[:20] == previous[:20]

        return False

    def final_verdict(
        self,
        proponent_strength: float,
        opponent_strength: float
    ) -> Dict[str, Any]:
        """输出最终裁判"""
        net_strength = proponent_strength - opponent_strength
        final_score = 0.5 + net_strength * 0.5

        verdict = {
            "accepted": final_score >= self.convergence_threshold,
            "confidence": final_score,
            "summary": f"最终置信度评分：{final_score:.2f}",
            "debate_rounds": len(self.debate_history)
        }

        return verdict


class MultiAgentDebateOrchestrator:
    """
    多智能体辩论协调器

    负责协调三方智能体的辩论流程：
    1. 初始化各智能体
    2. 管理辩论轮次
    3. 传递消息
    4. 控制辩论收敛
    5. 输出最终结果
    """

    def __init__(
        self,
        max_rounds: int = 3,
        convergence_threshold: float = 0.8,
        enable_asymmetry: bool = True
    ):
        """
        初始化辩论协调器

        Args:
            max_rounds: 最大辩论轮次
            convergence_threshold: 收敛阈值
            enable_asymmetry: 是否启用信息不对称机制
        """
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        self.enable_asymmetry = enable_asymmetry

        # 初始化三方智能体
        self.proponent = ProponentAgent()
        self.opponent = OpponentAgent()
        self.judge = JudgeAgent(convergence_threshold=convergence_threshold)

        self.current_round: int = 0
        self.debate_log: List[AgentMessage] = []

    def start_debate(
        self,
        topic: str,
        initial_content: str,
        citations: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        启动辩论

        Args:
            topic: 辩论主题
            initial_content: 初始内容
            citations: 引用列表

        Returns:
            辩论结果
        """
        citations = citations or []

        # 轮次0：支持者发起初始主张
        proponent_claim = self.proponent.initial_claim(
            initial_content, citations
        )
        self._log_message(
            sender=AgentType.PROPONENT,
            receiver=AgentType.OPPONENT,
            msg_type=MessageType.ARGUMENT,
            content=proponent_claim
        )

        # 主辩论循环
        proponent_args = [proponent_claim]
        opponent_args: List[str] = []

        for round_id in range(1, self.max_rounds + 1):
            self.current_round = round_id

            # 挑战者质疑
            opponent_challenge = self.opponent.generate_response(
                initial_content, proponent_args
            )
            opponent_args.append(opponent_challenge)
            self._log_message(
                sender=AgentType.OPPONENT,
                receiver=AgentType.PROPONENT,
                msg_type=MessageType.CHALLENGE,
                content=opponent_challenge
            )

            # 支持者反驳
            proponent_rebuttal = self.proponent.generate_response(
                initial_content, opponent_args
            )
            proponent_args.append(proponent_rebuttal)
            self._log_message(
                sender=AgentType.PROPONENT,
                receiver=AgentType.OPPONENT,
                msg_type=MessageType.REBUTTAL,
                content=proponent_rebuttal
            )

            # 裁判评价
            judge_comment = self.judge.generate_response(
                initial_content, proponent_args, opponent_args
            )
            self.judge.record_debate_round(
                round_id, proponent_rebuttal, opponent_challenge, judge_comment
            )
            self._log_message(
                sender=AgentType.JUDGE,
                receiver=AgentType.BROADCAST,
                msg_type=MessageType.VERDICT,
                content=judge_comment
            )

            # 检查收敛
            if self.judge.is_converged():
                break

        # 最终裁判
        proponent_strength = len(proponent_args) * 0.15
        opponent_strength = len(opponent_args) * 0.15
        final_verdict = self.judge.final_verdict(proponent_strength, opponent_strength)

        return {
            "converged": self.judge.is_converged(),
            "total_rounds": self.current_round,
            "proponent_args": proponent_args,
            "opponent_args": opponent_args,
            "final_verdict": final_verdict,
            "debate_log": self.debate_log
        }

    def _log_message(
        self,
        sender: AgentType,
        receiver: AgentType,
        msg_type: MessageType,
        content: str
    ):
        """记录消息"""
        msg = AgentMessage(
            sender=sender,
            receiver=receiver,
            type=msg_type,
            content=content,
            round_id=self.current_round
        )
        self.debate_log.append(msg)


class AgentBroadcast(Enum):
    """广播标识"""
    BROADCAST = "broadcast"
