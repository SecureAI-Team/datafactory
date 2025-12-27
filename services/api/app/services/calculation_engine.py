"""
计算引擎
用于参数计算、选型推荐、规格校验
"""
import re
import math
import logging
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CalculationType(str, Enum):
    """计算类型"""
    CAPACITY = "capacity"          # 产能计算
    PRECISION = "precision"        # 精度校验
    ROI = "roi"                    # 投资回报
    DEVICE_COUNT = "device_count"  # 设备数量
    COST = "cost"                  # 成本计算
    COVERAGE = "coverage"          # 覆盖能力校验
    COMPARISON = "comparison"      # 规格对比


@dataclass
class CalculationInput:
    """计算输入"""
    name: str                      # 参数名
    value: Optional[float] = None  # 数值
    unit: Optional[str] = None     # 单位
    source: str = "user"           # 来源（user/context/default）


@dataclass
class CalculationResult:
    """计算结果"""
    calculation_type: CalculationType
    success: bool
    result_value: Optional[float] = None
    result_unit: Optional[str] = None
    result_text: str = ""
    reasoning: str = ""
    inputs_used: Dict[str, Any] = field(default_factory=dict)
    missing_inputs: List[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class CalculationRule:
    """计算规则"""
    name: str
    calculation_type: CalculationType
    triggers: List[str]            # 触发关键词
    required_inputs: List[str]     # 必需输入
    optional_inputs: List[str]     # 可选输入
    formula: str                   # 公式表达式或计算方法名
    output_template: str           # 输出模板
    default_values: Dict[str, float] = field(default_factory=dict)


# ==================== 计算规则库 ====================

CALCULATION_RULES = [
    # 设备数量估算
    CalculationRule(
        name="设备数量估算",
        calculation_type=CalculationType.DEVICE_COUNT,
        triggers=["需要几台", "要多少台", "配置几套", "配多少", "几台设备"],
        required_inputs=["需求产能"],
        optional_inputs=["单台产能", "冗余系数"],
        formula="device_count",
        output_template="根据您的产能需求 {需求产能}{产能单位}，建议配置 **{result}台** 设备",
        default_values={"单台产能": 3000, "冗余系数": 1.1},
    ),
    
    # 精度校验
    CalculationRule(
        name="精度校验",
        calculation_type=CalculationType.PRECISION,
        triggers=["能否检测", "能检测吗", "检得出", "能看到", "能发现"],
        required_inputs=["设备精度", "缺陷尺寸"],
        optional_inputs=["安全系数"],
        formula="precision_check",
        output_template="{result_text}",
        default_values={"安全系数": 0.3},
    ),
    
    # 单件成本计算
    CalculationRule(
        name="单件检测成本",
        calculation_type=CalculationType.COST,
        triggers=["成本多少", "检测一片多少钱", "单件成本"],
        required_inputs=["设备价格", "日产能"],
        optional_inputs=["使用年限", "年工作日"],
        formula="unit_cost",
        output_template="预估单件检测成本约 **{result}元/件**",
        default_values={"使用年限": 5, "年工作日": 250},
    ),
    
    # 投资回报周期
    CalculationRule(
        name="投资回报周期",
        calculation_type=CalculationType.ROI,
        triggers=["投资回报", "多久回本", "ROI", "回报周期"],
        required_inputs=["设备成本"],
        optional_inputs=["节省人力", "良率提升收益", "月工作日"],
        formula="roi_period",
        output_template="预计投资回报周期约 **{result}个月**",
        default_values={"节省人力": 8000, "良率提升收益": 5000, "月工作日": 22},
    ),
    
    # 产能匹配检查
    CalculationRule(
        name="产能匹配检查",
        calculation_type=CalculationType.CAPACITY,
        triggers=["能满足吗", "够用吗", "产能够不够"],
        required_inputs=["需求产能", "设备产能"],
        optional_inputs=[],
        formula="capacity_check",
        output_template="{result_text}",
        default_values={},
    ),
]


class CalculationEngine:
    """计算引擎"""
    
    def __init__(self):
        self.rules = {r.name: r for r in CALCULATION_RULES}
        
        # 参数标准化映射
        self.param_aliases = {
            "产能": ["需求产能", "日产能", "设备产能", "单台产能"],
            "精度": ["设备精度", "检测精度"],
            "尺寸": ["缺陷尺寸", "最小缺陷"],
            "价格": ["设备价格", "设备成本", "预算"],
            "功率": ["设备功率", "功耗"],
        }
    
    def detect_calculation_need(
        self,
        query: str,
        entities: Dict[str, Any] = None,
    ) -> Optional[CalculationRule]:
        """检测是否需要计算"""
        query_lower = query.lower()
        
        for rule in CALCULATION_RULES:
            for trigger in rule.triggers:
                if trigger in query_lower:
                    return rule
        
        return None
    
    def calculate(
        self,
        query: str,
        entities: Dict[str, Any] = None,
        context_params: Dict[str, Any] = None,
        retrieved_params: List[Dict] = None,
    ) -> Optional[CalculationResult]:
        """
        执行计算
        
        Args:
            query: 用户查询
            entities: 从查询中提取的实体
            context_params: 上下文中的参数
            retrieved_params: 检索到的参数
        
        Returns:
            CalculationResult 或 None
        """
        entities = entities or {}
        context_params = context_params or {}
        retrieved_params = retrieved_params or []
        
        # 检测计算类型
        rule = self.detect_calculation_need(query, entities)
        if not rule:
            return None
        
        logger.info(f"Calculation detected: {rule.name}")
        
        # 收集输入参数
        inputs = self._collect_inputs(
            rule,
            entities,
            context_params,
            retrieved_params,
            query,
        )
        
        # 检查必需参数
        missing = [
            param for param in rule.required_inputs
            if param not in inputs
        ]
        
        if missing:
            return CalculationResult(
                calculation_type=rule.calculation_type,
                success=False,
                result_text=f"需要更多信息来完成计算",
                reasoning=f"缺少参数: {', '.join(missing)}",
                missing_inputs=missing,
                inputs_used=inputs,
            )
        
        # 执行计算
        result = self._execute_calculation(rule, inputs)
        
        return result
    
    def _collect_inputs(
        self,
        rule: CalculationRule,
        entities: Dict,
        context_params: Dict,
        retrieved_params: List[Dict],
        query: str,
    ) -> Dict[str, CalculationInput]:
        """收集计算输入"""
        inputs = {}
        
        # 1. 从实体中收集
        for param_name in rule.required_inputs + rule.optional_inputs:
            # 直接匹配
            if param_name in entities:
                value = entities[param_name]
                if isinstance(value, dict):
                    inputs[param_name] = CalculationInput(
                        name=param_name,
                        value=value.get("value"),
                        unit=value.get("unit"),
                        source="user",
                    )
                else:
                    inputs[param_name] = CalculationInput(
                        name=param_name,
                        value=float(value) if value else None,
                        source="user",
                    )
            
            # 别名匹配
            for base_name, aliases in self.param_aliases.items():
                if param_name in aliases or param_name == base_name:
                    for alias in [base_name] + aliases:
                        if alias in entities and param_name not in inputs:
                            value = entities[alias]
                            if isinstance(value, dict):
                                inputs[param_name] = CalculationInput(
                                    name=param_name,
                                    value=value.get("value"),
                                    unit=value.get("unit"),
                                    source="user",
                                )
                            else:
                                inputs[param_name] = CalculationInput(
                                    name=param_name,
                                    value=float(value) if value else None,
                                    source="user",
                                )
                            break
        
        # 2. 从上下文中补充
        for param_name in rule.required_inputs + rule.optional_inputs:
            if param_name not in inputs and param_name in context_params:
                value = context_params[param_name]
                inputs[param_name] = CalculationInput(
                    name=param_name,
                    value=float(value) if value else None,
                    source="context",
                )
        
        # 3. 从检索结果中补充
        for param_name in rule.required_inputs + rule.optional_inputs:
            if param_name not in inputs:
                for param in retrieved_params:
                    if param.get("name") == param_name:
                        inputs[param_name] = CalculationInput(
                            name=param_name,
                            value=param.get("value"),
                            unit=param.get("unit"),
                            source="retrieved",
                        )
                        break
        
        # 4. 从查询中提取数值
        inputs = self._extract_from_query(rule, inputs, query)
        
        # 5. 使用默认值
        for param_name, default_value in rule.default_values.items():
            if param_name not in inputs:
                inputs[param_name] = CalculationInput(
                    name=param_name,
                    value=default_value,
                    source="default",
                )
        
        return inputs
    
    def _extract_from_query(
        self,
        rule: CalculationRule,
        inputs: Dict,
        query: str,
    ) -> Dict:
        """从查询中提取参数"""
        
        # 产能提取
        if "需求产能" not in inputs:
            match = re.search(r"(\d+)\s*(片|件|个)/\s*(小时|h)", query)
            if match:
                inputs["需求产能"] = CalculationInput(
                    name="需求产能",
                    value=float(match.group(1)),
                    unit="pcs/h",
                    source="user",
                )
        
        # 精度/尺寸提取
        if "缺陷尺寸" not in inputs:
            match = re.search(r"(\d+(?:\.\d+)?)\s*(mm|毫米)", query)
            if match:
                inputs["缺陷尺寸"] = CalculationInput(
                    name="缺陷尺寸",
                    value=float(match.group(1)),
                    unit="mm",
                    source="user",
                )
        
        # 价格提取
        if "设备价格" not in inputs and "设备成本" not in inputs:
            match = re.search(r"(\d+(?:\.\d+)?)\s*万", query)
            if match:
                inputs["设备价格"] = CalculationInput(
                    name="设备价格",
                    value=float(match.group(1)) * 10000,
                    unit="CNY",
                    source="user",
                )
        
        return inputs
    
    def _execute_calculation(
        self,
        rule: CalculationRule,
        inputs: Dict[str, CalculationInput],
    ) -> CalculationResult:
        """执行具体计算"""
        
        # 获取数值
        values = {k: v.value for k, v in inputs.items() if v.value is not None}
        
        try:
            if rule.formula == "device_count":
                result = self._calc_device_count(values)
            elif rule.formula == "precision_check":
                result = self._calc_precision_check(values)
            elif rule.formula == "unit_cost":
                result = self._calc_unit_cost(values)
            elif rule.formula == "roi_period":
                result = self._calc_roi_period(values)
            elif rule.formula == "capacity_check":
                result = self._calc_capacity_check(values)
            else:
                result = self._calc_generic(rule.formula, values)
            
            # 格式化输出
            output_text = self._format_output(rule.output_template, values, result)
            
            return CalculationResult(
                calculation_type=rule.calculation_type,
                success=True,
                result_value=result.get("value"),
                result_unit=result.get("unit"),
                result_text=output_text,
                reasoning=result.get("reasoning", ""),
                inputs_used={k: v.value for k, v in inputs.items()},
            )
            
        except Exception as e:
            logger.error(f"Calculation error: {e}")
            return CalculationResult(
                calculation_type=rule.calculation_type,
                success=False,
                result_text=f"计算过程出错",
                reasoning=str(e),
                inputs_used={k: v.value for k, v in inputs.items()},
            )
    
    def _calc_device_count(self, values: Dict) -> Dict:
        """计算设备数量"""
        demand = values.get("需求产能", 0)
        single_capacity = values.get("单台产能", 3000)
        redundancy = values.get("冗余系数", 1.1)
        
        if single_capacity <= 0:
            return {"value": 1, "reasoning": "单台产能数据缺失，假设需要1台"}
        
        raw_count = demand / single_capacity
        with_redundancy = raw_count * redundancy
        final_count = math.ceil(with_redundancy)
        
        reasoning = (
            f"需求产能 {demand}片/小时 ÷ 单台产能 {single_capacity}片/小时 "
            f"= {raw_count:.1f}台，考虑 {int((redundancy-1)*100)}% 冗余后 "
            f"≈ {final_count}台"
        )
        
        return {
            "value": final_count,
            "unit": "台",
            "reasoning": reasoning,
        }
    
    def _calc_precision_check(self, values: Dict) -> Dict:
        """精度校验"""
        device_precision = values.get("设备精度", 0.01)
        defect_size = values.get("缺陷尺寸", 0.1)
        safety_factor = values.get("安全系数", 0.3)
        
        # 一般规则：设备精度 <= 缺陷尺寸 * 安全系数
        required_precision = defect_size * safety_factor
        can_detect = device_precision <= required_precision
        
        if can_detect:
            result_text = (
                f"**可以检测**。设备精度 {device_precision}mm 满足 "
                f"{defect_size}mm 缺陷的检测需求（建议精度 ≤ {required_precision:.3f}mm）"
            )
        else:
            result_text = (
                f"**可能无法可靠检测**。设备精度 {device_precision}mm "
                f"对于 {defect_size}mm 的缺陷可能不够（建议精度 ≤ {required_precision:.3f}mm）"
            )
        
        return {
            "value": 1 if can_detect else 0,
            "result_text": result_text,
            "reasoning": f"检测能力 = 设备精度({device_precision}) vs 要求({required_precision:.3f})",
        }
    
    def _calc_unit_cost(self, values: Dict) -> Dict:
        """单件成本计算"""
        device_price = values.get("设备价格", 500000)
        daily_capacity = values.get("日产能", 20000)
        years = values.get("使用年限", 5)
        work_days = values.get("年工作日", 250)
        
        total_pieces = daily_capacity * work_days * years
        if total_pieces <= 0:
            return {"value": 0, "reasoning": "产能数据异常"}
        
        unit_cost = device_price / total_pieces
        
        reasoning = (
            f"设备成本 {device_price/10000:.1f}万 ÷ "
            f"({years}年 × {work_days}天/年 × {daily_capacity}件/天) "
            f"= {unit_cost:.4f}元/件"
        )
        
        return {
            "value": round(unit_cost, 4),
            "unit": "元/件",
            "reasoning": reasoning,
        }
    
    def _calc_roi_period(self, values: Dict) -> Dict:
        """投资回报周期计算"""
        device_cost = values.get("设备成本", values.get("设备价格", 500000))
        labor_saving = values.get("节省人力", 8000)
        yield_benefit = values.get("良率提升收益", 5000)
        
        monthly_benefit = labor_saving + yield_benefit
        if monthly_benefit <= 0:
            return {"value": 0, "reasoning": "收益数据异常"}
        
        roi_months = device_cost / monthly_benefit
        
        reasoning = (
            f"设备成本 {device_cost/10000:.1f}万 ÷ "
            f"月收益 ({labor_saving}人力 + {yield_benefit}良率) = {roi_months:.1f}个月"
        )
        
        return {
            "value": round(roi_months, 1),
            "unit": "月",
            "reasoning": reasoning,
        }
    
    def _calc_capacity_check(self, values: Dict) -> Dict:
        """产能匹配检查"""
        demand = values.get("需求产能", 0)
        supply = values.get("设备产能", 0)
        
        if supply <= 0:
            return {
                "value": 0,
                "result_text": "需要知道设备的产能参数才能判断",
            }
        
        ratio = supply / demand if demand > 0 else float('inf')
        
        if ratio >= 1.2:
            result_text = f"**完全满足**。设备产能 {supply}片/小时 超出需求 {int((ratio-1)*100)}%"
        elif ratio >= 1.0:
            result_text = f"**刚好满足**。设备产能 {supply}片/小时 与需求相当，建议增加冗余"
        else:
            result_text = f"**无法满足**。设备产能 {supply}片/小时 仅能满足需求的 {int(ratio*100)}%"
        
        return {
            "value": ratio,
            "result_text": result_text,
            "reasoning": f"产能比 = {supply} / {demand} = {ratio:.2f}",
        }
    
    def _calc_generic(self, formula: str, values: Dict) -> Dict:
        """通用公式计算"""
        try:
            result = eval(formula, {"__builtins__": {}}, values)
            return {"value": result}
        except Exception as e:
            return {"value": None, "reasoning": f"公式计算失败: {e}"}
    
    def _format_output(
        self,
        template: str,
        values: Dict,
        result: Dict,
    ) -> str:
        """格式化输出"""
        output = template
        
        # 替换结果
        if "result" in result:
            output = output.replace("{result}", str(result.get("value", "")))
        if "result_text" in result:
            output = output.replace("{result_text}", result["result_text"])
        
        # 替换输入值
        for key, value in values.items():
            output = output.replace(f"{{{key}}}", str(value))
        
        # 补充单位
        output = output.replace("{产能单位}", "片/小时")
        
        return output
    
    def format_calculation_response(
        self,
        result: CalculationResult,
        include_reasoning: bool = True,
    ) -> str:
        """格式化计算响应"""
        lines = []
        
        lines.append("### 📊 计算结果\n")
        lines.append(result.result_text)
        
        if include_reasoning and result.reasoning:
            lines.append(f"\n**计算依据**：{result.reasoning}")
        
        if result.inputs_used:
            lines.append("\n**使用参数**：")
            for k, v in result.inputs_used.items():
                if v is not None:
                    lines.append(f"- {k}: {v}")
        
        if result.missing_inputs:
            lines.append(f"\n⚠️ 如需更精确计算，请提供：{', '.join(result.missing_inputs)}")
        
        return "\n".join(lines)


# ==================== 规格比对功能 ====================

@dataclass
class ComparisonItem:
    """比对项"""
    name: str
    value: Any
    unit: str = ""
    better_direction: str = "higher"  # higher/lower/neutral


@dataclass
class ComparisonResult:
    """比对结果"""
    success: bool
    products: List[Dict] = field(default_factory=list)
    comparison_table: Dict[str, Dict] = field(default_factory=dict)
    summary: str = ""
    recommendation: str = ""


class SpecComparator:
    """规格比对器"""
    
    # 参数比较方向（higher=越高越好，lower=越低越好）
    PARAM_DIRECTIONS = {
        "power": "lower",         # 功耗越低越好
        "precision": "lower",     # 精度越小越好
        "capacity": "higher",     # 产能越高越好
        "speed": "higher",        # 速度越高越好
        "price": "lower",         # 价格越低越好
        "cost": "lower",          # 成本越低越好
        "resolution": "higher",   # 分辨率越高越好
        "fov": "higher",          # 视野越大越好
        "weight": "lower",        # 重量越轻越好
        "accuracy": "higher",     # 准确度越高越好
    }
    
    def compare(
        self,
        products: List[Dict],
        param_names: List[str] = None,
        weights: Dict[str, float] = None,
    ) -> ComparisonResult:
        """
        比较多个产品/方案的规格
        
        Args:
            products: 产品列表，每个产品包含 name 和 params
            param_names: 要比较的参数列表
            weights: 参数权重
        
        Returns:
            ComparisonResult
        """
        if len(products) < 2:
            return ComparisonResult(
                success=False,
                summary="需要至少两个产品进行比对",
            )
        
        weights = weights or {}
        
        # 收集所有参数
        all_params = set()
        for prod in products:
            for param in prod.get("params", []):
                all_params.add(param.get("name", ""))
        
        if param_names:
            all_params = all_params.intersection(set(param_names))
        
        # 构建比对表
        comparison_table = {}
        scores = {prod["name"]: 0 for prod in products}
        
        for param_name in all_params:
            comparison_table[param_name] = {}
            values = []
            
            for prod in products:
                prod_name = prod["name"]
                param_value = None
                param_unit = ""
                
                for param in prod.get("params", []):
                    if param.get("name") == param_name:
                        param_value = param.get("value")
                        param_unit = param.get("unit", "")
                        break
                
                comparison_table[param_name][prod_name] = {
                    "value": param_value,
                    "unit": param_unit,
                }
                
                if param_value is not None:
                    values.append((prod_name, param_value))
            
            # 确定最佳值
            if values:
                direction = self.PARAM_DIRECTIONS.get(param_name, "higher")
                sorted_values = sorted(values, key=lambda x: x[1], reverse=(direction == "higher"))
                best_prod = sorted_values[0][0]
                worst_prod = sorted_values[-1][0]
                
                comparison_table[param_name]["_best"] = best_prod
                comparison_table[param_name]["_worst"] = worst_prod
                comparison_table[param_name]["_direction"] = direction
                
                # 更新分数
                weight = weights.get(param_name, 1.0)
                scores[best_prod] += weight
                if len(sorted_values) > 1:
                    scores[worst_prod] -= weight * 0.5
        
        # 生成摘要
        winner = max(scores.items(), key=lambda x: x[1])[0]
        
        summary_parts = []
        for param_name, data in comparison_table.items():
            best = data.get("_best")
            direction = data.get("_direction", "higher")
            if best:
                direction_text = "最高" if direction == "higher" else "最低"
                best_value = data.get(best, {}).get("value")
                unit = data.get(best, {}).get("unit", "")
                summary_parts.append(f"- **{param_name}**: {best} {direction_text} ({best_value}{unit})")
        
        summary = "\n".join(summary_parts)
        recommendation = f"综合比较，**{winner}** 在多项指标上表现更优"
        
        return ComparisonResult(
            success=True,
            products=[{"name": p["name"], "score": scores[p["name"]]} for p in products],
            comparison_table=comparison_table,
            summary=summary,
            recommendation=recommendation,
        )
    
    def format_comparison_response(self, result: ComparisonResult) -> str:
        """格式化比对响应"""
        if not result.success:
            return result.summary
        
        lines = ["### 📊 规格比对\n"]
        
        # 比对表（Markdown）
        if result.products and result.comparison_table:
            # 表头
            prod_names = [p["name"] for p in result.products]
            header = "| 参数 | " + " | ".join(prod_names) + " |"
            separator = "|" + "|".join(["---"] * (len(prod_names) + 1)) + "|"
            lines.append(header)
            lines.append(separator)
            
            # 数据行
            for param_name, data in result.comparison_table.items():
                row = f"| {param_name} |"
                best = data.get("_best")
                for prod_name in prod_names:
                    cell_data = data.get(prod_name, {})
                    value = cell_data.get("value", "-")
                    unit = cell_data.get("unit", "")
                    cell = f" {value}{unit}"
                    if prod_name == best:
                        cell = f" **{value}{unit}** ✓"
                    row += cell + " |"
                lines.append(row)
            
            lines.append("")
        
        if result.summary:
            lines.append("**各项最优**：")
            lines.append(result.summary)
            lines.append("")
        
        if result.recommendation:
            lines.append(f"**结论**：{result.recommendation}")
        
        return "\n".join(lines)


# ==================== 模块级便捷函数 ====================

_default_engine: Optional[CalculationEngine] = None
_default_comparator: Optional[SpecComparator] = None


def get_calculation_engine() -> CalculationEngine:
    """获取计算引擎实例"""
    global _default_engine
    if _default_engine is None:
        _default_engine = CalculationEngine()
    return _default_engine


def get_spec_comparator() -> SpecComparator:
    """获取规格比对器实例"""
    global _default_comparator
    if _default_comparator is None:
        _default_comparator = SpecComparator()
    return _default_comparator


def try_calculate(
    query: str,
    entities: Dict[str, Any] = None,
    context_params: Dict[str, Any] = None,
    retrieved_params: List[Dict] = None,
) -> Optional[CalculationResult]:
    """便捷函数：尝试执行计算"""
    engine = get_calculation_engine()
    return engine.calculate(query, entities, context_params, retrieved_params)


def calculate_with_extraction(
    query: str,
    context_params: Dict[str, Any] = None,
    retrieved_params: List[Dict] = None,
) -> Optional[CalculationResult]:
    """
    便捷函数：自动提取参数并执行计算
    
    从查询中自动提取参数，然后尝试执行计算
    """
    from .param_extractor import extract_params
    
    # 提取参数
    extracted = extract_params(query)
    
    # 转换为 entities 格式
    entities = {}
    for param in extracted:
        entities[param.canonical_name] = {
            "value": param.value,
            "unit": param.unit,
            "operator": param.operator.value,
        }
        # 也添加中文名
        entities[param.name] = entities[param.canonical_name]
    
    return try_calculate(query, entities, context_params, retrieved_params)


def compare_specs(
    products: List[Dict],
    param_names: List[str] = None,
) -> ComparisonResult:
    """便捷函数：规格比对"""
    return get_spec_comparator().compare(products, param_names)


def format_calculation_for_chat(
    result: CalculationResult,
    include_reasoning: bool = True,
) -> str:
    """便捷函数：格式化计算结果供聊天使用"""
    return get_calculation_engine().format_calculation_response(result, include_reasoning)


def format_comparison_for_chat(result: ComparisonResult) -> str:
    """便捷函数：格式化比对结果供聊天使用"""
    return get_spec_comparator().format_comparison_response(result)

