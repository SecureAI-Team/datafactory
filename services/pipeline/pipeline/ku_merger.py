"""
KU 智能合并模块
将多个相似/重复的 KU 合并为一个完整的 KU
"""
import re
import os
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
import json


@dataclass
class KUData:
    """KU 完整数据"""
    id: str
    title: str
    summary: str
    body_markdown: str
    sections: List[Dict] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    params: Dict = field(default_factory=dict)
    source_refs: List[str] = field(default_factory=list)
    version: int = 1
    product_id: Optional[str] = None
    ku_type: str = "core"
    industry_tags: List[str] = field(default_factory=list)
    use_case_tags: List[str] = field(default_factory=list)


@dataclass
class MergeResult:
    """合并结果"""
    merged_ku: KUData
    source_ku_ids: List[str]
    merge_report: Dict
    success: bool = True
    error: Optional[str] = None


class KUMerger:
    """KU 智能合并器"""
    
    def __init__(self, llm_client=None, use_llm: bool = True):
        """
        初始化合并器
        
        Args:
            llm_client: LLM 客户端（用于智能摘要生成）
            use_llm: 是否使用 LLM 进行智能合并
        """
        self.llm_client = llm_client
        self.use_llm = use_llm and llm_client is not None
    
    def merge_kus(
        self,
        kus: List[KUData],
        strategy: str = "comprehensive"
    ) -> MergeResult:
        """
        合并多个 KU
        
        Args:
            kus: 要合并的 KU 列表
            strategy: 合并策略
                - comprehensive: 综合合并，保留最完整信息
                - newest: 以最新版本为主
                - manual: 返回合并建议，不自动合并
                
        Returns:
            MergeResult
        """
        if not kus:
            return MergeResult(
                merged_ku=None,
                source_ku_ids=[],
                merge_report={},
                success=False,
                error="No KUs to merge"
            )
        
        if len(kus) == 1:
            return MergeResult(
                merged_ku=kus[0],
                source_ku_ids=[kus[0].id],
                merge_report={"action": "single_ku_no_merge"},
                success=True
            )
        
        try:
            if strategy == "comprehensive":
                merged = self._merge_comprehensive(kus)
            elif strategy == "newest":
                merged = self._merge_newest(kus)
            else:
                merged = self._merge_comprehensive(kus)
            
            # 生成合并报告
            report = self._generate_merge_report(kus, merged)
            
            return MergeResult(
                merged_ku=merged,
                source_ku_ids=[ku.id for ku in kus],
                merge_report=report,
                success=True
            )
            
        except Exception as e:
            return MergeResult(
                merged_ku=None,
                source_ku_ids=[ku.id for ku in kus],
                merge_report={"error": str(e)},
                success=False,
                error=str(e)
            )
    
    def _merge_comprehensive(self, kus: List[KUData]) -> KUData:
        """综合合并策略"""
        merged = KUData(
            id="",  # 新 ID 由调用者生成
            title="",
            summary="",
            body_markdown="",
            version=max(ku.version for ku in kus) + 1
        )
        
        # 1. 选择最佳标题
        merged.title = self._select_best_title(kus)
        
        # 2. 合并摘要
        merged.summary = self._merge_summaries(kus)
        
        # 3. 合并正文
        merged.body_markdown = self._merge_body(kus)
        
        # 4. 合并章节
        merged.sections = self._merge_sections(kus)
        
        # 5. 合并标签
        merged.tags = self._merge_tags(kus)
        
        # 6. 合并参数（取并集，冲突时保留最新）
        merged.params = self._merge_params(kus)
        
        # 7. 合并来源引用
        merged.source_refs = self._merge_source_refs(kus)
        
        # 8. 合并元数据
        merged.product_id = kus[0].product_id
        merged.ku_type = kus[0].ku_type
        merged.industry_tags = self._merge_list_unique([ku.industry_tags for ku in kus])
        merged.use_case_tags = self._merge_list_unique([ku.use_case_tags for ku in kus])
        
        return merged
    
    def _merge_newest(self, kus: List[KUData]) -> KUData:
        """以最新版本为主"""
        # 按版本号排序，取最新
        sorted_kus = sorted(kus, key=lambda k: k.version, reverse=True)
        newest = sorted_kus[0]
        
        # 基于最新版本，补充其他版本的独有内容
        merged = KUData(
            id="",
            title=newest.title,
            summary=newest.summary,
            body_markdown=newest.body_markdown,
            sections=newest.sections.copy() if newest.sections else [],
            tags=newest.tags.copy() if newest.tags else [],
            params=newest.params.copy() if newest.params else {},
            source_refs=newest.source_refs.copy() if newest.source_refs else [],
            version=newest.version + 1,
            product_id=newest.product_id,
            ku_type=newest.ku_type,
            industry_tags=newest.industry_tags.copy() if newest.industry_tags else [],
            use_case_tags=newest.use_case_tags.copy() if newest.use_case_tags else [],
        )
        
        # 补充其他版本的标签和参数
        for ku in sorted_kus[1:]:
            for tag in (ku.tags or []):
                if tag not in merged.tags:
                    merged.tags.append(tag)
            
            for key, value in (ku.params or {}).items():
                if key not in merged.params:
                    merged.params[key] = value
        
        return merged
    
    def _select_best_title(self, kus: List[KUData]) -> str:
        """选择最佳标题（最完整、最清晰的）"""
        titles = [ku.title for ku in kus if ku.title]
        
        if not titles:
            return "Merged Knowledge Unit"
        
        # 选择最长的标题（通常更完整）
        # 但如果太长（>100字符），选择次长的
        sorted_titles = sorted(titles, key=len, reverse=True)
        
        for title in sorted_titles:
            if len(title) <= 100:
                return title
        
        # 都太长的话，取第一个并截断
        return sorted_titles[0][:100]
    
    def _merge_summaries(self, kus: List[KUData]) -> str:
        """合并摘要"""
        summaries = [ku.summary for ku in kus if ku.summary]
        
        if not summaries:
            return ""
        
        if len(summaries) == 1:
            return summaries[0]
        
        # 如果使用 LLM，生成综合摘要
        if self.use_llm:
            return self._llm_merge_summaries(summaries)
        
        # 否则选择最长的摘要
        return max(summaries, key=len)
    
    def _llm_merge_summaries(self, summaries: List[str]) -> str:
        """使用 LLM 合并摘要"""
        prompt = f"""请将以下多个摘要合并为一个综合性的摘要，保留所有关键信息，去除重复内容：

摘要1：{summaries[0]}

摘要2：{summaries[1] if len(summaries) > 1 else '(无)'}

{'摘要3：' + summaries[2] if len(summaries) > 2 else ''}

请输出合并后的摘要（不超过500字）："""
        
        try:
            response = self.llm_client.chat.completions.create(
                model=os.getenv("QWEN_MODEL", "qwen-plus"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            # 降级：返回最长的摘要
            return max(summaries, key=len)
    
    def _merge_body(self, kus: List[KUData]) -> str:
        """合并正文"""
        bodies = [ku.body_markdown for ku in kus if ku.body_markdown]
        
        if not bodies:
            return ""
        
        if len(bodies) == 1:
            return bodies[0]
        
        # 选择最长的正文作为基础
        base_body = max(bodies, key=len)
        
        # 提取其他正文中的独特章节
        unique_sections = self._extract_unique_sections(base_body, bodies)
        
        if unique_sections:
            # 添加独特章节
            base_body += "\n\n## 补充内容\n\n"
            base_body += "\n\n".join(unique_sections)
        
        return base_body
    
    def _extract_unique_sections(self, base: str, all_bodies: List[str]) -> List[str]:
        """提取其他正文中的独特章节"""
        unique = []
        
        # 简化版：提取其他正文中的标题和内容
        for body in all_bodies:
            if body == base:
                continue
            
            # 提取 markdown 标题
            sections = re.split(r'\n##\s+', body)
            for section in sections[1:]:  # 跳过第一个（标题前内容）
                # 检查这个章节是否在 base 中
                section_title = section.split('\n')[0].strip()
                if section_title and section_title.lower() not in base.lower():
                    unique.append(f"## {section}")
        
        return unique[:3]  # 最多添加3个独特章节
    
    def _merge_sections(self, kus: List[KUData]) -> List[Dict]:
        """合并章节"""
        all_sections = []
        seen_titles = set()
        
        for ku in kus:
            for section in (ku.sections or []):
                title = section.get("title", "").lower()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    all_sections.append(section)
        
        return all_sections
    
    def _merge_tags(self, kus: List[KUData]) -> List[str]:
        """合并标签"""
        return self._merge_list_unique([ku.tags or [] for ku in kus])
    
    def _merge_params(self, kus: List[KUData]) -> Dict:
        """合并参数"""
        merged = {}
        
        # 按版本排序，较新版本的参数优先
        sorted_kus = sorted(kus, key=lambda k: k.version, reverse=True)
        
        for ku in sorted_kus:
            for key, value in (ku.params or {}).items():
                if key not in merged:
                    merged[key] = value
        
        return merged
    
    def _merge_source_refs(self, kus: List[KUData]) -> List[str]:
        """合并来源引用"""
        return self._merge_list_unique([ku.source_refs or [] for ku in kus])
    
    def _merge_list_unique(self, lists: List[List]) -> List:
        """合并多个列表，保持唯一性"""
        seen = set()
        result = []
        for lst in lists:
            for item in lst:
                item_key = str(item).lower() if isinstance(item, str) else json.dumps(item)
                if item_key not in seen:
                    seen.add(item_key)
                    result.append(item)
        return result
    
    def _generate_merge_report(self, source_kus: List[KUData], merged: KUData) -> Dict:
        """生成合并报告"""
        return {
            "source_count": len(source_kus),
            "source_ids": [ku.id for ku in source_kus],
            "source_titles": [ku.title for ku in source_kus],
            "merged_title": merged.title,
            "merged_summary_length": len(merged.summary),
            "merged_body_length": len(merged.body_markdown),
            "merged_tags_count": len(merged.tags),
            "merged_params_count": len(merged.params),
            "version": merged.version,
            "changes": {
                "title_changed": merged.title not in [ku.title for ku in source_kus],
                "summary_merged": len(source_kus) > 1,
                "sections_merged": len(merged.sections) > 0,
            }
        }


# 测试代码
if __name__ == "__main__":
    merger = KUMerger(use_llm=False)
    
    test_kus = [
        KUData(
            id="1",
            title="AOI检测系统白皮书",
            summary="AOI检测技术是一种自动光学检测技术...",
            body_markdown="# 概述\n\nAOI技术用于...\n\n## 工作原理\n\n...",
            tags=["AOI", "检测"],
            params={"精度": "0.01mm"},
            version=1,
            product_id="aoi",
        ),
        KUData(
            id="2",
            title="AOI检测系统技术白皮书",
            summary="AOI（自动光学检测）是一种高效的质量检测方法...",
            body_markdown="# 简介\n\nAOI系统...\n\n## 应用场景\n\n电子制造...",
            tags=["AOI", "质检", "SMT"],
            params={"精度": "0.01mm", "速度": "1200pcs/h"},
            version=2,
            product_id="aoi",
        ),
    ]
    
    result = merger.merge_kus(test_kus)
    
    if result.success:
        print(f"合并成功!")
        print(f"标题: {result.merged_ku.title}")
        print(f"摘要: {result.merged_ku.summary[:100]}...")
        print(f"标签: {result.merged_ku.tags}")
        print(f"参数: {result.merged_ku.params}")
        print(f"报告: {json.dumps(result.merge_report, indent=2, ensure_ascii=False)}")
    else:
        print(f"合并失败: {result.error}")

