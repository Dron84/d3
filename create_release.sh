#!/bin/bash
set -e

echo "📦 Создание релизного архива D3 VPN v7.0.0"

PROJECT_DIR="d3_vpn_full"
rm -rf $PROJECT_DIR
mkdir -p $PROJECT_DIR

# Копирование всех файлов
cp server.py $PROJECT_DIR/
cp client.py $PROJECT_DIR/
cp d3_ca.py $PROJECT_DIR/
cp requirements.txt $PROJECT_DIR/
cp Makefile $PROJECT_DIR/
cp build.sh $PROJECT_DIR/
cp .env.server.example $PROJECT_DIR/
cp .env.client.example $PROJECT_DIR/
cp README.md $PROJECT_DIR/

# Создание папок
mkdir -p $PROJECT_DIR/docker
mkdir -p $PROJECT_DIR/scripts
mkdir -p $PROJECT_DIR/certs

# Docker
cat > $PROJECT_DIR/docker/Dockerfile << 'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY server.py client.py d3_ca.py ./
CMD ["python3", "server.py"]
EXPOSE 6666 1080
EOF

cat > $PROJECT_DIR/docker/docker-compose.yml << 'EOF'
version: '3.8'
services:
  d3-vpn:
    build: .
    ports:
      - "6666:6666"
      - "1080:1080"
    environment:
      - SERVER_HOST=0.0.0.0
      - ALLOW_INTERNET=true
    cap_add:
      - NET_ADMIN
      - NET_RAW
    restart: unless-stopped
EOF

# Скрипты сборки
cat > $PROJECT_DIR/scripts/build_linux.sh << 'EOF'
#!/bin/bash
echo "🐧 Сборка для Linux..."
pyinstaller --onefile --name d3_server server.py
pyinstaller --onefile --name d3_client client.py
pyinstaller --onefile --name d3_ca d3_ca.py
EOF
chmod +x $PROJECT_DIR/scripts/build_linux.sh

# Упаковка
tar -czf ${PROJECT_DIR}.tar.gz ${PROJECT_DIR}/
zip -r ${PROJECT_DIR}.zip ${PROJECT_DIR}/ > /dev/null 2>&1

echo "✅ Архив создан: ${PROJECT_DIR}.tar.gz и ${PROJECT_DIR}.zip"
ls -lh ${PROJECT_DIR}.*
