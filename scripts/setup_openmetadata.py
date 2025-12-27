#!/usr/bin/env python3
"""
OpenMetadata 配置脚本
配置数据源连接
"""
import os

OPENMETADATA_URL = os.getenv("OPENMETADATA_URL", "http://localhost:8585")


def print_setup_guide():
    """打印配置指南"""
    print("""
============================================================
OpenMetadata 配置指南
============================================================

1. 访问 OpenMetadata: http://<ECS_IP>:8585

2. 首次登录:
   - 用户名: admin
   - 密码: admin

3. 添加 PostgreSQL 数据源:
   - Settings -> Databases -> Add New Database Service
   - Service Type: Postgres
   - Name: adf-postgres
   - Connection:
     - Host: postgres
     - Port: 5432
     - Username: adf
     - Password: (你的密码)
     - Database: adf
   - Test Connection -> Save

4. 添加 MinIO 数据源:
   - Settings -> Storage -> Add New Storage Service
   - Service Type: S3 (MinIO 兼容)
   - Name: adf-minio
   - Connection:
     - AWS Access Key: minioadmin
     - AWS Secret Key: (你的密码)
     - Endpoint URL: http://minio:9000
   - Save

5. 添加 OpenSearch 数据源:
   - Settings -> Search -> Add New Search Service
   - Service Type: OpenSearch
   - Name: adf-opensearch
   - Connection:
     - Host: opensearch
     - Port: 9200
   - Save

6. 运行元数据摄取:
   - 对每个数据源，点击 "Ingestion" -> "Add Ingestion"
   - 选择 "Metadata" 类型
   - 配置调度（如每天一次）
   - 运行

============================================================
OpenMetadata 功能说明
============================================================

- Data Discovery: 搜索和浏览数据资产
- Data Lineage: 数据血缘追踪
- Data Quality: 数据质量监控
- Glossary: 业务术语表
- Tags: 数据分类标签
- Teams: 数据所有权管理

============================================================
与 AI Data Factory 集成
============================================================

1. KU 元数据管理:
   - 在 OpenMetadata 中创建 "Knowledge Units" 表的元数据
   - 添加描述、标签、所有者

2. Pipeline 血缘:
   - 记录 Airflow DAG 的数据流向
   - 从 uploads -> bronze -> silver -> gold -> OpenSearch

3. 数据质量:
   - 配置 Great Expectations 规则
   - 在 OpenMetadata 中查看 DQ 结果

============================================================
""")


def check_openmetadata_health():
    """检查 OpenMetadata 是否运行"""
    import requests
    try:
        response = requests.get(f"{OPENMETADATA_URL}/api/v1/system/version", timeout=5)
        if response.status_code == 200:
            version = response.json().get("version", "unknown")
            print(f"✓ OpenMetadata 运行正常: {OPENMETADATA_URL} (v{version})")
            return True
        else:
            print(f"⚠ OpenMetadata 响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 无法连接 OpenMetadata: {e}")
        return False


def main():
    print("=" * 60)
    print("OpenMetadata 配置")
    print("=" * 60)
    
    check_openmetadata_health()
    print_setup_guide()


if __name__ == "__main__":
    main()

