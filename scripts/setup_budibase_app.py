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
            "name": "AI Data Factory Console",
            "useTemplate": False,
        }
    )
    
    print(f"  响应状态: {response.status_code}")
    
    if response.status_code in [200, 201]:
        try:
            app = response.json()
            # Budibase API 可能返回 data 包装或直接返回
            if isinstance(app, dict):
                app_data = app.get("data", app)
                app_id = app_data.get("_id") or app_data.get("appId") or app_data.get("id")
                print(f"✓ 应用创建成功: {app_id}")
                print(f"  完整响应: {app}")
                return {"_id": app_id, **app_data}
        except Exception as e:
            print(f"  解析响应失败: {e}")
            print(f"  原始响应: {response.text}")
        return None
    else:
        print(f"✗ 创建失败: {response.text}")
        return None


def create_datasource(app_id: str):
    """创建 REST 数据源"""
    print("创建 API 数据源...")
    print("  注意: Budibase Public API 不支持创建数据源，请手动配置")
    print(f"""
  手动配置步骤:
  1. 打开应用: http://localhost:10000
  2. 进入应用 -> Data -> Add data source -> REST API
  3. 配置:
     - Name: AI Data Factory API
     - URL: {API_URL}
     - Default Headers: Content-Type: application/json
""")
    # 返回模拟的数据源 ID
    return {"_id": "manual-config-required"}


def create_queries(app_id: str, datasource_id: str):
    """创建 API 查询"""
    print("创建 API 查询...")
    print("  注意: Budibase Public API 不支持创建查询，请手动配置")
    
    queries_info = [
        ("获取图谱统计", "GET", "/v1/kg/stats"),
        ("搜索知识图谱", "GET", "/v1/kg/search?q={{query}}"),
        ("获取所有节点", "GET", "/v1/kg/all-nodes?limit=50"),
        ("获取热门内容", "GET", "/v1/recommend/popular?limit=10"),
        ("获取推荐", "GET", "/v1/recommend?user_id={{user_id}}&limit=5"),
        ("抽取实体", "POST", "/v1/kg/extract"),
        ("导入到图谱", "POST", "/v1/kg/import"),
        ("生成摘要", "POST", "/v1/summary/generate"),
        ("分析图片", "POST", "/v1/vision/analyze-url"),
    ]
    
    print(f"""
  请在 Budibase 中手动创建以下查询:
  
  | 名称 | 方法 | 路径 |
  |------|------|------|""")
    
    for name, method, path in queries_info:
        print(f"  | {name} | {method} | {path} |")
    
    print(f"""
  POST 请求的 Body 示例:
  - 抽取实体: {{"text": "{{{{text}}}}"}}
  - 导入图谱: {{"text": "{{{{text}}}}", "extract_relations": true}}
  - 生成摘要: {{"conversation_id": "{{{{conv_id}}}}", "turns": []}}
  - 分析图片: {{"image_url": "{{{{url}}}}", "question": "{{{{q}}}}"}}
""")
    
    return []


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

