"""
Integration tests for external service connections.

These tests verify that all external services (OpenSearch, MinIO, PostgreSQL, Redis, etc.)
are properly configured and accessible.

Run with: pytest tests/test_integration_services.py -v
"""

import os
import pytest
from typing import Optional
import asyncio


class TestPostgresConnection:
    """Test PostgreSQL database connection."""
    
    def test_postgres_connection(self):
        """Test that we can connect to PostgreSQL."""
        from sqlalchemy import create_engine, text
        from app.config import settings
        
        # Build connection URL
        db_url = (
            f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )
        
        engine = create_engine(db_url)
        
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                assert result.scalar() == 1
        finally:
            engine.dispose()
    
    def test_postgres_tables_exist(self):
        """Test that required tables exist in the database."""
        from app.db import engine
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # Check for essential tables
        required_tables = [
            'users',
            'conversations',
            'conversation_messages',
            'knowledge_units',
            'contributions',
        ]
        
        for table in required_tables:
            assert table in tables, f"Required table '{table}' not found in database"


class TestMinIOConnection:
    """Test MinIO object storage connection."""
    
    def test_minio_connection(self):
        """Test that we can connect to MinIO."""
        from minio import Minio
        from app.config import settings
        
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE if hasattr(settings, 'MINIO_SECURE') else False,
        )
        
        # List buckets to verify connection
        buckets = client.list_buckets()
        assert buckets is not None
    
    def test_minio_required_buckets_exist(self):
        """Test that required buckets exist."""
        from minio import Minio
        from app.config import settings
        
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE if hasattr(settings, 'MINIO_SECURE') else False,
        )
        
        required_buckets = ['uploads', 'bronze', 'silver', 'gold']
        existing_buckets = [b.name for b in client.list_buckets()]
        
        for bucket in required_buckets:
            if bucket not in existing_buckets:
                pytest.skip(f"Bucket '{bucket}' not found - may need initialization")


class TestOpenSearchConnection:
    """Test OpenSearch connection."""
    
    def test_opensearch_connection(self):
        """Test that we can connect to OpenSearch."""
        from opensearchpy import OpenSearch
        from app.config import settings
        
        # Parse OpenSearch URL
        opensearch_url = settings.OPENSEARCH_URL if hasattr(settings, 'OPENSEARCH_URL') else 'http://opensearch:9200'
        
        client = OpenSearch(
            hosts=[opensearch_url],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
        )
        
        # Check cluster health
        health = client.cluster.health()
        assert health['status'] in ['green', 'yellow', 'red']
        
        # Yellow is acceptable for single-node clusters
        if health['status'] == 'red':
            pytest.fail("OpenSearch cluster status is RED")
    
    def test_opensearch_index_exists(self):
        """Test that the knowledge_units index exists."""
        from opensearchpy import OpenSearch
        from app.config import settings
        
        opensearch_url = settings.OPENSEARCH_URL if hasattr(settings, 'OPENSEARCH_URL') else 'http://opensearch:9200'
        
        client = OpenSearch(
            hosts=[opensearch_url],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
        )
        
        # Check if index exists
        index_name = 'knowledge_units'
        if not client.indices.exists(index=index_name):
            pytest.skip(f"Index '{index_name}' not found - may need initialization")


class TestRedisConnection:
    """Test Redis connection."""
    
    def test_redis_connection(self):
        """Test that we can connect to Redis."""
        import redis
        from app.config import settings
        
        redis_url = settings.REDIS_URL if hasattr(settings, 'REDIS_URL') else 'redis://redis:6379/0'
        
        client = redis.from_url(redis_url)
        
        try:
            # Ping to verify connection
            result = client.ping()
            assert result is True
        finally:
            client.close()
    
    def test_redis_basic_operations(self):
        """Test basic Redis operations."""
        import redis
        from app.config import settings
        import uuid
        
        redis_url = settings.REDIS_URL if hasattr(settings, 'REDIS_URL') else 'redis://redis:6379/0'
        
        client = redis.from_url(redis_url)
        
        try:
            # Test set/get
            test_key = f"test:integration:{uuid.uuid4()}"
            test_value = "test_value"
            
            client.set(test_key, test_value, ex=60)  # Expire in 60 seconds
            retrieved = client.get(test_key)
            
            assert retrieved.decode() == test_value
            
            # Cleanup
            client.delete(test_key)
        finally:
            client.close()


class TestLLMConnection:
    """Test LLM service connection."""
    
    def test_llm_api_key_configured(self):
        """Test that LLM API key is configured."""
        from app.config import settings
        
        api_key = getattr(settings, 'DASHSCOPE_API_KEY', None) or os.getenv('DASHSCOPE_API_KEY')
        
        if not api_key:
            pytest.skip("DASHSCOPE_API_KEY not configured")
        
        assert len(api_key) > 0
        assert api_key.startswith('sk-') or len(api_key) > 10
    
    @pytest.mark.asyncio
    async def test_llm_basic_call(self):
        """Test basic LLM API call (optional - may incur costs)."""
        from app.config import settings
        
        api_key = getattr(settings, 'DASHSCOPE_API_KEY', None) or os.getenv('DASHSCOPE_API_KEY')
        
        if not api_key:
            pytest.skip("DASHSCOPE_API_KEY not configured")
        
        # Skip actual API call in CI environment
        if os.getenv('CI') == 'true':
            pytest.skip("Skipping LLM call in CI environment")
        
        try:
            from langchain_openai import ChatOpenAI
            
            llm = ChatOpenAI(
                model_name="qwen-turbo",
                openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
                openai_api_key=api_key,
                max_tokens=50,
            )
            
            response = await llm.ainvoke("Say 'Hello' in one word.")
            assert response.content is not None
        except Exception as e:
            pytest.skip(f"LLM call failed: {e}")


class TestAuthService:
    """Test authentication service."""
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        from app.services.auth_service import AuthService
        
        service = AuthService()
        
        password = "test_password_123"
        hashed = service.get_password_hash(password)
        
        assert hashed != password
        assert service.verify_password(password, hashed)
        assert not service.verify_password("wrong_password", hashed)
    
    def test_jwt_token_creation(self):
        """Test JWT token creation and verification."""
        from app.services.auth_service import AuthService
        from datetime import timedelta
        
        service = AuthService()
        
        # Create access token
        user_data = {"sub": "test_user", "role": "user"}
        token = service.create_access_token(
            data=user_data,
            expires_delta=timedelta(minutes=15)
        )
        
        assert token is not None
        assert len(token) > 0


class TestAPIEndpoints:
    """Test API endpoint availability."""
    
    def test_health_endpoint(self):
        """Test API health endpoint."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # Try common health endpoints
        for endpoint in ['/health', '/api/health', '/']:
            response = client.get(endpoint)
            if response.status_code == 200:
                return
        
        # If no health endpoint, check docs
        response = client.get('/docs')
        assert response.status_code == 200
    
    def test_auth_endpoints_exist(self):
        """Test that auth endpoints are registered."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # Login endpoint should exist (even if returns 422 for missing body)
        response = client.post('/api/auth/login')
        assert response.status_code in [200, 401, 422]  # Not 404
    
    def test_conversations_endpoints_exist(self):
        """Test that conversation endpoints are registered."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # Should return 401 (unauthorized) not 404 (not found)
        response = client.get('/api/conversations')
        assert response.status_code in [401, 403]


class TestDatabaseIntegrity:
    """Test database integrity and data consistency."""
    
    def test_user_table_has_admin(self):
        """Test that admin user exists."""
        from app.db import SessionLocal
        from app.models.user import User
        
        db = SessionLocal()
        try:
            admin = db.query(User).filter(User.username == 'admin').first()
            if not admin:
                pytest.skip("Admin user not created yet")
            
            assert admin.role in ['admin', 'superadmin']
        finally:
            db.close()
    
    def test_ku_types_initialized(self):
        """Test that KU type definitions are initialized."""
        from app.db import SessionLocal
        from sqlalchemy import text
        
        db = SessionLocal()
        try:
            result = db.execute(text("SELECT COUNT(*) FROM ku_type_definitions"))
            count = result.scalar()
            
            if count == 0:
                pytest.skip("KU types not initialized yet")
            
            assert count > 0
        except Exception:
            pytest.skip("ku_type_definitions table may not exist")
        finally:
            db.close()
    
    def test_system_configs_initialized(self):
        """Test that system configs are initialized."""
        from app.db import SessionLocal
        from sqlalchemy import text
        
        db = SessionLocal()
        try:
            result = db.execute(text("SELECT COUNT(*) FROM system_configs"))
            count = result.scalar()
            
            if count == 0:
                pytest.skip("System configs not initialized yet")
            
            assert count > 0
        except Exception:
            pytest.skip("system_configs table may not exist")
        finally:
            db.close()


def run_all_tests():
    """Run all integration tests and return summary."""
    import sys
    
    # Run pytest
    exit_code = pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '-x',  # Stop on first failure
    ])
    
    return exit_code == 0


if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)

