#!/usr/bin/env python3
"""
MinIO 事件通知配置脚本
配置文件上传自动触发 n8n -> Airflow
"""
import os
import subprocess
import json

MINIO_ALIAS = "adf"
MINIO_URL = os.getenv("MINIO_URL", "http://minio:9000")
MINIO_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_PASS = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://n8n:5678/webhook/file-uploaded")


def print_setup_guide():
    """打印配置指南"""
    print(f"""
============================================================
MinIO 事件通知配置指南
============================================================

目标: 文件上传到 uploads bucket 时自动触发 Airflow DAG

方式: MinIO -> Webhook -> n8n -> Airflow

============================================================
方法 1: 使用 mc 命令行工具 (推荐)
============================================================

# 1. 进入 MinIO 容器或安装 mc
docker compose exec minio sh

# 2. 配置 mc alias
mc alias set {MINIO_ALIAS} {MINIO_URL} {MINIO_USER} {MINIO_PASS}

# 3. 添加 webhook 目标
mc admin config set {MINIO_ALIAS} notify_webhook:n8n \\
    endpoint="{N8N_WEBHOOK_URL}" \\
    queue_limit="10000"

# 4. 重启 MinIO 使配置生效
mc admin service restart {MINIO_ALIAS}

# 5. 为 uploads bucket 添加事件通知
mc event add {MINIO_ALIAS}/uploads arn:minio:sqs::n8n:webhook \\
    --event put \\
    --suffix ".pdf,.docx,.doc,.txt,.md"

# 6. 验证配置
mc event list {MINIO_ALIAS}/uploads

============================================================
方法 2: 使用 MinIO Console UI
============================================================

1. 访问 MinIO Console: http://<ECS_IP>:9001
   - 用户名: minioadmin
   - 密码: (你的密码)

2. 配置 Webhook:
   - Settings -> Configuration -> notify_webhook
   - 添加:
     - Name: n8n
     - Endpoint: http://n8n:5678/webhook/file-uploaded
   - Save

3. 重启 MinIO 服务

4. 配置 Bucket 事件:
   - Buckets -> uploads -> Events
   - Add Event Destination
   - ARN: arn:minio:sqs::n8n:webhook
   - Events: s3:ObjectCreated:Put
   - Suffix: .pdf,.docx,.txt

============================================================
方法 3: 简化方案 - 定时轮询
============================================================

如果 Webhook 配置复杂，可以使用定时轮询:

1. 修改 Airflow DAG 为定时触发 (每 5 分钟)
2. DAG 自动检查 uploads bucket 中的新文件
3. 处理后移动到 processed/ 目录

这个方案已在 ingest_to_bronze.py 中实现，只需启用定时调度。

============================================================
测试事件通知
============================================================

# 上传测试文件
mc cp test.pdf {MINIO_ALIAS}/uploads/

# 检查 n8n 执行日志
# 检查 Airflow DAG 运行记录

============================================================
""")


def check_mc_available():
    """检查 mc 是否可用"""
    try:
        result = subprocess.run(["mc", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ mc 已安装: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    print("✗ mc 未安装，请使用 MinIO Console 或进入容器配置")
    return False


def setup_with_mc():
    """使用 mc 配置事件通知"""
    print("\n尝试使用 mc 配置...")
    
    # 配置 alias
    cmd_alias = f"mc alias set {MINIO_ALIAS} {MINIO_URL} {MINIO_USER} {MINIO_PASS}"
    result = subprocess.run(cmd_alias.split(), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"✗ 配置 alias 失败: {result.stderr}")
        return False
    print("✓ 配置 alias 成功")
    
    # 配置 webhook
    cmd_webhook = f"mc admin config set {MINIO_ALIAS} notify_webhook:n8n endpoint={N8N_WEBHOOK_URL}"
    result = subprocess.run(cmd_webhook.split(), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"⚠ 配置 webhook 失败 (可能需要重启): {result.stderr}")
    else:
        print("✓ 配置 webhook 成功")
    
    print("\n需要手动重启 MinIO 并添加事件通知，请参考上方指南")
    return True


def main():
    print("=" * 60)
    print("MinIO 事件通知配置")
    print("=" * 60)
    
    print_setup_guide()
    
    # 检查是否可以自动配置
    if check_mc_available():
        response = input("\n是否尝试自动配置? (y/n): ").strip().lower()
        if response == 'y':
            setup_with_mc()
    
    print("""
============================================================
快速测试 (不配置事件通知)
============================================================

即使不配置事件通知，也可以手动触发:

# 方式 1: 调用 n8n Webhook
curl -X POST http://<ECS_IP>:5678/webhook/file-uploaded \\
  -H "Content-Type: application/json" \\
  -d '{"filename": "your-file.pdf", "bucket": "uploads"}'

# 方式 2: 在 Airflow UI 手动触发
访问 http://<ECS_IP>:8080
找到 ingest_to_bronze DAG
点击 "Trigger DAG"

# 方式 3: 使用 Airflow CLI
docker compose exec airflow airflow dags trigger ingest_to_bronze

============================================================
""")


if __name__ == "__main__":
    main()

