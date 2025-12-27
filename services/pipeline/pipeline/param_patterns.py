"""
参数提取正则规则库
用于从文档中提取结构化参数（性能、规格、价格等）
"""
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ExtractedParam:
    """提取的参数"""
    name: str
    value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    unit: str = ""
    param_type: str = "spec"  # performance, spec, price, scope
    raw_text: str = ""


# 单位标准化映射
UNIT_NORMALIZATION = {
    # 功率
    "W": "W", "瓦": "W", "w": "W",
    "kW": "kW", "千瓦": "kW", "kw": "kW", "KW": "kW",
    # 精度/尺寸
    "μm": "μm", "um": "μm", "微米": "μm",
    "mm": "mm", "毫米": "mm", "MM": "mm",
    "cm": "cm", "厘米": "cm",
    "m": "m", "米": "m",
    # 产能
    "片/小时": "pcs/h", "pcs/h": "pcs/h", "PCS/H": "pcs/h",
    "片/分钟": "pcs/min", "pcs/min": "pcs/min",
    "UPH": "pcs/h", "uph": "pcs/h",
    # 价格
    "万": "万CNY", "万元": "万CNY",
    "元": "CNY", "RMB": "CNY", "CNY": "CNY", "￥": "CNY",
    # 时间
    "秒": "s", "s": "s", "S": "s",
    "ms": "ms", "毫秒": "ms", "MS": "ms",
    "分钟": "min", "min": "min", "分": "min",
    "小时": "h", "h": "h", "H": "h",
    # 频率
    "Hz": "Hz", "hz": "Hz", "赫兹": "Hz",
    "MHz": "MHz", "mhz": "MHz",
    "GHz": "GHz", "ghz": "GHz",
    # 存储
    "GB": "GB", "gb": "GB", "G": "GB",
    "TB": "TB", "tb": "TB", "T": "TB",
    "MB": "MB", "mb": "MB", "M": "MB",
    # 重量
    "kg": "kg", "KG": "kg", "公斤": "kg", "千克": "kg",
    "g": "g", "克": "g",
    # 电压电流
    "V": "V", "伏": "V", "v": "V",
    "A": "A", "安": "A", "a": "A",
    "mA": "mA", "毫安": "mA",
}

# 参数名称标准化映射
PARAM_NAME_NORMALIZATION = {
    # 精度相关
    "精度": "检测精度", "检测精度": "检测精度", "定位精度": "定位精度",
    "分辨率": "分辨率", "解析度": "分辨率",
    "重复精度": "重复精度", "重复定位精度": "重复精度",
    # 速度相关
    "速度": "检测速度", "检测速度": "检测速度",
    "产能": "产能", "产量": "产能", "UPH": "产能",
    "节拍": "节拍时间", "节拍时间": "节拍时间", "CT": "节拍时间",
    # 功率相关
    "功率": "功率", "额定功率": "功率", "消耗功率": "功率",
    # 尺寸相关
    "尺寸": "外形尺寸", "外形尺寸": "外形尺寸", "设备尺寸": "外形尺寸",
    "FOV": "视场", "视场": "视场", "视野": "视场",
    "工作距离": "工作距离", "WD": "工作距离",
    # 价格相关
    "价格": "价格", "售价": "价格", "单价": "价格", "报价": "价格",
    "成本": "成本", "费用": "成本",
    # 其他
    "重量": "重量", "净重": "重量",
    "电压": "工作电压", "工作电压": "工作电压", "输入电压": "工作电压",
}

# 参数类型推断
PARAM_TYPE_KEYWORDS = {
    "performance": ["精度", "速度", "产能", "分辨率", "节拍", "效率", "准确率"],
    "spec": ["尺寸", "重量", "电压", "功率", "FOV", "视场", "工作距离"],
    "price": ["价格", "成本", "费用", "报价", "售价", "预算"],
    "scope": ["范围", "适用", "支持"],
}

# 正则模式定义
PARAM_PATTERNS = [
    # 格式: (模式, 参数名提取组, 数值提取组, 单位提取组, 类型)
    
    # 精确数值: "精度0.01mm" 或 "检测精度：0.01mm"
    (r'(精度|分辨率|检测精度|定位精度)[：:≤≥<>]?\s*(\d+\.?\d*)\s*(μm|um|mm|毫米|微米)', 1, 2, 3, "performance"),
    
    # 功率: "功率200W" 或 "200W功率"
    (r'(功率|额定功率)[：:]?\s*(\d+\.?\d*)\s*(W|kW|瓦|千瓦)', 1, 2, 3, "spec"),
    (r'(\d+\.?\d*)\s*(W|kW|瓦|千瓦)\s*(功率)?', None, 1, 2, "spec"),
    
    # 产能: "产能3000片/小时" 或 "3000pcs/h"
    (r'(产能|产量|UPH)[：:]?\s*(\d+\.?\d*)\s*(片/小时|pcs/h|PCS/H|UPH)', 1, 2, 3, "performance"),
    (r'(\d+\.?\d*)\s*(片/小时|pcs/h|PCS/H)\s*(产能|产量)?', None, 1, 2, "performance"),
    
    # 速度: "速度1秒/件" 或 "节拍2s"
    (r'(速度|节拍|CT)[：:]?\s*(\d+\.?\d*)\s*(秒|s|ms|毫秒)', 1, 2, 3, "performance"),
    
    # 价格: "价格50万" 或 "50万元"
    (r'(价格|成本|售价|报价)[：:]?\s*(\d+\.?\d*)\s*(万|万元|元|CNY)', 1, 2, 3, "price"),
    (r'(\d+\.?\d*)\s*(万|万元)\s*(元)?', None, 1, 2, "price"),
    
    # FOV/视场: "FOV 100mm"
    (r'(FOV|视场|视野)[：:]?\s*(\d+\.?\d*)\s*(mm|毫米|cm|厘米)', 1, 2, 3, "spec"),
    
    # 工作距离: "工作距离150mm"
    (r'(工作距离|WD)[：:]?\s*(\d+\.?\d*)\s*(mm|毫米|cm|厘米)', 1, 2, 3, "spec"),
    
    # 电压: "工作电压220V"
    (r'(电压|工作电压|输入电压)[：:]?\s*(\d+\.?\d*)\s*(V|伏)', 1, 2, 3, "spec"),
    
    # 重量: "重量50kg"
    (r'(重量|净重)[：:]?\s*(\d+\.?\d*)\s*(kg|g|公斤|克)', 1, 2, 3, "spec"),
    
    # 频率: "频率60Hz"
    (r'(频率)[：:]?\s*(\d+\.?\d*)\s*(Hz|MHz|GHz)', 1, 2, 3, "spec"),
]

# 范围模式
RANGE_PATTERNS = [
    # "精度0.01-0.05mm" 或 "0.01~0.05mm"
    (r'(精度|分辨率|范围)[：:]?\s*(\d+\.?\d*)\s*[-~至到]\s*(\d+\.?\d*)\s*(μm|um|mm|毫米|微米)', 1, 2, 3, 4),
    # "价格30-50万"
    (r'(价格|成本|预算)[：:]?\s*(\d+\.?\d*)\s*[-~至到]\s*(\d+\.?\d*)\s*(万|万元)', 1, 2, 3, 4),
    # "产能2000-3000片/小时"
    (r'(产能|产量)[：:]?\s*(\d+\.?\d*)\s*[-~至到]\s*(\d+\.?\d*)\s*(片/小时|pcs/h)', 1, 2, 3, 4),
]


def normalize_unit(unit: str) -> str:
    """标准化单位"""
    return UNIT_NORMALIZATION.get(unit, unit)


def normalize_param_name(name: str) -> str:
    """标准化参数名称"""
    return PARAM_NAME_NORMALIZATION.get(name, name)


def infer_param_type(name: str) -> str:
    """推断参数类型"""
    for ptype, keywords in PARAM_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                return ptype
    return "spec"


def extract_params_from_text(text: str) -> List[ExtractedParam]:
    """
    从文本中提取结构化参数
    
    Args:
        text: 输入文本
        
    Returns:
        提取的参数列表
    """
    params = []
    seen = set()  # 避免重复
    
    # 提取精确值参数
    for pattern, name_group, value_group, unit_group, ptype in PARAM_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                # 提取参数名
                if name_group is not None:
                    raw_name = match.group(name_group)
                    name = normalize_param_name(raw_name)
                else:
                    # 从单位推断参数名
                    unit = match.group(unit_group)
                    if unit in ["W", "kW", "瓦", "千瓦"]:
                        name = "功率"
                    elif unit in ["片/小时", "pcs/h", "PCS/H"]:
                        name = "产能"
                    elif unit in ["万", "万元"]:
                        name = "价格"
                    else:
                        name = "未知参数"
                
                # 提取数值
                value = float(match.group(value_group))
                
                # 提取并标准化单位
                raw_unit = match.group(unit_group)
                unit = normalize_unit(raw_unit)
                
                # 价格单位转换（万 -> 元）
                if "万" in raw_unit and name == "价格":
                    value = value * 10000
                    unit = "CNY"
                
                # 去重key
                key = f"{name}:{value}:{unit}"
                if key in seen:
                    continue
                seen.add(key)
                
                param = ExtractedParam(
                    name=name,
                    value=value,
                    unit=unit,
                    param_type=ptype or infer_param_type(name),
                    raw_text=match.group(0)
                )
                params.append(param)
                
            except (IndexError, ValueError) as e:
                continue
    
    # 提取范围值参数
    for pattern, name_group, min_group, max_group, unit_group in RANGE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                raw_name = match.group(name_group)
                name = normalize_param_name(raw_name)
                min_val = float(match.group(min_group))
                max_val = float(match.group(max_group))
                raw_unit = match.group(unit_group)
                unit = normalize_unit(raw_unit)
                
                # 价格单位转换
                if "万" in raw_unit and name == "价格":
                    min_val = min_val * 10000
                    max_val = max_val * 10000
                    unit = "CNY"
                
                key = f"{name}:range:{min_val}-{max_val}:{unit}"
                if key in seen:
                    continue
                seen.add(key)
                
                param = ExtractedParam(
                    name=name,
                    min_value=min_val,
                    max_value=max_val,
                    unit=unit,
                    param_type=infer_param_type(name),
                    raw_text=match.group(0)
                )
                params.append(param)
                
            except (IndexError, ValueError):
                continue
    
    return params


def params_to_dict(params: List[ExtractedParam]) -> List[Dict[str, Any]]:
    """
    将参数列表转换为字典格式（用于JSON序列化）
    """
    result = []
    for p in params:
        d = {
            "name": p.name,
            "unit": p.unit,
            "type": p.param_type,
        }
        if p.value is not None:
            d["value"] = p.value
        if p.min_value is not None:
            d["min"] = p.min_value
        if p.max_value is not None:
            d["max"] = p.max_value
        result.append(d)
    return result


# 测试代码
if __name__ == "__main__":
    test_texts = [
        "该设备检测精度0.01mm，产能3000片/小时，功率200W",
        "价格50万元，工作电压220V，重量150kg",
        "分辨率5μm，FOV 100mm，工作距离150mm",
        "精度范围0.01-0.05mm，价格30-50万",
        "产能2000-3000pcs/h，节拍时间2秒",
    ]
    
    for text in test_texts:
        print(f"\n输入: {text}")
        params = extract_params_from_text(text)
        for p in params:
            print(f"  - {p.name}: {p.value or f'{p.min_value}-{p.max_value}'} {p.unit} ({p.param_type})")

