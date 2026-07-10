#!/bin/bash
set -e

echo "🔨 D3 VPN Builder"
echo "================================"

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден!"
    exit 1
fi

# Установка зависимостей
echo "📦 Установка зависимостей..."
pip3 install -r requirements.txt
pip3 install pyinstaller

# Очистка
echo "🧹 Очистка..."
rm -rf build/ dist/ *.spec

# Сборка
echo "🔨 Сборка сервера..."
pyinstaller --onefile --name d3_server server.py

echo "🔨 Сборка клиента..."
pyinstaller --onefile --name d3_client client.py

echo "🔨 Сборка CA..."
pyinstaller --onefile --name d3_ca d3_ca.py

echo "✅ Бинарники в dist/"
ls -lh dist/
