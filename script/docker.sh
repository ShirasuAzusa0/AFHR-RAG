#!/bin/bash

# 运行 Chroma 实例
docker run -d --name chromaAFHR -p 8001:8000 -v ./chroma-data2:/chroma/chroma -e IS_PERSISTENT=TRUE chromadb/chroma:latest

echo "Chroma 实例已启动"
echo "chromaAFHR: http://localhost:8001"

# 等待 Chroma 启动
sleep 5

echo "开始构建知识库..."

python kb_builder.py

echo "知识库构建完成"