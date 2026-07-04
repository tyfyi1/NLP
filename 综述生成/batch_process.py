"""
批量处理综述文件 - 规范化格式
使用方法:
  python batch_process.py                           # 处理output目录下所有文件
  python batch_process.py <文件路径>                # 处理指定文件
"""
import asyncio
import re
import sys
from pathlib import Path
from typing import Dict, List, Any
from storage.cache import cache_manager


class DRAG_ReviewFormatter:
    """DRAG综述格式化器（基于DRAG分篇章校验后处理）"""

    def __init__(self):
        self.paper_refs: List[Dict[str, Any]] = []

    async def load_paper_metadata(self) -> Dict[str, Dict[str, Any]]:
        """加载论文元数据"""
        summaries = await cache_manager.get_all_summaries()
        metadata = {}

        for idx, summary in enumerate(summaries, 1):
            filename = summary.get("filename", "")
            content = summary.get("summary", {}).get("content", "")
            meta = self._extract_metadata(content)
            meta["filename"] = filename
            meta["index"] = idx
            metadata[filename] = meta
            self.paper_refs.append(meta)

        return metadata

    def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """从缓存摘要中提取元数据"""
        meta = {"title": "未知标题", "authors": "未知作者", "year": "未知年份", "source": ""}

        # 需要过滤的非作者词汇
        non_author_terms = {
            '作者', '通讯作者', '第一作者', '其他作者', '所属机构', '机构',
            '主要机构', '研究领域', '研究问题', '研究方法', '主要贡献',
            '关键结论', '研究意义', '标题', '发表年份'
        }

        # 标题 - 多种格式
        for pattern in [
            r'(?:##|###)\s*(?:1\.\s*)?标题\s*\n(?:[*#]*\s*)?([^\n]+)',
            r'标题\s*[:：]\s*([^\n]+)',
        ]:
            match = re.search(pattern, content)
            if match:
                title = match.group(1).strip()
                title = re.sub(r'^\*+\s*', '', title)
                title = re.sub(r'\s*\*+$', '', title)
                # 移除括号内的翻译
                title = re.sub(r'（[^）]+）', '', title)
                title = re.sub(r'\([^)]+\)', '', title)
                if title and len(title) > 5:
                    meta["title"] = title
                    break

        # 作者 - 多种格式
        authors = []

        # 格式1: - **作者**：Zhenyu Wang, Zikang Wang...
        author_line = re.search(r'\*\*作者\*\*[：:]\s*([^\n]+)', content)
        if author_line:
            # 直接提取英文名字
            names = re.findall(r'[A-Z][a-z]+\s+[A-Z][a-z]+', author_line.group(1))
            authors.extend(names)

        # 格式2: 提取 ** ** 内的名字（过滤非作者词）
        name_matches = re.findall(r'\*\*([^*]+)\*\*', content)
        for name in name_matches:
            name = name.strip()
            # 跳过包含"作者"、"机构"等的
            if any(term in name for term in non_author_terms):
                continue
            # 跳过太短或太长的
            if len(name) < 2 or len(name) > 40:
                continue
            # 跳过纯数字或包含数字开头的（可能是上标残留）
            if re.match(r'^\d', name):
                continue
            # 清理名字中的上标数字残留
            name = re.sub(r'\d+$', '', name).strip()
            if name and name not in authors:
                authors.append(name)

        # 格式3: 从 "作者: Name1, Name2" 格式提取
        if not authors:
            simple_author = re.search(r'作者[：:]\s*([A-Za-z][A-Za-z\s,]+?)(?=\n|$)', content)
            if simple_author:
                names = re.findall(r'[A-Z][a-z]+\s+[A-Z][a-z]+', simple_author.group(1))
                authors.extend(names)

        # 去重并限制数量
        unique_authors = []
        for name in authors:
            if name not in unique_authors:
                unique_authors.append(name)

        if unique_authors:
            if len(unique_authors) > 3:
                meta["authors"] = "、".join(unique_authors[:3]) + "等"
            else:
                meta["authors"] = "、".join(unique_authors)

        # 年份 - 多种格式
        for pattern in [
            r'(?:##|###)\s*(?:3\.\s*)?发表年份.*?(\d{4})',
            r'发表年份.*?(\d{4})',
        ]:
            match = re.search(pattern, content)
            if match:
                meta["year"] = match.group(1)
                break

        return meta

    def format(self, text: str, metadata: Dict[str, Dict[str, Any]]) -> str:
        """格式化综述"""
        # 1. 移除冗余内容
        text = self._remove_junk(text)

        # 2. 替换引用
        text = self._replace_citations(text, metadata)

        # 3. 添加参考文献
        text += "\n\n---\n\n" + self._build_references(metadata)

        return text

    def _remove_junk(self, text: str) -> str:
        """移除冗余内容"""
        # 策略：找到第一个 ## 参考文献 并保留其之前的内容，
        # 移除后面所有的校验日志和重复内容

        # 找第一个 ## 参考文献 的位置
        ref_match = re.search(r'^##\s*参考文献', text, re.MULTILINE)
        if ref_match:
            text = text[:ref_match.start()]

        # 移除"## 校验后的综述"
        text = re.sub(r'^##\s*校验后的综述\s*$', '', text, flags=re.MULTILINE)

        # 移除"# 学术综述"
        text = re.sub(r'^#\s*学术综述\s*$', '', text, flags=re.MULTILINE)

        # 移除"引用论文: xxx.pdf" 行
        text = re.sub(r'^引用论文:\s*.+\.pdf\s*$', '', text, flags=re.MULTILINE)

        # 移除"### # 标题" 重复格式
        text = re.sub(r'^###\s+#\s+', '### ', text, flags=re.MULTILINE)

        # 移除"## 校验日志"整个部分
        text = re.sub(r'^##\s*校验日志\s*$.*', '', text, flags=re.DOTALL | re.MULTILINE)

        # 移除---分隔符
        text = re.sub(r'\n---\n*', '\n', text)

        # 清理连续空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    def _replace_citations(self, text: str, metadata: Dict[str, Dict[str, Any]]) -> str:
        """替换引用格式，未知引用和无效引用直接删除"""
        index_map = {fname: meta["index"] for fname, meta in metadata.items()}

        def replace(match):
            filename = match.group(1)
            idx = index_map.get(filename)
            if idx is None:
                # 找不到对应论文，删除该引用
                return ''
            return f"[{idx}]"

        text = re.sub(r'\[([^\]]+\.pdf)\]', replace, text)

        # 删除无法识别的引用占位符 [?]
        text = re.sub(r'\[\?\]', '', text)

        return text

    def _build_references(self, metadata: Dict[str, Dict[str, Any]]) -> str:
        """构建参考文献"""
        lines = ["## 参考文献\n"]
        for ref in sorted(metadata.values(), key=lambda x: x.get("index", 0)):
            idx = ref.get("index", "?")
            lines.append(f"[{idx}] {ref['authors']}. **{ref['title']}**. {ref['year']}. {ref['source']}\n")
        return '\n'.join(lines)


async def process_file(filepath: str):
    """处理单个文件"""
    formatter = DRAG_ReviewFormatter()
    metadata = await formatter.load_paper_metadata()

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    formatted = formatter.format(content, metadata)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(formatted)

    print(f"已处理: {filepath}")


async def process_directory(dirpath: str):
    """处理目录下所有文件"""
    formatter = DRAG_ReviewFormatter()
    metadata = await formatter.load_paper_metadata()

    path = Path(dirpath)
    for filepath in sorted(path.glob("review_*.md")):
        print(f"处理: {filepath.name}")
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        formatted = formatter.format(content, metadata)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(formatted)
        print(f"  完成: {len(formatted)} 字符")


async def main():
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if Path(filepath).is_file():
            await process_file(filepath)
        elif Path(filepath).is_dir():
            await process_directory(filepath)
    else:
        await process_directory("output")


if __name__ == "__main__":
    asyncio.run(main())
