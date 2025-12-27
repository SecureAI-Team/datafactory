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
from .param_extractor import (
    ExtractedParam,
    ParamOperator,
    extract_params,
    extract_param_requirements,
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


# ==================== 参数化检索（Phase 3 增强）====================

def search_with_params(
    query: str,
    extracted_params: List[ExtractedParam] = None,
    scenario_id: str = None,
    intent_result: IntentResult = None,
    top_k: int = 10,
    boost_params: float = 2.0,
) -> List[Dict]:
    """
    基于提取参数的混合检索
    
    结合语义搜索 + 参数过滤，提供更精确的结果
    
    Args:
        query: 用户查询
        extracted_params: 提取的参数列表
        scenario_id: 场景过滤
        intent_result: 意图识别结果
        top_k: 返回数量
        boost_params: 参数匹配的权重提升
    
    Returns:
        匹配的知识单元列表
    """
    # 如果没有传入参数，自动提取
    if extracted_params is None:
        extracted_params = extract_params(query)
    
    logger.info(f"search_with_params: query='{query[:50]}...', params={[p.to_dict() for p in extracted_params]}")
    
    # 构建主查询
    query_truncated = query[:200] if len(query) > 200 else query
    
    main_query = {
        "simple_query_string": {
            "query": query_truncated,
            "fields": ["title^3", "summary^2", "full_text", "terms", "key_points"],
            "default_operator": "or"
        }
    }
    
    # 构建参数过滤/提升查询
    param_queries = []
    for param in extracted_params:
        param_query = _build_param_query(param, boost_params)
        if param_query:
            param_queries.append(param_query)
    
    # 构建过滤条件
    filter_clauses = []
    if scenario_id:
        filter_clauses.append({"term": {"scenario_id": scenario_id}})
    
    if intent_result and intent_result.scenario_ids:
        filter_clauses.append({"terms": {"scenario_id": intent_result.scenario_ids}})
    
    # 组装完整查询
    bool_query = {
        "must": [main_query],
    }
    
    if param_queries:
        bool_query["should"] = param_queries
        bool_query["minimum_should_match"] = 0  # 参数匹配是可选的，会提升分数
    
    if filter_clauses:
        bool_query["filter"] = filter_clauses
    
    body = {
        "query": {"bool": bool_query},
        "size": top_k,
    }
    
    try:
        res = os_client.search(index=settings.os_index, body=body)
    except RequestError as e:
        logger.warning(f"Param search query error, falling back: {e}")
        # 回退到简单搜索
        return _simple_search(query, None, top_k)
    except Exception as e:
        logger.error(f"OpenSearch error: {e}")
        return []
    
    hits = _parse_hits(res)
    
    # 添加参数匹配信息
    for hit in hits:
        hit["matched_params"] = _find_matched_params(hit, extracted_params)
    
    return hits


def _build_param_query(param: ExtractedParam, boost: float = 2.0) -> Optional[Dict]:
    """构建单个参数的嵌套查询"""
    
    nested_must = [{"term": {"params.name": param.canonical_name}}]
    
    # 根据运算符构建范围查询
    if param.operator == ParamOperator.EQ:
        # 精确匹配，使用容差
        tolerance = 0.1  # 10%
        nested_must.append({
            "range": {
                "params.value": {
                    "gte": param.value * (1 - tolerance),
                    "lte": param.value * (1 + tolerance),
                }
            }
        })
    elif param.operator == ParamOperator.GTE:
        nested_must.append({"range": {"params.value": {"gte": param.value}}})
    elif param.operator == ParamOperator.GT:
        nested_must.append({"range": {"params.value": {"gt": param.value}}})
    elif param.operator == ParamOperator.LTE:
        nested_must.append({"range": {"params.value": {"lte": param.value}}})
    elif param.operator == ParamOperator.LT:
        nested_must.append({"range": {"params.value": {"lt": param.value}}})
    elif param.operator == ParamOperator.BETWEEN:
        if param.value_max:
            nested_must.append({
                "range": {
                    "params.value": {
                        "gte": param.value,
                        "lte": param.value_max,
                    }
                }
            })
    elif param.operator == ParamOperator.APPROX:
        # 约等于，使用较大容差
        tolerance = 0.2  # 20%
        nested_must.append({
            "range": {
                "params.value": {
                    "gte": param.value * (1 - tolerance),
                    "lte": param.value * (1 + tolerance),
                }
            }
        })
    
    return {
        "nested": {
            "path": "params",
            "query": {"bool": {"must": nested_must}},
            "boost": boost,
            "inner_hits": {"size": 1},  # 返回匹配的参数
        }
    }


def _find_matched_params(hit: Dict, extracted_params: List[ExtractedParam]) -> List[Dict]:
    """找出命中文档中匹配的参数"""
    matched = []
    doc_params = hit.get("params", [])
    
    for req_param in extracted_params:
        for doc_param in doc_params:
            if doc_param.get("name") == req_param.canonical_name:
                doc_value = doc_param.get("value")
                if doc_value is not None:
                    is_match = _check_param_match(req_param, doc_value)
                    if is_match:
                        matched.append({
                            "name": req_param.canonical_name,
                            "requested": {
                                "value": req_param.value,
                                "operator": req_param.operator.value,
                            },
                            "found": {
                                "value": doc_value,
                                "unit": doc_param.get("unit", ""),
                            },
                            "match": True,
                        })
    
    return matched


def _check_param_match(req: ExtractedParam, doc_value: float) -> bool:
    """检查参数值是否匹配"""
    if req.operator == ParamOperator.EQ:
        tolerance = 0.1
        return req.value * (1 - tolerance) <= doc_value <= req.value * (1 + tolerance)
    elif req.operator == ParamOperator.GTE:
        return doc_value >= req.value
    elif req.operator == ParamOperator.GT:
        return doc_value > req.value
    elif req.operator == ParamOperator.LTE:
        return doc_value <= req.value
    elif req.operator == ParamOperator.LT:
        return doc_value < req.value
    elif req.operator == ParamOperator.BETWEEN:
        return req.value <= doc_value <= (req.value_max or req.value)
    elif req.operator == ParamOperator.APPROX:
        tolerance = 0.2
        return req.value * (1 - tolerance) <= doc_value <= req.value * (1 + tolerance)
    return False


def compare_products(
    product_names: List[str],
    param_names: List[str] = None,
    scenario_id: str = None,
) -> Dict[str, Any]:
    """
    产品/方案规格比对
    
    Args:
        product_names: 产品/方案名称列表
        param_names: 要比较的参数名列表（空则比较所有参数）
        scenario_id: 场景过滤
    
    Returns:
        比对结果
    """
    results = {"products": [], "comparison": {}}
    
    for name in product_names:
        # 搜索产品
        query = {
            "bool": {
                "must": [
                    {"match": {"title": name}}
                ]
            }
        }
        
        if scenario_id:
            query["bool"]["filter"] = [{"term": {"scenario_id": scenario_id}}]
        
        try:
            res = os_client.search(
                index=settings.os_index,
                body={"query": query, "size": 1}
            )
        except Exception as e:
            logger.error(f"Product search error: {e}")
            continue
        
        hits = res.get("hits", {}).get("hits", [])
        if hits:
            src = hits[0]["_source"]
            product_info = {
                "name": name,
                "title": src.get("title", ""),
                "params": {},
            }
            
            # 提取参数
            for param in src.get("params", []):
                param_name = param.get("name", "")
                if param_names is None or param_name in param_names:
                    product_info["params"][param_name] = {
                        "value": param.get("value"),
                        "unit": param.get("unit", ""),
                    }
            
            results["products"].append(product_info)
    
    # 构建比对表
    if len(results["products"]) >= 2:
        all_param_names = set()
        for prod in results["products"]:
            all_param_names.update(prod["params"].keys())
        
        for param_name in all_param_names:
            results["comparison"][param_name] = {}
            values = []
            
            for prod in results["products"]:
                param_data = prod["params"].get(param_name, {})
                value = param_data.get("value")
                results["comparison"][param_name][prod["name"]] = param_data
                if value is not None:
                    values.append(value)
            
            # 计算最大/最小
            if values:
                results["comparison"][param_name]["_best"] = max(values)
                results["comparison"][param_name]["_worst"] = min(values)
    
    return results


def smart_search(
    query: str,
    top_k: int = 10,
    auto_extract_params: bool = True,
) -> Dict[str, Any]:
    """
    智能搜索：自动识别查询类型并应用最佳检索策略
    
    Args:
        query: 用户查询
        top_k: 返回数量
        auto_extract_params: 是否自动提取参数
    
    Returns:
        搜索结果和元信息
    """
    from .intent_recognizer import recognize_intent
    
    # 意图识别
    intent_result = recognize_intent(query)
    
    # 参数提取
    extracted_params = []
    if auto_extract_params:
        extracted_params = extract_params(query)
    
    # 根据意图选择检索策略
    if intent_result.intent_type == IntentType.PARAMETER_QUERY and extracted_params:
        # 参数查询：使用参数化检索
        hits = search_with_params(
            query,
            extracted_params=extracted_params,
            intent_result=intent_result,
            top_k=top_k,
        )
        strategy = "param_search"
    elif intent_result.intent_type == IntentType.CALCULATION:
        # 计算查询：搜索包含相关参数的文档
        required_params = [p.canonical_name for p in extracted_params]
        hits = search_for_calculation(
            query,
            required_params=required_params,
            scenario_id=intent_result.scenario_ids[0] if intent_result.scenario_ids else None,
            top_k=top_k,
        )
        strategy = "calculation_search"
    elif intent_result.intent_type == IntentType.COMPARISON:
        # 比较查询：使用场景化检索
        hits = _scenario_aware_search(query, intent_result, {}, top_k)
        strategy = "comparison_search"
    else:
        # 通用查询：如果有参数则使用参数化检索，否则使用场景化检索
        if extracted_params:
            hits = search_with_params(
                query,
                extracted_params=extracted_params,
                intent_result=intent_result,
                top_k=top_k,
            )
            strategy = "param_enhanced_search"
        else:
            hits = _scenario_aware_search(query, intent_result, {}, top_k)
            strategy = "scenario_search"
    
    return {
        "hits": hits,
        "total": len(hits),
        "strategy": strategy,
        "intent": {
            "type": intent_result.intent_type.value,
            "confidence": intent_result.confidence,
            "scenarios": intent_result.scenario_ids,
        },
        "extracted_params": [p.to_dict() for p in extracted_params],
    }
