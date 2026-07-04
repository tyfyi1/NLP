"""
运行综述生成流程（不含校验，快速测试）
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.summarizer import drag_paper_summarizer
from core.reviewer import drag_review_generator


async def run_simple_pipeline():
    print('='*60)
    print('DRAG增强综述生成（快速模式）')
    print('='*60)

    # 阶段1：生成摘要（使用缓存）
    print('[阶段1/2] 检查论文摘要...')
    results = await drag_paper_summarizer.summarize_batch()
    print(f'摘要处理完成，共 {len(results)} 篇论文')

    # 阶段2：生成综述
    print('[阶段2/2] 正在生成综述...')
    print('(由于缓存存在，会跳过已处理的论文)')
    review_result = await drag_review_generator.generate(
        topic='大语言模型在生物医学领域的应用'
    )

    review_text = review_result.get('review', '')
    print(f'综述生成完成，共 {len(review_text)} 字符')

    # 保存原始综述（不含校验日志）
    output_path = os.path.join(os.path.dirname(__file__), 'output', 'review_dragsys.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(review_text)
    print(f'综述已保存到: {output_path}')

    return review_result


if __name__ == '__main__':
    result = asyncio.run(run_simple_pipeline())
    print('='*60)
    print('综述生成完成！')
    print('提示：如需校验引用，请调用 verify_citations 方法')
    print('='*60)
