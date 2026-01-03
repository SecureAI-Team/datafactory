FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.ustc.edu.cn/pypi/web/simple

# Copy application code
COPY . .

# Run the service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]

