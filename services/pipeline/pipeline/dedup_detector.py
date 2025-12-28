"""
重复检测模块
检测相似和重复的 KU，生成合并建议
"""
import hashlib
import re
import uuid
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class KUInfo:
    """KU 基本信息（用于重复检测）"""
    id: str
    title: str
    summary: str
    product_id: Optional[str]
    ku_type: str
    content_hash: Optional[str] = None
    key_params: Dict[str, any] = field(default_factory=dict)


@dataclass
class DuplicateGroup:
    """重复组"""
    group_id: str
    ku_ids: List[str]
    similarity_score: float
    match_type: str  # exact, semantic, param_match
    merge_recommendation: str  # merge, keep_all, review
    details: Dict = field(default_factory=dict)


class DedupDetector:
    """重复检测器"""
    
    def __init__(
        self,
        semantic_threshold: float = 0.85,
        param_match_threshold: float = 0.8,
    ):
        self.semantic_threshold = semantic_threshold
        self.param_match_threshold = param_match_threshold
    
    def detect_duplicates(self, kus: List[KUInfo]) -> List[DuplicateGroup]:
        """
        检测重复和相似 KU
        
        Args:
            kus: KU 列表
            
        Returns:
            DuplicateGroup 列表
        """
        groups = []
        processed_ids: Set[str] = set()
        
        # 1. 按 product_id + ku_type 分组
        product_type_groups = self._group_by_product_type(kus)
        
        for key, group_kus in product_type_groups.items():
            if len(group_kus) < 2:
                continue
            
            # 2. 在每个组内检测重复
            subgroups = self._detect_within_group(group_kus, processed_ids)
            groups.extend(subgroups)
        
        # 3. 跨产品检测语义相似（标题相似的可能是同一产品不同名称）
        remaining_kus = [ku for ku in kus if ku.id not in processed_ids]
        if len(remaining_kus) > 1:
            cross_groups = self._detect_cross_product(remaining_kus, processed_ids)
            groups.extend(cross_groups)
        
        return groups
    
    def _group_by_product_type(self, kus: List[KUInfo]) -> Dict[str, List[KUInfo]]:
        """按 product_id + ku_type 分组"""
        groups = defaultdict(list)
        for ku in kus:
            # 只对可合并类型进行分组
            if ku.ku_type in ["core", "whitepaper", "faq"]:
                key = f"{ku.product_id or 'unknown'}|{ku.ku_type}"
                groups[key].append(ku)
        return groups
    
    def _detect_within_group(
        self,
        kus: List[KUInfo],
        processed_ids: Set[str]
    ) -> List[DuplicateGroup]:
        """在同一组内检测重复"""
        groups = []
        n = len(kus)
        
        # 计算两两相似度
        similarity_matrix = {}
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._compute_similarity(kus[i], kus[j])
                if sim >= self.semantic_threshold:
                    similarity_matrix[(i, j)] = sim
        
        # 聚类
        clusters = self._cluster_by_similarity(kus, similarity_matrix)
        
        for cluster_indices in clusters:
            if len(cluster_indices) < 2:
                continue
            
            cluster_kus = [kus[i] for i in cluster_indices]
            ku_ids = [ku.id for ku in cluster_kus]
            
            # 计算平均相似度
            avg_sim = self._compute_cluster_avg_similarity(cluster_indices, similarity_matrix)
            
            # 生成合并建议
            recommendation = self._generate_recommendation(cluster_kus, avg_sim)
            
            group = DuplicateGroup(
                group_id=str(uuid.uuid4())[:8],
                ku_ids=ku_ids,
                similarity_score=avg_sim,
                match_type="semantic" if avg_sim < 0.95 else "exact",
                merge_recommendation=recommendation,
                details={
                    "product_id": cluster_kus[0].product_id,
                    "ku_type": cluster_kus[0].ku_type,
                    "titles": [ku.title for ku in cluster_kus],
                }
            )
            groups.append(group)
            
            # 标记已处理
            processed_ids.update(ku_ids)
        
        return groups
    
    def _detect_cross_product(
        self,
        kus: List[KUInfo],
        processed_ids: Set[str]
    ) -> List[DuplicateGroup]:
        """跨产品检测语义相似"""
        groups = []
        n = len(kus)
        
        if n < 2:
            return groups
        
        # 只检查标题高度相似的
        for i in range(n):
            if kus[i].id in processed_ids:
                continue
            
            similar_ids = [kus[i].id]
            
            for j in range(i + 1, n):
                if kus[j].id in processed_ids:
                    continue
                
                # 检查标题相似度
                title_sim = self._title_similarity(kus[i].title, kus[j].title)
                if title_sim >= 0.9:
                    similar_ids.append(kus[j].id)
                    processed_ids.add(kus[j].id)
            
            if len(similar_ids) > 1:
                processed_ids.add(kus[i].id)
                groups.append(DuplicateGroup(
                    group_id=str(uuid.uuid4())[:8],
                    ku_ids=similar_ids,
                    similarity_score=0.9,
                    match_type="title_match",
                    merge_recommendation="review",  # 跨产品需要人工审核
                    details={
                        "reason": "cross_product_title_match"
                    }
                ))
        
        return groups
    
    def _compute_similarity(self, ku1: KUInfo, ku2: KUInfo) -> float:
        """计算两个 KU 的相似度"""
        score = 0.0
        
        # 1. 内容哈希完全匹配 -> 1.0
        if ku1.content_hash and ku1.content_hash == ku2.content_hash:
            return 1.0
        
        # 2. 标题相似度 (权重 0.4)
        title_sim = self._title_similarity(ku1.title, ku2.title)
        score += title_sim * 0.4
        
        # 3. 摘要相似度 (权重 0.4)
        summary_sim = self._text_similarity(ku1.summary, ku2.summary)
        score += summary_sim * 0.4
        
        # 4. 参数匹配度 (权重 0.2)
        if ku1.key_params and ku2.key_params:
            param_sim = self._param_similarity(ku1.key_params, ku2.key_params)
            score += param_sim * 0.2
        else:
            # 没有参数时，增加摘要权重
            score += summary_sim * 0.2
        
        return min(1.0, score)
    
    def _title_similarity(self, title1: str, title2: str) -> float:
        """计算标题相似度（基于字符和词）"""
        if not title1 or not title2:
            return 0.0
        
        # 标准化
        t1 = self._normalize_text(title1)
        t2 = self._normalize_text(title2)
        
        if t1 == t2:
            return 1.0
        
        # Jaccard 相似度
        words1 = set(t1.split())
        words2 = set(t2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        if not text1 or not text2:
            return 0.0
        
        # 简化版：基于词的 Jaccard 相似度
        t1 = self._normalize_text(text1)
        t2 = self._normalize_text(text2)
        
        words1 = set(t1.split())
        words2 = set(t2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _param_similarity(self, params1: Dict, params2: Dict) -> float:
        """计算参数匹配度"""
        if not params1 or not params2:
            return 0.0
        
        all_keys = set(params1.keys()) | set(params2.keys())
        if not all_keys:
            return 0.0
        
        matching = 0
        for key in all_keys:
            if key in params1 and key in params2:
                if params1[key] == params2[key]:
                    matching += 1
        
        return matching / len(all_keys)
    
    def _normalize_text(self, text: str) -> str:
        """标准化文本"""
        # 转小写，去除特殊字符
        text = text.lower()
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _cluster_by_similarity(
        self,
        kus: List[KUInfo],
        similarity_matrix: Dict[Tuple[int, int], float]
    ) -> List[List[int]]:
        """基于相似度矩阵聚类"""
        n = len(kus)
        parent = list(range(n))
        
        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        # 合并相似的
        for (i, j), sim in similarity_matrix.items():
            if sim >= self.semantic_threshold:
                union(i, j)
        
        # 收集聚类
        clusters = defaultdict(list)
        for i in range(n):
            clusters[find(i)].append(i)
        
        # 只返回大于1个元素的聚类
        return [indices for indices in clusters.values() if len(indices) > 1]
    
    def _compute_cluster_avg_similarity(
        self,
        indices: List[int],
        similarity_matrix: Dict[Tuple[int, int], float]
    ) -> float:
        """计算聚类内平均相似度"""
        sims = []
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                key = (min(indices[i], indices[j]), max(indices[i], indices[j]))
                if key in similarity_matrix:
                    sims.append(similarity_matrix[key])
        
        return sum(sims) / len(sims) if sims else 0.0
    
    def _generate_recommendation(
        self,
        kus: List[KUInfo],
        avg_similarity: float
    ) -> str:
        """生成合并建议"""
        if avg_similarity >= 0.95:
            # 几乎完全相同，建议直接合并
            return "merge"
        elif avg_similarity >= 0.85:
            # 高度相似，建议人工审核后合并
            return "review"
        else:
            # 相似但有差异，保留全部但建立关联
            return "keep_all"
    
    def compute_content_hash(self, content: str) -> str:
        """计算内容哈希"""
        normalized = self._normalize_text(content)
        return hashlib.md5(normalized.encode()).hexdigest()


# 测试代码
if __name__ == "__main__":
    detector = DedupDetector()
    
    test_kus = [
        KUInfo(id="1", title="AOI检测系统白皮书", summary="介绍AOI检测技术...", product_id="aoi", ku_type="whitepaper"),
        KUInfo(id="2", title="AOI检测系统技术白皮书", summary="介绍AOI检测技术原理...", product_id="aoi", ku_type="whitepaper"),
        KUInfo(id="3", title="AOI系统用户手册", summary="AOI系统使用指南...", product_id="aoi", ku_type="core"),
        KUInfo(id="4", title="3D检测系统白皮书", summary="介绍3D检测技术...", product_id="3d", ku_type="whitepaper"),
    ]
    
    groups = detector.detect_duplicates(test_kus)
    
    for group in groups:
        print(f"\n重复组 {group.group_id}:")
        print(f"  KU IDs: {group.ku_ids}")
        print(f"  相似度: {group.similarity_score:.2f}")
        print(f"  匹配类型: {group.match_type}")
        print(f"  建议: {group.merge_recommendation}")
        print(f"  详情: {group.details}")

