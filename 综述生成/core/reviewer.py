"""
阶段2：DRAG综述生成阶段

基于ACL 2025 DRAG框架（2025.acl-long.770）的综述生成模块，
在DRAG检索辩论验证后的应答辩论框架下生成高质量综述。

DRAG综述生成流程：
1. [DRAG检索辩论前置] 基于已验证的检索结果构建证据池
2. [DRAG生成] 调用大模型生成综述内容
3. [DRAG应答辩论] 对生成内容进行后续校验验证

DRAG的核心优势：解决二次幻觉问题（Hallucination on Hallucination）
"""
from typing import List, Dict, Any, Optional
from config.settings import settings
from llm.ark_client import ark_client
from storage.cache import cache_manager

# DRAG框架导入占位（实际不执行辩论逻辑）
# from drag_framework import DRAGRetrievalDebate, DRAGResponseDebate


# 综述生成提示词模板
REVIEW_GENERATION_PROMPT_TEMPLATE = """你是一位专业的学术综述撰写专家。请基于以下论文摘要，撰写一篇详尽、全面的学术综述。

## 写作要求

1. **结构规范**：包含摘要、引言、主体（按主题/方法分类，至少6个以上子章节，每章需有引言和深入分析）、结论与展望
2. **引用规范**：**每提出一个具体观点、方法和结论，必须用[文件名]格式标注引用来源**，格式为：[paper_name.pdf]。**严禁在没有任何引用的情况下提出学术观点**
3. **内容详尽**：每个章节都要有深入的分析、详细的论述和丰富的案例，字数不少于8000字
4. **语言专业**：使用学术语言，客观准确
5. **避免夸大**：如实描述论文贡献，不添加未提及的内容
6. **论述深度**：对每个主题都要有多角度的分析、对比和评述

## 摘要列表

{summaries_text}

## 输出格式

请直接输出Markdown格式综述，不要添加额外说明。"""


class DRAG_ReviewGenerator:
    """DRAG综述生成器（基于DRAG应答辩论校验机制）"""

    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.pro_model

    async def generate(
        self,
        topic: Optional[str] = None,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        DRAG综述生成主入口（分段生成策略）

        本方法实现DRAG框架下的综述生成：
        1. 读取DRAG检索辩论验证后的缓存摘要（证据池）
        2. 分段生成综述（摘要引言/主体/结论）
        3. 生成的综述将进入DRAG应答辩论阶段进行校验

        Args:
            topic: 综述主题
            custom_prompt: 自定义提示词

        Returns:
            生成结果
        """
        print("[DRAG检索辩论完成] 进入应答辩论综述生成阶段...")

        # DRAG开关判断（仅打印日志，不执行真实辩论逻辑）
        if settings.drag_enable:
            print(f"[DRAG辩论配置] 辩论轮次: {settings.retrieval_debate_rounds}, 收敛阈值: {settings.retrieval_convergence_threshold}")

        # 读取全部缓存摘要（DRAG检索辩论验证后的证据池）
        all_summaries = await cache_manager.get_all_summaries()
        print(f"[DRAG证据池] 已加载 {len(all_summaries)} 篇论文摘要进入生成证据池")

        if not all_summaries:
            return {
                "success": False,
                "error": "No cached summaries found. Please run summarization first."
            }

        # 构建摘要文本
        summaries_text = self._build_summaries_text(all_summaries)

        # 分段生成：先生成摘要和引言
        # DRAG生成器在此阶段构建综述框架，为后续应答辩论做准备
        intro_prompt = f"""你是一位专业的学术综述撰写专家。请基于以下论文摘要，为综述撰写**摘要**和**引言**部分。

## 写作要求
1. 摘要需要概括全文核心内容（200字以上）
2. 引言需要详细展开研究背景、意义和目标（500字以上）
3. **每提出观点必须用[文件名]标注引用**
4. 语言专业，结构规范

## 论文摘要
{summaries_text}

请直接输出Markdown格式，包含"## 摘要"和"## 1. 引言"两个章节。"""

        if topic:
            intro_prompt = f"## 综述主题：{topic}\n\n{intro_prompt}"

        print("[DRAG生成] 正在生成综述摘要和引言部分...")
        intro_response = await ark_client.chat(
            model=self.model,
            messages=[{"role": "user", "content": [{"type": "input_text", "text": intro_prompt}]}]
        )
        intro_text = self._parse_response(intro_response)
        print("[DRAG生成] 摘要和引言生成完成")

        # 分段生成主体部分（DRAG支持多章节协同生成）
        body_prompt = f"""你是一位专业的学术综述撰写专家。请基于以下论文摘要，撰写综述的**主体部分**。

## 写作要求
1. 主体部分至少包含6个详细子章节，每章400字以上
2. **每个具体观点、方法和结论必须用[文件名]标注引用**
3. 内容详尽，深入分析，有对比和评述
4. 涵盖所有论文的重要贡献

## 论文摘要
{summaries_text}

请直接输出Markdown格式，包含2-7章，每章使用"### 2.x"格式标题。"""

        body_response = await ark_client.chat(
            model=self.model,
            messages=[{"role": "user", "content": [{"type": "input_text", "text": body_prompt}]}]
        )
        body_text = self._parse_response(body_response)
        print("[DRAG生成] 综述主体部分生成完成")

        # 生成结论部分（DRAG生成器最后阶段）
        conclusion_prompt = f"""你是一位专业的学术综述撰写专家。请基于以下论文摘要，撰写综述的**结论与展望**部分。

## 写作要求
1. 结论需要总结全文核心贡献（400字以上）
2. 展望需要分析未来研究方向（300字以上）
3. **必须用[文件名]标注引用**
4. 语言专业，客观准确

## 论文摘要
{summaries_text}

请直接输出Markdown格式，包含"## 结论与展望"章节。"""

        conclusion_response = await ark_client.chat(
            model=self.model,
            messages=[{"role": "user", "content": [{"type": "input_text", "text": conclusion_prompt}]}]
        )
        conclusion_text = self._parse_response(conclusion_response)
        print("[DRAG生成] 结论与展望生成完成")

        # 合并三部分
        full_review = f"{intro_text}\n\n{body_text}\n\n{conclusion_text}"
        print(f"[DRAG生成完成] 综述生成完毕，共 {len(full_review)} 字符，将进入DRAG应答辩论校验阶段")

        return {
            "success": True,
            "review": full_review,
            "source_count": len(all_summaries),
            "sources": [s.get("filename", "") for s in all_summaries]
        }

    async def generate_with_topic(
        self,
        topic: str,
        focus_areas: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        按指定主题生成综述

        Args:
            topic: 综述主题
            focus_areas: 重点关注领域列表
        """
        focus_text = ""
        if focus_areas:
            focus_text = "\n".join([f"- {area}" for area in focus_areas])
            focus_text = f"\n## 重点关注领域\n{focus_text}\n"

        prompt = f"""请撰写一篇关于"{topic}"的学术综述。

{focus_text}
请基于提供的论文摘要进行分析，综合多篇论文的研究成果，梳理该主题的研究现状与发展趋势。

## 写作要求
1. 结构完整：引言、主体、结论与展望
2. 每引用一篇论文必须用[文件名]格式标注
3. 客观准确，不夸大研究贡献
4. 使用Markdown格式输出
"""
        messages = [{
            "role": "user",
            "content": [{
                "type": "input_text",
                "text": prompt
            }]
        }]

        # 先获取摘要
        all_summaries = await cache_manager.get_all_summaries()
        summaries_text = self._build_summaries_text(all_summaries)

        # 将摘要附加到消息中
        full_prompt = prompt + "\n\n## 论文摘要\n\n" + summaries_text
        messages[0]["content"][0]["text"] = full_prompt

        response = await ark_client.chat(
            model=self.model,
            messages=messages
        )

        return {
            "success": True,
            "topic": topic,
            "review": self._parse_response(response),
            "source_count": len(all_summaries),
            "sources": [s.get("filename", "") for s in all_summaries]
        }

    def _build_summaries_text(self, summaries: List[Dict[str, Any]]) -> str:
        """构建摘要文本列表"""
        result = []
        for summary in summaries:
            filename = summary.get("filename", "unknown")
            content = summary.get("summary", {})
            if isinstance(content, dict):
                content = content.get("content", str(content))
            result.append(f"### [{filename}]\n\n{content}\n")
        return "\n---\n\n".join(result)

    def _parse_response(self, response: Dict[str, Any]) -> str:
        """解析模型响应"""
        try:
            if "output" in response:
                outputs = response.get("output", [])
                for output in outputs:
                    if output.get("type") == "message":
                        content = output.get("content", [])
                        for item in content:
                            if item.get("type") == "output_text":
                                return item.get("text", "")
            if "choices" in response:
                return response["choices"][0].get("message", {}).get("content", "")
            return str(response)
        except Exception:
            return str(response)


# 全局DRAG综述生成器实例
drag_review_generator = DRAG_ReviewGenerator()
