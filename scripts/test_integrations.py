#!/usr/bin/env python3
"""
Integration Service Connection Tester

This script tests connections to all external services and reports their status.
Run from the API service container or with appropriate environment variables set.

Usage:
    python scripts/test_integrations.py
    
Or from docker:
    docker compose exec api python /app/scripts/test_integrations.py
"""

import os
import sys
import time
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class Status(Enum):
    OK = "✅ OK"
    WARN = "⚠️ WARN"
    FAIL = "❌ FAIL"
    SKIP = "⏭️ SKIP"


@dataclass
class TestResult:
    service: str
    status: Status
    message: str
    latency_ms: Optional[float] = None


def test_postgres() -> TestResult:
    """Test PostgreSQL connection."""
    start = time.time()
    
    try:
        from sqlalchemy import create_engine, text
        
        host = os.getenv('POSTGRES_HOST', 'postgres')
        port = os.getenv('POSTGRES_PORT', '5432')
        user = os.getenv('POSTGRES_USER', 'adf_user')
        password = os.getenv('POSTGRES_PASSWORD', 'adf_pass')
        db = os.getenv('POSTGRES_DB', 'adf_db')
        
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
        engine = create_engine(db_url, connect_args={'connect_timeout': 5})
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
        
        latency = (time.time() - start) * 1000
        engine.dispose()
        
        return TestResult(
            service="PostgreSQL",
            status=Status.OK,
            message=f"Connected to {db}@{host}:{port}",
            latency_ms=latency
        )
    except Exception as e:
        return TestResult(
            service="PostgreSQL",
            status=Status.FAIL,
            message=str(e)
        )


def test_minio() -> TestResult:
    """Test MinIO connection."""
    start = time.time()
    
    try:
        from minio import Minio
        
        endpoint = os.getenv('MINIO_ENDPOINT', 'minio:9000')
        access_key = os.getenv('MINIO_ACCESS_KEY', 'minio')
        secret_key = os.getenv('MINIO_SECRET_KEY', 'minio123')
        secure = os.getenv('MINIO_SECURE', 'false').lower() == 'true'
        
        client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        
        buckets = client.list_buckets()
        bucket_names = [b.name for b in buckets]
        
        latency = (time.time() - start) * 1000
        
        # Check required buckets
        required = ['uploads', 'bronze', 'silver', 'gold']
        missing = [b for b in required if b not in bucket_names]
        
        if missing:
            return TestResult(
                service="MinIO",
                status=Status.WARN,
                message=f"Connected but missing buckets: {missing}",
                latency_ms=latency
            )
        
        return TestResult(
            service="MinIO",
            status=Status.OK,
            message=f"Connected, {len(buckets)} buckets available",
            latency_ms=latency
        )
    except Exception as e:
        return TestResult(
            service="MinIO",
            status=Status.FAIL,
            message=str(e)
        )


def test_opensearch() -> TestResult:
    """Test OpenSearch connection."""
    start = time.time()
    
    try:
        from opensearchpy import OpenSearch
        
        url = os.getenv('OPENSEARCH_URL', 'http://opensearch:9200')
        
        client = OpenSearch(
            hosts=[url],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            timeout=5,
        )
        
        health = client.cluster.health()
        cluster_status = health['status']
        cluster_name = health['cluster_name']
        
        latency = (time.time() - start) * 1000
        
        if cluster_status == 'red':
            return TestResult(
                service="OpenSearch",
                status=Status.FAIL,
                message=f"Cluster {cluster_name} status is RED",
                latency_ms=latency
            )
        elif cluster_status == 'yellow':
            return TestResult(
                service="OpenSearch",
                status=Status.WARN,
                message=f"Cluster {cluster_name} status is YELLOW (single node?)",
                latency_ms=latency
            )
        
        return TestResult(
            service="OpenSearch",
            status=Status.OK,
            message=f"Cluster {cluster_name} is GREEN",
            latency_ms=latency
        )
    except Exception as e:
        return TestResult(
            service="OpenSearch",
            status=Status.FAIL,
            message=str(e)
        )


def test_redis() -> TestResult:
    """Test Redis connection."""
    start = time.time()
    
    try:
        import redis
        
        url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
        
        client = redis.from_url(url, socket_connect_timeout=5)
        
        # Ping
        if not client.ping():
            return TestResult(
                service="Redis",
                status=Status.FAIL,
                message="Ping failed"
            )
        
        # Get info
        info = client.info()
        version = info.get('redis_version', 'unknown')
        
        latency = (time.time() - start) * 1000
        client.close()
        
        return TestResult(
            service="Redis",
            status=Status.OK,
            message=f"Redis v{version}",
            latency_ms=latency
        )
    except Exception as e:
        return TestResult(
            service="Redis",
            status=Status.FAIL,
            message=str(e)
        )


def test_neo4j() -> TestResult:
    """Test Neo4j connection (optional)."""
    start = time.time()
    
    uri = os.getenv('NEO4J_URI', '')
    if not uri:
        return TestResult(
            service="Neo4j",
            status=Status.SKIP,
            message="NEO4J_URI not configured"
        )
    
    try:
        from neo4j import GraphDatabase
        
        user = os.getenv('NEO4J_USER', 'neo4j')
        password = os.getenv('NEO4J_PASSWORD', 'password')
        
        driver = GraphDatabase.driver(uri, auth=(user, password))
        
        with driver.session() as session:
            result = session.run("RETURN 1 AS n")
            value = result.single()["n"]
        
        driver.close()
        latency = (time.time() - start) * 1000
        
        return TestResult(
            service="Neo4j",
            status=Status.OK,
            message=f"Connected to {uri}",
            latency_ms=latency
        )
    except ImportError:
        return TestResult(
            service="Neo4j",
            status=Status.SKIP,
            message="neo4j driver not installed"
        )
    except Exception as e:
        return TestResult(
            service="Neo4j",
            status=Status.FAIL,
            message=str(e)
        )


def test_langfuse() -> TestResult:
    """Test Langfuse connection (optional)."""
    start = time.time()
    
    host = os.getenv('LANGFUSE_HOST', '')
    if not host:
        return TestResult(
            service="Langfuse",
            status=Status.SKIP,
            message="LANGFUSE_HOST not configured"
        )
    
    try:
        import requests
        
        # Try health endpoint
        response = requests.get(f"{host}/api/public/health", timeout=5)
        
        latency = (time.time() - start) * 1000
        
        if response.status_code == 200:
            return TestResult(
                service="Langfuse",
                status=Status.OK,
                message=f"Connected to {host}",
                latency_ms=latency
            )
        else:
            return TestResult(
                service="Langfuse",
                status=Status.WARN,
                message=f"Status {response.status_code}",
                latency_ms=latency
            )
    except Exception as e:
        return TestResult(
            service="Langfuse",
            status=Status.FAIL,
            message=str(e)
        )


def test_llm_api() -> TestResult:
    """Test LLM API key configuration."""
    api_key = os.getenv('DASHSCOPE_API_KEY', '')
    
    if not api_key:
        return TestResult(
            service="LLM (Qwen)",
            status=Status.WARN,
            message="DASHSCOPE_API_KEY not configured"
        )
    
    if len(api_key) < 10:
        return TestResult(
            service="LLM (Qwen)",
            status=Status.FAIL,
            message="API key appears invalid (too short)"
        )
    
    # Just check if key is present, don't make actual API call
    masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    
    return TestResult(
        service="LLM (Qwen)",
        status=Status.OK,
        message=f"API key configured: {masked}"
    )


def print_results(results: List[TestResult]):
    """Print test results in a formatted table."""
    print("\n" + "=" * 70)
    print("🔧 Integration Service Connection Test Results")
    print("=" * 70)
    
    # Calculate column widths
    max_service = max(len(r.service) for r in results)
    max_status = max(len(r.status.value) for r in results)
    
    for result in results:
        latency_str = f"({result.latency_ms:.1f}ms)" if result.latency_ms else ""
        print(f"  {result.service:<{max_service}}  {result.status.value:<{max_status}}  {result.message} {latency_str}")
    
    print("=" * 70)
    
    # Summary
    ok_count = sum(1 for r in results if r.status == Status.OK)
    warn_count = sum(1 for r in results if r.status == Status.WARN)
    fail_count = sum(1 for r in results if r.status == Status.FAIL)
    skip_count = sum(1 for r in results if r.status == Status.SKIP)
    
    print(f"\n📊 Summary: {ok_count} OK, {warn_count} Warnings, {fail_count} Failed, {skip_count} Skipped")
    
    if fail_count > 0:
        print("\n❌ Some critical services are not available!")
        return False
    elif warn_count > 0:
        print("\n⚠️ Some services have warnings, but system should work.")
        return True
    else:
        print("\n✅ All services are healthy!")
        return True


def main():
    """Run all integration tests."""
    print("🚀 Starting integration service tests...")
    
    results = []
    
    # Run all tests
    tests = [
        test_postgres,
        test_minio,
        test_opensearch,
        test_redis,
        test_neo4j,
        test_langfuse,
        test_llm_api,
    ]
    
    for test_func in tests:
        print(f"  Testing {test_func.__doc__.strip()}...", end="", flush=True)
        result = test_func()
        results.append(result)
        print(f" {result.status.value}")
    
    # Print formatted results
    success = print_results(results)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

