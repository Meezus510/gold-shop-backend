import base64
import hashlib
import hmac
import re

from cryptography.fernet import Fernet

from app.config.settings import settings


def _fernet_key() -> bytes:
    configured = settings.CUSTOMER_PII_ENCRYPTION_KEY.strip()
    if configured:
        return configured.encode()
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(digest)


_FERNET = Fernet(_fernet_key())


def encrypt_text(value: str) -> str:
    return _FERNET.encrypt(value.strip().encode()).decode()


def decrypt_text(value: str) -> str:
    return _FERNET.decrypt(value.encode()).decode()


def normalize_phone(value: str) -> str:
    return "".join(re.findall(r"\d+", value))


def phone_hash(value: str) -> str:
    normalized = normalize_phone(value)
    key = settings.CUSTOMER_PII_ENCRYPTION_KEY or settings.SECRET_KEY
    return hmac.new(key.encode(), normalized.encode(), hashlib.sha256).hexdigest()
