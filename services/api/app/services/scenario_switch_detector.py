"""
场景切换检测器
识别用户话题转换，并处理上下文切换
"""
import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SwitchType(str, Enum):
    """切换类型"""
    NONE = "none"                     # 无切换
    TOPIC_SHIFT = "topic_shift"       # 话题偏移（同场景内）
    SCENARIO_SWITCH = "scenario_switch"  # 场景切换（跨场景）
    CLARIFICATION = "clarification"   # 澄清/补充（对上一轮的补充）
    FOLLOW_UP = "follow_up"           # 追问（深入上一话题）
    NEW_SESSION = "new_session"       # 新会话开始


@dataclass
class SwitchDetectionResult:
    """切换检测结果"""
    switch_type: SwitchType
    confidence: float
    previous_scenario: Optional[str] = None
    new_scenario: Optional[str] = None
    should_clear_context: bool = False
    should_summarize_previous: bool = False
    transition_message: str = ""
    reasoning: str = ""


# 切换信号关键词
SWITCH_SIGNALS = {
    # 明确的话题切换信号
    "explicit_switch": [
        "换个话题", "另外", "还有一个问题", "顺便问一下",
        "说到另一个", "除此之外", "还想问", "再问一个",
        "换一个问题", "其他方面", "关于其他",
    ],
    
    # 回到之前话题
    "return_previous": [
        "回到刚才", "刚才说的", "之前的问题", "前面提到",
        "还是那个", "继续刚才", "接着刚才",
    ],
    
    # 澄清/补充信号
    "clarification": [
        "我的意思是", "补充一下", "我想说的是", "不是这个",
        "我指的是", "具体来说", "更准确地说",
    ],
    
    # 追问信号
    "follow_up": [
        "那么", "那", "这个", "这种情况", "如果是这样",
        "具体怎么", "能详细说说", "展开说说",
    ],
    
    # 新会话信号
    "new_session": [
        "你好", "开始", "新问题", "请问",
    ],
}

# 场景相关关键词（用于检测场景切换）
SCENARIO_KEYWORDS = {
    "aoi_inspection": ["AOI", "检测", "光学检测", "外观检查", "缺陷检测"],
    "smt_process": ["SMT", "贴片", "回流焊", "印刷", "贴装"],
    "quality_control": ["质量", "品质", "良率", "不良", "缺陷率"],
    "equipment_selection": ["选型", "采购", "设备", "配置", "推荐"],
    "cost_analysis": ["成本", "价格", "预算", "ROI", "投资"],
    "technical_support": ["故障", "问题", "维修", "报错", "异常"],
}


class ScenarioSwitchDetector:
    """场景切换检测器"""
    
    def __init__(self):
        self.scenario_keywords = SCENARIO_KEYWORDS
        self.switch_signals = SWITCH_SIGNALS
    
    def detect(
        self,
        current_query: str,
        previous_queries: List[str] = None,
        current_scenario: str = None,
        context_entities: Dict[str, Any] = None,
    ) -> SwitchDetectionResult:
        """
        检测场景切换
        
        Args:
            current_query: 当前用户查询
            previous_queries: 之前的查询列表
            current_scenario: 当前场景ID
            context_entities: 上下文中的实体
        
        Returns:
            SwitchDetectionResult
        """
        previous_queries = previous_queries or []
        context_entities = context_entities or {}
        
        # 1. 检测明确的切换信号
        explicit_switch = self._detect_explicit_switch(current_query)
        if explicit_switch:
            return explicit_switch
        
        # 2. 检测澄清/补充
        if self._is_clarification(current_query, previous_queries):
            return SwitchDetectionResult(
                switch_type=SwitchType.CLARIFICATION,
                confidence=0.8,
                should_clear_context=False,
                reasoning="检测到澄清或补充信号",
            )
        
        # 3. 检测追问
        if self._is_follow_up(current_query, previous_queries):
            return SwitchDetectionResult(
                switch_type=SwitchType.FOLLOW_UP,
                confidence=0.7,
                should_clear_context=False,
                reasoning="检测到追问信号",
            )
        
        # 4. 检测场景切换（基于关键词）
        detected_scenario = self._detect_scenario(current_query)
        if detected_scenario and current_scenario and detected_scenario != current_scenario:
            return SwitchDetectionResult(
                switch_type=SwitchType.SCENARIO_SWITCH,
                confidence=0.75,
                previous_scenario=current_scenario,
                new_scenario=detected_scenario,
                should_clear_context=False,  # 不完全清除，但标记切换
                should_summarize_previous=True,
                transition_message=f"好的，我们来讨论{self._get_scenario_name(detected_scenario)}相关的问题。",
                reasoning=f"从 {current_scenario} 切换到 {detected_scenario}",
            )
        
        # 5. 检测话题偏移（同场景内的话题变化）
        if previous_queries and self._is_topic_shift(current_query, previous_queries[-1]):
            return SwitchDetectionResult(
                switch_type=SwitchType.TOPIC_SHIFT,
                confidence=0.6,
                should_clear_context=False,
                reasoning="同场景内话题偏移",
            )
        
        # 6. 无切换
        return SwitchDetectionResult(
            switch_type=SwitchType.NONE,
            confidence=0.9,
            should_clear_context=False,
            reasoning="未检测到场景切换",
        )
    
    def _detect_explicit_switch(self, query: str) -> Optional[SwitchDetectionResult]:
        """检测明确的切换信号"""
        query_lower = query.lower()
        
        # 明确的话题切换
        for signal in self.switch_signals["explicit_switch"]:
            if signal in query_lower:
                return SwitchDetectionResult(
                    switch_type=SwitchType.SCENARIO_SWITCH,
                    confidence=0.9,
                    should_clear_context=False,
                    should_summarize_previous=True,
                    transition_message="好的，让我们来看这个新问题。",
                    reasoning=f"检测到明确切换信号: {signal}",
                )
        
        # 回到之前话题
        for signal in self.switch_signals["return_previous"]:
            if signal in query_lower:
                return SwitchDetectionResult(
                    switch_type=SwitchType.TOPIC_SHIFT,
                    confidence=0.85,
                    should_clear_context=False,
                    transition_message="好的，让我们回到之前的话题。",
                    reasoning=f"检测到回退信号: {signal}",
                )
        
        # 新会话信号
        for signal in self.switch_signals["new_session"]:
            if query_lower.startswith(signal):
                return SwitchDetectionResult(
                    switch_type=SwitchType.NEW_SESSION,
                    confidence=0.7,
                    should_clear_context=True,
                    reasoning=f"检测到新会话信号: {signal}",
                )
        
        return None
    
    def _is_clarification(self, current: str, previous: List[str]) -> bool:
        """判断是否是澄清/补充"""
        if not previous:
            return False
        
        current_lower = current.lower()
        
        # 检查澄清信号词
        for signal in self.switch_signals["clarification"]:
            if signal in current_lower:
                return True
        
        # 检查是否是对上一轮的否定+澄清
        if current_lower.startswith("不是") or current_lower.startswith("不对"):
            return True
        
        return False
    
    def _is_follow_up(self, current: str, previous: List[str]) -> bool:
        """判断是否是追问"""
        if not previous:
            return False
        
        current_lower = current.lower()
        
        # 检查追问信号词
        for signal in self.switch_signals["follow_up"]:
            if current_lower.startswith(signal):
                return True
        
        # 短句可能是追问
        if len(current) < 15 and "?" in current:
            return True
        
        # 代词开头可能是追问
        if current_lower.startswith(("这个", "那个", "它", "这种")):
            return True
        
        return False
    
    def _detect_scenario(self, query: str) -> Optional[str]:
        """检测查询所属场景"""
        query_lower = query.lower()
        
        scenario_scores = {}
        for scenario_id, keywords in self.scenario_keywords.items():
            score = sum(1 for kw in keywords if kw.lower() in query_lower)
            if score > 0:
                scenario_scores[scenario_id] = score
        
        if scenario_scores:
            return max(scenario_scores.items(), key=lambda x: x[1])[0]
        
        return None
    
    def _is_topic_shift(self, current: str, previous: str) -> bool:
        """判断是否是话题偏移"""
        # 简单的相似度检查
        current_words = set(re.findall(r"[\u4e00-\u9fa5a-zA-Z]+", current.lower()))
        previous_words = set(re.findall(r"[\u4e00-\u9fa5a-zA-Z]+", previous.lower()))
        
        if not current_words or not previous_words:
            return False
        
        # 计算 Jaccard 相似度
        intersection = len(current_words & previous_words)
        union = len(current_words | previous_words)
        similarity = intersection / union if union > 0 else 0
        
        # 相似度很低可能是话题偏移
        return similarity < 0.2
    
    def _get_scenario_name(self, scenario_id: str) -> str:
        """获取场景显示名称"""
        names = {
            "aoi_inspection": "AOI光学检测",
            "smt_process": "SMT工艺",
            "quality_control": "质量管控",
            "equipment_selection": "设备选型",
            "cost_analysis": "成本分析",
            "technical_support": "技术支持",
        }
        return names.get(scenario_id, scenario_id)
    
    def handle_switch(
        self,
        detection: SwitchDetectionResult,
        context: Any,  # ConversationContext
    ) -> Dict[str, Any]:
        """
        处理场景切换
        
        Args:
            detection: 切换检测结果
            context: 会话上下文
        
        Returns:
            处理建议
        """
        actions = {
            "clear_context": detection.should_clear_context,
            "summarize_previous": detection.should_summarize_previous,
            "transition_message": detection.transition_message,
            "update_scenario": detection.new_scenario,
        }
        
        # 根据切换类型提供建议
        if detection.switch_type == SwitchType.SCENARIO_SWITCH:
            actions["preserve_entities"] = True  # 保留通用实体
            actions["reset_clarification"] = True  # 重置澄清状态
        
        elif detection.switch_type == SwitchType.NEW_SESSION:
            actions["preserve_entities"] = False
            actions["reset_all"] = True
        
        elif detection.switch_type == SwitchType.CLARIFICATION:
            actions["update_last_query"] = True  # 更新上一轮查询
        
        elif detection.switch_type == SwitchType.FOLLOW_UP:
            actions["inherit_intent"] = True  # 继承上一轮意图
        
        return actions


# ==================== 模块级便捷函数 ====================

_default_detector: Optional[ScenarioSwitchDetector] = None


def get_switch_detector() -> ScenarioSwitchDetector:
    """获取场景切换检测器实例"""
    global _default_detector
    if _default_detector is None:
        _default_detector = ScenarioSwitchDetector()
    return _default_detector


def detect_scenario_switch(
    current_query: str,
    previous_queries: List[str] = None,
    current_scenario: str = None,
    context_entities: Dict[str, Any] = None,
) -> SwitchDetectionResult:
    """便捷函数：检测场景切换"""
    return get_switch_detector().detect(
        current_query,
        previous_queries,
        current_scenario,
        context_entities,
    )

