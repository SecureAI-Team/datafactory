#!/usr/bin/env python3
"""
上传测试数据到 MinIO

用法:
    python scripts/upload_test_data.py [--scenario SCENARIO] [--dry-run]

示例:
    # 上传所有测试数据
    python scripts/upload_test_data.py
    
    # 只上传 AOI 检测场景
    python scripts/upload_test_data.py --scenario aoi_inspection
    
    # 预览（不实际上传）
    python scripts/upload_test_data.py --dry-run
"""

import os
import sys
import argparse
import mimetypes
from pathlib import Path
from datetime import datetime

try:
    from minio import Minio
    from minio.error import S3Error
except ImportError:
    print("请先安装 minio 库: pip install minio")
    sys.exit(1)


# MinIO 配置
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minio123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "uploads")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# 数据目录
DATA_DIR = Path(__file__).parent.parent / "data"

# 支持的文件类型
SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf", ".docx", ".xlsx", ".pptx", ".json"}


def get_minio_client():
    """创建 MinIO 客户端"""
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )


def ensure_bucket(client, bucket_name):
    """确保 bucket 存在"""
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        print(f"✅ 创建 bucket: {bucket_name}")
    else:
        print(f"📦 Bucket 已存在: {bucket_name}")


def get_content_type(file_path):
    """获取文件的 Content-Type"""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type:
        return mime_type
    
    # 常见扩展名映射
    ext_map = {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".json": "application/json",
    }
    return ext_map.get(file_path.suffix.lower(), "application/octet-stream")


def collect_files(data_dir, scenario=None):
    """收集要上传的文件"""
    files = []
    
    for root, dirs, filenames in os.walk(data_dir):
        # 跳过非场景目录
        root_path = Path(root)
        relative = root_path.relative_to(data_dir)
        
        # 如果指定了场景，只处理该场景
        if scenario:
            parts = relative.parts
            if parts and parts[0] != scenario:
                continue
        
        # 跳过根目录下的非材料文件
        if root_path == data_dir:
            # 只跳过 README 和 scenarios.json
            filenames = [f for f in filenames if f not in ("README.md", "scenarios.json")]
        
        for filename in filenames:
            file_path = root_path / filename
            if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(file_path)
    
    return files


def upload_file(client, bucket, file_path, data_dir, dry_run=False):
    """上传单个文件到 MinIO"""
    # 计算在 MinIO 中的对象名
    relative_path = file_path.relative_to(data_dir)
    object_name = str(relative_path).replace("\\", "/")
    
    content_type = get_content_type(file_path)
    file_size = file_path.stat().st_size
    
    if dry_run:
        print(f"  [预览] {object_name} ({file_size} bytes, {content_type})")
        return True
    
    try:
        client.fput_object(
            bucket,
            object_name,
            str(file_path),
            content_type=content_type,
        )
        print(f"  ✅ {object_name}")
        return True
    except S3Error as e:
        print(f"  ❌ {object_name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="上传测试数据到 MinIO")
    parser.add_argument(
        "--scenario",
        help="只上传指定场景 (如: aoi_inspection)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际上传",
    )
    parser.add_argument(
        "--endpoint",
        default=MINIO_ENDPOINT,
        help=f"MinIO 端点 (默认: {MINIO_ENDPOINT})",
    )
    parser.add_argument(
        "--bucket",
        default=MINIO_BUCKET,
        help=f"目标 bucket (默认: {MINIO_BUCKET})",
    )
    args = parser.parse_args()
    
    # 检查数据目录
    if not DATA_DIR.exists():
        print(f"❌ 数据目录不存在: {DATA_DIR}")
        sys.exit(1)
    
    # 收集文件
    print(f"\n📂 扫描数据目录: {DATA_DIR}")
    if args.scenario:
        print(f"   场景过滤: {args.scenario}")
    
    files = collect_files(DATA_DIR, args.scenario)
    
    if not files:
        print("⚠️  没有找到要上传的文件")
        sys.exit(0)
    
    print(f"\n📋 找到 {len(files)} 个文件待上传")
    
    # 按场景分组显示
    by_scenario = {}
    for f in files:
        rel = f.relative_to(DATA_DIR)
        scenario = rel.parts[0] if len(rel.parts) > 1 else "root"
        by_scenario.setdefault(scenario, []).append(f)
    
    for scenario, scenario_files in by_scenario.items():
        print(f"   - {scenario}: {len(scenario_files)} 个文件")
    
    if args.dry_run:
        print("\n🔍 预览模式 (不实际上传)\n")
    else:
        print(f"\n🚀 开始上传到 {args.endpoint}/{args.bucket}\n")
    
    # 连接 MinIO
    if not args.dry_run:
        try:
            client = get_minio_client()
            ensure_bucket(client, args.bucket)
        except Exception as e:
            print(f"❌ 连接 MinIO 失败: {e}")
            sys.exit(1)
    else:
        client = None
    
    # 上传文件
    success = 0
    failed = 0
    
    for scenario, scenario_files in by_scenario.items():
        print(f"\n📁 {scenario}:")
        for file_path in scenario_files:
            if upload_file(client, args.bucket, file_path, DATA_DIR, args.dry_run):
                success += 1
            else:
                failed += 1
    
    # 汇总
    print(f"\n{'='*50}")
    print(f"📊 上传完成")
    print(f"   成功: {success}")
    print(f"   失败: {failed}")
    
    if not args.dry_run and success > 0:
        print(f"\n💡 下一步:")
        print(f"   1. 运行 Pipeline: make pipeline-full")
        print(f"   2. 查看索引: make index-status")
        print(f"   3. 测试检索: make verify")


if __name__ == "__main__":
    main()

