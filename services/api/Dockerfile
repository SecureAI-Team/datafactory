FROM python:3.11-slim
ARG PIP_INDEX_URL=https://mirrors.ustc.edu.cn/pypi/web/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
