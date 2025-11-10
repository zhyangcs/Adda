#!/bin/bash
# 使用Docker运行带有pgml的PostgreSQL

echo "🐳 启动带有pgml的PostgreSQL Docker容器..."

# 检查Docker是否可用
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未找到，请先安装Docker"
    exit 1
fi

# 停止可能存在的旧容器
docker stop pgml-postgres 2>/dev/null || true
docker rm pgml-postgres 2>/dev/null || true

# 启动新的pgml容器
docker run -d \
    --name pgml-postgres \
    -e POSTGRES_USER=myuser \
    -e POSTGRES_PASSWORD=mypass \
    -e POSTGRES_DB=mydb \
    -p 5432:5432 \
    ghcr.io/postgresml/postgresml:latest

echo "✅ pgml PostgreSQL容器已启动"
echo "📊 等待数据库初始化..."
sleep 10

echo "🔧 在pgml中安装扩展..."
docker exec -it pgml-postgres psql -U myuser -d mydb -c "CREATE EXTENSION pgml;"

echo "✅ pgml扩展安装完成！"
echo "📊 现在可以使用pgml进行特征工程了"
echo "🔗 连接信息: localhost:5432, 用户: myuser, 数据库: mydb"