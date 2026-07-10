#!/bin/bash
echo "🐧 Сборка для Linux..."
pyinstaller --onefile --name d3_server server.py
pyinstaller --onefile --name d3_client client.py
pyinstaller --onefile --name d3_ca d3_ca.py
