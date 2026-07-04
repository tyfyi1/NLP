"""
PDF文字提取工具
由于方舟API不支持直接处理PDF二进制，需要先提取文字再发送给模型
"""
from PyPDF2 import PdfReader
from pathlib import Path
from typing import Optional


class PDFTextExtractor:
    """PDF文字提取器"""

    @staticmethod
    def extract_text(pdf_path: Path, max_chars: int = 50000) -> str:
        """
        从PDF提取文字

        Args:
            pdf_path: PDF文件路径
            max_chars: 最大提取字符数（避免超出模型输入限制）

        Returns:
            提取的文本内容
        """
        try:
            reader = PdfReader(str(pdf_path))
            text_parts = []

            for page_num, page in enumerate(reader.pages):
                if page_num >= 50:  # 最多处理50页
                    break
                text = page.extract_text()
                if text:
                    text_parts.append(f"[第{page_num + 1}页]\n{text}")

            full_text = "\n\n".join(text_parts)

            # 截断超长文本
            if len(full_text) > max_chars:
                full_text = full_text[:max_chars] + f"\n\n[...文档已截断，原文共{len(full_text)}字符...]"

            return full_text

        except Exception as e:
            return f"[PDF提取失败: {str(e)}]"

    @staticmethod
    def get_text_preview(pdf_path: Path, max_chars: int = 2000) -> str:
        """
        获取PDF文字预览（前几段）

        Args:
            pdf_path: PDF文件路径
            max_chars: 最大字符数
        """
        text = PDFTextExtractor.extract_text(pdf_path, max_chars=max_chars)
        return text[:max_chars] + "..." if len(text) > max_chars else text
