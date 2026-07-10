.PHONY: all install build-server build-client build-ca build-all clean

PYTHON := python3
PIP := pip3
PYINSTALLER := pyinstaller

all: clean install build-all

install:
	@echo "📦 Установка зависимостей..."
	$(PIP) install -r requirements.txt

build-server:
	@echo "🔨 Сборка сервера..."
	$(PYINSTALLER) --onefile --name d3_server server.py

build-client:
	@echo "🔨 Сборка клиента..."
	$(PYINSTALLER) --onefile --name d3_client client.py

build-ca:
	@echo "🔨 Сборка CA..."
	$(PYINSTALLER) --onefile --name d3_ca d3_ca.py

build-all: build-server build-client build-ca
	@echo "✅ Все бинарники собраны в dist/"

clean:
	@echo "🧹 Очистка..."
	rm -rf build/ dist/ *.spec
	rm -rf __pycache__ */__pycache__

run-server:
	$(PYTHON) server.py

run-client:
	$(PYTHON) client.py --name client1 --socks-port 1080

help:
	@echo "Доступные команды:"
	@echo "  make install        - Установка зависимостей"
	@echo "  make build-all      - Сборка всех бинарников"
	@echo "  make build-server   - Сборка сервера"
	@echo "  make build-client   - Сборка клиента"
	@echo "  make build-ca       - Сборка CA"
	@echo "  make clean          - Очистка"
	@echo "  make run-server     - Запуск сервера"
	@echo "  make run-client     - Запуск клиента"
