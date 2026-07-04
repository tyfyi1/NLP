from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import os
import sys
import logging

# 添加paper_retriever路径
sys.path.append(r"D:\pycode\自然语言处理\software\自动检索")

# 直接导入优化后的PaperRetriever类
from paper_retriever.main import PaperRetriever
from paper_retriever.utils.llm_client import LLMClient

logging.basicConfig(level=logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('paper_retriever').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # 启用CORS支持

# 全局检索器实例
retriever = None

def init_retriever():
    """初始化论文检索器"""
    global retriever
    try:
        print("正在初始化LLM客户端...")
        llm_client = LLMClient()
        print("LLM客户端初始化成功")
        
        print("正在创建论文检索器...")
        retriever = PaperRetriever(llm_client, top_k=10)
        print("论文检索器初始化成功（支持两阶段检索）")
    except Exception as e:
        print(f"警告：论文检索器初始化失败: {str(e)}")
        import traceback
        traceback.print_exc()
        retriever = None


@app.route('/api/retrieve', methods=['POST'])
def retrieve_papers_api():
    """
    论文检索API接口（支持两阶段检索）
    
    请求体格式：
    {
        "query": "检索查询内容",
        "ranking_mode": "A" 或 "B",
        "top_k": 10,
        "use_two_stage": true  // 是否使用两阶段检索（默认true）
    }
    
    返回格式：
    {
        "success": true,
        "papers": [
            {
                "title": "论文标题",
                "year": "年份",
                "relevance_score": 0.95,
                "matched_concepts": ["概念1", "概念2"],
                "url": "论文链接"
            }
        ],
        "message": "成功",
        "retrieval_mode": "两阶段检索"  // 返回使用的检索模式
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "papers": [],
                "message": "缺少必要参数: query"
            }), 400
        
        query = data['query']
        ranking_mode = data.get('ranking_mode', 'B')
        top_k = data.get('top_k', 10)
        use_two_stage = data.get('use_two_stage', True)  # 默认使用两阶段检索
        
        if not retriever:
            return jsonify({
                "success": False,
                "papers": [],
                "message": "论文检索器未初始化，请检查配置"
            }), 500
        
        # 运行异步检索
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            retrieval_mode_name = "两阶段检索" if use_two_stage else "单阶段检索"
            logger.info(f"开始检索: query='{query}', mode={ranking_mode}, top_k={top_k}, two_stage={use_two_stage}")
            
            # 根据参数选择检索方式
            try:
                if use_two_stage:
                    results = loop.run_until_complete(
                        retriever.retrieve_two_stage(query, ranking_mode=ranking_mode, final_top_k=top_k)
                    )
                else:
                    results = loop.run_until_complete(
                        retriever.retrieve(query, ranking_mode=ranking_mode)
                    )
                logger.info(f"{retrieval_mode_name}完成，找到 {len(results)} 篇论文")
            except Exception as e:
                logger.warning(f"{retrieval_mode_name}失败: {str(e)}, 切换到快速模式")
                if use_two_stage:
                    results = loop.run_until_complete(
                        retriever.retrieve_two_stage(query, ranking_mode='A', final_top_k=top_k)
                    )
                else:
                    results = loop.run_until_complete(retriever.retrieve(query, ranking_mode='A'))
                logger.info(f"快速模式检索完成，找到 {len(results)} 篇论文")
        finally:
            loop.close()
        
        # 格式化结果
        papers = []
        if results:
            for result in results:
                papers.append({
                    "title": result.title,
                    "year": result.year or '未知',
                    "relevance_score": round(result.relevance_score, 4),
                    "matched_concepts": result.matched_concepts[:3] if result.matched_concepts else [],
                    "url": result.url
                })
        
        if len(papers) == 0:
            logger.info(f"未找到相关论文: query='{query}'")
            return jsonify({
                "success": True,
                "papers": [],
                "message": "未找到相关论文，请尝试使用其他关键词或调整检索参数",
                "retrieval_mode": retrieval_mode_name
            })
        
        return jsonify({
            "success": True,
            "papers": papers,
            "message": f"成功检索到 {len(papers)} 篇论文",
            "retrieval_mode": retrieval_mode_name
        })
        
    except Exception as e:
        logger.error(f"检索错误: {str(e)}")
        return jsonify({
            "success": False,
            "papers": [],
            "message": f"服务器错误: {str(e)}"
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "healthy",
        "retriever_initialized": retriever is not None
    })


if __name__ == '__main__':
    init_retriever()
    app.run(host='0.0.0.0', port=5002, debug=True)