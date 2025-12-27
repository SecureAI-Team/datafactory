# Phase 3 升级指南：结构化参数

## 概述

Phase 3 实现了结构化参数处理能力，使系统能够：
- 从用户查询中精确提取参数需求（值、单位、运算符）
- 基于参数进行精确检索和过滤
- 支持规格比对和智能计算
- 可配置的计算规则

## 新增功能

### 1. 参数提取器 (`param_extractor.py`)

从自然语言中提取结构化参数：

```python
from app.services.param_extractor import extract_params

params = extract_params("功率>=500W的AOI设备，精度小于0.01mm")
# 返回:
# [
#   ExtractedParam(name="功率", canonical_name="power", value=500, unit="W", operator="gte"),
#   ExtractedParam(name="精度", canonical_name="precision", value=0.01, unit="mm", operator="lt"),
# ]
```

支持的运算符：
- `eq`: 等于（默认）
- `gt/gte`: 大于/大于等于
- `lt/lte`: 小于/小于等于
- `between`: 范围
- `approx`: 约等于

### 2. 智能搜索 (`retrieval.py`)

根据查询类型自动选择最佳检索策略：

```python
from app.services.retrieval import smart_search

result = smart_search("功率500W的AOI设备")
# 返回:
# {
#   "hits": [...],
#   "strategy": "param_enhanced_search",  # 使用了参数增强搜索
#   "intent": {"type": "parameter_query", ...},
#   "extracted_params": [...]
# }
```

策略类型：
- `param_search`: 纯参数搜索
- `param_enhanced_search`: 参数增强语义搜索
- `calculation_search`: 计算相关搜索
- `scenario_search`: 场景化搜索

### 3. 规格比对 (`calculation_engine.py`)

比较多个产品的规格参数：

```python
from app.services.calculation_engine import compare_specs

products = [
    {"name": "设备A", "params": [{"name": "power", "value": 500}, {"name": "precision", "value": 0.01}]},
    {"name": "设备B", "params": [{"name": "power", "value": 600}, {"name": "precision", "value": 0.005}]},
]
result = compare_specs(products)
# 返回比对表和推荐结论
```

### 4. 增强计算引擎

支持自动参数提取后计算：

```python
from app.services.calculation_engine import calculate_with_extraction

result = calculate_with_extraction("产能5000片/小时需要几台AOI设备")
# 自动提取产能参数，计算设备数量
```

## 新增 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/debug/extract-params` | POST | 测试参数提取 |
| `/v1/debug/smart-search` | POST | 智能搜索 |
| `/v1/debug/compare-specs` | POST | 规格比对 |
| `/v1/debug/search-by-params` | POST | 参数化搜索 |

## 升级步骤

### 现有部署升级

```bash
# 拉取最新代码
cd /opt/datafactory
git pull

# 运行升级脚本
make upgrade-phase3

# 或手动执行
docker compose run --rm api alembic upgrade head
docker compose build api
docker compose up -d api
```

### 新部署

新部署会自动包含 Phase 3 功能：

```bash
make init
make up
```

## 验证测试

```bash
# 1. 测试参数提取
curl -X POST http://localhost:8000/v1/debug/extract-params \
  -H "Content-Type: application/json" \
  -d '{"query": "功率>=500W的AOI设备，精度小于0.01mm"}'

# 2. 测试智能搜索
curl -X POST http://localhost:8000/v1/debug/smart-search \
  -H "Content-Type: application/json" \
  -d '{"query": "产能3000片/小时以上的检测设备"}'

# 3. 测试规格比对
curl -X POST http://localhost:8000/v1/debug/compare-specs \
  -H "Content-Type: application/json" \
  -d '{
    "products": [
      {"name": "设备A", "params": [{"name": "power", "value": 500}]},
      {"name": "设备B", "params": [{"name": "power", "value": 600}]}
    ]
  }'

# 4. 测试参数化搜索
curl -X POST http://localhost:8000/v1/debug/search-by-params \
  -H "Content-Type: application/json" \
  -d '{"param_name": "power", "min_value": 400, "max_value": 600}'
```

## 数据库变更

新增表：
- `calculation_rules`: 可配置的计算规则
- `parameter_definitions`: 参数标准定义

## 文件变更清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `services/api/app/services/param_extractor.py` | 参数提取器 |
| 修改 | `services/api/app/services/retrieval.py` | 添加参数化检索 |
| 修改 | `services/api/app/services/calculation_engine.py` | 添加规格比对 |
| 新建 | `services/api/alembic/versions/004_add_calculation_tables.py` | 数据库迁移 |
| 新建 | `scripts/upgrade_phase3.py` | 升级脚本 |

## 故障排除

### 参数提取不准确

检查参数名映射是否覆盖：
```python
from app.services.param_extractor import PARAM_NAME_MAPPING
print(PARAM_NAME_MAPPING)
```

### 搜索结果为空

确保 OpenSearch 索引包含 `params` 嵌套字段：
```bash
curl -X GET "http://localhost:9200/knowledge_units/_mapping?pretty"
```

### 计算规则未生效

检查计算规则是否匹配：
```python
from app.services.calculation_engine import get_calculation_engine
engine = get_calculation_engine()
rule = engine.detect_calculation_need("产能5000需要几台")
print(rule)
```

