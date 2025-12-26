# 添加新场景指南

本文档说明如何向 AI Data Factory 添加新的业务场景（如工业AOI视觉检测、智能制造等）。

## 1. 场景结构概述

系统采用三层结构管理知识：

```
场景 (Scenario)
├── 解决方案 (Solution)
│   ├── 材料 (Material) - PDF/PPT/文档
│   ├── 材料 (Material)
│   └── ...
├── 解决方案 (Solution)
│   └── ...
└── Prompt 模板 (按意图类型)
```

## 2. 添加新场景

### 方式一：代码配置（推荐）

编辑 `services/api/app/services/intent_scenario.py`：

```python
# 在 SCENARIO_CONFIGS 字典中添加
"your_scenario_id": ScenarioConfig(
    id="your_scenario_id",
    name="场景名称",
    domain="所属领域",
    keywords=["关键词1", "关键词2", ...],  # 用于意图匹配
    intents=[IntentType.SOLUTION_RECOMMENDATION, IntentType.TECHNICAL_QA],
    prompt_template="""你是一位 XXX 专家。
    
在回答时请注意：
1. ...
2. ...
""",
    retrieval_config={
        "boost_fields": {"field1": 2.0},
        "filter_tags": ["tag1", "tag2"],
    }
),
```

### 方式二：数据库配置

通过 API 添加场景：

```bash
curl -X POST http://localhost:8000/api/scenarios \
  -H "Content-Type: application/json" \
  -d '{
    "id": "aoi_inspection",
    "name": "工业AOI视觉检测",
    "domain": "工业智能",
    "keywords": ["AOI", "视觉检测", "缺陷检测"],
    "description": "工业AOI自动光学检测场景"
  }'
```

## 3. 添加 Prompt 模板

在 `PROMPT_TEMPLATES` 字典中为场景添加不同意图的模板：

```python
# (意图类型, 场景ID) -> 模板配置
(IntentType.SOLUTION_RECOMMENDATION, "your_scenario_id"): {
    "system_prompt": """...""",
    "context_template": """...""",
    "output_format": """...""",
},
```

## 4. 上传场景材料

### 4.1 准备材料

组织材料目录结构：

```
materials/
└── aoi_inspection/           # 场景目录
    ├── pcb_detection/        # 解决方案目录
    │   ├── whitepaper.pdf    # 白皮书
    │   ├── architecture.pptx # 架构文档
    │   └── case_study.docx   # 案例研究
    └── smt_inspection/       # 另一个解决方案
        └── ...
```

### 4.2 上传到 MinIO

```bash
# 上传整个场景目录
docker compose exec api python -c "
from minio import Minio
import os

client = Minio('minio:9000', 
    access_key='$MINIO_ROOT_USER',
    secret_key='$MINIO_ROOT_PASSWORD',
    secure=False)

# 上传文件
client.fput_object('uploads', 
    'aoi_inspection/pcb_detection/whitepaper.pdf',
    '/path/to/whitepaper.pdf')
"
```

或通过 MinIO 控制台：
1. 访问 http://your-ip:9001
2. 进入 `uploads` bucket
3. 创建场景目录并上传文件

### 4.3 触发处理 Pipeline

```bash
# 触发 Airflow DAG 处理新材料
docker compose exec airflow airflow dags trigger ingest_to_bronze

# 或通过 API
curl -X POST http://localhost:8000/api/pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{"dag_id": "full_pipeline"}'
```

## 5. 验证场景配置

### 5.1 测试意图识别

```bash
curl http://localhost:8000/api/conversation/intents \
  -H "Content-Type: application/json" \
  -d '{"query": "推荐一个PCB AOI检测方案"}'
```

预期返回：
```json
{
  "intent": "solution_recommendation",
  "scenario": "aoi_inspection",
  "confidence": 0.85
}
```

### 5.2 测试对话

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "messages": [{"role": "user", "content": "如何选择AOI相机和光源？"}]
  }'
```

## 6. 内置场景示例

### 6.1 工业AOI视觉检测 (aoi_inspection)

**关键词**: AOI, 视觉检测, 缺陷检测, PCB检测, SMT, 深度学习, 机器视觉

**支持的意图**:
- 方案推荐: "推荐一个PCB AOI检测方案"
- 技术问答: "AOI相机分辨率怎么选择"
- 故障诊断: "AOI误检率太高怎么办"
- 操作指南: "如何训练缺陷检测模型"

**典型问题**:
- "我们生产手机主板，需要检测焊点和贴片质量，推荐什么AOI方案？"
- "深度学习AOI和传统规则AOI有什么区别？"
- "AOI检测漏检率太高，应该如何优化？"
- "如何搭建AOI缺陷检测的标注和训练流程？"

### 6.2 网络安全 (network_security)

**关键词**: 网络安全, 防火墙, 入侵, 零信任, SASE

### 6.3 云架构 (cloud_architecture)

**关键词**: 云, AWS, 阿里云, K8s, 微服务

### 6.4 API设计 (api_design)

**关键词**: API, RESTful, GraphQL, OpenAPI

## 7. 最佳实践

1. **关键词覆盖**: 添加足够的关键词，包括同义词、缩写、中英文
2. **Prompt 优化**: 根据实际问答效果持续迭代 Prompt
3. **材料质量**: 上传高质量、结构清晰的文档
4. **分层组织**: 按 场景 -> 解决方案 -> 材料 组织内容
5. **持续反馈**: 收集用户反馈，优化检索和生成效果

