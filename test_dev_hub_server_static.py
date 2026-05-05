"""test_dev_hub_server_static.py — validation statique du Dev Hub Railway.

Vérifie sans démarrer de serveur :
  - server.py compile sans erreur
  - FastAPI app instanciable (sans Qt, sans Railway)
  - Routes déclarées : /health, /, /api/generate, /api/events/{id},
      /api/world/meta, /api/world/file/{name}, /api/story, /api/missions
  - sys.path inclut hacker_os
  - world_sync.py compile et exporte sync_if_needed
  - Config exemple cohérente
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HACKER_OS = ROOT / "hacker_os"
DEV_HUB_SERVER = ROOT / "dev_hub_server"


def test_server_compiles():
    import py_compile
    py_compile.compile(str(DEV_HUB_SERVER / "server.py"), doraise=True)
    print("  [OK] server.py compile")


def test_world_sync_compiles():
    import py_compile
    py_compile.compile(str(HACKER_OS / "core" / "world_sync.py"), doraise=True)
    print("  [OK] world_sync.py compile")


def test_os_kernel_compiles():
    import py_compile
    py_compile.compile(str(HACKER_OS / "core" / "os_kernel.py"), doraise=True)
    print("  [OK] os_kernel.py compile")


def test_server_routes():
    try:
        import fastapi  # noqa: F401
    except ImportError:
        print("  [SKIP] test_server_routes -- fastapi non installe (OK en local)")
        return

    if str(DEV_HUB_SERVER) not in sys.path:
        sys.path.insert(0, str(DEV_HUB_SERVER))
    if str(HACKER_OS) not in sys.path:
        sys.path.insert(0, str(HACKER_OS))

    import importlib.util
    spec = importlib.util.spec_from_file_location("server", DEV_HUB_SERVER / "server.py")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        raise AssertionError(f"Impossible de charger server.py : {e}")

    app = mod.app
    routes = {r.path for r in app.routes}

    required = [
        "/health",
        "/",
        "/api/auth",
        "/api/generate",
        "/api/events/{job_id}",
        "/api/world/meta",
        "/api/world/file/{name}",
        "/api/story",
        "/api/missions",
    ]
    for r in required:
        assert r in routes, f"Route manquante : {r}"
    print(f"  [OK] {len(required)} routes declarees")


def test_server_hacker_os_path():
    server_src = (DEV_HUB_SERVER / "server.py").read_text(encoding="utf-8")
    assert "_CORE_ROOT" in server_src, "_CORE_ROOT absent de server.py"
    assert 'sys.path.insert' in server_src, "sys.path.insert absent de server.py"
    assert "core/worldgen" in server_src, "detection core/worldgen absente"
    print("  [OK] path detection core/worldgen present dans server.py")


def test_server_auth_check():
    server_src = (DEV_HUB_SERVER / "server.py").read_text(encoding="utf-8")
    assert "_check_token" in server_src, "_check_token absent"
    assert "DEV_HUB_TOKEN" in server_src, "DEV_HUB_TOKEN absent"
    print("  [OK] token auth present dans server.py")


def test_world_sync_exports():
    if str(HACKER_OS) not in sys.path:
        sys.path.insert(0, str(HACKER_OS))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "world_sync", HACKER_OS / "core" / "world_sync.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "sync_if_needed"), "sync_if_needed manquant"
    assert hasattr(mod, "SYNC_FILES"), "SYNC_FILES manquant"
    assert "world.dat" in mod.SYNC_FILES
    assert "missions.dat" in mod.SYNC_FILES
    print(f"  [OK] world_sync.py exporte sync_if_needed et {len(mod.SYNC_FILES)} SYNC_FILES")


def test_world_sync_config_template():
    cfg_path = HACKER_OS / "world_sync_config.json"
    assert cfg_path.exists(), "world_sync_config.json absent dans hacker_os/"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert "enabled" in cfg, "clé 'enabled' manquante"
    assert "dev_hub_url" in cfg, "clé 'dev_hub_url' manquante"
    assert cfg["enabled"] is False, "enabled doit être False par défaut"
    print("  [OK] world_sync_config.json valide (enabled:false par defaut)")


def test_os_kernel_sync_hook():
    kernel_src = (HACKER_OS / "core" / "os_kernel.py").read_text(encoding="utf-8")
    assert "world_sync_config.json" in kernel_src, "hook world_sync_config.json absent"
    assert "sync_if_needed" in kernel_src, "sync_if_needed non appelé dans os_kernel"
    assert "WorldSync" in kernel_src, "log WorldSync absent"
    print("  [OK] hook sync_if_needed present dans os_kernel.py")


def test_env_example():
    env_path = DEV_HUB_SERVER / ".env.example"
    assert env_path.exists(), ".env.example absent"
    content = env_path.read_text(encoding="utf-8")
    assert "DEV_HUB_TOKEN" in content
    assert "STORAGE_DIR" in content
    print("  [OK] .env.example contient DEV_HUB_TOKEN et STORAGE_DIR")


def test_static_index_exists():
    idx = DEV_HUB_SERVER / "static" / "index.html"
    assert idx.exists(), "static/index.html absent"
    html = idx.read_text(encoding="utf-8")
    assert "MONDE" in html
    assert "HISTOIRE" in html
    assert "MISSIONS" in html
    assert "startGenerate" in html
    assert "loadStory" in html
    assert "loadMissions" in html
    print("  [OK] static/index.html contient les 3 onglets et leurs fonctions JS")


def test_railway_json():
    rj = DEV_HUB_SERVER / "railway.json"
    assert rj.exists(), "railway.json absent"
    cfg = json.loads(rj.read_text(encoding="utf-8"))
    assert cfg["deploy"]["startCommand"] == "python server.py"
    assert cfg["deploy"]["healthcheckPath"] == "/health"
    print("  [OK] railway.json valide")


def test_requirements():
    req = DEV_HUB_SERVER / "requirements.txt"
    assert req.exists(), "requirements.txt absent"
    content = req.read_text(encoding="utf-8")
    assert "fastapi" in content
    assert "uvicorn" in content
    print("  [OK] requirements.txt contient fastapi et uvicorn")


WORLDGEN_FILES = [
    "core/__init__.py",
    "core/world_codec.py",
    "core/worldgen/__init__.py",
    "core/worldgen/_impl.py",
    "core/worldgen/pipeline.py",
    "core/worldgen/export.py",
    "core/worldgen/samples.py",
    "core/worldgen/market_seed.py",
    "core/worldgen/audit.py",
    "dev_tools/gen_story_fr.py",
]


def test_worldgen_bundle_present():
    import py_compile
    missing = []
    for rel in WORLDGEN_FILES:
        p = DEV_HUB_SERVER / rel
        if not p.exists():
            missing.append(rel)
    assert not missing, f"Fichiers worldgen manquants : {missing}"
    for rel in WORLDGEN_FILES:
        p = DEV_HUB_SERVER / rel
        if p.stat().st_size > 0:
            py_compile.compile(str(p), doraise=True)
    print(f"  [OK] {len(WORLDGEN_FILES)} fichiers worldgen bundled et compilables")


def test_worldgen_bundle_no_qt():
    for rel in WORLDGEN_FILES:
        p = DEV_HUB_SERVER / rel
        if not p.exists() or p.stat().st_size == 0:
            continue
        src = p.read_text(encoding="utf-8")
        assert "PySide6" not in src, f"PySide6 detecte dans {rel}"
        assert "PyQt" not in src, f"PyQt detecte dans {rel}"
    print("  [OK] aucun import Qt dans les fichiers worldgen bundled")


def test_gen_story_fr_bundled():
    import py_compile
    p = DEV_HUB_SERVER / "dev_tools" / "gen_story_fr.py"
    assert p.exists(), "dev_tools/gen_story_fr.py absent"
    py_compile.compile(str(p), doraise=True)
    src = p.read_text(encoding="utf-8")
    assert "PySide6" not in src and "PyQt" not in src, "Qt detecte dans gen_story_fr.py"
    assert "story.json" in src, "story.json absent de gen_story_fr.py"
    assert "BEATS" in src or "beats" in src, "structure beats absente"
    print("  [OK] dev_tools/gen_story_fr.py bundled, stdlib-only, valide")


def test_worldgen_importable():
    import importlib.util
    if str(DEV_HUB_SERVER) not in sys.path:
        sys.path.insert(0, str(DEV_HUB_SERVER))
    spec = importlib.util.spec_from_file_location(
        "core.worldgen._impl", DEV_HUB_SERVER / "core" / "worldgen" / "_impl.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "WORLD_MAGIC"), "WORLD_MAGIC absent de _impl.py"
    assert hasattr(mod, "MISSIONS_MAGIC"), "MISSIONS_MAGIC absent"
    print("  [OK] core/worldgen/_impl.py importable et fonctionnel")


def test_sync_worldgen_script():
    import py_compile
    p = DEV_HUB_SERVER / "sync_worldgen.py"
    assert p.exists(), "sync_worldgen.py absent"
    py_compile.compile(str(p), doraise=True)
    src = p.read_text(encoding="utf-8")
    assert "world_codec.py" in src
    assert "worldgen/_impl.py" in src or "worldgen\\\\" in src or "_impl.py" in src
    assert "shutil.copy2" in src
    print("  [OK] sync_worldgen.py present et valide")


def test_server_run_story_fr_default_true():
    server_src = (DEV_HUB_SERVER / "server.py").read_text(encoding="utf-8")
    assert 'run_story_fr", True)' in server_src, \
        "run_story_fr doit etre True par defaut dans server.py (gen_story_fr.py bundled)"
    print("  [OK] run_story_fr=True par defaut dans server.py")


if __name__ == "__main__":
    tests = [
        test_server_compiles,
        test_world_sync_compiles,
        test_os_kernel_compiles,
        test_server_hacker_os_path,
        test_server_auth_check,
        test_server_routes,
        test_world_sync_exports,
        test_world_sync_config_template,
        test_os_kernel_sync_hook,
        test_env_example,
        test_static_index_exists,
        test_railway_json,
        test_requirements,
        test_worldgen_bundle_present,
        test_worldgen_bundle_no_qt,
        test_gen_story_fr_bundled,
        test_worldgen_importable,
        test_sync_worldgen_script,
        test_server_run_story_fr_default_true,
    ]
    print(f"\n=== Dev Hub Railway — {len(tests)} tests statiques ===\n")
    failures = []
    for t in tests:
        try:
            t()
        except Exception as e:
            failures.append((t.__name__, e))
            print(f"  [FAIL] {t.__name__} : {e}")
    print()
    if failures:
        print(f"ECHEC -- {len(failures)}/{len(tests)} tests echoues.")
        sys.exit(1)
    else:
        print(f"OK -- {len(tests)}/{len(tests)} tests reussis.")
