# Phase 5 升级指南 - 智能能力扩展

## 概述

Phase 5 为 AI Data Factory 添加了四大智能能力：

| 功能 | 描述 | 关键技术 |
|------|------|----------|
| 多模态理解 | 图片问答、表格提取、OCR | Qwen-VL |
| 知识图谱 | 实体/关系抽取、图谱查询 | Neo4j |
| 智能推荐 | 热门内容、协同过滤、个性化 | 行为分析 |
| 对话摘要 | 自动摘要、历史压缩 | LLM |

---

## 升级步骤

### 1. 拉取最新代码

```bash
cd /opt/datafactory
git pull
```

### 2. 执行升级

```bash
make upgrade-phase5
```

该命令会：
- 运行数据库迁移
- 启动 Neo4j 服务
- 重建并重启 API 服务
- 验证新模块加载

### 3. 验证服务

```bash
# 检查所有服务状态
make status

# 验证 Neo4j
curl http://localhost:7474

# 测试 API 文档
curl http://localhost:8000/docs
```

---

## 新增 API

### 多模态理解 (Vision)

```bash
# 上传图片并分析
curl -X POST http://localhost:8000/v1/vision/analyze \
  -F "file=@image.png" \
  -F "question=这张图片里有什么？"

# 提取表格
curl -X POST http://localhost:8000/v1/vision/extract-tables \
  -F "file=@table.png"

# OCR
curl -X POST http://localhost:8000/v1/vision/ocr \
  -F "file=@document.png"
```

### 知识图谱 (KG)

```bash
# 查询实体关系
curl "http://localhost:8000/v1/kg/query?entity=AOI设备&relation=has_param"

# 搜索图谱
curl "http://localhost:8000/v1/kg/search?q=检测精度"

# 获取图谱统计
curl "http://localhost:8000/v1/kg/stats"

# 从文本抽取并导入
curl -X POST http://localhost:8000/v1/kg/import \
  -H "Content-Type: application/json" \
  -d '{"text": "AOI设备功率为500W，精度达到0.01mm"}'
```

### 智能推荐 (Recommend)

```bash
# 获取推荐
curl "http://localhost:8000/v1/recommend?user_id=test&limit=5"

# 获取热门内容
curl "http://localhost:8000/v1/recommend/popular?limit=10"

# 获取用户画像
curl "http://localhost:8000/v1/recommend/profile/test"

# 追问建议
curl -X POST http://localhost:8000/v1/recommend/follow-up \
  -H "Content-Type: application/json" \
  -d '{"query": "AOI设备功率是多少", "response": "AOI设备功率为500W", "intent_type": "parameter_query"}'
```

### 对话摘要 (Summary)

```bash
# 生成摘要
curl -X POST http://localhost:8000/v1/summary/generate \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv-123",
    "turns": [
      {"role": "user", "content": "AOI设备是什么？"},
      {"role": "assistant", "content": "AOI是自动光学检测设备..."}
    ]
  }'

# 获取对话摘要
curl "http://localhost:8000/v1/summary/conv-123"

# 压缩历史
curl -X POST http://localhost:8000/v1/summary/compress \
  -H "Content-Type: application/json" \
  -d '{"turns": [...], "max_turns": 5}'
```

---

## 新增服务

### Neo4j

- **Browser**: http://localhost:7474
- **Bolt**: bolt://localhost:7687
- **默认账号**: neo4j / neo4jpass

Neo4j 用于存储知识图谱，支持：
- 实体存储（产品、参数、场景等）
- 关系存储（产品-参数、产品-场景等）
- 图谱查询和遍历

---

## 数据库迁移

Phase 5 添加了以下表：

### user_behaviors
用户行为记录表

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | String | 用户ID |
| behavior_type | String | 行为类型 (query/view/click/feedback) |
| target_type | String | 目标类型 (ku/document/scenario) |
| target_id | String | 目标ID |
| query | Text | 查询内容 |
| metadata | JSONB | 附加数据 |

### ku_access_stats
KU 访问统计表

| 字段 | 类型 | 说明 |
|------|------|------|
| ku_id | String | KU ID |
| view_count | Integer | 浏览次数 |
| click_count | Integer | 点击次数 |
| feedback_positive | Integer | 正面反馈数 |

### conversation_summaries
对话摘要表

| 字段 | 类型 | 说明 |
|------|------|------|
| conversation_id | String | 对话ID |
| summary_type | String | 摘要类型 |
| text | Text | 摘要内容 |
| key_points | JSONB | 关键点 |

---

## 文件变更

### 新增文件

| 文件 | 说明 |
|------|------|
| `services/api/app/services/vision_service.py` | 视觉理解服务 |
| `services/api/app/services/table_extractor.py` | 表格提取服务 |
| `services/api/app/api/vision.py` | 视觉 API |
| `services/api/app/services/entity_extractor.py` | 实体抽取服务 |
| `services/api/app/services/relation_extractor.py` | 关系抽取服务 |
| `services/api/app/services/knowledge_graph.py` | 知识图谱服务 |
| `services/api/app/api/kg.py` | 知识图谱 API |
| `services/api/app/services/behavior_tracker.py` | 行为跟踪服务 |
| `services/api/app/services/recommendation_engine.py` | 推荐引擎 |
| `services/api/app/api/recommend.py` | 推荐 API |
| `services/api/app/services/summary_service.py` | 摘要服务 |
| `services/api/app/api/summary.py` | 摘要 API |
| `services/api/alembic/versions/005_add_user_behavior.py` | 用户行为迁移 |
| `services/api/alembic/versions/006_add_conversation_summary.py` | 摘要迁移 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `docker-compose.yml` | 添加 Neo4j 服务 |
| `services/api/app/main.py` | 注册新路由 |
| `services/api/app/api/gateway.py` | 支持图片消息 |
| `services/api/app/services/retrieval.py` | 图谱增强检索 |
| `services/api/app/services/context_manager.py` | 摘要集成 |
| `Makefile` | 添加 upgrade-phase5 |

---

## 配置说明

### 环境变量

在 `.env` 中添加（可选）：

```bash
# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4jpass

# Qwen-VL（默认使用 DASHSCOPE_API_KEY）
QWEN_VL_MODEL=qwen-vl-max
```

---

## 使用示例

### 图片问答

```python
import requests

# 上传图片并提问
with open("spec_table.png", "rb") as f:
    response = requests.post(
        "http://localhost:8000/v1/vision/analyze",
        files={"file": f},
        data={"question": "这个产品的功率是多少？"}
    )
    
print(response.json()["text_content"])
```

### 构建知识图谱

```python
import requests

# 从文档文本抽取实体并导入
text = """
AOI-3000是一款高精度光学检测设备，由华为制造。
功率为500W，检测精度达到0.01mm，适用于PCB缺陷检测场景。
"""

response = requests.post(
    "http://localhost:8000/v1/kg/import",
    json={"text": text, "extract_relations": True}
)

print(f"导入 {response.json()['entities_imported']} 个实体")
print(f"导入 {response.json()['relations_imported']} 个关系")
```

### 获取个性化推荐

```python
import requests

# 记录用户行为
requests.post(
    "http://localhost:8000/v1/recommend/track",
    json={
        "user_id": "user123",
        "behavior_type": "query",
        "query": "AOI设备功率",
        "scenario_id": "aoi_inspection"
    }
)

# 获取推荐
response = requests.get(
    "http://localhost:8000/v1/recommend",
    params={"user_id": "user123", "limit": 5}
)

for rec in response.json()["recommendations"]:
    print(f"- {rec['title']} ({rec['type']}): {rec['reason']}")
```

---

## 故障排查

### Neo4j 连接失败

```bash
# 检查容器状态
docker compose ps neo4j

# 查看日志
docker compose logs neo4j

# 验证连接
docker compose exec neo4j cypher-shell -u neo4j -p neo4jpass "RETURN 1"
```

### 视觉服务超时

- 确保 `DASHSCOPE_API_KEY` 配置正确
- Qwen-VL 首次调用可能较慢，后续会加快
- 大图片建议先压缩

### 推荐为空

- 需要先记录用户行为数据
- 新用户会返回热门内容作为兜底

---

## 后续计划

Phase 5 为系统打下了智能化基础，后续可扩展：

1. **知识图谱增强**
   - 自动从新 KU 中抽取实体
   - 图谱可视化界面
   - 图谱推理查询

2. **推荐优化**
   - 基于向量的相似度推荐
   - 实时推荐更新
   - A/B 测试框架

3. **多模态扩展**
   - PDF 直接解析
   - 视频理解
   - 语音转文字

