from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.infrastructure.crypto import FernetCipher


@pytest.fixture()
def keys() -> list[str]:
    return [Fernet.generate_key().decode()]


def test_round_trip_text(keys: list[str]) -> None:
    cipher = FernetCipher(keys)
    token = cipher.encrypt("hello — мир — 世界")
    assert isinstance(token, bytes)
    assert cipher.decrypt(token) == "hello — мир — 世界"


def test_round_trip_json(keys: list[str]) -> None:
    cipher = FernetCipher(keys)
    payload = {"a": 1, "b": ["x", "y"], "c": {"d": True}}
    token = cipher.encrypt_json(payload)
    assert cipher.decrypt_json(token) == payload


def test_multi_key_rotation() -> None:
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()

    old_only = FernetCipher([old])
    token_old = old_only.encrypt("legacy")

    rotated = FernetCipher([new, old])  # new is primary, old still decrypts
    assert rotated.decrypt(token_old) == "legacy"

    token_new = rotated.encrypt("fresh")
    assert rotated.decrypt(token_new) == "fresh"
    # Old-only cipher cannot decrypt new ciphertext
    with pytest.raises(ValueError):
        old_only.decrypt(token_new)


def test_rejects_empty_keys() -> None:
    with pytest.raises(ValueError):
        FernetCipher([])
