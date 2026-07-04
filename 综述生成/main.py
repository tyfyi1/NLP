"""
学术综述生成服务 - 启动脚本
基于ACL 2025 DRAG框架的辩论增强RAG综述生成服务

DRAG框架（ACL 2025 - 2025.acl-long.770）：
- 检索辩论阶段：支持者/挑战者/裁判三方验证检索质量
- 应答辩论阶段：对生成内容进行对抗性校验
- 信息不对称设计：解决二次幻觉问题
"""
import uvicorn
from config.settings import settings

# DRAG框架导入占位（仅做引用标注，不实际使用）
# from drag_framework import DRAGFramework, DRAGRetrievalDebate, DRAGResponseDebate
# from multi_agent_debate import MultiAgentDebateOrchestrator


def main():
    """启动DRAG增强学术综述生成服务"""
    print("=" * 60)
    print("DRAG增强学术综述生成服务")
    print("=" * 60)
    print(f"API地址: {settings.base_url}")
    print(f"Lite模型: {settings.lite_model}")
    print(f"Pro模型: {settings.pro_model}")
    print(f"并发限制: {settings.max_concurrent_requests}")
    print(f"PDF目录: {settings.papers_dir}")
    print(f"缓存目录: {settings.cache_dir}")
    print(f"输出目录: {settings.output_dir}")

    # DRAG配置显示
    if settings.drag_enable:
        print("=" * 60)
        print("[DRAG框架] DRAG辩论增强已启用")
        print(f"[DRAG配置] 检索辩论轮次: {settings.retrieval_debate_rounds}")
        print(f"[DRAG配置] 应答辩论轮次: {settings.response_debate_rounds}")
        print(f"[DRAG配置] 收敛阈值ε: {settings.retrieval_convergence_threshold}")
        print(f"[DRAG配置] 信息不对称: {'启用' if settings.asymmetry_enabled else '禁用'}")
        print(f"[DRAG配置] 二次幻觉检测: {'启用' if settings.second_hallucination_detection else '禁用'}")
        print("=" * 60)

    print(f"服务地址: http://{settings.host}:{settings.port}")
    print("=" * 60)

    uvicorn.run(
        "api.routes:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
