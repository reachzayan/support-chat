"""RFC 8291 aes128gcm payloads and RFC 8292 VAPID using installed crypto primitives."""

import base64
import json
import os
import struct
import time
from urllib.parse import urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.settings import Settings


def encode_key(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def decode_key(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def trusted_endpoint(value: str) -> str:
    url = urlsplit(value)
    host = url.hostname or ""
    trusted = host == "fcm.googleapis.com" or any(
        host == suffix or host.endswith("." + suffix)
        for suffix in ("push.services.mozilla.com", "push.apple.com", "notify.windows.com")
    )
    if (
        not trusted
        or url.scheme != "https"
        or url.port not in (None, 443)
        or url.username
        or url.password
        or url.fragment
    ):
        raise ValueError("Unsupported push service endpoint")
    return value


def vapid_key(settings: Settings) -> ec.EllipticCurvePrivateKey | None:
    raw = settings.push_vapid_private_key.get_secret_value()
    if not raw:
        return None
    key = decode_key(raw)
    if len(key) != 32:
        raise ValueError("VAPID key must be a 32-byte P-256 private key")
    return ec.derive_private_key(int.from_bytes(key), ec.SECP256R1())


def public_key(settings: Settings) -> str | None:
    key = vapid_key(settings)
    return (
        encode_key(key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint))
        if key
        else None
    )


def encrypt_payload(payload: bytes, p256dh: str, auth: str) -> bytes:
    # One final record (0x02 delimiter); record size includes the AES-GCM authentication tag.
    if len(payload) > 3993:
        raise ValueError("Push payload is too large")
    receiver_bytes = decode_key(p256dh)
    receiver = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), receiver_bytes)
    ephemeral = ec.generate_private_key(ec.SECP256R1())
    sender_bytes = ephemeral.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )
    shared = ephemeral.exchange(ec.ECDH(), receiver)
    ikm = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=decode_key(auth),
        info=b"WebPush: info\x00" + receiver_bytes + sender_bytes,
    ).derive(shared)
    salt = os.urandom(16)
    cek = HKDF(
        algorithm=hashes.SHA256(), length=16, salt=salt, info=b"Content-Encoding: aes128gcm\x00"
    ).derive(ikm)
    nonce = HKDF(
        algorithm=hashes.SHA256(), length=12, salt=salt, info=b"Content-Encoding: nonce\x00"
    ).derive(ikm)
    header = salt + struct.pack("!I", 4096) + bytes([len(sender_bytes)]) + sender_bytes
    return header + AESGCM(cek).encrypt(nonce, payload + b"\x02", None)


class WebPushSender:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings, self.client = settings, client

    async def send(self, device, payload: dict) -> int:
        endpoint = trusted_endpoint(device.endpoint)
        origin = urlsplit(endpoint)
        key = vapid_key(self.settings)
        if key is None:
            raise ValueError("Push is not configured")
        token = jwt.encode(
            {
                "aud": f"https://{origin.hostname}",
                "exp": int(time.time()) + 12 * 3600,
                "sub": self.settings.push_vapid_subject,
            },
            key,
            algorithm="ES256",
        )
        encrypted = encrypt_payload(
            json.dumps(payload, separators=(",", ":")).encode(), device.p256dh, device.auth
        )
        response = await self.client.post(
            endpoint,
            content=encrypted,
            headers={
                "Authorization": f"vapid t={token}, k={public_key(self.settings)}",
                "Content-Encoding": "aes128gcm",
                "Content-Type": "application/octet-stream",
                "TTL": "300",
                "Urgency": "normal",
            },
        )
        return response.status_code
