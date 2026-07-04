import json
import logging
from typing import Any, Dict, Optional

import openai
from openai import OpenAI, AsyncOpenAI, APIError, APIConnectionError, APITimeoutError

from paper_retriever.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME, LLM_TIMEOUT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, 
                 model_name: Optional[str] = None, timeout: int = LLM_TIMEOUT):
        self.api_key = api_key or LLM_API_KEY
        self.base_url = base_url or LLM_BASE_URL
        self.model_name = model_name or LLM_MODEL_NAME
        self.timeout = timeout
        self.client = None
        self.async_client = None
        self._init_clients()
    
    def _init_clients(self):
        try:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
            self.async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
        except Exception as e:
            logger.warning(f"Failed to initialize LLM client: {e}")
            self.client = None
            self.async_client = None
    
    @property
    def is_available(self) -> bool:
        return self.client is not None and self.api_key
    
    def generate(self, prompt: str, temperature: float = 0.0) -> Optional[str]:
        if not self.is_available:
            logger.warning("LLM client not available")
            return None
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                timeout=self.timeout
            )
            return response.choices[0].message.content.strip()
        except APITimeoutError:
            logger.error("LLM API timeout")
            return None
        except (APIError, APIConnectionError) as e:
            logger.error(f"LLM API error: {e}")
            return None
    
    async def async_generate(self, prompt: str, temperature: float = 0.0) -> Optional[str]:
        if not self.is_available:
            logger.warning("LLM client not available")
            return None
        
        try:
            response = await self.async_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                timeout=self.timeout
            )
            content = response.choices[0].message.content.strip()
            logger.debug(f"LLM raw response: {content[:300]}")  # 添加调试日志
            return content
        except APITimeoutError:
            logger.error("LLM API timeout")
            return None
        except (APIError, APIConnectionError) as e:
            logger.error(f"LLM API error: {e}")
            return None
    
    def generate_json(self, prompt: str, temperature: float = 0.0) -> Optional[Dict[str, Any]]:
        result = self.generate(prompt, temperature)
        if result:
            # 先尝试提取 Markdown 代码块中的 JSON
            extracted = self._extract_json_from_text(result)
            target = extracted if extracted else result
            try:
                #return json.loads(result)
                return json.loads(target)
            except json.JSONDecodeError:
                # 如果失败，尝试提取 JSON 内容
                logger.debug(f"Direct JSON parse failed, trying to extract JSON from: {result[:200]}")
                extracted = self._extract_json_from_text(result)
                if extracted:
                    try:
                        return json.loads(extracted)
                    except json.JSONDecodeError:
                        logger.debug(f"Extracted JSON still invalid: {extracted[:200]}")
               #logger.debug("LLM response not valid JSON, falling back to text processing")
                logger.debug(f"JSON parse failed for: {target[:200]}")
        return None
    
    async def async_generate_json(self, prompt: str, temperature: float = 0.0) -> Optional[Dict[str, Any]]:
        result = await self.async_generate(prompt, temperature)
        if result:
            # 先尝试提取 Markdown 代码块中的 JSON
            extracted = self._extract_json_from_text(result)
            target = extracted if extracted else result
            try:
                #return json.loads(result)
                return json.loads(target)
            except json.JSONDecodeError:
                # 如果失败，尝试提取 JSON 内容
                logger.debug(f"Direct JSON parse failed, trying to extract JSON from: {result[:200]}")
                extracted = self._extract_json_from_text(result)
                if extracted:
                    try:
                        return json.loads(extracted)
                    except json.JSONDecodeError:
                        logger.debug(f"Extracted JSON still invalid: {extracted[:200]}")
                #logger.debug("LLM response not valid JSON, falling back to text processing")
                logger.debug(f"JSON parse failed for: {target[:200]}")
        return None

    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """
        从 LLM 响应中提取 JSON 内容
        处理常见情况：
        1. Markdown 代码块:json [...]
        2. 前后有额外文本
                3. 只有数组或对象
        """
        import re

        # 尝试提取 markdown 代码块中的 JSON
        #markdown_pattern = r'(?:json)?\s*([\s\S]*?)\s*'
        markdown_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(markdown_pattern, text, re.DOTALL)
        if match:
            return match.group(1)

        # 尝试找到第一个 [ 或 { 开始的内容
        array_match = re.search(r'\[.*\]', text, re.DOTALL)
        if array_match:
            return array_match.group(0)

        object_match = re.search(r'\{.*\}', text, re.DOTALL)
        if object_match:
            return object_match.group(0)

        # 如果都失败，返回原文
        return None