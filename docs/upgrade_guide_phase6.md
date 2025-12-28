# Phase 6 升级指南 - 多资料处理与角色流程优化

## 概述

Phase 6 实现了多资料处理策略和角色使用流程优化，主要功能包括：

1. **KU 类型管理** - 支持 core/case/quote/solution/whitepaper/faq 类型
2. **产品维度管理** - 按产品组织和关联 KU
3. **重复检测与合并** - 自动检测相似 KU 并生成合并建议
4. **关联检索** - 查询时自动获取关联的 KU
5. **BD/Sales 专用 API** - 案例搜索、报价查询、方案生成

## 新增文件

### 数据库迁移
- `services/api/alembic/versions/007_add_ku_relations.py`

### Pipeline 模块
- `services/pipeline/pipeline/dedup_detector.py` - 重复检测
- `services/pipeline/pipeline/ku_merger.py` - 智能合并

### Airflow DAG
- `services/airflow/dags/merge_duplicates.py` - 合并审核 DAG

### API 端点
- `services/api/app/api/dedup.py` - 重复检测 API
- `services/api/app/api/products.py` - 产品管理 API
- `services/api/app/api/bd.py` - BD/Sales 专用 API

### 服务模块
- `services/api/app/services/response_builder.py` - 回答构建服务

## 修改文件

- `services/api/app/models.py` - 新增 KURelation, Product, DedupGroup 模型
- `services/pipeline/pipeline/material_classifier.py` - 增强分类器
- `services/api/app/services/retrieval.py` - 增加关联检索
- `services/api/app/services/intent_recognizer.py` - 增加 QUOTE 意图
- `services/api/app/api/gateway.py` - 集成回答构建逻辑
- `services/api/app/main.py` - 注册新路由
- `scripts/create_opensearch_index.py` - 更新索引映射

## 升级步骤

### 对于现有部署

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 重建 API 镜像
docker compose build api

# 3. 运行数据库迁移
docker compose run --rm api alembic upgrade head

# 4. 更新 OpenSearch 索引（会添加新字段，不删除数据）
docker compose run --rm api python scripts/create_opensearch_index.py

# 5. 重建 Airflow 镜像（获取新的 DAG）
docker compose build airflow

# 6. 重启服务
docker compose up -d api airflow
```

### 对于新部署

```bash
# 使用标准初始化流程
make init up
```

## 新增 API 端点

### 重复检测 API

```bash
# 获取待处理的重复组
curl http://localhost:8000/v1/dedup/pending

# 批准合并
curl -X POST http://localhost:8000/v1/dedup/approve \
  -H "Content-Type: application/json" \
  -d '{"group_id": "abc123", "reviewer": "admin"}'

# 驳回（误判）
curl -X POST http://localhost:8000/v1/dedup/dismiss \
  -H "Content-Type: application/json" \
  -d '{"group_id": "abc123", "reviewer": "admin", "reason": "false_positive"}'

# 获取统计
curl http://localhost:8000/v1/dedup/stats
```

### 产品管理 API

```bash
# 获取产品列表
curl http://localhost:8000/v1/products

# 获取产品的所有 KU
curl http://localhost:8000/v1/products/aoi-3000/kus

# 设置主 KU
curl -X POST http://localhost:8000/v1/products/aoi-3000/primary \
  -H "Content-Type: application/json" \
  -d '{"ku_id": 123}'
```

### BD/Sales API

```bash
# 搜索案例
curl "http://localhost:8000/v1/bd/cases?industry=金融&limit=5"

# 获取报价
curl http://localhost:8000/v1/bd/quotes/aoi-3000

# 快速问答
curl "http://localhost:8000/v1/bd/quick-answer?q=AOI检测有哪些案例"

# 生成方案大纲
curl -X POST http://localhost:8000/v1/bd/generate-proposal \
  -H "Content-Type: application/json" \
  -d '{"topic": "工业质检自动化方案", "product_ids": ["aoi-3000"], "include_cases": true}'
```

## 验证测试

```bash
# 1. 检查 API 健康
curl http://localhost:8000/health

# 2. 测试案例搜索
curl "http://localhost:8000/v1/bd/cases?query=金融"

# 3. 测试关联检索
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "messages": [{"role": "user", "content": "找一个金融行业的AOI检测案例"}]
  }'

# 4. 测试报价查询
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "messages": [{"role": "user", "content": "AOI-3000多少钱？"}]
  }'

# 5. 检查重复检测 DAG
# 访问 Airflow UI: http://localhost:8080
# 查看 merge_duplicates DAG
```

## 数据模型说明

### KU 类型 (ku_type)

| 类型 | 说明 | 合并策略 |
|------|------|----------|
| `core` | 核心产品信息 | 智能合并 |
| `case` | 客户案例 | 独立保存 |
| `quote` | 报价信息 | 独立保存 |
| `solution` | 解决方案 | 独立保存 |
| `whitepaper` | 白皮书 | 可合并 |
| `faq` | 常见问题 | 可合并 |

### KU 关联类型 (relation_type)

| 类型 | 说明 |
|------|------|
| `parent_of` | 主 KU -> 附属 KU |
| `related_to` | 相互关联 |
| `merged_from` | 合并来源 |
| `supersedes` | 替代（新版本） |

## 常见问题

### Q: 如何手动触发重复检测？

```bash
docker compose exec airflow airflow dags trigger merge_duplicates
```

### Q: 如何重新索引所有 KU？

```bash
# 强制重建索引（会删除现有数据）
docker compose run --rm api python scripts/create_opensearch_index.py --force

# 然后重新运行 Airflow DAG 索引任务
docker compose exec airflow airflow dags trigger index_to_opensearch
```

### Q: 如何查看 KU 的类型分布？

```bash
curl http://localhost:8000/v1/index/stats
```

## 后续优化

- 添加 Budibase 重复处理工作台界面
- 增强合并算法（支持 LLM 智能合并）
- 添加产品关系图可视化

