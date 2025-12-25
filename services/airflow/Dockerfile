FROM apache/airflow:2.9.2
ARG PIP_INDEX_URL=https://mirrors.ustc.edu.cn/pypi/web/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV PIP_ROOT_USER_ACTION=ignore
USER root
RUN python -m pip install --root-user-action=ignore --no-cache-dir minio opensearch-py httpx openai
USER airflow
