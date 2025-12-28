# 工业制造测试数据集

用于测试 AI Data Factory 多资料处理、场景化检索、去重合并等功能的测试数据集。

## 当前可用场景

| 场景 | 产品 | 材料数量 | 状态 |
|------|------|---------|------|
| AOI 检测 | AOI8000, AOI5000 | 17 | ✅ 可用 |
| 智能仓储 | WMS-Pro, AGV-100 | - | 🚧 待生成 |
| 工业机器人 | RB-600, RB-1200 | - | 🚧 待生成 |
| 预测性维护 | PDM-Cloud, SensorKit | - | 🚧 待生成 |
| 质量控制 | QC-Vision, MES-Lite | - | 🚧 待生成 |

## AOI 检测场景详情

### 目录结构

```
data/aoi_inspection/
├── products/
│   ├── AOI8000/
│   │   ├── AOI8000_产品规格书.md      # core - 完整技术参数
│   │   ├── AOI8000_技术参数表.md      # core - 参数表格（与规格书相似，测试去重）
│   │   ├── AOI8000_白皮书.md          # whitepaper - 技术深度文档
│   │   ├── AOI8000_产品介绍.md        # core - 简介（与白皮书部分重复，测试去重）
│   │   └── AOI8000_报价单_2024Q1.md   # quote - 价格配置
│   └── AOI5000/
│       ├── AOI5000_产品规格书.md      # core
│       └── AOI5000_报价单.md          # quote
├── cases/
│   ├── 华为PCB产线案例.md             # case - 电子制造行业
│   ├── 富士康SMT检测案例.md           # case - EMS 行业
│   ├── 比亚迪电池检测案例.md          # case - 新能源行业
│   ├── 中兴通讯5G基站案例.md          # case - 通信行业
│   └── 宁德时代储能案例.md            # case - 储能行业
├── solutions/
│   ├── PCB缺陷检测解决方案.md         # solution
│   ├── SMT贴片质检方案.md             # solution
│   └── 汽车电子质检方案.md            # solution
└── faq/
    ├── AOI常见问题.md                 # faq
    └── AOI选型指南.md                 # faq
```

### 测试用例设计

| 材料类型 | 数量 | 测试目的 |
|---------|------|---------|
| 产品规格 (core) | 4 | 参数提取、规格对比 |
| 白皮书 (whitepaper) | 1 | 技术概念问答 |
| 客户案例 (case) | 5 | 案例检索、行业筛选 |
| 报价单 (quote) | 2 | 报价查询 |
| 解决方案 (solution) | 3 | 方案生成 |
| 常见问题 (faq) | 2 | 问题匹配 |
| **合计** | **17** | |

### 重复检测测试

以下材料故意设计有相似内容，用于测试去重功能：

1. **AOI8000_产品规格书.md** vs **AOI8000_技术参数表.md**
   - 参数数据相同，格式略有不同
   - 预期：检测为重复，建议合并

2. **AOI8000_白皮书.md** vs **AOI8000_产品介绍.md**
   - 产品介绍是白皮书的简化版
   - 预期：检测为相关，可选择合并

## 快速开始

### 1. 上传测试数据

```bash
# 预览要上传的文件
make upload-test-data-dry

# 上传 AOI 场景数据
make upload-test-data-aoi

# 或上传所有测试数据
make upload-test-data
```

### 2. 运行 Pipeline

```bash
# 触发完整处理流程
make pipeline-full

# 查看 Airflow 进度
# 访问 http://localhost:8080
```

### 3. 验证结果

```bash
# 查看索引状态
make index-status

# 查看 MinIO 内容
make buckets
```

## 测试场景

### 参数查询测试

```bash
# 测试参数查询
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "messages": [{"role": "user", "content": "AOI8000的检测精度是多少？"}]
  }'

# 预期回答：0.01mm
```

### 规格对比测试

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "messages": [{"role": "user", "content": "AOI8000和AOI5000有什么区别？"}]
  }'
```

### 案例检索测试

```bash
# 按行业搜索案例
curl "http://localhost:8000/v1/bd/cases?industry=电子制造"

# 自然语言查询
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "messages": [{"role": "user", "content": "给我找一个新能源行业的AOI案例"}]
  }'
```

### 报价查询测试

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "messages": [{"role": "user", "content": "AOI8000专业版多少钱？"}]
  }'

# 预期回答：¥970,000
```

### 计算选型测试

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "messages": [{"role": "user", "content": "日产10万片PCB需要几台AOI8000？"}]
  }'

# 预期计算：10万 ÷ 5000片/小时 ÷ 20小时 = 1台
```

### 去重检测测试

```bash
# 触发去重检测
make trigger-dedup

# 查看检测结果
make ku-relations
```

## 关键参数参考

用于验证参数提取是否正确：

| 产品 | 参数 | 值 | 单位 |
|------|------|-----|------|
| AOI8000 | 检测精度 | 0.01 | mm |
| AOI8000 | 功率 | 200 | W |
| AOI8000 | 产能 | 5000 | 片/小时 |
| AOI8000 | 视野范围 | 500×400 | mm |
| AOI5000 | 检测精度 | 0.02 | mm |
| AOI5000 | 功率 | 150 | W |
| AOI5000 | 产能 | 3500 | 片/小时 |

## 报价参考

| 产品 | 版本 | 价格 |
|------|------|------|
| AOI8000 | 标准版 | ¥680,000 |
| AOI8000 | 专业版 | ¥970,000 |
| AOI8000 | 旗舰版 | ¥1,230,000 |
| AOI5000 | 标准版 | ¥380,000 |
| AOI5000 | 增强版 | ¥550,000 |
