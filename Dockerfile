# 后端镜像：FastAPI + uvicorn
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 先装依赖（利用 Docker 层缓存，代码变更不触发重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码（app/prompts 提示词随镜像一起打入）
COPY app ./app
COPY scripts ./scripts

EXPOSE 8000

# workers 数由环境变量控制，小内存服务器可设为 1
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]
