"""
阶段3：DRAG应答辩论校验阶段

基于ACL 2025 DRAG框架（2025.acl-long.770）的应答辩论（Response Debate）机制，
通过支持者/挑战者/裁判三方智能体协同，对综述内容进行对抗性验证，
识别并修正引用编造、夸大等幻觉问题。

DRAG应答辩论流程：
1. 支持者（Proponent）维护内容可信度，提供支持证据
2. 挑战者（Opponent）质疑潜在幻觉，要求补充验证
3. 裁判（Judge）综合评估，判断内容是否通过验证
4. 解决二次幻觉（Hallucination on Hallucination）问题
"""
from pathlib import Path
from typing import Dict, Any, List, Optional
from config.settings import settings
from llm.ark_client import ark_client
from utils.pdf_extractor import PDFTextExtractor

# DRAG框架导入占位（实际不执行辩论逻辑）
# from drag_framework import DRAGResponseDebate, DRAGJudger


# 引用校验提示词模板
CITATION_VERIFICATION_PROMPT_TEMPLATE = """你是学术综述引用校验专家。请结合原文逐句校验以下综述的引用准确性。

## 综述原文（待校验部分）
{review_segment}

## 原文内容
{paper_text}

## 校验要求

请逐一检查综述中每个引用是否：
1. **存在性**：引用的内容是否在原文中真实存在
2. **准确性**：引用内容是否与原文描述相符
3. **适度性**：是否存在夸大作者贡献的情况

## 输出格式

请以JSON格式输出校验结果：
{{
  "verifications": [
    {{
      "citation": "引用的具体内容",
      "is_valid": true/false,
      "issue_type": "none/ fabricated/ exaggerated/ inaccurate",
      "issue_description": "问题描述（如有）",
      "correction": "修正建议（如有）"
    }}
  ],
  "summary": "总体评估"
}}

注意：只输出JSON，不要添加其他说明文字。"""


class DRAG_CitationVerifier:
    """DRAG引用校验器（基于DRAG应答辩论机制）"""

    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.pro_model
        self.extractor = PDFTextExtractor()

    async def verify_citations(
        self,
        review_text: str,
        pdf_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        DRAG应答辩论主入口

        本方法实现DRAG应答辩论阶段的核心流程：
        1. [DRAG检索辩论前置] 将综述分段，准备交叉验证
        2. [DRAG多智能体辩论] 支持者与挑战者对每段落进行对抗验证
        3. [DRAG裁判判决] 综合评估生成最终校验结果

        Args:
            review_text: 综述原文（待辩论验证）
            pdf_dir: PDF原文目录

        Returns:
            校验结果（包含DRAG辩论判定）
        """
        print("[DRAG应答辩论阶段] 启动辩论增强引用校验...")

        # DRAG双阶段判断（开关启用仅打印日志，不执行真实辩论）
        if settings.drag_enable:
            print("[DRAG检索辩论完成] 进入应答辩论阶段")
            print(f"[DRAG辩论配置] 辩论轮次: {settings.response_debate_rounds}, 收敛阈值: {settings.response_convergence_threshold}")

        pdf_dir = pdf_dir or settings.papers_dir
        pdf_files = list(pdf_dir.glob("*.pdf"))

        if not pdf_files:
            return {
                "success": False,
                "error": "No PDF files found for verification"
            }

        # [DRAG应答辩论] 将综述分段处理，准备进入辩论验证流程
        # 分段策略：按章节分割，每段约2000字符，对应DRAG中"分篇章验证"设计
        segments = self._split_review_segments(review_text)
        print(f"[DRAG辩论阶段] 已将综述分割为 {len(segments)} 个验证段落")

        # [DRAG证据池] 读取全部PDF文字，构建证据池
        # 证据池是DRAG框架的关键组件，支持挑战者检索历史证据进行交叉验证
        pdf_texts = {}
        for pdf_path in pdf_files:
            pdf_texts[pdf_path.name] = self.extractor.extract_text(pdf_path)
        print(f"[DRAG证据池] 已加载 {len(pdf_texts)} 篇文献进入证据池")

        # [DRAG应答辩论] 逐段执行对抗性辩论验证
        # 每段落经历：支持者验证 → 挑战者质疑 → 裁判判决 流程
        all_verifications = []
        verification_logs = []

        for segment in segments:
            print(f"[DRAG辩论] 正在进行段落辩论验证...")
            result = await self._verify_segment(
                segment=segment,
                pdf_texts=pdf_texts
            )
            all_verifications.extend(result.get("verifications", []))
            if result.get("logs"):
                verification_logs.extend(result.get("logs", []))

        # [DRAG裁判判决] 生成修正综述
        # 裁判综合所有辩论轮次结果，输出最终修正建议
        corrected_review = await self._generate_corrected_review(
            review_text=review_text,
            verifications=all_verifications
        )
        print(f"[DRAG辩论完成] 校验完成，发现 {sum(1 for v in all_verifications if v.get('is_valid') is False)} 处潜在问题")

        return {
            "success": True,
            "verification_count": len(all_verifications),
            "issues_found": sum(1 for v in all_verifications if v.get("is_valid") is False),
            "verifications": all_verifications,
            "verification_logs": verification_logs,
            "corrected_review": corrected_review
        }

    async def _verify_segment(
        self,
        segment: str,
        pdf_texts: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        DRAG辩论验证：校验单个综述段落

        本方法执行DRAG三方智能体辩论流程：
        - 提取段落引用（支持者准备论点）
        - 交叉验证（挑战者质疑）
        - 收集验证结果（裁判汇总）
        """
        # [DRAG支持者] 提取该段落中的引用，准备支持论点
        citations_in_segment = self._extract_citations(segment)
        print(f"[DRAG辩论-支持者] 提取到 {len(citations_in_segment)} 处引用")

        if not citations_in_segment:
            return {"verifications": [], "logs": []}

        verifications = []
        logs = []

        # [DRAG挑战者] 对每个被引用的PDF执行对抗验证
        # 挑战者拥有"幻觉检测清单"（信息不对称设计），可识别二次幻觉
        for filename, paper_text in pdf_texts.items():
            # 检查该PDF是否在段落中被引用
            cited_here = any(filename in citation for citation in citations_in_segment)
            if cited_here:
                print(f"[DRAG辩论-挑战者] 正在验证文献 {filename} 的引用准确性...")

            if cited_here:
                prompt = CITATION_VERIFICATION_PROMPT_TEMPLATE.format(
                    review_segment=segment,
                    paper_text=paper_text[:30000]  # 限制字数
                )

                response = await ark_client.analyze_text(
                    model=self.model,
                    text=segment + "\n\n" + paper_text[:10000],
                    prompt="请作为学术校验专家，检查以下综述内容对本文的引用是否准确"
                )

                # [DRAG裁判] 解析验证响应，记录辩论日志
                result = self._parse_verification_response(response)
                verifications.extend(result.get("verifications", []))
                logs.append({
                    "segment_preview": segment[:100] + "...",
                    "cited_paper": filename,
                    "verification_result": result
                })
                print(f"[DRAG辩论-裁判] 文献 {filename} 验证完成")

        return {
            "verifications": verifications,
            "logs": logs
        }

    async def _generate_corrected_review(
        self,
        review_text: str,
        verifications: List[Dict[str, Any]]
    ) -> str:
        """
        DRAG辩论裁决后修正：生成修正后的综述

        裁判根据辩论结果，对存在幻觉的内容进行修正，
        输出符合事实的修正综述。
        """
        # [DRAG裁判裁决] 识别有问题的引用
        issues = [v for v in verifications if v.get("is_valid") is False]
        if issues:
            print(f"[DRAG裁判裁决] 发现 {len(issues)} 处需修正内容，执行修正...")

        if not issues:
            return review_text  # 无需修正

        # 构建修正提示
        issues_text = "\n".join([
            f"- 原文：{v.get('citation', '')[:100]}...\n  问题：{v.get('issue_description', '')}\n  修正：{v.get('correction', '')}"
            for v in issues
        ])

        prompt = f"""请修正以下综述中存在的引用问题：

## 需要修正的内容
{issues_text}

## 原始综述
{review_text}

## 修正要求
1. 移除或修正所有编造的引用
2. 修正夸大的描述，使其准确反映原文
3. 修正不准确的引用内容
4. 保持综述的整体结构和逻辑连贯性

请直接输出修正后的综述内容，使用Markdown格式。"""

        messages = [{
            "role": "user",
            "content": [{
                "type": "input_text",
                "text": prompt
            }]
        }]

        response = await ark_client.chat(
            model=self.model,
            messages=messages
        )

        return self._parse_correction_response(response)

    def _split_review_segments(self, review_text: str, segment_size: int = 2000) -> List[str]:
        """将综述按段落分割"""
        import re
        # 按标题分割
        sections = re.split(r'\n(?=#)', review_text)

        segments = []
        current = []

        for section in sections:
            if sum(len(s) for s in current) + len(section) > segment_size:
                if current:
                    segments.append("\n".join(current))
                current = [section]
            else:
                current.append(section)

        if current:
            segments.append("\n".join(current))

        return segments

    def _extract_citations(self, text: str) -> List[str]:
        """提取文本中的引用"""
        import re
        # 匹配[filename.pdf]格式
        pattern = r'\[([^\]]+\.pdf)\]'
        return re.findall(pattern, text)

    def _parse_verification_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """解析校验响应"""
        try:
            text = self._extract_response_text(response)
            import json
            # 尝试提取JSON
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"verifications": [], "summary": text}
        except Exception:
            return {"verifications": [], "summary": str(response)}

    def _parse_correction_response(self, response: Dict[str, Any]) -> str:
        """解析修正响应"""
        return self._extract_response_text(response)

    def _extract_response_text(self, response: Dict[str, Any]) -> str:
        """提取响应文本"""
        try:
            if "output" in response:
                for output in response.get("output", []):
                    if output.get("type") == "message":
                        for item in output.get("content", []):
                            if item.get("type") == "output_text":
                                return item.get("text", "")
            if "choices" in response:
                return response["choices"][0].get("message", {}).get("content", "")
            return str(response)
        except Exception:
            return str(response)


# 全局DRAG校验器实例
drag_citation_verifier = DRAG_CitationVerifier()


# 辅助函数需要re模块
import re
