import os
from cryptography.fernet import Fernet

def _get_fernet():
    key = os.getenv("FERNET_KEY")
    if not key:
        raise RuntimeError("FERNET_KEY не задан в .env (нужен для шифрования паролей)")
    return Fernet(key.encode("utf-8"))

def encrypt_secret(plain: str) -> bytes:
    return _get_fernet().encrypt(plain.encode("utf-8"))

def decrypt_secret(token: bytes) -> str:
    return _get_fernet().decrypt(token).decode("utf-8")
