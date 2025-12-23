FROM apache/airflow:2.9.2
ARG PIP_INDEX_URL=https://mirrors.ustc.edu.cn/pypi/web/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
USER airflow
RUN pip install --user minio opensearch-py httpx
