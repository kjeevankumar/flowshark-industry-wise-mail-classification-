"""Security utilities for credential encryption at rest and secret masking.

Uses cryptography.fernet.Fernet with a deterministic or persistent master key.
Ensures Gmail App Passwords stored in the database are never stored as plaintext.
"""

import base64
import hashlib
import os
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

from app.config import BASE_DIR, get_settings


def _get_or_create_master_key() -> bytes:
    """Retrieve encryption key from settings or persistent data/.master_key file."""
    # Check if a custom key is provided in settings
    settings = get_settings()
    env_key = os.environ.get("ENCRYPTION_KEY")
    if env_key and len(env_key.strip()) >= 32:
        # Derive 32-byte urlsafe base64 key
        derived = hashlib.sha256(env_key.strip().encode("utf-8")).digest()
        return base64.urlsafe_b64encode(derived)

    # File-based persistent master key in data/
    key_file = BASE_DIR / "data" / ".master_key"
    if key_file.exists():
        try:
            return key_file.read_bytes().strip()
        except Exception:
            pass

    # Generate a new random key and persist it
    key_file.parent.mkdir(parents=True, exist_ok=True)
    new_key = Fernet.generate_key()
    try:
        key_file.write_bytes(new_key)
    except Exception:
        pass
    return new_key


_fernet_instance: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    """Singleton Fernet cipher instance."""
    global _fernet_instance
    if _fernet_instance is None:
        key = _get_or_create_master_key()
        _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a secret string for storage at rest in the database.

    Args:
        plaintext: Raw credential string (e.g. 16-character Google App Password).

    Returns:
        URL-safe Base64 encoded ciphertext string.
    """
    if not plaintext:
        return ""
    fernet = _get_fernet()
    encrypted_bytes = fernet.encrypt(plaintext.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt an encrypted credential string from the database.

    Args:
        ciphertext: URL-safe Base64 encoded ciphertext string.

    Returns:
        Plaintext credential string.
    """
    if not ciphertext:
        return ""
    fernet = _get_fernet()
    try:
        decrypted_bytes = fernet.decrypt(ciphertext.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        # If decryption fails (e.g. legacy plain text during migration), return safely or raise
        return ciphertext


def mask_email(email_address: Optional[str]) -> str:
    """Mask email address for UI / log display without leaking identity."""
    if not email_address or "@" not in email_address:
        return "unconfigured"
    local_part, domain = email_address.split("@", 1)
    if len(local_part) <= 2:
        masked_local = local_part[0] + "***"
    else:
        masked_local = local_part[0] + "***" + local_part[-1]
    return f"{masked_local}@{domain}"

