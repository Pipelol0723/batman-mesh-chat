"""
crypto.py — Cifrado Fernet para batman-mesh-chat

Algoritmo:
  passphrase (str)
      → PBKDF2-HMAC-SHA256 (100 000 iteraciones, salt fijo de red)
      → 32 bytes de clave
      → base64url
      → Fernet key (AES-128-CBC + HMAC-SHA256)

Todos los mensajes y chunks de archivo viajan cifrados.
Solo quien conozca la passphrase puede leer/enviar en la red.
"""

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Salt fijo de red: misma salt = misma clave para la misma passphrase.
# No es un secreto; su propósito es que cada red ("batman-mesh", "mi-red", ...)
# genere una clave diferente aunque la passphrase sea la misma.
_NETWORK_SALT = b"batman-mesh-salt-v1"
_ITERATIONS = 100_000


def _derive_key(passphrase: str) -> bytes:
    """Deriva una clave Fernet de 32 bytes a partir de la passphrase."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_NETWORK_SALT,
        iterations=_ITERATIONS,
    )
    raw_key = kdf.derive(passphrase.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_key)


class Crypto:
    """Wrapper de alto nivel para cifrar/descifrar bytes y strings."""

    def __init__(self, passphrase: str):
        self._fernet = Fernet(_derive_key(passphrase))

    # ── bytes ──────────────────────────────────────────────────────────────

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        """Levanta InvalidToken si el token es inválido o de otra red."""
        return self._fernet.decrypt(token)

    # ── strings ────────────────────────────────────────────────────────────

    def encrypt_str(self, text: str) -> bytes:
        return self.encrypt(text.encode("utf-8"))

    def decrypt_str(self, token: bytes) -> str:
        return self.decrypt(token).decode("utf-8")

    # ── utilidad ───────────────────────────────────────────────────────────

    def try_decrypt(self, token: bytes) -> bytes | None:
        """Como decrypt pero retorna None si falla (paquete de otra red)."""
        try:
            return self.decrypt(token)
        except (InvalidToken, Exception):
            return None
