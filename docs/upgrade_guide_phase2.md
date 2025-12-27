# Phase 2 升级指南

## 概述

Phase 2 实现了**上下文管理**、**计算引擎**和**反馈优化**功能，支持多轮对话和智能计算。

### 新增功能

| 功能 | 说明 |
|------|------|
| 对话上下文管理 | 实体跟踪、偏好记忆、历史压缩、上下文注入 |
| 计算引擎 | 设备数量估算、精度校验、成本/ROI计算 |
| 反馈优化器 | 自然语言反馈检测、统计分析、Prompt增强 |

---

## 升级步骤

### 场景一：现有部署升级

```bash
# 1. 拉取最新代码
cd /opt/datafactory
git pull

# 2. 运行升级命令
make upgrade-phase2

# 3. 验证升级
make verify-phase2
```

### 场景二：新部署

新部署会自动包含 Phase 2 功能：

```bash
make init up
```

---

## 功能详解

### 1. 对话上下文管理

**核心能力**：

- **实体跟踪**：自动从对话中提取参数（功率、精度、产能等）
- **偏好记忆**：记住用户选择（预算范围、技术水平）
- **历史压缩**：长对话自动摘要，保持上下文窗口可控
- **上下文注入**：将历史信息融入每次请求的 Prompt

**示例对话**：

```
用户: 推荐一个AOI检测方案
助手: [返回澄清问卷]

用户: 预算50万，检测PCB焊点
助手: [推荐方案，记住预算和产品类型]

用户: 需要几台设备才能满足5000片/小时的产能
助手: [基于上下文中的预算和产品类型，结合产能计算]
```

**调试接口**：

```bash
# 查看对话上下文
curl http://localhost:8000/v1/debug/context/{conversation_id}
```

---

### 2. 计算引擎

**支持的计算类型**：

| 计算类型 | 触发词 | 示例 |
|---------|--------|------|
| 设备数量 | "需要几台"、"配多少" | "产能5000片/小时需要几台设备" |
| 精度校验 | "能否检测"、"检得出吗" | "能检测0.1mm的缺陷吗" |
| 单件成本 | "成本多少"、"单件成本" | "检测一片成本多少钱" |
| ROI计算 | "多久回本"、"投资回报" | "设备投资回报周期是多少" |
| 产能匹配 | "能满足吗"、"够用吗" | "这个方案能满足我们的产能吗" |

**计算逻辑**：

```
设备数量 = ceil(需求产能 / 单台产能 * 冗余系数)
精度校验 = 设备精度 <= 缺陷尺寸 * 0.3
单件成本 = 设备价格 / (使用年限 * 年工作日 * 日产能)
ROI周期 = 设备成本 / (月节省人力 + 月良率收益)
```

**调试接口**：

```bash
# 测试计算引擎
curl -X POST http://localhost:8000/v1/debug/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "产能5000片/小时需要几台AOI设备",
    "entities": {"需求产能": {"value": 5000}}
  }'
```

**响应示例**：

```json
{
  "calculation_type": "device_count",
  "success": true,
  "result_value": 2,
  "result_unit": "台",
  "result_text": "根据您的产能需求 5000片/小时，建议配置 **2台** 设备",
  "reasoning": "需求产能 5000片/小时 ÷ 单台产能 3000片/小时 = 1.7台，考虑 10% 冗余后 ≈ 2台"
}
```

---

### 3. 反馈优化器

**反馈检测**：

| 反馈类型 | 检测关键词 |
|---------|-----------|
| 正面 | "有帮助"、"很好"、"谢谢"、"完美" |
| 负面 | "不满意"、"没有帮助"、"不对"、"错了" |
| 追问 | "再解释"、"什么意思"、"不明白" |

**反馈应用**：

1. **Prompt 增强**：将高评分案例作为 Few-shot 示例
2. **问题分析**：识别常见问题模式（不相关、不详细等）
3. **统计报告**：按意图、场景汇总满意度

**调试接口**：

```bash
# 查看反馈统计
curl "http://localhost:8000/v1/debug/feedback-stats?days=7"

# 手动记录反馈
curl -X POST http://localhost:8000/v1/debug/record-feedback \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "test",
    "feedback_type": "explicit_positive",
    "query": "推荐AOI方案",
    "response": "...",
    "rating": 5,
    "intent_type": "solution_recommendation"
  }'
```

---

## 新增文件清单

```
services/api/app/services/
├── context_manager.py      # 对话上下文管理
├── calculation_engine.py   # 计算引擎
└── feedback_optimizer.py   # 反馈优化器

services/api/alembic/versions/
└── 003_add_context_and_feedback.py  # 数据库迁移

scripts/
└── upgrade_phase2.py       # 升级脚本
```

---

## 使用建议

### 多轮对话最佳实践

1. **传递会话ID**：在请求头中添加 `X-Conversation-Id`
   ```bash
   curl -X POST http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "X-Conversation-Id: my-session-123" \
     -d '{"messages": [...]}'
   ```

2. **利用上下文**：后续问题会自动继承之前的参数和偏好

3. **触发计算**：使用计算相关关键词触发自动计算
   - "需要几台"
   - "能否检测"
   - "成本多少"
   - "多久回本"

### 反馈收集

1. 系统会自动检测自然语言反馈（"有帮助"、"不满意"）
2. 可通过 API 手动记录评分反馈
3. 定期查看统计报告，识别改进点

---

## 故障排除

### 问题：计算结果不准确

**解决方案**：
1. 检查参数提取是否正确
2. 查看计算依赖的默认值是否合理
3. 通过调试接口查看 `inputs_used` 和 `reasoning`

### 问题：上下文未保存

**解决方案**：
1. 确保传递了 `X-Conversation-Id` 请求头
2. 检查 Redis 服务是否运行（可选）
3. 查看日志中的 "Context save" 信息

### 问题：反馈未记录

**解决方案**：
1. 检查反馈关键词是否被识别
2. 通过调试接口手动测试反馈检测
3. 查看 `/v1/debug/feedback-stats` 确认记录

---

## 配置说明

### 计算规则配置

计算规则在 `services/api/app/services/calculation_engine.py` 的 `CALCULATION_RULES` 中定义：

```python
CalculationRule(
    name="设备数量估算",
    calculation_type=CalculationType.DEVICE_COUNT,
    triggers=["需要几台", "要多少台", "配置几套"],
    required_inputs=["需求产能"],
    optional_inputs=["单台产能", "冗余系数"],
    formula="device_count",
    output_template="...",
    default_values={"单台产能": 3000, "冗余系数": 1.1},
)
```

### 上下文存储

默认使用内存存储，可配置 Redis 持久化：

```python
# services/api/app/services/context_manager.py
ContextManager(storage_backend="redis")  # 或 "memory"
```

---

## 回滚说明

如需回滚：

```bash
git checkout HEAD~1
docker compose build --no-cache api
docker compose up -d api
```

