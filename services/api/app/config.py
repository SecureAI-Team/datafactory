import os

class Settings:
    postgres_user = os.getenv("POSTGRES_USER")
    postgres_password = os.getenv("POSTGRES_PASSWORD")
    postgres_host = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db = os.getenv("POSTGRES_DB", "adf")

    minio_url = os.getenv("MINIO_URL")
    minio_user = os.getenv("MINIO_ROOT_USER")
    minio_pass = os.getenv("MINIO_ROOT_PASSWORD")

    os_host = os.getenv("OPENSEARCH_HOST", "opensearch")
    os_port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    os_index = os.getenv("OPENSEARCH_INDEX", "knowledge_units")

    jwt_secret = os.getenv("JWT_SECRET", "devjwtsecret")
    jwt_algo = os.getenv("JWT_ALGO", "HS256")

    langfuse_host = os.getenv("LANGFUSE_HOST")
    langfuse_api_key = os.getenv("LANGFUSE_API_KEY")
    langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")

    upstream_llm_url = os.getenv("UPSTREAM_LLM_URL")
    upstream_llm_key = os.getenv("UPSTREAM_LLM_API_KEY")
    default_model = os.getenv("DEFAULT_MODEL", "qwen-plus")
    default_scenario = os.getenv("GATEWAY_SCENARIO_DEFAULT", "sales_qa")

    n8n_webhook = os.getenv("N8N_WEBHOOK_URL")

settings = Settings()
