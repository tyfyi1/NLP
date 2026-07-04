"""
综述后处理器 - 规范化格式
1. 移除"校验后的综述"等冗余标题
2. 转换[文件名.pdf]为[1],[2]等序号引用
3. 在文章末尾添加参考文献列表（含作者、发表时间）
"""
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any
from config.settings import settings
from storage.cache import cache_manager


class ReviewPostProcessor:
    """综述后处理器"""

    def __init__(self):
        self.paper_refs: List[Dict[str, Any]] = []

    async def load_paper_metadata(self) -> Dict[str, Dict[str, Any]]:
        """加载论文元数据（从缓存摘要中提取）"""
        summaries = await cache_manager.get_all_summaries()
        metadata = {}

        for idx, summary in enumerate(summaries, 1):
            filename = summary.get("filename", "")
            content = summary.get("summary", {}).get("content", "")

            # 从摘要内容中提取信息
            meta = self._extract_metadata(content)
            meta["filename"] = filename
            meta["index"] = idx

            metadata[filename] = meta
            self.paper_refs.append(meta)

        return metadata

    def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """从摘要内容中提取元数据"""
        meta = {
            "title": "未知标题",
            "authors": "未知作者",
            "year": "未知年份",
            "source": "未知来源"
        }

        # 提取标题
        title_match = re.search(r'#{1,3}\s*(?:标题|Title)[:：]?\s*(.+?)(?=\n|#)', content, re.IGNORECASE)
        if title_match:
            meta["title"] = title_match.group(1).strip()

        # 提取作者
        author_match = re.search(r'#{1,3}\s*(?:作者|Authors?)[:：]?\s*(.+?)(?=\n|#)', content, re.IGNORECASE)
        if author_match:
            authors = author_match.group(1).strip()
            # 清理格式
            authors = re.sub(r'\*\*(.*?)\*\*', r'\1', authors)
            authors = re.sub(r'[-*•]\s*', ', ', authors)
            meta["authors"] = authors

        # 提取年份
        year_match = re.search(r'(?:发表年份|Published|Year)[:：]?\s*(\d{4})', content, re.IGNORECASE)
        if year_match:
            meta["year"] = year_match.group(1)

        # 提取发表来源
        source_match = re.search(r'(?:机构?|Institution|发表来源)[:：]?\s*(.+?)(?=\n)', content, re.IGNORECASE)
        if source_match:
            meta["source"] = source_match.group(1).strip()[:100]

        return meta

    def process(self, review_text: str, metadata: Dict[str, Dict[str, Any]]) -> str:
        """
        处理综述文本

        Args:
            review_text: 原始综述文本
            metadata: 论文元数据字典 {filename: meta}

        Returns:
            处理后的综述文本
        """
        result = review_text

        # 1. 移除冗余标题
        result = self._remove_redundant_headers(result)

        # 2. 替换引用格式
        result = self._replace_citations(result, metadata)

        # 3. 添加参考文献列表
        references = self._build_references(metadata)
        result = result + "\n\n---\n\n" + references

        return result

    def _remove_redundant_headers(self, text: str) -> str:
        """移除冗余标题和校验日志"""
        # 移除"校验后的综述"
        text = re.sub(r'^##\s*校验后的综述\s*$', '', text, flags=re.MULTILINE)

        # 移除"学术综述"
        text = re.sub(r'^#\s*学术综述\s*$', '', text, flags=re.MULTILINE)

        # 移除"校验日志"整个部分（包括标题和内容）
        text = re.sub(r'^##\s*校验日志\s*$.*?(?=\n---|\n##|\Z)', '', text, flags=re.DOTALL | re.MULTILINE)

        # 移除"---"分隔符（如果后面跟着校验日志相关内容）
        text = re.sub(r'\n---\n*(?=##\s*校验)', '\n', text)

        # 清理空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    def _replace_citations(self, text: str, metadata: Dict[str, Dict[str, Any]]) -> str:
        """
        将[文件名.pdf]替换为[1],[2]等序号

        Args:
            text: 原始文本
            metadata: 文件名到索引的映射

        Returns:
            替换后的文本
        """
        # 文件名到序号映射
        filename_to_index = {fname: meta["index"] for fname, meta in metadata.items()}

        def replace_citation(match):
            filename = match.group(1)
            if filename in filename_to_index:
                return f"[{filename_to_index[filename]}]"
            return match.group(0)

        # 替换所有[文件名.pdf]格式
        pattern = r'\[([^\]]+\.pdf)\]'
        return re.sub(pattern, replace_citation, text)

    def _build_references(self, metadata: Dict[str, Dict[str, Any]]) -> str:
        """构建参考文献列表"""
        lines = ["## 参考文献\n"]

        # 按序号排序
        sorted_refs = sorted(metadata.values(), key=lambda x: x.get("index", 0))

        for ref in sorted_refs:
            idx = ref.get("index", "?")
            title = ref.get("title", "未知标题")
            authors = ref.get("authors", "未知作者")
            year = ref.get("year", "未知年份")
            source = ref.get("source", "")

            lines.append(f"[{idx}] {authors}. **{title}**. {year}. {source}\n")

        return '\n'.join(lines)

    async def process_file(self, input_path: Path, output_path: Path):
        """处理文件"""
        # 加载元数据
        metadata = await self.load_paper_metadata()

        # 读取原始文本
        with open(input_path, 'r', encoding='utf-8') as f:
            text = f.read()

        # 处理
        processed = self.process(text, metadata)

        # 写入
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(processed)


async def process_review(input_file: str, output_file: str = None):
    """
    处理综述文件的便捷函数

    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径（可选，默认覆盖原文件）
    """
    processor = ReviewPostProcessor()

    input_path = Path(input_file)
    output_path = Path(output_file) if output_file else input_path

    await processor.process_file(input_path, output_path)

    print(f"处理完成: {output_path}")


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) < 2:
        print("用法: python post_processor.py <输入文件> [输出文件]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    asyncio.run(process_review(input_file, output_file))
