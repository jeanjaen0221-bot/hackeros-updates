"""dev_hub_server/server.py — HackerOS Dev Hub web service (FastAPI).

Déployé sur Railway comme service Python séparé.
Expose :
  GET  /health                         — healthcheck
  GET  /                               — web UI (token requis)
  POST /api/generate                   — lance worldgen (token requis)
  GET  /api/events/{job_id}            — SSE progression (token requis)
  GET  /api/world/meta                 — world.meta.json actuel (public)
  GET  /api/world/file/{name:path}     — fichiers world (public)
  GET  /api/story                      — story.json (token requis)
  GET  /api/missions                   — missions décodées (token requis)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional

# ── Chemin vers core.worldgen ─────────────────────────────────────────────────
# Priorité :
#   1. dev_hub_server/core/worldgen (bundlé — Railway Root Dir = dev_hub_server)
#   2. HACKER_OS_PATH env var (override manuel)
#   3. hacker_os/ sibling (repo complet en dev local)
#   4. cwd/hacker_os (fallback)
_HERE = Path(__file__).resolve().parent
_env_hacker = os.environ.get("HACKER_OS_PATH", "").strip()

# _CORE_ROOT : dossier dont le sous-dossier core/worldgen est importable
_CORE_ROOT: Path | None = None
for _candidate in [
    _HERE,                               # core/ bundlé dans dev_hub_server/ (Railway ✓)
    Path(_env_hacker) if _env_hacker else None,
    _HERE.parent / "hacker_os",          # repo complet en dev local
    Path(os.getcwd()) / "hacker_os",     # cwd fallback
]:
    if _candidate is None:
        continue
    if (_candidate / "core" / "worldgen").is_dir():
        _CORE_ROOT = _candidate
        break

if _CORE_ROOT is None:
    print(
        "[WARN] core/worldgen introuvable. La generation echouera.\n"
        "  Lancez 'python dev_hub_server/sync_worldgen.py' pour copier les fichiers worldgen,\n"
        "  ou definir HACKER_OS_PATH=/chemin/vers/hacker_os"
    )
else:
    if str(_CORE_ROOT) not in sys.path:
        sys.path.insert(0, str(_CORE_ROOT))
    print(f"[DevHub] core.worldgen trouve dans : {_CORE_ROOT}")

from fastapi import Cookie, FastAPI, HTTPException, Query, Request
from fastapi.responses import (
    FileResponse, HTMLResponse, JSONResponse, StreamingResponse,
)
from fastapi.staticfiles import StaticFiles

# ── Config ────────────────────────────────────────────────────────────────────
DEV_HUB_TOKEN: str = os.environ.get("DEV_HUB_TOKEN", "")
STORAGE_DIR: Path = Path(os.environ.get("STORAGE_DIR", str(_HERE / "data")))
SAVE_DIR: Path = STORAGE_DIR / "save"
PORT: int = int(os.environ.get("PORT", 8000))
STATIC_DIR: Path = _HERE / "static"

SAVE_DIR.mkdir(parents=True, exist_ok=True)

# ── Job state ─────────────────────────────────────────────────────────────────
_jobs: Dict[str, Dict[str, Any]] = {}
_executor = ThreadPoolExecutor(max_workers=2)

app = FastAPI(title="HackerOS Dev Hub", docs_url=None, redoc_url=None)


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _check_token(
    token: Optional[str] = None,
    dev_hub_token: Optional[str] = Cookie(default=None),
) -> None:
    """Vérifie le token passé en query param ou cookie."""
    if not DEV_HUB_TOKEN:
        raise HTTPException(503, detail="DEV_HUB_TOKEN is not configured on this server.")
    provided = token or dev_hub_token or ""
    if provided != DEV_HUB_TOKEN:
        raise HTTPException(401, detail="Invalid or missing token.")


def _token_ok(token: Optional[str], cookie: Optional[str]) -> bool:
    if not DEV_HUB_TOKEN:
        return False
    return (token or cookie or "") == DEV_HUB_TOKEN


# ── Helpers worldgen ─────────────────────────────────────────────────────────

def _zip_world_fs(save_dir: Path) -> Optional[str]:
    """Zippe save_dir/world_fs/ → save_dir/world_fs.zip. Retourne SHA256 ou None."""
    world_fs_dir = save_dir / "world_fs"
    if not world_fs_dir.exists():
        print("[_zip_world_fs] world_fs/ absent — génération incomplète ou skip_fs=True")
        return None
    files = [f for f in world_fs_dir.rglob("*") if f.is_file()]
    if not files:
        print("[_zip_world_fs] world_fs/ vide — espace disque insuffisant lors de la génération")
        return None
    zip_path = save_dir / "world_fs.zip"
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for file in sorted(files):
                zf.write(file, file.relative_to(world_fs_dir))
        sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        print(f"[_zip_world_fs] {len(files)} fichiers → world_fs.zip sha:{sha[:12]}…")
        return sha
    except Exception as exc:
        print(f"[_zip_world_fs] erreur création ZIP (espace disque?) : {exc}")
        return None


# ── Worldgen worker ───────────────────────────────────────────────────────────

def _run_worldgen(job_id: str, params: Dict[str, Any]) -> None:
    """Exécute le pipeline de génération dans le thread pool."""
    job = _jobs[job_id]
    job["status"] = "running"
    job["events"] = []
    job["start_time"] = time.time()

    def _push(pct: int, msg: str) -> None:
        event = {"pct": pct, "msg": msg, "ts": time.time()}
        job["events"].append(event)

    try:
        if _CORE_ROOT is None:
            raise ImportError(
                "core/worldgen introuvable. "
                "Lancez sync_worldgen.py ou definir HACKER_OS_PATH."
            )

        # Nettoyage préventif pour libérer de l'espace sur le volume Railway
        import shutil as _shutil
        _old_wfs = SAVE_DIR / "world_fs"
        _old_zip = SAVE_DIR / "world_fs.zip"
        if _old_wfs.exists():
            _push(0, "Nettoyage ancien world_fs/…")
            _shutil.rmtree(str(_old_wfs), ignore_errors=True)
        if _old_zip.exists():
            _old_zip.unlink(missing_ok=True)

        from core.worldgen import Pipeline, PipelineOptions  # type: ignore

        opts = PipelineOptions(
            seed=int(params.get("seed", 42)),
            size=str(params.get("size", "M")),
            difficulty=str(params.get("difficulty", "normal")),
            economy_mult=float(params.get("economy_mult", 1.0)),
            mission_count=int(params.get("mission_count", 45)),
            wifi_density=str(params.get("wifi_density", "medium")),
            districts_mode=str(params.get("districts_mode", "auto")),
            region=str(params.get("region", "eu")),
            types=list(params.get("types", ["company", "government", "person", "public_wifi", "bank"])),
            tax_rate=float(params.get("tax_rate", 0.0)),
            save_dir=SAVE_DIR,
            skip_fs=bool(params.get("skip_fs", False)),
            run_story_fr=bool(params.get("run_story_fr", True)),
        )

        result = Pipeline(opts).run(on_progress=_push)

        # Zipper world_fs si généré (skip_fs=False)
        world_fs_zip_sha: Optional[str] = None
        if not opts.skip_fs:
            _push(99, "Archivage world_fs.zip…")
            world_fs_zip_sha = _zip_world_fs(SAVE_DIR)
            if world_fs_zip_sha:
                # Injecter le SHA dans world.meta.json pour que le client le détecte
                meta_path = SAVE_DIR / "world.meta.json"
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    meta["world_fs_zip_sha256"] = world_fs_zip_sha
                    meta_path.write_text(
                        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                except Exception as _me:
                    print(f"[_zip_world_fs] meta update failed : {_me}")
                _push(100, f"world_fs.zip prêt (sha:{world_fs_zip_sha[:12]}…)")
            else:
                _push(100, "[WARN] world_fs.zip non créé (world_fs vide?)")

        job["status"] = "done"
        job["result"] = {
            "targets": result.targets,
            "missions": result.missions,
            "networks": result.networks,
            "hosts": result.hosts,
            "world_sha256": result.world_sha256,
            "missions_sha256": result.missions_sha256,
            "world_fs_zip_sha256": world_fs_zip_sha,
            "duration": round(time.time() - job["start_time"], 1),
        }
        _push(100, f"Terminé — {result.targets} cibles, {result.missions} missions.")

    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)
        _push(-1, f"[ERREUR] {exc}")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> JSONResponse:
    world_meta = SAVE_DIR / "world.meta.json"
    return JSONResponse({
        "ok": True,
        "storage_dir": str(STORAGE_DIR),
        "world_exists": world_meta.exists(),
    })


@app.get("/", response_class=HTMLResponse)
async def root(
    request: Request,
    token: Optional[str] = Query(default=None),
    dev_hub_token: Optional[str] = Cookie(default=None),
) -> HTMLResponse:
    if not _token_ok(token, dev_hub_token):
        return HTMLResponse(_login_page(), status_code=401)
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    resp = HTMLResponse(html)
    if token:
        resp.set_cookie("dev_hub_token", token, httponly=True, samesite="lax")
    return resp


@app.post("/api/auth")
async def auth(request: Request) -> JSONResponse:
    body = await request.json()
    provided = str(body.get("token", ""))
    if not _token_ok(provided, None):
        raise HTTPException(401, detail="Token invalide.")
    resp = JSONResponse({"ok": True})
    resp.set_cookie("dev_hub_token", provided, httponly=True, samesite="lax")
    return resp


@app.post("/api/generate")
async def generate(
    request: Request,
    token: Optional[str] = Query(default=None),
    dev_hub_token: Optional[str] = Cookie(default=None),
) -> JSONResponse:
    _check_token(token, dev_hub_token)
    params = await request.json()
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending", "events": [], "result": None, "error": None}
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_worldgen, job_id, params)
    return JSONResponse({"ok": True, "job_id": job_id})


@app.get("/api/events/{job_id}")
async def events(
    job_id: str,
    token: Optional[str] = Query(default=None),
    dev_hub_token: Optional[str] = Cookie(default=None),
) -> StreamingResponse:
    _check_token(token, dev_hub_token)
    if job_id not in _jobs:
        raise HTTPException(404, detail="Job inconnu.")

    async def _stream():
        last_idx = 0
        while True:
            job = _jobs.get(job_id, {})
            evts = job.get("events", [])
            for evt in evts[last_idx:]:
                data = json.dumps(evt, ensure_ascii=False)
                yield f"data: {data}\n\n"
                last_idx += 1
            status = job.get("status", "pending")
            if status in ("done", "error"):
                result = job.get("result") or {}
                error = job.get("error", "")
                payload = json.dumps({"status": status, "result": result, "error": error})
                yield f"event: finish\ndata: {payload}\n\n"
                break
            await asyncio.sleep(0.3)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/world/meta")
async def world_meta() -> JSONResponse:
    meta_path = SAVE_DIR / "world.meta.json"
    if not meta_path.exists():
        return JSONResponse({"ok": False, "error": "Aucun monde généré."}, status_code=404)
    return JSONResponse(json.loads(meta_path.read_text(encoding="utf-8")))


@app.get("/api/world/file/{name:path}")
async def world_file(name: str) -> FileResponse:
    allowed = {
        "world.dat", "missions.dat", "market_seed.json",
        "world.meta.json", "missions.meta.json",
        "story/story.json", "world_fs.zip",
    }
    clean = name.replace("\\", "/").lstrip("/")
    if clean not in allowed:
        raise HTTPException(400, detail=f"Fichier non autorisé : {name}")
    path = SAVE_DIR / clean
    if not path.exists():
        raise HTTPException(404, detail=f"Fichier absent : {clean}")
    media = "application/octet-stream"
    if clean.endswith(".json"):
        media = "application/json"
    return FileResponse(path, media_type=media, filename=path.name)


@app.get("/api/story")
async def story(
    token: Optional[str] = Query(default=None),
    dev_hub_token: Optional[str] = Cookie(default=None),
) -> JSONResponse:
    _check_token(token, dev_hub_token)
    p = SAVE_DIR / "story" / "story.json"
    if not p.exists():
        return JSONResponse({"ok": False, "error": "story.json absent."}, status_code=404)
    return JSONResponse(json.loads(p.read_text(encoding="utf-8")))


@app.get("/api/missions")
async def missions_list(
    token: Optional[str] = Query(default=None),
    dev_hub_token: Optional[str] = Cookie(default=None),
) -> JSONResponse:
    _check_token(token, dev_hub_token)
    p = SAVE_DIR / "missions.dat"
    if not p.exists():
        return JSONResponse({"ok": False, "error": "missions.dat absent."}, status_code=404)
    try:
        from core.world_codec import decode_dat  # type: ignore
        MISSIONS_MAGIC = b"MISN"
        _SECRET = b"hacker_os_world_secret_v1"
        blob = p.read_bytes()
        _, data = decode_dat(blob, magic=MISSIONS_MAGIC, secret=_SECRET)
        missions = data.get("missions", [])
        return JSONResponse({"ok": True, "count": len(missions), "missions": missions})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── Login page (minimal) ──────────────────────────────────────────────────────

def _login_page() -> str:
    return """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HackerOS Dev Hub — Auth</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0b0f14;color:#c9d1d9;font-family:Consolas,'Courier New',monospace;
  display:flex;align-items:center;justify-content:center;min-height:100vh;}
.card{background:#0d1117;border:1px solid #1a2a3a;border-radius:8px;padding:40px 48px;
  width:100%;max-width:380px;text-align:center;}
h1{color:#00d4ff;font-size:15px;letter-spacing:2px;margin-bottom:8px;}
p{color:#586069;font-size:11px;margin-bottom:28px;}
input{width:100%;background:#0c1828;border:1px solid #1a2a3a;border-radius:4px;
  padding:10px 12px;color:#c9d1d9;font-family:inherit;font-size:12px;
  outline:none;margin-bottom:16px;}
input:focus{border-color:#00d4ff;}
button{width:100%;background:#0d1117;color:#39ff14;border:1px solid #39ff1466;
  border-radius:4px;padding:12px;font-family:inherit;font-size:13px;
  font-weight:700;cursor:pointer;letter-spacing:1px;}
button:hover{background:#0a2010;border-color:#39ff14;}
#err{color:#ff4444;font-size:11px;margin-top:12px;min-height:16px;}
</style>
</head>
<body>
<div class="card">
  <h1>▌ HACKEROS /// DEV HUB</h1>
  <p>Entrez votre token d'accès</p>
  <input id="tok" type="password" placeholder="Token..." onkeydown="if(event.key==='Enter')auth()">
  <button onclick="auth()">CONNEXION</button>
  <div id="err"></div>
</div>
<script>
async function auth(){
  const tok=document.getElementById('tok').value.trim();
  const r=await fetch('/api/auth',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({token:tok})});
  if(r.ok){location.reload();}
  else{document.getElementById('err').textContent='Token invalide.';}
}
</script>
</body>
</html>"""


# ── Static files & entry point ────────────────────────────────────────────────

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=PORT, reload=False)
