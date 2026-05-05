"""core.worldgen.export — encodage + écriture des artefacts de jeu.

Fonction pure ``export_world()`` qui prend en entrée un ``world_obj`` et un
``missions_obj`` **déjà édités** (typiquement par l'éditeur manuel), les encode
en ``.dat`` chiffrés, génère le filesystem externe et écrit les ``.meta.json``.

Extrait de l'ancienne classe inline ``ExportWorker`` (dev_tools/world_editor_gui.py),
qui était un 4e duplicata de la logique de génération — maintenant déduplicué.

Zéro dépendance Qt : consommé par un mince ``QThread`` wrapper côté GUI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.world_codec import encode_dat
from core.worldgen._impl import (
    WORLD_MAGIC, MISSIONS_MAGIC, CODEC_VERSION, _SECRET,
    _generate_external_fs, _legacy_network_index, _sha256_bytes,
)


ProgressCb = Callable[[int, str], None]


@dataclass
class ExportPaths:
    """Chemins de sortie (4 fichiers)."""
    world_dat: Path
    missions_dat: Path
    world_meta: Path
    missions_meta: Path

    @classmethod
    def under(cls, save_dir: Path) -> "ExportPaths":
        s = Path(save_dir)
        return cls(
            world_dat=s / "world.dat",
            missions_dat=s / "missions.dat",
            world_meta=s / "world.meta.json",
            missions_meta=s / "missions.meta.json",
        )


@dataclass
class ExportResult:
    fs_root: str
    fs_sha: str
    world_sha256: str
    missions_sha256: str


def export_world(
    *,
    world_obj: Dict[str, Any],
    missions_obj: Dict[str, Any],
    seed: int,
    paths: ExportPaths,
    on_progress: Optional[ProgressCb] = None,
) -> ExportResult:
    """Encode + écrit les artefacts pour un monde déjà édité.

    Étapes : indexing → encoding → filesystem → writing → meta.
    Ne modifie ``world_obj`` que pour ajouter ``networks`` et ``hosts_total``
    s'ils sont manquants (index legacy utilisé par le runtime).
    """
    prog = on_progress or (lambda pct, msg: None)

    # 1. indexing (ne modifie que si absent)
    prog(5, "indexing")
    networks, hosts_total = _legacy_network_index(world_obj)
    if "networks" not in world_obj:
        world_obj["networks"] = networks
    if "hosts_total" not in world_obj:
        world_obj["hosts_total"] = int(hosts_total)

    # 2. pre-encode pour récupérer le SHA utilisé par le filesystem
    prog(15, "encoding")
    pre_world_blob = encode_dat(WORLD_MAGIC, CODEC_VERSION, int(seed), world_obj, _SECRET)
    world_sha = _sha256_bytes(pre_world_blob)

    # 3. filesystem
    prog(35, "filesystem")
    fs_root = ""
    fs_sha = ""
    try:
        save_dir = Path(paths.world_dat).parent
        fs_root, fs_sha = _generate_external_fs(
            save_dir=save_dir, world_sha=world_sha,
            world_obj=world_obj, seed=int(seed),
        )
    except Exception as e:
        prog(45, f"fs failed: {e}")

    # 4. encode final + write
    prog(60, "writing")
    world_blob = encode_dat(WORLD_MAGIC, CODEC_VERSION, int(seed), world_obj, _SECRET)
    missions_blob = encode_dat(MISSIONS_MAGIC, CODEC_VERSION, int(seed), missions_obj, _SECRET)
    Path(paths.world_dat).write_bytes(world_blob)
    Path(paths.missions_dat).write_bytes(missions_blob)
    world_sha_final = _sha256_bytes(world_blob)
    missions_sha_final = _sha256_bytes(missions_blob)

    # 5. meta
    prog(90, "meta")
    meta = {
        "world_file_sha256": world_sha_final,
        "missions_file_sha256": missions_sha_final,
        "world_fs_root": fs_root,
        "world_fs_sha256": fs_sha,
        "seed": int(seed),
        "networks": list(world_obj.get("networks", []))
            if isinstance(world_obj.get("networks"), list) else [],
        "hosts_total": int(world_obj.get("hosts_total", 0)),
    }
    Path(paths.world_meta).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    Path(paths.missions_meta).write_text(
        json.dumps({
            "missions_file_sha256": missions_sha_final,
            "seed": int(seed),
            "mission_count": len(missions_obj.get("missions", [])),
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    prog(100, "done")
    return ExportResult(
        fs_root=fs_root, fs_sha=fs_sha,
        world_sha256=world_sha_final,
        missions_sha256=missions_sha_final,
    )
