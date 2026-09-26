FROM python:3.13-slim

WORKDIR /app

# 装 uv
RUN pip install --no-cache-dir uv

# 先拷依赖文件(利用缓存层)
COPY pyproject.toml uv.lock ./
COPY third_party/ ./third_party/

# 装依赖
RUN uv sync --frozen --no-dev

# 再拷代码
COPY . .

# 私钥通过 compose 卷挂载到 /data/folio-auth/（见 docker-compose.yml），
# 不要构建进镜像；开发容器无密钥时自动降级临时密钥并告警
EXPOSE 8003

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
