from langfuse import Langfuse
from ..config import settings

langfuse = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_api_key,
    host=settings.langfuse_host,
)
