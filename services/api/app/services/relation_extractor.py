"""
关系抽取服务
从实体中抽取关系
"""
import os
import re
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .entity_extractor import Entity, EntityType, ExtractionResult

logger = logging.getLogger(__name__)


class RelationType(str, Enum):
    """关系类型"""
    HAS_PARAMETER = "has_parameter"       # 产品-参数
    HAS_VALUE = "has_value"               # 参数-值
    APPLIES_TO = "applies_to"             # 产品-场景
    SOLVED_BY = "solved_by"               # 场景-解决方案
    USES = "uses"                         # 解决方案-产品
    COMPETES_WITH = "competes_with"       # 产品-产品（竞品）
    PART_OF = "part_of"                   # 组件-产品
    MANUFACTURED_BY = "manufactured_by"   # 产品-公司
    REQUIRES = "requires"                 # 产品-技术
    SUCCEEDS = "succeeds"                 # 产品-产品（迭代）


@dataclass
class Relation:
    """抽取的关系"""
    source: Entity                    # 源实体
    target: Entity                    # 目标实体
    relation_type: RelationType       # 关系类型
    confidence: float = 0.0           # 置信度
    context: str = ""                 # 关系上下文
    attributes: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "relation": self.relation_type.value,
            "confidence": self.confidence,
            "context": self.context,
        }
    
    def to_triple(self) -> Tuple[str, str, str]:
        """转换为三元组"""
        return (
            self.source.normalized or self.source.text,
            self.relation_type.value,
            self.target.normalized or self.target.text,
        )


@dataclass
class RelationExtractionResult:
    """关系抽取结果"""
    relations: List[Relation] = field(default_factory=list)
    entities: List[Entity] = field(default_factory=list)
    
    def get_relations_by_type(self, rel_type: RelationType) -> List[Relation]:
        return [r for r in self.relations if r.relation_type == rel_type]
    
    def get_triples(self) -> List[Tuple[str, str, str]]:
        return [r.to_triple() for r in self.relations]
    
    def to_dict(self) -> Dict:
        return {
            "relations": [r.to_dict() for r in self.relations],
            "entity_count": len(self.entities),
            "relation_count": len(self.relations),
        }


class RelationExtractor:
    """关系抽取器"""
    
    # 关系模式
    RELATION_PATTERNS = {
        RelationType.HAS_PARAMETER: [
            (EntityType.PRODUCT, EntityType.PARAMETER, r"(?:的|具有|支持|配备)"),
        ],
        RelationType.HAS_VALUE: [
            (EntityType.PARAMETER, EntityType.VALUE, r"(?:为|是|达到|高达|约为)?"),
        ],
        RelationType.APPLIES_TO: [
            (EntityType.PRODUCT, EntityType.SCENARIO, r"(?:用于|适用于|应用于|在.+中)"),
        ],
        RelationType.MANUFACTURED_BY: [
            (EntityType.PRODUCT, EntityType.COMPANY, r"(?:由|出自|来自|是.+的产品)"),
        ],
    }
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def extract(
        self,
        text: str,
        entities: List[Entity] = None,
        use_llm: bool = False,
    ) -> RelationExtractionResult:
        """
        从文本和实体中抽取关系
        
        Args:
            text: 原文本
            entities: 已抽取的实体列表
            use_llm: 是否使用 LLM 增强
        
        Returns:
            RelationExtractionResult
        """
        result = RelationExtractionResult(entities=entities or [])
        
        if not entities:
            return result
        
        # 1. 基于规则抽取
        result.relations.extend(self._extract_by_rules(text, entities))
        
        # 2. 基于距离抽取（相邻实体）
        result.relations.extend(self._extract_by_proximity(text, entities))
        
        # 3. LLM 增强（可选）
        if use_llm and self.llm_client:
            llm_relations = self._extract_with_llm(text, entities)
            result.relations.extend(llm_relations)
        
        # 去重
        result.relations = self._deduplicate_relations(result.relations)
        
        return result
    
    def _extract_by_rules(self, text: str, entities: List[Entity]) -> List[Relation]:
        """基于规则抽取关系"""
        relations = []
        
        # 按类型分组实体
        entities_by_type: Dict[EntityType, List[Entity]] = {}
        for entity in entities:
            if entity.entity_type not in entities_by_type:
                entities_by_type[entity.entity_type] = []
            entities_by_type[entity.entity_type].append(entity)
        
        # 尝试匹配关系模式
        for rel_type, patterns in self.RELATION_PATTERNS.items():
            for source_type, target_type, pattern in patterns:
                sources = entities_by_type.get(source_type, [])
                targets = entities_by_type.get(target_type, [])
                
                for source in sources:
                    for target in targets:
                        if source == target:
                            continue
                        
                        # 检查实体间的文本是否匹配模式
                        if self._check_relation_context(text, source, target, pattern):
                            relations.append(Relation(
                                source=source,
                                target=target,
                                relation_type=rel_type,
                                confidence=0.75,
                            ))
        
        return relations
    
    def _check_relation_context(
        self,
        text: str,
        source: Entity,
        target: Entity,
        pattern: str,
    ) -> bool:
        """检查两个实体间的上下文是否匹配关系模式"""
        # 找到两个实体在文本中的位置
        source_idx = text.find(source.text)
        target_idx = text.find(target.text)
        
        if source_idx < 0 or target_idx < 0:
            return False
        
        # 获取两个实体之间的文本
        if source_idx < target_idx:
            between = text[source_idx + len(source.text):target_idx]
        else:
            between = text[target_idx + len(target.text):source_idx]
        
        # 检查距离（太远可能不相关）
        if len(between) > 50:
            return False
        
        # 检查是否匹配模式
        if re.search(pattern, between):
            return True
        
        # 距离很近也可能相关
        if len(between.strip()) < 10:
            return True
        
        return False
    
    def _extract_by_proximity(self, text: str, entities: List[Entity]) -> List[Relation]:
        """基于距离抽取关系（相邻实体可能相关）"""
        relations = []
        
        # 按在文本中的位置排序实体
        sorted_entities = sorted(entities, key=lambda e: text.find(e.text))
        
        for i in range(len(sorted_entities) - 1):
            current = sorted_entities[i]
            next_entity = sorted_entities[i + 1]
            
            # 检查相邻实体是否可以形成关系
            relation = self._infer_relation(current, next_entity)
            if relation:
                # 获取上下文
                start = max(0, text.find(current.text))
                end = min(len(text), text.find(next_entity.text) + len(next_entity.text))
                context = text[start:end]
                
                relation.context = context
                relations.append(relation)
        
        return relations
    
    def _infer_relation(self, source: Entity, target: Entity) -> Optional[Relation]:
        """推断两个实体间的关系"""
        type_pair = (source.entity_type, target.entity_type)
        
        # 定义类型对到关系的映射
        type_to_relation = {
            (EntityType.PRODUCT, EntityType.PARAMETER): RelationType.HAS_PARAMETER,
            (EntityType.PARAMETER, EntityType.VALUE): RelationType.HAS_VALUE,
            (EntityType.PRODUCT, EntityType.SCENARIO): RelationType.APPLIES_TO,
            (EntityType.PRODUCT, EntityType.COMPANY): RelationType.MANUFACTURED_BY,
            (EntityType.SCENARIO, EntityType.SOLUTION): RelationType.SOLVED_BY,
            (EntityType.SOLUTION, EntityType.PRODUCT): RelationType.USES,
        }
        
        if type_pair in type_to_relation:
            return Relation(
                source=source,
                target=target,
                relation_type=type_to_relation[type_pair],
                confidence=0.6,
            )
        
        # 反向也检查
        reverse_pair = (target.entity_type, source.entity_type)
        if reverse_pair in type_to_relation:
            return Relation(
                source=target,
                target=source,
                relation_type=type_to_relation[reverse_pair],
                confidence=0.6,
            )
        
        return None
    
    def _extract_with_llm(self, text: str, entities: List[Entity]) -> List[Relation]:
        """使用 LLM 抽取关系"""
        if not self.llm_client:
            return []
        
        try:
            entity_list = "\n".join([
                f"- {e.text} ({e.entity_type.value})"
                for e in entities
            ])
            
            prompt = f"""请从以下文本中抽取实体间的关系。

文本：
{text}

已识别的实体：
{entity_list}

关系类型包括：
- has_parameter: 产品具有参数
- has_value: 参数的值
- applies_to: 产品应用于场景
- manufactured_by: 产品由公司制造
- solved_by: 场景由解决方案解决
- uses: 解决方案使用产品

请以 JSON 格式返回：
```json
{{
  "relations": [
    {{"source": "源实体文本", "target": "目标实体文本", "relation": "关系类型"}}
  ]
}}
```

只返回 JSON，不要其他内容。"""

            response = self.llm_client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
            
            content = response.choices[0].message.content
            
            # 解析 JSON
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                data = json.loads(content[json_start:json_end])
                
                relations = []
                entity_map = {e.text.lower(): e for e in entities}
                
                for r in data.get("relations", []):
                    source_text = r.get("source", "").lower()
                    target_text = r.get("target", "").lower()
                    
                    if source_text in entity_map and target_text in entity_map:
                        try:
                            rel_type = RelationType(r.get("relation", "has_parameter"))
                        except ValueError:
                            continue
                        
                        relations.append(Relation(
                            source=entity_map[source_text],
                            target=entity_map[target_text],
                            relation_type=rel_type,
                            confidence=0.65,
                        ))
                
                return relations
                
        except Exception as e:
            logger.error(f"LLM relation extraction failed: {e}")
        
        return []
    
    def _deduplicate_relations(self, relations: List[Relation]) -> List[Relation]:
        """去重关系"""
        seen = set()
        unique = []
        
        for rel in relations:
            key = (
                rel.source.text.lower(),
                rel.relation_type.value,
                rel.target.text.lower(),
            )
            if key not in seen:
                seen.add(key)
                unique.append(rel)
        
        return unique


# ==================== 模块级便捷函数 ====================

_default_extractor: Optional[RelationExtractor] = None


def get_relation_extractor(llm_client=None) -> RelationExtractor:
    """获取关系抽取器实例"""
    global _default_extractor
    if _default_extractor is None:
        _default_extractor = RelationExtractor(llm_client)
    return _default_extractor


def extract_relations(
    text: str,
    entities: List[Entity] = None,
    use_llm: bool = False,
) -> RelationExtractionResult:
    """便捷函数：抽取关系"""
    return get_relation_extractor().extract(text, entities, use_llm)

