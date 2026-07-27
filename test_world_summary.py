"""Consultation du monde déjà généré par le Dev Hub.

L'interface n'exposait qu'un formulaire de génération : impossible de savoir ce
que contenait le monde en place sans le régénérer. Ces tests couvrent les routes
de consultation ajoutées pour y remédier, en construisant un vrai monde plutôt
qu'en simulant des données.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
HACKER_OS = REPO / "hacker_os"


def _load_server(storage: Path):
    """Charge server.py avec un STORAGE_DIR isolé."""
    pytest.importorskip("fastapi")
    os.environ["STORAGE_DIR"] = str(storage)
    os.environ["DEV_HUB_TOKEN"] = "test-token"
    # Seul dev_hub_server est ajouté au path : son paquet core/ est la copie
    # sans Qt destinée à Railway, et c'est bien celle-là qu'on veut tester.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("devhub_server_under_test", ROOT / "server.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _call(coro):
    """Exécute une route async et renvoie (status, payload)."""
    from fastapi import HTTPException
    try:
        resp = asyncio.run(coro)
    except HTTPException as exc:
        return exc.status_code, {"error": exc.detail}
    return resp.status_code, json.loads(bytes(resp.body).decode("utf-8"))


@pytest.fixture(scope="module")
def world_server(tmp_path_factory):
    """Génère un petit monde réel et sert un serveur pointé dessus."""
    pytest.importorskip("fastapi")
    storage = tmp_path_factory.mktemp("hub_storage")
    save = storage / "save"
    save.mkdir(parents=True, exist_ok=True)

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        # Copie bundlée dans dev_hub_server : stdlib uniquement, pas de Qt.
        from core.worldgen import Pipeline, PipelineOptions
    except Exception as exc:  # pragma: no cover - dépend de l'environnement
        pytest.skip(f"worldgen indisponible : {exc}")

    Pipeline(PipelineOptions(
        seed=7, size="S", difficulty="normal", mission_count=10,
        types=["company", "bank"], save_dir=save, run_story_fr=False,
    )).run()

    return _load_server(storage), save


def test_summary_describes_the_existing_world(world_server):
    server, _save = world_server
    status, data = _call(server.world_summary(token="test-token", dev_hub_token=None))
    assert status == 200, data
    assert data["ok"] is True
    assert data["seed"] == 7

    counts = data["counts"]
    for key in ("districts", "places", "targets", "networks", "hosts", "services", "missions"):
        assert key in counts, f"{key} absent du résumé"
    assert counts["targets"] > 0
    assert counts["hosts"] >= counts["targets"]
    # Le compteur de missions vient d'un second fichier : il manquait à l'origine.
    assert counts["missions"] > 0

    assert data["targets_by_type"], "aucune répartition par type"
    assert sum(data["targets_by_type"].values()) == counts["targets"]


def test_summary_reports_what_the_game_will_download(world_server):
    """Un fichier manquant côté serveur doit être visible, pas silencieux."""
    server, _save = world_server
    _status, data = _call(server.world_summary(token="test-token", dev_hub_token=None))
    files = data["files"]
    assert "world.dat" in files and files["world.dat"]["present"]
    assert files["world.dat"]["size"] > 0
    # world_fs.zip n'est produit qu'à la publication : son absence doit se voir.
    assert "world_fs.zip" in files


def test_targets_browsing_search_and_filter(world_server):
    server, _save = world_server
    status, data = _call(server.world_targets(
        q="", kind="", limit=5, offset=0, token="test-token", dev_hub_token=None))
    assert status == 200
    assert data["total"] > 0
    assert len(data["targets"]) <= 5

    first = data["targets"][0]
    for key in ("target_id", "name", "type", "hosts", "networks"):
        assert key in first
    if first["hosts"]:
        host = first["hosts"][0]
        assert "ip" in host and "services" in host
        for svc in host["services"]:
            # Le champ du monde généré est "name" : une lecture de "service"
            # renvoyait des chaînes vides.
            assert "name" in svc and "port" in svc

    _s, filtered = _call(server.world_targets(
        q="", kind="bank", limit=50, offset=0, token="test-token", dev_hub_token=None))
    assert all(t["type"] == "bank" for t in filtered["targets"])

    _s, empty = _call(server.world_targets(
        q="zzz-inexistant", kind="", limit=50, offset=0,
        token="test-token", dev_hub_token=None))
    assert empty["total"] == 0


def test_targets_pagination_does_not_overlap(world_server):
    server, _save = world_server
    _s, page1 = _call(server.world_targets(q="", kind="", limit=3, offset=0,
                                           token="test-token", dev_hub_token=None))
    _s, page2 = _call(server.world_targets(q="", kind="", limit=3, offset=3,
                                           token="test-token", dev_hub_token=None))
    ids1 = {t["target_id"] for t in page1["targets"]}
    ids2 = {t["target_id"] for t in page2["targets"]}
    assert not (ids1 & ids2), "les pages se recouvrent"


def test_routes_require_a_token(world_server):
    server, _save = world_server
    for coro in (
        server.world_summary(token=None, dev_hub_token=None),
        server.world_targets(q="", kind="", limit=10, offset=0,
                             token=None, dev_hub_token=None),
    ):
        status, _ = _call(coro)
        assert status == 401


def test_missing_world_is_reported_clearly(tmp_path):
    """Serveur neuf : message explicite plutôt qu'une erreur brute."""
    server = _load_server(tmp_path)
    status, data = _call(server.world_summary(token="test-token", dev_hub_token=None))
    assert status == 404
    assert data["ok"] is False
    assert "monde" in data["error"].lower()


def test_decode_cache_is_keyed_per_file(world_server):
    """world.dat et missions.dat doivent coexister en cache.

    Une première version vidait le cache à chaque décodage : consulter les
    missions puis le monde relançait un décodage complet à chaque fois.
    """
    server, save = world_server
    server._decoded_cache.clear()
    _call(server.world_summary(token="test-token", dev_hub_token=None))
    _call(server.missions_list(token="test-token", dev_hub_token=None))
    assert len(server._decoded_cache) >= 2, server._decoded_cache.keys()

    # Une régénération (mtime modifié) doit invalider l'entrée concernée.
    world_path = save / "world.dat"
    stamp_before = server._decoded_cache[str(world_path)][0]
    os.utime(world_path, None)
    _call(server.world_summary(token="test-token", dev_hub_token=None))
    assert server._decoded_cache[str(world_path)][0] != stamp_before


def test_codec_constants_are_imported_not_copied():
    """Les magies/secret recopiés ici ont déjà rendu des mondes illisibles."""
    src = (ROOT / "server.py").read_text(encoding="utf-8")
    assert "from core.world_codec import" in src
    assert 'b"MISN"' not in src, "MISSIONS_MAGIC recopié au lieu d'être importé"
    assert "hacker_os_world_secret" not in src, "secret du codec recopié"
