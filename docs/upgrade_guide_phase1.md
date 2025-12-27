# Phase 1 升级指南

## 概述

Phase 1 实现了**意图识别增强**和**场景化检索路由**功能，提升问答系统的智能程度。

### 新增功能

| 功能 | 说明 |
|------|------|
| 增强意图识别 | 规则+LLM混合识别，新增参数查询、计算选型、案例查询意图 |
| 实体抽取 | 自动提取功率、精度、产能、价格等结构化参数 |
| 场景化检索路由 | 根据意图和场景动态调整检索策略 |
| 澄清问卷引擎 | 动态生成场景相关的澄清问题 |
| 调试接口 | 意图识别、场景检索测试接口 |

### 新增意图类型

| 意图类型 | 说明 | 示例 |
|---------|------|------|
| `parameter_query` | 参数/规格查询 | "AOI设备功率是多少" |
| `calculation` | 计算/选型 | "产能5000片需要几台设备" |
| `case_study` | 案例查询 | "有没有PCB检测的成功案例" |

---

## 升级步骤

### 场景一：现有部署升级

```bash
# 1. 拉取最新代码
cd /opt/datafactory
git pull

# 2. 运行升级命令
make upgrade-phase1

# 3. 验证升级
make verify-phase1
```

### 场景二：新部署

```bash
# 1. 克隆仓库
git clone <repo-url> /opt/datafactory
cd /opt/datafactory

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，配置 DASHSCOPE_API_KEY 等

# 3. 启动服务
make init
make up

# 4. 验证
make verify-phase1
```

---

## 功能验证

### 1. 测试意图识别

```bash
# 方案推荐意图
curl -X POST http://localhost:8000/v1/debug/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query": "推荐一个AOI检测方案"}'

# 参数查询意图
curl -X POST http://localhost:8000/v1/debug/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query": "AOI设备功率是多少瓦"}'

# 计算选型意图
curl -X POST http://localhost:8000/v1/debug/recognize-intent \
  -H "Content-Type: application/json" \
  -d '{"query": "产能5000片/小时需要几台设备"}'
```

**预期响应示例**：
```json
{
  "intent_type": "parameter_query",
  "confidence": 0.85,
  "scenario_ids": ["aoi_inspection"],
  "entities": {
    "power": {"value": null, "is_query": true}
  },
  "needs_clarification": false
}
```

### 2. 测试场景化检索

```bash
curl -X POST http://localhost:8000/v1/debug/search \
  -H "Content-Type: application/json" \
  -d '{"query": "PCB焊点检测方案推荐", "top_k": 5}'
```

**预期响应示例**：
```json
{
  "query": "PCB焊点检测方案推荐",
  "intent": {
    "type": "solution_recommendation",
    "scenarios": ["aoi_inspection"],
    "entities": {}
  },
  "hits": [
    {
      "id": "xxx",
      "title": "PCB焊点AOI检测方案",
      "score": 5.2,
      "scenario_id": "aoi_inspection",
      "material_type": "whitepaper"
    }
  ]
}
```

### 3. 测试澄清问卷

在 Open WebUI 中输入模糊问题，如：
- "推荐一个方案"
- "怎么做检测"

系统会自动生成澄清问卷，引导用户提供更多信息。

---

## 新增文件清单

```
services/api/app/services/
├── intent_recognizer.py    # 增强意图识别器
├── scenario_router.py      # 场景化检索路由
├── clarification.py        # 澄清问卷引擎
└── retrieval.py            # 更新：集成场景化检索

services/api/app/api/
└── gateway.py              # 更新：集成新模块

scripts/
└── upgrade_phase1.py       # 升级脚本
```

---

## 配置说明

### 场景配置

场景定义在 `services/api/app/services/intent_recognizer.py` 的 `SCENARIO_KEYWORDS` 中：

```python
SCENARIO_KEYWORDS = {
    "aoi_inspection": {
        "keywords": ["AOI", "视觉检测", "缺陷检测", ...],
        "priority": 10,
    },
    "network_security": {
        "keywords": ["网络安全", "防火墙", ...],
        "priority": 8,
    },
    # 添加新场景...
}
```

### 澄清问题配置

澄清问题在 `services/api/app/services/clarification.py` 的 `question_templates` 中定义：

```python
self.question_templates = {
    "aoi_product_type": ClarificationQuestion(
        id="aoi_product_type",
        question="您需要检测的产品类型是？",
        options=[
            ClarificationOption("pcb", "PCB电路板", {...}),
            ...
        ],
    ),
    # 添加新问题...
}
```

### 检索路由规则

检索配置在 `services/api/app/services/scenario_router.py` 的 `routing_rules` 中定义：

```python
self.routing_rules = {
    ("aoi_inspection", IntentType.PARAMETER_QUERY): {
        "field_boosts": {...},
        "include_params_query": True,
        ...
    },
    # 添加新规则...
}
```

---

## 故障排除

### 问题：意图识别不准确

**解决方案**：
1. 检查 `INTENT_PATTERNS` 中的关键词和正则规则
2. 如果 LLM 识别被禁用，确保 `settings.upstream_llm_key` 正确配置
3. 查看日志：`docker compose logs api | grep "Intent:"`

### 问题：澄清问卷不出现

**解决方案**：
1. 确保意图的 `needs_clarification` 为 `True`
2. 检查 `questionnaire_rules` 是否包含该场景+意图组合
3. 确认用户输入不被判定为澄清回复（`is_clarification_response`）

### 问题：场景检索结果为空

**解决方案**：
1. 确保 OpenSearch 索引包含场景相关字段：
   ```bash
   curl "http://localhost:9200/knowledge_units/_mapping?pretty"
   ```
2. 确保已运行 Pipeline V2 处理文档：
   ```bash
   make pipeline-full
   ```
3. 检查路由配置的过滤条件是否过严

---

## 回滚说明

如需回滚到升级前状态：

```bash
# 1. 恢复代码
git checkout HEAD~1

# 2. 重建 API 服务
docker compose build --no-cache api
docker compose up -d api
```

备份文件位于 `backups/phase1_upgrade/` 目录。

