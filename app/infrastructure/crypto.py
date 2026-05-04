from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class FernetCipher:
    """Field-level cipher for free-text PII.

    Multi-key support enables rotation: the first key encrypts new data;
    decrypt tries each key in order. To rotate, prepend a new key and
    keep the old one until you've re-encrypted historical rows.
    """

    def __init__(self, keys: Iterable[str]) -> None:
        key_list = [k.encode() if isinstance(k, str) else k for k in keys]
        if not key_list:
            raise ValueError("FernetCipher requires at least one key")
        self._mf = MultiFernet([Fernet(k) for k in key_list])

    def encrypt(self, plaintext: str) -> bytes:
        return self._mf.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, token: bytes | memoryview) -> str:
        try:
            return self._mf.decrypt(bytes(token)).decode("utf-8")
        except InvalidToken as e:
            raise ValueError("Failed to decrypt: invalid or unknown key") from e

    def encrypt_json(self, value: Any) -> bytes:
        return self.encrypt(json.dumps(value, ensure_ascii=False, separators=(",", ":")))

    def decrypt_json(self, token: bytes | memoryview) -> Any:
        return json.loads(self.decrypt(token))
