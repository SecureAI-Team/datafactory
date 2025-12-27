# Phase 4 升级指南：优化闭环

## 概述

Phase 4 实现了系统的自动优化闭环能力：
- 智能检测用户话题切换
- 分析反馈数据识别问题模式
- 自动生成 Prompt 优化建议
- 实时监控系统健康状态

## 新增功能

### 1. 场景切换检测 (`scenario_switch_detector.py`)

智能识别用户在对话中的话题转换：

```python
from app.services.scenario_switch_detector import detect_scenario_switch

result = detect_scenario_switch(
    current_query="换个话题，问一下成本问题",
    previous_queries=["AOI设备功率多少？"],
    current_scenario="aoi_inspection"
)

# 返回:
# SwitchDetectionResult(
#   switch_type=SwitchType.SCENARIO_SWITCH,
#   confidence=0.9,
#   new_scenario="cost_analysis",
#   transition_message="好的，让我们来看这个新问题。"
# )
```

支持的切换类型：
- `NONE`: 无切换，继续当前话题
- `TOPIC_SHIFT`: 话题偏移（同场景内）
- `SCENARIO_SWITCH`: 场景切换（跨场景）
- `CLARIFICATION`: 澄清/补充
- `FOLLOW_UP`: 追问
- `NEW_SESSION`: 新会话开始

### 2. 反馈分析报表 (`feedback_analyzer.py`)

分析用户反馈，生成洞察报告：

```python
from app.services.feedback_analyzer import analyze_feedback

report = analyze_feedback(days=7)

# 报告包含:
# - 基础统计（正面率、平均评分）
# - 按意图/场景分布
# - 识别的问题模式
# - 改进建议
# - 健康评分
```

识别的模式类型：
- `negative_cluster`: 负面反馈聚集（某意图/场景问题多）
- `incomplete_answers`: 回答不完整（追问率高）
- `time_anomaly`: 时段异常

### 3. 自动Prompt优化 (`prompt_optimizer.py`)

基于反馈自动生成优化建议：

```python
from app.services.prompt_optimizer import optimize_prompt

optimized = optimize_prompt(
    base_prompt="你是一个专业助手...",
    intent_type="technical_qa"
)

# 自动添加:
# - Few-shot 示例（从高评分回答中提取）
# - 指令调整（基于负面反馈）
# - 避免事项（负面示例）
# - 格式指导
```

优化类型：
- `few_shot`: 添加高质量回答示例
- `negative`: 负面示例（避免类似错误）
- `instruction`: 指令调整
- `retrieval_hint`: 检索提示
- `format_guide`: 格式指导

### 4. 质量监控仪表盘 (`quality_monitor.py`)

实时监控系统核心指标：

```python
from app.services.quality_monitor import get_health_status, get_dashboard_data

# 健康状态
health = get_health_status()
# HealthStatus(healthy=True, score=85.0, ...)

# 仪表盘数据
dashboard = get_dashboard_data()
# 包含各项指标、组件状态、活动告警
```

监控指标：
- `feedback_positive_rate`: 正面反馈率
- `feedback_average_rating`: 平均评分
- `response_latency_ms`: 响应延迟
- `error_rate`: 错误率
- `conversation_count`: 对话数量

告警规则：
- 正面反馈率 < 50%: WARNING
- 正面反馈率 < 30%: CRITICAL
- 错误率 > 10%: CRITICAL
- 响应延迟 > 5s: WARNING

## 新增 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/debug/detect-switch` | POST | 场景切换检测 |
| `/v1/debug/feedback-report` | GET | 反馈分析报告 |
| `/v1/debug/feedback-trend` | GET | 反馈趋势 |
| `/v1/debug/optimization-suggestions` | GET | 优化建议 |
| `/v1/debug/health` | GET | 健康状态 |
| `/v1/debug/dashboard` | GET | 监控仪表盘 |
| `/v1/debug/record-quality-metric` | POST | 记录指标 |

## 升级步骤

### 现有部署升级

```bash
# 拉取最新代码
cd /opt/datafactory
git pull

# 运行升级脚本
make upgrade-phase4

# 或手动执行
docker compose build api
docker compose up -d api
```

### 新部署

新部署会自动包含 Phase 4 功能。

## 验证测试

```bash
# 1. 场景切换检测
curl -X POST http://localhost:8000/v1/debug/detect-switch \
  -H "Content-Type: application/json" \
  -d '{
    "query": "换个话题，问一下成本问题",
    "previous_queries": ["AOI设备功率多少？"],
    "current_scenario": "aoi_inspection"
  }'

# 2. 反馈分析报告
curl "http://localhost:8000/v1/debug/feedback-report?days=7"

# 3. 反馈趋势
curl "http://localhost:8000/v1/debug/feedback-trend?metric=positive_rate&days=7"

# 4. 优化建议
curl "http://localhost:8000/v1/debug/optimization-suggestions"

# 5. 健康状态
curl http://localhost:8000/v1/debug/health

# 6. 监控仪表盘
curl http://localhost:8000/v1/debug/dashboard
```

## 集成使用

### 在对话中使用场景切换检测

```python
from app.services.scenario_switch_detector import detect_scenario_switch

# 在处理每条消息时检测
switch_result = detect_scenario_switch(
    current_query=user_message,
    previous_queries=context.get_recent_queries(),
    current_scenario=context.current_scenario,
)

if switch_result.switch_type == SwitchType.SCENARIO_SWITCH:
    # 处理场景切换
    if switch_result.should_summarize_previous:
        # 生成前一话题的摘要
        pass
    if switch_result.transition_message:
        # 添加过渡消息
        response_prefix = switch_result.transition_message
```

### 在生成回答时使用Prompt优化

```python
from app.services.prompt_optimizer import optimize_prompt

# 优化系统Prompt
optimized_prompt = optimize_prompt(
    base_prompt=SYSTEM_PROMPT,
    intent_type=intent_result.intent_type.value,
    scenario_id=scenario_id,
)
```

### 记录质量指标

```python
from app.services.quality_monitor import get_quality_monitor

monitor = get_quality_monitor()

# 记录对话指标
monitor.record_conversation_metrics(
    latency_ms=response_time * 1000,
    has_error=False,
    feedback_positive=True,
    feedback_rating=5,
    intent_type="technical_qa",
)
```

## 文件变更清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `services/api/app/services/scenario_switch_detector.py` | 场景切换检测器 |
| 新建 | `services/api/app/services/feedback_analyzer.py` | 反馈分析器 |
| 新建 | `services/api/app/services/prompt_optimizer.py` | Prompt优化器 |
| 新建 | `services/api/app/services/quality_monitor.py` | 质量监控器 |
| 修改 | `services/api/app/api/gateway.py` | 添加调试端点 |
| 新建 | `scripts/upgrade_phase4.py` | 升级脚本 |

## 监控告警配置

可以自定义告警规则：

```python
from app.services.quality_monitor import get_quality_monitor, AlertLevel

monitor = get_quality_monitor()

# 添加自定义告警规则
monitor.add_alert_rule(
    name="very_slow_response",
    metric="response_latency_ms",
    condition="gt",
    threshold=10000,  # 10秒
    level=AlertLevel.CRITICAL,
    window_minutes=5,
    message="过去5分钟响应时间超过10秒",
)

# 添加告警回调
def alert_handler(alert):
    # 发送通知...
    print(f"Alert: {alert.message}")

monitor.add_alert_callback(alert_handler)
```

## 故障排除

### 场景切换误判

检查关键词配置：
```python
from app.services.scenario_switch_detector import SCENARIO_KEYWORDS
print(SCENARIO_KEYWORDS)
```

### 优化建议为空

确保有足够的反馈数据：
```python
from app.services.feedback_optimizer import get_feedback_optimizer
optimizer = get_feedback_optimizer()
print(f"反馈记录数: {len(optimizer._feedback_records)}")
```

### 健康评分异常

检查指标数据：
```python
from app.services.quality_monitor import get_quality_monitor
monitor = get_quality_monitor()
for name in monitor._metrics:
    stats = monitor.get_metric_stats(name, 60)
    print(f"{name}: {stats}")
```

