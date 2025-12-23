from opensearchpy import OpenSearch
from ..config import settings

os_client = OpenSearch(
    hosts=[{"host": settings.os_host, "port": settings.os_port}],
    http_compress=True,
    use_ssl=False,
    verify_certs=False,
)
