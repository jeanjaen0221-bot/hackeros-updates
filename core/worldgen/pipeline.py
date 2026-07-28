"""core.worldgen.pipeline — orchestration des étapes de génération.

Zéro dépendance Qt. Réutilisable depuis CLI, GUI (via QThread wrapper) ou tests.

Étapes :
    1. world             — génère districts/places/targets/hosts
    2. story_anchors     — injecte les cibles narratives (story_*)
    3. story_fr          — invoque gen_story_fr.py → save/story/story.json
    4. missions          — génère les missions
    5. filesystem        — matérialise le FS virtuel (skippable)
    6. network_index     — index legacy réseaux/hôtes
    7. encode            — world.dat + missions.dat (encode_dat chiffré)
    8. meta              — world.meta.json + missions.meta.json
    9. cleanup           — purge runtime_state, story_state, anciens world_fs/*

Exemple::

    from core.worldgen import Pipeline, PipelineOptions
    opts = PipelineOptions(
        seed=42, size="S", difficulty="normal",
        types=["company", "person", "public_wifi"],
        mission_count=20, save_dir=Path("save"),
    )
    result = Pipeline(opts).run(on_progress=lambda pct, msg: print(f"{pct}% {msg}"))
    print(result.targets, result.missions)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.world_codec import CODEC_VERSION, MISSIONS_MAGIC, WORLD_MAGIC, _SECRET


# ── Data classes ──────────────────────────────────────────────────────────

@dataclass
class PipelineOptions:
    """Options d'entrée pour un run complet du pipeline."""
    seed: int
    size: str = "M"
    difficulty: str = "normal"
    economy_mult: float = 1.0
    mission_count: int = 120
    wifi_density: str = "medium"
    districts_mode: str = "auto"
    region: str = "eu"
    types: List[str] = field(default_factory=lambda: [
        "company", "government", "person", "public_wifi", "bank",
    ])
    tax_rate: float = 0.05
    save_dir: Path = field(default_factory=lambda: Path("save"))
    skip_fs: bool = False
    run_story_fr: bool = True
    """Si True, invoque dev_tools/gen_story_fr.py après l'injection des ancres."""


@dataclass
class PipelineResult:
    """Résumé retourné après exécution."""
    targets: int
    missions: int
    networks: int
    hosts: int
    fs_root: str
    world_sha256: str
    missions_sha256: str
    story_json_path: Optional[str] = None


# ── Exceptions ────────────────────────────────────────────────────────────

class PipelineCancelled(Exception):
    """Levée lorsque ``cancel_flag()`` retourne True entre deux étapes."""


# ── Pipeline ──────────────────────────────────────────────────────────────

ProgressCb = Callable[[int, str], None]
CancelCb = Callable[[], bool]


class Pipeline:
    """Orchestrateur de génération. Un appel à ``run()`` exécute les 9 étapes."""

    def __init__(self, options: PipelineOptions):
        self.opts = options

    # ── utilitaires ────────────────────────────────────────────────────
    @staticmethod
    def _noop_progress(pct: int, msg: str) -> None:
        return None

    @staticmethod
    def _noop_cancel() -> bool:
        return False

    def _check(self, cancel: CancelCb) -> None:
        if cancel():
            raise PipelineCancelled()

    # ── étapes individuelles ──────────────────────────────────────────
    def run(
        self,
        on_progress: Optional[ProgressCb] = None,
        cancel_flag: Optional[CancelCb] = None,
    ) -> PipelineResult:
        """Exécute les 9 étapes. Lève ``PipelineCancelled`` si annulé."""
        prog = on_progress or self._noop_progress
        cancel = cancel_flag or self._noop_cancel
        o = self.opts
        save_dir = Path(o.save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        # Import paresseux — évite de charger Qt au chargement de ce module.
        from core.worldgen import (
            generate_world, inject_story_anchors, generate_missions,
            generate_external_fs, build_network_index, sha256_bytes,
        )
        from core.world_codec import encode_dat

        # 1. world
        self._check(cancel)
        prog(5, "Génération du monde…")
        world = generate_world(
            seed=o.seed, size=o.size, difficulty=o.difficulty, types=list(o.types),
            region_id=o.region, wifi_density=o.wifi_density,
            districts_mode=o.districts_mode, economy_mult=o.economy_mult,
        )
        world["crypto_tax_rate"] = float(o.tax_rate)

        # 2. story anchors
        self._check(cancel)
        prog(20, "Injection des ancres narratives…")
        inject_story_anchors(world, o.seed)

        # 3. story_fr (optionnel)
        story_path: Optional[Path] = None
        if o.run_story_fr:
            self._check(cancel)
            prog(28, "Génération du scénario (gen_story_fr)…")
            story_path = self._run_gen_story_fr(save_dir, prog)

        # 4. missions
        self._check(cancel)
        prog(40, "Génération des missions…")
        missions = generate_missions(
            seed=o.seed, world=world, mission_count=o.mission_count,
        )

        # 5. filesystem
        self._check(cancel)
        fs_root, fs_sha = "", ""
        if o.skip_fs:
            prog(60, "Filesystem ignoré (skip_fs activé)")
        else:
            prog(55, "Génération du filesystem…")
            # Pré-encodage pour récupérer le SHA du monde
            pre_blob = encode_dat(WORLD_MAGIC, CODEC_VERSION, o.seed, world, _SECRET)
            world_sha = sha256_bytes(pre_blob)
            try:
                fs_root, fs_sha = generate_external_fs(
                    save_dir=save_dir, world_sha=world_sha,
                    world_obj=world, seed=o.seed,
                )
            except Exception as e:
                prog(65, f"[WARN] filesystem partiel : {e}")

        # 5b. enrichissement des lieux
        # Placé ici, après que toutes les sources de lieux ont contribué
        # (génération procédurale et ancres narratives) : enrichir plus tôt en
        # laissait un tiers sans attributs.
        self._check(cancel)
        prog(70, "Enrichissement des lieux (horaires, sécurité, PNJ)…")
        try:
            from core.worldgen._impl import enrich_world_places
            enriched = enrich_world_places(world, o.seed)
            prog(72, f"{enriched} lieu(x) enrichi(s)")
        except Exception as e:
            prog(72, f"[WARN] enrichissement des lieux ignoré : {e}")

        # 6. network index
        self._check(cancel)
        prog(75, "Index réseau…")
        networks, hosts_total = build_network_index(world)
        world["networks"] = networks
        world["hosts_total"] = int(hosts_total)

        # 7. encode (final)
        self._check(cancel)
        prog(85, "Encodage world.dat / missions.dat…")
        world_blob = encode_dat(WORLD_MAGIC, CODEC_VERSION, o.seed, world, _SECRET)
        missions_blob = encode_dat(MISSIONS_MAGIC, CODEC_VERSION, o.seed, missions, _SECRET)
        (save_dir / "world.dat").write_bytes(world_blob)
        (save_dir / "missions.dat").write_bytes(missions_blob)
        world_sha_final = sha256_bytes(world_blob)
        missions_sha_final = sha256_bytes(missions_blob)

        # 8. meta
        self._check(cancel)
        prog(92, "Écriture des métadonnées…")
        meta = {
            "world_file_sha256": world_sha_final,
            "missions_file_sha256": missions_sha_final,
            "world_fs_root": fs_root,
            "world_fs_sha256": fs_sha,
            "seed": int(o.seed),
            "networks": networks,
            "hosts_total": int(hosts_total),
        }
        (save_dir / "world.meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        (save_dir / "missions.meta.json").write_text(
            json.dumps({
                "missions_file_sha256": missions_sha_final,
                "seed": int(o.seed),
                "mission_count": len(missions.get("missions", [])),
            }, indent=2),
            encoding="utf-8",
        )

        # 10. market seed (anchored on world)
        self._check(cancel)
        prog(95, "Initialisation du ShadowMarket…")
        try:
            from core.worldgen.market_seed import generate_market_seed
            mseed = generate_market_seed(world, int(o.seed))
            (save_dir / "market_seed.json").write_text(
                json.dumps(mseed, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            prog(96, f"[WARN] market_seed a échoué : {e}")

        # 9. cleanup
        self._check(cancel)
        prog(97, "Nettoyage…")
        self._cleanup(save_dir, fs_root)

        prog(100, "Terminé ✓")
        return PipelineResult(
            targets=len(world.get("targets", [])),
            missions=len(missions.get("missions", [])),
            networks=len(networks),
            hosts=int(hosts_total),
            fs_root=fs_root,
            world_sha256=world_sha_final,
            missions_sha256=missions_sha_final,
            story_json_path=str(story_path) if story_path else None,
        )

    # ── helpers ────────────────────────────────────────────────────────

    def _run_gen_story_fr(self, save_dir: Path, prog: ProgressCb) -> Optional[Path]:
        """Invoque ``dev_tools/gen_story_fr.py`` en sous-processus.

        Ne lève pas si le script est absent : émet juste un warning de progress.
        Retourne le chemin de ``save/story/story.json`` s'il existe à la fin.
        """
        root = Path(__file__).resolve().parents[2]
        gen = root / "dev_tools" / "gen_story_fr.py"
        if not gen.exists():
            prog(32, "[WARN] gen_story_fr.py introuvable — étape ignorée")
            return None
        try:
            result = subprocess.run(
                [sys.executable, str(gen), "--seed", str(self.opts.seed), "--save-dir", str(save_dir)],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                prog(35, f"[WARN] gen_story_fr a échoué (rc={result.returncode})")
                return None
        except Exception as e:
            prog(35, f"[WARN] gen_story_fr a levé : {e}")
            return None
        story_json = save_dir / "story" / "story.json"
        if story_json.exists():
            return story_json
        return None

    def _cleanup(self, save_dir: Path, fs_root: str) -> None:
        """Purge les fichiers de runtime/story state et les anciens world_fs."""
        for fname in (
            "story_state.json",
            "story_state.meta.json",
            "missions_state.json",
            "runtime_state.dat",
            "runtime_state.meta.json",
        ):
            p = save_dir / fname
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        wfs = save_dir / "world_fs"
        cur = Path(fs_root).name if fs_root else ""
        if wfs.is_dir() and cur:
            for old in wfs.iterdir():
                if old.is_dir() and old.name != cur:
                    try:
                        shutil.rmtree(old, ignore_errors=True)
                    except Exception:
                        pass
