#!/usr/bin/env python3
"""
Pipeline V2 迁移脚本
用于已部署环境的升级，支持：
1. 重建 OpenSearch 索引（新字段结构）
2. 清理中间数据（可选）
3. 重新运行 Pipeline 处理已有文件
"""
import os
import sys
import argparse
from datetime import datetime


def get_minio_client():
    """获取 MinIO 客户端"""
    from minio import Minio
    
    endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    access_key = os.getenv("MINIO_ROOT_USER", "minioadmin")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")
    
    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)


def get_opensearch_client():
    """获取 OpenSearch 客户端"""
    from opensearchpy import OpenSearch
    
    host = os.getenv("OPENSEARCH_HOST", "opensearch")
    port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    
    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        use_ssl=False,
        verify_certs=False
    )


def backup_index(os_client, index_name: str, backup_suffix: str = None):
    """
    备份现有索引
    
    Args:
        os_client: OpenSearch客户端
        index_name: 索引名称
        backup_suffix: 备份后缀，默认为时间戳
    """
    if not os_client.indices.exists(index=index_name):
        print(f"Index {index_name} does not exist, skipping backup")
        return None
    
    if backup_suffix is None:
        backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    backup_name = f"{index_name}_backup_{backup_suffix}"
    
    # 检查备份是否已存在
    if os_client.indices.exists(index=backup_name):
        print(f"Backup {backup_name} already exists")
        return backup_name
    
    # 创建备份（reindex）
    print(f"Creating backup: {backup_name}")
    
    # 先获取原索引的设置
    settings = os_client.indices.get_settings(index=index_name)
    mappings = os_client.indices.get_mapping(index=index_name)
    
    # 创建备份索引
    os_client.indices.create(
        index=backup_name,
        body={
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0
            },
            "mappings": mappings[index_name]["mappings"]
        }
    )
    
    # reindex 数据
    os_client.reindex(
        body={
            "source": {"index": index_name},
            "dest": {"index": backup_name}
        },
        wait_for_completion=True
    )
    
    # 验证
    count = os_client.count(index=backup_name)["count"]
    print(f"Backup complete: {count} documents in {backup_name}")
    
    return backup_name


def recreate_index(os_client, index_name: str):
    """
    重建索引（使用新的映射）
    """
    from scripts.create_opensearch_index import get_index_mapping
    
    # 删除旧索引
    if os_client.indices.exists(index=index_name):
        print(f"Deleting old index: {index_name}")
        os_client.indices.delete(index=index_name)
    
    # 创建新索引
    mapping = get_index_mapping()
    os_client.indices.create(index=index_name, body=mapping)
    print(f"Created new index: {index_name}")


def clear_intermediate_data(minio_client, buckets: list = None):
    """
    清理中间数据（bronze, silver, gold）
    
    Args:
        minio_client: MinIO客户端
        buckets: 要清理的bucket列表
    """
    if buckets is None:
        buckets = ["bronze", "silver", "gold"]
    
    for bucket in buckets:
        if not minio_client.bucket_exists(bucket):
            continue
        
        objects = list(minio_client.list_objects(bucket, recursive=True))
        if not objects:
            print(f"Bucket {bucket} is empty")
            continue
        
        print(f"Clearing {len(objects)} objects from {bucket}...")
        for obj in objects:
            minio_client.remove_object(bucket, obj.object_name)
        
        print(f"Cleared {bucket}")


def move_uploads_back(minio_client):
    """
    将已处理的文件从 bronze/raw 移回 uploads（用于重新处理）
    """
    if not minio_client.bucket_exists("bronze"):
        print("Bronze bucket does not exist")
        return 0
    
    from minio.commonconfig import CopySource
    
    objects = list(minio_client.list_objects("bronze", prefix="raw/", recursive=True))
    moved = 0
    
    for obj in objects:
        # raw/xxx -> xxx
        original_path = obj.object_name[4:]  # 移除 "raw/"
        
        # 检查 uploads 中是否已存在
        try:
            minio_client.stat_object("uploads", original_path)
            print(f"  {original_path} already exists in uploads, skipping")
            continue
        except Exception:
            pass
        
        # 复制回 uploads
        minio_client.copy_object(
            "uploads",
            original_path,
            CopySource("bronze", obj.object_name)
        )
        moved += 1
    
    print(f"Moved {moved} files back to uploads")
    return moved


def print_status(minio_client, os_client, index_name: str):
    """打印当前状态"""
    print("\n=== Current Status ===")
    
    # MinIO buckets
    for bucket in ["uploads", "bronze", "silver", "gold"]:
        if minio_client.bucket_exists(bucket):
            count = len(list(minio_client.list_objects(bucket, recursive=True)))
            print(f"  {bucket}: {count} objects")
        else:
            print(f"  {bucket}: not exists")
    
    # OpenSearch
    if os_client.indices.exists(index=index_name):
        count = os_client.count(index=index_name)["count"]
        mapping = os_client.indices.get_mapping(index=index_name)
        fields = list(mapping[index_name]["mappings"]["properties"].keys())
        print(f"  OpenSearch ({index_name}): {count} documents, {len(fields)} fields")
        
        # 检查新字段是否存在
        new_fields = ["scenario_id", "intent_types", "params", "applicability_score"]
        missing = [f for f in new_fields if f not in fields]
        if missing:
            print(f"    Missing new fields: {missing}")
        else:
            print(f"    New fields present: {new_fields}")
    else:
        print(f"  OpenSearch ({index_name}): index not exists")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline V2 Migration Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 查看当前状态
  python migrate_pipeline_v2.py --status
  
  # 仅重建索引（保留数据）
  python migrate_pipeline_v2.py --recreate-index
  
  # 完整迁移（备份 -> 重建索引 -> 清理数据 -> 移回uploads）
  python migrate_pipeline_v2.py --full-migrate
  
  # 不备份直接迁移（危险）
  python migrate_pipeline_v2.py --full-migrate --no-backup
        """
    )
    
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--recreate-index", action="store_true", help="Recreate OpenSearch index")
    parser.add_argument("--clear-data", action="store_true", help="Clear intermediate data (bronze, silver, gold)")
    parser.add_argument("--move-back", action="store_true", help="Move files from bronze/raw back to uploads")
    parser.add_argument("--full-migrate", action="store_true", help="Full migration (backup, recreate, clear, move)")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup (use with caution)")
    parser.add_argument("--index", default=None, help="Index name (default: from env)")
    
    args = parser.parse_args()
    
    index_name = args.index or os.getenv("OPENSEARCH_INDEX", "knowledge_units")
    
    print("Pipeline V2 Migration Script")
    print("=" * 40)
    
    try:
        minio_client = get_minio_client()
        os_client = get_opensearch_client()
        print("Connected to MinIO and OpenSearch")
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)
    
    if args.status:
        print_status(minio_client, os_client, index_name)
        return
    
    if args.full_migrate:
        print("\n=== Full Migration ===")
        
        # 1. 备份
        if not args.no_backup:
            print("\n[1/4] Backing up index...")
            backup_index(os_client, index_name)
        else:
            print("\n[1/4] Skipping backup (--no-backup)")
        
        # 2. 重建索引
        print("\n[2/4] Recreating index...")
        # 需要导入模块
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        recreate_index(os_client, index_name)
        
        # 3. 移动文件回 uploads
        print("\n[3/4] Moving files back to uploads...")
        move_uploads_back(minio_client)
        
        # 4. 清理中间数据
        print("\n[4/4] Clearing intermediate data...")
        clear_intermediate_data(minio_client)
        
        print("\n=== Migration Complete ===")
        print("Next steps:")
        print("  1. Trigger 'ingest_to_bronze' DAG")
        print("  2. Trigger 'extract_to_silver' DAG")
        print("  3. Trigger 'extract_params' DAG")
        print("  4. Trigger 'expand_and_rewrite_to_gold' DAG")
        print("  5. Trigger 'index_to_opensearch' DAG")
        print("\nOr use: make pipeline-full")
        return
    
    if args.recreate_index:
        if not args.no_backup:
            backup_index(os_client, index_name)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        recreate_index(os_client, index_name)
    
    if args.clear_data:
        clear_intermediate_data(minio_client)
    
    if args.move_back:
        move_uploads_back(minio_client)
    
    print_status(minio_client, os_client, index_name)


if __name__ == "__main__":
    main()

