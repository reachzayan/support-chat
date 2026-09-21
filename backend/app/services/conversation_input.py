"""Normalize visitor input and issue opaque resume identity; no I/O or state changes."""

from base64 import urlsafe_b64encode
from hashlib import sha256
from ipaddress import ip_address
from json import dumps
from secrets import token_bytes

from app.models.conversation import INQUIRY_TYPES
from app.services.conversation_types import CommandError

MAX_MESSAGE = 4000
MAX_NAME = 120
MAX_EMAIL = 320
MAX_PHONE = 40
MAX_UA = 512


def hash_resume_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def prechat_payload_hash(
    name: str,
    email: str,
    phone: str,
    inquiry_type: str,
    message: str,
) -> str:
    payload = {
        "email": email,
        "inquiry_type": inquiry_type,
        "message": message,
        "name": name,
        "phone": phone,
    }
    return sha256(dumps(payload, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def peer_ip(host: str | None) -> str | None:
    if not host:
        return None
    try:
        return str(ip_address(host))
    except ValueError:
        return None


def cap_user_agent(raw: str | None) -> str | None:
    if raw is None:
        return None
    trimmed = raw.strip()
    if not trimmed:
        return None
    return trimmed[:MAX_UA]


def welcome_line(site_name: str, page_title: str | None) -> str:
    raw = (page_title or "").strip()
    title = raw.split("|", 1)[0].strip() if raw else ""
    brand = title or site_name
    return f"Hi, welcome to {brand}. How can we help you today?"


def normalize_prechat(
    name: str, email: str, phone: str, inquiry_type: str, message: str
) -> dict[str, str]:
    clean_name = name.strip()
    clean_email = email.strip().lower()
    clean_phone = phone.strip()
    clean_message = message.strip()
    inquiry = inquiry_type.strip() if inquiry_type else "other"
    if not clean_name or not clean_email:
        raise CommandError("invalid")
    if len(clean_name) > MAX_NAME or len(clean_email) > MAX_EMAIL or len(clean_phone) > MAX_PHONE:
        raise CommandError("oversize")
    if len(clean_message) > MAX_MESSAGE:
        raise CommandError("oversize")
    if inquiry not in INQUIRY_TYPES:
        raise CommandError("invalid")
    if "@" not in clean_email or " " in clean_email:
        raise CommandError("invalid")
    return {
        "name": clean_name,
        "email": clean_email,
        "phone": clean_phone,
        "inquiry_type": inquiry,
        "message": clean_message,
    }


def require_message_body(body: str) -> str:
    text = body.strip()
    if not text:
        raise CommandError("invalid")
    if len(text) > MAX_MESSAGE:
        raise CommandError("oversize")
    return text


def issue_resume_token() -> tuple[str, str]:
    raw = token_bytes(32)
    token = urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return token, hash_resume_token(token)


def masked_name(name: str | None) -> str:
    parts = [part for part in (name or "").strip().split() if part]
    if not parts:
        return "Returning visitor"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


def masked_email(email: str | None) -> str:
    value = (email or "").strip()
    local, separator, domain = value.partition("@")
    if not separator or not local or not domain:
        return "Email saved"
    return f"{local[0]}•••@{domain}"


def masked_phone(phone: str | None) -> str | None:
    digits = "".join(character for character in (phone or "") if character.isdigit())
    if not digits:
        return None
    return f"••• ••• {digits[-4:].rjust(4, '•')}"
