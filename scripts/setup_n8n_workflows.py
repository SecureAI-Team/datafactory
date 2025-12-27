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


def get_file_upload_trigger_airflow_workflow():
    """文件上传触发 Airflow 工作流"""
    # Airflow 服务地址（从 n8n 容器视角）
    airflow_url = os.getenv("AIRFLOW_URL", "http://airflow:8080")
    airflow_user = os.getenv("AIRFLOW_USER", "admin")
    airflow_pass = os.getenv("AIRFLOW_PASSWORD", "admin")
    
    return {
        "name": "File Upload Trigger Airflow",
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": "file-uploaded",
                    "responseMode": "responseNode",
                    "options": {}
                },
                "id": "webhook-upload",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 300]
            },
            {
                "parameters": {
                    "url": f"{airflow_url}/api/v1/dags/ingest_to_bronze/dagRuns",
                    "authentication": "genericCredentialType",
                    "genericAuthType": "httpBasicAuth",
                    "sendBody": True,
                    "specifyBody": "json",
                    "jsonBody": '={"conf": {"filename": "{{ $json.filename }}", "bucket": "{{ $json.bucket || \'uploads\' }}"}}',
                    "options": {
                        "timeout": 30000
                    }
                },
                "id": "http-airflow",
                "name": "Trigger Airflow DAG",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [450, 300],
                "credentials": {}
            },
            {
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{ { \"status\": \"triggered\", \"dag_run\": $json } }}"
                },
                "id": "respond-upload",
                "name": "Respond to Webhook",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [650, 300]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Trigger Airflow DAG", "type": "main", "index": 0}]]
            },
            "Trigger Airflow DAG": {
                "main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]
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


def get_pipeline_complete_notification_workflow():
    """Pipeline 完成通知工作流"""
    return {
        "name": "Pipeline Complete Notification",
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": "pipeline-complete",
                    "responseMode": "responseNode",
                    "options": {}
                },
                "id": "webhook-pipeline",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 300]
            },
            {
                "parameters": {
                    "functionCode": """
const data = $input.first().json;
const status = data.status || 'unknown';
const dagId = data.dag_id || 'unknown';
const runId = data.run_id || 'unknown';
const duration = data.duration || 0;

// 构建通知消息
const message = {
    title: status === 'success' ? '✅ Pipeline 完成' : '❌ Pipeline 失败',
    dag: dagId,
    run_id: runId,
    status: status,
    duration_seconds: duration,
    timestamp: new Date().toISOString()
};

// 这里可以扩展：发送邮件、Slack、钉钉等
console.log('Pipeline notification:', JSON.stringify(message));

return [{ json: message }];
"""
                },
                "id": "code-pipeline",
                "name": "Build Notification",
                "type": "n8n-nodes-base.code",
                "typeVersion": 1,
                "position": [450, 300]
            },
            {
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{ $json }}"
                },
                "id": "respond-pipeline",
                "name": "Respond",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [650, 300]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Build Notification", "type": "main", "index": 0}]]
            },
            "Build Notification": {
                "main": [[{"node": "Respond", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }


def get_dq_alert_workflow():
    """数据质量告警工作流"""
    return {
        "name": "Data Quality Alert",
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": "dq-alert",
                    "responseMode": "responseNode",
                    "options": {}
                },
                "id": "webhook-dq",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 300]
            },
            {
                "parameters": {
                    "conditions": {
                        "string": [
                            {
                                "value1": "={{ $json.status }}",
                                "operation": "equals",
                                "value2": "failed"
                            }
                        ]
                    }
                },
                "id": "if-dq",
                "name": "Check Failed",
                "type": "n8n-nodes-base.if",
                "typeVersion": 1,
                "position": [450, 300]
            },
            {
                "parameters": {
                    "functionCode": """
const data = $input.first().json;
const alert = {
    severity: 'high',
    title: '🚨 数据质量检查失败',
    ku_id: data.ku_id || 'unknown',
    checks_failed: data.failed_checks || [],
    timestamp: new Date().toISOString(),
    action_required: '请检查并修复数据质量问题'
};

console.log('DQ Alert:', JSON.stringify(alert));
return [{ json: alert }];
"""
                },
                "id": "code-dq",
                "name": "Build Alert",
                "type": "n8n-nodes-base.code",
                "typeVersion": 1,
                "position": [650, 200]
            },
            {
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{ { \"alert_sent\": true, \"details\": $json } }}"
                },
                "id": "respond-dq-alert",
                "name": "Respond Alert",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [850, 200]
            },
            {
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{ { \"alert_sent\": false, \"reason\": \"check passed\" } }}"
                },
                "id": "respond-dq-ok",
                "name": "Respond OK",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [650, 400]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Check Failed", "type": "main", "index": 0}]]
            },
            "Check Failed": {
                "main": [
                    [{"node": "Build Alert", "type": "main", "index": 0}],
                    [{"node": "Respond OK", "type": "main", "index": 0}]
                ]
            },
            "Build Alert": {
                "main": [[{"node": "Respond Alert", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }


def get_prompt_optimization_workflow():
    """Prompt 优化执行工作流"""
    return {
        "name": "Weekly Prompt Optimization",
        "nodes": [
            {
                "parameters": {
                    "rule": {
                        "interval": [{"field": "weeks", "weeksInterval": 1}]
                    }
                },
                "id": "schedule-prompt",
                "name": "Weekly Trigger",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1,
                "position": [250, 300]
            },
            {
                "parameters": {
                    "url": f"{API_URL}/v1/debug/feedback-report",
                    "options": {}
                },
                "id": "http-feedback",
                "name": "Get Feedback Stats",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [450, 300]
            },
            {
                "parameters": {
                    "url": f"{API_URL}/v1/debug/optimize-prompts",
                    "sendBody": True,
                    "specifyBody": "json",
                    "jsonBody": '{"auto_apply": false}',
                    "options": {}
                },
                "id": "http-optimize",
                "name": "Generate Optimization",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [650, 300]
            },
            {
                "parameters": {
                    "functionCode": """
const feedback = $input.all()[0].json;
const optimization = $input.all()[1]?.json || {};

const report = {
    timestamp: new Date().toISOString(),
    feedback_summary: {
        total: feedback.total_feedbacks || 0,
        positive_rate: feedback.positive_rate || 0,
        health_score: feedback.health_score || 0
    },
    optimization_suggestions: optimization.suggestions || [],
    new_examples: optimization.new_examples || []
};

console.log('Weekly optimization report:', JSON.stringify(report));
return [{ json: report }];
"""
                },
                "id": "code-report",
                "name": "Build Report",
                "type": "n8n-nodes-base.code",
                "typeVersion": 1,
                "position": [850, 300]
            }
        ],
        "connections": {
            "Weekly Trigger": {
                "main": [[{"node": "Get Feedback Stats", "type": "main", "index": 0}]]
            },
            "Get Feedback Stats": {
                "main": [[{"node": "Generate Optimization", "type": "main", "index": 0}]]
            },
            "Generate Optimization": {
                "main": [[{"node": "Build Report", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }


def get_conversation_summary_workflow():
    """长对话自动摘要工作流"""
    return {
        "name": "Auto Conversation Summary",
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": "conversation-long",
                    "responseMode": "responseNode",
                    "options": {}
                },
                "id": "webhook-conv",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 300]
            },
            {
                "parameters": {
                    "conditions": {
                        "number": [
                            {
                                "value1": "={{ $json.turn_count }}",
                                "operation": "largerEqual",
                                "value2": 10
                            }
                        ]
                    }
                },
                "id": "if-long",
                "name": "Check Long Conversation",
                "type": "n8n-nodes-base.if",
                "typeVersion": 1,
                "position": [450, 300]
            },
            {
                "parameters": {
                    "url": f"{API_URL}/v1/summary/generate",
                    "sendBody": True,
                    "bodyParameters": {
                        "parameters": [
                            {"name": "conversation_id", "value": "={{ $json.conversation_id }}"}
                        ]
                    },
                    "options": {}
                },
                "id": "http-summary",
                "name": "Generate Summary",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [650, 200]
            },
            {
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{ { \"summary_generated\": true, \"summary\": $json } }}"
                },
                "id": "respond-summary",
                "name": "Respond Summary",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [850, 200]
            },
            {
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{ { \"summary_generated\": false, \"reason\": \"conversation too short\" } }}"
                },
                "id": "respond-skip",
                "name": "Respond Skip",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [650, 400]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Check Long Conversation", "type": "main", "index": 0}]]
            },
            "Check Long Conversation": {
                "main": [
                    [{"node": "Generate Summary", "type": "main", "index": 0}],
                    [{"node": "Respond Skip", "type": "main", "index": 0}]
                ]
            },
            "Generate Summary": {
                "main": [[{"node": "Respond Summary", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }


def get_vision_analysis_workflow():
    """图片分析处理工作流"""
    return {
        "name": "Vision Analysis Pipeline",
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": "analyze-image",
                    "responseMode": "responseNode",
                    "options": {}
                },
                "id": "webhook-vision",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 300]
            },
            {
                "parameters": {
                    "url": f"{API_URL}/v1/vision/analyze-url",
                    "sendBody": True,
                    "bodyParameters": {
                        "parameters": [
                            {"name": "image_url", "value": "={{ $json.image_url }}"},
                            {"name": "question", "value": "={{ $json.question || '描述这张图片的内容' }}"}
                        ]
                    },
                    "options": {}
                },
                "id": "http-vision",
                "name": "Analyze Image",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [450, 300]
            },
            {
                "parameters": {
                    "url": f"{API_URL}/v1/kg/import",
                    "sendBody": True,
                    "bodyParameters": {
                        "parameters": [
                            {"name": "text", "value": "={{ 'Image analysis: ' + $json.analysis }}"},
                            {"name": "extract_relations", "value": "true"}
                        ]
                    },
                    "options": {}
                },
                "id": "http-kg-import",
                "name": "Import to KG",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [650, 300]
            },
            {
                "parameters": {
                    "respondWith": "json",
                    "responseBody": "={{ { \"analysis\": $input.all()[0].json, \"kg_import\": $json } }}"
                },
                "id": "respond-vision",
                "name": "Respond",
                "type": "n8n-nodes-base.respondToWebhook",
                "typeVersion": 1,
                "position": [850, 300]
            }
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Analyze Image", "type": "main", "index": 0}]]
            },
            "Analyze Image": {
                "main": [[{"node": "Import to KG", "type": "main", "index": 0}]]
            },
            "Import to KG": {
                "main": [[{"node": "Respond", "type": "main", "index": 0}]]
            }
        },
        "settings": {}
    }


def get_system_health_check_workflow():
    """系统健康检查工作流"""
    return {
        "name": "System Health Check",
        "nodes": [
            {
                "parameters": {
                    "rule": {
                        "interval": [{"field": "minutes", "minutesInterval": 30}]
                    }
                },
                "id": "schedule-health",
                "name": "Every 30 Minutes",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1,
                "position": [250, 300]
            },
            {
                "parameters": {
                    "url": f"{API_URL}/health",
                    "options": {"timeout": 10000}
                },
                "id": "http-api-health",
                "name": "Check API",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [450, 300]
            },
            {
                "parameters": {
                    "url": f"{API_URL}/v1/kg/stats",
                    "options": {"timeout": 10000}
                },
                "id": "http-kg-health",
                "name": "Check KG",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [650, 300]
            },
            {
                "parameters": {
                    "functionCode": """
const apiHealth = $input.all()[0]?.json || {};
const kgHealth = $input.all()[1]?.json || {};

const status = {
    timestamp: new Date().toISOString(),
    api: apiHealth.status || 'unknown',
    kg_nodes: kgHealth.total_nodes || 0,
    kg_edges: kgHealth.total_edges || 0,
    overall: 'healthy'
};

if (apiHealth.status !== 'healthy') {
    status.overall = 'degraded';
    console.log('ALERT: API unhealthy');
}

console.log('Health check:', JSON.stringify(status));
return [{ json: status }];
"""
                },
                "id": "code-health",
                "name": "Aggregate Status",
                "type": "n8n-nodes-base.code",
                "typeVersion": 1,
                "position": [850, 300]
            }
        ],
        "connections": {
            "Every 30 Minutes": {
                "main": [[{"node": "Check API", "type": "main", "index": 0}]]
            },
            "Check API": {
                "main": [[{"node": "Check KG", "type": "main", "index": 0}]]
            },
            "Check KG": {
                "main": [[{"node": "Aggregate Status", "type": "main", "index": 0}]]
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
        # 核心 Pipeline 工作流
        ("文件上传触发Airflow", get_file_upload_trigger_airflow_workflow()),
        ("文档处理通知", get_document_processing_workflow()),
        ("Pipeline完成通知", get_pipeline_complete_notification_workflow()),
        ("数据质量告警", get_dq_alert_workflow()),
        
        # 智能分析工作流
        ("图片分析Pipeline", get_vision_analysis_workflow()),
        ("长对话自动摘要", get_conversation_summary_workflow()),
        ("用户推荐", get_recommendation_workflow()),
        
        # 定时任务工作流
        ("反馈分析报告", get_feedback_analysis_workflow()),
        ("知识图谱同步", get_kg_sync_workflow()),
        ("Prompt周优化", get_prompt_optimization_workflow()),
        ("系统健康检查", get_system_health_check_workflow()),
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
  - 文件上传:     POST {N8N_URL}/webhook/file-uploaded
  - 文档处理:     POST {N8N_URL}/webhook/document-processed
  - Pipeline完成: POST {N8N_URL}/webhook/pipeline-complete
  - 数据质量:     POST {N8N_URL}/webhook/dq-alert
  - 图片分析:     POST {N8N_URL}/webhook/analyze-image
  - 长对话摘要:   POST {N8N_URL}/webhook/conversation-long
  - 用户查询:     POST {N8N_URL}/webhook/user-query
""")


if __name__ == "__main__":
    main()

