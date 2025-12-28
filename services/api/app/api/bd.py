"""
BD/Sales 专用 API
提供案例搜索、报价查询、方案生成等功能
"""
import os
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services.retrieval import (
    search_cases,
    search_quotes,
    search_with_relations,
    get_product_kus,
)
from ..services.intent_recognizer import recognize_intent, IntentType
from ..services.response_builder import build_response, ResponseBuilder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/bd", tags=["bd"])


class CaseSearchRequest(BaseModel):
    query: Optional[str] = None
    industry: Optional[str] = None
    product_id: Optional[str] = None
    use_case: Optional[str] = None
    limit: int = 10


class QuoteSearchRequest(BaseModel):
    product_id: Optional[str] = None
    query: Optional[str] = None
    limit: int = 5


class ProposalRequest(BaseModel):
    topic: str
    product_ids: Optional[List[str]] = None
    include_cases: bool = True
    include_quotes: bool = True
    style: str = "professional"  # professional, concise, detailed


class CaseResponse(BaseModel):
    id: str
    title: str
    summary: str
    industry: List[str]
    use_case: List[str]
    product_id: Optional[str] = None
    highlights: List[str] = []


@router.post("/cases", response_model=List[CaseResponse])
async def search_cases_endpoint(request: CaseSearchRequest):
    """
    搜索客户案例
    
    支持按行业、产品、场景筛选
    """
    try:
        hits = search_cases(
            industry=request.industry,
            product_id=request.product_id,
            use_case=request.use_case,
            query=request.query,
            top_k=request.limit,
        )
        
        results = []
        for hit in hits:
            # 从摘要中提取亮点
            summary = hit.get("summary", "")
            highlights = _extract_highlights(summary)
            
            results.append(CaseResponse(
                id=hit.get("id", ""),
                title=hit.get("title", ""),
                summary=summary,
                industry=hit.get("industry_tags", []),
                use_case=hit.get("use_case_tags", []),
                product_id=hit.get("product_id"),
                highlights=highlights,
            ))
        
        return results
        
    except Exception as e:
        logger.error(f"Search cases error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases")
async def search_cases_get(
    query: Optional[str] = Query(None),
    industry: Optional[str] = Query(None, description="行业筛选"),
    product: Optional[str] = Query(None, description="产品筛选"),
    limit: int = Query(10, ge=1, le=50),
):
    """
    搜索客户案例（GET 方式）
    
    示例：/v1/bd/cases?industry=金融&limit=5
    """
    try:
        hits = search_cases(
            industry=industry,
            product_id=product,
            query=query,
            top_k=limit,
        )
        
        return {
            "count": len(hits),
            "cases": [
                {
                    "id": hit.get("id"),
                    "title": hit.get("title"),
                    "summary": hit.get("summary", "")[:300],
                    "industry": hit.get("industry_tags", []),
                    "use_case": hit.get("use_case_tags", []),
                    "product_id": hit.get("product_id"),
                }
                for hit in hits
            ],
        }
        
    except Exception as e:
        logger.error(f"Search cases error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quotes/{product_id}")
async def get_product_quotes(
    product_id: str,
    query: Optional[str] = Query(None),
):
    """
    获取产品报价信息
    """
    try:
        hits = search_quotes(product_id=product_id, query=query, top_k=5)
        
        if not hits:
            # 尝试从产品 KU 中提取价格信息
            product_kus = get_product_kus(product_id, include_types=["core", "quote"])
            quotes = product_kus.get("kus_by_type", {}).get("quote", [])
            
            if quotes:
                hits = quotes
            else:
                return {
                    "product_id": product_id,
                    "has_quote": False,
                    "message": "未找到该产品的报价信息，请联系销售获取最新报价",
                    "contact": "sales@example.com",
                }
        
        return {
            "product_id": product_id,
            "has_quote": True,
            "quotes": [
                {
                    "id": hit.get("id"),
                    "title": hit.get("title"),
                    "summary": hit.get("summary", ""),
                    "source_file": hit.get("source_file", ""),
                }
                for hit in hits
            ],
            "note": "报价信息可能有时效性，建议确认最新价格",
        }
        
    except Exception as e:
        logger.error(f"Get quotes error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-proposal")
async def generate_proposal(request: ProposalRequest):
    """
    生成方案大纲
    
    根据主题和产品，自动生成方案的结构大纲
    """
    try:
        # 1. 搜索相关内容
        intent_result = recognize_intent(request.topic)
        
        search_result = search_with_relations(
            query=request.topic,
            intent_result=intent_result,
            include_related=True,
            top_k=10,
        )
        
        hits = search_result.get("hits", [])
        
        # 2. 如果指定了产品，筛选相关内容
        if request.product_ids:
            hits = [h for h in hits if h.get("product_id") in request.product_ids] or hits
        
        # 3. 收集案例
        cases = []
        if request.include_cases:
            for product_id in (request.product_ids or []):
                product_cases = search_cases(product_id=product_id, top_k=3)
                cases.extend(product_cases)
        
        # 4. 收集报价
        quotes = []
        if request.include_quotes:
            for product_id in (request.product_ids or []):
                product_quotes = search_quotes(product_id=product_id, top_k=2)
                quotes.extend(product_quotes)
        
        # 5. 生成方案大纲
        outline = _generate_proposal_outline(
            topic=request.topic,
            hits=hits,
            cases=cases,
            quotes=quotes,
            style=request.style,
        )
        
        return {
            "topic": request.topic,
            "outline": outline,
            "related_content": {
                "kus": len(hits),
                "cases": len(cases),
                "quotes": len(quotes),
            },
            "sources": [
                {"id": h.get("id"), "title": h.get("title")}
                for h in hits[:5]
            ],
        }
        
    except Exception as e:
        logger.error(f"Generate proposal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick-answer")
async def quick_answer(
    q: str = Query(..., description="问题"),
    product: Optional[str] = Query(None, description="产品筛选"),
):
    """
    快速问答
    
    返回简洁的回答和相关来源
    """
    try:
        # 识别意图
        intent_result = recognize_intent(q)
        
        # 搜索相关内容
        search_result = search_with_relations(
            query=q,
            intent_result=intent_result,
            product_id=product,
            include_related=True,
            top_k=5,
        )
        
        hits = search_result.get("hits", [])
        related = search_result.get("related", {})
        
        if not hits:
            return {
                "query": q,
                "answer": "抱歉，未找到相关信息。请尝试换个方式提问。",
                "sources": [],
                "recommendations": [],
            }
        
        # 构建回答上下文
        built_response = build_response(
            query=q,
            intent=intent_result,
            hits=hits,
            related_kus=related,
        )
        
        # 提取关键信息作为快速回答
        quick_answer_text = _extract_quick_answer(hits, intent_result)
        
        # 格式化来源
        builder = ResponseBuilder()
        sources_text = builder.format_sources(built_response.sources)
        recommendations_text = builder.format_recommendations(built_response.recommendations)
        
        return {
            "query": q,
            "intent": intent_result.intent_type.value,
            "answer": quick_answer_text,
            "sources": built_response.sources,
            "recommendations": built_response.recommendations,
            "formatted_sources": sources_text,
            "formatted_recommendations": recommendations_text,
        }
        
    except Exception as e:
        logger.error(f"Quick answer error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/industries")
async def list_industries():
    """获取支持的行业列表"""
    return {
        "industries": [
            {"id": "金融", "name": "金融", "icon": "🏦"},
            {"id": "制造", "name": "制造", "icon": "🏭"},
            {"id": "医疗", "name": "医疗", "icon": "🏥"},
            {"id": "零售", "name": "零售", "icon": "🛒"},
            {"id": "能源", "name": "能源", "icon": "⚡"},
            {"id": "交通", "name": "交通", "icon": "🚗"},
            {"id": "教育", "name": "教育", "icon": "🎓"},
            {"id": "政府", "name": "政府", "icon": "🏛️"},
            {"id": "通信", "name": "通信", "icon": "📡"},
            {"id": "互联网", "name": "互联网", "icon": "🌐"},
        ]
    }


def _extract_highlights(summary: str) -> List[str]:
    """从摘要中提取亮点"""
    highlights = []
    
    # 查找常见的成果模式
    import re
    patterns = [
        r'提升[了]?(\d+%)',
        r'降低[了]?(\d+%)',
        r'节省[了]?(\d+[万亿%])',
        r'效率提高[了]?(\d+)',
        r'成本降低[了]?(\d+)',
        r'(\d+)个月.*上线',
        r'服务(\d+[万亿]+)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, summary)
        for match in matches:
            # 找到包含这个数字的完整句子片段
            idx = summary.find(match)
            if idx >= 0:
                start = max(0, summary.rfind('，', 0, idx) + 1)
                end = summary.find('。', idx)
                if end < 0:
                    end = min(len(summary), idx + 50)
                highlight = summary[start:end].strip('，。')
                if len(highlight) < 50 and highlight not in highlights:
                    highlights.append(highlight)
    
    return highlights[:3]


def _generate_proposal_outline(
    topic: str,
    hits: List[dict],
    cases: List[dict],
    quotes: List[dict],
    style: str,
) -> dict:
    """生成方案大纲"""
    
    # 提取关键产品和功能
    products = list(set(h.get("product_id") for h in hits if h.get("product_id")))
    
    # 生成大纲结构
    outline = {
        "title": f"{topic} 解决方案",
        "sections": [
            {
                "title": "1. 背景与需求分析",
                "content_hints": ["行业背景", "客户痛点", "需求分析"],
            },
            {
                "title": "2. 解决方案概述",
                "content_hints": ["整体架构", "核心能力", "技术优势"],
            },
            {
                "title": "3. 详细方案设计",
                "content_hints": [
                    f"产品: {', '.join(products[:3]) if products else '待定'}",
                    "功能模块",
                    "技术实现",
                ],
            },
        ],
    }
    
    if cases:
        outline["sections"].append({
            "title": "4. 成功案例",
            "content_hints": [f"案例: {c.get('title')}" for c in cases[:3]],
        })
    
    outline["sections"].append({
        "title": f"{len(outline['sections']) + 1}. 实施计划",
        "content_hints": ["实施步骤", "时间规划", "资源配置"],
    })
    
    if quotes:
        outline["sections"].append({
            "title": f"{len(outline['sections']) + 1}. 投资预算",
            "content_hints": ["费用明细", "ROI 分析"],
        })
    
    outline["sections"].append({
        "title": f"{len(outline['sections']) + 1}. 总结",
        "content_hints": ["价值主张", "后续建议"],
    })
    
    return outline


def _extract_quick_answer(hits: List[dict], intent_result) -> str:
    """提取快速回答"""
    if not hits:
        return "未找到相关信息"
    
    top_hit = hits[0]
    summary = top_hit.get("summary", "")
    
    # 根据意图类型调整回答格式
    intent_type = intent_result.intent_type
    
    if intent_type == IntentType.CASE_STUDY:
        return f"找到 {len(hits)} 个相关案例，最相关的是：{top_hit.get('title')}\n\n{summary[:200]}..."
    
    elif intent_type.value == "quote":
        return f"关于报价：\n{summary[:300]}...\n\n建议联系销售获取最新报价。"
    
    else:
        return summary[:400] + ("..." if len(summary) > 400 else "")

