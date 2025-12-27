"""
知识库检索服务
支持场景化检索和参数查询
"""
import logging
from typing import Optional, List, Dict, Any

from opensearchpy.helpers import scan
from opensearchpy.exceptions import RequestError

from ..clients.opensearch_client import os_client
from ..config import settings
from .intent_recognizer import IntentResult, IntentType
from .scenario_router import (
    RetrievalConfig,
    ScenarioRouter,
    get_scenario_router,
    route_and_build_query,
)

logger = logging.getLogger(__name__)


def search(
    query: str,
    filters: Dict = None,
    top_k: int = 5,
    intent_result: Optional[IntentResult] = None,
    entities: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """
    搜索知识单元
    
    Args:
        query: 用户查询
        filters: 简单过滤条件（向后兼容）
        top_k: 返回数量
        intent_result: 意图识别结果（可选，用于场景化检索）
        entities: 抽取的实体（可选，用于参数过滤）
    
    Returns:
        匹配的知识单元列表
    """
    try:
        if intent_result:
            # 使用场景化检索
            return _scenario_aware_search(query, intent_result, entities, top_k)
        else:
            # 简单检索（向后兼容）
            return _simple_search(query, filters, top_k)
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []


def _simple_search(
    query: str,
    filters: Dict = None,
    top_k: int = 5,
) -> List[Dict]:
    """简单检索（向后兼容）"""
    # 截断过长查询
    query_truncated = query[:200] if len(query) > 200 else query
    
    # 使用 simple_query_string 避免 maxClauseCount 问题
    search_query = {
        "simple_query_string": {
            "query": query_truncated,
            "fields": ["title^3", "summary^2", "full_text", "terms", "key_points"],
            "default_operator": "or"
        }
    }
    
    if filters:
        must = [search_query]
        for k, v in filters.items():
            must.append({"term": {k: v}})
        body = {"query": {"bool": {"must": must}}, "size": top_k}
    else:
        body = {"query": search_query, "size": top_k}
    
    try:
        res = os_client.search(index=settings.os_index, body=body)
    except RequestError as e:
        logger.error(f"OpenSearch query error: {e}")
        # 回退到 match_all
        try:
            res = os_client.search(
                index=settings.os_index,
                body={"query": {"match_all": {}}, "size": top_k}
            )
        except Exception:
            return []
    except Exception as e:
        logger.error(f"OpenSearch error: {e}")
        return []
    
    return _parse_hits(res)


def _scenario_aware_search(
    query: str,
    intent_result: IntentResult,
    entities: Optional[Dict[str, Any]],
    top_k: int,
) -> List[Dict]:
    """场景化检索"""
    
    # 获取检索配置和查询
    config, os_query = route_and_build_query(
        query,
        intent_result,
        entities or intent_result.entities,
    )
    
    # 覆盖 top_k
    os_query["size"] = top_k or config.top_k
    
    logger.info(
        f"Scenario-aware search: "
        f"scenario_filter={config.scenario_filter}, "
        f"scene_tags={config.scenario_tags_filter}, "
        f"params_query={config.include_params_query}"
    )
    
    try:
        res = os_client.search(index=settings.os_index, body=os_query)
    except RequestError as e:
        logger.warning(f"Scenario search failed, falling back: {e}")
        # 回退到简单搜索
        return _simple_search(query, None, top_k)
    except Exception as e:
        logger.error(f"OpenSearch error: {e}")
        return []
    
    hits = _parse_hits(res)
    
    # 如果场景检索结果太少，补充通用检索
    if len(hits) < top_k // 2:
        logger.info(f"Scenario search returned few results ({len(hits)}), supplementing...")
        supplemental = _simple_search(query, None, top_k - len(hits))
        
        # 合并去重
        seen_ids = {h["id"] for h in hits}
        for h in supplemental:
            if h["id"] not in seen_ids:
                hits.append(h)
                seen_ids.add(h["id"])
    
    return hits[:top_k]


def _parse_hits(res: Dict) -> List[Dict]:
    """解析 OpenSearch 响应"""
    hits = []
    
    for hit in res.get("hits", {}).get("hits", []):
        src = hit.get("_source", {})
        
        parsed = {
            "id": hit.get("_id"),
            "title": src.get("title", "Untitled"),
            "summary": src.get("summary", ""),
            "body": src.get("full_text", ""),
            "score": hit.get("_score"),
            "tags": src.get("terms", []),
            "key_points": src.get("key_points", []),
            "source_file": src.get("source_file", ""),
            # 新增字段
            "scenario_id": src.get("scenario_id", ""),
            "scenario_tags": src.get("scenario_tags", []),
            "solution_id": src.get("solution_id", ""),
            "intent_types": src.get("intent_types", []),
            "applicability_score": src.get("applicability_score", 0.5),
            "material_type": src.get("material_type", ""),
            "params": src.get("params", []),
        }
        
        hits.append(parsed)
    
    return hits


def search_by_params(
    param_name: str,
    min_value: float = None,
    max_value: float = None,
    exact_value: float = None,
    tolerance: float = 0.2,
    scenario_id: str = None,
    top_k: int = 10,
) -> List[Dict]:
    """
    按参数搜索知识单元
    
    Args:
        param_name: 参数名称（如"功率"、"精度"）
        min_value: 最小值
        max_value: 最大值
        exact_value: 精确值（会转换为容差范围）
        tolerance: 容差比例（用于精确值搜索）
        scenario_id: 场景过滤
        top_k: 返回数量
    
    Returns:
        匹配的知识单元列表
    """
    # 构建嵌套查询
    nested_must = [{"term": {"params.name": param_name}}]
    
    if exact_value is not None:
        min_value = exact_value * (1 - tolerance)
        max_value = exact_value * (1 + tolerance)
    
    if min_value is not None or max_value is not None:
        range_query = {}
        if min_value is not None:
            range_query["gte"] = min_value
        if max_value is not None:
            range_query["lte"] = max_value
        nested_must.append({"range": {"params.value": range_query}})
    
    nested_query = {
        "nested": {
            "path": "params",
            "query": {
                "bool": {"must": nested_must}
            },
            "inner_hits": {"size": 3}  # 返回匹配的参数详情
        }
    }
    
    # 外层过滤
    filter_clauses = []
    if scenario_id:
        filter_clauses.append({"term": {"scenario_id": scenario_id}})
    
    # 构建完整查询
    if filter_clauses:
        body = {
            "query": {
                "bool": {
                    "must": [nested_query],
                    "filter": filter_clauses,
                }
            },
            "size": top_k,
        }
    else:
        body = {"query": nested_query, "size": top_k}
    
    try:
        res = os_client.search(index=settings.os_index, body=body)
    except Exception as e:
        logger.error(f"Param search error: {e}")
        return []
    
    return _parse_hits(res)


def search_for_calculation(
    query: str,
    required_params: List[str],
    scenario_id: str = None,
    top_k: int = 5,
) -> List[Dict]:
    """
    为计算查询搜索知识单元
    
    Args:
        query: 用户查询
        required_params: 需要的参数列表
        scenario_id: 场景过滤
        top_k: 返回数量
    
    Returns:
        包含所需参数的知识单元列表
    """
    # 主查询
    query_truncated = query[:200] if len(query) > 200 else query
    
    main_query = {
        "simple_query_string": {
            "query": query_truncated,
            "fields": ["title^2", "summary", "full_text"],
            "default_operator": "or"
        }
    }
    
    # 参数存在性查询
    should_clauses = []
    for param_name in required_params:
        should_clauses.append({
            "nested": {
                "path": "params",
                "query": {"term": {"params.name": param_name}},
                "boost": 2.0,
            }
        })
    
    # 场景过滤
    filter_clauses = []
    if scenario_id:
        filter_clauses.append({"term": {"scenario_id": scenario_id}})
    
    # 组装查询
    bool_query = {
        "must": [main_query],
        "should": should_clauses,
        "minimum_should_match": 1 if required_params else 0,
    }
    
    if filter_clauses:
        bool_query["filter"] = filter_clauses
    
    body = {
        "query": {"bool": bool_query},
        "size": top_k,
    }
    
    try:
        res = os_client.search(index=settings.os_index, body=body)
    except Exception as e:
        logger.error(f"Calculation search error: {e}")
        return []
    
    return _parse_hits(res)


def get_index_stats() -> Dict[str, Any]:
    """获取索引统计信息"""
    try:
        count_res = os_client.count(index=settings.os_index)
        doc_count = count_res.get("count", 0)
        
        # 聚合统计
        agg_body = {
            "size": 0,
            "aggs": {
                "scenarios": {"terms": {"field": "scenario_id", "size": 20}},
                "material_types": {"terms": {"field": "material_type", "size": 20}},
                "intent_types": {"terms": {"field": "intent_types", "size": 20}},
                "avg_applicability": {"avg": {"field": "applicability_score"}},
            }
        }
        
        agg_res = os_client.search(index=settings.os_index, body=agg_body)
        aggs = agg_res.get("aggregations", {})
        
        return {
            "document_count": doc_count,
            "scenarios": [
                {"id": b["key"], "count": b["doc_count"]}
                for b in aggs.get("scenarios", {}).get("buckets", [])
            ],
            "material_types": [
                {"type": b["key"], "count": b["doc_count"]}
                for b in aggs.get("material_types", {}).get("buckets", [])
            ],
            "intent_types": [
                {"type": b["key"], "count": b["doc_count"]}
                for b in aggs.get("intent_types", {}).get("buckets", [])
            ],
            "avg_applicability_score": aggs.get("avg_applicability", {}).get("value", 0),
        }
    except Exception as e:
        logger.error(f"Index stats error: {e}")
        return {"error": str(e)}
