"""
知识图谱服务
Neo4j 图谱操作：创建、查询、遍历
"""
import os
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from contextlib import contextmanager

from .entity_extractor import Entity, EntityType
from .relation_extractor import Relation, RelationType

logger = logging.getLogger(__name__)


@dataclass
class GraphNode:
    """图谱节点"""
    node_id: str
    label: str
    properties: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.node_id,
            "label": self.label,
            "properties": self.properties,
        }


@dataclass
class GraphEdge:
    """图谱边"""
    source_id: str
    target_id: str
    relation_type: str
    properties: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "relation": self.relation_type,
            "properties": self.properties,
        }


@dataclass
class GraphQueryResult:
    """图谱查询结果"""
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)
    paths: List[List[Dict]] = field(default_factory=list)
    raw_result: Any = None
    
    def to_dict(self) -> Dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "paths": self.paths,
        }


class KnowledgeGraphService:
    """知识图谱服务"""
    
    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None,
    ):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "neo4jpass")
        
        self._driver = None
    
    @property
    def driver(self):
        """延迟初始化 Neo4j driver"""
        if self._driver is None:
            try:
                from neo4j import GraphDatabase
                self._driver = GraphDatabase.driver(
                    self.uri,
                    auth=(self.user, self.password),
                )
                logger.info(f"Neo4j connected: {self.uri}")
            except Exception as e:
                logger.error(f"Neo4j connection failed: {e}")
                raise
        return self._driver
    
    @contextmanager
    def session(self):
        """获取会话"""
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()
    
    def close(self):
        """关闭连接"""
        if self._driver:
            self._driver.close()
            self._driver = None
    
    # ==================== 节点操作 ====================
    
    def create_node(
        self,
        label: str,
        properties: Dict,
        unique_key: str = "name",
    ) -> Optional[str]:
        """
        创建或合并节点
        
        Args:
            label: 节点标签
            properties: 节点属性
            unique_key: 唯一键
        
        Returns:
            节点 ID
        """
        try:
            with self.session() as session:
                query = f"""
                MERGE (n:{label} {{{unique_key}: $unique_value}})
                SET n += $properties
                RETURN elementId(n) as id
                """
                
                result = session.run(
                    query,
                    unique_value=properties.get(unique_key, ""),
                    properties=properties,
                )
                
                record = result.single()
                return record["id"] if record else None
                
        except Exception as e:
            logger.error(f"Create node failed: {e}")
            return None
    
    def get_node(self, label: str, name: str) -> Optional[GraphNode]:
        """获取节点"""
        try:
            with self.session() as session:
                query = f"""
                MATCH (n:{label} {{name: $name}})
                RETURN n, elementId(n) as id
                """
                
                result = session.run(query, name=name)
                record = result.single()
                
                if record:
                    node = record["n"]
                    return GraphNode(
                        node_id=record["id"],
                        label=label,
                        properties=dict(node),
                    )
                
        except Exception as e:
            logger.error(f"Get node failed: {e}")
        
        return None
    
    def delete_node(self, label: str, name: str) -> bool:
        """删除节点"""
        try:
            with self.session() as session:
                query = f"""
                MATCH (n:{label} {{name: $name}})
                DETACH DELETE n
                """
                session.run(query, name=name)
                return True
                
        except Exception as e:
            logger.error(f"Delete node failed: {e}")
            return False
    
    # ==================== 关系操作 ====================
    
    def create_relation(
        self,
        source_label: str,
        source_name: str,
        target_label: str,
        target_name: str,
        relation_type: str,
        properties: Dict = None,
    ) -> bool:
        """创建关系"""
        try:
            with self.session() as session:
                query = f"""
                MATCH (s:{source_label} {{name: $source_name}})
                MATCH (t:{target_label} {{name: $target_name}})
                MERGE (s)-[r:{relation_type}]->(t)
                SET r += $properties
                RETURN r
                """
                
                result = session.run(
                    query,
                    source_name=source_name,
                    target_name=target_name,
                    properties=properties or {},
                )
                
                return result.single() is not None
                
        except Exception as e:
            logger.error(f"Create relation failed: {e}")
            return False
    
    # ==================== 查询操作 ====================
    
    def query_neighbors(
        self,
        label: str,
        name: str,
        relation_type: str = None,
        direction: str = "both",
        depth: int = 1,
    ) -> GraphQueryResult:
        """
        查询邻居节点
        
        Args:
            label: 起始节点标签
            name: 起始节点名称
            relation_type: 关系类型（可选）
            direction: 方向 (in/out/both)
            depth: 遍历深度
        
        Returns:
            GraphQueryResult
        """
        result = GraphQueryResult()
        
        try:
            with self.session() as session:
                rel_pattern = f":{relation_type}" if relation_type else ""
                
                if direction == "out":
                    pattern = f"(n)-[r{rel_pattern}]->(m)"
                elif direction == "in":
                    pattern = f"(n)<-[r{rel_pattern}]-(m)"
                else:
                    pattern = f"(n)-[r{rel_pattern}]-(m)"
                
                query = f"""
                MATCH (n:{label} {{name: $name}})
                MATCH {pattern}
                RETURN n, r, m, type(r) as rel_type,
                       elementId(n) as n_id, elementId(m) as m_id
                LIMIT 100
                """
                
                records = session.run(query, name=name)
                
                seen_nodes = set()
                for record in records:
                    # 添加源节点
                    if record["n_id"] not in seen_nodes:
                        result.nodes.append(GraphNode(
                            node_id=record["n_id"],
                            label=label,
                            properties=dict(record["n"]),
                        ))
                        seen_nodes.add(record["n_id"])
                    
                    # 添加目标节点
                    if record["m_id"] not in seen_nodes:
                        m = record["m"]
                        result.nodes.append(GraphNode(
                            node_id=record["m_id"],
                            label=list(m.labels)[0] if m.labels else "Node",
                            properties=dict(m),
                        ))
                        seen_nodes.add(record["m_id"])
                    
                    # 添加边
                    result.edges.append(GraphEdge(
                        source_id=record["n_id"],
                        target_id=record["m_id"],
                        relation_type=record["rel_type"],
                        properties=dict(record["r"]),
                    ))
                    
        except Exception as e:
            logger.error(f"Query neighbors failed: {e}")
        
        return result
    
    def find_path(
        self,
        source_label: str,
        source_name: str,
        target_label: str,
        target_name: str,
        max_depth: int = 5,
    ) -> GraphQueryResult:
        """
        查找两个节点间的路径
        
        Args:
            source_label: 源节点标签
            source_name: 源节点名称
            target_label: 目标节点标签
            target_name: 目标节点名称
            max_depth: 最大深度
        
        Returns:
            GraphQueryResult
        """
        result = GraphQueryResult()
        
        try:
            with self.session() as session:
                query = f"""
                MATCH p = shortestPath(
                    (s:{source_label} {{name: $source_name}})-[*1..{max_depth}]-
                    (t:{target_label} {{name: $target_name}})
                )
                RETURN p
                """
                
                records = session.run(
                    query,
                    source_name=source_name,
                    target_name=target_name,
                )
                
                for record in records:
                    path = record["p"]
                    path_nodes = []
                    
                    for node in path.nodes:
                        path_nodes.append({
                            "label": list(node.labels)[0] if node.labels else "Node",
                            "name": node.get("name", ""),
                            "properties": dict(node),
                        })
                    
                    result.paths.append(path_nodes)
                    
        except Exception as e:
            logger.error(f"Find path failed: {e}")
        
        return result
    
    def search_by_property(
        self,
        label: str,
        property_name: str,
        property_value: Any,
        limit: int = 20,
    ) -> List[GraphNode]:
        """按属性搜索节点"""
        nodes = []
        
        try:
            with self.session() as session:
                query = f"""
                MATCH (n:{label})
                WHERE n.{property_name} CONTAINS $value OR n.{property_name} = $value
                RETURN n, elementId(n) as id
                LIMIT $limit
                """
                
                records = session.run(
                    query,
                    value=str(property_value),
                    limit=limit,
                )
                
                for record in records:
                    nodes.append(GraphNode(
                        node_id=record["id"],
                        label=label,
                        properties=dict(record["n"]),
                    ))
                    
        except Exception as e:
            logger.error(f"Search failed: {e}")
        
        return nodes
    
    def full_text_search(
        self,
        query_text: str,
        labels: List[str] = None,
        limit: int = 20,
    ) -> List[GraphNode]:
        """全文搜索 - 直接搜索所有节点"""
        nodes = []
        
        try:
            with self.session() as session:
                # 直接搜索所有节点，不按标签分
                cypher = """
                MATCH (n)
                WHERE toLower(n.name) CONTAINS toLower($query)
                   OR toLower(coalesce(n.text, '')) CONTAINS toLower($query)
                RETURN n, elementId(n) as id, labels(n) as node_labels
                LIMIT $limit
                """
                
                records = session.run(
                    cypher,
                    query=query_text,
                    limit=limit,
                )
                
                for record in records:
                    node_labels = record.get("node_labels", [])
                    nodes.append(GraphNode(
                        node_id=record["id"],
                        label=node_labels[0] if node_labels else "Node",
                        properties=dict(record["n"]),
                    ))
                        
        except Exception as e:
            logger.error(f"Full text search failed: {e}")
        
        return nodes
    
    # ==================== 批量操作 ====================
    
    def import_entities(self, entities: List[Entity]) -> int:
        """批量导入实体"""
        count = 0
        
        # 映射 EntityType 到 Neo4j 标签
        label_map = {
            EntityType.PRODUCT: "Product",
            EntityType.PARAMETER: "Parameter",
            EntityType.SCENARIO: "Scenario",
            EntityType.COMPANY: "Company",
            EntityType.TECHNOLOGY: "Technology",
            EntityType.VALUE: "Value",
            EntityType.SOLUTION: "Solution",
        }
        
        for entity in entities:
            label = label_map.get(entity.entity_type, "Entity")
            
            properties = {
                "name": entity.normalized or entity.text,
                "text": entity.text,
                "confidence": entity.confidence,
                **entity.attributes,
            }
            
            if self.create_node(label, properties):
                count += 1
        
        return count
    
    def import_relations(self, relations: List[Relation]) -> int:
        """批量导入关系"""
        count = 0
        
        label_map = {
            EntityType.PRODUCT: "Product",
            EntityType.PARAMETER: "Parameter",
            EntityType.SCENARIO: "Scenario",
            EntityType.COMPANY: "Company",
            EntityType.TECHNOLOGY: "Technology",
            EntityType.VALUE: "Value",
            EntityType.SOLUTION: "Solution",
        }
        
        for rel in relations:
            source_label = label_map.get(rel.source.entity_type, "Entity")
            target_label = label_map.get(rel.target.entity_type, "Entity")
            
            if self.create_relation(
                source_label,
                rel.source.normalized or rel.source.text,
                target_label,
                rel.target.normalized or rel.target.text,
                rel.relation_type.value.upper(),
                {"confidence": rel.confidence},
            ):
                count += 1
        
        return count
    
    def get_stats(self) -> Dict:
        """获取图谱统计"""
        stats = {"nodes": 0, "edges": 0, "labels": []}
        
        try:
            with self.session() as session:
                # 节点数
                result = session.run("MATCH (n) RETURN count(n) as count")
                stats["nodes"] = result.single()["count"]
                
                # 边数
                result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
                stats["edges"] = result.single()["count"]
                
                # 标签
                result = session.run("CALL db.labels() YIELD label RETURN label")
                stats["labels"] = [record["label"] for record in result]
                
        except Exception as e:
            logger.error(f"Get stats failed: {e}")
        
        return stats


# ==================== 模块级便捷函数 ====================

_default_service: Optional[KnowledgeGraphService] = None


def get_knowledge_graph() -> KnowledgeGraphService:
    """获取知识图谱服务实例"""
    global _default_service
    if _default_service is None:
        _default_service = KnowledgeGraphService()
    return _default_service


def query_graph(
    label: str,
    name: str,
    relation_type: str = None,
) -> GraphQueryResult:
    """便捷函数：查询图谱"""
    return get_knowledge_graph().query_neighbors(label, name, relation_type)


def search_graph(query: str, limit: int = 20) -> List[GraphNode]:
    """便捷函数：搜索图谱"""
    return get_knowledge_graph().full_text_search(query, limit=limit)

