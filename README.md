# 🚀 D3 Stealth VPN v1.0.0

**Supported Platforms:** Linux, Windows, macOS, Android

**D3** is a highly secure VPN protocol with traffic obfuscation, certificate support, SOCKS5 proxy, cascade connection, and load balancing.  
D3 = Direct, Dynamic, Discreet

---

## 📋 Table of Contents

1. [Quick Start](#-quick-start)
2. [How It Works](#-how-it-works)
3. [Server Configuration](#-server-configuration)
4. [Client Configuration](#-client-configuration)
5. [Tunnel Configuration (TUNNEL_MODE)](#-tunnel-configuration-tunnel_mode)
6. [DNS Tunnel Configuration](#-dns-tunnel-configuration)
7. [Correct vs Incorrect Usage](#-correct-vs-incorrect-usage)
8. [Building Binaries](#-building-binaries)
9. [Running the Server](#-running-the-server)
10. [Running the Client](#-running-the-client)
11. [SOCKS5 Configuration](#-socks5-configuration)
12. [Cascade Connection](#-cascade-connection)
13. [Load Balancing](#-load-balancing)
14. [Certificate Management](#-certificate-management)
15. [Android (Termux)](#-android-termux)
16. [Troubleshooting](#-troubleshooting)

---

## ⚡ Quick Start

```powershell
# ============================================
# 1. CREATE VIRTUAL ENVIRONMENT
# ============================================

# Windows
py -m venv .venv

# Linux/macOS
python3 -m venv .venv

# ============================================
# 2. ACTIVATE VIRTUAL ENVIRONMENT
# ============================================

# Windows (PowerShell/CMD)
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# ✅ After activation, (.venv) will appear at the beginning of the line
# (.venv) PS C:\projects\d3>

# ❌ If (.venv) does NOT appear → activation FAILED!
#    Try: .venv\Scripts\activate.bat (Windows)
#    Or: source .venv/bin/activate (Linux)

# ============================================
# 3. EXIT VIRTUAL ENVIRONMENT
# ============================================

deactivate

# ✅ (.venv) will disappear from the line
# PS C:\projects\d3>

# ❌ If (.venv) does NOT disappear → try: exit (close terminal)

# ============================================
# 4. INSTALL DEPENDENCIES (INSIDE .venv!)
# ============================================

# ✅ CORRECT (activated .venv first, then installed)
.venv\Scripts\activate
pip install -r requirements.txt

# ❌ INCORRECT (installing globally, without activation)
pip install -r requirements.txt

# ============================================
# 5. VERIFY EVERYTHING WORKS
# ============================================

# ✅ Verify Python
python --version
# Python 3.14.6

# ✅ Verify pip
pip --version
# pip 26.1.2 from ...\.venv\Lib\site-packages\pip

# ❌ If pip path does NOT contain .venv → you're NOT inside!
#    Need: .venv\Scripts\activate
```

---

## 🧠 How It Works

### Overall Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         D3 VPN                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  CLIENT                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  1. Application (browser/Telegram) sends request        │    │
│  │  2. SOCKS5 proxy (127.0.0.1:1080) intercepts           │    │
│  │  3. D3 Client encrypts data with ChaCha20              │    │
│  │  4. Obfuscates as HTTP/HTTPS/Traffic                   │    │
│  │  5. Sends through tunnel (ICMP/DNS/RAW)                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  TUNNEL (ICMP / DNS / RAW)                              │    │
│  │  - Data is transmitted inside the selected protocol     │    │
│  │  - DPI cannot identify it as VPN traffic                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  SERVER                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  1. Receives traffic through tunnel                     │    │
│  │  2. Removes obfuscation                                 │    │
│  │  3. Decrypts with ChaCha20                              │    │
│  │  4. Routes the request                                  │    │
│  │  5. Sends to internet (NAT)                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  INTERNET                                               │    │
│  │  - Server uses its own IP                               │    │
│  │  - Response returns to client                           │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### How a Packet Travels (Step by Step)

```
1. Client: Application (browser) wants to load google.com
   └── SOCKS5 proxy (127.0.0.1:1080)

2. Client: D3 encrypts request with ChaCha20
   └── plaintext: "GET / HTTP/1.1 Host: google.com"
   └── encrypted: (binary data)

3. Client: Adds obfuscation (if enabled)
   └── HTTP obfuscation: "HTTP/1.1 200 OK... {encrypted}"

4. Client: Sends through tunnel
   └── TUNNEL_MODE=icmp → packet inside ping
   └── TUNNEL_MODE=dns → packet inside DNS query
   └── TUNNEL_MODE=raw → packet as UDP datagram

5. Server: Receives packet
   └── Extracts from tunnel
   └── Removes obfuscation
   └── Decrypts with ChaCha20

6. Server: Routes
   └── If request to google.com → NAT to internet
   └── If request to another client → forwards

7. Server: Receives response from google.com
   └── Encrypts with ChaCha20
   └── Obfuscates
   └── Sends back to client
```

---

## 🖥️ Server Configuration

### Step 1: Prepare Environment

```bash
# 1. Create server folder
mkdir d3_server
cd d3_server

# 2. Create virtual environment
python -m venv .venv

# 3. Activate it
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

### Step 2: Create `.env.server` File

```bash
# Create .env.server file in server folder
nano .env.server
```

```bash
# ============================================
# D3 VPN SERVER CONFIGURATION
# ============================================

# === BASIC PARAMETERS ===
# SERVER_HOST - which IP to listen on
#   - 0.0.0.0  → listen on all interfaces (recommended)
#   - 127.0.0.1 → local access only (for testing)
#   - 192.168.1.100 → specific IP
SERVER_HOST=0.0.0.0

# SERVER_PORT - port for client connections
#   - 6666 - default port
#   - Can use any free port
SERVER_PORT=6666

# VPN_SUBNET - subnet for clients
#   - Clients get IPs from this subnet
#   - Server gets .1 address
VPN_SUBNET=10.0.0.0/24

# ALLOW_INTERNET - allow clients to access internet
#   - true  → clients can access internet through server (NAT)
#   - false → clients can only communicate within VPN
ALLOW_INTERNET=true

# === OBFUSCATION ===
# MASK_MODE - how to obfuscate traffic
#   - http    → packets look like HTTP responses
#   - https   → packets look like TLS traffic
#   - traffic → packets look like YouTube/Google traffic
MASK_MODE=https

# === TUNNELING ===
# TUNNEL_MODE - how to transmit data
#   - icmp   → through ICMP (ping) packets
#   - dns    → through DNS queries
#   - raw    → direct UDP transmission (fastest)
TUNNEL_MODE=icmp

# === DNS TUNNEL (needed only for TUNNEL_MODE=dns) ===
# DNS_DOMAIN - your domain pointing to the server
#   - Example: vpn.example.com
#   - Domain must have an A-record pointing to server IP
DNS_DOMAIN=vpn.example.com

# === CERTIFICATES ===
CA_DIR=certs/ca
AUTO_RENEW_THRESHOLD=7
KEY_ROTATION_INTERVAL=60

# === CASCADE CONNECTION ===
# CASCADE_MODE - enable cascade or not
#   - true  → server connects to another server
#   - false → server works independently
CASCADE_MODE=false

# SERVER_LEVEL - server level in cascade
#   - 0 → main server (internet gateway)
#   - 1 → intermediate
#   - 2+ → entry servers
SERVER_LEVEL=0

# UPSTREAM_SERVER - which server to connect to (for cascade)
UPSTREAM_SERVER=192.168.1.100:6666

# === LOAD BALANCING ===
BALANCE_ENABLED=false
BALANCE_STRATEGY=adaptive
BALANCE_SERVERS=server1,192.168.1.101,6666,russia;server2,10.0.0.102,6666,netherlands
BALANCE_API_PORT=8080
SERVER_LOCATION=russia
```

### Step 3: Initialize Certificates

```bash
# Create root CA certificate
python d3_ca.py init

# Issue certificate for client
python d3_ca.py issue client1 --days 365

# Verify certificate was created
python d3_ca.py list
# ✅ client1: Active (365 days)
```

### Step 4: Start Server

```bash
# Start with configuration file
python server.py

# Run in background (Linux)
nohup python server.py > d3.log 2>&1 &

# Verify server is running
netstat -tlnp | grep 6666
# tcp  0  0 0.0.0.0:6666  0.0.0.0:*  LISTEN  12345/python
```

---

## 💻 Client Configuration

### Step 1: Prepare Environment

```bash
# 1. Create client folder
mkdir d3_client
cd d3_client

# 2. Create virtual environment
python -m venv .venv

# 3. Activate it
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

### Step 2: Get Certificate from Server

Certificates are generated on the server. Copy them to the client:

```bash
# On the server
# Certificates are located in: certs/clients/client1/
#   ├── client_cert.pem   # Client certificate
#   ├── client_private.pem # Private key (password protected)
#   └── ca_cert.pem        # CA certificate

# Copy certs folder to client
scp -r certs/ user@client:/path/to/d3_client/
```

### Step 3: Create `.env.client` File

```bash
# Create .env.client file in client folder
nano .env.client
```

```bash
# ============================================
# D3 VPN CLIENT CONFIGURATION
# ============================================

# === SERVER ===
# SERVER_HOST - server IP address
#   - Can specify IP: 192.168.1.100
#   - Can specify domain: vpn.example.com
SERVER_HOST=192.168.1.100

# SERVER_PORT - server port (must match server)
SERVER_PORT=6666

# === CLIENT ===
# CLIENT_NAME - client name (must match certificate)
CLIENT_NAME=client1

# === OBFUSCATION ===
# MASK_MODE - how to obfuscate traffic (must match server)
#   - http, https, traffic
MASK_MODE=https

# === TUNNELING ===
# TUNNEL_MODE - how to transmit data (must match server!)
#   - icmp, dns, raw
TUNNEL_MODE=icmp

# === DNS TUNNEL (needed only for TUNNEL_MODE=dns) ===
# DNS_DOMAIN - must MATCH the server!
DNS_DOMAIN=vpn.example.com

# === SOCKS5 PROXY ===
# SOCKS_HOST - where to run the proxy
#   - 127.0.0.1 → local applications only
#   - 0.0.0.0 → all devices on network
SOCKS_HOST=127.0.0.1

# SOCKS_PORT - SOCKS5 proxy port
SOCKS_PORT=1080

# SOCKS_ENABLED - enable SOCKS5 proxy
SOCKS_ENABLED=true
```

### Step 4: Start Client

```bash
# Start with parameters (override .env)
python client.py --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080

# Start with configuration file
python client.py --config .env.client

# Run in background (Linux)
nohup python client.py > d3.log 2>&1 &

# Verify SOCKS5 is working
netstat -tlnp | grep 1080
# tcp  0  0 127.0.0.1:1080  0.0.0.0:*  LISTEN  12346/python
```

---

## 🔌 Tunnel Configuration (TUNNEL_MODE)

### What is TUNNEL_MODE?

**TUNNEL_MODE** is how data is transmitted between client and server. You can choose **ONLY ONE** option!

```
┌─────────────────────────────────────────────────────────────┐
│  CLIENT                    TUNNEL                SERVER     │
│  ┌──────────┐           ┌──────────┐           ┌──────────┐ │
│  │  Data    │ ────────▶ │  ICMP    │ ────────▶ │  Data    │ │
│  └──────────┘           │  DNS     │           └──────────┘ │
│                         │  RAW     │                        │
│                         └──────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### Available Modes

| Mode | How It Works | When to Use | Speed | Stealth |
|------|--------------|-------------|-------|---------|
| **RAW** | Direct UDP transmission | When no restrictions | 🟢 High | 🔴 Low |
| **ICMP** | Inside ping packets | When ports are blocked | 🟡 Medium | 🟡 Medium |
| **DNS** | Inside DNS queries | When everything is blocked | 🔴 Low | 🟢 High |

### How to Choose TUNNEL_MODE

```bash
# ============================================
# Step 1: Start with RAW (fastest)
# ============================================
TUNNEL_MODE=raw

# If it works → great!
# If it does NOT work → switch to ICMP

# ============================================
# Step 2: Try ICMP (bypasses port blocking)
# ============================================
TUNNEL_MODE=icmp

# If it works → great!
# If it does NOT work → switch to DNS

# ============================================
# Step 3: Use DNS (bypasses almost everything)
# ============================================
TUNNEL_MODE=dns
DNS_DOMAIN=vpn.example.com  # ← DOMAIN REQUIRED!

# If it works → great!
# If it does NOT work → check DNS_DOMAIN
```

### Configuration Examples

```bash
# ============================================
# EXAMPLE 1: Fastest (RAW)
# ============================================
# Use if network doesn't block UDP
TUNNEL_MODE=raw

# ============================================
# EXAMPLE 2: Bypass Port Blocking (ICMP)
# ============================================
# Use if UDP/TCP ports are blocked
TUNNEL_MODE=icmp

# ============================================
# EXAMPLE 3: Maximum Stealth (DNS)
# ============================================
# Use if everything except DNS is blocked
TUNNEL_MODE=dns
DNS_DOMAIN=vpn.dynv6.net

# ============================================
# EXAMPLE 4: Combination with Obfuscation
# ============================================
# Traffic looks like HTTPS inside DNS
TUNNEL_MODE=dns
MASK_MODE=https
DNS_DOMAIN=vpn.dynv6.net
```

### ❌ What NOT to Do

```bash
# ❌ Can't specify multiple tunnels!
TUNNEL_MODE=icmp,dns,raw   # INCORRECT!
TUNNEL_MODE=[icmp,dns]     # INCORRECT!

# ❌ Can't use different tunnels on client and server
# Client: TUNNEL_MODE=icmp
# Server: TUNNEL_MODE=dns   # INCORRECT! They won't see each other!

# ✅ CORRECT: client and server use the SAME tunnel
TUNNEL_MODE=icmp   # On both client and server
```

---

## 🌐 DNS Tunnel Configuration

### What is a DNS Tunnel?

**DNS Tunnel** is a way to transmit data inside DNS queries. Traffic looks like normal DNS queries, but your data is "hidden" inside them.

```
How it looks to DPI:
  DNS query: "a1b2c3d4.vpn.example.com"
  DPI sees: normal DNS query to vpn.example.com
  Actually: your data is hidden inside "a1b2c3d4"

How it looks to D3:
  Client: "Hello" → HEX: "48656c6c6f" → query: "48656c6c6f.vpn.example.com"
  Server: receives → extracts "48656c6c6f" → "Hello"
```

### Step-by-Step DNS Tunnel Setup

#### Step 1: Get a Domain

You need a domain that points to your server's IP.

**Options:**

| Option | Difficulty | Cost | Example |
|--------|------------|------|---------|
| Buy a domain | 🟡 Medium | 💰 Paid | `example.com` |
| Free DynDNS | 🟢 Simple | 🆓 Free | `vpn.dynv6.net` |
| Local DNS | 🔴 Complex | 🆓 Free | `vpn.local` |

**Free DynDNS Services:**

```bash
# 1. DynV6 (recommended)
# Website: https://dynv6.com
# Domain: vpn.dynv6.net

# 2. DuckDNS
# Website: https://duckdns.org
# Domain: vpn.duckdns.org

# 3. No-IP
# Website: https://noip.com
# Domain: vpn.no-ip.org
```

#### Step 2: Configure DNS Record

At your domain registrar, add an **A-record**:

```
Name: vpn
Type: A
Value: 192.168.1.100   # ← Your D3 server IP
TTL: 60
```

**Verification:**

```bash
# Check DNS record works
nslookup vpn.example.com
# Server:  8.8.8.8
# Address: 8.8.8.8#53
# Non-authoritative answer:
# Name:    vpn.example.com
# Address: 192.168.1.100  ✅

# If no response → check DNS settings
```

#### Step 3: Configure Server

```bash
# .env.server
TUNNEL_MODE=dns
DNS_DOMAIN=vpn.example.com   # ← your domain
SERVER_HOST=0.0.0.0
SERVER_PORT=6666
```

```bash
# Start server
python server.py
```

#### Step 4: Configure Client

```bash
# .env.client
TUNNEL_MODE=dns
DNS_DOMAIN=vpn.example.com   # ← MUST MATCH SERVER!
SERVER_HOST=192.168.1.100
SERVER_PORT=6666
```

```bash
# Start client
python client.py
```

#### Step 5: Verify It Works

```bash
# On server: watch DNS queries
sudo tcpdump -i any port 53

# On client: test
curl --socks5 127.0.0.1:1080 https://api.ipify.org

# On server: you'll see DNS queries like
# 48656c6c6f.vpn.example.com
```

### ❌ What NOT to Do with DNS Tunnel

```bash
# ❌ Can't use DNS tunnel without a domain
TUNNEL_MODE=dns
# DNS_DOMAIN not set → ERROR!

# ❌ Can't have domain NOT pointing to server
DNS_DOMAIN=google.com   # INCORRECT!
# Queries will go to Google, not your server

# ❌ Can't use different domains on client and server
# Server: DNS_DOMAIN=vpn1.example.com
# Client: DNS_DOMAIN=vpn2.example.com   # INCORRECT!

# ✅ CORRECT: same domain on client and server
DNS_DOMAIN=vpn.example.com   # On both client and server
```

---

## ✅ Correct vs Incorrect Usage

### Correct (✅)

```bash
# 1. Use one TUNNEL_MODE on both client and server
# Server: TUNNEL_MODE=icmp
# Client: TUNNEL_MODE=icmp  ✅

# 2. Use one DNS_DOMAIN on both client and server
# Server: DNS_DOMAIN=vpn.example.com
# Client: DNS_DOMAIN=vpn.example.com  ✅

# 3. Use virtual environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt  ✅

# 4. Verify server is running
netstat -tlnp | grep 6666  ✅

# 5. Use same obfuscation mode
# Server: MASK_MODE=https
# Client: MASK_MODE=https  ✅

# 6. Start with RAW, then try others
TUNNEL_MODE=raw   # first
TUNNEL_MODE=icmp  # if raw doesn't work
TUNNEL_MODE=dns   # if icmp doesn't work  ✅
```

### Incorrect (❌)

```bash
# 1. Different TUNNEL_MODE on client and server
# Server: TUNNEL_MODE=icmp
# Client: TUNNEL_MODE=dns  ❌

# 2. Different DNS_DOMAIN on client and server
# Server: DNS_DOMAIN=vpn1.example.com
# Client: DNS_DOMAIN=vpn2.example.com  ❌

# 3. Installing packages without virtual environment
pip install -r requirements.txt  ❌

# 4. Starting client without checking server is running
python client.py  # server not running  ❌

# 5. Specifying multiple TUNNEL_MODE
TUNNEL_MODE=icmp,dns,raw  ❌

# 6. Using DNS tunnel without domain
TUNNEL_MODE=dns
# DNS_DOMAIN not set  ❌

# 7. Starting server without initializing CA
python server.py  # CA not created  ❌
# First: python d3_ca.py init
```

---

## 📊 Table: What Must Match

| Parameter | Server | Client | Must Match? |
|-----------|--------|--------|-------------|
| `TUNNEL_MODE` | icmp | icmp | ✅ YES! |
| `DNS_DOMAIN` | vpn.example.com | vpn.example.com | ✅ YES! (for DNS) |
| `MASK_MODE` | https | https | ✅ YES! |
| `SERVER_PORT` | 6666 | 6666 | ✅ YES! |
| `SERVER_HOST` | 0.0.0.0 | 192.168.1.100 | ❌ NO (different) |
| `CLIENT_NAME` | - | client1 | ❌ NO (client only) |
| `SOCKS_PORT` | - | 1080 | ❌ NO (client only) |

---

## 📦 Building Binaries

### Method 1: Using Makefile (recommended)

```bash
# Install PyInstaller
pip install pyinstaller

# Build all binaries
# if make command is not available, install it
# on Windows: (choco install make | scoop install make)
make build-all

# Binaries in dist/
ls dist/
# d3_server  d3_client  d3_ca
```

### Method 2: Using Script

```bash
# Run build script
./build.sh

# Binaries in dist/
```

### Method 3: Manually

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

### Building for Different Platforms

```bash
# Linux (run on Linux)
pyinstaller --onefile --name d3_server_linux server.py

# Windows (run on Windows)
pyinstaller --onefile --name d3_server_windows.exe server.py

# macOS (run on macOS)
pyinstaller --onefile --name d3_server_mac server.py

# Cross-platform build (via Docker)
docker run --rm -v $(pwd):/app -w /app python:3.11-slim bash -c "
    pip install pyinstaller
    pyinstaller --onefile --name d3_server server.py
    pyinstaller --onefile --name d3_client client.py
    pyinstaller --onefile --name d3_ca d3_ca.py
"
```

### Cleanup

```bash
# Remove temporary files
make clean

# Or manually
rm -rf build/ dist/ *.spec
```

---

## 🖥️ Running the Server

### From Python (development)

```bash
# 1. Activate virtual environment
.venv\Scripts\activate

# 2. Start server
python server.py

# 3. Start with specific config file
python server.py --config .env.server

# 4. Start with debugging (more logs)
python server.py --debug
```

### From Binary (production)

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
# 1. Create service
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
# 2. Start service
sudo systemctl daemon-reload
sudo systemctl enable d3-vpn
sudo systemctl start d3-vpn
sudo systemctl status d3-vpn

# 3. View logs
sudo journalctl -u d3-vpn -f
```

### Docker

```bash
cd docker
docker-compose up -d
docker logs d3-vpn-server
docker-compose down
```

### Verify It Works

```bash
# Check server is listening on port
netstat -tlnp | grep 6666

# Check via curl
curl --socks5 127.0.0.1:1080 https://api.ipify.org
```

---

## 💻 Running the Client

### From Python (development)

```bash
# 1. Activate virtual environment
.venv\Scripts\activate

# 2. Start client
python client.py --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080

# 3. Start with config file
python client.py --config .env.client

# 4. Start with debugging
python client.py --debug
```

### From Binary (production)

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

### Background Mode

```bash
# Linux/macOS
nohup ./d3_client --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080 > d3.log 2>&1 &

# Windows (PowerShell)
Start-Process -NoNewWindow -FilePath "d3_client.exe" -ArgumentList "--name client1 --server 192.168.1.100 --port 6666 --socks-port 1080"
```

### Client Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--server` | Server IP | 127.0.0.1 |
| `--port` | Server port | 6666 |
| `--name` | Client name | client1 |
| `--socks-port` | SOCKS5 port | 1080 |
| `--no-socks` | Disable SOCKS5 | false |
| `--mask` | Obfuscation mode | https |
| `--tunnel` | Tunnel mode | icmp |

---

## 🌐 SOCKS5 Configuration

### Browsers

**Firefox:**
```
Settings → Network → Proxy Settings → Manual proxy configuration
SOCKS5 Host: 127.0.0.1, Port: 1080
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

### System Proxy

**Linux:**
```bash
export ALL_PROXY="socks5://127.0.0.1:1080"
export http_proxy="socks5://127.0.0.1:1080"
export https_proxy="socks5://127.0.0.1:1080"

# Disable
unset ALL_PROXY
```

**Windows (PowerShell):**
```powershell
$env:ALL_PROXY="socks5://127.0.0.1:1080"
$env:http_proxy="socks5://127.0.0.1:1080"
$env:https_proxy="socks5://127.0.0.1:1080"

# Disable
$env:ALL_PROXY=""
```

**macOS:**
```bash
export ALL_PROXY="socks5://127.0.0.1:1080"

# Disable
unset ALL_PROXY
```

### Applications

**Telegram:**
```
Settings → Advanced → Proxy → SOCKS5
Host: 127.0.0.1, Port: 1080
```

**Tor Browser:**
```
Settings → Connection → Proxy Settings → SOCKS5
Host: 127.0.0.1, Port: 1080
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

## 🔗 Cascade Connection

### Architecture
```
Client → Server C (level 2) → Server B (level 1) → Server A (level 0) → Internet
```

### Configuration

**Server A (main, level 0):**
```bash
# .env.server_a
SERVER_HOST=0.0.0.0
SERVER_PORT=6666
CASCADE_MODE=false
SERVER_LEVEL=0
ALLOW_INTERNET=true
```

**Server B (intermediate, level 1):**
```bash
# .env.server_b
SERVER_HOST=0.0.0.0
SERVER_PORT=6667
CASCADE_MODE=true
UPSTREAM_SERVER=192.168.1.100:6666
SERVER_LEVEL=1
ALLOW_INTERNET=false
```

**Server C (entry, level 2):**
```bash
# .env.server_c
SERVER_HOST=0.0.0.0
SERVER_PORT=6668
CASCADE_MODE=true
UPSTREAM_SERVER=192.168.1.101:6667
SERVER_LEVEL=2
ALLOW_INTERNET=false
```

### Starting the Cascade
```bash
# 1. Start Server A
python server.py --config .env.server_a

# 2. Start Server B
python server.py --config .env.server_b

# 3. Start Server C
python server.py --config .env.server_c

# 4. Connect client to Server C
python client.py --name client1 --server 192.168.1.102 --port 6668 --socks-port 1080
```

### Verifying Cascade
```bash
# On Server A, you'll see clients from Server B
# On Server B, you'll see clients from Server C
# On Server C, you'll see the original client
```

---

## ⚖️ Load Balancing

### Strategies

| Strategy | Description | When to Use |
|-----------|-------------|-------------|
| `random` | Random selection with weights | Testing |
| `lowest_latency` | Lowest ping | Gaming/Voice |
| `round_robin` | In rotation | Even load |
| `geographic` | Geographic proximity | Distributed clients |
| `least_load` | Minimum load | Downloads/Streaming |
| `adaptive` | Combination of all | Universal |

### Configuration

```bash
# .env.server
BALANCE_ENABLED=true
BALANCE_STRATEGY=adaptive
# Format: id,host,port,location;id2,host2,port2,location2
BALANCE_SERVERS=server1,192.168.1.101,6666,russia;server2,10.0.0.102,6666,netherlands
BALANCE_API_PORT=8080
SERVER_LOCATION=russia
```

### Management API

```bash
# Balancer status
curl http://localhost:8080/status

# Response:
{
  "strategy": "adaptive",
  "total_servers": 2,
  "available_servers": 2,
  "servers": [
    {"id": "server1", "location": "russia", "latency": 5.2, "load": 0.3},
    {"id": "server2", "location": "netherlands", "latency": 82.5, "load": 0.1}
  ]
}

# Select server for client
curl "http://localhost:8080/select?client_id=client1&location=russia"

# Change strategy
curl "http://localhost:8080/strategy?name=lowest_latency"

# Add server
curl "http://localhost:8080/add_server?id=server3&host=10.0.0.103&port=6666&location=germany"

# Remove server
curl "http://localhost:8080/remove_server?id=server3"
```

---

## 🔐 Certificate Management

### Initialize CA
```bash
python d3_ca.py init
# ✅ CA created: D3 Root CA
```

### Issue Certificate
```bash
python d3_ca.py issue client1 --days 365
# 🔑 Enter password: ******
# ✅ Certificate for client1 created
#    📁 Folder: certs/clients/client1/
#    🔑 Private key: client_private.pem (password protected)
#    📜 Certificate: client_cert.pem
#    🏛️ CA certificate: ca_cert.pem
```

### List Certificates
```bash
python d3_ca.py list
# 📋 Issued certificates:
# --------------------------------------------------
#    client1: ✅ Active (350 days)
#    client2: ✅ Active (100 days)
```

### Renew Certificate
```bash
python d3_ca.py renew client1 --days 365
# 🔄 Renewing certificate for client1...
# ✅ Certificate for client1 renewed
```

### Revoke Certificate
```bash
python d3_ca.py revoke client1
# 🚫 Certificate client1 revoked
```

### Automatic Renewal (on server)
```bash
# In .env.server
AUTO_RENEW_THRESHOLD=7  # Renew 7 days before expiry
```

---

## 📱 Android (Termux)

### Installation
```bash
# 1. Install Termux from F-Droid

# 2. Update packages
pkg update && pkg upgrade

# 3. Install Python and dependencies
pkg install python python-pip openssl iptables

# 4. Install Python packages
pip install cryptography python-dotenv dnspython

# 5. Copy client
# Place d3_client_android in /data/data/com.termux/files/home/
chmod +x d3_client_android
```

### Running
```bash
# Basic run
./d3_client_android --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080

# Run in background
nohup ./d3_client_android --name client1 --server 192.168.1.100 --port 6666 --socks-port 1080 > d3.log 2>&1 &

# Check logs
cat d3.log

# Stop
killall d3_client_android
```

### Selecting App for Proxying
```bash
# List apps
./d3_client_android --list-apps

# Select app
./d3_client_android --android-app com.example.app

# Configure iptables for app
su -c "iptables -t nat -A OUTPUT -p tcp -m owner --uid-owner 10043 -j DNAT --to-destination 127.0.0.1:1080"
```

### Auto-start in Termux
```bash
# Create auto-start script
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

## 🔧 Troubleshooting

### Client Won't Connect

```bash
# 1. Check server is running
netstat -tlnp | grep 6666

# 2. Check port is open
telnet 192.168.1.100 6666

# 3. Check TUNNEL_MODE matches
# Server: grep TUNNEL_MODE .env.server
# Client: grep TUNNEL_MODE .env.client

# 4. Check DNS_DOMAIN matches (for DNS tunnel)
grep DNS_DOMAIN .env.server
grep DNS_DOMAIN .env.client
```

### DNS Tunnel Not Working

```bash
# 1. Check domain points to server
nslookup vpn.example.com

# 2. Check server is listening for DNS
sudo tcpdump -i any port 53

# 3. Check client is sending DNS queries
# On client: enable logging
python client.py --debug

# 4. Check firewall on port 53
sudo ufw allow 53
```

### Error "AUTH_FAILED"

```bash
# 1. Check certificate exists
ls certs/clients/client1/

# 2. Check certificate hasn't expired
openssl x509 -in certs/clients/client1/client_cert.pem -enddate -noout

# 3. Renew certificate
python d3_ca.py renew client1 --days 365

# 4. Check client name
# In .env.client: CLIENT_NAME=client1
# In certificate: client1
```

### Error "Connection refused"

```bash
# Check server is running
netstat -tlnp | grep 6666

# Check firewall
sudo ufw allow 6666
sudo ufw allow 1080

# Check SELinux (CentOS/RHEL)
sudo setenforce 0
```

### Error "Permission denied"

```bash
# Add execute permissions
chmod +x d3_server d3_client d3_ca

# Run as root (for iptables)
sudo ./d3_server
```

### Proxy Not Working

```bash
# Check SOCKS5
curl --socks5 127.0.0.1:1080 https://api.ipify.org

# Check port
netstat -tlnp | grep 1080

# Check client is running
ps aux | grep d3_client
```

### Load Balancing Not Working

```bash
# Check status
curl http://localhost:8080/status

# Check server list
curl "http://localhost:8080/strategy?name=random"

# Check logs
tail -f logs/server.log | grep BALANCE
```

---

## 📄 License

MIT License

---

## ⚠️ Disclaimer

Use only for lawful purposes! The author is not responsible for misuse.

---

**Version:** 1.0.0
**Supported Platforms:** Linux, Windows, macOS, Android