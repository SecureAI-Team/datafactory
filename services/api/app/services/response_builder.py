"""
回答构建服务
综合主 KU 和关联 KU 生成结构化回答
"""
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from .intent_recognizer import IntentResult, IntentType

logger = logging.getLogger(__name__)


@dataclass
class ResponseContext:
    """回答上下文"""
    query: str
    intent: IntentResult
    primary_hits: List[Dict]
    related_kus: Dict[str, List[Dict]] = field(default_factory=dict)
    extracted_params: List[Dict] = field(default_factory=list)
    calculation_result: Optional[Dict] = None


@dataclass
class BuiltResponse:
    """构建的回答"""
    answer_text: str  # 主回答文本
    sources: List[Dict]  # 来源列表
    recommendations: List[Dict]  # 推荐内容
    context_for_llm: str  # 给 LLM 的上下文
    metadata: Dict = field(default_factory=dict)


class ResponseBuilder:
    """回答构建器"""
    
    def __init__(self, max_context_length: int = 8000):
        self.max_context_length = max_context_length
    
    def build_response(self, ctx: ResponseContext) -> BuiltResponse:
        """
        综合构建回答
        
        根据意图类型选择不同的构建策略
        """
        intent_type = ctx.intent.intent_type
        
        if intent_type == IntentType.CASE_STUDY:
            return self._build_case_response(ctx)
        elif intent_type.value == "quote":
            return self._build_quote_response(ctx)
        elif intent_type == IntentType.CALCULATION:
            return self._build_calculation_response(ctx)
        elif intent_type == IntentType.COMPARISON:
            return self._build_comparison_response(ctx)
        else:
            return self._build_general_response(ctx)
    
    def _build_general_response(self, ctx: ResponseContext) -> BuiltResponse:
        """构建通用回答"""
        context_parts = []
        sources = []
        recommendations = []
        
        # 1. 添加主 KU 内容
        for hit in ctx.primary_hits[:3]:
            title = hit.get("title", "")
            summary = hit.get("summary", "")
            body = hit.get("body", "")[:1500]  # 截断
            
            context_parts.append(f"【{title}】\n{summary}\n\n{body}")
            
            sources.append({
                "id": hit.get("id"),
                "title": title,
                "type": hit.get("ku_type", "core"),
                "source_file": hit.get("source_file", ""),
            })
            
            # 2. 添加关联 KU 内容（如果有）
            related = ctx.related_kus.get(hit.get("id"), [])
            for rel_ku in related[:2]:
                rel_type = rel_ku.get("ku_type", "")
                if rel_type == "case":
                    context_parts.append(
                        f"【相关案例：{rel_ku.get('title')}】\n{rel_ku.get('summary', '')}"
                    )
                    recommendations.append({
                        "id": rel_ku.get("id"),
                        "title": rel_ku.get("title"),
                        "type": "case",
                        "reason": "相关案例",
                    })
                elif rel_type == "quote":
                    context_parts.append(
                        f"【报价信息】\n{rel_ku.get('summary', '')}"
                    )
        
        # 3. 构建 LLM 上下文
        context_for_llm = self._build_llm_context(ctx.query, context_parts)
        
        return BuiltResponse(
            answer_text="",  # 由 LLM 生成
            sources=sources,
            recommendations=recommendations,
            context_for_llm=context_for_llm,
            metadata={
                "intent": ctx.intent.intent_type.value,
                "hit_count": len(ctx.primary_hits),
            }
        )
    
    def _build_case_response(self, ctx: ResponseContext) -> BuiltResponse:
        """构建案例查找回答"""
        context_parts = []
        sources = []
        recommendations = []
        
        # 找出案例类型的 KU
        case_hits = [h for h in ctx.primary_hits if h.get("ku_type") == "case"]
        other_hits = [h for h in ctx.primary_hits if h.get("ku_type") != "case"]
        
        # 优先使用案例
        all_hits = case_hits + other_hits
        
        for i, hit in enumerate(all_hits[:5]):
            title = hit.get("title", "")
            summary = hit.get("summary", "")
            industry = ", ".join(hit.get("industry_tags", []))
            use_case = ", ".join(hit.get("use_case_tags", []))
            
            if hit.get("ku_type") == "case":
                context_parts.append(
                    f"案例 {i+1}: {title}\n"
                    f"行业: {industry or '未分类'}\n"
                    f"场景: {use_case or '未分类'}\n"
                    f"摘要: {summary}"
                )
            else:
                context_parts.append(f"【{title}】\n{summary}")
            
            sources.append({
                "id": hit.get("id"),
                "title": title,
                "type": hit.get("ku_type", "core"),
                "industry": industry,
                "use_case": use_case,
            })
        
        # 添加同产品的其他案例作为推荐
        for hit in case_hits[:3]:
            related = ctx.related_kus.get(hit.get("id"), [])
            for rel_ku in related:
                if rel_ku.get("ku_type") == "case" and rel_ku.get("id") not in [s["id"] for s in sources]:
                    recommendations.append({
                        "id": rel_ku.get("id"),
                        "title": rel_ku.get("title"),
                        "type": "case",
                        "reason": "更多相关案例",
                    })
        
        # 构建专用提示
        system_hint = """你是一个案例查找助手。用户正在寻找相关案例。
请根据以下案例信息，用以下格式回答：

找到 N 个相关案例：

1. **{案例标题}**
   - 行业：{行业}
   - 亮点：{关键成果/亮点}
   
2. ...

如果需要更多详情，可以询问具体哪个案例。"""
        
        context_for_llm = self._build_llm_context(
            ctx.query,
            context_parts,
            system_hint=system_hint
        )
        
        return BuiltResponse(
            answer_text="",
            sources=sources,
            recommendations=recommendations,
            context_for_llm=context_for_llm,
            metadata={
                "intent": "case_study",
                "case_count": len(case_hits),
            }
        )
    
    def _build_quote_response(self, ctx: ResponseContext) -> BuiltResponse:
        """构建报价查询回答"""
        context_parts = []
        sources = []
        recommendations = []
        
        # 找出报价类型的 KU
        quote_hits = [h for h in ctx.primary_hits if h.get("ku_type") == "quote"]
        core_hits = [h for h in ctx.primary_hits if h.get("ku_type") == "core"]
        
        # 优先使用报价
        if quote_hits:
            for hit in quote_hits[:3]:
                context_parts.append(
                    f"【报价信息：{hit.get('title')}】\n"
                    f"{hit.get('summary', '')}\n"
                    f"{hit.get('body', '')[:1000]}"
                )
                sources.append({
                    "id": hit.get("id"),
                    "title": hit.get("title"),
                    "type": "quote",
                    "product_id": hit.get("product_id", ""),
                })
        
        # 补充产品信息
        for hit in core_hits[:2]:
            context_parts.append(
                f"【产品信息：{hit.get('title')}】\n{hit.get('summary', '')}"
            )
            sources.append({
                "id": hit.get("id"),
                "title": hit.get("title"),
                "type": "core",
            })
        
        system_hint = """你是一个报价助手。用户正在咨询价格/报价信息。
请根据提供的信息回答，如果有具体价格请直接说明，如果没有请说明需要联系销售获取。
注意：报价信息可能有时效性，建议用户确认最新价格。"""
        
        context_for_llm = self._build_llm_context(
            ctx.query,
            context_parts,
            system_hint=system_hint
        )
        
        return BuiltResponse(
            answer_text="",
            sources=sources,
            recommendations=recommendations,
            context_for_llm=context_for_llm,
            metadata={
                "intent": "quote",
                "quote_count": len(quote_hits),
            }
        )
    
    def _build_calculation_response(self, ctx: ResponseContext) -> BuiltResponse:
        """构建计算类回答"""
        context_parts = []
        sources = []
        
        # 添加相关 KU
        for hit in ctx.primary_hits[:3]:
            context_parts.append(
                f"【{hit.get('title')}】\n{hit.get('summary', '')}"
            )
            
            # 添加参数信息
            params = hit.get("params", [])
            if params:
                param_lines = []
                for p in params[:10]:
                    name = p.get("name", "")
                    value = p.get("value", "")
                    unit = p.get("unit", "")
                    param_lines.append(f"  - {name}: {value} {unit}")
                context_parts.append("参数:\n" + "\n".join(param_lines))
            
            sources.append({
                "id": hit.get("id"),
                "title": hit.get("title"),
                "type": hit.get("ku_type", "core"),
            })
        
        # 添加计算结果（如果有）
        if ctx.calculation_result:
            calc = ctx.calculation_result
            context_parts.append(
                f"\n【计算结果】\n"
                f"公式: {calc.get('formula', '')}\n"
                f"结果: {calc.get('result', '')}\n"
                f"说明: {calc.get('explanation', '')}"
            )
        
        system_hint = """你是一个技术计算助手。用户需要进行技术计算或参数查询。
请根据提供的参数信息进行计算或说明，展示计算过程和结果。
如果缺少必要参数，请指出需要哪些信息。"""
        
        context_for_llm = self._build_llm_context(
            ctx.query,
            context_parts,
            system_hint=system_hint
        )
        
        return BuiltResponse(
            answer_text="",
            sources=sources,
            recommendations=[],
            context_for_llm=context_for_llm,
            metadata={
                "intent": "calculation",
                "has_calculation": ctx.calculation_result is not None,
            }
        )
    
    def _build_comparison_response(self, ctx: ResponseContext) -> BuiltResponse:
        """构建比较类回答"""
        context_parts = []
        sources = []
        
        # 收集所有产品的参数
        products_data = {}
        
        for hit in ctx.primary_hits[:5]:
            product_id = hit.get("product_id") or hit.get("title")
            if product_id not in products_data:
                products_data[product_id] = {
                    "title": hit.get("title"),
                    "summary": hit.get("summary", ""),
                    "params": {},
                }
            
            # 合并参数
            for p in hit.get("params", []):
                name = p.get("name", "")
                if name:
                    products_data[product_id]["params"][name] = {
                        "value": p.get("value"),
                        "unit": p.get("unit", ""),
                    }
            
            sources.append({
                "id": hit.get("id"),
                "title": hit.get("title"),
                "type": hit.get("ku_type", "core"),
            })
        
        # 构建比较表
        if len(products_data) >= 2:
            all_params = set()
            for data in products_data.values():
                all_params.update(data["params"].keys())
            
            comparison_lines = ["| 参数 | " + " | ".join(products_data.keys()) + " |"]
            comparison_lines.append("|" + "---|" * (len(products_data) + 1))
            
            for param in sorted(all_params):
                row = [param]
                for product_id in products_data.keys():
                    p_data = products_data[product_id]["params"].get(param, {})
                    value = p_data.get("value", "-")
                    unit = p_data.get("unit", "")
                    row.append(f"{value} {unit}".strip())
                comparison_lines.append("| " + " | ".join(row) + " |")
            
            context_parts.append("【产品比较】\n" + "\n".join(comparison_lines))
        
        # 添加摘要
        for product_id, data in products_data.items():
            context_parts.append(f"【{data['title']}】\n{data['summary']}")
        
        system_hint = """你是一个产品比较助手。用户正在比较不同产品/方案。
请根据提供的信息，以表格或列表形式清晰地比较各项参数，并给出建议。"""
        
        context_for_llm = self._build_llm_context(
            ctx.query,
            context_parts,
            system_hint=system_hint
        )
        
        return BuiltResponse(
            answer_text="",
            sources=sources,
            recommendations=[],
            context_for_llm=context_for_llm,
            metadata={
                "intent": "comparison",
                "product_count": len(products_data),
            }
        )
    
    def _build_llm_context(
        self,
        query: str,
        context_parts: List[str],
        system_hint: str = None
    ) -> str:
        """构建给 LLM 的上下文"""
        parts = []
        
        if system_hint:
            parts.append(system_hint)
        
        parts.append(f"用户问题：{query}")
        parts.append("\n相关知识：\n")
        parts.extend(context_parts)
        
        full_context = "\n\n".join(parts)
        
        # 截断
        if len(full_context) > self.max_context_length:
            full_context = full_context[:self.max_context_length] + "\n...(内容过长已截断)"
        
        return full_context
    
    def format_sources(self, sources: List[Dict]) -> str:
        """格式化来源列表"""
        if not sources:
            return ""
        
        lines = ["\n---\n📚 来源："]
        for i, src in enumerate(sources[:5], 1):
            title = src.get("title", "未知")
            src_type = src.get("type", "")
            type_label = {
                "core": "📄",
                "case": "📋",
                "quote": "💰",
                "solution": "🔧",
                "whitepaper": "📖",
                "faq": "❓",
            }.get(src_type, "📄")
            
            lines.append(f"{i}. {type_label} {title}")
        
        return "\n".join(lines)
    
    def format_recommendations(self, recommendations: List[Dict]) -> str:
        """格式化推荐列表"""
        if not recommendations:
            return ""
        
        lines = ["\n💡 您可能还感兴趣："]
        for rec in recommendations[:3]:
            title = rec.get("title", "")
            reason = rec.get("reason", "")
            lines.append(f"- {title}" + (f" ({reason})" if reason else ""))
        
        return "\n".join(lines)


# 便捷函数
def build_response(
    query: str,
    intent: IntentResult,
    hits: List[Dict],
    related_kus: Dict[str, List[Dict]] = None,
    calculation_result: Dict = None,
) -> BuiltResponse:
    """便捷函数：构建回答"""
    builder = ResponseBuilder()
    ctx = ResponseContext(
        query=query,
        intent=intent,
        primary_hits=hits,
        related_kus=related_kus or {},
        calculation_result=calculation_result,
    )
    return builder.build_response(ctx)

