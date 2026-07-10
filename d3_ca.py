#!/usr/bin/env python3
"""
D3 Certificate Authority CLI
Управление сертификатами через командную строку
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import argparse
import datetime
import getpass
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("❌ Установите cryptography: pip install cryptography")
    sys.exit(1)


class D3CA:
    def __init__(self, ca_dir="certs/ca"):
        self.ca_dir = Path(ca_dir)
        self.ca_dir.mkdir(parents=True, exist_ok=True)
        self.ca_private_key_path = self.ca_dir / "ca_private.pem"
        self.ca_cert_path = self.ca_dir / "ca_cert.pem"
        
        if self.ca_cert_path.exists():
            self._load_ca()
        else:
            self._create_ca()
    
    def _load_ca(self):
        with open(self.ca_private_key_path, "rb") as f:
            self.ca_private_key = serialization.load_pem_private_key(f.read(), password=None)
        with open(self.ca_cert_path, "rb") as f:
            self.ca_cert = x509.load_pem_x509_certificate(f.read())
        print(f"✅ CA загружен")
    
    def _create_ca(self):
        print("🔐 Создание нового корневого CA...")
        self.ca_private_key = Ed25519PrivateKey.generate()
        ca_public_key = self.ca_private_key.public_key()
        
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "RU"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "D3 VPN"),
            x509.NameAttribute(NameOID.COMMON_NAME, "D3 Root CA"),
        ])
        
        self.ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(ca_public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365*10))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(self.ca_private_key, None)
        )
        
        with open(self.ca_private_key_path, "wb") as f:
            f.write(self.ca_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        with open(self.ca_cert_path, "wb") as f:
            f.write(self.ca_cert.public_bytes(serialization.Encoding.PEM))
        
        print(f"✅ CA создан")
    
    def issue_certificate(self, client_name: str, validity_days: int = 365):
        print(f"📜 Выпуск сертификата для {client_name}...")
        
        client_private_key = Ed25519PrivateKey.generate()
        client_public_key = client_private_key.public_key()
        
        client_dir = Path("certs/clients") / client_name
        client_dir.mkdir(parents=True, exist_ok=True)
        
        client_private_path = client_dir / "client_private.pem"
        password = getpass.getpass(f"🔑 Введите пароль для клиента {client_name}: ")
        with open(client_private_path, "wb") as f:
            f.write(client_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.BestAvailableEncryption(password.encode())
            ))
        
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "RU"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "D3 VPN"),
            x509.NameAttribute(NameOID.COMMON_NAME, client_name),
        ])
        
        client_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self.ca_cert.subject)
            .public_key(client_public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=validity_days))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(self.ca_private_key, None)
        )
        
        with open(client_dir / "client_cert.pem", "wb") as f:
            f.write(client_cert.public_bytes(serialization.Encoding.PEM))
        
        with open(client_dir / "ca_cert.pem", "wb") as f:
            f.write(self.ca_cert.public_bytes(serialization.Encoding.PEM))
        
        print(f"✅ Сертификат для {client_name} создан в {client_dir}")
    
    def list_certificates(self):
        clients_dir = Path("certs/clients")
        if not clients_dir.exists():
            print("❌ Нет выпущенных сертификатов")
            return
        
        print("\n📋 Выпущенные сертификаты:")
        print("-" * 50)
        for client_dir in clients_dir.iterdir():
            if client_dir.is_dir():
                cert_path = client_dir / "client_cert.pem"
                if cert_path.exists():
                    try:
                        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
                        days_left = (cert.not_valid_after - datetime.datetime.utcnow()).days
                        status = "✅ Активен" if days_left > 0 else "❌ Истёк"
                        print(f"   {client_dir.name}: {status} ({days_left} дней)")
                    except:
                        print(f"   {client_dir.name}: ⚠️ Ошибка чтения")
    
    def revoke_certificate(self, client_name: str):
        revoked_file = self.ca_dir / "revoked.txt"
        with open(revoked_file, "a") as f:
            f.write(f"{client_name} - {datetime.datetime.utcnow().isoformat()}\n")
        print(f"🚫 Сертификат {client_name} отозван")


def main():
    parser = argparse.ArgumentParser(description="D3 Certificate Authority")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    p_issue = subparsers.add_parser("issue", help="Выпустить сертификат")
    p_issue.add_argument("client", help="Имя клиента")
    p_issue.add_argument("--days", type=int, default=365, help="Срок действия (дней)")
    
    p_revoke = subparsers.add_parser("revoke", help="Отозвать сертификат")
    p_revoke.add_argument("client", help="Имя клиента")
    
    p_list = subparsers.add_parser("list", help="Список сертификатов")
    
    p_renew = subparsers.add_parser("renew", help="Обновить сертификат")
    p_renew.add_argument("client", help="Имя клиента")
    p_renew.add_argument("--days", type=int, default=365, help="Срок действия (дней)")
    
    p_init = subparsers.add_parser("init", help="Инициализировать CA")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    ca = D3CA()
    
    if args.command == "init":
        print("✅ CA уже инициализирован")
    elif args.command == "issue":
        ca.issue_certificate(args.client, args.days)
    elif args.command == "revoke":
        ca.revoke_certificate(args.client)
    elif args.command == "list":
        ca.list_certificates()
    elif args.command == "renew":
        ca.issue_certificate(args.client, args.days)


if __name__ == "__main__":
    main()
