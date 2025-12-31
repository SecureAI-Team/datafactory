"""Statistics and dashboard API endpoints"""
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..db import get_db
from ..models.user import User
from ..models.legacy import KnowledgeUnit, SourceDocument, PipelineRun, DQRun
from ..models.contribution import Contribution, ContributionStats
from ..models.conversation import ConversationV2, ConversationMessage
from .auth import get_current_user, require_role

router = APIRouter(prefix="/api/stats", tags=["stats"])


# ==================== Dashboard Overview ====================

@router.get("/overview")
async def get_overview(
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取仪表盘概览数据"""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    
    # Today's processed documents
    try:
        today_processed = db.query(func.count(SourceDocument.id)).filter(
            SourceDocument.created_at >= today
        ).scalar() or 0
    except Exception:
        today_processed = 0
    
    # Total KUs
    try:
        total_kus = db.query(func.count(KnowledgeUnit.id)).scalar() or 0
    except Exception:
        total_kus = 0
    
    # Published KUs
    try:
        published_kus = db.query(func.count(KnowledgeUnit.id)).filter(
            KnowledgeUnit.status == "published"
        ).scalar() or 0
    except Exception:
        published_kus = 0
    
    # Pending reviews
    try:
        pending_reviews = db.query(func.count(Contribution.id)).filter(
            Contribution.status == "pending"
        ).scalar() or 0
    except Exception:
        pending_reviews = 0
    
    # Failed pipeline runs (last 24h)
    try:
        failed_runs = db.query(func.count(PipelineRun.id)).filter(
            PipelineRun.status == "failed",
            PipelineRun.started_at >= yesterday
        ).scalar() or 0
    except Exception:
        failed_runs = 0
    
    # Active users today
    try:
        active_users = db.query(func.count(func.distinct(ConversationMessage.conversation_id))).filter(
            ConversationMessage.created_at >= today
        ).scalar() or 0
    except Exception:
        active_users = 0
    
    return {
        "today_processed": today_processed,
        "total_kus": total_kus,
        "published_kus": published_kus,
        "pending_reviews": pending_reviews,
        "failed_runs": failed_runs,
        "active_users": active_users
    }


# ==================== Pipeline Stats ====================

@router.get("/pipeline")
async def get_pipeline_stats(
    days: int = 7,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取 Pipeline 统计数据"""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get pipeline runs
    runs = db.query(
        func.date(PipelineRun.started_at).label('date'),
        PipelineRun.status,
        func.count(PipelineRun.id).label('count')
    ).filter(
        PipelineRun.started_at >= start_date
    ).group_by(
        func.date(PipelineRun.started_at),
        PipelineRun.status
    ).all()
    
    # Organize by date
    daily_stats = {}
    for run in runs:
        date_str = str(run.date)
        if date_str not in daily_stats:
            daily_stats[date_str] = {"success": 0, "failed": 0, "running": 0}
        daily_stats[date_str][run.status] = run.count
    
    # Get recent pipeline runs
    recent_runs = db.query(PipelineRun).order_by(
        desc(PipelineRun.started_at)
    ).limit(10).all()
    
    recent = []
    for run in recent_runs:
        duration = None
        if run.ended_at and run.started_at:
            duration = (run.ended_at - run.started_at).total_seconds()
        
        recent.append({
            "id": run.id,
            "pipeline_name": run.pipeline_name,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "duration_seconds": duration,
            "input_count": run.input_count,
            "output_count": run.output_count
        })
    
    return {
        "daily_stats": daily_stats,
        "recent_runs": recent
    }


# ==================== Quality Stats ====================

@router.get("/quality")
async def get_quality_stats(
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取质量指标"""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    # DQ pass rate (last 30 days)
    total_dq = 0
    passed_dq = 0
    pass_rate = 0
    
    try:
        dq_runs = db.query(
            DQRun.passed,
            func.count(DQRun.id)
        ).filter(
            DQRun.run_at >= thirty_days_ago
        ).group_by(DQRun.passed).all()
        
        total_dq = sum(count for _, count in dq_runs)
        passed_dq = next((count for passed, count in dq_runs if passed), 0)
        pass_rate = (passed_dq / total_dq * 100) if total_dq > 0 else 0
    except Exception:
        # Table may not exist
        pass
    
    # KU distribution by type
    type_distribution = {}
    try:
        ku_types = db.query(
            KnowledgeUnit.ku_type,
            func.count(KnowledgeUnit.id)
        ).group_by(KnowledgeUnit.ku_type).all()
        type_distribution = {t: c for t, c in ku_types if t}
    except Exception:
        pass
    
    # KU distribution by status
    status_distribution = {}
    try:
        ku_status = db.query(
            KnowledgeUnit.status,
            func.count(KnowledgeUnit.id)
        ).group_by(KnowledgeUnit.status).all()
        status_distribution = {s: c for s, c in ku_status if s}
    except Exception:
        pass
    
    return {
        "dq_pass_rate": round(pass_rate, 2),
        "total_dq_runs": total_dq,
        "ku_type_distribution": type_distribution,
        "ku_status_distribution": status_distribution
    }


# ==================== Contribution Stats ====================

@router.get("/contributions")
async def get_contribution_stats(
    days: int = 30,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取贡献统计"""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Contributions by status
    status_counts = db.query(
        Contribution.status,
        func.count(Contribution.id)
    ).group_by(Contribution.status).all()
    
    by_status = {s: c for s, c in status_counts}
    
    # Contributions by type
    type_counts = db.query(
        Contribution.contribution_type,
        func.count(Contribution.id)
    ).group_by(Contribution.contribution_type).all()
    
    by_type = {t: c for t, c in type_counts}
    
    # Daily trend
    daily_contributions = db.query(
        func.date(Contribution.created_at).label('date'),
        func.count(Contribution.id).label('count')
    ).filter(
        Contribution.created_at >= start_date
    ).group_by(
        func.date(Contribution.created_at)
    ).order_by('date').all()
    
    daily_trend = [{"date": str(d), "count": c} for d, c in daily_contributions]
    
    # Top contributors
    top_contributors = db.query(
        ContributionStats.user_id,
        ContributionStats.total_contributions,
        ContributionStats.approved_count,
        User.username,
        User.display_name
    ).join(
        User, ContributionStats.user_id == User.id
    ).order_by(
        desc(ContributionStats.approved_count)
    ).limit(10).all()
    
    contributors = [
        {
            "user_id": uid,
            "username": uname,
            "display_name": dname,
            "total": total,
            "approved": approved
        }
        for uid, total, approved, uname, dname in top_contributors
    ]
    
    return {
        "by_status": by_status,
        "by_type": by_type,
        "daily_trend": daily_trend,
        "top_contributors": contributors
    }


# ==================== Recent Activity ====================

@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = 20,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取最近活动"""
    activities = []
    
    # Recent pipeline runs
    try:
        recent_pipelines = db.query(PipelineRun).order_by(
            desc(PipelineRun.started_at)
        ).limit(5).all()
        
        for run in recent_pipelines:
            duration = None
            if run.ended_at and run.started_at:
                duration = f"{(run.ended_at - run.started_at).total_seconds():.1f}s"
            
            activities.append({
                "type": "pipeline",
                "status": run.status,
                "message": f"Pipeline {run.pipeline_name} {run.status}" + (f" (耗时 {duration})" if duration else ""),
                "time": run.started_at.isoformat() if run.started_at else None
            })
    except Exception:
        pass
    
    # Recent contributions
    try:
        recent_contributions = db.query(
            Contribution, User.display_name, User.username
        ).join(
            User, Contribution.contributor_id == User.id
        ).order_by(
            desc(Contribution.created_at)
        ).limit(5).all()
        
        for contrib, display_name, username in recent_contributions:
            name = display_name or username
            activities.append({
                "type": "contribution",
                "status": contrib.status,
                "message": f"用户 {name} 提交了新贡献: {contrib.title}",
                "time": contrib.created_at.isoformat() if contrib.created_at else None
            })
    except Exception:
        pass
    
    # Recent DQ failures
    try:
        recent_dq = db.query(DQRun).filter(
            DQRun.passed == False
        ).order_by(
            desc(DQRun.run_at)
        ).limit(3).all()
        
        for dq in recent_dq:
            failure_msg = ""
            if dq.failure_reasons and len(dq.failure_reasons) > 0:
                failure_msg = dq.failure_reasons[0]
            activities.append({
                "type": "dq",
                "status": "failed",
                "message": f"DQ 检查失败: KU-{dq.ku_id} {failure_msg}",
                "time": dq.run_at.isoformat() if dq.run_at else None
            })
    except Exception:
        pass
    
    # Sort by time
    activities.sort(key=lambda x: x["time"] or "", reverse=True)
    
    return {"activities": activities[:limit]}


# ==================== Usage Stats ====================

@router.get("/usage")
async def get_usage_stats(
    days: int = 7,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取使用情况统计"""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Daily conversations
    daily_conversations = db.query(
        func.date(ConversationV2.started_at).label('date'),
        func.count(ConversationV2.id).label('count')
    ).filter(
        ConversationV2.started_at >= start_date
    ).group_by(
        func.date(ConversationV2.started_at)
    ).order_by('date').all()
    
    # Daily messages
    daily_messages = db.query(
        func.date(ConversationMessage.created_at).label('date'),
        func.count(ConversationMessage.id).label('count')
    ).filter(
        ConversationMessage.created_at >= start_date
    ).group_by(
        func.date(ConversationMessage.created_at)
    ).order_by('date').all()
    
    # Active users per day
    daily_users = db.query(
        func.date(ConversationV2.started_at).label('date'),
        func.count(func.distinct(ConversationV2.user_id)).label('count')
    ).filter(
        ConversationV2.started_at >= start_date
    ).group_by(
        func.date(ConversationV2.started_at)
    ).order_by('date').all()
    
    return {
        "daily_conversations": [{"date": str(d), "count": c} for d, c in daily_conversations],
        "daily_messages": [{"date": str(d), "count": c} for d, c in daily_messages],
        "daily_active_users": [{"date": str(d), "count": c} for d, c in daily_users]
    }


# ==================== Feedback Stats ====================

@router.get("/feedback")
async def get_feedback_stats(
    days: int = 30,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取反馈统计"""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get feedback counts
    positive_count = db.query(func.count(ConversationMessage.id)).filter(
        ConversationMessage.feedback == 'positive',
        ConversationMessage.created_at >= start_date
    ).scalar() or 0
    
    negative_count = db.query(func.count(ConversationMessage.id)).filter(
        ConversationMessage.feedback == 'negative',
        ConversationMessage.created_at >= start_date
    ).scalar() or 0
    
    total_feedback = positive_count + negative_count
    
    # Get negative feedback details
    negative_messages = db.query(ConversationMessage).filter(
        ConversationMessage.feedback == 'negative',
        ConversationMessage.created_at >= start_date
    ).order_by(ConversationMessage.created_at.desc()).limit(50).all()
    
    negative_feedback_list = []
    for msg in negative_messages:
        # Get the previous user message as the query
        prev_msg = db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == msg.conversation_id,
            ConversationMessage.role == 'user',
            ConversationMessage.created_at < msg.created_at
        ).order_by(ConversationMessage.created_at.desc()).first()
        
        negative_feedback_list.append({
            "id": str(msg.id),
            "query": prev_msg.content[:100] if prev_msg else "未知问题",
            "feedback": "negative",
            "reason": msg.feedback_text or "用户未说明原因",
            "date": msg.created_at.strftime("%Y-%m-%d") if msg.created_at else "",
            "conversation_id": msg.conversation_id,
        })
    
    return {
        "positive_rate": round((positive_count / total_feedback * 100) if total_feedback > 0 else 0, 1),
        "negative_rate": round((negative_count / total_feedback * 100) if total_feedback > 0 else 0, 1),
        "pending_count": len(negative_feedback_list),  # Count of negative feedback to process
        "total_feedback": total_feedback,
        "negative_feedback": negative_feedback_list
    }


# ==================== DQ Runs ====================

@router.get("/dq-runs")
async def get_dq_runs(
    limit: int = 20,
    passed: Optional[bool] = None,
    admin: User = Depends(require_role("admin", "data_ops")),
    db: Session = Depends(get_db)
):
    """获取 DQ 检查记录"""
    query = db.query(DQRun)
    
    if passed is not None:
        query = query.filter(DQRun.passed == passed)
    
    dq_runs = query.order_by(desc(DQRun.run_at)).limit(limit).all()
    
    runs_list = []
    for run in dq_runs:
        # Get KU info
        ku = db.query(KnowledgeUnit).filter(KnowledgeUnit.id == run.ku_id).first()
        
        # Parse reasons from JSON
        reasons = []
        checks = []
        if run.check_results:
            try:
                results = run.check_results if isinstance(run.check_results, dict) else json.loads(run.check_results)
                for check_name, check_result in results.items():
                    check_passed = check_result.get('passed', True) if isinstance(check_result, dict) else bool(check_result)
                    check_msg = check_result.get('message', '') if isinstance(check_result, dict) else ''
                    checks.append({
                        "name": check_name,
                        "passed": check_passed,
                        "message": check_msg
                    })
                    if not check_passed:
                        reasons.append(check_msg or check_name)
            except (json.JSONDecodeError, AttributeError):
                pass
        
        runs_list.append({
            "id": run.id,
            "ku_id": f"KU-{run.ku_id}",
            "passed": run.passed,
            "reasons": reasons,
            "date": run.run_at.strftime("%Y-%m-%d %H:%M") if run.run_at else "",
            "details": {
                "title": ku.title if ku else "未知",
                "ku_type": ku.ku_type if ku else "",
                "checks": checks
            } if not run.passed else None
        })
    
    return {
        "runs": runs_list
    }


# ==================== Airflow DAG Trigger ====================

@router.post("/trigger-pipeline")
async def trigger_pipeline(
    dag_id: str = "ingest_to_bronze",
    admin: User = Depends(require_role("admin", "data_ops")),
):
    """
    手动触发 Airflow DAG 处理新材料
    
    Available DAGs:
    - ingest_to_bronze: 导入新文件到 Bronze 层
    - extract_to_silver: 提取文本到 Silver 层
    - expand_and_rewrite_to_gold: LLM 扩展到 Gold 层
    - index_to_opensearch: 索引到 OpenSearch
    - dq_validate_and_publish: 质量检查并发布
    """
    import httpx
    import base64
    from ..config import settings
    
    # Validate DAG ID
    valid_dags = [
        "ingest_to_bronze",
        "extract_to_silver",
        "expand_and_rewrite_to_gold",
        "index_to_opensearch",
        "dq_validate_and_publish",
        "extract_params",
        "merge_duplicates"
    ]
    
    if dag_id not in valid_dags:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid DAG ID. Valid options: {', '.join(valid_dags)}"
        )
    
    # Build Airflow REST API URL
    airflow_api_url = f"{settings.airflow_url}/api/v1/dags/{dag_id}/dagRuns"
    
    # Create Basic Auth header
    credentials = f"{settings.airflow_user}:{settings.airflow_password}"
    auth_header = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/json"
    }
    
    # Trigger DAG run
    payload = {
        "conf": {
            "triggered_by": admin.username,
            "triggered_at": datetime.now(timezone.utc).isoformat()
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                airflow_api_url,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200 or response.status_code == 201:
                result = response.json()
                return {
                    "success": True,
                    "message": f"DAG '{dag_id}' 已触发",
                    "dag_run_id": result.get("dag_run_id"),
                    "execution_date": result.get("execution_date"),
                    "state": result.get("state")
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "message": "Airflow 认证失败，请检查配置"
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "message": f"DAG '{dag_id}' 不存在"
                }
            else:
                return {
                    "success": False,
                    "message": f"触发失败: {response.text}"
                }
    except httpx.ConnectError:
        return {
            "success": False,
            "message": "无法连接到 Airflow 服务器"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"触发失败: {str(e)}"
        }


@router.get("/pipeline-dags")
async def get_available_dags(
    admin: User = Depends(require_role("admin", "data_ops")),
):
    """获取可用的 Airflow DAG 列表"""
    return {
        "dags": [
            {"id": "ingest_to_bronze", "name": "导入新材料", "description": "将新上传的文件导入到 Bronze 层"},
            {"id": "extract_to_silver", "name": "文本提取", "description": "从文档中提取文本内容"},
            {"id": "expand_and_rewrite_to_gold", "name": "LLM 扩展", "description": "使用 LLM 扩展和改写内容"},
            {"id": "index_to_opensearch", "name": "索引更新", "description": "更新 OpenSearch 搜索索引"},
            {"id": "dq_validate_and_publish", "name": "质量检查", "description": "执行质量检查并发布通过的内容"},
            {"id": "extract_params", "name": "参数提取", "description": "提取产品参数信息"},
            {"id": "merge_duplicates", "name": "去重合并", "description": "合并重复内容"},
        ]
    }

