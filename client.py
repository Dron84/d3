#!/usr/bin/env python3
"""
D3 Stealth VPN Client v0.0.1
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
import logging
from typing import Optional, Dict
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.backends import default_backend
except Exception:
    print("[ERROR] Установите: pip install cryptography")
    sys.exit(1)

# ============================================
# ЛОГИРОВАНИЕ
# ============================================
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("D3Client")

# ============================================
# КОНФИГУРАЦИЯ
# ============================================
class ClientConfig:
    def __init__(self, env_file: Optional[str] = None):
        self._load_env(env_file)
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

    def _load_env(self, env_file: Optional[str] = None):
        if load_dotenv is None:
            if env_file:
                logger.warning("python-dotenv не установлен. Файл .env не будет загружен. pip install python-dotenv")
            return

        if env_file:
            path = Path(env_file)
            if path.exists():
                load_dotenv(path, override=False)
                logger.info(f"Загружен .env файл: {path.resolve()}")
            else:
                logger.warning(f"Файл .env не найден: {path.resolve()}. Используются значения по умолчанию.")
        else:
            # Автопоиск: .env.client, .env
            candidates = [Path(".env.client"), Path(".env")]
            for candidate in candidates:
                if candidate.exists():
                    load_dotenv(candidate, override=False)
                    logger.info(f"Загружен .env файл: {candidate.resolve()}")
                    return
            logger.info("Файл .env не найден. Используются значения по умолчанию.")

config: Optional[ClientConfig] = None

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
            max_fragment = 16384
            result = b""
            for i in range(0, len(data), max_fragment):
                chunk = data[i:i+max_fragment]
                tls_header = b"\x16\x03\x03" + struct.pack(">H", len(chunk) + 5)
                tls_record = b"\x17\x03\x03" + struct.pack(">H", len(chunk)) + chunk
                result += tls_header + tls_record
            return result
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
            logger.debug(f"Mask.remove https: len={len(data)}, first10: {data[:10]!r}")
            result = b""
            offset = 0
            while offset < len(data):
                if offset + 5 > len(data):
                    logger.warning(f"Mask.remove: неполный заголовок TLS at offset {offset}")
                    break
                if data[offset:offset+3] != b"\x16\x03\x03":
                    logger.warning(f"Mask.remove: неожиданный тип записи: {data[offset:offset+3]!r} at offset {offset}")
                    break
                if offset + 5 > len(data):
                    break
                record_type = data[offset+5]
                if record_type != 0x17:  # application data
                    logger.warning(f"Mask.remove: не application data: {record_type:#x} at offset {offset}")
                    break
                if offset + 10 > len(data):
                    break
                payload_len = struct.unpack(">H", data[offset+8:offset+10])[0]
                if offset + 10 + payload_len > len(data):
                    logger.warning(f"Mask.remove: неполные данные: need {payload_len}, have {len(data) - offset - 10}")
                    break
                result += data[offset+10:offset+10+payload_len]
                offset += 10 + payload_len
            return result if result else None
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
        logger.debug(f"Tunnel send {len(data)} bytes")
        frame = b"ICMP:" + struct.pack(">I", len(data)) + data
        writer.write(frame)
        await writer.drain()
    async def receive(self, reader) -> Optional[bytes]:
        header = await reader.readexactly(5)
        if not header or header[:4] != b"ICMP":
            logger.warning(f"Tunnel: неверный префикс: {header!r}")
            return None
        length_bytes = await reader.readexactly(4)
        length = struct.unpack(">I", length_bytes)[0]
        data = await reader.readexactly(length)
        return data

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
        # Проверяем сертификат
        if config.cert_path.exists():
            try:
                with open(config.cert_path, "rb") as f:
                    self.certificate = x509.load_pem_x509_certificate(f.read())
                logger.info(f"Сертификат загружен: {config.cert_path}")
            except Exception as e:
                logger.error(f"Ошибка чтения сертификата {config.cert_path}: {e}")
                logger.error("Перегенерируйте сертификат: python d3_ca.py issue " + config.client_name)
                sys.exit(1)
        else:
            logger.error(f"Сертификат не найден: {config.cert_path}")
            logger.error(f"Создайте его: python d3_ca.py issue {config.client_name}")
            sys.exit(1)

        # Проверяем приватный ключ
        if config.private_path.exists():
            # Пытаемся загрузить без пароля, затем из env
            pwd = os.getenv("CLIENT_KEY_PASSWORD", "")
            try:
                with open(config.private_path, "rb") as f:
                    self.private_key = serialization.load_pem_private_key(f.read(), password=pwd.encode() if pwd else None)
                logger.info(f"Приватный ключ загружен: {config.private_path}")
            except Exception as e:
                error_str = str(e).lower()
                if "password" in error_str or "bad decrypt" in error_str or "invalid" in error_str:
                    logger.error("Неверный пароль от приватного ключа. Установите CLIENT_KEY_PASSWORD в .env или используйте ключ без пароля.")
                else:
                    logger.error(f"Ошибка чтения приватного ключа: {e}")
                logger.error("Убедитесь, что пароль корректен и файл не повреждён.")
                sys.exit(1)
        else:
            logger.error(f"Приватный ключ не найден: {config.private_path}")
            logger.error(f"Создайте его: python d3_ca.py issue {config.client_name}")
            sys.exit(1)

        # Проверяем, что ключ и сертификат совпадают
        try:
            cert_pub = self.certificate.public_key()
            # Проверяем что тип ключа совпадает
            if type(cert_pub) != type(self.private_key.public_key()):
                logger.error("Несовпадение типа ключа: сертификат и приватный ключ используют разные алгоритмы.")
                logger.error("Перегенерируйте сертификат: python d3_ca.py issue " + config.client_name)
                sys.exit(1)
        except Exception as e:
            logger.warning(f"Не удалось проверить совпадение ключей: {e}")
    
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
        logger.info(f"SOCKS5 прокси запущен: {self.host}:{self.port}")
        self.server = await asyncio.start_server(self._handle, self.host, self.port)
        async with self.server:
            await self.server.serve_forever()
    
    async def _handle(self, reader, writer):
        client_addr = writer.get_extra_info('peername')
        logger.debug(f"SOCKS5 новое соединение: {client_addr}")
        try:
            header = await reader.read(2)
            if len(header) < 2 or header[0] != 0x05:
                logger.warning(f"SOCKS5 неверное рукопожатие: {header!r}")
                writer.close()
                return
            
            nmethods = header[1]
            methods = await reader.read(nmethods)
            logger.debug(f"SOCKS5 handshake: ver=0x05 nmethods={nmethods} methods={methods!r}")
            
            writer.write(b"\x05\x00")
            await writer.drain()
            logger.debug("SOCKS5 handshake ответ отправлен")
            
            req = await reader.read(4)
            logger.debug(f"SOCKS5 request raw: {req!r} ({len(req)} bytes)")
            if len(req) < 4:
                logger.warning(f"SOCKS5 короткий запрос: {req!r}")
                writer.close()
                return
            
            ver, cmd, rsv, atyp = req[0], req[1], req[2], req[3]
            logger.debug(f"SOCKS5: ver={ver:#x} cmd={cmd:#x} rsv={rsv:#x} atyp={atyp:#x}")
            
            if atyp == 0x01:
                addr_data = await reader.read(4)
                port_data = await reader.read(2)
                target_ip = socket.inet_ntoa(addr_data)
                target_port = struct.unpack("!H", port_data)[0]
            elif atyp == 0x03:
                domain_len_data = await reader.read(1)
                domain = (await reader.read(domain_len_data[0])).decode()
                port_data = await reader.read(2)
                target_ip = domain
                target_port = struct.unpack("!H", port_data)[0]
            elif atyp == 0x04:
                addr_data = await reader.read(16)
                port_data = await reader.read(2)
                target_ip = socket.inet_ntop(socket.AF_INET6, addr_data)
                target_port = struct.unpack("!H", port_data)[0]
            else:
                logger.warning(f"SOCKS5 неизвестный atyp: {atyp}")
                writer.close()
                return
            
            logger.info(f"SOCKS5 запрос: {client_addr} -> {target_ip}:{target_port}")
            
            self.d3_client._request_id += 1
            conn_id = self.d3_client._request_id
            
            response = await self.d3_client._send_and_wait(target_ip, target_port, b"", conn_id, timeout=5)
            if response is None:
                logger.warning(f"SOCKS5 таймаут: {target_ip}:{target_port}")
                fail_resp = struct.pack("!BBBB", 0x05, 0x05, 0x00, 0x01) + socket.inet_aton("0.0.0.0") + struct.pack("!H", 0)
                writer.write(fail_resp)
                await writer.drain()
                writer.close()
                return
            
            bind_addr = socket.inet_aton("0.0.0.0")
            bind_port = struct.pack("!H", 0)
            resp = struct.pack("!BBBB", 0x05, 0x00, 0x00, 0x01) + bind_addr + bind_port
            writer.write(resp)
            await writer.drain()
            
            logger.info(f"SOCKS5 подключено: {target_ip}:{target_port}")
            
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                response = await self.d3_client._send_and_wait(target_ip, target_port, data, conn_id, timeout=5)
                if response is None:
                    break
                writer.write(response)
                await writer.drain()
                
        except Exception as e:
            logger.error(f"SOCKS5 ошибка ({client_addr}): {e}", exc_info=True)
        finally:
            writer.close()
            logger.debug(f"SOCKS5 соединение закрыто: {client_addr}")

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
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self._request_id = 0
    
    async def connect(self):
        logger.info(f"Подключение к {self.config.server_host}:{self.config.server_port}")
        logger.info(f"Маскировка: {self.config.mask_mode}, Туннель: {self.config.tunnel_mode}")
        
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.config.server_host, self.config.server_port
            )
            logger.info(f"TCP соединение установлено с {self.config.server_host}:{self.config.server_port}")
            
            cert_pem = self.cert.get_cert_pem()
            nonce = os.urandom(16)
            signature = self.cert.sign(nonce)
            auth = struct.pack(">H", len(cert_pem)) + cert_pem + nonce + signature
            logger.debug(f"Auth пакет: cert_len={len(cert_pem)}, total={len(auth)}")
            
            masked = await PacketMask.apply(auth, self.config.mask_mode)
            logger.debug(f"Отправка через туннель: {len(masked)} bytes, first10: {masked[:10]!r}")
            await self.tunnel.send(self.writer, masked)
            
            raw = await self.tunnel.receive(self.reader)
            if raw:
                data = await PacketMask.remove(raw, self.config.mask_mode)
                if data:
                    if data.startswith(b"AUTH_FAILED"):
                        logger.error("Аутентификация отклонена сервером.")
                        logger.error("Возможные причины:")
                        logger.error("  - Сертификат клиента не подписан CA сервера")
                        logger.error("  - Сертификат просрочен")
                        logger.error("  - Неверная подпись")
                        logger.error(f"  - Проверьте что сертификат для '{self.config.client_name}' выпущен тем же CA")
                        self.writer.close()
                        return

                    try:
                        msg = json.loads(data.decode())
                        if msg.get("type") == "redirect":
                            host, port = msg.get("host"), msg.get("port")
                            logger.info(f"Сервер перенаправляет на {host}:{port}")
                            self.config.server_host = host
                            self.config.server_port = port
                            self.writer.close()
                            await asyncio.sleep(1)
                            await self.connect()
                            return
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
                    
                    try:
                        cfg = json.loads(data.decode())
                        self.vpn_ip = cfg.get("ip")
                        logger.info(f"Подключён! VPN IP: {self.vpn_ip}")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        logger.warning("Получен неизвестный ответ от сервера")
            
            if config.socks_enabled:
                asyncio.create_task(self.socks5.start())
            
            self.is_running = True
            logger.info("Клиент запущ, ожидание данных...")
            await self._receive_loop()
            
        except ConnectionRefusedError:
            logger.error(f"Соединение отклонено: {self.config.server_host}:{self.config.server_port}")
            logger.error("Убедитесь, что сервер запущен и доступен.")
        except ConnectionError as e:
            logger.error(f"Ошибка соединения: {e}")
        except OSError as e:
            logger.error(f"Сетевая ошибка: {e}")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка: {e}")
    
    async def _receive_loop(self):
        try:
            while self.is_running:
                raw = await self.tunnel.receive(self.reader)
                if not raw:
                    logger.warning("Соединение с сервером разорвано")
                    break
                data = await PacketMask.remove(raw, self.config.mask_mode)
                if not data:
                    continue

                logger.debug(f"recv_loop: {len(data)} bytes, first20: {data[:20]!r}")

                if data.startswith(b"DST:"):
                    rest = data.split(b"DST:", 1)[1]
                    parts = rest.split(b":PAYLOAD:", 1)
                    meta = parts[0].decode()
                    meta_parts = meta.split(":")
                    if len(meta_parts) >= 3:
                        req_id = meta_parts[2]
                        if req_id in self.pending_requests:
                            fut = self.pending_requests.pop(req_id)
                            if not fut.done():
                                payload = parts[1] if len(parts) > 1 else b""
                                fut.set_result(payload)
                                continue
                    logger.debug(f"recv_loop: нет pending для id={req_id if len(meta_parts) >= 3 else '?'}")

                await self.msg_queue.put(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Ошибка приёма данных: {e}")
        finally:
            self.is_running = False
    
    async def _send_data(self, data: bytes):
        masked = await PacketMask.apply(data, self.config.mask_mode)
        await self.tunnel.send(self.writer, masked)
    
    async def _send_and_wait(self, dst_ip: str, dst_port: int, payload: bytes, conn_id: int, timeout: float = 5.0) -> Optional[bytes]:
        key = str(conn_id)
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self.pending_requests[key] = fut
        try:
            logger.debug(f"send_and_wait #{conn_id}: DST:{dst_ip}:{dst_port} ({len(payload)} bytes)")
            await self._send_data(f"DST:{dst_ip}:{dst_port}:{conn_id}:PAYLOAD:".encode() + payload)
            result = await asyncio.wait_for(fut, timeout)
            logger.debug(f"send_and_wait #{conn_id}: ответ ({len(result)} bytes)")
            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(key, None)
            logger.warning(f"conn #{conn_id} таймаут: {dst_ip}:{dst_port}")
            return None
    
    async def send_request(self, dst_ip: str, dst_port: int, payload: bytes, timeout: float = 5.0) -> Optional[bytes]:
        self._request_id += 1
        req_id = self._request_id
        key = str(req_id)
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self.pending_requests[key] = fut
        try:
            logger.debug(f"send_request #{req_id}: DST:{dst_ip}:{dst_port}:PAYLOAD: ({len(payload)} bytes)")
            await self._send_data(f"DST:{dst_ip}:{dst_port}:{req_id}:PAYLOAD:".encode() + payload)
            result = await asyncio.wait_for(fut, timeout)
            logger.debug(f"send_request #{req_id}: ответ получен ({len(result)} bytes)")
            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(key, None)
            logger.warning(f"Запрос #{req_id} таймаут: {dst_ip}:{dst_port}")
            return None
    
    async def _receive_data(self, timeout: float = 5.0) -> Optional[bytes]:
        try:
            return await asyncio.wait_for(self.msg_queue.get(), timeout)
        except asyncio.TimeoutError:
            return None

# ============================================
# ЗАПУСК
# ============================================
async def main():
    parser = argparse.ArgumentParser(description="D3 Stealth VPN Client v0.0.1")
    parser.add_argument("--env", default=None, help="Путь к .env файлу конфигурации (по умолчанию: .env.client)")
    parser.add_argument("--server", default=None, help="IP/домен сервера")
    parser.add_argument("--port", type=int, default=None, help="Порт сервера")
    parser.add_argument("--name", default=None, help="Имя клиента")
    parser.add_argument("--socks-port", type=int, default=None, help="Порт SOCKS5 прокси")
    parser.add_argument("--no-socks", action="store_true", help="Отключить SOCKS5 прокси")
    parser.add_argument("--mask", default=None, help="Режим маскировки (http/https/traffic)")
    parser.add_argument("--tunnel", default=None, help="Режим туннеля (icmp/dns/raw)")
    parser.add_argument("--debug", action="store_true", help="Включить отладочный вывод")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    global config
    config = ClientConfig(env_file=args.env)

    # Параметры командной строки перезаписывают .env
    if args.server is not None:
        config.server_host = args.server
    if args.port is not None:
        config.server_port = args.port
    if args.name is not None:
        config.client_name = args.name
        config.cert_dir = Path("certs/clients") / config.client_name
        config.cert_path = config.cert_dir / "client_cert.pem"
        config.private_path = config.cert_dir / "client_private.pem"
        config.ca_cert_path = config.cert_dir / "ca_cert.pem"
    if args.socks_port is not None:
        config.socks_port = args.socks_port
    if args.mask is not None:
        config.mask_mode = args.mask
    if args.tunnel is not None:
        config.tunnel_mode = args.tunnel
    if args.no_socks:
        config.socks_enabled = False

    logger.info(f"D3 Stealth VPN Client v0.0.1")
    logger.info(f"Сервер: {config.server_host}:{config.server_port}")
    logger.info(f"Клиент: {config.client_name}")

    client = D3VPNClient()
    await client.connect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Выход")
