"""
交互流程智能触发服务
使用 LLM 智能识别是否应该触发交互流程
"""
import re
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from sqlalchemy.orm import Session
from openai import OpenAI

from ..models.config import InteractionFlow

logger = logging.getLogger(__name__)


@dataclass
class FlowTriggerResult:
    """流程触发检测结果"""
    should_trigger: bool
    flow_id: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""
    matched_keywords: List[str] = None
    
    def __post_init__(self):
        if self.matched_keywords is None:
            self.matched_keywords = []


class InteractionFlowTriggerService:
    """交互流程触发服务 - 结合规则和 LLM 智能识别"""
    
    def __init__(self, db: Session, llm_client: Optional[OpenAI] = None):
        self.db = db
        self.llm_client = llm_client
    
    def detect_trigger(
        self,
        query: str,
        history: List[Dict] = None,
        use_llm: bool = True
    ) -> FlowTriggerResult:
        """
        检测是否应该触发交互流程
        
        Args:
            query: 用户输入
            history: 对话历史
            use_llm: 是否使用 LLM 增强识别
        
        Returns:
            FlowTriggerResult: 触发检测结果
        """
        # 获取所有活跃的交互流程
        flows = self.db.query(InteractionFlow).filter(
            InteractionFlow.is_active == True
        ).all()
        
        if not flows:
            return FlowTriggerResult(should_trigger=False, reason="no_active_flows")
        
        # Step 1: 规则引擎匹配
        rule_result = self._rule_based_detection(query, flows)
        
        if rule_result.should_trigger and rule_result.confidence >= 0.8:
            # 高置信度规则匹配，直接返回
            logger.info(f"Rule-based trigger: {rule_result.flow_id} (conf={rule_result.confidence:.2f})")
            return rule_result
        
        # Step 2: LLM 智能识别
        if use_llm and self.llm_client:
            llm_result = self._llm_based_detection(query, flows, history)
            
            if llm_result.should_trigger:
                # LLM 结果优先（如果有触发）
                if llm_result.confidence > rule_result.confidence:
                    logger.info(f"LLM-based trigger: {llm_result.flow_id} (conf={llm_result.confidence:.2f})")
                    return llm_result
        
        # 返回规则匹配结果（可能是无触发）
        if rule_result.should_trigger:
            logger.info(f"Rule-based trigger (low conf): {rule_result.flow_id} (conf={rule_result.confidence:.2f})")
        
        return rule_result
    
    def _rule_based_detection(
        self,
        query: str,
        flows: List[InteractionFlow]
    ) -> FlowTriggerResult:
        """基于规则的触发检测"""
        query_lower = query.lower()
        best_match = FlowTriggerResult(should_trigger=False)
        best_score = 0.0
        
        for flow in flows:
            trigger_patterns = flow.trigger_patterns or []
            score = 0.0
            matched = []
            
            for pattern_group in trigger_patterns:
                # 关键词匹配
                keywords = pattern_group.get("keywords", [])
                for keyword in keywords:
                    if keyword.lower() in query_lower:
                        score += 1.0
                        matched.append(keyword)
                
                # 正则模式匹配
                patterns = pattern_group.get("patterns", [])
                for pattern in patterns:
                    try:
                        if re.search(pattern, query_lower):
                            score += 2.0
                            matched.append(f"pattern:{pattern[:20]}")
                    except re.error:
                        pass
            
            if score > best_score:
                best_score = score
                # 归一化置信度 (0-1)
                confidence = min(score / 5.0, 1.0)
                best_match = FlowTriggerResult(
                    should_trigger=True,
                    flow_id=flow.flow_id,
                    confidence=confidence,
                    reason="rule_match",
                    matched_keywords=matched
                )
        
        return best_match
    
    def _llm_based_detection(
        self,
        query: str,
        flows: List[InteractionFlow],
        history: List[Dict] = None
    ) -> FlowTriggerResult:
        """基于 LLM 的智能触发检测"""
        if not self.llm_client:
            return FlowTriggerResult(should_trigger=False, reason="no_llm_client")
        
        # 构建流程描述
        flow_descriptions = []
        for flow in flows:
            flow_descriptions.append(
                f"- {flow.flow_id}: {flow.name}\n"
                f"  描述: {flow.description or '无'}\n"
                f"  用途: {self._get_flow_purpose(flow)}"
            )
        
        flows_text = "\n".join(flow_descriptions)
        
        # 构建对话历史
        history_text = "无"
        if history:
            history_lines = []
            for msg in history[-3:]:
                role = "用户" if msg.get("role") == "user" else "助手"
                content = msg.get("content", "")[:100]
                history_lines.append(f"{role}: {content}")
            history_text = "\n".join(history_lines)
        
        prompt = f"""分析用户意图，判断是否需要启动结构化交互流程来收集信息。

用户问题: {query}

最近对话历史:
{history_text}

可用的交互流程:
{flows_text}

判断标准:
1. 如果用户询问的内容需要多个参数才能回答（如报价、选型、案例查找），应该触发对应流程
2. 如果用户明确表达需要帮助完成某个任务（如"帮我算一下"、"我想找案例"），应该触发
3. 如果用户的问题可以直接回答，不需要收集额外信息，不应该触发
4. 如果用户正在提供信息或补充说明，不应该触发

请以 JSON 格式返回分析结果:
{{
    "should_trigger": true或false,
    "flow_id": "如果触发则填写流程ID，否则为null",
    "confidence": 0.0-1.0的置信度,
    "reason": "判断理由（简短）"
}}

只返回 JSON，不要其他内容。"""

        try:
            response = self.llm_client.chat.completions.create(
                model="qwen-turbo",  # 使用快速模型
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=256,
            )
            
            content = response.choices[0].message.content.strip()
            
            # 提取 JSON
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                result = json.loads(json_match.group())
                
                should_trigger = result.get("should_trigger", False)
                flow_id = result.get("flow_id")
                confidence = float(result.get("confidence", 0.5))
                reason = result.get("reason", "")
                
                # 验证 flow_id 是否有效
                if should_trigger and flow_id:
                    valid_ids = [f.flow_id for f in flows]
                    if flow_id not in valid_ids:
                        logger.warning(f"LLM suggested invalid flow_id: {flow_id}")
                        return FlowTriggerResult(
                            should_trigger=False,
                            reason="invalid_flow_id_from_llm"
                        )
                
                return FlowTriggerResult(
                    should_trigger=should_trigger,
                    flow_id=flow_id if should_trigger else None,
                    confidence=confidence,
                    reason=f"llm:{reason}"
                )
                
        except Exception as e:
            logger.warning(f"LLM flow trigger detection failed: {e}")
        
        return FlowTriggerResult(should_trigger=False, reason="llm_error")
    
    def _get_flow_purpose(self, flow: InteractionFlow) -> str:
        """根据 on_complete 获取流程用途描述"""
        purposes = {
            "calculate_quote": "收集产品和数量信息后计算报价",
            "search_cases": "收集行业和规模信息后搜索案例",
            "save_contribution_draft": "收集材料信息后保存贡献草稿",
            "generate_proposal": "收集需求后生成方案",
        }
        return purposes.get(flow.on_complete, flow.on_complete or "通用交互")


# ==================== 便捷函数 ====================

def detect_interaction_trigger(
    db: Session,
    query: str,
    llm_client: Optional[OpenAI] = None,
    history: List[Dict] = None,
    use_llm: bool = True
) -> FlowTriggerResult:
    """
    便捷函数：检测是否应该触发交互流程
    
    Args:
        db: 数据库会话
        query: 用户输入
        llm_client: OpenAI 客户端（可选）
        history: 对话历史（可选）
        use_llm: 是否使用 LLM 增强（默认 True）
    
    Returns:
        FlowTriggerResult: 触发检测结果
    """
    service = InteractionFlowTriggerService(db, llm_client)
    return service.detect_trigger(query, history, use_llm)

