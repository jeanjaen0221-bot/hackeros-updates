"""dev_hub_server/sync_worldgen.py — synchronise les fichiers worldgen locaux.

A lancer depuis la racine du repo quand core/worldgen/ est modifie dans hacker_os :

    python dev_hub_server/sync_worldgen.py

Copie les 8 fichiers Python purs de hacker_os/core/ vers dev_hub_server/core/.
Ces fichiers n'ont aucune dependance externe (stdlib uniquement) et peuvent
etre commites dans le repo pour que Railway les utilise directement.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent

SRC_BASE = _ROOT / "hacker_os"
DST_BASE = _HERE

SYNC_MAP = {
    "core/world_codec.py":              "core/world_codec.py",
    "core/worldgen/__init__.py":        "core/worldgen/__init__.py",
    "core/worldgen/_impl.py":           "core/worldgen/_impl.py",
    "core/worldgen/pipeline.py":        "core/worldgen/pipeline.py",
    "core/worldgen/export.py":          "core/worldgen/export.py",
    "core/worldgen/samples.py":         "core/worldgen/samples.py",
    "core/worldgen/market_seed.py":     "core/worldgen/market_seed.py",
    "core/worldgen/audit.py":           "core/worldgen/audit.py",
    "dev_tools/gen_story_fr.py":        "dev_tools/gen_story_fr.py",
}


def sync() -> int:
    if not SRC_BASE.is_dir():
        print(f"[ERREUR] hacker_os introuvable : {SRC_BASE}")
        print("  Lancez ce script depuis la racine du repo (d:/fourtoiut/O.S2.0/).")
        return 1

    copied = 0
    errors = 0
    for src_rel, dst_rel in SYNC_MAP.items():
        src = SRC_BASE / src_rel
        dst = DST_BASE / dst_rel
        if not src.exists():
            print(f"[WARN] Source absente : {src_rel}")
            errors += 1
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  [OK] {src_rel}")
        copied += 1

    print(f"\n{copied} fichier(s) synchronise(s) vers dev_hub_server/core/.")
    if errors:
        print(f"{errors} fichier(s) manquant(s).")
    return errors


if __name__ == "__main__":
    raise SystemExit(sync())
