"""
参数提取器
从用户问题中提取结构化参数需求
支持：精确值、范围、比较运算、单位识别
"""
import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ParamOperator(str, Enum):
    """参数运算符"""
    EQ = "eq"           # 等于
    GT = "gt"           # 大于
    GTE = "gte"         # 大于等于
    LT = "lt"           # 小于
    LTE = "lte"         # 小于等于
    BETWEEN = "between" # 范围
    APPROX = "approx"   # 约等于/左右


@dataclass
class ExtractedParam:
    """提取的参数"""
    name: str                           # 参数名（如"功率"、"精度"）
    canonical_name: str                 # 标准化名称（如"power"、"precision"）
    value: float                        # 数值
    value_max: Optional[float] = None   # 范围最大值（用于 BETWEEN）
    unit: str = ""                      # 单位
    operator: ParamOperator = ParamOperator.EQ
    confidence: float = 1.0
    source_text: str = ""               # 原始文本片段
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "canonical_name": self.canonical_name,
            "value": self.value,
            "value_max": self.value_max,
            "unit": self.unit,
            "operator": self.operator.value,
            "confidence": self.confidence,
            "source_text": self.source_text,
        }


# ==================== 参数定义 ====================

# 参数名称映射（中文 -> 标准名）
PARAM_NAME_MAPPING = {
    # 功率相关
    "功率": "power",
    "power": "power",
    "瓦数": "power",
    "额定功率": "rated_power",
    "峰值功率": "peak_power",
    
    # 精度相关
    "精度": "precision",
    "accuracy": "precision",
    "检测精度": "detection_precision",
    "定位精度": "positioning_precision",
    "重复精度": "repeatability",
    
    # 产能/速度相关
    "产能": "capacity",
    "throughput": "capacity",
    "速度": "speed",
    "检测速度": "inspection_speed",
    "处理速度": "processing_speed",
    "节拍": "cycle_time",
    "takt": "cycle_time",
    "UPH": "uph",
    
    # 尺寸相关
    "尺寸": "size",
    "长度": "length",
    "宽度": "width",
    "高度": "height",
    "厚度": "thickness",
    "直径": "diameter",
    
    # 价格相关
    "价格": "price",
    "成本": "cost",
    "单价": "unit_price",
    "预算": "budget",
    
    # 重量相关
    "重量": "weight",
    "净重": "net_weight",
    
    # 分辨率相关
    "分辨率": "resolution",
    "像素": "pixels",
    
    # 温度相关
    "温度": "temperature",
    "工作温度": "operating_temperature",
    
    # 电压/电流
    "电压": "voltage",
    "电流": "current",
    
    # FOV 相关
    "视野": "fov",
    "FOV": "fov",
    "视场": "fov",
}

# 单位标准化映射
UNIT_NORMALIZATION = {
    # 功率
    "w": ("W", 1),
    "W": ("W", 1),
    "瓦": ("W", 1),
    "kw": ("W", 1000),
    "KW": ("W", 1000),
    "千瓦": ("W", 1000),
    
    # 长度
    "mm": ("mm", 1),
    "毫米": ("mm", 1),
    "um": ("um", 1),
    "μm": ("um", 1),
    "微米": ("um", 1),
    "cm": ("mm", 10),
    "厘米": ("mm", 10),
    "m": ("mm", 1000),
    "米": ("mm", 1000),
    
    # 速度/产能
    "片/小时": ("pcs/h", 1),
    "pcs/h": ("pcs/h", 1),
    "片/h": ("pcs/h", 1),
    "个/小时": ("pcs/h", 1),
    "件/小时": ("pcs/h", 1),
    "片/分钟": ("pcs/h", 60),
    "片/min": ("pcs/h", 60),
    "个/分钟": ("pcs/h", 60),
    "UPH": ("pcs/h", 1),
    
    # 时间
    "s": ("s", 1),
    "秒": ("s", 1),
    "ms": ("ms", 1),
    "毫秒": ("ms", 1),
    "min": ("s", 60),
    "分钟": ("s", 60),
    "h": ("s", 3600),
    "小时": ("s", 3600),
    
    # 重量
    "kg": ("kg", 1),
    "公斤": ("kg", 1),
    "千克": ("kg", 1),
    "g": ("kg", 0.001),
    "克": ("kg", 0.001),
    "t": ("kg", 1000),
    "吨": ("kg", 1000),
    
    # 价格
    "元": ("CNY", 1),
    "万": ("CNY", 10000),
    "万元": ("CNY", 10000),
    "k": ("CNY", 1000),
    "K": ("CNY", 1000),
    
    # 温度
    "℃": ("℃", 1),
    "°C": ("℃", 1),
    "度": ("℃", 1),
    
    # 电压
    "V": ("V", 1),
    "伏": ("V", 1),
    "kV": ("V", 1000),
    
    # 电流
    "A": ("A", 1),
    "安": ("A", 1),
    "mA": ("A", 0.001),
    
    # 像素
    "MP": ("MP", 1),
    "百万像素": ("MP", 1),
    "万像素": ("MP", 0.01),
}


# ==================== 提取模式 ====================

# 数值模式（支持整数、小数、科学计数法）
NUMBER_PATTERN = r"(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"

# 单位模式
UNIT_PATTERN = r"([a-zA-Z℃°]+|[瓦毫微厘米秒分钟小时千克公斤吨元万片个件度伏安]+(?:/[小时分钟hmin]+)?)"

# 运算符模式
OPERATOR_PATTERNS = {
    ParamOperator.GTE: [r">=", r"≥", r"大于等于", r"不低于", r"至少", r"最低", r"以上"],
    ParamOperator.LTE: [r"<=", r"≤", r"小于等于", r"不超过", r"最多", r"最高", r"以下", r"以内"],
    ParamOperator.GT: [r">", r"大于", r"超过", r"高于"],
    ParamOperator.LT: [r"<", r"小于", r"低于"],
    ParamOperator.APPROX: [r"约", r"大约", r"左右", r"上下", r"差不多"],
    ParamOperator.BETWEEN: [r"到", r"至", r"-", r"~", r"之间"],
}


class ParamExtractor:
    """参数提取器"""
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则模式"""
        # 参数名模式
        param_names = "|".join(re.escape(name) for name in PARAM_NAME_MAPPING.keys())
        self.param_name_pattern = re.compile(f"({param_names})", re.IGNORECASE)
        
        # 完整参数提取模式
        # 格式1: 参数名 + 运算符 + 数值 + 单位
        # 格式2: 数值 + 单位 + 参数名
        # 格式3: 参数名 + 数值 + 单位
        
        # 运算符合并
        all_ops = []
        for ops in OPERATOR_PATTERNS.values():
            all_ops.extend(ops)
        ops_pattern = "|".join(re.escape(op) for op in all_ops)
        
        # 主模式：参数名 [运算符] 数值 [单位]
        self.main_pattern = re.compile(
            rf"({param_names})\s*"  # 参数名
            rf"(?:(?:是|为|=|：|:)\s*)?"  # 可选的连接词
            rf"({ops_pattern})?\s*"  # 可选的运算符
            rf"{NUMBER_PATTERN}\s*"  # 数值
            rf"{UNIT_PATTERN}?"  # 可选单位
            rf"(?:\s*(?:到|至|-|~)\s*{NUMBER_PATTERN}\s*{UNIT_PATTERN}?)?"  # 可选范围
            , re.IGNORECASE
        )
        
        # 辅助模式：数值 + 单位（用于提取独立的参数值）
        self.value_unit_pattern = re.compile(
            rf"{NUMBER_PATTERN}\s*{UNIT_PATTERN}",
            re.IGNORECASE
        )
    
    def extract(self, text: str) -> List[ExtractedParam]:
        """从文本中提取参数"""
        params = []
        
        # 主模式匹配
        for match in self.main_pattern.finditer(text):
            param = self._parse_main_match(match, text)
            if param:
                params.append(param)
        
        # 如果主模式没有匹配，尝试更宽松的匹配
        if not params:
            params = self._extract_loose(text)
        
        # 去重
        params = self._deduplicate(params)
        
        return params
    
    def _parse_main_match(self, match: re.Match, text: str) -> Optional[ExtractedParam]:
        """解析主模式匹配结果"""
        groups = match.groups()
        
        param_name = groups[0]
        operator_str = groups[1] if len(groups) > 1 else None
        value_str = groups[2] if len(groups) > 2 else None
        unit_str = groups[3] if len(groups) > 3 else None
        value_max_str = groups[4] if len(groups) > 4 else None
        
        if not value_str:
            return None
        
        try:
            value = float(value_str)
        except ValueError:
            return None
        
        # 解析运算符
        operator = self._parse_operator(operator_str, text, match.start(), match.end())
        
        # 范围值
        value_max = None
        if value_max_str:
            try:
                value_max = float(value_max_str)
                operator = ParamOperator.BETWEEN
            except ValueError:
                pass
        
        # 标准化单位
        unit, multiplier = self._normalize_unit(unit_str)
        value *= multiplier
        if value_max:
            value_max *= multiplier
        
        # 标准化参数名
        canonical_name = PARAM_NAME_MAPPING.get(param_name.lower(), param_name.lower())
        
        return ExtractedParam(
            name=param_name,
            canonical_name=canonical_name,
            value=value,
            value_max=value_max,
            unit=unit,
            operator=operator,
            source_text=match.group(0),
        )
    
    def _parse_operator(
        self,
        operator_str: Optional[str],
        text: str,
        start: int,
        end: int
    ) -> ParamOperator:
        """解析运算符"""
        if operator_str:
            for op, patterns in OPERATOR_PATTERNS.items():
                for pattern in patterns:
                    if re.match(pattern, operator_str, re.IGNORECASE):
                        return op
        
        # 检查上下文中的运算符
        context = text[max(0, start-10):end+10]
        for op, patterns in OPERATOR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, context, re.IGNORECASE):
                    return op
        
        return ParamOperator.EQ
    
    def _normalize_unit(self, unit_str: Optional[str]) -> Tuple[str, float]:
        """标准化单位，返回 (标准单位, 乘数)"""
        if not unit_str:
            return "", 1.0
        
        unit_str = unit_str.strip()
        if unit_str in UNIT_NORMALIZATION:
            return UNIT_NORMALIZATION[unit_str]
        
        # 尝试小写匹配
        if unit_str.lower() in UNIT_NORMALIZATION:
            return UNIT_NORMALIZATION[unit_str.lower()]
        
        return unit_str, 1.0
    
    def _extract_loose(self, text: str) -> List[ExtractedParam]:
        """宽松模式提取"""
        params = []
        
        # 查找所有参数名
        param_names = list(self.param_name_pattern.finditer(text))
        
        # 查找所有数值+单位
        values = list(self.value_unit_pattern.finditer(text))
        
        # 尝试关联最近的参数名和数值
        for param_match in param_names:
            param_name = param_match.group(1)
            param_pos = param_match.start()
            
            # 找最近的数值
            closest_value = None
            min_distance = float('inf')
            
            for value_match in values:
                distance = abs(value_match.start() - param_pos)
                if distance < min_distance and distance < 20:  # 20字符以内
                    min_distance = distance
                    closest_value = value_match
            
            if closest_value:
                try:
                    value = float(closest_value.group(1))
                    unit_str = closest_value.group(2) if len(closest_value.groups()) > 1 else ""
                    unit, multiplier = self._normalize_unit(unit_str)
                    
                    canonical_name = PARAM_NAME_MAPPING.get(param_name.lower(), param_name.lower())
                    
                    # 检查上下文中的运算符
                    context = text[max(0, param_pos-15):closest_value.end()+5]
                    operator = self._parse_operator(None, context, 0, len(context))
                    
                    params.append(ExtractedParam(
                        name=param_name,
                        canonical_name=canonical_name,
                        value=value * multiplier,
                        unit=unit,
                        operator=operator,
                        confidence=0.7,  # 宽松匹配置信度较低
                        source_text=text[param_pos:closest_value.end()],
                    ))
                except ValueError:
                    continue
        
        return params
    
    def _deduplicate(self, params: List[ExtractedParam]) -> List[ExtractedParam]:
        """去重，保留置信度最高的"""
        seen = {}
        for param in params:
            key = (param.canonical_name, param.value)
            if key not in seen or param.confidence > seen[key].confidence:
                seen[key] = param
        return list(seen.values())
    
    def extract_requirements(self, text: str) -> Dict[str, Any]:
        """
        提取参数需求，返回可用于检索过滤的结构
        
        返回格式:
        {
            "params": [
                {"name": "power", "op": "gte", "value": 500, "unit": "W"},
                {"name": "precision", "op": "lte", "value": 0.1, "unit": "mm"},
            ],
            "keywords": ["AOI", "检测"],
        }
        """
        params = self.extract(text)
        
        result = {
            "params": [],
            "keywords": [],
        }
        
        for param in params:
            result["params"].append({
                "name": param.canonical_name,
                "op": param.operator.value,
                "value": param.value,
                "value_max": param.value_max,
                "unit": param.unit,
            })
        
        # 提取关键词（非参数部分）
        # 移除已匹配的参数文本
        remaining = text
        for param in params:
            remaining = remaining.replace(param.source_text, " ")
        
        # 提取关键词
        keywords = re.findall(r"[\u4e00-\u9fa5a-zA-Z]{2,}", remaining)
        # 过滤停用词
        stopwords = {"的", "是", "有", "在", "和", "与", "或", "要", "需要", "多少", "什么", "怎么", "如何"}
        result["keywords"] = [kw for kw in keywords if kw not in stopwords]
        
        return result


# ==================== 模块级便捷函数 ====================

_default_extractor: Optional[ParamExtractor] = None


def get_param_extractor() -> ParamExtractor:
    """获取参数提取器实例"""
    global _default_extractor
    if _default_extractor is None:
        _default_extractor = ParamExtractor()
    return _default_extractor


def extract_params(text: str) -> List[ExtractedParam]:
    """便捷函数：提取参数"""
    return get_param_extractor().extract(text)


def extract_param_requirements(text: str) -> Dict[str, Any]:
    """便捷函数：提取参数需求（用于检索）"""
    return get_param_extractor().extract_requirements(text)

