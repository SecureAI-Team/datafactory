# AI Data Factory (single-VM, docker-compose)

一站式 AI 数据工厂：文档处理 → 知识提取 → RAG 对话

---

## 📋 目录

- [系统架构](#-系统架构)
- [用户角色与旅程](#-用户角色与旅程)
- [一键部署](#-一键部署-阿里云-ecs)
- [服务访问](#-服务访问地址)
- [Make 命令](#-make-命令)
- [更多文档](#-更多文档)

---

## 🏗️ 系统架构

```mermaid
flowchart TB
    subgraph users [👥 用户层]
        DE[🔧 数据工程师]
        BD[💼 BD/Sales]
    end
    
    subgraph frontend [🖥️ 前端入口]
        WebUI[Open WebUI<br/>智能问答]
        Budibase[Budibase<br/>管理后台]
        Airflow[Airflow<br/>Pipeline 监控]
    end
    
    subgraph api [⚡ API 服务层]
        Gateway[RAG Gateway]
        KUAPI[KU 管理 API]
        BDAPI[BD 专用 API]
        DedupAPI[去重 API]
    end
    
    subgraph core [🧠 核心处理]
        Intent[意图识别]
        Retrieval[场景化检索]
        Calc[计算引擎]
        Response[回答构建]
    end
    
    subgraph pipeline [🔄 数据 Pipeline]
        Ingest[Ingest<br/>文档入库]
        Extract[Extract<br/>文本提取]
        Expand[Expand<br/>LLM 扩展]
        Index[Index<br/>索引构建]
        Dedup[Dedup<br/>重复检测]
    end
    
    subgraph storage [💾 存储层]
        MinIO[(MinIO<br/>对象存储)]
        PG[(PostgreSQL<br/>元数据)]
        OS[(OpenSearch<br/>知识检索)]
        Neo4j[(Neo4j<br/>知识图谱)]
    end
    
    subgraph llm [🤖 AI 服务]
        Qwen[阿里云百炼<br/>Qwen]
    end
    
    DE --> Budibase
    DE --> Airflow
    BD --> WebUI
    
    WebUI --> Gateway
    Budibase --> KUAPI
    Budibase --> DedupAPI
    
    Gateway --> Intent
    Gateway --> Retrieval
    Gateway --> Response
    
    Intent --> Retrieval
    Retrieval --> OS
    Retrieval --> Neo4j
    Response --> Qwen
    
    Ingest --> MinIO
    Extract --> MinIO
    Expand --> MinIO
    Expand --> Qwen
    Index --> OS
    Dedup --> PG
    
    KUAPI --> PG
    KUAPI --> MinIO
```

---

## 👥 用户角色与旅程

### 角色职责概览

```mermaid
flowchart LR
    subgraph dataOps [🔧 数据工程师]
        D1[📤 上传资料]
        D2[📊 监控 Pipeline]
        D3[✅ 审核 KU 质量]
        D4[🔀 处理重复]
        D5[🏷️ 维护元数据]
    end
    
    subgraph bdSales [💼 BD/Sales]
        B1[💬 智能问答]
        B2[📋 查找案例]
        B3[💰 获取报价]
        B4[📝 生成方案]
    end
    
    subgraph shared [🤝 共享功能]
        S1[📚 知识库浏览]
        S2[👍 反馈评价]
    end
    
    D1 --> S1
    B1 --> S1
    B1 --> S2
    D3 --> S2
```

### 界面入口对照

| 功能 | 数据工程师入口 | BD/Sales 入口 |
|------|---------------|---------------|
| 上传资料 | Budibase 上传页 | - |
| 监控 Pipeline | Airflow UI | - |
| 审核 KU | Budibase 审核页 | - |
| 处理重复 | Budibase 去重页 | - |
| 智能问答 | Open WebUI | ✅ Open WebUI |
| 查找案例 | - | Open WebUI (意图识别) |
| 获取报价 | - | Open WebUI (意图识别) |
| 浏览知识库 | Budibase KU 列表 | Open WebUI 附带链接 |
| 反馈评价 | Budibase 报告 | Open WebUI 点赞/踩 |

---

## 🔧 数据工程师旅程

### 场景 1：上传资料

```mermaid
sequenceDiagram
    autonumber
    actor DE as 🔧 数据工程师
    participant Budi as Budibase<br/>上传页面
    participant API as FastAPI
    participant MinIO as MinIO
    participant Airflow as Airflow
    participant Pipeline as Pipeline
    
    DE->>Budi: 拖拽上传文件<br/>(白皮书、案例、规格书)
    Budi->>API: POST /api/ingest/preview
    API-->>Budi: 返回分类预览<br/>(ku_type, product_id)
    
    DE->>Budi: 确认/修改分类
    Budi->>API: POST /api/ingest/batch
    API->>MinIO: 上传到 uploads/
    API->>Airflow: 触发 DAG
    API-->>Budi: 返回任务 ID
    
    Airflow->>Pipeline: 执行 ingest → extract → expand → index
    Pipeline-->>Airflow: 完成
    
    DE->>Airflow: 查看处理状态
    Airflow-->>DE: 显示 DAG 运行结果
```

### 场景 2：KU 质量审核

```mermaid
sequenceDiagram
    autonumber
    actor DE as 🔧 数据工程师
    participant Budi as Budibase<br/>审核页面
    participant API as FastAPI
    participant PG as PostgreSQL
    participant OS as OpenSearch
    
    DE->>Budi: 进入审核页面
    Budi->>API: GET /api/ku?status=pending
    API->>PG: 查询待审核 KU
    PG-->>API: 返回 KU 列表
    API-->>Budi: 显示待审核队列
    
    DE->>Budi: 点击查看 KU 详情
    Budi->>API: GET /api/ku/{id}
    API-->>Budi: 返回完整内容<br/>(标题、摘要、参数、正文)
    
    alt 批准
        DE->>Budi: 点击"批准"
        Budi->>API: POST /api/ku/{id}/approve
        API->>PG: 更新状态为 published
        API->>OS: 索引到 OpenSearch
    else 拒绝
        DE->>Budi: 点击"拒绝"并填写原因
        Budi->>API: POST /api/ku/{id}/reject
        API->>PG: 更新状态为 rejected
    else 退回修改
        DE->>Budi: 编辑内容后保存
        Budi->>API: PUT /api/ku/{id}
        API->>PG: 更新 KU 内容
    end
```

### 场景 3：处理重复 KU

```mermaid
sequenceDiagram
    autonumber
    actor DE as 🔧 数据工程师
    participant Budi as Budibase<br/>去重页面
    participant API as FastAPI
    participant PG as PostgreSQL
    participant Airflow as Airflow
    
    Note over DE,Airflow: 定时任务自动检测重复
    Airflow->>PG: 扫描 KU，检测相似度 > 85%
    Airflow->>PG: 创建 dedup_groups
    
    DE->>Budi: 进入去重工作台
    Budi->>API: GET /v1/dedup/pending
    API-->>Budi: 返回疑似重复组列表
    
    DE->>Budi: 点击查看重复组详情
    Budi->>API: GET /v1/dedup/group/{id}/details
    API-->>Budi: 返回并排对比视图
    
    alt 确认合并
        DE->>Budi: 点击"合并"
        Budi->>API: POST /v1/dedup/approve
        API->>PG: 标记为 approved
        Note over API,PG: Airflow 定时执行合并
    else 保留两者
        DE->>Budi: 点击"保留全部"
        Budi->>API: POST /v1/dedup/dismiss
        API->>PG: 标记为 dismissed
    end
```

### 场景 4：监控 Pipeline

```mermaid
flowchart TB
    subgraph monitor [📊 Pipeline 监控仪表盘]
        subgraph status [DAG 运行状态]
            S1[✅ ingest_to_bronze<br/>成功 98%]
            S2[✅ extract_to_silver<br/>成功 95%]
            S3[⚠️ expand_to_gold<br/>成功 87%]
            S4[✅ index_to_opensearch<br/>成功 99%]
        end
        
        subgraph metrics [关键指标]
            M1[📄 今日处理: 156 文件]
            M2[📦 生成 KU: 89 个]
            M3[⏱️ 平均耗时: 45s/文件]
            M4[❌ 失败: 3 个]
        end
        
        subgraph alerts [告警]
            A1[🔴 expand DAG 失败率上升]
            A2[🟡 队列积压 > 100]
        end
    end
    
    DE[🔧 数据工程师] --> monitor
    
    subgraph actions [操作]
        Act1[🔄 重试失败任务]
        Act2[🔍 查看错误日志]
        Act3[⏸️ 暂停 DAG]
    end
    
    alerts --> actions
```

---

## 💼 BD/Sales 旅程

### 场景 1：智能问答

```mermaid
sequenceDiagram
    autonumber
    actor BD as 💼 BD/Sales
    participant WebUI as Open WebUI
    participant Gateway as RAG Gateway
    participant Intent as 意图识别
    participant Search as 场景化检索
    participant OS as OpenSearch
    participant LLM as Qwen LLM
    
    BD->>WebUI: 输入问题<br/>"AOI设备功率是多少？"
    WebUI->>Gateway: POST /v1/chat/completions
    
    Gateway->>Intent: 识别意图
    Intent-->>Gateway: 意图: parameter_query<br/>实体: {产品: AOI, 参数: 功率}
    
    Gateway->>Search: 场景化检索
    Search->>OS: 查询 KU + 参数过滤
    OS-->>Search: 返回匹配 KU
    Search-->>Gateway: Top 5 结果 + 关联 KU
    
    Gateway->>LLM: 生成回答<br/>(query + context)
    LLM-->>Gateway: 回答文本
    
    Gateway-->>WebUI: 返回回答 + 来源
    WebUI-->>BD: 显示结果<br/>"AOI8000功率为200W【来源: 产品规格书】"
```

### 场景 2：查找案例

```mermaid
sequenceDiagram
    autonumber
    actor BD as 💼 BD/Sales
    participant WebUI as Open WebUI
    participant Gateway as RAG Gateway
    participant Intent as 意图识别
    participant Search as 检索服务
    participant OS as OpenSearch
    
    BD->>WebUI: "给我找一个金融行业的案例"
    WebUI->>Gateway: POST /v1/chat/completions
    
    Gateway->>Intent: 识别意图
    Intent-->>Gateway: 意图: case_study<br/>筛选: {industry: 金融}
    
    Gateway->>Search: 案例检索
    Search->>OS: 查询 ku_type:case<br/>+ industry_tags:金融
    OS-->>Search: 返回案例列表
    
    Gateway-->>WebUI: 格式化回答
    
    Note over WebUI,BD: 专用案例回答模板
    WebUI-->>BD: 找到 3 个相关案例：<br/>1. XX银行智能风控案例<br/>   行业: 金融 | 规模: 大型<br/>   亮点: 效率提升40%<br/>2. ...
```

### 场景 3：获取报价

```mermaid
sequenceDiagram
    autonumber
    actor BD as 💼 BD/Sales
    participant WebUI as Open WebUI
    participant Gateway as RAG Gateway
    participant Search as 检索服务
    participant OS as OpenSearch
    participant Calc as 计算引擎
    
    BD->>WebUI: "产品A100多少钱？"
    WebUI->>Gateway: POST /v1/chat/completions
    
    Gateway->>Search: 报价检索
    Search->>OS: 查询 ku_type:quote<br/>+ product_id:A100
    OS-->>Search: 返回报价 KU
    
    alt 有现成报价
        Gateway-->>WebUI: 返回报价信息
        WebUI-->>BD: 产品A100报价：<br/>标准版: ¥50,000<br/>企业版: ¥120,000<br/>⚠️ 报价有效期至2024-03
    else 需要计算
        BD->>WebUI: "10台设备配置费用"
        Gateway->>Calc: 执行计算
        Calc-->>Gateway: 计算结果
        Gateway-->>WebUI: 返回计算后报价
    end
```

### 场景 4：生成方案

```mermaid
sequenceDiagram
    autonumber
    actor BD as 💼 BD/Sales
    participant WebUI as Open WebUI
    participant Gateway as RAG Gateway
    participant Search as 检索服务
    participant LLM as Qwen LLM
    
    BD->>WebUI: "帮我生成一个智能制造方案大纲"
    WebUI->>Gateway: POST /v1/bd/generate-proposal
    
    Gateway->>Search: 搜索相关内容
    Note over Search: 检索 solution/case/core KU
    Search-->>Gateway: 相关 KU 列表
    
    Gateway->>LLM: 生成方案大纲
    LLM-->>Gateway: 返回大纲
    
    Gateway-->>WebUI: 格式化输出
    WebUI-->>BD: 📋 智能制造解决方案<br/><br/>1. 背景与需求分析<br/>2. 解决方案概述<br/>3. 详细方案设计<br/>   - 产品: AOI8000, ...<br/>4. 成功案例<br/>5. 实施计划<br/>6. 投资预算
```

### 快捷命令

```mermaid
flowchart LR
    subgraph commands [⌨️ BD 快捷命令]
        C1["/案例 金融行业"]
        C2["/报价 产品A100"]
        C3["/方案 网络安全"]
        C4["/对比 A100 vs B200"]
    end
    
    subgraph results [📤 快速响应]
        R1[返回案例列表 + 亮点]
        R2[返回报价信息]
        R3[生成方案大纲]
        R4[规格对比表格]
    end
    
    C1 --> R1
    C2 --> R2
    C3 --> R3
    C4 --> R4
```

---

## 🔄 数据处理 Pipeline

### 完整数据流

```mermaid
flowchart TB
    subgraph upload [📤 上传阶段]
        U1[用户上传文档]
        U2[MinIO: uploads/]
    end
    
    subgraph bronze [🥉 Bronze 层]
        B1[ingest_to_bronze DAG]
        B2[解析元数据<br/>场景/产品/类型]
        B3[MinIO: bronze/]
    end
    
    subgraph silver [🥈 Silver 层]
        S1[extract_to_silver DAG]
        S2[Tika 文本提取]
        S3[Unstructured 结构化]
        S4[材料分类器]
        S5[MinIO: silver/]
    end
    
    subgraph gold [🥇 Gold 层]
        G1[expand_to_gold DAG]
        G2[LLM 扩展重写]
        G3[参数提取]
        G4[生成 KU]
        G5[MinIO: gold/]
    end
    
    subgraph index [🔍 索引阶段]
        I1[index_to_opensearch DAG]
        I2[OpenSearch 索引]
    end
    
    subgraph dedup [🔀 去重阶段]
        D1[merge_duplicates DAG]
        D2[相似度检测]
        D3[智能合并]
    end
    
    U1 --> U2
    U2 --> B1
    B1 --> B2
    B2 --> B3
    
    B3 --> S1
    S1 --> S2
    S2 --> S3
    S3 --> S4
    S4 --> S5
    
    S5 --> G1
    G1 --> G2
    G2 --> G3
    G3 --> G4
    G4 --> G5
    
    G5 --> I1
    I1 --> I2
    
    I2 --> D1
    D1 --> D2
    D2 --> D3
    D3 -.-> I2
```

### KU 类型与处理策略

```mermaid
flowchart LR
    subgraph input [📥 输入材料]
        I1[产品白皮书]
        I2[技术规格书]
        I3[客户案例]
        I4[报价单]
        I5[解决方案]
    end
    
    subgraph classify [🏷️ 分类]
        C1[core<br/>核心产品信息]
        C2[case<br/>客户案例]
        C3[quote<br/>报价信息]
        C4[solution<br/>解决方案]
    end
    
    subgraph strategy [📋 处理策略]
        S1[智能合并<br/>去重保留最全]
        S2[独立保存<br/>关联到产品]
        S3[独立保存<br/>注意时效性]
        S4[独立保存<br/>按场景分类]
    end
    
    I1 --> C1
    I2 --> C1
    I3 --> C2
    I4 --> C3
    I5 --> C4
    
    C1 --> S1
    C2 --> S2
    C3 --> S3
    C4 --> S4
```

---

## 🚀 一键部署 (阿里云 ECS)

```bash
# 1. SSH 登录 ECS
ssh root@YOUR_ECS_IP

# 2. 下载代码到 /opt/datafactory
mkdir -p /opt/datafactory && cd /opt/datafactory
git clone https://github.com/yourorg/ai-data-factory.git .

# 3. 一键部署
chmod +x deploy.sh
DASHSCOPE_API_KEY=sk-你的百炼Key bash deploy.sh

# 部署完成后访问:
# Chat: http://YOUR_IP:3001
# API:  http://YOUR_IP:8000/docs
```

## 🔧 手动部署

```bash
# 1. 克隆并配置
git clone https://github.com/yourorg/ai-data-factory.git
cd ai-data-factory
cp .env.example .env

# 2. 编辑 .env 配置 API Key
# DASHSCOPE_API_KEY=sk-xxxxx  # 阿里云百炼 API Key

# 3. 启动服务
make init up

# 4. 查看状态
make status
```

---

## 📍 服务访问地址

| 服务 | 地址 | 说明 | 用户角色 |
|------|------|------|----------|
| 💬 Chat (Open WebUI) | http://IP:3001 | AI 对话界面 | BD/Sales |
| 📝 Budibase | http://IP:10000 | 管理后台 | 数据工程师 |
| 🌬️ Airflow | http://IP:8080 | Pipeline 监控 | 数据工程师 |
| 🔧 API Docs | http://IP:8000/docs | FastAPI 文档 | 开发者 |
| 📊 Langfuse | http://IP:3000 | LLM 追踪 | 开发者 |
| 🔄 n8n | http://IP:5678 | 自动化工作流 | 管理员 |
| 💾 MinIO Console | http://IP:9001 | 对象存储 | 管理员 |
| 🔍 OpenSearch | http://IP:9200 | 搜索引擎 | 管理员 |

## 🔑 默认账户

| 服务 | 用户名 | 密码 |
|------|--------|------|
| Airflow | admin | admin123 |
| MinIO | minio | minio123 |
| Budibase | admin@example.com | admin |
| Langfuse | 首次注册创建 | - |
| n8n | 首次注册创建 | - |

---

## 📦 Make 命令

### 基础操作

```bash
make up        # 启动所有服务
make down      # 停止服务
make logs      # 查看日志
make status    # 查看状态
make help      # 查看所有命令
```

### Pipeline 操作

```bash
make pipeline         # 触发完整 Pipeline
make pipeline-ingest  # 仅运行 ingest (uploads → bronze)
make pipeline-extract # 仅运行 extract (bronze → silver)
make pipeline-expand  # 仅运行 expand (silver → gold)
make pipeline-index   # 仅运行 index (gold → OpenSearch)
make trigger-dedup    # 触发重复检测
```

### 升级命令

```bash
make upgrade-phase-a  # 数据模型增强
make upgrade-phase-b  # Pipeline 增强
make upgrade-phase-c  # 检索增强
make upgrade-phase-d  # UI/UX 增强
```

### 验证和调试

```bash
make verify       # 验证 RAG 流程
make smoke        # 健康检查
make buckets      # 查看 MinIO 内容
make index-status # 查看索引状态
make ku-relations # 查看 KU 关系统计
```

---

## 📋 资源需求

推荐配置: 8 vCPU / 16GB RAM
最低配置: 4 vCPU / 8GB RAM (禁用部分服务)

禁用可选服务:
```bash
# 在 .env 中设置
DISABLE_BUDIBASE=1
DISABLE_OPENMETADATA=1
DISABLE_LANGFUSE=1
```

## 🔐 安全说明

- Open WebUI 通过 Nginx 反向代理，可配置 Basic Auth
- API 支持 JWT 认证，角色: `DATA_OPS`, `BD