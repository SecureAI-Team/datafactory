"""Statistics and dashboard API endpoints"""
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
    
    # Today's processed documents
    today_processed = db.query(func.count(SourceDocument.id)).filter(
        SourceDocument.created_at >= today
    ).scalar() or 0
    
    # Total KUs
    total_kus = db.query(func.count(KnowledgeUnit.id)).scalar() or 0
    
    # Published KUs
    published_kus = db.query(func.count(KnowledgeUnit.id)).filter(
        KnowledgeUnit.status == "published"
    ).scalar() or 0
    
    # Pending reviews
    pending_reviews = db.query(func.count(Contribution.id)).filter(
        Contribution.status == "pending"
    ).scalar() or 0
    
    # Failed pipeline runs (last 24h)
    yesterday = today - timedelta(days=1)
    failed_runs = db.query(func.count(PipelineRun.id)).filter(
        PipelineRun.status == "failed",
        PipelineRun.started_at >= yesterday
    ).scalar() or 0
    
    # Active users today
    active_users = db.query(func.count(func.distinct(ConversationMessage.conversation_id))).filter(
        ConversationMessage.created_at >= today
    ).scalar() or 0
    
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
    # DQ pass rate (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    dq_runs = db.query(
        DQRun.passed,
        func.count(DQRun.id)
    ).filter(
        DQRun.run_at >= thirty_days_ago
    ).group_by(DQRun.passed).all()
    
    total_dq = sum(count for _, count in dq_runs)
    passed_dq = next((count for passed, count in dq_runs if passed), 0)
    pass_rate = (passed_dq / total_dq * 100) if total_dq > 0 else 0
    
    # KU distribution by type
    ku_types = db.query(
        KnowledgeUnit.ku_type,
        func.count(KnowledgeUnit.id)
    ).group_by(KnowledgeUnit.ku_type).all()
    
    type_distribution = {t: c for t, c in ku_types if t}
    
    # KU distribution by status
    ku_status = db.query(
        KnowledgeUnit.status,
        func.count(KnowledgeUnit.id)
    ).group_by(KnowledgeUnit.status).all()
    
    status_distribution = {s: c for s, c in ku_status if s}
    
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
    
    # Recent contributions
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
    
    # Recent DQ failures
    recent_dq = db.query(DQRun).filter(
        DQRun.passed == False
    ).order_by(
        desc(DQRun.run_at)
    ).limit(3).all()
    
    for dq in recent_dq:
        activities.append({
            "type": "dq",
            "status": "failed",
            "message": f"DQ 检查失败: KU-{dq.ku_id} {dq.failure_reasons[0] if dq.failure_reasons else ''}",
            "time": dq.run_at.isoformat() if dq.run_at else None
        })
    
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

