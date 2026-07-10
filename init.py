"""Quick setup - generates CA and client1 cert with empty password"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
sys.path.insert(0, os.path.dirname(__file__))

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pathlib import Path
import datetime

ca_dir = Path("certs/ca")
clients_dir = Path("certs/clients/client1")
ca_dir.mkdir(parents=True, exist_ok=True)
clients_dir.mkdir(parents=True, exist_ok=True)

# Create CA
print("[1/2] Creating CA...")
ca_key = Ed25519PrivateKey.generate()
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, "RU"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "D3 VPN"),
    x509.NameAttribute(NameOID.COMMON_NAME, "D3 Root CA"),
])
ca_cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(ca_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.now(datetime.UTC))
    .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365*10))
    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    .sign(ca_key, None)
)

(ca_dir / "ca_private.pem").write_bytes(ca_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
))
(ca_dir / "ca_cert.pem").write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
print("  CA created")

# Create client cert
print("[2/2] Creating client1 cert...")
client_key = Ed25519PrivateKey.generate()
client_subject = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, "RU"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "D3 VPN"),
    x509.NameAttribute(NameOID.COMMON_NAME, "client1"),
])
client_cert = (
    x509.CertificateBuilder()
    .subject_name(client_subject)
    .issuer_name(ca_cert.subject)
    .public_key(client_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.now(datetime.UTC))
    .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365))
    .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
    .sign(ca_key, None)
)

(clients_dir / "client_private.pem").write_bytes(client_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
))
(clients_dir / "client_cert.pem").write_bytes(client_cert.public_bytes(serialization.Encoding.PEM))
(ca_dir / "ca_cert.pem").copy(clients_dir / "ca_cert.pem")
print("  Client1 cert created")
print("\nDone! Files:")
for f in sorted(Path("certs").rglob("*.pem")):
    print(f"  {f}")
