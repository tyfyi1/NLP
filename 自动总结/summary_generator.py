import requests
import json
import os
from typing import Optional


class SummaryGenerator:
    def __init__(self, api_key: str = None, api_base: str = None, model: str = None):
        """
        初始化摘要生成器
        
        Args:
            api_key: API密钥，如果未提供则从环境变量获取
            api_base: API基础URL，如果未提供则使用默认值
            model: 使用的模型名称，默认使用 GLM-4-9B-0414（长文本摘要效果更好）
        """
        self.api_key = api_key or os.getenv("SILICONFLOW_API_KEY")
        self.api_base = api_base or "https://api.siliconflow.cn/v1"
        # 默认使用 GLM-4-9B-0414（智谱AI），长文本摘要和数字保真度更好
        # 备选：Qwen/Qwen2.5-7B-Instruct
        self.model = model or "THUDM/GLM-4-9B-0414"
        
        if not self.api_key:
            raise ValueError("API密钥未提供，请设置环境变量SILICONFLOW_API_KEY或传入api_key参数")
    
    def generate_summary(self, text: str, max_tokens: int = 500, temperature: float = 0.3) -> Optional[str]:
        """
        生成文本摘要（支持中英文论文）
        
        Args:
            text: 要总结的文本内容（中英文均可）
            max_tokens: 最大输出token数
            temperature: 生成温度，控制输出多样性（默认0.3，更稳定）
        
        Returns:
            生成的摘要文本，如果失败返回None
        """
        url = f"{self.api_base}/chat/completions"
        
        prompt = f"""你是一位专业的学术论文摘要助手。请对以下论文内容进行总结。

【重要要求】
1. 无论输入论文是中文还是英文，输出**必须使用中文**
2. 准确提取关键信息：研究背景、方法、结果、结论
3. **数字、专有名词、模型名称要严格忠实原文，不要编造或修改**
4. 重点突出论文的核心贡献和创新点
5. 语言简洁专业，逻辑清晰
6. 字数控制在300-500字

【论文内容】
{text}

【中文摘要】
"""
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                summary = result["choices"][0]["message"]["content"].strip()
                return summary
            else:
                print("API返回格式错误")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"API调用失败: {e}")
            return None
        except Exception as e:
            print(f"未知错误: {e}")
            return None
    
    def generate_detailed_summary(self, text: str) -> Optional[str]:
        """
        生成详细摘要（支持中英文论文）
        
        Args:
            text: 要总结的文本内容（中英文均可）
        
        Returns:
            生成的详细摘要文本，如果失败返回None
        """
        url = f"{self.api_base}/chat/completions"
        
        prompt = f"""你是一位专业的学术论文摘要助手。请对以下论文进行结构化详细总结。

【重要要求】
1. 无论输入论文是中文还是英文，输出**必须使用中文**
2. **数字、年份、模型名称、专有名词要严格忠实原文，不得修改**
3. 准确提炼每个部分的核心内容
4. 输出严格按照下面的格式

【论文内容】
{text}

---

【输出格式】（请严格按此格式输出）

【研究背景】
（用2-3句话说明论文要解决的问题）

【研究方法】
（详细说明论文提出的方法或模型）

【实验结果】
（列出关键实验数据，使用原文中准确的数字）

【主要结论】
（总结论文的核心贡献）

【关键词】
（5-8个关键词，用逗号分隔）
"""
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.3,
            "stream": False
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                summary = result["choices"][0]["message"]["content"].strip()
                return summary
            else:
                print("API返回格式错误")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"API调用失败: {e}")
            return None
        except Exception as e:
            print(f"未知错误: {e}")
            return None


def main():
    """示例用法"""
    # 设置API密钥（从环境变量获取或直接设置）
    os.environ["SILICONFLOW_API_KEY"] = "sk-ogopmfbtujtsmopibvfmaigawixcmyvuwyoaoasnsyrsdpft"
    
    # 创建摘要生成器（默认使用 GLM-4-9B-0414，长文本摘要和数字保真度更好）
    generator = SummaryGenerator()
    print(f"当前使用模型: {generator.model}")
    print()
    
    # 示例论文内容
    sample_paper = """
Transformer是一种基于自注意力机制的深度学习模型，由Vaswani等人在2017年提出。
该模型摒弃了传统的循环神经网络结构，采用多头注意力机制来捕捉输入序列中不同位置之间的依赖关系。

Transformer主要由编码器和解码器两部分组成。编码器包含多层多头注意力和前馈神经网络，用于处理输入序列并生成上下文表示。
解码器同样包含多层结构，但在多头注意力层之外还增加了编码器-解码器注意力层，用于关注输入序列的相关部分。

实验结果表明，Transformer在机器翻译任务上取得了显著优于传统模型的性能。
在WMT 2014英德翻译任务中，Transformer达到了28.4 BLEU分数，超过了当时最好的模型。

此外，Transformer的并行计算能力使其训练效率远高于循环神经网络，为后续大规模预训练模型的发展奠定了基础。
    """
    
    # 生成简洁摘要
    print("=== 简洁摘要 ===")
    summary = generator.generate_summary(sample_paper)
    if summary:
        print(summary)
        print()
    
    # 生成详细摘要
    print("=== 详细摘要 ===")
    detailed_summary = generator.generate_detailed_summary(sample_paper)
    if detailed_summary:
        print(detailed_summary)


if __name__ == "__main__":
    main()