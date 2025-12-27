"""
知识图谱 API
实体查询、关系遍历、图谱搜索
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services.knowledge_graph import (
    get_knowledge_graph,
    KnowledgeGraphService,
    GraphNode,
    GraphQueryResult,
)
from ..services.entity_extractor import (
    get_entity_extractor,
    extract_entities,
    EntityType,
)
from ..services.relation_extractor import (
    get_relation_extractor,
    extract_relations,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kg", tags=["knowledge-graph"])


# ==================== 请求/响应模型 ====================

class ExtractRequest(BaseModel):
    """实体抽取请求"""
    text: str
    use_llm: bool = False


class ExtractResponse(BaseModel):
    """实体抽取响应"""
    entities: List[dict]
    relations: List[dict]


class ImportRequest(BaseModel):
    """导入请求"""
    text: str
    extract_relations: bool = True
    use_llm: bool = False


class ImportResponse(BaseModel):
    """导入响应"""
    entities_imported: int
    relations_imported: int


class QueryRequest(BaseModel):
    """查询请求"""
    label: str
    name: str
    relation_type: Optional[str] = None
    direction: str = "both"
    depth: int = 1


class PathRequest(BaseModel):
    """路径查询请求"""
    source_label: str
    source_name: str
    target_label: str
    target_name: str
    max_depth: int = 5


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    labels: Optional[List[str]] = None
    limit: int = 20


# ==================== API 端点 ====================

@router.post("/extract", response_model=ExtractResponse)
async def extract_from_text(request: ExtractRequest):
    """
    从文本中抽取实体和关系
    
    Args:
        request: 包含文本的请求
    
    Returns:
        抽取的实体和关系
    """
    # 抽取实体
    entity_result = extract_entities(request.text, request.use_llm)
    
    # 抽取关系
    relation_result = extract_relations(
        request.text,
        entity_result.entities,
        request.use_llm,
    )
    
    return ExtractResponse(
        entities=[e.to_dict() for e in entity_result.entities],
        relations=[r.to_dict() for r in relation_result.relations],
    )


@router.post("/import", response_model=ImportResponse)
async def import_to_graph(request: ImportRequest):
    """
    从文本抽取并导入到知识图谱
    
    Args:
        request: 导入请求
    
    Returns:
        导入统计
    """
    try:
        kg = get_knowledge_graph()
        
        # 抽取实体
        entity_result = extract_entities(request.text, request.use_llm)
        
        # 导入实体
        entities_count = kg.import_entities(entity_result.entities)
        
        relations_count = 0
        if request.extract_relations:
            # 抽取关系
            relation_result = extract_relations(
                request.text,
                entity_result.entities,
                request.use_llm,
            )
            # 导入关系
            relations_count = kg.import_relations(relation_result.relations)
        
        return ImportResponse(
            entities_imported=entities_count,
            relations_imported=relations_count,
        )
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/node/{label}/{name}")
async def get_node(label: str, name: str):
    """获取节点详情"""
    try:
        kg = get_knowledge_graph()
        node = kg.get_node(label, name)
        
        if not node:
            raise HTTPException(status_code=404, detail="节点不存在")
        
        return node.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get node failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query_graph(request: QueryRequest):
    """
    查询节点的邻居
    
    Args:
        request: 查询请求
    
    Returns:
        相关节点和边
    """
    try:
        kg = get_knowledge_graph()
        
        result = kg.query_neighbors(
            label=request.label,
            name=request.name,
            relation_type=request.relation_type,
            direction=request.direction,
            depth=request.depth,
        )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query")
async def query_graph_get(
    entity: str = Query(..., description="实体名称"),
    relation: str = Query(None, description="关系类型"),
    label: str = Query("Product", description="实体标签"),
):
    """
    查询实体关系（GET 方式）
    
    Args:
        entity: 实体名称
        relation: 关系类型
        label: 实体标签
    
    Returns:
        相关节点和边
    """
    try:
        kg = get_knowledge_graph()
        
        result = kg.query_neighbors(
            label=label,
            name=entity,
            relation_type=relation,
        )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/path")
async def find_path(request: PathRequest):
    """
    查找两个节点间的路径
    
    Args:
        request: 路径查询请求
    
    Returns:
        路径信息
    """
    try:
        kg = get_knowledge_graph()
        
        result = kg.find_path(
            source_label=request.source_label,
            source_name=request.source_name,
            target_label=request.target_label,
            target_name=request.target_name,
            max_depth=request.max_depth,
        )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Find path failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search(request: SearchRequest):
    """
    全文搜索图谱
    
    Args:
        request: 搜索请求
    
    Returns:
        匹配的节点
    """
    try:
        kg = get_knowledge_graph()
        
        nodes = kg.full_text_search(
            query_text=request.query,
            labels=request.labels,
            limit=request.limit,
        )
        
        return {
            "query": request.query,
            "count": len(nodes),
            "nodes": [n.to_dict() for n in nodes],
        }
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_get(
    q: str = Query(..., description="搜索关键词"),
    limit: int = Query(20, description="结果数量"),
):
    """全文搜索（GET 方式）"""
    try:
        kg = get_knowledge_graph()
        nodes = kg.full_text_search(q, limit=limit)
        
        return {
            "query": q,
            "count": len(nodes),
            "nodes": [n.to_dict() for n in nodes],
        }
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """获取图谱统计信息"""
    try:
        kg = get_knowledge_graph()
        return kg.get_stats()
        
    except Exception as e:
        logger.error(f"Get stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/node/{label}/{name}")
async def delete_node(label: str, name: str):
    """删除节点"""
    try:
        kg = get_knowledge_graph()
        
        if kg.delete_node(label, name):
            return {"status": "deleted", "label": label, "name": name}
        else:
            raise HTTPException(status_code=500, detail="删除失败")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """知识图谱健康检查"""
    try:
        kg = get_knowledge_graph()
        stats = kg.get_stats()
        
        return {
            "status": "healthy",
            "connected": True,
            "stats": stats,
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
        }


@router.get("/all-nodes")
async def get_all_nodes(limit: int = Query(50, description="返回数量")):
    """调试：获取所有节点"""
    try:
        kg = get_knowledge_graph()
        
        with kg.session() as session:
            query = """
            MATCH (n)
            RETURN n, labels(n) as labels, elementId(n) as id
            LIMIT $limit
            """
            records = session.run(query, limit=limit)
            
            nodes = []
            for record in records:
                node = record["n"]
                nodes.append({
                    "id": record["id"],
                    "labels": record["labels"],
                    "properties": dict(node),
                })
            
            return {
                "count": len(nodes),
                "nodes": nodes,
            }
            
    except Exception as e:
        logger.error(f"Get all nodes failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cypher")
async def run_cypher(
    query: str = Query(..., description="Cypher 查询"),
):
    """调试：直接运行 Cypher 查询"""
    try:
        kg = get_knowledge_graph()
        
        with kg.session() as session:
            records = session.run(query)
            
            results = []
            for record in records:
                row = {}
                for key in record.keys():
                    value = record[key]
                    # 处理 Neo4j 节点对象
                    if hasattr(value, 'items'):
                        row[key] = dict(value)
                    elif hasattr(value, 'labels'):
                        row[key] = {
                            "labels": list(value.labels),
                            "properties": dict(value),
                        }
                    else:
                        row[key] = value
                results.append(row)
            
            return {"results": results}
            
    except Exception as e:
        logger.error(f"Cypher query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug-search")
async def debug_search(q: str = Query(..., description="搜索词")):
    """调试：测试 full_text_search 并返回详细信息"""
    try:
        kg = get_knowledge_graph()
        
        # 1. 先用 Cypher 直接查
        direct_results = []
        with kg.session() as session:
            cypher = """
            MATCH (n)
            WHERE toLower(n.name) CONTAINS toLower($search_term)
               OR toLower(coalesce(n.text, '')) CONTAINS toLower($search_term)
            RETURN n, elementId(n) as id, labels(n) as node_labels
            LIMIT 10
            """
            records = session.run(cypher, search_term=q)
            for record in records:
                direct_results.append({
                    "id": record["id"],
                    "labels": record["node_labels"],
                    "properties": dict(record["n"]),
                })
        
        # 2. 用 full_text_search 方法
        nodes = kg.full_text_search(q, limit=10)
        method_results = [n.to_dict() for n in nodes]
        
        return {
            "query": q,
            "direct_cypher_count": len(direct_results),
            "direct_cypher_results": direct_results,
            "method_count": len(method_results),
            "method_results": method_results,
        }
        
    except Exception as e:
        logger.error(f"Debug search failed: {e}")
        return {"error": str(e)}

