#!/usr/bin/env python3
"""
n8n 工作流自动创建脚本
创建 AI Data Factory 自动化工作流
"""
import os
import json
import requests
import time

# n8n 配置
N8N_URL = os.getenv("N8N_URL", "http://localhost:5678")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")

# API 服务地址（从 n8n 容器视角）
API_URL = os.getenv("API_INTERNAL_URL", "http://api:8000")


def get_headers():
    """获取 API 请求头"""
    headers = {
        "Content-Type": "application/json",
    }
    if N8N_API_KEY:
        headers["X-N8N-API-KEY"] = N8N_API_KEY
    return headers


def create_workflow(workflow_data: dict) -> dict:
    """创建工作流"""
    response = requests.post(
        f"{N8N_URL}/api/v1/workflows",
        headers=get_headers(),
        json=workflow_data,
    )
    
    if response.status_code in [200, 201]:
        return response.json()
    else:
        print(f"  创建失败: {response.status_code} - {response.text}")
        return None


def activate_workflow(workflow_id: str) -> bool:
    """激活工作流"""
    response = requests.patch(
        f"{N8N_URL}/api/v1/workflows/{workflow_id}",
        headers=get_headers(),
        json={"active": True},
    )
    return response.status_code == 200


# ==================== 工作流定义 ====================

def get_document_processing_workflow():
    """文档处理通知工作流"""
    return {
        "name": "Document Processing Notification",
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": "document-processed",
                    "responseMode": "responseNode",
                    "options": {}
                },
                "id": "webhook-1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 300]
            },
            {
                "parameters": {
                    "url": f"{API_URL}/v1/kg/import",
                    "sendBody": True,
                    "bodyParameters": {
                        "parameters": [
                            {
                                "name": "text",
                                "value": "={{ $json.title }} {{ $json.summary }}"
                            },
                            {
                                "name": "extract_relations",
                                "value": "true"
                            }
                        ]
                    },
                    "options": {}
                },
                "id": "http-1",
                "name": "Import to KG",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [450, 300]
            },
            {
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{ { \"status\": \"processed\", \"kg_import\": $json } }}"
                },
                "id": "respond-1",
                "name": "Respond to Webhook",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [650, 300]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Import to KG", "type": "main", "index": 0}]]
            },
            "Import to KG": {
                "main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }


def get_feedback_analysis_workflow():
    """反馈分析工作流"""
    return {
        "name": "Daily Feedback Analysis",
        "nodes": [
            {
                "parameters": {
                    "rule": {
                        "interval": [{"field": "hours", "hoursInterval": 24}]
                    }
                },
                "id": "schedule-1",
                "name": "Daily Trigger",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1,
                "position": [250, 300]
            },
            {
                "parameters": {
                    "url": f"{API_URL}/v1/debug/feedback-report",
                    "options": {}
                },
                "id": "http-2",
                "name": "Get Feedback Report",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [450, 300]
            },
            {
                "parameters": {
                    "conditions": {
                        "number": [
                            {
                                "value1": "={{ $json.health_score }}",
                                "operation": "smaller",
                                "value2": 70
                            }
                        ]
                    }
                },
                "id": "if-1",
                "name": "Health Check",
                "type": "n8n-nodes-base.if",
                "typeVersion": 1,
                "position": [650, 300]
            },
            {
                "parameters": {
                    "functionCode": "return [{ json: { alert: 'Low health score: ' + $input.first().json.health_score, report: $input.first().json } }];"
                },
                "id": "code-1",
                "name": "Generate Alert",
                "type": "n8n-nodes-base.code",
                "typeVersion": 1,
                "position": [850, 200]
            }
        ],
        "connections": {
            "Daily Trigger": {
                "main": [[{"node": "Get Feedback Report", "type": "main", "index": 0}]]
            },
            "Get Feedback Report": {
                "main": [[{"node": "Health Check", "type": "main", "index": 0}]]
            },
            "Health Check": {
                "main": [
                    [{"node": "Generate Alert", "type": "main", "index": 0}],
                    []
                ]
            }
        },
        "settings": {}
    }


def get_kg_sync_workflow():
    """知识图谱同步工作流"""
    return {
        "name": "KG Stats Sync",
        "nodes": [
            {
                "parameters": {
                    "rule": {
                        "interval": [{"field": "hours", "hoursInterval": 6}]
                    }
                },
                "id": "schedule-2",
                "name": "Every 6 Hours",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1,
                "position": [250, 300]
            },
            {
                "parameters": {
                    "url": f"{API_URL}/v1/kg/stats",
                    "options": {}
                },
                "id": "http-3",
                "name": "Get KG Stats",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [450, 300]
            },
            {
                "parameters": {
                    "functionCode": "const stats = $input.first().json; console.log('KG Stats:', JSON.stringify(stats)); return [{ json: { timestamp: new Date().toISOString(), nodes: stats.nodes, edges: stats.edges, labels: stats.labels }}];"
                },
                "id": "code-2",
                "name": "Log Stats",
                "type": "n8n-nodes-base.code",
                "typeVersion": 1,
                "position": [650, 300]
            }
        ],
        "connections": {
            "Every 6 Hours": {
                "main": [[{"node": "Get KG Stats", "type": "main", "index": 0}]]
            },
            "Get KG Stats": {
                "main": [[{"node": "Log Stats", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }


def get_recommendation_workflow():
    """推荐触发工作流"""
    return {
        "name": "User Query Recommendation",
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": "user-query",
                    "responseMode": "responseNode",
                    "options": {}
                },
                "id": "webhook-2",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 300]
            },
            {
                "parameters": {
                    "url": f"{API_URL}/v1/recommend/track",
                    "sendBody": True,
                    "bodyParameters": {
                        "parameters": [
                            {"name": "user_id", "value": "={{ $json.user_id }}"},
                            {"name": "behavior_type", "value": "query"},
                            {"name": "query", "value": "={{ $json.query }}"}
                        ]
                    },
                    "options": {}
                },
                "id": "http-4",
                "name": "Track Query",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [450, 300]
            },
            {
                "parameters": {
                    "url": f"{API_URL}/v1/recommend",
                    "qs": {
                        "parameters": [
                            {"name": "user_id", "value": "={{ $json.user_id }}"},
                            {"name": "limit", "value": "5"}
                        ]
                    },
                    "options": {}
                },
                "id": "http-5",
                "name": "Get Recommendations",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [650, 300]
            },
            {
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{ $json }}"
                },
                "id": "respond-2",
                "name": "Return Response",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [850, 300]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Track Query", "type": "main", "index": 0}]]
            },
            "Track Query": {
                "main": [[{"node": "Get Recommendations", "type": "main", "index": 0}]]
            },
            "Get Recommendations": {
                "main": [[{"node": "Return Response", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }


def main():
    print("=" * 60)
    print("n8n 工作流自动创建")
    print("=" * 60)
    
    # 检查 n8n 是否可访问
    try:
        response = requests.get(f"{N8N_URL}/api/v1/workflows", headers=get_headers(), timeout=5)
        if response.status_code == 401:
            print(f"""
注意: n8n API 需要认证

请先配置 n8n API Key:
1. 访问 n8n: {N8N_URL}
2. 进入 Settings -> API
3. 生成 API Key
4. 设置环境变量: export N8N_API_KEY=your_key
5. 重新运行此脚本

或者，如果 n8n 没有启用 API 认证，请检查 n8n 配置。
""")
        elif response.status_code != 200:
            print(f"n8n API 响应异常: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"""
错误: 无法连接到 n8n ({N8N_URL})

请确保:
1. n8n 服务已启动: docker compose up -d n8n
2. n8n 端口正确: 默认 5678
""")
        return
    
    workflows = [
        ("文档处理通知", get_document_processing_workflow()),
        ("反馈分析报告", get_feedback_analysis_workflow()),
        ("知识图谱同步", get_kg_sync_workflow()),
        ("用户推荐", get_recommendation_workflow()),
    ]
    
    created_count = 0
    
    for name, workflow_data in workflows:
        print(f"\n创建工作流: {name}")
        
        result = create_workflow(workflow_data)
        
        if result:
            workflow_id = result.get("id")
            print(f"  ✓ 创建成功: {workflow_id}")
            
            # 尝试激活
            if activate_workflow(workflow_id):
                print(f"  ✓ 已激活")
            else:
                print(f"  ⚠ 激活失败（需手动激活）")
            
            created_count += 1
        else:
            print(f"  ✗ 创建失败")
    
    print("\n" + "=" * 60)
    print(f"工作流创建完成: {created_count}/{len(workflows)}")
    print("=" * 60)
    print(f"""
下一步:
1. 访问 n8n: {N8N_URL}
2. 检查并激活工作流
3. 测试 Webhook 端点

Webhook 端点:
  - 文档处理: POST {N8N_URL}/webhook/document-processed
  - 用户查询: POST {N8N_URL}/webhook/user-query
""")


if __name__ == "__main__":
    main()

