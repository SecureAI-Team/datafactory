"""
层级化材料管理服务
支持: 场景 → 方案 → 材料 的层级结构
"""
import uuid
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class MaterialFormat(str, Enum):
    """材料格式"""
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    MD = "md"
    TXT = "txt"
    IMAGE = "image"
    JSON = "json"


class MaterialType(str, Enum):
    """材料类型"""
    WHITEPAPER = "whitepaper"           # 白皮书
    ARCHITECTURE = "architecture"        # 架构文档
    DEPLOYMENT_GUIDE = "deployment"      # 部署指南
    CASE_STUDY = "case_study"            # 案例研究
    COST_ANALYSIS = "cost_analysis"      # 成本分析
    COMPARISON = "comparison"            # 对比分析
    FAQ = "faq"                          # 常见问题
    TUTORIAL = "tutorial"                # 教程
    DIAGRAM = "diagram"                  # 图表


@dataclass
class Material:
    """材料"""
    id: str
    name: str
    solution_id: str
    
    # 分类
    format: MaterialFormat
    material_type: MaterialType
    
    # 内容
    file_path: str                       # MinIO 路径
    content_summary: str = ""            # 内容摘要
    key_points: List[str] = field(default_factory=list)
    
    # 元数据
    tags: List[str] = field(default_factory=list)
    language: str = "zh"
    version: str = "1.0"
    author: str = ""
    
    # 索引
    indexed: bool = False
    index_id: str = ""
    
    # 质量
    quality_score: float = 0.0
    relevance_boost: float = 1.0
    
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Solution:
    """解决方案"""
    id: str
    name: str
    scenario_id: str
    
    description: str = ""
    summary: str = ""                    # 用于快速展示
    
    # 特征
    tags: List[str] = field(default_factory=list)
    target_audience: List[str] = field(default_factory=list)
    applicable_scenarios: List[str] = field(default_factory=list)
    
    # 评估
    maturity_score: float = 0.0         # 成熟度 0-5
    cost_level: str = "medium"           # low/medium/high
    complexity_level: str = "medium"     # low/medium/high
    
    # 关联材料
    materials: List[Material] = field(default_factory=list)
    
    priority: int = 0
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Scenario:
    """场景"""
    id: str
    name: str
    domain: str
    
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    
    # 关联方案
    solutions: List[Solution] = field(default_factory=list)
    
    priority: int = 0
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


# ==================== 材料仓库 (内存版，生产环境用数据库) ====================

class MaterialRepository:
    """材料仓库"""
    
    def __init__(self):
        self.scenarios: Dict[str, Scenario] = {}
        self.solutions: Dict[str, Solution] = {}
        self.materials: Dict[str, Material] = {}
        
        # 初始化示例数据
        self._init_sample_data()
    
    def _init_sample_data(self):
        """初始化示例数据 - 网络安全场景"""
        
        # 场景：网络安全
        security_scenario = Scenario(
            id="network_security",
            name="网络安全",
            domain="安全",
            description="企业网络安全解决方案",
            keywords=["网络安全", "防火墙", "入侵检测", "零信任", "纵深防御"],
        )
        
        # 方案1：纵深防御
        defense_in_depth = Solution(
            id="defense_in_depth",
            name="纵深防御",
            scenario_id="network_security",
            description="多层次安全防护体系，从边界到终端的全面防护",
            summary="通过多层安全控制实现纵深防护，降低单点失效风险",
            tags=["边界安全", "主机安全", "应用安全", "数据安全"],
            target_audience=["中大型企业", "金融机构", "政府机关"],
            applicable_scenarios=["数据中心", "混合云", "多分支机构"],
            maturity_score=4.5,
            cost_level="high",
            complexity_level="high",
        )
        
        # 纵深防御的材料
        defense_materials = [
            Material(
                id="did_whitepaper_001",
                name="纵深防御技术白皮书",
                solution_id="defense_in_depth",
                format=MaterialFormat.PDF,
                material_type=MaterialType.WHITEPAPER,
                file_path="gold/network_security/defense_in_depth/whitepaper.pdf",
                content_summary="详细介绍纵深防御的理论基础、技术架构和实施方法",
                key_points=["分层防护", "最小权限", "纵深控制", "安全域划分"],
                tags=["理论", "架构"],
                quality_score=4.8,
            ),
            Material(
                id="did_arch_001",
                name="纵深防御参考架构图",
                solution_id="defense_in_depth",
                format=MaterialFormat.IMAGE,
                material_type=MaterialType.ARCHITECTURE,
                file_path="gold/network_security/defense_in_depth/architecture.png",
                content_summary="展示典型的纵深防御架构，包括边界层、网络层、主机层、应用层、数据层",
                key_points=["五层架构", "安全组件", "数据流向"],
                tags=["架构图", "可视化"],
                quality_score=4.5,
            ),
            Material(
                id="did_deploy_001",
                name="纵深防御部署指南",
                solution_id="defense_in_depth",
                format=MaterialFormat.MD,
                material_type=MaterialType.DEPLOYMENT_GUIDE,
                file_path="gold/network_security/defense_in_depth/deployment_guide.md",
                content_summary="分阶段实施纵深防御的详细步骤和配置指南",
                key_points=["评估阶段", "规划阶段", "实施阶段", "运维阶段"],
                tags=["部署", "实施"],
                quality_score=4.2,
            ),
            Material(
                id="did_case_001",
                name="某金融机构纵深防御案例",
                solution_id="defense_in_depth",
                format=MaterialFormat.DOCX,
                material_type=MaterialType.CASE_STUDY,
                file_path="gold/network_security/defense_in_depth/case_finance.docx",
                content_summary="某银行实施纵深防御的实际案例，包括需求分析、方案设计、实施过程和效果评估",
                key_points=["需求背景", "方案选型", "实施经验", "效果评估"],
                tags=["案例", "金融"],
                quality_score=4.6,
            ),
            Material(
                id="did_cost_001",
                name="纵深防御成本分析",
                solution_id="defense_in_depth",
                format=MaterialFormat.XLSX,
                material_type=MaterialType.COST_ANALYSIS,
                file_path="gold/network_security/defense_in_depth/cost_analysis.xlsx",
                content_summary="不同规模企业实施纵深防御的成本估算和ROI分析",
                key_points=["硬件成本", "软件成本", "人力成本", "运维成本", "ROI"],
                tags=["成本", "预算"],
                quality_score=4.0,
            ),
        ]
        
        defense_in_depth.materials = defense_materials
        
        # 方案2：零信任
        zero_trust = Solution(
            id="zero_trust",
            name="零信任架构",
            scenario_id="network_security",
            description="基于'永不信任，始终验证'原则的新一代安全架构",
            summary="打破传统边界安全模型，实现持续验证和最小权限访问",
            tags=["身份验证", "持续验证", "微分段", "最小权限"],
            target_audience=["云原生企业", "远程办公场景", "多云环境"],
            applicable_scenarios=["SaaS应用", "远程访问", "多云管理"],
            maturity_score=4.0,
            cost_level="medium",
            complexity_level="medium",
        )
        
        zero_trust_materials = [
            Material(
                id="zt_whitepaper_001",
                name="零信任架构白皮书",
                solution_id="zero_trust",
                format=MaterialFormat.PDF,
                material_type=MaterialType.WHITEPAPER,
                file_path="gold/network_security/zero_trust/whitepaper.pdf",
                content_summary="零信任架构的原理、组件和实施路径",
                key_points=["核心原则", "技术组件", "实施路径"],
                tags=["理论", "架构"],
                quality_score=4.7,
            ),
            Material(
                id="zt_comparison_001",
                name="零信任与传统安全对比",
                solution_id="zero_trust",
                format=MaterialFormat.PDF,
                material_type=MaterialType.COMPARISON,
                file_path="gold/network_security/zero_trust/comparison.pdf",
                content_summary="零信任架构与传统边界安全模型的详细对比分析",
                key_points=["安全模型对比", "适用场景", "迁移策略"],
                tags=["对比", "分析"],
                quality_score=4.3,
            ),
        ]
        
        zero_trust.materials = zero_trust_materials
        
        # 方案3：SASE
        sase = Solution(
            id="sase",
            name="SASE (安全访问服务边缘)",
            scenario_id="network_security",
            description="融合网络和安全能力的云交付服务架构",
            summary="将SD-WAN与云安全服务整合，提供统一的安全访问体验",
            tags=["SD-WAN", "云安全", "CASB", "SWG", "ZTNA"],
            target_audience=["分布式企业", "云优先企业", "跨国企业"],
            applicable_scenarios=["分支机构", "远程办公", "多云访问"],
            maturity_score=3.5,
            cost_level="medium",
            complexity_level="low",
        )
        
        sase.materials = [
            Material(
                id="sase_overview_001",
                name="SASE解决方案概述",
                solution_id="sase",
                format=MaterialFormat.PDF,
                material_type=MaterialType.WHITEPAPER,
                file_path="gold/network_security/sase/overview.pdf",
                content_summary="SASE架构概述、核心组件和主流厂商分析",
                key_points=["架构组件", "厂商对比", "选型建议"],
                tags=["概述", "选型"],
                quality_score=4.4,
            ),
        ]
        
        # 添加方案到场景
        security_scenario.solutions = [defense_in_depth, zero_trust, sase]
        
        # 保存到仓库
        self.scenarios["network_security"] = security_scenario
        
        for solution in security_scenario.solutions:
            self.solutions[solution.id] = solution
            for material in solution.materials:
                self.materials[material.id] = material
    
    # ==================== 查询方法 ====================
    
    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        """获取场景"""
        return self.scenarios.get(scenario_id)
    
    def get_solution(self, solution_id: str) -> Optional[Solution]:
        """获取方案"""
        return self.solutions.get(solution_id)
    
    def get_material(self, material_id: str) -> Optional[Material]:
        """获取材料"""
        return self.materials.get(material_id)
    
    def list_scenarios(self, domain: str = None) -> List[Scenario]:
        """列出场景"""
        scenarios = list(self.scenarios.values())
        if domain:
            scenarios = [s for s in scenarios if s.domain == domain]
        return sorted(scenarios, key=lambda x: x.priority, reverse=True)
    
    def list_solutions(self, scenario_id: str) -> List[Solution]:
        """列出场景下的方案"""
        solutions = [s for s in self.solutions.values() if s.scenario_id == scenario_id and s.enabled]
        return sorted(solutions, key=lambda x: x.priority, reverse=True)
    
    def list_materials(
        self,
        solution_id: str = None,
        material_type: MaterialType = None,
        format: MaterialFormat = None,
        tags: List[str] = None,
    ) -> List[Material]:
        """列出材料（支持多维过滤）"""
        materials = list(self.materials.values())
        
        if solution_id:
            materials = [m for m in materials if m.solution_id == solution_id]
        
        if material_type:
            materials = [m for m in materials if m.material_type == material_type]
        
        if format:
            materials = [m for m in materials if m.format == format]
        
        if tags:
            materials = [m for m in materials if any(t in m.tags for t in tags)]
        
        return sorted(materials, key=lambda x: x.quality_score, reverse=True)
    
    def search_materials(self, query: str, scenario_id: str = None) -> List[Material]:
        """搜索材料"""
        results = []
        query_lower = query.lower()
        
        for material in self.materials.values():
            # 如果指定了场景，先过滤方案
            if scenario_id:
                solution = self.solutions.get(material.solution_id)
                if not solution or solution.scenario_id != scenario_id:
                    continue
            
            score = 0
            
            # 名称匹配
            if query_lower in material.name.lower():
                score += 3
            
            # 摘要匹配
            if query_lower in material.content_summary.lower():
                score += 2
            
            # 关键点匹配
            for kp in material.key_points:
                if query_lower in kp.lower():
                    score += 1
            
            # 标签匹配
            for tag in material.tags:
                if query_lower in tag.lower():
                    score += 1
            
            if score > 0:
                results.append((material, score * material.relevance_boost))
        
        # 按分数排序
        results.sort(key=lambda x: x[1], reverse=True)
        return [r[0] for r in results]
    
    def get_materials_for_retrieval(
        self,
        scenario_id: str,
        solution_ids: List[str] = None,
        material_types: List[MaterialType] = None,
    ) -> List[Dict]:
        """
        获取用于检索的材料数据
        返回适合传递给 LLM 的格式
        """
        results = []
        
        for material in self.materials.values():
            solution = self.solutions.get(material.solution_id)
            if not solution:
                continue
            
            # 场景过滤
            if scenario_id and solution.scenario_id != scenario_id:
                continue
            
            # 方案过滤
            if solution_ids and material.solution_id not in solution_ids:
                continue
            
            # 类型过滤
            if material_types and material.material_type not in material_types:
                continue
            
            results.append({
                "id": material.id,
                "name": material.name,
                "solution": solution.name,
                "type": material.material_type.value,
                "format": material.format.value,
                "summary": material.content_summary,
                "key_points": material.key_points,
                "quality_score": material.quality_score,
            })
        
        return results


# ==================== 全局实例 ====================

_repository = MaterialRepository()


def get_material_repository() -> MaterialRepository:
    """获取材料仓库"""
    return _repository

