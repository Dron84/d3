

# 🚀 D3 Stealth VPN v1.0.0

**Поддерживаемые платформы:** Linux, Windows, macOS, Android

**D3** — это высокозащищённый VPN-протокол с маскировкой трафика, поддержкой сертификатов, SOCKS5 прокси, каскадным подключением и балансировкой нагрузки.  
D3 = Direct, Dynamic, Discreet  
*(Прямой, Динамичный, Незаметный)*

---

## 📋 Оглавление

1. [Быстрый старт](#-быстрый-старт)
2. [Как это работает](#-как-это-работает)
3. [Настройка сервера](#-настройка-сервера)
4. [Настройка клиента](#-настройка-клиента)
5. [Настройка туннеля (TUNNEL_MODE)](#-настройка-туннеля-tunnel_mode)
6. [Настройка DNS-туннеля](#-настройка-dns-туннеля)
7. [Как правильно и как неправильно](#-как-правильно-и-как-неправильно)
8. [Сборка бинарников](#-сборка-бинарников)
9. [Запуск сервера](#-запуск-сервера)
10. [Запуск клиента](#-запуск-клиента)
11. [Настройка SOCKS5](#-настройка-socks5)
12. [Каскадное подключение](#-каскадное-подключение)
13. [Балансировка нагрузки](#-балансировка-нагрузки)
14. [Управление сертификатами](#-управление-сертификатами)
15. [Android (Termux)](#-android-termux)
16. [Устранение неполадок](#-устранение-неполадок)

---

## ⚡ Быстрый старт

```powershell
# ============================================
# 1. СОЗДАНИЕ ВИРТУАЛЬНОГО ОКРУЖЕНИЯ
# ============================================

# Windows
py -m venv .venv

# Linux/macOS
python3 -m venv .venv

# ============================================
# 2. АКТИВАЦИЯ ВИРТУАЛЬНОГО ОКРУЖЕНИЯ
# ============================================

# Windows (PowerShell/CMD)
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# ✅ После активации в начале строки появится (.venv)
# (.venv) PS C:\projects\d3>

# ❌ Если (.venv) НЕ появился → активация НЕ сработала!
#    Попробуй: .venv\Scripts\activate.bat (Windows)
#    Или: source .venv/bin/activate (Linux)

# ============================================
# 3. ВЫХОД ИЗ ВИРТУАЛЬНОГО ОКРУЖЕНИЯ
# ============================================

deactivate

# ✅ (.venv) исчезнет из строки
# PS C:\projects\d3>

# ❌ Если (.venv) НЕ исчез → попробуй: exit (закрыть терминал)

# ============================================
# 4. УСТАНОВКА ЗАВИСИМОСТЕЙ (ВНУТРИ .venv!)
# ============================================

# ✅ ПРАВИЛЬНО (сначала активировал .venv, потом установил)
.venv\Scripts\activate
pip install -r requirements.txt

# ❌ НЕПРАВИЛЬНО (устанавливаешь глобально, без активации)
pip install -r requirements.txt

# ============================================
# 5. ПРОВЕРКА, ЧТО ВСЁ РАБОТАЕТ
# ============================================

# ✅ Проверка Python
python --version
# Python 3.14.6

# ✅ Проверка pip
pip --version
# pip 26.1.2 from ...\.venv\Lib\site-packages\pip

# ❌ Если путь к pip НЕ содержит .venv → ты НЕ внутри!
#    Нужно: .venv\Scripts\activate
```

---

## 🧠 Как это работает

### Общая архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         D3 VPN                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  КЛИЕНТ                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  1. Приложение (браузер/Telegram) отправляет запрос     │    │
│  │  2. SOCKS5 прокси (127.0.0.1:1080) перехватывает        │    │
│  │  3. D3 Клиент шифрует данные ChaCha20                   │    │
│  │  4. Маскирует под HTTP/HTTPS/Traffic                    │    │
│  │  5. Отправляет через туннель (ICMP/DNS/RAW)             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ТУННЕЛЬ (ICMP / DNS / RAW)                             │    │
│  │  - Данные передаются внутри выбранного протокола        │    │
│  │  - DPI не может определить, что это VPN                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  СЕРВЕР                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  1. Принимает трафик через туннель                      │    │
│  │  2. Снимает маскировку                                  │    │
│  │  3. Расшифровывает ChaCha20                             │    │
│  │  4. Маршрутизирует запрос                               │    │
│  │  5. Отправляет в интернет (NAT)                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ИНТЕРНЕТ                                               │    │
│  │  - Сервер подставляет свой IP                           │    │
│  │  - Ответ возвращается клиенту                           │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Как проходит пакет (пошагово)

```
1. Клиент: Приложение (браузер) хочет загрузить google.com
   └── SOCKS5 прокси (127.0.0.1:1080)

2. Клиент: D3 шифрует запрос ChaCha20
   └── plaintext: "GET / HTTP/1.1 Host: google.com"
   └── encrypted: (бинарные данные)

3. Клиент: Добавляет маскировку (если включена)
   └── HTTP маскировка: "HTTP/1.1 200 OK... {encrypted}"

4. Клиент: Отправляет через туннель
   └── TUNNEL_MODE=icmp → пакет внутри ping
   └── TUNNEL_MODE=dns → пакет внутри DNS запроса
   └── TUNNEL_MODE=raw → пакет как UDP датаграмма

5. Сервер: Принимает пакет
   └── Распаковывает из туннеля
   └── Снимает маскировку
   └── Расшифровывает ChaCha20

6. Сервер: Маршрутизирует
   └── Если запрос к google.com → NAT в интернет
   └── Если запрос к другому клиенту → пересылает

7. Сервер: Получает ответ от google.com
   └── Шифрует ChaCha20
   └── Маскирует
   └── Отправляет обратно клиенту
```

---

## 🖥️ Настройка сервера

### Шаг 1: Подготовка окружения

```bash
# 1. Создай папку для сервера
mkdir d3_server
cd d3_server

# 2. Создай виртуальное окружение
python -m venv .venv

# 3. Активируй его
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 4. Установи зависимости
pip install -r requirements.txt
```

### Шаг 2: Создай файл `.env.server`

```bash
# Создай файл .env.server в папке с сервером
nano .env.server
```

```bash
# ============================================
# D3 VPN SERVER CONFIGURATION
# ============================================

# === ОСНОВНЫЕ ПАРАМЕТРЫ ===
# SERVER_HOST - на каком IP слушать
#   - 0.0.0.0  → слушать на всех интерфейсах (рекомендуется)
#   - 127.0.0.1 → только локальный доступ (для тестов)
#   - 192.168.1.100 → конкретный IP
SERVER_HOST=0.0.0.0

# SERVER_PORT - порт для подключения клиентов
#   - 6666 - порт по умолчанию
#   - Можно использовать любой свободный порт
SERVER_PORT=6666

# VPN_SUBNET - подсеть для клиентов
#   - Клиенты получают IP из этой подсети
#   - Сервер получает .1 адрес
VPN_SUBNET=10.0.0.0/24

# ALLOW_INTERNET - разрешить клиентам выход в интернет
#   - true  → клиенты могут ходить в интернет через сервер (NAT)
#   - false → клиенты могут общаться только внутри VPN
ALLOW_INTERNET=true

# === МАСКИРОВКА ===
# MASK_MODE - как маскировать трафик
#   - http    → пакеты выглядят как HTTP ответы
#   - https   → пакеты выглядят как TLS трафик
#   - traffic → пакеты выглядят как YouTube/Google трафик
MASK_MODE=https

# === ТУННЕЛИРОВАНИЕ ===
# TUNNEL_MODE - как передавать данные
#   - icmp   → через ICMP (ping) пакеты
#   - dns    → через DNS запросы
#   - raw    → прямая UDP передача (самый быстрый)
TUNNEL_MODE=icmp

# === DNS ТУННЕЛЬ (нужен только для TUNNEL_MODE=dns) ===
# DNS_DOMAIN - твой домен, который ведёт на сервер
#   - Пример: vpn.example.com
#   - Домен должен иметь A-запись, указывающую на IP сервера
DNS_DOMAIN=vpn.example.com

# === СЕРТИФИКАТЫ ===
CA_DIR=certs/ca
AUTO_RENEW_THRESHOLD=7
KEY_ROTATION_INTERVAL=60

# === КАСКАДНОЕ ПОДКЛЮЧЕНИЕ ===
# CASCADE_MODE - включать ли каскад
#   - true  → сервер подключается к другому серверу
#   - false → сервер работает самостоятельно
CASCADE_MODE=false

# SERVER_LEVEL - уровень сервера в каскаде
#   - 0 → основной сервер (выход в интернет)
#   - 1 → промежуточный
#   - 2+ → входные серверы
SERVER_LEVEL=0

# UPSTREAM_SERVER - к какому серверу подключаться (для каскада)
UPSTREAM_SERVER=192.168.1.100:6666

# === БАЛАНСИРОВКА ===
BALANCE_ENABLED=false
BALANCE_STRATEGY=adaptive
BALANCE_SERVERS=server1,192.168.1.101,6666,russia;server2,10.0.0.102,6666,netherlands
BALANCE_API_PORT=8080
SERVER_LOCATION=russia
```

### Шаг 3: Инициализация сертификатов

```bash
# Создаём корневой сертификат CA
python d3_ca.py init

# Выпускаем сертификат для клиента
python d3_ca.py issue client1 --days 365

# Проверяем, что сертификат создан
python d3_ca.py list
# ✅ client1: Активен (365 дней)
```

### Шаг 4: Запуск сервера

```bash
# Запуск с файлом конфигурации
python server.py

# Запуск в фоне (Linux)
nohup python server.py > d3.log 2>&1 &

# Проверка, что сервер работает
netstat -tlnp | grep 6666
# tcp  0  0 0.0.0.0:6666  0.0.0.0:*  LISTEN  12345/python
```

---

## 💻 Настройка клиента

### Шаг 1: Подготовка окружения

```bash
# 1. Создай папку для клиента
mkdir d3_client
cd d3_client

# 2. Создай виртуальное окружение
python -m venv .venv

# 3. Активируй его
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 4. Установи зависимости
pip install -r requirements.txt
```

### Шаг 2: Получи сертификат от сервера

Сертификаты генерируются на сервере. Скопируй их на клиент:

```bash
# На сервере
# Сертификаты лежат в: certs/clients/client1/
#   ├── client_cert.pem   # Сертификат клиента
#   ├── client_private.pem # Приватный ключ (запаролен)
#   └── ca_cert.pem        # Сертификат CA

# Скопируй папку certs на клиент
scp -r certs/ user@client:/path/to/d3_client/
```

### Шаг 3: Создай файл `.env.client`

```bash
# Создай файл .env.client в папке с клиентом
nano .env.client
```

```bash
# ============================================
# D3 VPN CLIENT CONFIGURATION
# ============================================

# === СЕРВЕР ===
# SERVER_HOST - IP адрес сервера
#   - Можно указать IP: 192.168.1.100
#   - Можно указать домен: vpn.example.com
SERVER_HOST=192.168.1.100

# SERVER_PORT - порт сервера (должен совпадать с сервером)
SERVER_PORT=6666

# === КЛИЕНТ ===
# CLIENT_NAME - имя клиента (должно совпадать с сертификатом)
CLIENT_NAME=client1

# === МАСКИРОВКА ===
# MASK_MODE - как маскировать трафик (должен совпадать с сервером)
#   - http, https, traffic
MASK_MODE=https

# === ТУННЕЛИРОВАНИЕ ===
# TUNNEL_MODE - как передавать данные (должен совпадать с сервером!)
#   - icmp, dns, raw
TUNNEL_MODE=icmp

# === DNS ТУННЕЛЬ (нужен только для TUNNEL_MODE=dns) ===
# DNS_DOMAIN - должен СОВПАДАТЬ с серверным!
DNS_DOMAIN=vpn.example.com

# === SOCKS5 ПРОКСИ ===
# SOCKS_HOST - где запускать прокси
#   - 127.0.0.1 → только для локальных приложений
#   - 0.0.0.0 → для всех устройств в сети
SOCKS_HOST=127.0.0.1

# SOCKS_PORT - порт SOCKS5 прокси
SOCKS_PORT=1080

# SOCKS_ENABLED - включать ли SOCKS5 прокси
SOCKS_ENABLED=true
```

### Шаг 4: Запуск клиента

```bash
# Запуск с параметрами (переопределяют .env)
python client.py --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080

# Запуск с файлом конфигурации
python client.py --config .env.client

# Запуск в фоне (Linux)
nohup python client.py > d3.log 2>&1 &

# Проверка, что SOCKS5 работает
netstat -tlnp | grep 1080
# tcp  0  0 127.0.0.1:1080  0.0.0.0:*  LISTEN  12346/python
```

---

## 🔌 Настройка туннеля (TUNNEL_MODE)

### Что такое TUNNEL_MODE?

**TUNNEL_MODE** — это способ передачи данных между клиентом и сервером. Можно выбрать **ТОЛЬКО ОДИН** вариант!

```
┌─────────────────────────────────────────────────────────────┐
│  КЛИЕНТ                    ТУННЕЛЬ                СЕРВЕР    │
│  ┌──────────┐           ┌──────────┐           ┌──────────┐ │
│  │  Данные  │ ────────▶ │  ICMP    │ ────────▶ │  Данные  │ │
│  └──────────┘           │  DNS     │           └──────────┘ │
│                         │  RAW     │                        │
│                         └──────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### Доступные режимы

| Режим | Как работает | Когда использовать | Скорость | Скрытность |
|-------|--------------|-------------------|----------|------------|
| **RAW** | Прямая UDP передача | Когда нет блокировок | 🟢 Высокая | 🔴 Низкая |
| **ICMP** | Внутри ping пакетов | Когда блокируют порты | 🟡 Средняя | 🟡 Средняя |
| **DNS** | Внутри DNS запросов | Когда всё блокируют | 🔴 Низкая | 🟢 Высокая |

### Как выбрать TUNNEL_MODE

```bash
# ============================================
# Шаг 1: Начни с RAW (самый быстрый)
# ============================================
TUNNEL_MODE=raw

# Если работает → отлично! 
# Если НЕ работает → переходи к ICMP

# ============================================
# Шаг 2: Попробуй ICMP (обходит блокировку портов)
# ============================================
TUNNEL_MODE=icmp

# Если работает → отлично!
# Если НЕ работает → переходи к DNS

# ============================================
# Шаг 3: Используй DNS (обходит почти всё)
# ============================================
TUNNEL_MODE=dns
DNS_DOMAIN=vpn.example.com  # ← НУЖЕН ДОМЕН!

# Если работает → отлично!
# Если НЕ работает → проверь DNS_DOMAIN
```

### Примеры конфигурации

```bash
# ============================================
# ПРИМЕР 1: Самый быстрый (RAW)
# ============================================
# Используй, если сеть не блокирует UDP
TUNNEL_MODE=raw

# ============================================
# ПРИМЕР 2: Обход блокировки портов (ICMP)
# ============================================
# Используй, если блокируют UDP/TCP порты
TUNNEL_MODE=icmp

# ============================================
# ПРИМЕР 3: Максимальная скрытность (DNS)
# ============================================
# Используй, если блокируют всё, кроме DNS
TUNNEL_MODE=dns
DNS_DOMAIN=vpn.dynv6.net

# ============================================
# ПРИМЕР 4: Комбинация с маскировкой
# ============================================
# Трафик выглядит как HTTPS внутри DNS
TUNNEL_MODE=dns
MASK_MODE=https
DNS_DOMAIN=vpn.dynv6.net
```

### ❌ Что НЕЛЬЗЯ делать

```bash
# ❌ НЕЛЬЗЯ указать несколько туннелей!
TUNNEL_MODE=icmp,dns,raw   # НЕПРАВИЛЬНО!
TUNNEL_MODE=[icmp,dns]     # НЕПРАВИЛЬНО!

# ❌ НЕЛЬЗЯ, чтобы клиент и сервер использовали разные туннели
# Клиент: TUNNEL_MODE=icmp
# Сервер: TUNNEL_MODE=dns   # НЕПРАВИЛЬНО! Они не увидят друг друга!

# ✅ ПРАВИЛЬНО: клиент и сервер используют ОДИН туннель
TUNNEL_MODE=icmp   # И на клиенте, и на сервере
```

---

## 🌐 Настройка DNS-туннеля

### Что такое DNS-туннель?

**DNS-туннель** — это способ передавать данные внутри DNS-запросов. Трафик выглядит как обычные DNS-запросы, но внутри них "спрятаны" ваши данные.

```
Как это выглядит для DPI:
  DNS запрос: "a1b2c3d4.vpn.example.com"
  DPI видит: обычный DNS запрос к vpn.example.com
  На самом деле: внутри "a1b2c3d4" спрятаны ваши данные

Как это выглядит для D3:
  Клиент: "Hello" → HEX: "48656c6c6f" → запрос: "48656c6c6f.vpn.example.com"
  Сервер: принимает → извлекает "48656c6c6f" → "Hello"
```

### Пошаговая настройка DNS-туннеля

#### Шаг 1: Получи домен

Тебе нужен домен, который указывает на IP твоего сервера.

**Варианты:**

| Вариант | Сложность | Стоимость | Пример |
|---------|-----------|-----------|--------|
| Купить домен | 🟡 Средняя | 💰 Есть | `example.com` |
| Бесплатный DynDNS | 🟢 Простая | 🆓 Бесплатно | `vpn.dynv6.net` |
| Локальный DNS | 🔴 Сложная | 🆓 Бесплатно | `vpn.local` |

**Бесплатные DynDNS сервисы:**

```bash
# 1. DynV6 (рекомендую)
# Сайт: https://dynv6.com
# Домен: vpn.dynv6.net

# 2. DuckDNS
# Сайт: https://duckdns.org
# Домен: vpn.duckdns.org

# 3. No-IP
# Сайт: https://noip.com
# Домен: vpn.no-ip.org
```

#### Шаг 2: Настрой DNS-запись

У твоего регистратора домена добавь **A-запись**:

```
Имя: vpn
Тип: A
Значение: 192.168.1.100   # ← IP твоего D3-сервера
TTL: 60
```

**Проверка:**

```bash
# Проверка, что DNS-запись работает
nslookup vpn.example.com
# Server:  8.8.8.8
# Address: 8.8.8.8#53
# Non-authoritative answer:
# Name:    vpn.example.com
# Address: 192.168.1.100  ✅

# Если ответа нет → проверь настройки DNS
```

#### Шаг 3: Настрой сервер

```bash
# .env.server
TUNNEL_MODE=dns
DNS_DOMAIN=vpn.example.com   # ← твой домен
SERVER_HOST=0.0.0.0
SERVER_PORT=6666
```

```bash
# Запуск сервера
python server.py
```

#### Шаг 4: Настрой клиент

```bash
# .env.client
TUNNEL_MODE=dns
DNS_DOMAIN=vpn.example.com   # ← ДОЛЖЕН СОВПАДАТЬ С СЕРВЕРОМ!
SERVER_HOST=192.168.1.100
SERVER_PORT=6666
```

```bash
# Запуск клиента
python client.py
```

#### Шаг 5: Проверка работы

```bash
# На сервере: смотрим DNS-запросы
sudo tcpdump -i any port 53

# На клиенте: тестируем
curl --socks5 127.0.0.1:1080 https://api.ipify.org

# На сервере: видно DNS-запросы вида
# 48656c6c6f.vpn.example.com
```

### ❌ Что НЕЛЬЗЯ делать с DNS-туннелем

```bash
# ❌ НЕЛЬЗЯ использовать DNS-туннель без домена
TUNNEL_MODE=dns
# DNS_DOMAIN не указан → ОШИБКА!

# ❌ НЕЛЬЗЯ, чтобы домен НЕ указывал на сервер
DNS_DOMAIN=google.com   # НЕПРАВИЛЬНО!
# Запросы пойдут в Google, а не в твой сервер

# ❌ НЕЛЬЗЯ использовать разные домены на клиенте и сервере
# Сервер: DNS_DOMAIN=vpn1.example.com
# Клиент: DNS_DOMAIN=vpn2.example.com   # НЕПРАВИЛЬНО!

# ✅ ПРАВИЛЬНО: один и тот же домен на клиенте и сервере
DNS_DOMAIN=vpn.example.com   # И на клиенте, и на сервере
```

---

## ✅ Как правильно и как неправильно

### Правильно (✅)

```bash
# 1. Использовать один TUNNEL_MODE на клиенте и сервере
# Сервер: TUNNEL_MODE=icmp
# Клиент: TUNNEL_MODE=icmp  ✅

# 2. Использовать один DNS_DOMAIN на клиенте и сервере
# Сервер: DNS_DOMAIN=vpn.example.com
# Клиент: DNS_DOMAIN=vpn.example.com  ✅

# 3. Использовать виртуальное окружение
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt  ✅

# 4. Проверять, что сервер запущен
netstat -tlnp | grep 6666  ✅

# 5. Использовать одинаковую маскировку
# Сервер: MASK_MODE=https
# Клиент: MASK_MODE=https  ✅

# 6. Начинать с RAW, потом пробовать другие
TUNNEL_MODE=raw   # сначала
TUNNEL_MODE=icmp  # если raw не работает
TUNNEL_MODE=dns   # если icmp не работает  ✅
```

### Неправильно (❌)

```bash
# 1. Разные TUNNEL_MODE на клиенте и сервере
# Сервер: TUNNEL_MODE=icmp
# Клиент: TUNNEL_MODE=dns  ❌

# 2. Разные DNS_DOMAIN на клиенте и сервере
# Сервер: DNS_DOMAIN=vpn1.example.com
# Клиент: DNS_DOMAIN=vpn2.example.com  ❌

# 3. Установка пакетов без виртуального окружения
pip install -r requirements.txt  ❌

# 4. Запуск клиента без проверки, что сервер работает
python client.py  # сервер не запущен  ❌

# 5. Указание нескольких TUNNEL_MODE
TUNNEL_MODE=icmp,dns,raw  ❌

# 6. Использование DNS-туннеля без домена
TUNNEL_MODE=dns
# DNS_DOMAIN не указан  ❌

# 7. Запуск сервера без инициализации CA
python server.py  # CA не создан  ❌
# Сначала: python d3_ca.py init
```

---

## 📊 Таблица: что должно совпадать

| Параметр | Сервер | Клиент | Должно совпадать? |
|----------|--------|--------|-------------------|
| `TUNNEL_MODE` | icmp | icmp | ✅ ДА! |
| `DNS_DOMAIN` | vpn.example.com | vpn.example.com | ✅ ДА! (для DNS) |
| `MASK_MODE` | https | https | ✅ ДА! |
| `SERVER_PORT` | 6666 | 6666 | ✅ ДА! |
| `SERVER_HOST` | 0.0.0.0 | 192.168.1.100 | ❌ НЕТ (разные) |
| `CLIENT_NAME` | - | client1 | ❌ НЕТ (только клиент) |
| `SOCKS_PORT` | - | 1080 | ❌ НЕТ (только клиент) |

---

## 📦 Сборка бинарников

### Способ 1: Через Makefile (рекомендуется)

```bash
# Установка PyInstaller
pip install pyinstaller

# Сборка всех бинарников
# если нет команды make то нужно его установить 
# если на windows то (choco install make | scoop install make)
make build-all

# Бинарники в папке dist/
ls dist/
# d3_server  d3_client  d3_ca
```

### Способ 2: Через скрипт

```bash
# Запуск скрипта сборки
./build.sh

# Бинарники в папке dist/
```

### Способ 3: Вручную

```bash
# Linux/macOS
pyinstaller --onefile --name d3_server server.py
pyinstaller --onefile --name d3_client client.py
pyinstaller --onefile --name d3_ca d3_ca.py

# Windows (PowerShell)
pyinstaller --onefile --name d3_server.exe server.py
pyinstaller --onefile --name d3_client.exe client.py
pyinstaller --onefile --name d3_ca.exe d3_ca.py
```

### Сборка для разных платформ

```bash
# Linux (запустить на Linux)
pyinstaller --onefile --name d3_server_linux server.py

# Windows (запустить на Windows)
pyinstaller --onefile --name d3_server_windows.exe server.py

# macOS (запустить на macOS)
pyinstaller --onefile --name d3_server_mac server.py

# Кросс-платформенная сборка (через Docker)
docker run --rm -v $(pwd):/app -w /app python:3.11-slim bash -c "
    pip install pyinstaller
    pyinstaller --onefile --name d3_server server.py
    pyinstaller --onefile --name d3_client client.py
    pyinstaller --onefile --name d3_ca d3_ca.py
"
```

### Очистка

```bash
# Удаление временных файлов
make clean

# Или вручную
rm -rf build/ dist/ *.spec
```

---

## 🖥️ Запуск сервера

### Из Python (разработка)

```bash
# 1. Активируй виртуальное окружение
.venv\Scripts\activate

# 2. Запуск сервера
python server.py

# 3. Запуск с конкретным файлом конфигурации
python server.py --config .env.server

# 4. Запуск с отладкой (больше логов)
python server.py --debug
```

### Из бинарника (продакшен)

```bash
# Linux
chmod +x d3_server
./d3_server

# Windows
d3_server.exe

# macOS
chmod +x d3_server_mac
./d3_server_mac
```

### Systemd (Linux)

```bash
# 1. Создай сервис
sudo nano /etc/systemd/system/d3-vpn.service
```

```ini
[Unit]
Description=D3 VPN Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/d3_vpn
ExecStart=/usr/local/bin/d3_server
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# 2. Запуск сервиса
sudo systemctl daemon-reload
sudo systemctl enable d3-vpn
sudo systemctl start d3-vpn
sudo systemctl status d3-vpn

# 3. Просмотр логов
sudo journalctl -u d3-vpn -f
```

### Docker

```bash
cd docker
docker-compose up -d
docker logs d3-vpn-server
docker-compose down
```

### Проверка работы

```bash
# Проверка, что сервер слушает порт
netstat -tlnp | grep 6666

# Проверка через curl
curl --socks5 127.0.0.1:1080 https://api.ipify.org
```

---

## 💻 Запуск клиента

### Из Python (разработка)

```bash
# 1. Активируй виртуальное окружение
.venv\Scripts\activate

# 2. Запуск клиента
python client.py --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080

# 3. Запуск с файлом конфигурации
python client.py --config .env.client

# 4. Запуск с отладкой
python client.py --debug
```

### Из бинарника (продакшен)

```bash
# Linux
chmod +x d3_client
./d3_client --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080

# Windows
d3_client.exe --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080

# macOS
chmod +x d3_client_mac
./d3_client_mac --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080
```

### Systemd (Linux)

```bash
sudo nano /etc/systemd/system/d3-client.service
```

```ini
[Unit]
Description=D3 VPN Client
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/d3_vpn
ExecStart=/root/d3_vpn/d3_client --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable d3-client
sudo systemctl start d3-client
```

### Фоновый режим

```bash
# Linux/macOS
nohup ./d3_client --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080 > d3.log 2>&1 &

# Windows (PowerShell)
Start-Process -NoNewWindow -FilePath "d3_client.exe" -ArgumentList "--name client1 --server 192.168.1.100 --port 6666 --socks-port 1080"
```

### Параметры клиента

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `--server` | IP сервера | 127.0.0.1 |
| `--port` | Порт сервера | 6666 |
| `--name` | Имя клиента | client1 |
| `--socks-port` | Порт SOCKS5 | 1080 |
| `--no-socks` | Отключить SOCKS5 | false |
| `--mask` | Режим маскировки | https |
| `--tunnel` | Режим туннеля | icmp |

---

## 🌐 Настройка SOCKS5

### Браузеры

**Firefox:**
```
Настройки → Сеть → Настройки прокси → Ручная настройка
SOCKS5 хост: 127.0.0.1, порт: 1080
```

**Chrome/Edge:**
```bash
# Linux
google-chrome --proxy-server="socks5://127.0.0.1:1080"

# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --proxy-server="socks5://127.0.0.1:1080"

# macOS
open -a "Google Chrome" --args --proxy-server="socks5://127.0.0.1:1080"
```

### Системный прокси

**Linux:**
```bash
export ALL_PROXY="socks5://127.0.0.1:1080"
export http_proxy="socks5://127.0.0.1:1080"
export https_proxy="socks5://127.0.0.1:1080"

# Отключение
unset ALL_PROXY
```

**Windows (PowerShell):**
```powershell
$env:ALL_PROXY="socks5://127.0.0.1:1080"
$env:http_proxy="socks5://127.0.0.1:1080"
$env:https_proxy="socks5://127.0.0.1:1080"

# Отключение
$env:ALL_PROXY=""
```

**macOS:**
```bash
export ALL_PROXY="socks5://127.0.0.1:1080"

# Отключение
unset ALL_PROXY
```

### Приложения

**Telegram:**
```
Настройки → Расширенные → Прокси → SOCKS5
Хост: 127.0.0.1, Порт: 1080
```

**Tor Browser:**
```
Настройки → Подключение → Настройки прокси → SOCKS5
Хост: 127.0.0.1, Порт: 1080
```

**curl:**
```bash
curl --socks5 127.0.0.1:1080 https://api.ipify.org
```

**git:**
```bash
git config --global http.proxy socks5://127.0.0.1:1080
git config --global https.proxy socks5://127.0.0.1:1080
```

---

## 🔗 Каскадное подключение

### Архитектура
```
Клиент → Сервер C (уровень 2) → Сервер B (уровень 1) → Сервер A (уровень 0) → Интернет
```

### Настройка

**Сервер A (основной, уровень 0):**
```bash
# .env.server_a
SERVER_HOST=0.0.0.0
SERVER_PORT=6666
CASCADE_MODE=false
SERVER_LEVEL=0
ALLOW_INTERNET=true
```

**Сервер B (промежуточный, уровень 1):**
```bash
# .env.server_b
SERVER_HOST=0.0.0.0
SERVER_PORT=6667
CASCADE_MODE=true
UPSTREAM_SERVER=192.168.1.100:6666
SERVER_LEVEL=1
ALLOW_INTERNET=false
```

**Сервер C (входной, уровень 2):**
```bash
# .env.server_c
SERVER_HOST=0.0.0.0
SERVER_PORT=6668
CASCADE_MODE=true
UPSTREAM_SERVER=192.168.1.101:6667
SERVER_LEVEL=2
ALLOW_INTERNET=false
```

### Запуск каскада
```bash
# 1. Запуск Сервера A
python server.py --config .env.server_a

# 2. Запуск Сервера B
python server.py --config .env.server_b

# 3. Запуск Сервера C
python server.py --config .env.server_c

# 4. Подключение клиента к Серверу C
python client.py --name client1 --server 192.168.1.102 --port 6668 --socks-port 1080
```

### Проверка каскада
```bash
# На Сервере A видно, что клиенты от Сервера B
# На Сервере B видно, что клиенты от Сервера C
# На Сервере C виден исходный клиент
```

---

## ⚖️ Балансировка нагрузки

### Стратегии

| Стратегия | Описание | Когда использовать |
|-----------|----------|-------------------|
| `random` | Случайный выбор с весами | Тестирование |
| `lowest_latency` | Минимальный пинг | Игры/голос |
| `round_robin` | По очереди | Равномерная нагрузка |
| `geographic` | По географической близости | Распределённые клиенты |
| `least_load` | Минимальная загрузка | Скачивание/стриминг |
| `adaptive` | Комбинация всех | Универсальная |

### Настройка

```bash
# .env.server
BALANCE_ENABLED=true
BALANCE_STRATEGY=adaptive
# Формат: id,host,port,location;id2,host2,port2,location2
BALANCE_SERVERS=server1,192.168.1.101,6666,russia;server2,10.0.0.102,6666,netherlands
BALANCE_API_PORT=8080
SERVER_LOCATION=russia
```

### API управления

```bash
# Статус балансировщика
curl http://localhost:8080/status

# Ответ:
{
  "strategy": "adaptive",
  "total_servers": 2,
  "available_servers": 2,
  "servers": [
    {"id": "server1", "location": "russia", "latency": 5.2, "load": 0.3},
    {"id": "server2", "location": "netherlands", "latency": 82.5, "load": 0.1}
  ]
}

# Выбор сервера для клиента
curl "http://localhost:8080/select?client_id=client1&location=russia"

# Смена стратегии
curl "http://localhost:8080/strategy?name=lowest_latency"

# Добавление сервера
curl "http://localhost:8080/add_server?id=server3&host=10.0.0.103&port=6666&location=germany"

# Удаление сервера
curl "http://localhost:8080/remove_server?id=server3"
```

---

## 🔐 Управление сертификатами

### Инициализация CA
```bash
python d3_ca.py init
# ✅ CA создан: D3 Root CA
```

### Выпуск сертификата
```bash
python d3_ca.py issue client1 --days 365
# 🔑 Введите пароль: ******
# ✅ Сертификат для client1 создан
#    📁 Папка: certs/clients/client1/
#    🔑 Приватный ключ: client_private.pem (запаролен)
#    📜 Сертификат: client_cert.pem
#    🏛️ CA сертификат: ca_cert.pem
```

### Список сертификатов
```bash
python d3_ca.py list
# 📋 Выпущенные сертификаты:
# --------------------------------------------------
#    client1: ✅ Активен (350 дней)
#    client2: ✅ Активен (100 дней)
```

### Обновление сертификата
```bash
python d3_ca.py renew client1 --days 365
# 🔄 Обновление сертификата для client1...
# ✅ Сертификат для client1 обновлён
```

### Отзыв сертификата
```bash
python d3_ca.py revoke client1
# 🚫 Сертификат client1 отозван
```

### Автоматическое обновление (на сервере)
```bash
# В .env.server
AUTO_RENEW_THRESHOLD=7  # Обновлять за 7 дней до истечения
```

---

## 📱 Android (Termux)

### Установка
```bash
# 1. Установка Termux из F-Droid

# 2. Обновление пакетов
pkg update && pkg upgrade

# 3. Установка Python и зависимостей
pkg install python python-pip openssl iptables

# 4. Установка Python пакетов
pip install cryptography python-dotenv dnspython

# 5. Копирование клиента
# Поместите d3_client_android в /data/data/com.termux/files/home/
chmod +x d3_client_android
```

### Запуск
```bash
# Базовый запуск
./d3_client_android --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080

# Запуск в фоне
nohup ./d3_client_android --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080 > d3.log 2>&1 &

# Проверка логов
cat d3.log

# Остановка
killall d3_client_android
```

### Выбор приложения для проксирования
```bash
# Список приложений
./d3_client_android --list-apps

# Выбор приложения
./d3_client_android --android-app com.example.app

# Настройка iptables для приложения
su -c "iptables -t nat -A OUTPUT -p tcp -m owner --uid-owner 10043 -j DNAT --to-destination 127.0.0.1:1080"
```

### Автозапуск в Termux
```bash
# Создание скрипта автозапуска
mkdir -p ~/.termux/boot
nano ~/.termux/boot/d3_vpn.sh
```

```bash
#!/bin/bash
cd ~/d3_vpn
nohup ./d3_client_android --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080 > d3.log 2>&1 &
```

```bash
chmod +x ~/.termux/boot/d3_vpn.sh
```

---

## 🔧 Устранение неполадок

### Клиент не подключается

```bash
# 1. Проверь, что сервер запущен
netstat -tlnp | grep 6666

# 2. Проверь, что порт открыт
telnet 192.168.1.100 6666

# 3. Проверь, что TUNNEL_MODE совпадает
# Сервер: grep TUNNEL_MODE .env.server
# Клиент: grep TUNNEL_MODE .env.client

# 4. Проверь, что DNS_DOMAIN совпадает (для DNS-туннеля)
grep DNS_DOMAIN .env.server
grep DNS_DOMAIN .env.client
```

### DNS-туннель не работает

```bash
# 1. Проверь, что домен ведёт на сервер
nslookup vpn.example.com

# 2. Проверь, что сервер слушает DNS
sudo tcpdump -i any port 53

# 3. Проверь, что клиент отправляет DNS-запросы
# На клиенте: включи логи
python client.py --debug

# 4. Проверь, что нет фаервола на порту 53
sudo ufw allow 53
```

### Ошибка "AUTH_FAILED"

```bash
# 1. Проверь, что сертификат существует
ls certs/clients/client1/

# 2. Проверь, что сертификат не истёк
openssl x509 -in certs/clients/client1/client_cert.pem -enddate -noout

# 3. Перевыпусти сертификат
python d3_ca.py renew client1 --days 365

# 4. Проверь имя клиента
# В .env.client: CLIENT_NAME=client1
# В сертификате: client1
```

### Ошибка "Connection refused"

```bash
# Проверка, что сервер запущен
netstat -tlnp | grep 6666

# Проверка фаервола
sudo ufw allow 6666
sudo ufw allow 1080

# Проверка SELinux (CentOS/RHEL)
sudo setenforce 0
```

### Ошибка "Permission denied"

```bash
# Добавление прав на выполнение
chmod +x d3_server d3_client d3_ca

# Запуск от root (для iptables)
sudo ./d3_server
```

### Прокси не работает

```bash
# Проверка SOCKS5
curl --socks5 127.0.0.1:1080 https://api.ipify.org

# Проверка порта
netstat -tlnp | grep 1080

# Проверка, что клиент запущен
ps aux | grep d3_client
```

### Балансировка не работает

```bash
# Проверка статуса
curl http://localhost:8080/status

# Проверка списка серверов
curl "http://localhost:8080/strategy?name=random"

# Проверка логов
tail -f logs/server.log | grep BALANCE
```

---

## 📄 Лицензия

MIT License

---

## ⚠️ Disclaimer

Используйте только в законных целях! Автор не несёт ответственности за неправомерное использование.

---

**Версия:** 1.0.0
**Поддерживаемые платформы:** Linux, Windows, macOS, Android

---