#!/usr/bin/env python3
"""
D3 Stealth VPN Client v7.0.0
Поддерживает: SOCKS5 прокси, маскировку, туннели, автоматическое перенаправление
ВСЁ В ОДНОМ ФАЙЛЕ
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import asyncio
import struct
import socket
import os
import time
import random
import json
import argparse
from typing import Optional, Dict
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.backends import default_backend
except:
    print("⚠️ Установите: pip install cryptography")
    sys.exit(1)

# ============================================
# КОНФИГУРАЦИЯ
# ============================================
class ClientConfig:
    def __init__(self):
        self.server_host = os.getenv("SERVER_HOST", "127.0.0.1")
        self.server_port = int(os.getenv("SERVER_PORT", "6666"))
        self.mask_mode = os.getenv("MASK_MODE", "https")
        self.tunnel_mode = os.getenv("TUNNEL_MODE", "icmp")
        self.client_name = os.getenv("CLIENT_NAME", "client1")
        self.cert_dir = Path("certs/clients") / self.client_name
        self.cert_path = self.cert_dir / "client_cert.pem"
        self.private_path = self.cert_dir / "client_private.pem"
        self.ca_cert_path = self.cert_dir / "ca_cert.pem"
        self.socks_host = os.getenv("SOCKS_HOST", "127.0.0.1")
        self.socks_port = int(os.getenv("SOCKS_PORT", "1080"))
        self.socks_enabled = os.getenv("SOCKS_ENABLED", "true").lower() == "true"

config = ClientConfig()

# ============================================
# МАСКИРОВКА
# ============================================
class PacketMask:
    @staticmethod
    async def apply(data: bytes, mode: str) -> bytes:
        if mode == "http":
            headers = [f"GET /{os.urandom(8).hex()} HTTP/1.1", f"Host: {os.urandom(6).hex()}.com",
                      f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)", f"Content-Length: {len(data)}", "", ""]
            return "\r\n".join(headers).encode() + data
        elif mode == "https":
            tls_header = b"\x16\x03\x03" + struct.pack(">H", len(data) + 5)
            return tls_header + b"\x17\x03\x03" + struct.pack(">H", len(data)) + data
        elif mode == "traffic":
            headers = [f"GET /{os.urandom(8).hex()} HTTP/1.1", f"Host: {os.urandom(6).hex()}.com",
                      f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)", f"X-D3-Data: {data.hex()}", "", ""]
            return "\r\n".join(headers).encode()
        return data
    
    @staticmethod
    async def remove(data: bytes, mode: str) -> Optional[bytes]:
        if mode == "http":
            try: return data.split(b"\r\n\r\n", 1)[1]
            except: return None
        elif mode == "https":
            if len(data) >= 5 and data[:3] == b"\x17\x03\x03":
                return data[5:]
            return None
        elif mode == "traffic":
            try:
                for line in data.split(b"\r\n"):
                    if line.startswith(b"X-D3-Data:"):
                        return bytes.fromhex(line.split(b":")[1].strip().decode())
                return None
            except: return None
        return data

# ============================================
# ТУННЕЛИ
# ============================================
class Tunnel:
    async def send(self, writer, data: bytes): raise NotImplementedError
    async def receive(self, reader) -> Optional[bytes]: raise NotImplementedError

class ICMPTunnel(Tunnel):
    async def send(self, writer, data: bytes):
        writer.write(b"ICMP:" + data)
        await writer.drain()
    async def receive(self, reader) -> Optional[bytes]:
        data = await reader.read(65535)
        if data.startswith(b"ICMP:"):
            return data[5:]
        return None

class DNSTunnel(Tunnel):
    def __init__(self):
        self.domain = os.getenv("DNS_DOMAIN", "vpn.dns-tunnel.com")
    async def send(self, writer, data: bytes):
        import dns.message, dns.rdatatype
        data_hex = data.hex()
        chunks = [data_hex[i:i+50] for i in range(0, len(data_hex), 50)]
        domain = ".".join(chunks) + "." + self.domain
        message = dns.message.make_query(domain, dns.rdatatype.TXT)
        writer.write(b"DNS:" + message.to_wire())
        await writer.drain()
    async def receive(self, reader) -> Optional[bytes]:
        data = await reader.read(65535)
        if data.startswith(b"DNS:"):
            try:
                import dns.message
                message = dns.message.from_wire(data[4:])
                for answer in message.answer:
                    for item in answer.items:
                        if item.rdtype == dns.rdatatype.TXT:
                            return bytes.fromhex(b"".join(item.strings).decode())
                return None
            except:
                return None
        return None

class RawTunnel(Tunnel):
    async def send(self, writer, data: bytes):
        writer.write(data)
        await writer.drain()
    async def receive(self, reader) -> Optional[bytes]:
        return await reader.read(65535)

class TunnelFactory:
    _tunnels = {"icmp": ICMPTunnel, "dns": DNSTunnel, "raw": RawTunnel}
    @classmethod
    def create(cls, mode: str) -> Tunnel:
        return cls._tunnels.get(mode, RawTunnel)()

# ============================================
# СЕРТИФИКАТ
# ============================================
class CertificateLoader:
    def __init__(self):
        self.private_key = None
        self.certificate = None
        self._load()
    
    def _load(self):
        if config.cert_path.exists():
            with open(config.cert_path, "rb") as f:
                self.certificate = x509.load_pem_x509_certificate(f.read())
        if config.private_path.exists():
            import getpass
            pwd = getpass.getpass(f"🔑 Пароль для {config.client_name}: ")
            with open(config.private_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(f.read(), password=pwd.encode())
        if not self.certificate or not self.private_key:
            print(f"❌ Сертификат не найден! Запустите: python3 d3_ca.py issue {config.client_name}")
            sys.exit(1)
    
    def get_cert_pem(self) -> bytes:
        return self.certificate.public_bytes(serialization.Encoding.PEM)
    
    def sign(self, data: bytes) -> bytes:
        return self.private_key.sign(data)

# ============================================
# SOCKS5 ПРОКСИ
# ============================================
class SOCKS5Proxy:
    def __init__(self, d3_client):
        self.d3_client = d3_client
        self.host = config.socks_host
        self.port = config.socks_port
        self.server = None
    
    async def start(self):
        if not config.socks_enabled:
            return
        print(f"🔌 SOCKS5 прокси: {self.host}:{self.port}")
        self.server = await asyncio.start_server(self._handle, self.host, self.port)
        async with self.server:
            await self.server.serve_forever()
    
    async def _handle(self, reader, writer):
        try:
            # Рукопожатие
            data = await reader.read(2)
            if len(data) < 2 or data[0] != 0x05:
                writer.close()
                return
            writer.write(b"\x05\x00")
            await writer.drain()
            
            # Запрос
            data = await reader.read(4)
            if len(data) < 4:
                writer.close()
                return
            
            addr_data = await reader.read(4)
            port_data = await reader.read(2)
            if len(addr_data) < 4 or len(port_data) < 2:
                writer.close()
                return
            
            target_ip = socket.inet_ntoa(addr_data)
            target_port = struct.unpack("!H", port_data)[0]
            
            print(f"🎯 {target_ip}:{target_port}")
            
            # Отправка через D3
            await self.d3_client._send_data(f"DST:{target_ip}:{target_port}:PAYLOAD:".encode())
            
            # Ответ
            resp = struct.pack("!BBBB", 0x05, 0x00, 0x00, 0x01) + addr_data + port_data
            writer.write(resp)
            await writer.drain()
            
            # Проксирование
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                await self.d3_client._send_data(data)
                
        except Exception as e:
            print(f"⚠️ SOCKS5 ошибка: {e}")
        finally:
            writer.close()

# ============================================
# ОСНОВНОЙ КЛИЕНТ
# ============================================
class D3VPNClient:
    def __init__(self):
        self.config = config
        self.cert = CertificateLoader()
        self.reader = None
        self.writer = None
        self.vpn_ip = None
        self.is_running = False
        self.tunnel = TunnelFactory.create(config.tunnel_mode)
        self.socks5 = SOCKS5Proxy(self)
        self.msg_queue = asyncio.Queue()
    
    async def connect(self):
        print(f"🔗 Подключение к {self.config.server_host}:{self.config.server_port}")
        print(f"🎭 Маскировка: {self.config.mask_mode}")
        print(f"🔌 Туннель: {self.config.tunnel_mode}")
        
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.config.server_host, self.config.server_port
            )
            
            # Аутентификация
            cert_pem = self.cert.get_cert_pem()
            nonce = os.urandom(16)
            signature = self.cert.sign(nonce)
            auth = struct.pack(">H", len(cert_pem)) + cert_pem + nonce + signature
            
            masked = await PacketMask.apply(auth, self.config.mask_mode)
            await self.tunnel.send(self.writer, masked)
            
            # Ответ
            raw = await self.tunnel.receive(self.reader)
            if raw:
                data = await PacketMask.remove(raw, self.config.mask_mode)
                if data and not data.startswith(b"AUTH_FAILED"):
                    # Проверка на редирект
                    try:
                        msg = json.loads(data.decode())
                        if msg.get("type") == "redirect":
                            host, port = msg.get("host"), msg.get("port")
                            print(f"🔄 Перенаправление на {host}:{port}")
                            self.config.server_host = host
                            self.config.server_port = port
                            writer.close()
                            await asyncio.sleep(1)
                            await self.connect()
                            return
                    except:
                        pass
                    
                    try:
                        cfg = json.loads(data.decode())
                        self.vpn_ip = cfg.get("ip")
                        print(f"✅ Подключён! IP: {self.vpn_ip}")
                    except:
                        pass
            
            # Запуск SOCKS5
            if config.socks_enabled:
                asyncio.create_task(self.socks5.start())
            
            self.is_running = True
            await self._receive_loop()
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    async def _receive_loop(self):
        try:
            while self.is_running:
                raw = await self.tunnel.receive(self.reader)
                if not raw:
                    break
                data = await PacketMask.remove(raw, self.config.mask_mode)
                if data:
                    await self.msg_queue.put(data)
        except:
            pass
    
    async def _send_data(self, data: bytes):
        masked = await PacketMask.apply(data, self.config.mask_mode)
        await self.tunnel.send(self.writer, masked)
    
    async def _receive_data(self, timeout: float = 5.0) -> Optional[bytes]:
        try:
            return await asyncio.wait_for(self.msg_queue.get(), timeout)
        except:
            return None

# ============================================
# ЗАПУСК
# ============================================
async def main():
    parser = argparse.ArgumentParser(description="D3 Stealth VPN Client v7.0.0")
    parser.add_argument("--server", default=config.server_host)
    parser.add_argument("--port", type=int, default=config.server_port)
    parser.add_argument("--name", default=config.client_name)
    parser.add_argument("--socks-port", type=int, default=config.socks_port)
    parser.add_argument("--no-socks", action="store_true")
    parser.add_argument("--mask", default=config.mask_mode)
    parser.add_argument("--tunnel", default=config.tunnel_mode)
    args = parser.parse_args()
    
    config.server_host = args.server
    config.server_port = args.port
    config.client_name = args.name
    config.socks_port = args.socks_port
    config.mask_mode = args.mask
    config.tunnel_mode = args.tunnel
    if args.no_socks:
        config.socks_enabled = False
    
    client = D3VPNClient()
    await client.connect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Выход")
