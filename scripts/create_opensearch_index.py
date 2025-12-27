#!/usr/bin/env python3
"""
创建/更新 OpenSearch 索引
支持场景化字段和结构化参数
"""
import os
import sys
from urllib.parse import urlparse
from opensearchpy import OpenSearch


def get_opensearch_client():
    """获取 OpenSearch 客户端"""
    url = os.environ.get("OPENSEARCH_URL")
    host_env = os.environ.get("OPENSEARCH_HOST", "opensearch")
    port_env = os.environ.get("OPENSEARCH_PORT", "9200")

    if url:
        parsed = urlparse(url if "://" in url else f"http://{url}")
        host = parsed.hostname or host_env
        port = parsed.port or int(port_env)
        scheme = parsed.scheme
    else:
        host = host_env
        port = int(port_env)
        scheme = "http"

    return OpenSearch(
        hosts=[{"host": host, "port": port, "scheme": scheme}],
        use_ssl=False,
        verify_certs=False
    )


def get_index_mapping():
    """获取增强后的索引映射"""
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "default": {
                        "type": "standard"
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                # 基础内容字段
                "title": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                },
                "summary": {
                    "type": "text",
                    "analyzer": "standard"
                },
                "full_text": {
                    "type": "text",
                    "analyzer": "standard"
                },
                "key_points": {
                    "type": "text",
                    "analyzer": "standard"
                },
                "terms": {
                    "type": "keyword"
                },
                
                # 场景化字段
                "scenario_id": {
                    "type": "keyword"
                },
                "scenario_tags": {
                    "type": "keyword"
                },
                "solution_id": {
                    "type": "keyword"
                },
                "intent_types": {
                    "type": "keyword"
                },
                "material_type": {
                    "type": "keyword"
                },
                "applicability_score": {
                    "type": "float"
                },
                
                # 结构化参数（nested类型支持精确查询）
                "params": {
                    "type": "nested",
                    "properties": {
                        "name": {"type": "keyword"},
                        "value": {"type": "float"},
                        "min": {"type": "float"},
                        "max": {"type": "float"},
                        "unit": {"type": "keyword"},
                        "type": {"type": "keyword"}
                    }
                },
                
                # 来源信息
                "source_file": {
                    "type": "keyword"
                },
                "original_path": {
                    "type": "keyword"
                },
                
                # 时间戳
                "indexed_at": {
                    "type": "date"
                },
                "generated_at": {
                    "type": "date"
                },
                
                # 兼容旧字段（逐步废弃）
                "body": {
                    "type": "text"
                },
                "tags": {
                    "type": "keyword"
                },
                "glossary_terms": {
                    "type": "keyword"
                },
                "source_refs": {
                    "type": "nested"
                },
                "updated_at": {
                    "type": "date"
                }
            }
        }
    }


def create_index(client: OpenSearch, index_name: str, force_recreate: bool = False):
    """
    创建索引
    
    Args:
        client: OpenSearch客户端
        index_name: 索引名称
        force_recreate: 是否强制重建（删除旧索引）
    """
    exists = client.indices.exists(index=index_name)
    
    if exists:
        if force_recreate:
            print(f"Deleting existing index: {index_name}")
            client.indices.delete(index=index_name)
        else:
            print(f"Index {index_name} already exists. Use --force to recreate.")
            # 尝试更新映射（只能添加新字段）
            try:
                current_mapping = client.indices.get_mapping(index=index_name)
                print("Attempting to update mapping with new fields...")
                new_mapping = get_index_mapping()["mappings"]
                client.indices.put_mapping(index=index_name, body=new_mapping)
                print("Mapping updated successfully (new fields added)")
            except Exception as e:
                print(f"Could not update mapping: {e}")
                print("To add incompatible changes, use --force to recreate the index")
            return
    
    # 创建新索引
    mapping = get_index_mapping()
    client.indices.create(index=index_name, body=mapping)
    print(f"Created index: {index_name}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Create or update OpenSearch index")
    parser.add_argument("--force", action="store_true", help="Force recreate index (deletes existing)")
    parser.add_argument("--index", default=None, help="Index name (default: from env)")
    args = parser.parse_args()
    
    index_name = args.index or os.environ.get("OPENSEARCH_INDEX", "knowledge_units")
    
    print(f"Connecting to OpenSearch...")
    client = get_opensearch_client()
    
    # 检查连接
    try:
        info = client.info()
        print(f"Connected to OpenSearch {info.get('version', {}).get('number', 'unknown')}")
    except Exception as e:
        print(f"Failed to connect to OpenSearch: {e}")
        sys.exit(1)
    
    create_index(client, index_name, force_recreate=args.force)
    print("Done!")


if __name__ == "__main__":
    main()
