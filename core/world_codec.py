from __future__ import annotations

import hashlib
import json
import struct
import zlib
from dataclasses import dataclass
from typing import Any, Dict, Tuple

# Single source of truth for the .dat container format shared by every module
# that encodes/decodes world.dat, missions.dat and runtime_state.dat. These
# were previously copy-pasted as literals into ~9 files (core/mission_engine.py,
# core/runtime_state.py, core/world_state.py, core/worldgen/pipeline.py,
# core/worldgen/_impl.py, dev_tools/dev_hub.py, dev_tools/test_story.py,
# tools/audit_worldgen.py, dev_tools/world_editor_gui.py) — an accidental edit
# to any one copy silently breaks decoding for that file (the same class of
# bug that made hacker_os/ and dev_hub_server/ world_codec.py diverge; see
# dev_hub_server/sync_worldgen.py and its drift-detection test).
WORLD_MAGIC = b"WRLD"
MISSIONS_MAGIC = b"MISN"
CODEC_VERSION = 1
_SECRET = b"hacker_os_world_secret_v1"

# Versions de format que ce jeu sait lire. Le champ « version » de l'en-tête
# était jusqu'ici décodé puis ignoré : un fichier produit par une version
# ultérieure du générateur aurait été décodé de travers, ou aurait paru vide,
# sans que rien ne l'explique. On préfère un refus net et actionnable.
SUPPORTED_VERSIONS = frozenset({1})


class UnsupportedVersionError(ValueError):
    """Le fichier vient d'une version du format que ce jeu ne sait pas lire."""

    def __init__(self, version: int, magic: bytes) -> None:
        self.version = int(version)
        kind = {WORLD_MAGIC: "monde", MISSIONS_MAGIC: "missions"}.get(magic, "données")
        super().__init__(
            f"Fichier {kind} en version de format {version}, "
            f"or ce jeu lit {sorted(SUPPORTED_VERSIONS)}. "
            f"Mets le jeu à jour, ou republie un monde compatible depuis le Dev Hub."
        )


@dataclass(frozen=True)
class CodecHeader:
    magic: bytes
    version: int
    seed: int
    payload_sha256: bytes


def _keystream(key: bytes, n: int) -> bytes:
    return hashlib.shake_256(key).digest(n)


def _xor(data: bytes, key: bytes) -> bytes:
    n = len(data)
    ks = _keystream(key, n)
    d_int = int.from_bytes(data, "little")
    k_int = int.from_bytes(ks, "little")
    return (d_int ^ k_int).to_bytes(n, "little")


def encode_dat(magic: bytes, version: int, seed: int, obj: Dict[str, Any], secret: bytes) -> bytes:
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload = zlib.compress(raw, level=6)
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
    if int(version) not in SUPPORTED_VERSIONS:
        raise UnsupportedVersionError(int(version), magic)
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
