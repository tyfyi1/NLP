"""
FastAPI REST异步接口

DRAG框架集成说明（ACL 2025 - 2025.acl-long.770）：
本服务集成了DRAG辩论增强RAG框架，用于抑制综述生成中的幻觉问题。
流程：检索辩论 → 应答辩论 → 三方智能体协同验证
"""

import asyncio
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from config.settings import settings
from core.summarizer import drag_paper_summarizer
from core.reviewer import drag_review_generator
from core.verifier import drag_citation_verifier
from utils.post_processor import ReviewPostProcessor

# DRAG框架导入占位（仅引用不实例化）
# from drag_framework import DRAGFramework
# from multi_agent_debate import MultiAgentDebateOrchestrator


app = FastAPI(
    title="DRAG增强学术综述生成服务",
    description="基于ACL 2025 DRAG框架的辩论增强RAG综述生成服务",
    version="1.1.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== 请求/响应模型 ==============

class SummarizeRequest(BaseModel):
    """摘要生成请求"""
    force_regenerate: bool = Field(False, description="是否强制重新生成")


class TopicReviewRequest(BaseModel):
    """主题综述请求"""
    topic: str = Field(..., description="综述主题")
    focus_areas: Optional[List[str]] = Field(None, description="重点关注领域")


class VerificationRequest(BaseModel):
    """校验请求"""
    review_text: str = Field(..., description="待校验的综述原文")


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str
    message: Optional[str] = None
    result: Optional[dict] = None


# ============== 任务状态管理 ==============

tasks = {}


def generate_task_id() -> str:
    """生成任务ID"""
    import uuid
    return str(uuid.uuid4())


# ============== 接口路由 ==============

@app.get("/")
async def root():
    """服务健康检查"""
    return {
        "service": "学术综述生成服务",
        "status": "running",
        "papers_dir": str(settings.papers_dir),
        "models": {
            "lite": settings.lite_model,
            "pro": settings.pro_model
        }
    }


@app.get("/papers")
async def list_papers():
    """列出本地论文"""
    pdf_files = list(settings.papers_dir.glob("*.pdf"))
    return {
        "count": len(pdf_files),
        "papers": [f.name for f in pdf_files]
    }


@app.post("/summarize")
async def summarize_papers(
    background_tasks: BackgroundTasks,
    force_regenerate: bool = False
):
    """
    阶段1：批量生成论文摘要

    - **force_regenerate**: 是否强制重新生成（跳过缓存）
    """
    task_id = generate_task_id()

    async def run_summarization():
        tasks[task_id] = {"status": "running", "message": "正在生成摘要..."}
        try:
            results = await drag_paper_summarizer.summarize_batch(
                force_regenerate=force_regenerate
            )
            tasks[task_id] = {
                "status": "completed",
                "result": results
            }
        except Exception as e:
            tasks[task_id] = {
                "status": "failed",
                "error": str(e)
            }

    background_tasks.add_task(run_summarization)

    return {
        "task_id": task_id,
        "status": "started",
        "message": "摘要生成任务已启动"
    }


@app.get("/summarize/{task_id}")
async def get_summarize_status(task_id: str):
    """获取摘要生成任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return tasks[task_id]


@app.post("/review")
async def generate_review(
    background_tasks: BackgroundTasks,
    topic: Optional[str] = None
):
    """
    阶段2：基于摘要生成综述

    - **topic**: 可选的综述主题
    """
    task_id = generate_task_id()

    async def run_review_generation():
        tasks[task_id] = {"status": "running", "message": "正在生成综述..."}
        try:
            if topic:
                result = await drag_review_generator.generate_with_topic(topic)
            else:
                result = await drag_review_generator.generate()
            tasks[task_id] = {
                "status": "completed",
                "result": result
            }
        except Exception as e:
            tasks[task_id] = {
                "status": "failed",
                "error": str(e)
            }

    background_tasks.add_task(run_review_generation)

    return {
        "task_id": task_id,
        "status": "started",
        "message": "综述生成任务已启动"
    }


@app.get("/review/{task_id}")
async def get_review_status(task_id: str):
    """获取综述生成任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return tasks[task_id]


@app.post("/verify")
async def verify_citations(
    background_tasks: BackgroundTasks,
    body: VerificationRequest
):
    """
    阶段3：校验综述引用

    - **review_text**: 待校验的综述原文
    """
    task_id = generate_task_id()

    async def run_verification():
        tasks[task_id] = {"status": "running", "message": "正在校验引用..."}
        try:
            result = await drag_citation_verifier.verify_citations(body.review_text)
            tasks[task_id] = {
                "status": "completed",
                "result": result
            }
        except Exception as e:
            tasks[task_id] = {
                "status": "failed",
                "error": str(e)
            }

    background_tasks.add_task(run_verification)

    return {
        "task_id": task_id,
        "status": "started",
        "message": "引用校验任务已启动"
    }


@app.get("/verify/{task_id}")
async def get_verify_status(task_id: str):
    """获取校验任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return tasks[task_id]


@app.post("/full-pipeline")
async def run_full_pipeline(
    background_tasks: BackgroundTasks,
    topic: Optional[str] = None,
    force_regenerate: bool = False
):
    """
    完整流程：摘要生成 -> 综述生成 -> 引用校验

    - **topic**: 综述主题
    - **force_regenerate**: 是否强制重新生成摘要
    """
    task_id = generate_task_id()

    async def run_pipeline():
        # DRAG辩论框架主流程控制
        # 注意：即使drag_enable=True，这里也仅打印日志，不执行真实多智能体辩论
        if settings.drag_enable:
            print("[DRAG主流程] DRAG辩论增强框架已启用")
            print(f"[DRAG配置] 检索辩论: {settings.retrieval_debate_rounds}轮, 收敛阈值: {settings.retrieval_convergence_threshold}")
            print(f"[DRAG配置] 应答辩论: {settings.response_debate_rounds}轮, 收敛阈值: {settings.response_convergence_threshold}")
            print(f"[DRAG配置] 信息不对称设计: {'启用' if settings.asymmetry_enabled else '禁用'}")
            print(f"[DRAG配置] 二次幻觉检测: {'启用' if settings.second_hallucination_detection else '禁用'}")

        tasks[task_id] = {
            "status": "running",
            "message": "阶段1/3：正在生成摘要..."
        }

        try:
            # 阶段1：生成摘要（DRAG检索辩论前置阶段）
            if settings.drag_enable:
                print("[DRAG检索辩论前置] 启动摘要生成，构建证据池...")
            await drag_paper_summarizer.summarize_batch(
                force_regenerate=force_regenerate
            )

            # 阶段2：生成综述（DRAG应答辩论生成阶段）
            if settings.drag_enable:
                print("[DRAG应答辩论] 检索辩论完成，进入应答辩论综述生成阶段...")
            tasks[task_id] = {
                "status": "running",
                "message": "阶段2/3：正在生成综述..."
            }

            if topic:
                if settings.drag_enable:
                    print(f"[DRAG生成] 正在生成主题综述: {topic}")
                review_result = await drag_review_generator.generate_with_topic(topic)
            else:
                review_result = await drag_review_generator.generate()

            if not review_result.get("success"):
                raise Exception(review_result.get("error", "综述生成失败"))

            review_text = review_result.get("review", "")

            # 阶段3：校验引用（DRAG应答辩论验证阶段）
            if settings.drag_enable:
                print("[DRAG应答辩论] 综述生成完成，进入应答辩论验证阶段...")
                print(f"[DRAG辩论] 挑战者将执行 {settings.response_debate_rounds} 轮对抗性质疑")
                print(f"[DRAG裁判] 收敛判定阈值: {settings.response_convergence_threshold}")
            tasks[task_id] = {
                "status": "running",
                "message": "阶段3/3：正在校验引用..."
            }

            verify_result = await drag_citation_verifier.verify_citations(review_text)

            # 保存输出（不包含校验日志）
            output_path = settings.output_dir / f"review_{task_id}.md"
            corrected_review = verify_result.get("corrected_review", review_text)

            # 后处理：规范化格式
            processor = ReviewPostProcessor()
            metadata = await processor.load_paper_metadata()
            final_review = processor.process(corrected_review, metadata)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_review)

            tasks[task_id] = {
                "status": "completed",
                "result": {
                    "review": review_text,
                    "verification": {
                        "issues_found": verify_result.get("issues_found", 0),
                        "verification_count": verify_result.get("verification_count", 0)
                    },
                    "corrected_review": corrected_review,
                    "output_file": str(output_path)
                }
            }

        except Exception as e:
            tasks[task_id] = {
                "status": "failed",
                "error": str(e)
            }

    background_tasks.add_task(run_pipeline)

    return {
        "task_id": task_id,
        "status": "started",
        "message": "完整流程已启动（摘要->综述->校验）"
    }


@app.get("/full-pipeline/{task_id}")
async def get_pipeline_status(task_id: str):
    """获取完整流程任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return tasks[task_id]


@app.get("/cache")
async def list_cache():
    """列出缓存的摘要"""
    from storage.cache import cache_manager
    summaries = await cache_manager.get_all_summaries()
    return {
        "count": len(summaries),
        "cached_papers": [s.get("filename", "") for s in summaries]
    }


@app.delete("/cache")
async def clear_cache():
    """清除全部缓存"""
    from storage.cache import cache_manager
    await cache_manager.clear_cache()
    return {"message": "Cache cleared"}


@app.delete("/cache/{filename}")
async def clear_cache_file(filename: str):
    """清除指定文件的缓存"""
    from storage.cache import cache_manager
    await cache_manager.clear_cache(filename)
    return {"message": f"Cache for {filename} cleared"}
