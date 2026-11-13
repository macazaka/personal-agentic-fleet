"""
Local Loopback TLS Certificate Authority & Dual-Stack HTTPS Engine for AFCC.
Generates a local Root CA (`afcc_root_ca.crt`) and a 365-day SAN leaf server certificate
(`localhost.crt` covering `127.0.0.1`, `localhost`, and `::1`), installs the Root CA into
the Windows CurrentUser Trust Store (`Cert:\\CurrentUser\\Root`), and builds an `ssl.SSLContext`
for `https://127.0.0.1:7890`.

All certificate and key files are stored exclusively in gitignored `fleet/data/certs/`.
"""

from __future__ import annotations

import datetime
import ipaddress
import logging
import os
import ssl
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from fleet.config import DATA_DIR

tls_logger = logging.getLogger("fleet.local_tls")

CERTS_DIR = DATA_DIR / "certs"
ROOT_CA_CERT_PATH = CERTS_DIR / "afcc_root_ca.crt"
ROOT_CA_KEY_PATH = CERTS_DIR / "afcc_root_ca.key"
SERVER_CERT_PATH = CERTS_DIR / "localhost.crt"
SERVER_FULLCHAIN_PATH = CERTS_DIR / "localhost_fullchain.crt"
SERVER_KEY_PATH = CERTS_DIR / "localhost.key"


def ensure_local_tls_certificates(force_regenerate: bool = False) -> Dict[str, Any]:
    """
    Ensures a valid Root CA and a 365-day leaf TLS certificate with SANs
    (IP:127.0.0.1, DNS:localhost, IP:::1) exist in `fleet/data/certs/`.
    """
    CERTS_DIR.mkdir(parents=True, exist_ok=True)

    if (
        not force_regenerate
        and ROOT_CA_CERT_PATH.exists()
        and SERVER_FULLCHAIN_PATH.exists()
        and SERVER_KEY_PATH.exists()
    ):
        return {
            "status": "existing",
            "ca_cert": str(ROOT_CA_CERT_PATH),
            "server_cert": str(SERVER_FULLCHAIN_PATH),
            "server_key": str(SERVER_KEY_PATH),
        }

    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    except ImportError as exc:
        tls_logger.warning("cryptography package unavailable for local TLS generation: %s", exc)
        return {"status": "error", "message": f"cryptography unavailable: {exc}"}

    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Generate Root CA key & certificate (10-year validity, CA:TRUE)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Personal Agentic Fleet"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "AFCC Local Security Authority"),
        x509.NameAttribute(NameOID.COMMON_NAME, "AFCC Local Root CA"),
    ])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    # 2. Generate Leaf Server key & certificate (365 days <= Chrome 398-day limit, CA:FALSE, SANs)
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Personal Agentic Fleet"),
        x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1"),
    ])
    san = x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address("::1")),
    ])
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_subject)
        .issuer_name(ca_subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .add_extension(san, critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    ca_cert_bytes = ca_cert.public_bytes(serialization.Encoding.PEM)
    ca_key_bytes = ca_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    srv_cert_bytes = server_cert.public_bytes(serialization.Encoding.PEM)
    srv_key_bytes = server_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    ROOT_CA_CERT_PATH.write_bytes(ca_cert_bytes)
    ROOT_CA_KEY_PATH.write_bytes(ca_key_bytes)
    SERVER_CERT_PATH.write_bytes(srv_cert_bytes)
    SERVER_FULLCHAIN_PATH.write_bytes(srv_cert_bytes + b"\n" + ca_cert_bytes)
    SERVER_KEY_PATH.write_bytes(srv_key_bytes)

    return {
        "status": "generated",
        "ca_cert": str(ROOT_CA_CERT_PATH),
        "server_cert": str(SERVER_FULLCHAIN_PATH),
        "server_key": str(SERVER_KEY_PATH),
    }


def install_root_ca_to_windows_user_store() -> Dict[str, Any]:
    """
    Installs `afcc_root_ca.crt` into the Windows CurrentUser Trusted Root Certification Authorities store
    (`Cert:\\CurrentUser\\Root`) so Chrome/Edge trust `https://127.0.0.1:7890` and `https://localhost:7890`.
    """
    cert_res = ensure_local_tls_certificates()
    if not ROOT_CA_CERT_PATH.exists():
        return {"status": "error", "message": "Root CA certificate not found", "details": cert_res}

    if sys.platform != "win32":
        return {"status": "skipped", "message": "Non-Windows platform", "ca_cert": str(ROOT_CA_CERT_PATH)}

    try:
        import shutil
        import tempfile
        tmp_dir = Path(tempfile.gettempdir())
        tmp_cert = tmp_dir / "afcc_root_ca.crt"
        try:
            shutil.copyfile(ROOT_CA_CERT_PATH, tmp_cert)
        except Exception:
            tmp_cert = ROOT_CA_CERT_PATH

        proc = subprocess.run(
            ["certutil", "-user", "-addstore", "Root", str(tmp_cert)],
            cwd=str(tmp_dir),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode == 0:
            return {
                "status": "installed",
                "store": "Cert:\\CurrentUser\\Root",
                "ca_cert": str(ROOT_CA_CERT_PATH),
                "output": (proc.stdout or "").strip(),
            }
        return {
            "status": "warning",
            "returncode": proc.returncode,
            "ca_cert": str(ROOT_CA_CERT_PATH),
            "output": (proc.stdout or proc.stderr or "").strip(),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc), "ca_cert": str(ROOT_CA_CERT_PATH)}


def build_local_ssl_context() -> Optional[ssl.SSLContext]:
    """
    Returns a configured `ssl.SSLContext` for `https://127.0.0.1:7890` if local TLS certificates exist.
    """
    try:
        ensure_local_tls_certificates()
        if not SERVER_FULLCHAIN_PATH.exists() or not SERVER_KEY_PATH.exists():
            return None
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(certfile=str(SERVER_FULLCHAIN_PATH), keyfile=str(SERVER_KEY_PATH))
        return ctx
    except Exception as exc:
        tls_logger.warning("Could not initialize local SSLContext: %s", exc)
        return None
