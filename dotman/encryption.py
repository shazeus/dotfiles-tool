"""AES-256-GCM encryption for sensitive dotfiles."""

import os
import struct
from pathlib import Path
from typing import Tuple

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

MAGIC = b"DOTMAN\x01"
SALT_LEN = 32
NONCE_LEN = 12


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1, backend=default_backend())
    return kdf.derive(password.encode())


def encrypt_file(source: Path, dest: Path, password: str) -> Tuple[bool, str]:
    if not HAS_CRYPTO:
        return False, "cryptography package not installed."
    if not source.exists():
        return False, f"File not found: {source}"

    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = _derive_key(password, salt)
    plaintext = source.read_bytes()

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        f.write(MAGIC)
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)
    return True, f"Encrypted: {source} → {dest}"


def decrypt_file(source: Path, dest: Path, password: str) -> Tuple[bool, str]:
    if not HAS_CRYPTO:
        return False, "cryptography package not installed."
    if not source.exists():
        return False, f"File not found: {source}"

    with open(source, "rb") as f:
        magic = f.read(len(MAGIC))
        if magic != MAGIC:
            return False, "Not a dotman-encrypted file."
        salt = f.read(SALT_LEN)
        nonce = f.read(NONCE_LEN)
        ciphertext = f.read()

    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        return False, "Decryption failed — wrong password or corrupted file."

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(plaintext)
    return True, f"Decrypted: {source} → {dest}"


def is_encrypted(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with open(path, "rb") as f:
            return f.read(len(MAGIC)) == MAGIC
    except OSError:
        return False
