"""
本地缓存管理 - 摘要JSON持久化
"""
import json
import aiofiles
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from config.settings import settings


class CacheManager:
    """缓存管理器"""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or settings.cache_dir
        self.cache_dir.mkdir(exist_ok=True)

    def _get_cache_path(self, paper_filename: str) -> Path:
        """获取缓存文件路径"""
        # 将pdf后缀替换为json
        stem = Path(paper_filename).stem
        return self.cache_dir / f"{stem}_summary.json"

    async def save_summary(self, filename: str, summary: Dict[str, Any]) -> Path:
        """
        保存摘要到缓存

        Args:
            filename: 原始PDF文件名
            summary: 摘要内容
        """
        cache_path = self._get_cache_path(filename)

        async with aiofiles.open(cache_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps({
                "filename": filename,
                "cached_at": datetime.now().isoformat(),
                "summary": summary
            }, ensure_ascii=False, indent=2))

        return cache_path

    async def get_summary(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        读取缓存摘要

        Args:
            filename: 原始PDF文件名

        Returns:
            缓存的摘要内容，如不存在返回None
        """
        cache_path = self._get_cache_path(filename)

        if not cache_path.exists():
            return None

        async with aiofiles.open(cache_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            data = json.loads(content)
            return data.get("summary")

    async def get_all_summaries(self) -> List[Dict[str, Any]]:
        """读取全部缓存摘要"""
        summaries = []

        for cache_file in self.cache_dir.glob("*_summary.json"):
            async with aiofiles.open(cache_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
                summaries.append(data)

        # 按文件名排序
        summaries.sort(key=lambda x: x.get("filename", ""))
        return summaries

    async def clear_cache(self, filename: Optional[str] = None):
        """清除缓存"""
        if filename:
            cache_path = self._get_cache_path(filename)
            if cache_path.exists():
                cache_path.unlink()
        else:
            # 清除全部
            for cache_file in self.cache_dir.glob("*_summary.json"):
                cache_file.unlink()


# 全局缓存管理器
cache_manager = CacheManager()
