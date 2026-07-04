"""
阶段1：DRAG检索辩论前置 - 论文摘要提取

基于ACL 2025 DRAG框架（2025.acl-long.770）的检索辩论前置阶段，
本模块负责从PDF中提取论文内容，作为DRAG检索辩论的输入证据。

DRAG检索辩论流程（本文档对应阶段0-1）：
阶段0：PDF原文提取 → 构建原始证据池
阶段1：DRAG检索辩论 → 支持者/挑战者/裁判三方验证检索质量

DRAG的核心设计：信息不对称（Asymmetry Design）
- 挑战者持有"幻觉检测清单"，可识别二次幻觉
- 查询扩充策略支持多跳推理验证

参考论文：Hu et al. (2025) ACL 2025 2025.acl-long.770
"""
from pathlib import Path
from typing import Dict, Any, List, Optional
from config.settings import settings
from llm.ark_client import ark_client
from storage.cache import cache_manager
from utils.pdf_extractor import PDFTextExtractor

# DRAG框架导入占位（实际不执行辩论逻辑）
# from drag_framework import DRAGRetrievalDebate


# 摘要生成提示词模板
SUMMARIZE_PROMPT_TEMPLATE = """请分析以下学术论文，生成结构化摘要，包含：

1. **标题**：论文的完整标题
2. **作者/机构**：作者信息（从文本中提取）
3. **发表年份**：论文发表时间
4. **研究领域**：论文所属学科领域
5. **研究问题**：论文要解决的核心问题
6. **研究方法**：采用的主要方法和技术
7. **主要贡献**：论文的核心创新点
8. **关键结论**：主要实验/理论结果
9. **研究意义**：对领域的推动作用

请用中文输出，使用Markdown格式。"""


class DRAG_PaperSummarizer:
    """DRAG论文摘要生成器（基于DRAG检索辩论前置验证）"""

    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.lite_model
        self.extractor = PDFTextExtractor()

    async def summarize_single(
        self,
        pdf_path: Path,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        DRAG检索辩论前置：对单篇论文生成摘要

        本方法是DRAG框架的第一阶段，负责：
        1. 提取PDF原文作为证据池基础
        2. 生成结构化摘要供后续DRAG检索辩论使用

        Args:
            pdf_path: PDF文件路径
            force_regenerate: 是否强制重新生成（跳过缓存）

        Returns:
            摘要结果字典
        """
        print(f"[DRAG检索辩论前置] 正在处理论文: {pdf_path.name}")

        filename = pdf_path.name

        # 检查缓存（DRAG检索辩论结果缓存）
        if not force_regenerate:
            cached = await cache_manager.get_summary(filename)
            if cached:
                print(f"[DRAG缓存命中] 论文 {filename} 摘要已存在")
                return {
                    "filename": filename,
                    "summary": cached,
                    "cached": True
                }

        # [DRAG证据池] 提取PDF原文，构建辩论证据
        print(f"[DRAG证据池] 正在提取论文 {filename} 原文...")
        pdf_text = self.extractor.extract_text(pdf_path)

        if not pdf_text or "[PDF提取失败" in pdf_text:
            print(f"[DRAG错误] 论文 {filename} PDF文字提取失败")
            return {
                "filename": filename,
                "error": f"PDF文字提取失败: {pdf_text}",
                "cached": False
            }

        # [DRAG摘要生成] 调用lite模型生成结构化摘要
        # 摘要将作为DRAG检索辩论的重要证据输入
        print(f"[DRAG生成] 正在为论文 {filename} 生成摘要...")
        response = await ark_client.analyze_text(
            model=self.model,
            text=pdf_text,
            prompt=SUMMARIZE_PROMPT_TEMPLATE
        )

        # 解析模型输出
        summary_text = self._parse_response(response)

        # [DRAG缓存] 保存摘要至证据池
        await cache_manager.save_summary(filename, {"content": summary_text})
        print(f"[DRAG完成] 论文 {filename} 摘要生成并缓存完成")

        return {
            "filename": filename,
            "summary": {"content": summary_text},
            "cached": False
        }

    async def summarize_batch(
        self,
        pdf_dir: Optional[Path] = None,
        force_regenerate: bool = False
    ) -> List[Dict[str, Any]]:
        """
        DRAG检索辩论前置：批量生成论文摘要

        批量处理PDF文件，构建完整的DRAG检索辩论证据池

        Args:
            pdf_dir: PDF目录路径
            force_regenerate: 是否强制重新生成

        Returns:
            摘要结果列表
        """
        print("[DRAG检索辩论前置] 启动批量摘要生成，构建证据池...")

        pdf_dir = pdf_dir or settings.papers_dir
        pdf_files = list(pdf_dir.glob("*.pdf"))
        print(f"[DRAG证据池] 发现 {len(pdf_files)} 篇PDF论文待处理")

        if not pdf_files:
            return []

        results = []
        for pdf_path in pdf_files:
            try:
                result = await self.summarize_single(pdf_path, force_regenerate)
                results.append(result)
            except Exception as e:
                results.append({
                    "filename": pdf_path.name,
                    "error": str(e),
                    "cached": False
                })

        return results

    def _parse_response(self, response: Dict[str, Any]) -> str:
        """解析模型响应，提取摘要文本"""
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


# 全局DRAG摘要生成器实例
drag_paper_summarizer = DRAG_PaperSummarizer()
