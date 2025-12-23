FROM python:3.11-slim
ARG PIP_INDEX_URL=https://mirrors.ustc.edu.cn/pypi/web/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
WORKDIR /opt/pipeline
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY pipeline ./pipeline
CMD ["python", "-c", "print('pipeline image ready')"]
