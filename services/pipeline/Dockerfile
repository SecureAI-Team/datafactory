FROM python:3.11-slim
WORKDIR /opt/pipeline
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY pipeline ./pipeline
CMD ["python", "-c", "print('pipeline image ready')"]
