# 使用官方轻量级 Python 镜像作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 将 requirements.txt 文件复制到镜像中
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 将项目文件复制到工作目录中
COPY . .

# 指定 Flask 应用的入口文件
ENV FLASK_APP=app.py

# 设置 Flask 环境为生产模式
ENV FLASK_ENV=production

# 暴露 Flask 默认运行的端口
EXPOSE 5000

# 运行 Flask 应用
CMD ["flask", "run", "--host=0.0.0.0"]
