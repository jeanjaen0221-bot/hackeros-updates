"""core.worldgen — API unique de génération du monde, des missions et du filesystem.

Ce package centralise ce qui était auparavant éparpillé entre
``dev_tools/world_editor_gui.py`` (logique), ``dev_tools/dev_hub.py`` (worker 1)
et ``dev_tools/worldgen_gui.py`` (worker 2 — supprimé car redondant).

Depuis la 2e passe du refactor, la logique pure vit dans
``core/worldgen/_impl.py`` (zéro dépendance Qt). ``world_editor_gui.py``
n'héberge plus que de l'UI et re-exporte ces symboles pour compatibilité.

API publique::

    from core.worldgen import (
        generate_world, generate_missions, inject_story_anchors,
        generate_external_fs, build_network_index,
        Pipeline, PipelineOptions, PipelineResult, PipelineCancelled,
    )
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


# ── Ré-exports depuis le module pur _impl ─────────────────────────────
from core.worldgen._impl import (
    generate_world_auto as _generate_world_auto,
    generate_missions_auto as _generate_missions_auto,
    _inject_story_anchors,
    _generate_external_fs,
    _legacy_network_index,
    _sha256_bytes as _sha256_bytes_impl,
    WORLD_MAGIC,
    MISSIONS_MAGIC,
    CODEC_VERSION,
    _SECRET,
)


def generate_world(
    *,
    seed: int,
    size: str,
    difficulty: str,
    types: List[str],
    region_id: str = "eu",
    wifi_density: str = "medium",
    districts_mode: str = "auto",
    economy_mult: float = 1.0,
) -> Dict[str, Any]:
    """Génère l'objet ``world`` (districts, places, targets, hosts, networks…)."""
    return _generate_world_auto(
        seed=seed, size=size, difficulty=difficulty, types=types,
        region_id=region_id, wifi_density=wifi_density,
        districts_mode=districts_mode, economy_mult=economy_mult,
    )


def inject_story_anchors(world: Dict[str, Any], seed: int) -> None:
    """Ajoute les cibles narratives (``story_company_000``, etc.) in-place."""
    _inject_story_anchors(world, seed)


def generate_missions(
    *, seed: int, world: Dict[str, Any], mission_count: int = 120,
) -> Dict[str, Any]:
    """Génère un batch de missions cohérentes avec le monde fourni."""
    return _generate_missions_auto(seed=seed, world=world, mission_count=mission_count)


def generate_external_fs(
    *, save_dir: Path, world_sha: str, world_obj: Dict[str, Any], seed: int,
) -> tuple[str, str]:
    """Matérialise le filesystem virtuel sur disque. Retourne ``(fs_root, fs_sha)``."""
    return _generate_external_fs(
        save_dir=save_dir, world_sha=world_sha,
        world_obj=world_obj, seed=seed,
    )


def build_network_index(world: Dict[str, Any]) -> tuple[List[dict], int]:
    """Construit l'index legacy des réseaux. Retourne ``(networks, hosts_total)``."""
    return _legacy_network_index(world)


def sha256_bytes(data: bytes) -> str:
    """Helper — SHA-256 hex d'un blob binaire."""
    return _sha256_bytes_impl(bytes(data))


# Pipeline publique
from core.worldgen.pipeline import (  # noqa: E402
    Pipeline, PipelineOptions, PipelineResult, PipelineCancelled,
)

# Export pur (utilisé par l'éditeur manuel côté GUI)
from core.worldgen.export import (  # noqa: E402
    export_world, ExportPaths, ExportResult,
)

# Mondes d'exemple (fixtures pour l'éditeur)
from core.worldgen.samples import (  # noqa: E402
    make_sample_world, make_sample_missions,
)

__all__ = [
    "generate_world",
    "generate_missions",
    "inject_story_anchors",
    "generate_external_fs",
    "build_network_index",
    "sha256_bytes",
    "Pipeline",
    "PipelineOptions",
    "PipelineResult",
    "PipelineCancelled",
    "WORLD_MAGIC",
    "MISSIONS_MAGIC",
    "CODEC_VERSION",
    "export_world",
    "ExportPaths",
    "ExportResult",
    "make_sample_world",
    "make_sample_missions",
]
