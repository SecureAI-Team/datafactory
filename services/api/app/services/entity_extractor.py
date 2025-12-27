"""
实体抽取服务
从文本中抽取产品、参数、场景等实体
"""
import os
import re
import json
import logging
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EntityType(str, Enum):
    """实体类型"""
    PRODUCT = "product"           # 产品/设备
    PARAMETER = "parameter"       # 参数/指标
    VALUE = "value"               # 数值
    UNIT = "unit"                 # 单位
    SCENARIO = "scenario"         # 场景/应用
    SOLUTION = "solution"         # 解决方案
    COMPANY = "company"           # 公司/品牌
    TECHNOLOGY = "technology"     # 技术/工艺
    MATERIAL = "material"         # 材料
    SPECIFICATION = "specification"  # 规格型号


@dataclass
class Entity:
    """抽取的实体"""
    text: str                     # 实体文本
    entity_type: EntityType       # 实体类型
    start: int = 0                # 起始位置
    end: int = 0                  # 结束位置
    normalized: str = ""          # 标准化名称
    confidence: float = 0.0       # 置信度
    attributes: Dict = field(default_factory=dict)  # 附加属性
    
    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "type": self.entity_type.value,
            "normalized": self.normalized or self.text,
            "confidence": self.confidence,
            "attributes": self.attributes,
        }


@dataclass
class ExtractionResult:
    """抽取结果"""
    entities: List[Entity] = field(default_factory=list)
    relations: List[Dict] = field(default_factory=list)
    raw_text: str = ""
    
    def get_entities_by_type(self, entity_type: EntityType) -> List[Entity]:
        return [e for e in self.entities if e.entity_type == entity_type]
    
    def to_dict(self) -> Dict:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relations": self.relations,
        }


class EntityExtractor:
    """实体抽取器"""
    
    # 产品关键词
    PRODUCT_PATTERNS = [
        r"(AOI|SPI|SMT|PCB|BGA|QFN|LED|LCD|OLED)[\s\-]?[设备检测仪机器系统]*",
        r"[激光光学视觉自动]检测[设备仪器系统机]*",
        r"贴片机|回流焊|印刷机|检测仪|测试机",
        r"[A-Z][A-Z0-9\-]+(?:\s*[型号])?",  # 型号
    ]
    
    # 参数关键词
    PARAMETER_PATTERNS = [
        r"(功率|电压|电流|频率|速度|精度|分辨率|产能|效率|良率)",
        r"(温度|湿度|压力|尺寸|重量|体积|面积)",
        r"(检测速度|识别率|误检率|漏检率)",
    ]
    
    # 数值+单位模式
    VALUE_UNIT_PATTERNS = [
        r"(\d+(?:\.\d+)?)\s*(W|kW|MW|瓦|千瓦)",
        r"(\d+(?:\.\d+)?)\s*(V|mV|kV|伏特?)",
        r"(\d+(?:\.\d+)?)\s*(A|mA|安培?)",
        r"(\d+(?:\.\d+)?)\s*(Hz|MHz|GHz|赫兹)",
        r"(\d+(?:\.\d+)?)\s*(mm|cm|m|毫米|厘米|米)",
        r"(\d+(?:\.\d+)?)\s*(kg|g|千克|克)",
        r"(\d+(?:\.\d+)?)\s*(℃|°C|度)",
        r"(\d+(?:\.\d+)?)\s*(%|百分比)",
        r"(\d+(?:\.\d+)?)\s*(pcs|片|个|台|件)(?:/[小时分秒hms])?",
        r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)",  # 尺寸
    ]
    
    # 场景关键词
    SCENARIO_KEYWORDS = {
        "smt_process": ["SMT", "贴片", "表面贴装", "回流焊", "印刷"],
        "aoi_inspection": ["AOI", "光学检测", "外观检查", "视觉检测", "缺陷检测"],
        "quality_control": ["质量控制", "品质管控", "良率", "不良品", "品检"],
        "production_line": ["产线", "生产线", "流水线", "自动化"],
    }
    
    # 公司/品牌
    COMPANY_PATTERNS = [
        r"(华为|中兴|比亚迪|富士康|台积电|联想|小米)",
        r"(Siemens|Panasonic|Sony|Samsung|Apple|Intel|AMD)",
        r"[A-Z][a-z]+(?:tech|tron|ics|soft)",
    ]
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则表达式"""
        self._product_re = [re.compile(p, re.IGNORECASE) for p in self.PRODUCT_PATTERNS]
        self._param_re = [re.compile(p) for p in self.PARAMETER_PATTERNS]
        self._value_re = [re.compile(p) for p in self.VALUE_UNIT_PATTERNS]
        self._company_re = [re.compile(p, re.IGNORECASE) for p in self.COMPANY_PATTERNS]
    
    def extract(self, text: str, use_llm: bool = False) -> ExtractionResult:
        """
        从文本中抽取实体
        
        Args:
            text: 输入文本
            use_llm: 是否使用 LLM 增强抽取
        
        Returns:
            ExtractionResult
        """
        result = ExtractionResult(raw_text=text)
        
        # 1. 规则抽取
        result.entities.extend(self._extract_products(text))
        result.entities.extend(self._extract_parameters(text))
        result.entities.extend(self._extract_values(text))
        result.entities.extend(self._extract_scenarios(text))
        result.entities.extend(self._extract_companies(text))
        
        # 2. LLM 增强（可选）
        if use_llm and self.llm_client:
            llm_entities = self._extract_with_llm(text)
            result.entities.extend(llm_entities)
        
        # 3. 去重和合并
        result.entities = self._deduplicate_entities(result.entities)
        
        return result
    
    def _extract_products(self, text: str) -> List[Entity]:
        """抽取产品实体"""
        entities = []
        
        for pattern in self._product_re:
            for match in pattern.finditer(text):
                entities.append(Entity(
                    text=match.group(),
                    entity_type=EntityType.PRODUCT,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.8,
                ))
        
        return entities
    
    def _extract_parameters(self, text: str) -> List[Entity]:
        """抽取参数实体"""
        entities = []
        
        for pattern in self._param_re:
            for match in pattern.finditer(text):
                entities.append(Entity(
                    text=match.group(),
                    entity_type=EntityType.PARAMETER,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.85,
                ))
        
        return entities
    
    def _extract_values(self, text: str) -> List[Entity]:
        """抽取数值和单位"""
        entities = []
        
        for pattern in self._value_re:
            for match in pattern.finditer(text):
                full_text = match.group()
                
                # 提取数值
                value = match.group(1)
                unit = match.group(2) if len(match.groups()) > 1 else ""
                
                entities.append(Entity(
                    text=full_text,
                    entity_type=EntityType.VALUE,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9,
                    attributes={"value": float(value), "unit": unit},
                ))
        
        return entities
    
    def _extract_scenarios(self, text: str) -> List[Entity]:
        """抽取场景实体"""
        entities = []
        text_lower = text.lower()
        
        for scenario_id, keywords in self.SCENARIO_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    # 找到关键词位置
                    idx = text_lower.find(keyword.lower())
                    entities.append(Entity(
                        text=keyword,
                        entity_type=EntityType.SCENARIO,
                        start=idx,
                        end=idx + len(keyword),
                        normalized=scenario_id,
                        confidence=0.75,
                    ))
                    break  # 每个场景只记录一次
        
        return entities
    
    def _extract_companies(self, text: str) -> List[Entity]:
        """抽取公司/品牌实体"""
        entities = []
        
        for pattern in self._company_re:
            for match in pattern.finditer(text):
                entities.append(Entity(
                    text=match.group(),
                    entity_type=EntityType.COMPANY,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.7,
                ))
        
        return entities
    
    def _extract_with_llm(self, text: str) -> List[Entity]:
        """使用 LLM 抽取实体"""
        if not self.llm_client:
            return []
        
        try:
            prompt = f"""请从以下文本中抽取实体。

文本：
{text}

请以 JSON 格式返回，格式如下：
```json
{{
  "entities": [
    {{"text": "实体文本", "type": "product/parameter/scenario/company/technology", "normalized": "标准化名称"}}
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
                
                entities = []
                for e in data.get("entities", []):
                    try:
                        entity_type = EntityType(e.get("type", "product"))
                    except ValueError:
                        entity_type = EntityType.PRODUCT
                    
                    entities.append(Entity(
                        text=e.get("text", ""),
                        entity_type=entity_type,
                        normalized=e.get("normalized", ""),
                        confidence=0.7,
                    ))
                
                return entities
                
        except Exception as e:
            logger.error(f"LLM entity extraction failed: {e}")
        
        return []
    
    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """去重实体"""
        seen: Set[str] = set()
        unique = []
        
        for entity in entities:
            key = f"{entity.entity_type.value}:{entity.text.lower()}"
            if key not in seen:
                seen.add(key)
                unique.append(entity)
        
        return unique
    
    def extract_from_ku(self, ku: Dict) -> ExtractionResult:
        """
        从知识单元中抽取实体
        
        Args:
            ku: 知识单元字典
        
        Returns:
            ExtractionResult
        """
        # 合并所有文本字段
        text_parts = [
            ku.get("title", ""),
            ku.get("summary", ""),
            ku.get("full_text", ""),
        ]
        
        if ku.get("key_points"):
            text_parts.extend(ku["key_points"])
        
        if ku.get("terms"):
            text_parts.extend(ku["terms"])
        
        full_text = "\n".join(text_parts)
        
        return self.extract(full_text)


# ==================== 模块级便捷函数 ====================

_default_extractor: Optional[EntityExtractor] = None


def get_entity_extractor(llm_client=None) -> EntityExtractor:
    """获取实体抽取器实例"""
    global _default_extractor
    if _default_extractor is None:
        _default_extractor = EntityExtractor(llm_client)
    return _default_extractor


def extract_entities(text: str, use_llm: bool = False) -> ExtractionResult:
    """便捷函数：抽取实体"""
    return get_entity_extractor().extract(text, use_llm)

