#!/usr/bin/env python3
"""
D3 Stealth VPN Server v0.0.1
Поддерживает: каскадное подключение, балансировку нагрузки, маскировку, туннели
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
import hashlib
import hmac
import ipaddress
import subprocess
import datetime
import logging
import argparse
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from math import radians, sin, cos, sqrt, atan2

# ============================================
# ЛОГИРОВАНИЕ
# ============================================
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("D3Server")

# ============================================
# ЗАГРУЗКА КОНФИГУРАЦИИ
# ============================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# ============================================
# КРИПТОГРАФИЯ
# ============================================
try:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.x509.oid import NameOID
    import cryptography.x509 as x509
except:
    print("⚠️ Установите: pip install cryptography")
    sys.exit(1)

# ============================================
# КОНФИГУРАЦИЯ
# ============================================
@dataclass
class ServerConfig:
    # Основные
    host: str = os.getenv("SERVER_HOST", "0.0.0.0")
    port: int = int(os.getenv("SERVER_PORT", "6666"))
    vpn_subnet: str = os.getenv("VPN_SUBNET", "10.0.0.0/24")
    allow_internet: bool = os.getenv("ALLOW_INTERNET", "true").lower() == "true"
    
    # Маскировка и туннель
    mask_mode: str = os.getenv("MASK_MODE", "https")
    tunnel_mode: str = os.getenv("TUNNEL_MODE", "icmp")
    
    # Сертификаты
    ca_dir: str = os.getenv("CA_DIR", "certs/ca")
    ca_cert_path: str = os.getenv("CA_CERT_PATH", "certs/ca/ca_cert.pem")
    ca_private_path: str = os.getenv("CA_PRIVATE_PATH", "certs/ca/ca_private.pem")
    key_rotation_interval: int = int(os.getenv("KEY_ROTATION_INTERVAL", "60"))
    auto_renew_threshold: int = int(os.getenv("AUTO_RENEW_THRESHOLD", "7"))
    
    # DNS туннель
    dns_domain: str = os.getenv("DNS_DOMAIN", "vpn.dns-tunnel.com")
    
    # Каскад
    cascade_mode: bool = os.getenv("CASCADE_MODE", "false").lower() == "true"
    upstream_server: Optional[str] = os.getenv("UPSTREAM_SERVER", None)
    upstream_cert: Optional[str] = os.getenv("UPSTREAM_CERT", None)
    upstream_key: Optional[str] = os.getenv("UPSTREAM_KEY", None)
    server_level: int = int(os.getenv("SERVER_LEVEL", "0"))
    
    # Балансировка
    balance_enabled: bool = os.getenv("BALANCE_ENABLED", "false").lower() == "true"
    balance_strategy: str = os.getenv("BALANCE_STRATEGY", "adaptive")
    balance_servers: str = os.getenv("BALANCE_SERVERS", "")
    balance_api_port: int = int(os.getenv("BALANCE_API_PORT", "8080"))
    server_location: str = os.getenv("SERVER_LOCATION", "unknown")

config = ServerConfig()

# Глобальный ключ для шифрования (ротация)
SESSION_KEY = os.urandom(32)

# ============================================
# ============================================
# МАСКИРОВКА
# ============================================
class PacketMask:
    @staticmethod
    async def apply(data: bytes, mode: str) -> bytes:
        if mode == "http":
            headers = [
                f"HTTP/1.1 200 OK",
                f"Content-Type: application/octet-stream",
                f"Content-Length: {len(data)}",
                f"Server: nginx/1.18.0",
                f"Date: {time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())}",
                "",
                ""
            ]
            return "\r\n".join(headers).encode() + data
        elif mode == "https":
            tls_header = b"\x16\x03\x03" + struct.pack(">H", len(data) + 5)
            tls_record = b"\x17\x03\x03" + struct.pack(">H", len(data)) + data
            return tls_header + tls_record
        elif mode == "traffic":
            headers = [
                f"GET /{os.urandom(8).hex()} HTTP/1.1",
                f"Host: {os.urandom(6).hex()}.com",
                f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                f"X-D3-Data: {data.hex()}",
                f"Connection: keep-alive",
                "",
                ""
            ]
            return "\r\n".join(headers).encode()
        return data
    
    @staticmethod
    async def remove(data: bytes, mode: str) -> Optional[bytes]:
        if mode == "http":
            try:
                parts = data.split(b"\r\n\r\n", 1)
                return parts[1] if len(parts) == 2 else None
            except:
                return None
        elif mode == "https":
            logger.debug(f"Mask.remove https: len={len(data)}, first10: {data[:10]!r}")
            if len(data) >= 10 and data[:3] == b"\x16\x03\x03" and data[5:8] == b"\x17\x03\x03":
                payload_len = struct.unpack(">H", data[8:10])[0]
                return data[10:10+payload_len]
            logger.warning(f"Mask.remove: неожиданные данные: {data[:20]!r}")
            return None
        elif mode == "traffic":
            try:
                lines = data.split(b"\r\n")
                for line in lines:
                    if line.startswith(b"X-D3-Data:"):
                        hex_data = line.split(b":")[1].strip()
                        return bytes.fromhex(hex_data.decode())
                return None
            except:
                return None
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
        if not data:
            return None
        logger.debug(f"Tunnel recv {len(data)} bytes, first20: {data[:20]!r}")
        if data.startswith(b"ICMP:"):
            return data[5:]
        logger.warning(f"Tunnel: нет префикса ICMP!, first20: {data[:20]!r}")
        return None

class DNSTunnel(Tunnel):
    def __init__(self):
        self.domain = config.dns_domain
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
                            txt_data = b"".join(item.strings)
                            return bytes.fromhex(txt_data.decode())
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
# СЕРТИФИКАТЫ
# ============================================
class CertificateManager:
    def __init__(self):
        self.revoked_certs = set()
        self._load_ca()
    
    def _load_ca(self):
        try:
            with open(config.ca_private_path, "rb") as f:
                self.ca_private_key = serialization.load_pem_private_key(f.read(), password=None)
            with open(config.ca_cert_path, "rb") as f:
                self.ca_cert = x509.load_pem_x509_certificate(f.read())
            logger.info(f"CA загружен: {config.ca_cert_path}")
        except FileNotFoundError:
            logger.error("Файлы CA не найдены!")
            logger.error(f"Ожидается: {config.ca_cert_path}")
            logger.error(f"            {config.ca_private_path}")
            logger.error("Запустите: python d3_ca.py init")
            raise
        except Exception as e:
            logger.error(f"Ошибка загрузки CA: {e}")
            raise
    
    def verify_certificate(self, cert_pem: bytes) -> Tuple[bool, Optional[str]]:
        try:
            cert = x509.load_pem_x509_certificate(cert_pem)
            self.ca_cert.public_key().verify(cert.signature, cert.tbs_certificate_bytes)
            now = datetime.datetime.utcnow()
            if cert.not_valid_before > now or cert.not_valid_after < now:
                logger.warning("Сертификат клиента просрочен")
                return False, "expired"
            name = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            return True, name
        except Exception as e:
            logger.warning(f"Сертификат не прошёл проверку: {e}")
            return False, None

# ============================================
# БАЛАНСИРОВКА
# ============================================
class BalanceStrategy(Enum):
    RANDOM = "random"
    LOWEST_LATENCY = "lowest_latency"
    ROUND_ROBIN = "round_robin"
    GEOGRAPHIC = "geographic"
    LEAST_LOAD = "least_load"
    ADAPTIVE = "adaptive"

@dataclass
class ServerNode:
    id: str
    host: str
    port: int
    location: str
    latitude: float = 0.0
    longitude: float = 0.0
    avg_latency: float = 0.0
    current_load: float = 0.0
    connections: int = 0
    max_connections: int = 100
    is_available: bool = True
    
    def __post_init__(self):
        if self.latitude == 0 and self.longitude == 0:
            self.latitude, self.longitude = self._get_coords()
    
    def _get_coords(self) -> Tuple[float, float]:
        coords = {
            "russia": (55.7558, 37.6173), "netherlands": (52.3676, 4.9041),
            "kazakhstan": (43.2383, 76.9454), "finland": (60.1699, 24.9384),
            "germany": (52.5200, 13.4050), "usa": (40.7128, -74.0060),
            "uk": (51.5074, -0.1278), "singapore": (1.3521, 103.8198),
            "japan": (35.6762, 139.6503), "australia": (-33.8688, 151.2093),
            "brazil": (-23.5505, -46.6333), "south_africa": (-33.9249, 18.4241),
        }
        loc = self.location.lower()
        for key, coord in coords.items():
            if key in loc:
                return coord
        return (50.1109, 8.6821)
    
    def distance_to(self, lat: float, lon: float) -> float:
        lat1, lon1 = radians(self.latitude), radians(self.longitude)
        lat2, lon2 = radians(lat), radians(lon)
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
        return 2*atan2(sqrt(a), sqrt(1-a))*6371

class LoadBalancer:
    def __init__(self, strategy: str = "adaptive"):
        self.strategy = BalanceStrategy(strategy)
        self.servers: Dict[str, ServerNode] = {}
        self.rr_index = 0
        self.client_history: Dict[str, List[Tuple[str, float]]] = {}
    
    def add_server(self, node: ServerNode):
        self.servers[node.id] = node
    
    def remove_server(self, sid: str):
        if sid in self.servers:
            del self.servers[sid]
    
    async def select(self, client_id: str = None, location: str = None) -> Optional[ServerNode]:
        available = [s for s in self.servers.values() if s.is_available]
        if not available:
            return None
        if len(available) == 1:
            return available[0]
        
        if self.strategy == BalanceStrategy.RANDOM:
            weights = [max(1, 100 - s.avg_latency) * max(1, 10 - s.current_load*10) for s in available]
            return random.choices(available, weights=weights, k=1)[0]
        
        elif self.strategy == BalanceStrategy.LOWEST_LATENCY:
            return min(available, key=lambda s: s.avg_latency if s.avg_latency > 0 else 999)
        
        elif self.strategy == BalanceStrategy.ROUND_ROBIN:
            self.rr_index = (self.rr_index + 1) % len(available)
            return available[self.rr_index]
        
        elif self.strategy == BalanceStrategy.GEOGRAPHIC and location:
            client_coords = {"russia": (55.7558, 37.6173), "netherlands": (52.3676, 4.9041),
                           "germany": (52.5200, 13.4050), "usa": (40.7128, -74.0060),
                           "uk": (51.5074, -0.1278), "singapore": (1.3521, 103.8198)}
            lat, lon = client_coords.get(location.lower(), (50.1109, 8.6821))
            return min(available, key=lambda s: s.distance_to(lat, lon))
        
        elif self.strategy == BalanceStrategy.LEAST_LOAD:
            return min(available, key=lambda s: s.current_load)
        
        else:  # ADAPTIVE
            scores = {}
            for s in available:
                score = max(0, 100 - s.avg_latency)/100*30 + (1 - s.current_load)*25
                if location:
                    client_coords = {"russia": (55.7558, 37.6173), "netherlands": (52.3676, 4.9041)}
                    lat, lon = client_coords.get(location.lower(), (50.1109, 8.6821))
                    score += max(0, 1 - s.distance_to(lat, lon)/20000)*20
                if client_id and client_id in self.client_history:
                    hist = self.client_history[client_id]
                    if hist:
                        avg = sum(l for _, l in hist)/len(hist)
                        score += max(0, 100 - avg)/100*15
                score += random.random() * 10
                scores[s.id] = score
            return self.servers[max(scores, key=scores.get)]
    
    def record(self, client_id: str, server_id: str, latency: float):
        if client_id not in self.client_history:
            self.client_history[client_id] = []
        self.client_history[client_id].append((server_id, latency))
        if len(self.client_history[client_id]) > 50:
            self.client_history[client_id] = self.client_history[client_id][-50:]
    
    def get_status(self) -> Dict:
        return {
            "strategy": self.strategy.value,
            "total": len(self.servers),
            "available": sum(1 for s in self.servers.values() if s.is_available),
            "servers": [{"id": s.id, "location": s.location, "latency": s.avg_latency,
                        "load": s.current_load, "connections": s.connections} 
                       for s in self.servers.values()]
        }

# ============================================
# ОСНОВНОЙ СЕРВЕР
# ============================================
class D3VPNServer:
    def __init__(self):
        self.config = config
        self.cert_manager = CertificateManager()
        self.clients: Dict[str, Tuple[asyncio.StreamReader, asyncio.StreamWriter, str]] = {}
        self.ip_pool = self._generate_ip_pool()
        self.routing_table: Dict[str, str] = {}
        self.tunnel = TunnelFactory.create(config.tunnel_mode)
        
        # Балансировка
        self.balancer = None
        if config.balance_enabled:
            self.balancer = LoadBalancer(config.balance_strategy)
            if config.balance_servers:
                for s in config.balance_servers.split(";"):
                    parts = [p.strip() for p in s.split(",")]
                    if len(parts) >= 4:
                        self.balancer.add_server(ServerNode(
                            id=parts[0], host=parts[1], port=int(parts[2]), location=parts[3]
                        ))
            else:
                self.balancer.add_server(ServerNode(
                    id="local", host=config.host, port=config.port, location=config.server_location
                ))
            logger.info(f"Балансировщик: {config.balance_strategy}, серверов: {len(self.balancer.servers)}")
        
        # Каскад
        self.upstream_reader = None
        self.upstream_writer = None
        self.cascade_connected = False
        if config.cascade_mode and config.upstream_server:
            logger.info(f"Каскад: уровень {config.server_level} -> {config.upstream_server}")
    
    def _generate_ip_pool(self):
        network = ipaddress.ip_network(self.config.vpn_subnet)
        return list(network.hosts())[1:]
    
    async def start(self):
        logger.info("D3 Stealth VPN Server v0.0.1")
        logger.info(f"Слушаю: {self.config.host}:{self.config.port}")
        logger.info(f"Туннель: {self.config.tunnel_mode}, Маскировка: {self.config.mask_mode}")
        logger.info(f"Подсеть VPN: {self.config.vpn_subnet}")
        
        if self.balancer:
            logger.info(f"Балансировка: {self.config.balance_strategy}")
        if self.config.cascade_mode:
            logger.info(f"Каскад: уровень {self.config.server_level}")
        
        if self.config.allow_internet:
            await self._setup_nat()
        
        # Запуск API балансировщика
        if self.balancer and config.balance_api_port:
            asyncio.create_task(self._run_balancer_api())
            asyncio.create_task(self._update_metrics_loop())
        
        # Подключение к upstream
        if self.config.cascade_mode and self.config.upstream_server:
            asyncio.create_task(self._connect_upstream())
        
        server = await asyncio.start_server(
            self._handle_client,
            self.config.host,
            self.config.port
        )
        
        async with server:
            await server.serve_forever()
    
    # ============================================
    # ОБРАБОТКА КЛИЕНТОВ
    # ============================================
    async def _handle_client(self, reader, writer):
        client_addr = writer.get_extra_info('peername')
        logger.info(f"Новое соединение: {client_addr}")
        
        try:
            raw = await self.tunnel.receive(reader)
            if not raw:
                logger.warning(f"Пустой запрос от {client_addr}")
                return
            data = await PacketMask.remove(raw, self.config.mask_mode)
            if not data:
                logger.warning(f"Не удалось декодировать данные от {client_addr}")
                return
            
            # Проверка: upstream или клиент?
            if data.startswith(b"UPSTREAM:"):
                await self._handle_upstream(data, reader, writer)
                return
            
            # Аутентификация клиента
            if len(data) < 2:
                logger.warning(f"Слишком короткий запрос от {client_addr}")
                return
            cert_len = struct.unpack(">H", data[:2])[0]
            cert_pem = data[2:2+cert_len]
            valid, client_name = self.cert_manager.verify_certificate(cert_pem)
            if not valid:
                logger.warning(f"Аутентификация отклонена: сертификат невалиден (адрес: {client_name or client_addr})")
                await self._send(writer, b"AUTH_FAILED")
                return
            
            # Проверка подписи
            nonce = data[2+cert_len:2+cert_len+16]
            signature = data[2+cert_len+16:]
            try:
                cert = x509.load_pem_x509_certificate(cert_pem)
                cert.public_key().verify(signature, nonce)
            except Exception as e:
                logger.warning(f"Проверка подписи не пройдена для клиента '{client_name}': {e}")
                await self._send(writer, b"AUTH_FAILED")
                return
            
            logger.info(f"Клиент '{client_name}' прошёл аутентификацию (адрес: {client_addr})")
            
            # Балансировка: выбор сервера
            if self.balancer:
                loc = self._get_location(client_addr[0])
                target = await self.balancer.select(client_name, loc)
                if target and target.id != "local":
                    logger.info(f"Балансировщик: '{client_name}' -> сервер '{target.id}' ({target.host}:{target.port})")
                    await self._send(writer, json.dumps({
                        "type": "redirect",
                        "host": target.host,
                        "port": target.port
                    }).encode())
                    writer.close()
                    return
            
            # Локальная обработка
            await self._handle_local_client(client_name, reader, writer, client_addr)
            
        except Exception as e:
            logger.error(f"Ошибка обработки клиента {client_addr}: {e}")
        finally:
            writer.close()
    
    async def _handle_local_client(self, name: str, reader, writer, addr):
        ip = self._assign_ip(name)
        if not ip:
            logger.error(f"Пул IP исчерпан, клиент '{name}' отклонён")
            await self._send(writer, b"IP_POOL_EXHAUSTED")
            return
        
        self.clients[name] = (reader, writer, ip)
        self.routing_table[ip] = name
        
        if self.balancer:
            for s in self.balancer.servers.values():
                if s.id == "local":
                    s.connections += 1
                    s.current_load = s.connections / s.max_connections
        
        logger.info(f"Клиент '{name}' подключён, выделен IP: {ip} (всего: {len(self.clients)})")
        await self._send_config(writer, ip)
        
        while True:
            raw = await self.tunnel.receive(reader)
            if not raw:
                break
            data = await PacketMask.remove(raw, self.config.mask_mode)
            if data:
                await self._route_packet(data, name)
        
        # Очистка
        if name in self.clients:
            del self.clients[name]
        if ip in self.routing_table:
            del self.routing_table[ip]
        if self.balancer:
            for s in self.balancer.servers.values():
                if s.id == "local":
                    s.connections = max(0, s.connections - 1)
                    s.current_load = s.connections / s.max_connections
        
        logger.info(f"Клиент '{name}' отключён (IP: {ip}, осталось: {len(self.clients)})")
    
    async def _route_packet(self, data: bytes, sender: str):
        try:
            if b"DST:" in data:
                parts = data.split(b"DST:")
                dest_ip = parts[1].split(b":")[0].decode()
                
                if dest_ip in self.routing_table:
                    target = self.routing_table[dest_ip]
                    if target in self.clients:
                        _, writer, _ = self.clients[target]
                        await self._send(writer, data)
                elif self.config.allow_internet:
                    await self._forward_internet(data, sender)
        except:
            pass
    
    async def _forward_internet(self, data: bytes, client_id: str):
        try:
            if b"DST:" not in data:
                return
            parts = data.split(b"DST:")
            dest = parts[1].split(b":")[0].decode()
            dest_ip, dest_port = dest.split(":")
            dest_port = int(dest_port)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            payload = data.split(b"PAYLOAD:")[1] if b"PAYLOAD:" in data else data
            sock.sendto(payload, (dest_ip, dest_port))
            
            response, _ = sock.recvfrom(65535)
            sock.close()
            
            if client_id in self.clients:
                _, writer, _ = self.clients[client_id]
                await self._send(writer, response)
        except Exception as e:
            logger.error(f"NAT ошибка для клиента '{client_id}': {e}")
    
    def _assign_ip(self, name: str) -> Optional[str]:
        if name in self.clients:
            return self.clients[name][2]
        if not self.ip_pool:
            return None
        return str(self.ip_pool.pop(0))
    
    def _get_location(self, ip: str) -> str:
        # Простая эмуляция GeoIP
        import random
        return random.choice(["russia", "netherlands", "germany", "usa"])
    
    async def _send(self, writer, data: bytes):
        masked = await PacketMask.apply(data, self.config.mask_mode)
        await self.tunnel.send(writer, masked)
    
    async def _send_config(self, writer, ip: str):
        network = ipaddress.ip_network(self.config.vpn_subnet)
        cfg = {
            "ip": ip,
            "mask": str(network.netmask),
            "gateway": str(network.network_address + 1),
            "dns": ["8.8.8.8", "1.1.1.1"],
            "level": self.config.server_level
        }
        await self._send(writer, json.dumps(cfg).encode())
    
    # ============================================
    # КАСКАД (UPSTREAM)
    # ============================================
    async def _handle_upstream(self, data: bytes, reader, writer):
        logger.info(f"Upstream подключение (уровень {self.config.server_level})")
        self.upstream_reader = reader
        self.upstream_writer = writer
        self.cascade_connected = True
        await self._send(writer, b"AUTH_SUCCESS")
        
        while True:
            raw = await self.tunnel.receive(reader)
            if not raw:
                logger.warning("Upstream соединение разорвано")
                break
            data = await PacketMask.remove(raw, self.config.mask_mode)
            if data:
                # Проксируем в клиенты
                for cid, (r, w, ip) in self.clients.items():
                    await self._send(w, data)
        
        self.cascade_connected = False
    
    async def _connect_upstream(self):
        while True:
            try:
                host, port = self.config.upstream_server.split(":")
                port = int(port)
                logger.info(f"Подключение к upstream {host}:{port}")
                reader, writer = await asyncio.open_connection(host, port)
                
                # Отправляем UPSTREAM пакет
                await self.tunnel.send(writer, b"UPSTREAM:" + str(self.config.server_level).encode())
                
                # Ждём подтверждение
                raw = await self.tunnel.receive(reader)
                if raw:
                    data = await PacketMask.remove(raw, self.config.mask_mode)
                    if data == b"AUTH_SUCCESS":
                        logger.info(f"Upstream подключён: {host}:{port}")
                        self.upstream_reader = reader
                        self.upstream_writer = writer
                        self.cascade_connected = True
                        
                        # Проксируем трафик от клиентов в upstream
                        while True:
                            for cid, (r, w, ip) in self.clients.items():
                                try:
                                    raw = await asyncio.wait_for(r.read(4096), 0.1)
                                    if raw:
                                        await self.tunnel.send(writer, raw)
                                except:
                                    pass
                            await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Upstream ошибка: {e}")
            await asyncio.sleep(5)
    
    # ============================================
    # API БАЛАНСИРОВЩИКА
    # ============================================
    async def _run_balancer_api(self):
        server = await asyncio.start_server(
            self._handle_api,
            "0.0.0.0",
            config.balance_api_port
        )
        logger.info(f"API балансировщика: порт {config.balance_api_port}")
        async with server:
            await server.serve_forever()
    
    async def _handle_api(self, reader, writer):
        try:
            req = await reader.read(4096)
            path = req.decode().split(" ")[1] if req else "/"
            
            if path == "/status":
                resp = json.dumps(self.balancer.get_status() if self.balancer else {"error": "No balancer"})
            elif "/select" in path:
                params = self._parse_params(path)
                target = await self.balancer.select(params.get("client_id"), params.get("location"))
                resp = json.dumps({"server": {"id": target.id, "host": target.host, "port": target.port}} if target else {"error": "No server"})
            elif "/strategy" in path:
                params = self._parse_params(path)
                strategy = params.get("name")
                if strategy and self.balancer:
                    self.balancer.strategy = BalanceStrategy(strategy)
                    resp = json.dumps({"status": "ok", "strategy": strategy})
                else:
                    resp = json.dumps({"error": "Invalid strategy"})
            else:
                resp = json.dumps({"error": "Not found"})
            
            response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(resp)}\r\n\r\n{resp}"
            writer.write(response.encode())
            await writer.drain()
        except:
            pass
        finally:
            writer.close()
    
    def _parse_params(self, path: str) -> Dict:
        params = {}
        if "?" in path:
            for pair in path.split("?")[1].split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v
        return params
    
    async def _update_metrics_loop(self):
        while True:
            if self.balancer:
                await asyncio.sleep(5)
                for s in self.balancer.servers.values():
                    s.avg_latency = s.avg_latency * 0.9 + random.uniform(1, 10) * 0.1
                    if s.connections > 0:
                        s.current_load = min(1, s.connections / s.max_connections)
                    else:
                        s.current_load *= 0.95
    
    # ============================================
    # NAT
    # ============================================
    async def _setup_nat(self):
        try:
            subprocess.run(["sysctl", "-w", "net.ipv4.ip_forward=1"], check=False)
            subprocess.run([
                "iptables", "-t", "nat", "-A", "POSTROUTING",
                "-s", self.config.vpn_subnet, "-o", "eth0",
                "-j", "MASQUERADE"
            ], check=False)
            logger.info("NAT настроен")
        except Exception:
            logger.warning("NAT не настроен (нужны права root)")

# ============================================
# ЗАПУСК
# ============================================
async def main():
    parser = argparse.ArgumentParser(description="D3 Stealth VPN Server v0.0.1")
    parser.add_argument("--debug", action="store_true", help="Включить отладочный вывод")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    server = D3VPNServer()
    await server.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Сервер остановлен")
