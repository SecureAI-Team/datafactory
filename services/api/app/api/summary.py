"""
摘要 API
对话摘要生成和管理
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.summary_service import (
    get_summary_service,
    SummaryService,
    SummaryType,
    Summary,
    ConversationTurn,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/summary", tags=["summary"])


# ==================== 请求/响应模型 ====================

class TurnInput(BaseModel):
    """对话轮次输入"""
    role: str
    content: str
    timestamp: Optional[float] = None
    intent_type: Optional[str] = None


class GenerateSummaryRequest(BaseModel):
    """生成摘要请求"""
    conversation_id: Optional[str] = None
    turns: Optional[List[TurnInput]] = None
    summary_type: str = "instant"


class GenerateSummaryResponse(BaseModel):
    """生成摘要响应"""
    success: bool
    summary: dict = {}
    error: str = ""


class CompressHistoryRequest(BaseModel):
    """压缩历史请求"""
    turns: List[TurnInput]
    max_turns: int = 5


# ==================== API 端点 ====================

@router.post("/generate", response_model=GenerateSummaryResponse)
async def generate_summary(request: GenerateSummaryRequest):
    """
    生成对话摘要
    
    Args:
        request: 摘要生成请求
    
    Returns:
        生成的摘要
    """
    try:
        service = get_summary_service()
        
        # 转换轮次
        turns = []
        if request.turns:
            for t in request.turns:
                turns.append(ConversationTurn(
                    role=t.role,
                    content=t.content,
                    timestamp=t.timestamp or 0.0,
                    intent_type=t.intent_type or "",
                ))
        
        if not turns:
            return GenerateSummaryResponse(
                success=False,
                error="No turns provided",
            )
        
        # 解析摘要类型
        try:
            summary_type = SummaryType(request.summary_type)
        except ValueError:
            summary_type = SummaryType.INSTANT
        
        # 生成摘要
        summary = service.generate_summary(
            turns=turns,
            summary_type=summary_type,
            conversation_id=request.conversation_id,
        )
        
        return GenerateSummaryResponse(
            success=True,
            summary=summary.to_dict(),
        )
        
    except Exception as e:
        logger.error(f"Generate summary failed: {e}")
        return GenerateSummaryResponse(
            success=False,
            error=str(e),
        )


@router.get("/{conversation_id}")
async def get_summaries(conversation_id: str):
    """
    获取对话的所有摘要
    
    Args:
        conversation_id: 对话ID
    
    Returns:
        摘要列表
    """
    try:
        service = get_summary_service()
        summaries = service.get_all_summaries(conversation_id)
        
        return {
            "conversation_id": conversation_id,
            "summaries": [s.to_dict() for s in summaries],
            "count": len(summaries),
        }
        
    except Exception as e:
        logger.error(f"Get summaries failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/context")
async def get_summary_for_context(conversation_id: str):
    """
    获取用于上下文的摘要
    
    Args:
        conversation_id: 对话ID
    
    Returns:
        摘要文本
    """
    service = get_summary_service()
    context = service.get_summary_for_context(conversation_id)
    
    return {
        "conversation_id": conversation_id,
        "context": context,
        "has_summary": context is not None,
    }


@router.post("/compress")
async def compress_history(request: CompressHistoryRequest):
    """
    压缩对话历史
    
    将超出限制的历史消息生成摘要，保留最近的消息
    """
    try:
        service = get_summary_service()
        
        # 转换轮次
        turns = [
            ConversationTurn(
                role=t.role,
                content=t.content,
                timestamp=t.timestamp or 0.0,
                intent_type=t.intent_type or "",
            )
            for t in request.turns
        ]
        
        # 压缩
        kept_turns, summary = service.compress_history(turns, request.max_turns)
        
        return {
            "original_count": len(turns),
            "kept_count": len(kept_turns),
            "summary": summary.to_dict() if summary else None,
            "kept_turns": [
                {"role": t.role, "content": t.content}
                for t in kept_turns
            ],
        }
        
    except Exception as e:
        logger.error(f"Compress history failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check")
async def check_should_summarize(request: CompressHistoryRequest):
    """
    检查是否需要生成摘要
    """
    service = get_summary_service()
    
    turns = [
        ConversationTurn(
            role=t.role,
            content=t.content,
            timestamp=t.timestamp or 0.0,
        )
        for t in request.turns
    ]
    
    should_sum, sum_type = service.should_summarize(turns)
    
    return {
        "should_summarize": should_sum,
        "summary_type": sum_type.value if should_sum else None,
        "turn_count": len(turns),
    }


@router.delete("/{conversation_id}")
async def clear_summaries(conversation_id: str):
    """清除对话的摘要"""
    service = get_summary_service()
    service.clear_summaries(conversation_id)
    
    return {"status": "cleared", "conversation_id": conversation_id}

