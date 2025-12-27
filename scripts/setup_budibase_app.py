#!/usr/bin/env python3
"""
Budibase 应用自动创建脚本
创建 AI Data Factory 管理控制台应用
"""
import os
import json
import requests
import time

# Budibase 配置
BUDIBASE_URL = os.getenv("BUDIBASE_URL", "http://localhost:10000")
BUDIBASE_API_KEY = os.getenv("BUDIBASE_API_KEY", "")

# API 服务地址（从 Budibase 容器视角）
API_URL = os.getenv("API_INTERNAL_URL", "http://api:8000")


def get_headers():
    """获取 API 请求头"""
    return {
        "x-budibase-api-key": BUDIBASE_API_KEY,
        "Content-Type": "application/json",
    }


def create_app():
    """创建应用"""
    print("创建 Budibase 应用...")
    
    response = requests.post(
        f"{BUDIBASE_URL}/api/public/v1/applications",
        headers=get_headers(),
        json={
            "name": "AI Data Factory 控制台",
            "useTemplate": False,
        }
    )
    
    if response.status_code == 200:
        app = response.json()
        print(f"✓ 应用创建成功: {app.get('_id')}")
        return app
    else:
        print(f"✗ 创建失败: {response.text}")
        return None


def create_datasource(app_id: str):
    """创建 REST 数据源"""
    print("创建 API 数据源...")
    
    response = requests.post(
        f"{BUDIBASE_URL}/api/public/v1/applications/{app_id}/datasources",
        headers=get_headers(),
        json={
            "name": "AI Data Factory API",
            "type": "REST",
            "config": {
                "url": API_URL,
                "defaultHeaders": {
                    "Content-Type": "application/json"
                }
            }
        }
    )
    
    if response.status_code == 200:
        ds = response.json()
        print(f"✓ 数据源创建成功: {ds.get('_id')}")
        return ds
    else:
        print(f"✗ 创建失败: {response.text}")
        return None


def create_queries(app_id: str, datasource_id: str):
    """创建 API 查询"""
    print("创建 API 查询...")
    
    queries = [
        {
            "name": "获取图谱统计",
            "queryVerb": "read",
            "fields": {
                "path": "/v1/kg/stats",
                "headers": {},
                "queryString": ""
            }
        },
        {
            "name": "搜索知识图谱",
            "queryVerb": "read",
            "fields": {
                "path": "/v1/kg/search",
                "headers": {},
                "queryString": "q={{query}}"
            },
            "parameters": [
                {"name": "query", "default": ""}
            ]
        },
        {
            "name": "获取热门内容",
            "queryVerb": "read",
            "fields": {
                "path": "/v1/recommend/popular",
                "headers": {},
                "queryString": "limit=10"
            }
        },
        {
            "name": "获取推荐",
            "queryVerb": "read",
            "fields": {
                "path": "/v1/recommend",
                "headers": {},
                "queryString": "user_id={{user_id}}&limit=5"
            },
            "parameters": [
                {"name": "user_id", "default": ""}
            ]
        },
        {
            "name": "抽取实体",
            "queryVerb": "create",
            "fields": {
                "path": "/v1/kg/extract",
                "headers": {"Content-Type": "application/json"},
                "requestBody": '{"text": "{{text}}"}'
            },
            "parameters": [
                {"name": "text", "default": ""}
            ]
        },
        {
            "name": "导入到图谱",
            "queryVerb": "create",
            "fields": {
                "path": "/v1/kg/import",
                "headers": {"Content-Type": "application/json"},
                "requestBody": '{"text": "{{text}}", "extract_relations": true}'
            },
            "parameters": [
                {"name": "text", "default": ""}
            ]
        },
        {
            "name": "生成摘要",
            "queryVerb": "create",
            "fields": {
                "path": "/v1/summary/generate",
                "headers": {"Content-Type": "application/json"},
                "requestBody": '{"conversation_id": "{{conversation_id}}", "turns": []}'
            },
            "parameters": [
                {"name": "conversation_id", "default": ""}
            ]
        },
        {
            "name": "分析图片",
            "queryVerb": "create",
            "fields": {
                "path": "/v1/vision/analyze-url",
                "headers": {"Content-Type": "application/json"},
                "requestBody": '{"image_url": "{{image_url}}", "question": "{{question}}", "task_type": "general_qa"}'
            },
            "parameters": [
                {"name": "image_url", "default": ""},
                {"name": "question", "default": "描述这张图片"}
            ]
        }
    ]
    
    created = []
    for query in queries:
        query["datasourceId"] = datasource_id
        
        response = requests.post(
            f"{BUDIBASE_URL}/api/public/v1/applications/{app_id}/queries",
            headers=get_headers(),
            json=query
        )
        
        if response.status_code == 200:
            q = response.json()
            print(f"  ✓ 查询 '{query['name']}' 创建成功")
            created.append(q)
        else:
            print(f"  ✗ 查询 '{query['name']}' 创建失败: {response.text}")
    
    return created


def create_screens(app_id: str, queries: list):
    """创建应用界面"""
    print("创建应用界面...")
    
    # Budibase 界面需要通过 UI 或更复杂的 API 创建
    # 这里只输出指导信息
    
    print("""
界面创建指南（需要在 Budibase UI 中手动完成）:

1. 仪表盘 (/dashboard)
   - 添加统计卡片显示: KU数量、图谱节点数、今日查询、用户数
   - 绑定 "获取图谱统计" 查询

2. 知识图谱 (/knowledge-graph)
   - 添加搜索表单
   - 添加结果表格，绑定 "搜索知识图谱" 查询
   - 添加实体导入表单，绑定 "导入到图谱" 查询

3. 图片分析 (/vision)
   - 添加图片 URL 输入框
   - 添加问题输入框
   - 添加分析按钮，绑定 "分析图片" 查询
   - 添加结果显示区域

4. 推荐管理 (/recommendations)
   - 添加热门内容表格，绑定 "获取热门内容" 查询
   - 添加用户推荐测试表单

5. 对话摘要 (/summaries)
   - 添加对话 ID 输入
   - 添加摘要生成按钮
   - 添加结果显示

注意: 请访问 http://localhost:10000 登录 Budibase 并完成界面设计
""")


def main():
    print("=" * 60)
    print("Budibase 应用自动创建")
    print("=" * 60)
    
    if not BUDIBASE_API_KEY:
        print("""
错误: 未设置 BUDIBASE_API_KEY

请先在 Budibase 中获取 API Key:
1. 登录 Budibase (http://localhost:10000)
2. 进入 Settings -> API
3. 生成 API Key
4. 设置环境变量: export BUDIBASE_API_KEY=your_key
5. 重新运行此脚本
""")
        return
    
    # 创建应用
    app = create_app()
    if not app:
        return
    
    app_id = app.get("_id")
    
    # 创建数据源
    datasource = create_datasource(app_id)
    if not datasource:
        return
    
    datasource_id = datasource.get("_id")
    
    # 创建查询
    queries = create_queries(app_id, datasource_id)
    
    # 创建界面（输出指南）
    create_screens(app_id, queries)
    
    print("\n" + "=" * 60)
    print("应用创建完成!")
    print("=" * 60)
    print(f"""
应用 ID: {app_id}
数据源 ID: {datasource_id}
查询数量: {len(queries)}

下一步:
1. 访问 Budibase: http://localhost:10000
2. 打开 "AI Data Factory 控制台" 应用
3. 设计界面并发布应用
""")


if __name__ == "__main__":
    main()

