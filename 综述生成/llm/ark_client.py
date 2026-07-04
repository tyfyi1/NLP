"""
火山方舟 Ark API 客户端封装
纯文本模式，支持429限流指数退避重试
"""
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from config.settings import settings
from utils.retry import with_retry


class ArkClient:
    """方舟API异步客户端"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.api_key
        self.base_url = settings.base_url
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_requests)

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def _request(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """发送请求到方舟API（带并发控制）"""
        async with self.semaphore:
            async with httpx.AsyncClient(timeout=300.0) as client:
                # 设置较大的max_tokens以支持长文本输出
                payload = {
                    "model": model,
                    "input": messages,
                    "max_output_tokens": 16000,
                    **kwargs
                }
                response = await client.post(
                    f"{self.base_url}/responses",
                    headers=self._build_headers(),
                    json=payload
                )
                response.raise_for_status()
                return response.json()

    @with_retry(max_retries=settings.max_retries, initial_delay=settings.initial_retry_delay)
    async def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        通用聊天接口

        Args:
            model: 模型名称
            messages: 消息列表
            **kwargs: 其他参数（stream等）
        """
        return await self._request(model, messages, **kwargs)

    async def analyze_text(
        self,
        model: str,
        text: str,
        prompt: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        分析文本内容

        Args:
            model: 模型名称
            text: 文本内容
            prompt: 分析提示词
        """
        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": f"{prompt}\n\n## 待分析文本\n\n{text}"
                }
            ]
        }]

        return await self.chat(model, messages, **kwargs)

    async def batch_analyze_texts(
        self,
        model: str,
        texts: List[str],
        prompts: List[str],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        批量分析多个文本

        Args:
            model: 模型名称
            texts: 文本列表
            prompts: 每个文本对应的提示词
        """
        results = []

        for text, prompt in zip(texts, prompts):
            result = await self.analyze_text(model, text, prompt)
            results.append(result)

        return results


# 全局客户端实例
ark_client = ArkClient()
