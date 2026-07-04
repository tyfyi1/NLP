"""
运行完整综述生成流程
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.summarizer import drag_paper_summarizer
from core.reviewer import drag_review_generator
from core.verifier import drag_citation_verifier


async def run_pipeline():
    print('='*60)
    print('DRAG增强学术综述生成流程')
    print('='*60)

    # 阶段1：生成摘要
    print('[阶段1/3] 正在生成论文摘要...')
    results = await drag_paper_summarizer.summarize_batch()
    print(f'摘要生成完成，共处理 {len(results)} 篇论文')

    # 阶段2：生成综述
    print('[阶段2/3] 正在生成综述...')
    review_result = await drag_review_generator.generate(
        topic='大语言模型在生物医学领域的应用'
    )
    review_text = review_result.get('review', '')
    print(f'综述生成完成，共 {len(review_text)} 字符')

    # 阶段3：校验引用
    print('[阶段3/3] 正在校验引用...')
    verify_result = await drag_citation_verifier.verify_citations(review_text)
    print(f'校验完成，发现 {verify_result.get("issues_found", 0)} 处问题')

    # 保存结果
    output_path = os.path.join(os.path.dirname(__file__), 'output', 'review_dragsys.md')
    corrected_review = verify_result.get('corrected_review', review_text)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(corrected_review)
    print(f'综述已保存到: {output_path}')

    return review_result, verify_result


if __name__ == '__main__':
    result = asyncio.run(run_pipeline())
    print('流程完成!')
