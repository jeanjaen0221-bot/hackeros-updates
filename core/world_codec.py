from __future__ import annotations

import hashlib
import json
import struct
import zlib
from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class CodecHeader:
    magic: bytes
    version: int
    seed: int
    payload_sha256: bytes


def _keystream(key: bytes, n: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < n:
        out.extend(hashlib.sha256(key + struct.pack("<I", counter)).digest())
        counter += 1
    return bytes(out[:n])


def _xor(data: bytes, key: bytes) -> bytes:
    ks = _keystream(key, len(data))
    return bytes([a ^ b for a, b in zip(data, ks)])


def encode_dat(magic: bytes, version: int, seed: int, obj: Dict[str, Any], secret: bytes) -> bytes:
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload = zlib.compress(raw, level=9)
    sha = hashlib.sha256(payload).digest()

    key = hashlib.sha256(secret + struct.pack("<Q", int(seed))).digest()
    enc = _xor(payload, key)

    header = magic + struct.pack("<IQI", int(version), int(seed), len(enc)) + sha
    return header + enc


def decode_dat(blob: bytes, magic: bytes, secret: bytes) -> Tuple[CodecHeader, Dict[str, Any]]:
    if len(blob) < 4 + 4 + 8 + 4 + 32:
        raise ValueError("invalid dat")
    if blob[:4] != magic:
        raise ValueError("bad magic")

    version, seed, payload_len = struct.unpack("<IQI", blob[4 : 4 + 4 + 8 + 4])
    sha = blob[4 + 4 + 8 + 4 : 4 + 4 + 8 + 4 + 32]
    enc = blob[4 + 4 + 8 + 4 + 32 :]
    if len(enc) != payload_len:
        raise ValueError("truncated")

    key = hashlib.sha256(secret + struct.pack("<Q", int(seed))).digest()
    payload = _xor(enc, key)

    if hashlib.sha256(payload).digest() != sha:
        raise ValueError("corrupt")

    raw = zlib.decompress(payload)
    obj = json.loads(raw.decode("utf-8"))
    return CodecHeader(magic=magic, version=int(version), seed=int(seed), payload_sha256=sha), obj
