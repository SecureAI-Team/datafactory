"""
场景化检索路由
根据意图和场景动态构建 OpenSearch 查询
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .intent_recognizer import IntentResult, IntentType, SceneClassification

logger = logging.getLogger(__name__)


@dataclass
class RetrievalConfig:
    """检索配置"""
    # 检索字段权重
    field_boosts: Dict[str, float] = field(default_factory=lambda: {
        "title": 3.0,
        "summary": 2.0,
        "full_text": 1.0,
        "terms": 1.5,
        "key_points": 1.5,
    })
    
    # 过滤条件
    scenario_filter: Optional[str] = None
    scenario_tags_filter: List[str] = field(default_factory=list)
    intent_types_filter: List[str] = field(default_factory=list)
    material_type_filter: Optional[str] = None
    
    # 参数过滤（用于参数查询和计算）
    param_filters: List[Dict] = field(default_factory=list)
    
    # 通用性评分阈值
    min_applicability_score: float = 0.0
    
    # 检索数量
    top_k: int = 5
    
    # 是否使用混合检索
    use_hybrid: bool = True
    
    # 是否包含参数嵌套查询
    include_params_query: bool = False


class ScenarioRouter:
    """场景化检索路由器"""
    
    def __init__(self):
        # 场景-意图 -> 检索配置映射
        self.routing_rules = self._build_routing_rules()
    
    def _build_routing_rules(self) -> Dict[Tuple[str, IntentType], Dict]:
        """构建路由规则"""
        return {
            # === AOI 视觉检测场景 ===
            ("aoi_inspection", IntentType.SOLUTION_RECOMMENDATION): {
                "field_boosts": {
                    "title": 3.0,
                    "summary": 2.5,
                    "key_points": 2.0,
                    "terms": 1.5,
                },
                "scenario_tags_filter": ["aoi", "vision", "inspection"],
                "material_type_priority": ["datasheet", "whitepaper", "case_study"],
                "top_k": 6,
            },
            ("aoi_inspection", IntentType.PARAMETER_QUERY): {
                "field_boosts": {
                    "params.name": 3.0,
                    "terms": 2.0,
                    "title": 1.5,
                },
                "include_params_query": True,
                "scenario_tags_filter": ["aoi"],
                "top_k": 5,
            },
            ("aoi_inspection", IntentType.CALCULATION): {
                "field_boosts": {
                    "params.name": 3.0,
                    "terms": 2.0,
                },
                "include_params_query": True,
                "scenario_tags_filter": ["aoi"],
                "material_type_priority": ["datasheet", "tutorial"],
                "top_k": 5,
            },
            ("aoi_inspection", IntentType.TROUBLESHOOTING): {
                "field_boosts": {
                    "key_points": 3.0,
                    "full_text": 2.0,
                    "summary": 1.5,
                },
                "scenario_tags_filter": ["aoi"],
                "intent_types_filter": ["troubleshooting", "faq"],
                "top_k": 5,
            },
            
            # === 网络安全场景 ===
            ("network_security", IntentType.SOLUTION_RECOMMENDATION): {
                "field_boosts": {
                    "title": 3.0,
                    "summary": 2.5,
                    "key_points": 2.0,
                },
                "scenario_tags_filter": ["security", "network"],
                "material_type_priority": ["whitepaper", "solution"],
                "top_k": 6,
            },
            ("network_security", IntentType.COMPARISON): {
                "field_boosts": {
                    "title": 2.0,
                    "summary": 2.5,
                    "key_points": 3.0,
                },
                "scenario_tags_filter": ["security"],
                "top_k": 8,  # 对比需要更多材料
            },
            
            # === 通用场景 ===
            ("default", IntentType.CONCEPT_EXPLAIN): {
                "field_boosts": {
                    "title": 2.5,
                    "summary": 3.0,
                    "full_text": 1.5,
                },
                "min_applicability_score": 0.5,  # 偏向通用材料
                "top_k": 4,
            },
            ("default", IntentType.BEST_PRACTICE): {
                "field_boosts": {
                    "key_points": 3.0,
                    "summary": 2.0,
                    "full_text": 1.5,
                },
                "intent_types_filter": ["best_practice"],
                "top_k": 5,
            },
            ("default", IntentType.HOW_TO): {
                "field_boosts": {
                    "key_points": 3.0,
                    "full_text": 2.0,
                    "summary": 1.5,
                },
                "material_type_priority": ["tutorial", "guide"],
                "intent_types_filter": ["how_to"],
                "top_k": 5,
            },
        }
    
    def route(
        self,
        intent_result: IntentResult,
        entities: Dict[str, Any] = None,
    ) -> RetrievalConfig:
        """
        根据意图结果路由到合适的检索配置
        
        Args:
            intent_result: 意图识别结果
            entities: 抽取的实体
        
        Returns:
            RetrievalConfig: 检索配置
        """
        entities = entities or {}
        
        # 获取基础配置
        config = self._get_base_config(intent_result)
        
        # 根据场景分类调整
        config = self._adjust_by_scene_classification(config, intent_result)
        
        # 根据实体构建参数过滤
        if entities:
            config = self._add_param_filters(config, entities)
        
        logger.info(
            f"Routed query: intent={intent_result.intent_type.value}, "
            f"scenes={intent_result.scenario_ids}, "
            f"top_k={config.top_k}"
        )
        
        return config
    
    def _get_base_config(self, intent_result: IntentResult) -> RetrievalConfig:
        """获取基础检索配置"""
        # 尝试精确匹配 (scenario, intent)
        for scenario_id in intent_result.scenario_ids or ["default"]:
            key = (scenario_id, intent_result.intent_type)
            if key in self.routing_rules:
                rule = self.routing_rules[key]
                return self._rule_to_config(rule, scenario_id)
        
        # 尝试匹配 (default, intent)
        key = ("default", intent_result.intent_type)
        if key in self.routing_rules:
            rule = self.routing_rules[key]
            return self._rule_to_config(rule, None)
        
        # 返回默认配置
        return RetrievalConfig()
    
    def _rule_to_config(self, rule: Dict, scenario_id: Optional[str]) -> RetrievalConfig:
        """将规则转换为配置"""
        config = RetrievalConfig()
        
        if "field_boosts" in rule:
            config.field_boosts = rule["field_boosts"]
        
        if "scenario_tags_filter" in rule:
            config.scenario_tags_filter = rule["scenario_tags_filter"]
        
        if "intent_types_filter" in rule:
            config.intent_types_filter = rule["intent_types_filter"]
        
        if "min_applicability_score" in rule:
            config.min_applicability_score = rule["min_applicability_score"]
        
        if "top_k" in rule:
            config.top_k = rule["top_k"]
        
        if "include_params_query" in rule:
            config.include_params_query = rule["include_params_query"]
        
        if scenario_id:
            config.scenario_filter = scenario_id
        
        return config
    
    def _adjust_by_scene_classification(
        self,
        config: RetrievalConfig,
        intent_result: IntentResult,
    ) -> RetrievalConfig:
        """根据场景分类调整配置"""
        
        if intent_result.scene_classification == SceneClassification.GENERAL:
            # 通用场景：放宽过滤条件，偏向高通用性材料
            config.scenario_filter = None
            config.scenario_tags_filter = []
            config.min_applicability_score = 0.5
            config.top_k = max(config.top_k, 5)
            
        elif intent_result.scene_classification == SceneClassification.SINGLE_SCENE:
            # 单一场景：严格过滤到该场景
            if intent_result.scenario_ids:
                config.scenario_filter = intent_result.scenario_ids[0]
            
        elif intent_result.scene_classification == SceneClassification.MULTI_SCENE:
            # 多场景交叉：使用 should 条件，增加检索数量
            config.scenario_filter = None  # 不严格过滤
            config.top_k = min(config.top_k + 3, 10)
        
        return config
    
    def _add_param_filters(
        self,
        config: RetrievalConfig,
        entities: Dict[str, Any],
    ) -> RetrievalConfig:
        """根据实体添加参数过滤"""
        
        param_mapping = {
            "power": "功率",
            "precision": "精度",
            "capacity": "产能",
            "price": "价格",
        }
        
        for entity_key, param_name in param_mapping.items():
            if entity_key in entities:
                entity = entities[entity_key]
                value = entity.get("value")
                
                if value is not None:
                    # 添加参数范围过滤
                    config.param_filters.append({
                        "name": param_name,
                        "value": value,
                        "tolerance": 0.2,  # 允许 20% 误差
                    })
                    config.include_params_query = True
        
        return config
    
    def build_opensearch_query(
        self,
        query: str,
        config: RetrievalConfig,
    ) -> Dict[str, Any]:
        """
        构建 OpenSearch 查询
        
        Args:
            query: 用户查询
            config: 检索配置
        
        Returns:
            OpenSearch 查询体
        """
        # 截断过长查询
        query_truncated = query[:200] if len(query) > 200 else query
        
        # 构建多字段查询
        fields_with_boosts = [
            f"{field}^{boost}" 
            for field, boost in config.field_boosts.items()
            if not field.startswith("params.")  # 参数字段单独处理
        ]
        
        # 主查询
        main_query = {
            "simple_query_string": {
                "query": query_truncated,
                "fields": fields_with_boosts,
                "default_operator": "or",
            }
        }
        
        # 构建 bool 查询
        must = [main_query]
        filter_clauses = []
        should = []
        
        # 场景过滤
        if config.scenario_filter:
            filter_clauses.append({
                "term": {"scenario_id": config.scenario_filter}
            })
        
        # 场景标签过滤（should，提升相关性）
        if config.scenario_tags_filter:
            should.append({
                "terms": {
                    "scenario_tags": config.scenario_tags_filter,
                    "boost": 2.0,
                }
            })
        
        # 意图类型过滤（should）
        if config.intent_types_filter:
            should.append({
                "terms": {
                    "intent_types": config.intent_types_filter,
                    "boost": 1.5,
                }
            })
        
        # 通用性评分过滤
        if config.min_applicability_score > 0:
            filter_clauses.append({
                "range": {
                    "applicability_score": {
                        "gte": config.min_applicability_score
                    }
                }
            })
        
        # 参数嵌套查询
        if config.include_params_query and config.param_filters:
            for param_filter in config.param_filters:
                param_name = param_filter["name"]
                param_value = param_filter["value"]
                tolerance = param_filter.get("tolerance", 0.2)
                
                min_value = param_value * (1 - tolerance)
                max_value = param_value * (1 + tolerance)
                
                should.append({
                    "nested": {
                        "path": "params",
                        "query": {
                            "bool": {
                                "must": [
                                    {"term": {"params.name": param_name}},
                                    {"range": {
                                        "params.value": {
                                            "gte": min_value,
                                            "lte": max_value,
                                        }
                                    }}
                                ]
                            }
                        },
                        "boost": 3.0,
                    }
                })
        
        # 组装最终查询
        bool_query = {"must": must}
        
        if filter_clauses:
            bool_query["filter"] = filter_clauses
        
        if should:
            bool_query["should"] = should
            bool_query["minimum_should_match"] = 0  # should 是加分项
        
        return {
            "query": {"bool": bool_query},
            "size": config.top_k,
        }


# ==================== 模块级便捷函数 ====================

_default_router: Optional[ScenarioRouter] = None


def get_scenario_router() -> ScenarioRouter:
    """获取场景路由器实例"""
    global _default_router
    if _default_router is None:
        _default_router = ScenarioRouter()
    return _default_router


def route_and_build_query(
    query: str,
    intent_result: IntentResult,
    entities: Dict[str, Any] = None,
) -> Tuple[RetrievalConfig, Dict[str, Any]]:
    """
    便捷函数：路由并构建查询
    
    Returns:
        (RetrievalConfig, OpenSearch 查询体)
    """
    router = get_scenario_router()
    config = router.route(intent_result, entities)
    os_query = router.build_opensearch_query(query, config)
    return config, os_query

