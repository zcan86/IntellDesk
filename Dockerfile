# IntelliDesk Backend + Static Docker Image
# 单容器部署：FastAPI 同时提供 API 和静态文件

FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p data/uploads data/chroma_db logs

# 暴露端口
EXPOSE 8000

# 启动服务
CMD ["python", "main.py"]
