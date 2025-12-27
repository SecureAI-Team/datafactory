#!/usr/bin/env python3
"""
Phase 5 升级脚本
智能能力扩展：多模态理解、知识图谱、智能推荐、对话摘要
"""
import subprocess
import sys
import os


def run_command(cmd: str, check: bool = True) -> bool:
    """运行命令"""
    print(f"\n>>> {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}")
        return False
    return True


def main():
    print("=" * 60)
    print("Phase 5 升级: 智能能力扩展")
    print("=" * 60)
    
    # 1. 运行数据库迁移
    print("\n[1/4] 运行数据库迁移...")
    run_command("docker compose run --rm api alembic upgrade head", check=False)
    
    # 2. 启动 Neo4j
    print("\n[2/4] 启动 Neo4j...")
    run_command("docker compose up -d neo4j", check=False)
    
    # 3. 重建 API 服务
    print("\n[3/4] 重建 API 服务...")
    run_command("docker compose build --no-cache api")
    run_command("docker compose up -d api")
    
    # 4. 验证新模块
    print("\n[4/4] 验证新模块...")
    
    # 测试视觉服务
    test_vision = """
docker compose exec -T api python -c "
from app.services.vision_service import get_vision_service, VisionTaskType
print('✓ VisionService loaded')
"
"""
    run_command(test_vision, check=False)
    
    # 测试知识图谱
    test_kg = """
docker compose exec -T api python -c "
from app.services.knowledge_graph import get_knowledge_graph
print('✓ KnowledgeGraph loaded')
"
"""
    run_command(test_kg, check=False)
    
    # 测试推荐引擎
    test_rec = """
docker compose exec -T api python -c "
from app.services.recommendation_engine import get_recommendation_engine
print('✓ RecommendationEngine loaded')
"
"""
    run_command(test_rec, check=False)
    
    # 测试摘要服务
    test_summary = """
docker compose exec -T api python -c "
from app.services.summary_service import get_summary_service
print('✓ SummaryService loaded')
"
"""
    run_command(test_summary, check=False)
    
    print("\n" + "=" * 60)
    print("Phase 5 升级完成!")
    print("=" * 60)
    print("""
新增功能:
  - 多模态理解: 图片问答、表格提取、OCR
  - 知识图谱: 实体/关系抽取、图谱查询、图谱增强检索
  - 智能推荐: 热门内容、协同过滤、个性化推荐
  - 对话摘要: 自动摘要、历史压缩

新增 API:
  - POST /v1/vision/analyze     - 图片分析
  - POST /v1/vision/extract-tables - 表格提取
  - GET  /v1/kg/query           - 知识图谱查询
  - POST /v1/kg/search          - 图谱搜索
  - GET  /v1/recommend          - 获取推荐
  - POST /v1/summary/generate   - 生成摘要

服务端口:
  - Neo4j Browser: http://localhost:7474
  - Neo4j Bolt: bolt://localhost:7687
""")


if __name__ == "__main__":
    main()

