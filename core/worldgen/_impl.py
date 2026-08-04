"""core.worldgen._impl — code de génération pur (sans Qt).

Extrait physiquement depuis dev_tools/world_editor_gui.py lors du refactor
``core/worldgen/``. N'expose que des fonctions déterministes opérant sur des
dicts Python standard.

Ne pas importer Qt ici. Les consommateurs passent par ``core.worldgen``.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.world_codec import CODEC_VERSION, MISSIONS_MAGIC, WORLD_MAGIC, _SECRET

def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()


def _safe_host_dir(host_id: str) -> str:
    return str(host_id).replace(":", "_").replace("/", "_").replace("\\", "_")


def _write_text(p: Path, text: str, _seen_dirs: "set | None" = None) -> Tuple[int, str]:
    parent = p.parent
    if _seen_dirs is None or parent not in _seen_dirs:
        parent.mkdir(parents=True, exist_ok=True)
        if _seen_dirs is not None:
            _seen_dirs.add(parent)
    # Important : utiliser write_bytes pour garantir que le SHA manifeste
    # corresponde exactement aux octets sur disque. Avec write_text() +
    # newline par défaut, Windows convertit \n en \r\n et casse la SHA.
    b = text.encode("utf-8", errors="ignore")
    p.write_bytes(b)
    return (len(b), hashlib.sha256(b).hexdigest())


def _gen_windows_tree(r: random.Random, target_type: str, persona: str) -> Dict[str, str]:
    base = f"C/Users/{persona}"
    _dy = f"{r.randint(2022,2025)}-{r.randint(1,12):02d}-{r.randint(1,28):02d}"
    docs = {
        f"{base}/Desktop/README.txt": f"PC: {persona}\nLast login: {_dy}\nOS: Windows 11 Pro\n",
        f"{base}/Documents/notes.txt": _generate_doc(target_type, "notes.txt", r),
        f"{base}/Documents/todo.txt": f"[ ] Update antivirus\n[ ] Rotate passwords\n[x] Weekly backup done {_dy}\n",
        f"{base}/Downloads/setup_log.txt": f"Setup completed {_dy}\nVersion: {r.randint(1,5)}.{r.randint(0,9)}.{r.randint(0,99)}\nInstalled to: C:/Program Files/App\n",
        f"{base}/AppData/Roaming/browser/history.json": '{"items": [{"url": "https://google.com"}, {"url": "https://github.com"}, {"url": "https://mail.google.com"}]}\n',
        f"{base}/AppData/Roaming/browser/cookies.json": '{"cookies": [{"domain": ".google.com", "name": "SID", "value": "auto-generated"}, {"domain": "github.com", "name": "user_session", "value": "auto-generated"}]}\n',
        "C/Windows/System32/drivers/etc/hosts": "127.0.0.1 localhost\n::1 localhost\n",
    }
    # Add many small realistic files
    for i in range(r.randint(180, 520)):
        folder = r.choice([
            f"{base}/Documents",
            f"{base}/Documents/Work",
            f"{base}/Documents/Finance",
            f"{base}/Documents/Scans",
            f"{base}/Downloads",
        ])
        ext = r.choice(["txt", "md", "log", "csv"])
        name = r.choice(["report", "invoice", "summary", "meeting", "draft", "budget", "export"]) + f"_{r.randint(1,9999):04d}.{ext}"
        if target_type in ("company", "government", "bank") and folder.endswith("Work"):
            content = _generate_doc(target_type, name, r) if r.random() < 0.12 else (
                f"{target_type.upper()} INTERNAL\nRef: {r.randint(100000,999999)}\n"
                f"Date: {r.randint(2022,2025)}-{r.randint(1,12):02d}-{r.randint(1,28):02d}\n"
                f"Status: {'open' if r.random() < 0.4 else 'closed'}\n"
            )
        elif target_type == "person":
            content = f"Note {r.randint(1,999)} — {r.choice(['Meeting', 'Call', 'Reminder', 'TODO'])} {r.randint(9,18):02d}:{r.randint(0,59):02d}\n"
        else:
            content = (
                f"[{r.randint(2022,2025)}-{r.randint(1,12):02d}-{r.randint(1,28):02d}] "
                f"event_id={r.randint(10000,99999)} status={'ok' if r.random() < 0.8 else 'warn'}\n"
            )
        docs[f"{folder}/{name}"] = content
    # A few larger docs
    for k in range(r.randint(3, 8)):
        docs[f"{base}/Documents/Work/Doc_{k:02d}.txt"] = _generate_doc(target_type, f"Doc_{k:02d}.txt", r) + "\n" + ("-" * 60) + "\n" + _generate_doc(target_type, f"Doc_{k:02d}_b.txt", r)
    return docs


def _gen_linux_tree(r: random.Random, target_type: str, user: str = "dev", home_prefix: str = "/home") -> Dict[str, str]:
    _ip = f"10.{r.randint(0,254)}.{r.randint(0,254)}.{r.randint(1,254)}"
    docs: Dict[str, str] = {
        "/etc/ssh/sshd_config": "Port 22\nPermitRootLogin no\nPasswordAuthentication yes\n",
        "/etc/hosts": f"127.0.0.1 localhost\n{_ip} {user}-srv\n",
        "/var/log/auth.log": (
            f"sshd[{r.randint(1000,9999)}]: Accepted password for {user} from {_ip} port {r.randint(1024,65535)} ssh2\n"
            f"sshd[{r.randint(1000,9999)}]: session opened for user {user} by (uid=0)\n"
        ),
        f"{home_prefix}/{user}/notes.txt": _generate_doc(target_type, "notes.txt", r),
        f"{home_prefix}/{user}/.bash_history": f"ls -la\ncd /srv\npwd\ncat /etc/hosts\nsudo -l\nhistory\n",
    }
    for i in range(r.randint(180, 520)):
        folder = r.choice([
            f"{home_prefix}/{user}",
            f"{home_prefix}/{user}/docs",
            "/srv/docs",
            "/srv/backups",
            "/var/log",
        ])
        ext = r.choice(["txt", "conf", "log", "json", "csv"])
        name = r.choice(["runbook", "audit", "export", "ticket", "snapshot", "service"]) + f"_{r.randint(1,9999):04d}.{ext}"
        if folder == "/var/log":
            content = f"[{_now_ts()}] service event id={r.randint(1000,9999)} host={user}-srv level={'INFO' if r.random() < 0.7 else 'WARN'}\n"
        elif folder in (f"{home_prefix}/{user}/docs", "/srv/docs") and r.random() < 0.12:
            content = _generate_doc(target_type, name, r)
        else:
            content = f"ref={r.randint(10000,99999)} type={target_type} status={'active' if r.random() < 0.6 else 'archived'}\n"
        docs[f"{folder}/{name}"] = content
    for k in range(r.randint(3, 8)):
        docs[f"/srv/docs/briefing_{k:02d}.txt"] = _generate_doc(target_type, f"briefing_{k:02d}.txt", r)
    return docs


def _gen_router_tree(r: random.Random, ssid: str = "FreeWiFi", encryption: str = "none") -> Dict[str, str]:
    _dy = f"{r.randint(2022,2025)}-{r.randint(1,12):02d}-{r.randint(1,28):02d}"
    docs: Dict[str, str] = {
        "/etc/config/network": "config interface 'lan'\n option ipaddr '10.42.0.1'\n option netmask '255.255.255.0'\n",
        "/etc/config/wireless": f"config wifi-iface\n option ssid '{ssid}'\n option encryption '{encryption}'\n option mode 'ap'\n",
        "/var/log/messages": f"kern.info kernel: [{r.randint(1,999)}.{r.randint(100000,999999)}] br-lan: port 1(eth0) entered forwarding state\n",
        "/root/maintenance.txt": f"- reboot weekly\n- update firmware monthly\n- last reboot: {_dy}\n",
    }
    for i in range(r.randint(80, 220)):
        docs[f"/var/log/messages.{i:03d}"] = f"[{_now_ts()}] logrotate: archive {i} completed\n"
    return docs


_WIFI_PIVOT_SUFFIXES = (":wifi_staff", ":wifi_guest", ":home_wifi")


def _generate_external_fs(
    save_dir: Path,
    world_sha: str,
    world_obj: Dict[str, Any],
    seed: int,
) -> Tuple[str, str]:
    r = random.Random(int(seed) ^ 0xFACE)
    fs_root = Path(save_dir) / "world_fs" / str(world_sha)
    fs_root.mkdir(parents=True, exist_ok=True)
    _seen_dirs: set = set()

    manifest: Dict[str, Any] = {"version": 1, "world_sha": str(world_sha), "hosts": {}}

    targets = world_obj.get("targets")
    if not isinstance(targets, list):
        targets = []

    for t in targets:
        if not isinstance(t, dict):
            continue
        ttype = str(t.get("type", "company"))
        hosts = t.get("hosts")
        if not isinstance(hosts, list):
            continue

        # Per-target wifi data: passwords for LAN pivot hints, SSIDs for router config
        _target_wifi_pwds: Dict[str, str] = {}
        _target_net_ssids: Dict[str, str] = {}
        for _n in (t.get("networks") or []):
            if not isinstance(_n, dict):
                continue
            _nid = str(_n.get("network_id", ""))
            if _nid and _n.get("ssid"):
                _target_net_ssids[_nid] = str(_n["ssid"])
            if _nid and str(_n.get("type", "")) == "wifi_private":
                try:
                    _target_wifi_pwds[_nid] = "wpa2-" + hashlib.sha256(
                        f"{seed}:wifi:{_nid}".encode("utf-8")
                    ).hexdigest()[:10]
                except Exception:
                    pass
        _wifi_pivot_injected = False  # inject only into first non-wifi host per target

        for h in hosts:
            if not isinstance(h, dict):
                continue
            host_id = str(h.get("host_id", ""))
            if not host_id:
                continue
            os_name = str(h.get("os", "Linux"))
            net_id  = str(h.get("network_id", ""))
            safe_dir = _safe_host_dir(host_id)
            host_root = fs_root / safe_dir
            host_root.mkdir(parents=True, exist_ok=True)

            persona = _pick(r, ["alice", "bob", "dev", "admin", "user", "guest"])
            # deterministic WPA2 password used by runtime connect_wifi()
            expected_wifi_pwd = ""
            try:
                mix = f"{seed}:wifi:{net_id}".encode("utf-8")
                expected_wifi_pwd = "wpa2-" + hashlib.sha256(mix).hexdigest()[:10]
            except Exception:
                expected_wifi_pwd = ""
            if "windows" in os_name.lower():
                files = _gen_windows_tree(r, ttype, persona)
            elif "openwrt" in os_name.lower() or "router" in os_name.lower():
                _ap_ssid = _target_net_ssids.get(net_id, "FreeWiFi")
                _ap_enc = next(
                    (str(_n2.get("security", "none")) for _n2 in (t.get("networks") or [])
                     if isinstance(_n2, dict) and str(_n2.get("network_id", "")) == net_id),
                    "none"
                )
                files = _gen_router_tree(r, ssid=_ap_ssid, encryption=_ap_enc)
            else:
                _home = "/Users" if "macos" in os_name.lower() else "/home"
                files = _gen_linux_tree(r, ttype, user=persona if persona not in ("guest",) else "dev", home_prefix=_home)

            # Pivot hint: store wifi_private passwords on the first LAN host of the target,
            # NOT on wifi hosts themselves (circular dependency — can't reach them without password).
            try:
                _is_lan = not any(net_id.endswith(s) for s in _WIFI_PIVOT_SUFFIXES)
                if _is_lan and not _wifi_pivot_injected and _target_wifi_pwds:
                    _wifi_lines = "\n".join(
                        f"WIFI_PASSWORD: {_nid} {_pwd}"
                        for _nid, _pwd in _target_wifi_pwds.items()
                    )
                    if "windows" in os_name.lower():
                        files[f"C/Users/{persona}/Documents/wifi_passwords.txt"] = _wifi_lines + "\n"
                    else:
                        _wu = persona if persona not in ("guest",) else "dev"
                        _home_pfx = "/Users" if "macos" in os_name.lower() else "/home"
                        files[f"{_home_pfx}/{_wu}/wifi_passwords.txt"] = _wifi_lines + "\n"
                    _wifi_pivot_injected = True
            except Exception:
                pass

            # B1-FIX: merge pre-injected files (wallet keys, story files, manual edits)
            # These take priority over the randomly generated tree.
            try:
                _om = h.get("os_model")
                if isinstance(_om, dict):
                    _pre = _om.get("files")
                    if isinstance(_pre, dict):
                        for _p, _c in _pre.items():
                            if _p and isinstance(_c, str):
                                files[str(_p)] = _c
            except Exception:
                pass

            files_index: List[dict] = []
            host_entries: List[dict] = []

            for logical_path, content in files.items():
                disk_rel = logical_path.strip("/")
                disk_path = host_root / disk_rel
                size, sha = _write_text(disk_path, content, _seen_dirs)
                files_index.append({"path": logical_path, "disk_rel": disk_rel, "size": size, "sha256": sha})
                host_entries.append({"disk_rel": disk_rel, "sha256": sha, "size": size})

            # write per-host index
            (host_root / "index.json").write_text(json.dumps({"host_id": host_id, "files": files_index}, indent=2), encoding="utf-8")

            # inject metadata into os_model for runtime
            os_model = h.get("os_model")
            if not isinstance(os_model, dict):
                os_model = {}
            os_model["files_root"] = f"world_fs/{world_sha}/{safe_dir}"
            os_model["files_index"] = files_index
            h["os_model"] = os_model

            manifest["hosts"][host_id] = host_entries

    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    (fs_root / "manifest.json").write_bytes(manifest_bytes)
    return ("world_fs/" + str(world_sha), hashlib.sha256(manifest_bytes).hexdigest())


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def _now_ts() -> int:
    return int(time.time())


def _generate_doc(target_type: str, filename: str = "report.txt", r: "random.Random | None" = None) -> str:
    import random as _rmod
    import datetime
    if r is None:
        r = _rmod.Random(hash(filename) & 0xFFFFFFFF)
    tt = (target_type or "").strip().lower()

    def _date() -> str:
        year = r.randint(2022, 2025)
        month = r.randint(1, 12)
        day = r.randint(1, 28)
        return f"{year}-{month:02d}-{day:02d}"

    def _ref() -> str:
        return f"{r.choice(['INT','SEC','OPS','ADM','FIN','HR','IT'])}-{r.randint(10000,99999)}"

    def _svc() -> str:
        return r.choice(["ssh","vpn-gateway","admin-panel","mail-relay","db-primary","file-share","auth-service","monitoring"])

    def _user() -> str:
        return r.choice(["alice","bob","carol","david","emma","frank","grace","admin","sysop","netops"])

    if tt == "company":
        tpl = r.randint(0, 3)
        if tpl == 0:
            return (
                f"INTERNAL MEMO\nRef: {_ref()}  Date: {_date()}\n\n"
                f"Subject: Quarterly Security Review\n"
                f"- {r.randint(1,6)} open vulnerability tickets pending closure\n"
                f"- VPN audit scheduled for {_date()}\n"
                f"- Credential rotation overdue on {_svc()}\n\n"
                f"Action items:\n"
                f"1) Rotate SSH keys for {_user()} and {_user()}\n"
                f"2) Disable legacy SMB shares on file server\n"
                f"3) Enforce MFA on admin panel by {_date()}\n"
            )
        if tpl == 1:
            return (
                f"FINANCE REPORT — {_date()}\nRef: {_ref()}\n\n"
                f"Q{r.randint(1,4)} Summary:\n"
                f"Revenue: ${r.randint(100,9000)*1000:,}\n"
                f"Operating costs: ${r.randint(50,4000)*1000:,}\n"
                f"Outstanding invoices: {r.randint(3,42)}\n"
                f"Flagged transactions: {r.randint(0,5)}\n\n"
                f"Next review: {_date()}\n"
            )
        if tpl == 2:
            return (
                f"HR NOTICE — Ref: {_ref()}\nDate: {_date()}\n\n"
                f"Employee {_user()} access review — status: {'pending' if r.random()<0.5 else 'complete'}\n"
                f"Onboarding batch {r.randint(1,20)}: {r.randint(2,15)} new accounts created\n"
                f"Password policy reminder: rotate every {r.choice([30,60,90])} days\n"
            )
        return (
            f"IT OPERATIONS LOG\nRef: {_ref()}  Date: {_date()}\n\n"
            f"Service {_svc()} — uptime: {r.randint(90,100)}%\n"
            f"Last incident: {_date()} — severity {r.choice(['low','medium','high'])}\n"
            f"Backup status: {'OK' if r.random()<0.8 else 'FAILED — investigate'}\n"
            f"Next maintenance window: {_date()} 02:00 UTC\n"
        )

    if tt == "government":
        tpl = r.randint(0, 2)
        if tpl == 0:
            return (
                f"CLASSIFIED — INTERNAL\nCase: {_ref()}  Date: {_date()}\n\n"
                f"Incident Report:\n"
                f"Anomalous auth attempts on {_svc()} at {r.randint(0,23):02d}:00 UTC.\n"
                f"Source IPs: {r.randint(1,8)} distinct addresses from external range.\n\n"
                f"Recommended actions:\n"
                f"- Update firmware on perimeter router (ref {_ref()})\n"
                f"- Revoke shared credentials for {_user()}\n"
                f"- Restrict management interface to VPN-only\n"
                f"Status: {'OPEN' if r.random()<0.4 else 'IN PROGRESS'}\n"
            )
        if tpl == 1:
            return (
                f"INTERNAL CIRCULAR — {_ref()}\nDate: {_date()}\n\n"
                f"Re: Access Control Review\n"
                f"All staff must reset credentials by {_date()}.\n"
                f"Privileged accounts: {r.randint(4,20)} under review.\n"
                f"Non-compliant users will have accounts suspended.\n"
                f"Contact: {_user()}@gov.int\n"
            )
        return (
            f"FIELD REPORT — Ref: {_ref()}  Date: {_date()}\n\n"
            f"Operation codename: {r.choice(['NIGHTFALL','IRONGATE','SILENTNET','REDWATCH','BLUESTREAM'])}\n"
            f"Objective: network integrity audit on sector {r.randint(1,9)}\n"
            f"Findings: {r.randint(0,4)} critical, {r.randint(0,8)} medium issues\n"
            f"Next review: {_date()}\n"
        )

    if tt == "person":
        tpl = r.randint(0, 2)
        if tpl == 0:
            return (
                f"Personal Notes — {_date()}\n\n"
                f"- Reminder: change {r.choice(['email','bank','wifi','VPN'])} password\n"
                f"- Backup photos to external drive (last done {_date()})\n"
                f"- Call {r.choice(['bank','insurance','dentist','landlord'])} about the {r.choice(['invoice','renewal','appointment','deposit'])}\n"
                f"- WiFi pass: {r.choice(['do not write here...','[redacted]','see sticky note','check phone'])}\n"
            )
        if tpl == 1:
            return (
                f"Journal — {_date()}\n\n"
                f"Had a long day. The {r.choice(['laptop','phone','router'])} keeps disconnecting.\n"
                f"Need to fix the {r.choice(['firewall settings','parental controls','VPN config','wifi password'])}.\n"
                f"Bought {r.choice(['a new router','an external HDD','a webcam','a keyboard'])} — have to set it up.\n"
            )
        return (
            f"TODO List — {_date()}\n\n"
            f"[ ] Rotate passwords (especially {_svc()})\n"
            f"[ ] Update {r.choice(['phone','laptop','tablet','router'])} firmware\n"
            f"[ ] Back up /home/{r.choice(['alice','bob','user','me'])}\n"
            f"[x] Change email — done {_date()}\n"
        )

    if tt == "public_wifi":
        tpl = r.randint(0, 1)
        if tpl == 0:
            return (
                f"AP Maintenance Log — {_date()}\n\n"
                f"SSID broadcast: {'stable' if r.random()<0.85 else 'intermittent'}\n"
                f"Connected clients: {r.randint(2,40)}\n"
                f"Firmware version: {r.randint(18,23)}.{r.randint(0,9)}.{r.randint(0,9)}\n"
                f"TODO: {'change default admin password' if r.random()<0.7 else 'update firmware to latest'}\n"
                f"Last reboot: {_date()} {r.randint(0,23):02d}:{r.randint(0,59):02d} UTC\n"
            )
        return (
            f"Access Log — {_date()}\n\n"
            f"Total sessions: {r.randint(10,300)}\n"
            f"Peak concurrent: {r.randint(5,50)}\n"
            f"Blocked attempts: {r.randint(0,12)}\n"
            f"Guest portal: {'enabled' if r.random()<0.4 else 'disabled'}\n"
            f"Admin login last seen: {_date()} by {_user()}\n"
        )

    if tt == "bank":
        tpl = r.randint(0, 2)
        if tpl == 0:
            return (
                f"CONFIDENTIAL — BANKING OPERATIONS\nRef: {_ref()}  Date: {_date()}\n\n"
                f"Account Summary:\n"
                f"Active accounts: {r.randint(1000, 50000):,}\n"
                f"Pending transfers: {r.randint(5, 200)}\n"
                f"Flagged transactions: {r.randint(0, 12)}\n"
                f"Crypto custody balance: {r.randint(50000, 5000000):,} USD equivalent\n\n"
                f"Compliance review scheduled: {_date()}\n"
                f"AML alert threshold: ${r.randint(5000,50000):,}\n"
            )
        if tpl == 1:
            return (
                f"INTERNAL AUDIT LOG — Ref: {_ref()}\nDate: {_date()}\n\n"
                f"Audited by: {_user()}\n"
                f"Scope: digital asset custody, wire transfers\n"
                f"Findings:\n"
                f"- {r.randint(0,3)} critical access control gaps\n"
                f"- {r.randint(1,8)} unresolved KYC records\n"
                f"- Crypto hot wallet exposure: {r.randint(10,40)}% of reserves\n"
                f"Next audit: {_date()}\n"
            )
        return (
            f"TREASURY REPORT — {_date()}\nRef: {_ref()}\n\n"
            f"Holdings breakdown:\n"
            f"  Fiat reserves: ${r.randint(1,50)*1_000_000:,}\n"
            f"  Crypto custody: {r.randint(100,9000)} BTC equivalent\n"
            f"  Stablecoin pool: ${r.randint(1,20)*1_000_000:,}\n"
            f"Outgoing wire (last 24h): {r.randint(10,500)}\n"
            f"Hot wallet seed backup: [REDACTED — see vault {_ref()}]\n"
        )

    return f"Document: {filename}\nGenerated at: {_now_ts()}\nRef: {_ref()}\n"


# ── Story anchor injection ────────────────────────────────────────────────────

# Minimum targets needed by story.json roles
_STORY_REQUIRED: Dict[str, int] = {
    "company":     18,
    "government":  8,
    "public_wifi": 4,
    "person":      4,
    "bank":         5,
}

# Files that MUST exist on the first host of each type for story objectives
_STORY_FILES_COMPANY: Dict[str, str] = {
    "/srv/git/README.md":          "# Internal repos\n",
    "/srv/git/deploy_notes.txt":   "Deployment schedule: TBD\n",
    "/home/dev/report.txt":        "FINANCE REPORT\nQ4 Summary: classified\n",
    "/home/dev/db_export.csv":     "id,amount,account\n1,9999,offshore_01\n",
    "/home/dev/inbox_summary.txt": "From: ops@nexus.prism\nSubject: Transfer confirmed\n",
    "/home/dev/relations.md":      "RELATION DOSSIER\nrelation_id=story_rel_core\npivot_target=NEXUS\n",
    "/var/log/audit.log":          "audit: suspicious admin login accepted\n",
    "/srv/git/nexus_arch.md":      "# NEXUS Architecture\ncontrol-plane: segmented\n",
    "/etc/prism/node.conf":        "node_role=relay\ntrust_group=PRISM\n",
}

_STORY_FILES_GOVERNMENT: Dict[str, str] = {
    "/srv/docs/classified.txt":    "CLASSIFIED — NEXUS AUTHORIZATION\nRef: INT-88421\nStatus: APPROVED\n",
    "/srv/docs/procedure.txt":     "OPERATIONAL PROCEDURE\nRef: OPS-55612\nStep 1: authenticate via VPN\n",
    "/home/dev/casefile.txt":      "CASE FILE — Ref: SEC-10291\nSubject: NEXUS network activity\n",
    "/srv/docs/access_review.log": "ACCESS REVIEW\nexternal contractor approved\n",
    "/srv/docs/intercept_policy.md": "# Intercept Policy\ncollection tier: mass\n",
    "/var/log/gateway.log":        "vpn accepted upstream relay\n",
}

_STORY_FILES_WIFI: Dict[str, str] = {
    "/home/admin/ap_log.txt":      "AP Log — beacon burst detected\nTimestamp: 2025-04-01T03:14:00Z\n",
    "/home/admin/beacon_cache.log": "beacon cache: prism burst channel active\n",
    "/home/admin/clients.csv":     "mac,vendor,note\n00:11:22:33:44:55,unknown,dead-drop handset\n",
}

_STORY_FILES_PERSON: Dict[str, str] = {
    "/home/user/notes.txt":        "Account: CH93-0076-2011-6238-5295-7\nTransfer code: NEXUS-9938\n",
    "/home/user/contacts.json":    "{\"echo\":\"unknown\",\"spectre\":\"burner\",\"lame\":\"broker\"}\n",
    "/home/user/dead_drop.txt":    "dead_drop=station locker 17\nfallback=public_wifi\n",
}

_STORY_FILES_BANK: Dict[str, str] = {
    "/srv/banking/accounts.csv":   "id,holder,balance,crypto_custody\n1,NEXUS_CLIENT,9999999,BTC\n",
    "/home/dev/treasury_report.txt": "TREASURY REPORT\nRef: FIN-00421\nCrypto hot wallet: see vault\n",
    "/home/dev/kyc_flags.txt":     "KYC ALERT\nRef: AML-5521\nFlagged: 3 accounts\nStatus: PENDING\n",
    "/srv/banking/custody_ledger.csv": "wallet,owner,status\nNEXUS_COLD,PRISM,active\n",
    "/var/log/aml_review.log":     "aml override accepted by executive token\n",
}

_STORY_ANCHOR_NAMES: Dict[str, List[str]] = {
    "company": [
        "Nexus Holdings", "Cobalt Dynamics", "Apex Systems", "Stratos Logistics",
        "Quantum Analytics", "Prism Technologies", "Vortex Security", "Zenith Capital",
        "Ironclad Solutions", "Leviathan Industries", "Helix Identity", "Obsidian Mesh",
        "Axiom Relay", "DeepCore Analytics", "Sentinel Procurement", "Crown Data",
        "BlackVault Systems", "Orion Signals",
    ],
    "government": [
        "Directorate of Digital Services", "Ministry of Infrastructure",
        "Bureau of Internal Affairs", "Agency of Cybersecurity",
        "Office of National Intelligence", "Civil Registry Authority",
        "Public Procurement Office", "Border Systems Directorate",
    ],
    "public_wifi": ["Café Nexus", "Hotel Prism", "Station Meridian", "Library Cobalt"],
    "person": ["Jordan Vasquez", "Maya Renaud", "Omar Petrov", "Lina Moreau"],
    "bank": ["Northwind Bank", "MetroCredit", "Crown Custody", "Harbor Clearing", "Atlas Trust"],
}


def _ensure_story_files_on_host(h: Dict[str, Any], extra_files: Dict[str, str]) -> None:
    """Inject missing story-required files into a host's os_model.files."""
    os_model = h.get("os_model")
    if not isinstance(os_model, dict):
        os_model = {}
        h["os_model"] = os_model
    files = os_model.get("files")
    if not isinstance(files, dict):
        files = {}
        os_model["files"] = files
    for path, content in extra_files.items():
        if path not in files:
            files[path] = content


def _inject_story_anchors(world: Dict[str, Any], seed: int) -> None:
    """Ensure the world has at least the minimum story-required targets per type,
    and that the first host of each company/government/wifi/person target has the
    story-required files. Operates in-place on world dict."""
    import random as _rmod
    r = _rmod.Random(int(seed) ^ 0xC4FE)

    targets = world.get("targets")
    if not isinstance(targets, list):
        targets = []
        world["targets"] = targets

    # Count existing targets by type
    counts: Dict[str, int] = {}
    for t in targets:
        if isinstance(t, dict):
            ttype = str(t.get("type", ""))
            counts[ttype] = counts.get(ttype, 0) + 1

    # Inject missing story files onto existing targets' first hosts
    _files_by_type = {
        "company":     _STORY_FILES_COMPANY,
        "government":  _STORY_FILES_GOVERNMENT,
        "public_wifi": _STORY_FILES_WIFI,
        "person":      _STORY_FILES_PERSON,
        "bank":        _STORY_FILES_BANK,
    }
    for t in targets:
        if not isinstance(t, dict):
            continue
        ttype = str(t.get("type", ""))
        extra = _files_by_type.get(ttype)
        if not extra:
            continue
        hosts = t.get("hosts")
        if isinstance(hosts, list) and hosts and isinstance(hosts[0], dict):
            _ensure_story_files_on_host(hosts[0], extra)

    # Track used host_idx counters per network to avoid collisions
    host_idx_by_net: Dict[str, int] = {}
    for t in targets:
        if not isinstance(t, dict):
            continue
        for h in (t.get("hosts") or []):
            if not isinstance(h, dict):
                continue
            net_id = str(h.get("network_id", ""))
            host_idx_by_net[net_id] = host_idx_by_net.get(net_id, 0) + 1

    districts = world.get("districts") or [{"district_id": "d00"}]
    region_id = str((world.get("regions") or [{}])[0].get("region_id", "eu"))

    for ttype, required in _STORY_REQUIRED.items():
        # Always inject all required story anchor targets regardless of world size.
        # story_TYPE_NNN IDs sort before t_TYPE_XXXX alphabetically (s < t),
        # so _assign_roles always maps story roles to these deterministic targets.
        existing_story_ids = {
            str(t.get("target_id", "")) for t in targets
            if isinstance(t, dict) and str(t.get("target_id", "")).startswith(f"story_{ttype}_")
        }
        names = list(_STORY_ANCHOR_NAMES.get(ttype, []))
        extra_files = _files_by_type.get(ttype, {})

        for ni in range(required):
            anchor_idx = ni
            tid = f"story_{ttype}_{anchor_idx:03d}"
            if tid in existing_story_ids:
                continue  # idempotent — skip if already present
            name = names[ni % len(names)] if names else f"NEXUS-{ttype}-{ni}"
            did = str((districts[r.randrange(0, len(districts))] or {}).get("district_id", "d00"))
            place_id = f"{did}:{tid}"

            def nid(suffix: str) -> str:
                return f"{tid}:{suffix}"

            if ttype == "company":
                lan_id = nid("lan")
                host_idx = host_idx_by_net.get(lan_id, 0)
                host_idx_by_net[lan_id] = host_idx + 1
                host: Dict[str, Any] = {
                    "host_id": f"{lan_id}:{host_idx}",
                    "network_id": lan_id,
                    "ip": f"10.0.{100 + anchor_idx}.10",
                    "hostname": "git",
                    "os": "Debian",
                    "services": [
                        {"port": 22, "name": "ssh", "version": "OpenSSH_9.0", "vuln_tags": ["bruteforce"]},
                        {"port": 80, "name": "http", "version": "nginx_1.22", "vuln_tags": ["rce_http"]},
                    ],
                    "os_model": {"users": ["root", "dev"], "files": dict(extra_files), "suid_bins": ["/usr/bin/find"]},
                }
                # Add a second host (workstation) for beats that use host_index=1
                ws_idx = host_idx + 1
                host_idx_by_net[lan_id] = ws_idx + 1
                ws_host: Dict[str, Any] = {
                    "host_id": f"{lan_id}:{ws_idx}",
                    "network_id": lan_id,
                    "ip": f"10.0.{100 + anchor_idx}.11",
                    "hostname": "ws-01",
                    "os": "Windows",
                    "services": [
                        {"port": 445, "name": "smb", "version": "SMB_3.1", "vuln_tags": ["weak_creds"]},
                    ],
                    "os_model": {"users": ["root", "admin"], "files": {}, "suid_bins": []},
                }
                t_obj: Dict[str, Any] = {
                    "target_id": tid, "type": ttype, "name": name,
                    "region_id": region_id, "district_id": did, "place_id": place_id,
                    "story_reserved": True,
                    "networks": [{"network_id": lan_id, "type": "lan", "district_id": did, "place_id": place_id}],
                    "hosts": [host, ws_host],
                }

            elif ttype == "government":
                lan_ops_id = nid("lan_ops")
                lan_admin_id = nid("lan_admin")
                hidx = host_idx_by_net.get(lan_ops_id, 0)
                host_idx_by_net[lan_ops_id] = hidx + 2
                host = {
                    "host_id": f"{lan_ops_id}:{hidx}",
                    "network_id": lan_ops_id,
                    "ip": f"10.11.{100 + anchor_idx}.10",
                    "hostname": "files",
                    "os": "Debian",
                    "services": [
                        {"port": 22, "name": "ssh", "version": "OpenSSH_8.9", "vuln_tags": ["bruteforce"]},
                        {"port": 445, "name": "smb", "version": "Samba_4.15", "vuln_tags": ["weak_creds"]},
                    ],
                    "os_model": {"users": ["root", "dev"], "files": dict(extra_files), "suid_bins": []},
                }
                gw_hidx = host_idx_by_net.get(lan_admin_id, 0)
                host_idx_by_net[lan_admin_id] = gw_hidx + 1
                gw_host = {
                    "host_id": f"{lan_admin_id}:{gw_hidx}",
                    "network_id": lan_admin_id,
                    "ip": f"10.10.{100 + anchor_idx}.1",
                    "hostname": "gateway",
                    "os": "Debian",
                    "services": [
                        {"port": 22, "name": "ssh", "version": "OpenSSH_7.9", "vuln_tags": ["bruteforce"]},
                        {"port": 443, "name": "https", "version": "nginx_1.20", "vuln_tags": []},
                    ],
                    "os_model": {"users": ["root", "dev"], "files": dict(extra_files), "suid_bins": []},
                }
                # Second host for host_index=1 beats
                ws_hidx = host_idx_by_net.get(lan_ops_id, hidx + 1)
                host_idx_by_net[lan_ops_id] = ws_hidx + 1
                ws_host = {
                    "host_id": f"{lan_ops_id}:{ws_hidx}",
                    "network_id": lan_ops_id,
                    "ip": f"10.11.{100 + anchor_idx}.100",
                    "hostname": "ws-01",
                    "os": "Windows",
                    "services": [{"port": 445, "name": "smb", "version": "SMB_3.1", "vuln_tags": ["weak_creds"]}],
                    "os_model": {"users": ["root", "analyst"], "files": {}, "suid_bins": []},
                }
                t_obj = {
                    "target_id": tid, "type": ttype, "name": name,
                    "region_id": region_id, "district_id": did, "place_id": place_id,
                    "story_reserved": True,
                    "networks": [
                        {"network_id": lan_ops_id,   "type": "lan", "district_id": did, "place_id": place_id},
                        {"network_id": lan_admin_id, "type": "lan", "district_id": did, "place_id": place_id},
                    ],
                    "hosts": [host, ws_host, gw_host],
                }

            elif ttype == "public_wifi":
                guest_id = nid("wifi_guest")
                hidx = host_idx_by_net.get(guest_id, 0)
                host_idx_by_net[guest_id] = hidx + 1
                ssid = f"{name.replace(' ', '_')}_Free"
                host = {
                    "host_id": f"{guest_id}:ap",
                    "network_id": guest_id,
                    "ip": f"10.42.{100 + anchor_idx}.1",
                    "hostname": "ap",
                    "os": "OpenWRT",
                    "services": [
                        {"port": 80, "name": "http", "version": "uhttpd_1.0", "vuln_tags": ["rce_http"]},
                        {"port": 22, "name": "ssh", "version": "OpenSSH_8.2", "vuln_tags": ["bruteforce"]},
                    ],
                    "os_model": {"users": ["root", "admin"], "files": dict(extra_files), "suid_bins": ["/usr/bin/busybox"]},
                }
                t_obj = {
                    "target_id": tid, "type": ttype, "name": name,
                    "region_id": region_id, "district_id": did, "place_id": place_id,
                    "story_reserved": True,
                    "networks": [{"network_id": guest_id, "type": "wifi_public",
                                  "ssid": ssid, "security": "open",
                                  "district_id": did, "place_id": place_id}],
                    "hosts": [host],
                    "venue": {"kind": "cafe"},
                    "wifi_profile": {"base_clients": 8, "peaks": {"morning": 0.8, "noon": 1.2, "evening": 1.5, "night": 0.3}, "jitter": 0.2},
                }

            elif ttype == "bank":
                lan_id = nid("lan")
                hidx = host_idx_by_net.get(lan_id, 0)
                host_idx_by_net[lan_id] = hidx + 2
                host = {
                    "host_id": f"{lan_id}:{hidx}",
                    "network_id": lan_id,
                    "ip": f"10.20.{100 + anchor_idx}.10",
                    "hostname": "core-banking",
                    "os": "Debian",
                    "services": [
                        {"port": 22,  "name": "ssh",   "version": "OpenSSH_9.0",  "vuln_tags": ["bruteforce"]},
                        {"port": 443, "name": "https", "version": "nginx_1.22",   "vuln_tags": ["rce_http"]},
                        {"port": 8443,"name": "api",   "version": "express_4.18", "vuln_tags": ["sqli"]},
                    ],
                    "os_model": {"users": ["root", "dev", "banker"], "files": dict(extra_files), "suid_bins": ["/usr/bin/find"]},
                }
                ws_hidx = hidx + 1
                ws_host = {
                    "host_id": f"{lan_id}:{ws_hidx}",
                    "network_id": lan_id,
                    "ip": f"10.20.{100 + anchor_idx}.11",
                    "hostname": "ws-trader",
                    "os": "Windows",
                    "services": [
                        {"port": 445, "name": "smb", "version": "SMB_3.1", "vuln_tags": ["weak_creds"]},
                        {"port": 3389,"name": "rdp", "version": "RDP_10",  "vuln_tags": ["bruteforce"]},
                    ],
                    "os_model": {"users": ["root", "trader"], "files": {}, "suid_bins": []},
                }
                t_obj = {
                    "target_id": tid, "type": ttype, "name": name,
                    "region_id": region_id, "district_id": did, "place_id": place_id,
                    "story_reserved": True,
                    "networks": [{"network_id": lan_id, "type": "lan", "district_id": did, "place_id": place_id}],
                    "hosts": [host, ws_host],
                }

            else:  # person
                home_id = nid("home_wifi")
                hidx = host_idx_by_net.get(home_id, 0)
                host_idx_by_net[home_id] = hidx + 1
                host = {
                    "host_id": f"{home_id}:{hidx}",
                    "network_id": home_id,
                    "ip": f"192.168.{100 + anchor_idx}.20",
                    "hostname": "laptop",
                    "os": "Ubuntu",
                    "services": [
                        {"port": 22, "name": "ssh", "version": "OpenSSH_8.4", "vuln_tags": ["bruteforce"]},
                    ],
                    "os_model": {"users": ["root", "user"], "files": dict(extra_files), "suid_bins": []},
                }
                t_obj = {
                    "target_id": tid, "type": ttype, "name": name,
                    "region_id": region_id, "district_id": did, "place_id": place_id,
                    "story_reserved": True,
                    "networks": [{"network_id": home_id, "type": "wifi_private",
                                  "ssid": f"{name.split()[0]}s_WiFi", "security": "wpa2",
                                  "district_id": did, "place_id": place_id}],
                    "hosts": [host],
                }

            # B3-FIX: generate crypto wallets for story anchor targets
            try:
                _r2 = random.Random(int(seed) ^ abs(hash(str(tid))) & 0xFFFFFF)
                _wallets = _gen_wallets(_r2, ttype, name, tid, economy_mult=1.0)
                if _wallets:
                    t_obj["crypto_wallets"] = _wallets
                    for _w in _wallets:
                        _kc = (
                            f"WALLET_KEY\ncurrency={_w['currency']}\n"
                            f"address={_w['address']}\n"
                            f"private_key=ENCRYPTED_{_w['wallet_id'].upper()}\n"
                        )
                        if t_obj.get("hosts"):
                            _h0 = t_obj["hosts"][0]
                            if isinstance(_h0, dict):
                                _h0_os = str(_h0.get("os", "")).lower()
                                # Wallet id suffix garantit l'unicité quand plusieurs
                                # wallets d'une même currency coexistent (sinon le
                                # dernier écrase le premier).
                                _wid_short = str(_w["wallet_id"]).rsplit("_", 1)[-1]  # e.g. "w00"
                                _kf = (
                                    f"C/Users/admin/AppData/Roaming/{_w['currency']}/wallet_{_wid_short}.key"
                                    if "windows" in _h0_os
                                    else f"/home/dev/.{_w['currency'].lower()}/wallet_{_wid_short}.key"
                                )
                                _w["key_file"] = _kf
                                _om = _h0.setdefault("os_model", {})
                                _om.setdefault("files", {})[_kf] = _kc
            except Exception:
                pass

            targets.append(t_obj)

            # Bug 10 fix: story anchor targets must also appear in world["places"]
            # so the player can navigate there and _network_allowed_in_place returns True.
            try:
                _places = world.setdefault("places", [])
                _existing_pids = {p.get("place_id") for p in _places if isinstance(p, dict)}
                if place_id not in _existing_pids:
                    _cat = {
                        "company": "office",
                        "government": "government_building",
                        "bank": "bank",
                        "person": "home",
                        "public_wifi": "cafe",
                    }.get(ttype, "office")
                    _dref = next(
                        (d for d in districts if isinstance(d, dict) and str(d.get("district_id", "")) == did),
                        None,
                    )
                    _cx = float((_dref or {}).get("center", {}).get("x", r.random()))  # type: ignore[union-attr]
                    _cy = float((_dref or {}).get("center", {}).get("y", r.random()))  # type: ignore[union-attr]
                    _rad = float((_dref or {}).get("radius", 0.15))
                    _places.append({
                        "place_id": place_id,
                        "district_id": did,
                        "category": _cat,
                        "name": name,
                        "target_id": tid,
                        "x": float(max(0.0, min(1.0, _cx + (r.random() - 0.5) * 2.0 * _rad))),
                        "y": float(max(0.0, min(1.0, _cy + (r.random() - 0.5) * 2.0 * _rad))),
                    })
            except Exception:
                pass

    world["targets"] = targets
    # Les ancres narratives ajoutent leurs propres hôtes après la construction
    # du monde : l'invariant « aucun hôte sans compte » doit être réappliqué.
    assign_host_accounts(world, r)


def assign_host_accounts(world: Dict[str, Any], r) -> int:
    """Donne des comptes à tout hôte qui n'en a pas. Retourne le nombre traité.

    Les hôtes naissent de plusieurs endroits du générateur — ancres narratives,
    cibles ordinaires, routeurs domestiques. Attribuer les comptes à chacun de
    ces endroits reviendrait à en oublier un, aujourd'hui ou au prochain ajout :
    cette passe finale garantit l'invariant « aucun hôte sans compte », quelle
    que soit son origine.

    Sans comptes, ``attempt_login`` retombe sur « le mot de passe est
    l'identifiant » et les wordlists du marché ne servent à rien.
    """
    from core.wordlists import password_at, rank_range_for

    targets = world.get("targets") or []
    if isinstance(targets, dict):
        targets = list(targets.values())

    filled = 0
    for target in targets:
        if not isinstance(target, dict):
            continue
        lo, hi = rank_range_for(str(target.get("type", "")))
        for host in (target.get("hosts") or []):
            if not isinstance(host, dict) or host.get("accounts"):
                continue
            users = ((host.get("os_model") or {}).get("users")
                     or ["root", "dev"])
            accounts: Dict[str, Any] = {}
            for user in users:
                # root est toujours mieux protégé : y accéder doit rester le
                # chemin difficile, même sur une cible modeste.
                low = lo + (hi - lo) // 2 if str(user) == "root" else lo
                rank = r.randint(int(low), int(hi))
                accounts[str(user)] = {"password": password_at(rank), "rank": rank}
            host["accounts"] = accounts
            filled += 1
    return filled


def make_empty_world(seed: int = 123) -> Dict[str, Any]:
    return {
        "schema": "world_v2",
        "seed": int(seed),
        "generated_at": _now_ts(),
        "regions": [{"region_id": "eu", "name": "EU"}],
        "targets": [],
    }


def _pick(r, xs: List[str]) -> str:
    return xs[int(r.randrange(0, max(1, len(xs)))) % max(1, len(xs))]


def _make_target_name(r, ttype: str) -> str:
    if ttype == "company":
        prefixes = [
            "Northwind","Astra","Helio","BluePeak","Cobalt","Ardent","Nova","Vertex",
            "Apex","Orbital","Cipher","Nexus","Prism","Stratos","Vortex","Zenith",
            "Ironclad","Blackstone","Meridian","Pinnacle","Quantum","Sterling","Titan",
            "Solaris","Lynx","Cascade","Epoch","Fractal","Helix","Impex","Javelin",
            "Kinetic","Lumina","Mosaic","Nimbus","Onyx","Parallax","Radian","Synapse",
            "Neural","Tensor","Vector","Matrix","CloudForge","EdgePoint","DataHaven",
            "Redwood","Silverline","DeepCore","SignalWorks","SkyBridge","Cortex",
            "RailGrid","MediCore","AeroDyne","BioNorth","TerraVolt","MaritimeX",
            "Clearwater","BlueRiver","Arcadia","GreyMatter","CopperLeaf","Vaultline",
            "Packet","Node","Hash","Ledger","Sentinel","Keystone","CivicMesh",
            "BrightPath","UrbanGrid","Oceanic","Evergreen","Crescent","Polar","Monolith",
            "OptiCore","CloudNine","Quanta","Orion","Pulsar","Axiom","Verdant",
            "MetroLink","FreightOS","Skyline","NeuroVista","MedAtlas","Finora",
            "Secura","TrustBridge","DataForge","HydroLine","AgriNova","GameNest",
            "StreamWave","AdPulse","RetailHub","BuildCraft","OrbitCom","MineCore",
            "GridWorks","VoltEdge","CarePoint","FleetMind","Cardinal","OmniPay",
        ]
        suffixes = [
            "Dynamics","Systems","Labs","Industries","Holdings","Logistics","Security",
            "Technologies","Solutions","Innovations","Networks","Ventures","Capital",
            "Analytics","Robotics","Aerospace","Pharma","Finance","Media","Consulting",
            "Engineering","Services","Digital","Global","Group",
            "AI","Cloud","Compute","Data","Health","Energy","Defense","Autonomous",
            "Biotech","Fintech","Insurtech","Maritime","Space","Chain","Ledger",
            "Platform","Infrastructure","Research","Manufacturing","Mobility",
            "Payments","Observability","Telecom","Satcom","Materials",
            "Insurance","Retail","Transport","Rail","Aviation","Shipping","Mining",
            "Utilities","Gaming","Streaming","Advertising","Agritech","Datacenter",
            "Construction","Robotics","Satellite","Identity","Payments","Commerce",
            "Healthcare","Mobility","Fleet","Tickets","Procurement","Compliance",
        ]
        return f"{_pick(r, prefixes)} {_pick(r, suffixes)}"
    if ttype == "government":
        kinds = ["Ministry","Agency","Office","Directorate","Bureau","Department","Commission","Authority"]
        domains = [
            "Infrastructure","Civil Affairs","Digital Services","Transport","Health","Energy",
            "Defence","Justice","Finance","Education","Environment","Labour","Communications",
            "Border Control","Internal Affairs","Economic Development","Foreign Affairs",
            "Cybersecurity","Intelligence","Public Safety",
            "Taxation","Customs","Immigration","Civil Registry","Elections","Corrections",
            "Emergency Management","Nuclear Safety","Space Affairs","Veterans Services",
            "Public Procurement","Urban Planning","Water Resources","Food Safety",
            "Maritime Security","Aviation","Social Benefits","National Archives",
            "Public Procurement","Water Resources","Environmental Protection",
            "Emergency Services","Elections","Customs","Immigration","Utilities",
            "Courts","Police Oversight","Pension Funds","Digital Identity",
            "Disaster Response","Agriculture","Housing","Public Works",
        ]
        return f"{_pick(r, kinds)} of {_pick(r, domains)}"
    if ttype == "person":
        first = [
            "Alex","Sam","Jordan","Maya","Noah","Lina","Omar","Eva",
            "Kai","Nora","Ivan","Sofia","Yuki","Leon","Amara","Zara",
            "Remi","Theo","Hana","Elias","Mia","Lucas","Asha","Erik",
            "Priya","Marco","Leila","Finn","Camille","Dmitri","Sonia","Tariq",
            "Jean-Marc","Anna-Lisa","Mei","Hiro","Fatima","Nadia","Ibrahim","Amina",
            "Mateo","Lucia","Diego","Ines","Anika","Ravi","Sanjay","Elif",
            "Marek","Kasia","Lars","Astrid","Jamal","Noémie","Clara","Nikolai",
            "Rania","Tomas","Isabella","Chen","Sakura","Eleni","Moussa","Hugo",
            "Bastien","Maëlle","Chloé","Arthur","Sven","Freya","Kaito","Akira",
            "Mina","Yara","Samir","Aaliyah","Vikram","Neha","Carlos","Valeria",
            "Bruno","Giulia","Piotr","Magda","Andrei","Irina","Kwame","Zola",
        ]
        last = [
            "Martin","Dubois","Nguyen","Silva","Khan","Rossi","Ivanov","Moreau",
            "Schmidt","Tanaka","Patel","Okafor","Svensson","Petrov","Johansson",
            "Ferreira","Müller","Andersen","Nakamura","Bergmann","Castillo","Reyes",
            "Yamamoto","Cohen","Lindqvist","Mensah","Papadopoulos","Kowalski","Torres",
            "Fischer","Okonkwo","Haugen","Vasquez","Zimmermann","Delacroix",
            "Benali","El Mansouri","Haddad","Kaur","Singh","Zhang","Li","Chen",
            "Garcia","Hernandez","Santos","Nowak","Horvat","Novak","Kovač",
            "Peterson","Olsen","Nielsen","Lemoine","Roux","Bianchi","Ricci",
            "Sato","Kim","Park","Ionescu","Dumont","Alvarez","Rahman","Adebayo",
            "Mercier","Lefevre","Garnier","Faure","Bennett","Cooper","Morgan",
            "Nordin","Björk","Watanabe","Kobayashi","Hassan","Nasser","Sharma",
            "Mehta","Costa","Romero","Greco","Zielinski","Popescu","Diallo",
        ]
        return f"{_pick(r, first)} {_pick(r, last)}"
    if ttype == "bank":
        prefixes = [
            "Northwind","Union","Civic","Metro","Nova","Sterling","Apex","Atlas",
            "Harbor","Meridian","Pinnacle","Ironclad","Solaris","Capitol","Crest",
            "Swiss","Cayman","Singapore","Delaware","Baltic","Alpine","Pacific",
            "Continental","Frontier","Argent","Sovereign","Crown","Ledger","Vault",
            "Maritime","Helvetic","Nordic","Andean","Sahara","Orchid","TrustBridge",
            "Clearwater","Reserve","Keystone","Omni","Crescent","Evergreen",
        ]
        kinds = ["Bank","Credit Union","Finance","Capital","Invest","Savings","Trust",
                 "Custody","Exchange","DeFi","Staking","Clearing","Payments",
                 "Private Bank","Brokerage","Remittance","Card Services","Settlement",
                 "Merchant Bank","Digital Bank","Treasury"]
        return f"{_pick(r, prefixes)} {_pick(r, kinds)}"
    if ttype == "public_wifi":
        venues = [
            "Café","Bistro","Restaurant","Hotel","Library","Mall","Station",
            "Bar","Lounge","Brasserie","Hostel","Airport","Museum","Gym",
            "Co-working","University","Hospital","Cinema","Arena","Market",
        ]
        names = [
            "Aurora","Atlas","Lumen","Saffron","Harbor","Orchid","Nimbus","Cedar",
            "Soleil","Bravo","Zinc","Indigo","Cobalt","Sienna","Volta","Ember",
            "Cirrus","Dune","Flare","Grove","Quartz","Slate","Topaz","Vega",
            "Monarch","Copper","Juniper","Mirage","Riviera","Metro","Beacon",
            "Bluebird","Horizon","Pixel","Arcade","Velvet","Canal","Rooftop",
            "Terminal","Gallery","Foundry","Maple","Cinnamon","Opera","Lagoon",
            "Forum","Depot","Harlequin","Lantern","Summit","Mistral","Harborlight",
        ]
        return f"{_pick(r, venues)} {_pick(r, names)}"
    return f"Target {_pick(r, ['A','B','C','D','E','F'])}"


_COMPANY_PROFILES = [
    "software", "fintech", "healthtech", "biotech", "energy", "logistics",
    "defense", "media", "manufacturing", "cloud", "telecom", "law_firm",
    "hospital", "university", "ngo", "insurance", "retail", "transport",
    "rail", "aviation", "shipping", "mining", "oil_gas", "smart_city",
    "adtech", "gaming", "streaming", "agritech", "datacenter",
    "construction", "pharma", "robotics", "satellite", "security_vendor",
    "msp", "payment_processor",
]
_GOV_PROFILES = [
    "civil_registry", "tax", "transport", "public_safety", "health", "defense",
    "archives", "immigration", "elections", "customs", "utilities", "police",
    "courts", "procurement", "water", "environment", "education",
    "emergency_services", "housing",
]
_BANK_PROFILES = [
    "retail_bank", "crypto_custody", "clearing", "payments", "wealth",
    "private_bank", "neobank", "brokerage", "remittance", "insurance_bank",
    "atm_network", "card_processor",
]
_PUBLIC_WIFI_PROFILES = [
    "cafe", "hotel", "library", "station", "coworking", "hospitality",
    "airport", "metro", "stadium", "conference", "clinic", "campus",
    "museum", "restaurant_chain",
]


def _slug_name(name: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(name))
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")[:24] or "target"


def _target_profile(r: random.Random, ttype: str, name: str) -> str:
    low = str(name).lower()
    if ttype == "company":
        for key, profile in [
            ("health", "hospital"), ("medical", "hospital"), ("pharma", "healthtech"),
            ("bio", "biotech"), ("cloud", "cloud"), ("telecom", "telecom"),
            ("media", "media"), ("capital", "fintech"), ("finance", "fintech"),
            ("defense", "defense"), ("aero", "defense"), ("energy", "energy"),
            ("insurance", "insurance"), ("retail", "retail"), ("transport", "transport"),
            ("rail", "rail"), ("aviation", "aviation"), ("shipping", "shipping"),
            ("mining", "mining"), ("oil", "oil_gas"), ("gas", "oil_gas"),
            ("city", "smart_city"), ("advertising", "adtech"), ("gaming", "gaming"),
            ("streaming", "streaming"), ("agri", "agritech"), ("datacenter", "datacenter"),
            ("construction", "construction"), ("robotics", "robotics"), ("sat", "satellite"),
            ("security", "security_vendor"), ("payments", "payment_processor"),
        ]:
            if key in low:
                return profile
        return _pick(r, _COMPANY_PROFILES)
    if ttype == "government":
        return _pick(r, _GOV_PROFILES)
    if ttype == "bank":
        for key, profile in [("exchange", "crypto_custody"), ("custody", "crypto_custody"), ("payments", "payments")]:
            if key in low:
                return profile
        return _pick(r, _BANK_PROFILES)
    if ttype == "public_wifi":
        return _pick(r, _PUBLIC_WIFI_PROFILES)
    if ttype == "person":
        return _pick(r, [
            "freelancer", "student", "remote_worker", "crypto_user", "journalist",
            "gamer", "executive", "trader", "activist", "contractor", "researcher",
            "sysadmin",
        ])
    return "generic"


def _host_label(r: random.Random, ttype: str, role: str, profile: str = "generic", idx: int = 1) -> str:
    role = str(role)
    profile = str(profile)
    n = f"{idx:02d}"
    company = {
        "git": ["gitlab-prod", "gitea-core", "repo-mirror", "code-review", "ci-control", "jenkins-main"],
        "db": ["db-primary", "postgres-ledger", "sql-warehouse", "analytics-db", "mongo-store", "redis-cache"],
        "mail": ["mx-inbound", "mail-relay", "imap-archive", "smtp-edge"],
        "web": ["portal-prod", "web-front", "app-gateway", "customer-portal", "api-edge", "graphql-gw"],
        "vpn": ["vpn-edge", "remote-access", "wireguard-gw", "openvpn-prod", "ztna-proxy"],
        "ws": ["wkst-fin", "wkst-ops", "laptop-eng", "desktop-admin", "helpdesk-pc", "contractor-laptop"],
        "ap": ["ap-staff", "wifi-controller", "ap-lobby", "ap-office"],
    }
    specialized = {
        "hospital": {
            "git": ["emr-api", "patient-portal", "pacs-gateway"],
            "db": ["patient-db", "pharmacy-db", "lab-results-db"],
            "web": ["appointments", "emr-web", "billing-portal"],
            "ws": ["nurse-station", "doctor-wkst", "lab-terminal"],
        },
        "university": {
            "git": ["research-git", "student-code", "lab-gitlab"],
            "db": ["student-db", "grades-db", "library-db"],
            "web": ["student-portal", "moodle", "research-portal"],
            "ws": ["lab-wkst", "faculty-laptop", "library-desk"],
        },
        "telecom": {
            "git": ["netops-git", "noc-tools", "provisioning-api"],
            "db": ["subscriber-db", "billing-db", "cdr-warehouse"],
            "web": ["customer-portal", "noc-dashboard", "provisioning"],
            "vpn": ["noc-vpn", "field-access", "ops-vpn"],
        },
        "cloud": {
            "git": ["infra-git", "terraform-state", "ci-control"],
            "db": ["tenant-db", "metering-db", "object-index"],
            "web": ["console-api", "s3-gateway", "k8s-control"],
            "ws": ["sre-laptop", "build-agent", "ops-jumpbox"],
        },
        "law_firm": {
            "db": ["case-management", "client-db", "billing-ledger"],
            "web": ["client-portal", "discovery-vault", "dms-web"],
            "mail": ["privileged-mail", "mx-legal", "imap-discovery"],
        },
        "retail": {
            "db": ["pos-db", "inventory-db", "loyalty-ledger"],
            "web": ["shopfront", "merchant-api", "coupon-service"],
            "ws": ["pos-terminal", "store-manager", "stockroom-pc"],
        },
        "transport": {
            "db": ["fleet-db", "ticketing-db", "route-planner"],
            "web": ["dispatch-portal", "tracking-api", "booking-web"],
            "ws": ["dispatcher-wkst", "fleet-ops", "depot-terminal"],
        },
        "rail": {
            "db": ["ticketing-db", "signals-archive", "crew-roster"],
            "web": ["passenger-portal", "operations-board", "delay-api"],
            "ws": ["station-wkst", "signaldesk", "yard-terminal"],
        },
        "aviation": {
            "db": ["crew-db", "flightops-db", "baggage-db"],
            "web": ["flightops", "booking-api", "gate-dashboard"],
            "ws": ["ops-control", "gate-terminal", "maintenance-laptop"],
        },
        "payment_processor": {
            "db": ["card-vault", "settlement-db", "merchant-ledger"],
            "web": ["payment-api", "merchant-portal", "tokenization-gw"],
            "vpn": ["processor-vpn", "merchant-access", "audit-vpn"],
        },
        "insurance": {
            "db": ["claims-db", "policy-ledger", "actuary-warehouse"],
            "web": ["claims-portal", "broker-api", "policy-web"],
            "mail": ["claims-mail", "mx-underwriting", "broker-inbox"],
        },
        "datacenter": {
            "git": ["infra-git", "rack-automation", "dcim-ci"],
            "db": ["dcim-db", "asset-db", "power-telemetry"],
            "web": ["dcim-portal", "rack-map", "cooling-dashboard"],
        },
        "gaming": {
            "db": ["player-db", "matchmaking-db", "telemetry-warehouse"],
            "web": ["launcher-api", "matchmaker", "storefront"],
            "ws": ["gm-console", "build-agent", "anti-cheat-lab"],
        },
        "security_vendor": {
            "git": ["rules-git", "malware-lab", "sensor-ci"],
            "db": ["ioc-db", "telemetry-db", "cases-db"],
            "web": ["soc-portal", "sensor-api", "threat-feed"],
        },
    }
    bank = {
        "core": ["core-banking-api", "swift-routing", "custody-vault", "payment-switch"],
        "db": ["ledger-primary", "kyc-db", "aml-warehouse", "txn-postgres"],
        "ws": ["trader-desk", "compliance-wkst", "audit-laptop", "risk-terminal"],
    }
    gov = {
        "files": ["classified-docs", "records-archive", "citizen-files", "case-vault"],
        "gw": ["border-gateway", "secure-portal", "vpn-gateway", "firewall-edge"],
        "dns": ["dns-primary", "resolver-admin", "zone-master"],
        "vpn": ["vpn-gov-secure", "remote-access", "field-vpn"],
        "ws": ["analyst-wkst", "clerk-pc", "officer-laptop", "inspector-wkst"],
        "ap": ["ap-secure", "wifi-controller", "ap-admin"],
    }
    person = {
        "laptop": ["daily-driver", "personal-laptop", "workbook", "travel-mac"],
        "router": ["home-router", "edge-router", "fiber-gw"],
        "nas": ["home-nas", "backup-box", "media-vault"],
    }
    public = {"ap": ["ap-lobby", "guest-ap", "hotspot-gw"], "mgmt": ["guest-portal", "wifi-mgmt", "captive-portal"]}
    if ttype == "company":
        choices = specialized.get(profile, {}).get(role) or company.get(role) or [role]
    elif ttype == "government":
        choices = gov.get(role) or [role]
    elif ttype == "bank":
        choices = bank.get(role) or [role]
    elif ttype == "person":
        choices = person.get(role) or [role]
    elif ttype == "public_wifi":
        choices = public.get(role) or [role]
    else:
        choices = [role]
    base = _pick(r, choices)
    return f"{base}-{n}" if role in {"ws", "ap"} and not base.endswith(n) else base


def _make_lore_extras(r: random.Random, ttype: str, profile: str, name: str, slug: str) -> Dict[str, Any]:
    """Return profile-coherent lore fields to merge into t['lore']."""
    _first = [
        "Alex","Sam","Jordan","Maya","Noah","Lina","Omar","Eva","Kai","Nora",
        "Ivan","Sofia","Yuki","Leon","Amara","Zara","Remi","Theo","Hana","Elias",
        "Mia","Lucas","Asha","Erik","Priya","Marco","Leila","Finn","Camille","Dmitri",
    ]
    _last = [
        "Martin","Dubois","Nguyen","Silva","Khan","Rossi","Ivanov","Moreau",
        "Schmidt","Tanaka","Patel","Okafor","Svensson","Petrov","Johansson",
        "Ferreira","Andersen","Nakamura","Castillo","Reyes","Fischer","Torres",
    ]
    def _nm() -> str:
        return f"{_pick(r, _first)} {_pick(r, _last)}"
    if ttype == "company":
        return {
            "founded": r.randint(1985, 2022),
            "employees": _pick(r, ["10-50", "50-200", "200-1000", "1000-5000", "5000+"]),
            "revenue_range": _pick(r, ["<1M USD", "1-10M USD", "10-100M USD", "100M-1B USD", ">1B USD"]),
            "ceo": _nm(),
            "ciso": _nm(),
            "tech_stack": _pick(r, ["AWS/K8s", "Azure/.NET", "GCP/Go", "On-prem/VMware", "Hybrid/OpenStack"]),
            "hq": _pick(r, ["Paris, FR", "Berlin, DE", "London, UK", "Amsterdam, NL", "Zurich, CH",
                             "Dublin, IE", "Stockholm, SE", "Milan, IT", "Madrid, ES", "Warsaw, PL"]),
        }
    if ttype == "government":
        return {
            "director_general": _nm(),
            "jurisdiction": _pick(r, ["national", "regional", "municipal", "inter-agency"]),
            "org_code": f"{slug.upper()[:3]}-{r.randint(100, 999)}",
            "annual_budget": _pick(r, ["<10M EUR", "10-100M EUR", "100M-500M EUR", "500M-2B EUR", ">2B EUR"]),
            "public_site": f"https://www.{slug[:16]}.gov",
        }
    if ttype == "person":
        return {
            "age": r.randint(18, 68),
            "email": (
                f"{slug[:12]}@"
                + _pick(r, ["gmail.com", "protonmail.com", "outlook.com", "yahoo.com", "icloud.com"])
            ),
            "city": _pick(r, ["Paris", "Berlin", "London", "Amsterdam", "Madrid", "Milan",
                               "Warsaw", "Stockholm", "Vienna", "Zurich", "Lisbon", "Brussels"]),
            "devices": _pick(r, [  # type: ignore[arg-type]
                ["laptop", "smartphone"], ["laptop", "tablet", "smartphone"],
                ["desktop", "smartphone"], ["laptop"], ["nas", "laptop", "smartphone"],
            ]),
        }
    if ttype == "bank":
        _cc = _pick(r, ["FR", "DE", "GB", "NL", "CH", "IE", "SE"])
        return {
            "swift_code": f"{slug.upper()[:4]}{_cc}XX",
            "founded": r.randint(1880, 2018),
            "assets_range": _pick(r, ["<100M USD", "100M-1B USD", "1B-50B USD", "50B-500B USD", ">500B USD"]),
            "ceo": _nm(),
            "regulator": _pick(r, ["ECB", "FCA", "FINMA", "OCC", "AMF", "BaFin", "CSSF"]),
            "branches": r.randint(1, 250),
        }
    if ttype == "public_wifi":
        return {
            "operator": _pick(r, ["TelecomVendor", "CityWireless", "OpenNet", "ConnectHub", "FreeZone Networks"]),
            "daily_visitors": r.randint(30, 2000),
            "hours": _pick(r, ["07:00-23:00", "08:00-22:00", "24/7", "06:00-00:00", "09:00-21:00"]),
            "monthly_data_tb": round(r.uniform(0.1, 15.0), 1),
        }
    return {}


def _rich_files(r: random.Random, ttype: str, profile: str, name: str) -> Dict[str, str]:
    slug = _slug_name(name)
    ref = f"{slug.upper()[:4]}-{r.randint(1000, 9999)}"
    ip = f"10.{r.randint(1, 223)}.{r.randint(0, 254)}.{r.randint(1, 254)}"
    owner = _pick(r, ["ops", "admin", "security", "finance", "it", "compliance", "field"])
    files: Dict[str, str] = {
        "/home/dev/.env": (
            f"APP_ENV=production\nSERVICE_NAME={slug}\nAPI_BASE=https://api.{slug}.internal\n"
            f"DB_HOST={ip}\nDB_USER={owner}\nDB_PASS=rotate-{r.randint(1000,9999)}\n"
        ),
        "/home/dev/runbook.md": (
            f"# {name} runbook\n\nRef: {ref}\nOwner: {owner}@{slug}.internal\n"
            f"- Rotate VPN credentials monthly\n- Review exposed services after maintenance windows\n"
            f"- Escalation bridge: bridge-{r.randint(10,99)}.{slug}.internal\n"
        ),
        "/var/log/access.log": (
            f'{ip} - - [{r.randint(1,28):02d}/Apr/2026:0{r.randint(0,9)}:{r.randint(10,59)}:12 +0000] "GET /login HTTP/1.1" 200 {r.randint(900,5000)}\n'
            f'{ip} - - [{r.randint(1,28):02d}/Apr/2026:1{r.randint(0,9)}:{r.randint(10,59)}:02 +0000] "POST /api/session HTTP/1.1" 302 {r.randint(120,900)}\n'
        ),
        "/home/dev/inbox.eml": (
            f"From: {owner}@{slug}.internal\nTo: dev@{slug}.internal\nSubject: {ref} access review\n\n"
            f"Please confirm whether {ip} is still used by the legacy integration. The audit team found stale credentials in the last export.\n"
        ),
    }
    if profile == "hospital":
        files.update({
            "/srv/emr/patient_sample.csv": "patient_id,last_name,ward,status\nP-10241,Martin,cardiology,admitted\nP-10242,Nguyen,oncology,followup\n",
            "/srv/pacs/README.txt": f"PACS gateway for {name}\nDICOM sync window: 01:00-03:00 UTC\n",
        })
    elif profile == "university":
        files.update({
            "/srv/students/grades_sample.csv": "student_id,course,grade\nS-10021,CS-401,A-\nS-10022,NET-220,B+\n",
            "/srv/research/grant_notes.txt": f"Grant {ref}\nPartner lab: {slug}-ai\nDataset embargo until 2026-Q4\n",
        })
    elif profile == "telecom":
        files.update({
            "/srv/netops/cdr_sample.csv": "msisdn,tower,bytes\n+33123450001,TWR-17,2441201\n+33123450002,TWR-21,921114\n",
            "/etc/netflow/exporter.conf": f"collector={ip}:2055\nsite={slug}\nretention_days=90\n",
        })
    elif profile == "cloud":
        files.update({
            "/srv/tenants/buckets.txt": f"{slug}-backups\n{slug}-logs\ncustomer-archive-{r.randint(10,99)}\n",
            "/etc/kubernetes/admin.conf": f"cluster: {slug}-prod\nserver: https://{ip}:6443\nuser: admin\n",
        })
    elif profile == "law_firm":
        files.update({
            "/srv/cases/case_index.csv": "case_id,client,status\nL-9021,Atlas Holdings,discovery\nL-9022,Private Client,settlement\n",
            "/srv/discovery/privilege_log.txt": f"Privilege log {ref}\nDo not email outside counsel without encryption.\n",
        })
    elif profile == "retail":
        files.update({
            "/srv/pos/terminals.csv": "terminal_id,store,last_batch\nPOS-01,central,02:10\nPOS-02,outlet,02:14\n",
            "/srv/loyalty/export_sample.csv": "customer_id,points,email\nC-10021,4220,redacted@example.net\n",
        })
    elif profile in ("transport", "rail", "aviation", "shipping"):
        files.update({
            "/srv/ops/dispatch.csv": "unit,route,status\nVH-17,R-204,delayed\nVH-22,R-118,on_time\n",
            "/srv/ticketing/recon_notes.txt": f"Ticketing reconciliation {ref}\nLegacy API endpoint: https://tickets.{slug}.internal/v1\n",
        })
    elif profile in ("insurance", "insurance_bank"):
        files.update({
            "/srv/claims/open_claims.csv": "claim_id,policy,status\nCL-20411,POL-91,review\nCL-20412,POL-44,fraud_check\n",
            "/home/dev/underwriting_notes.txt": f"Underwriting model refresh {ref}\nBroker SSO token rotation pending.\n",
        })
    elif profile in ("payment_processor", "card_processor"):
        files.update({
            "/srv/payments/merchant_routes.csv": "merchant_id,route,status\nM-901,settlement-a,active\nM-902,settlement-b,hold\n",
            "/home/dev/tokenization_memo.txt": f"Token vault migration {ref}\nAudit token prefix: tok_{r.randint(10000,99999)}\n",
        })
    elif profile in ("datacenter", "msp"):
        files.update({
            "/srv/dcim/rack_inventory.csv": "rack,power_kw,tenant\nR12,8.4,finance\nR18,6.1,health\n",
            "/home/dev/customer_access.md": f"# Customer remote access\njumpbox=jump-{slug}.internal\nrotation={ref}\n",
        })
    elif profile == "gaming":
        files.update({
            "/srv/game/player_sample.csv": "player_id,rank,last_login\nP-991,diamond,2026-04-02\nP-992,gold,2026-04-03\n",
            "/srv/anticheat/ban_queue.txt": f"Anti-cheat queue {ref}\nKernel driver rollout delayed.\n",
        })
    elif profile == "security_vendor":
        files.update({
            "/srv/threat/ioc_feed.txt": f"feed={slug}-ioc\nstale_api_key=feed-{r.randint(1000,9999)}-rotate\n",
            "/srv/cases/customer_incidents.csv": "case_id,customer,severity\nIR-2041,redacted,high\nIR-2042,redacted,medium\n",
        })
    elif profile == "software":
        files.update({
            "/srv/ci/pipeline.yml": (
                f"name: {slug}-ci\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
                f"    steps:\n      - uses: actions/checkout@v3\n      - run: make test\n"
            ),
            "/home/dev/deployment_checklist.md": (
                f"# {name} Deploy Checklist\n\nRef: {ref}\n"
                f"- [ ] Run test suite (>95% coverage)\n- [ ] Bump semver in version.txt\n"
                f"- [ ] Push to registry: registry.{slug}.internal\n- [ ] Notify {owner}@{slug}.internal\n"
            ),
        })
    elif profile == "fintech":
        files.update({
            "/srv/compliance/aml_report.csv": (
                f"tx_id,amount,flag,reviewed_by\n"
                f"TX-{r.randint(10000,99999)},{r.randint(5000,500000)},suspicious,{owner}\n"
                f"TX-{r.randint(10000,99999)},{r.randint(100,4999)},ok,auto\n"
            ),
            "/srv/api/openapi.yaml": (
                f"openapi: 3.0.0\ninfo:\n  title: {name} API\n  version: v{r.randint(1,4)}.{r.randint(0,9)}\n"
                f"servers:\n  - url: https://api.{slug}.internal\n"
            ),
            "/home/dev/kyc_backlog.txt": (
                f"KYC Backlog — Ref: {ref}\nPending reviews: {r.randint(5,120)}\n"
                f"Oldest pending: {r.randint(3,60)} days\nAssigned to: {owner}@{slug}.internal\n"
            ),
        })
    elif profile in ("biotech", "pharma"):
        files.update({
            "/srv/lab/trial_data.csv": (
                "trial_id,compound,phase,status\n"
                f"T-{r.randint(1000,9999)},{slug.upper()[:6]}-{r.randint(10,99)},"
                f"phase{r.randint(1,3)},{'ongoing' if r.random()<0.6 else 'paused'}\n"
            ),
            "/home/dev/compound_notes.txt": (
                f"Compound Notes — Ref: {ref}\nLead molecule: {slug.upper()[:4]}-{r.randint(100,999)}\n"
                f"Target: {_pick(r, ['oncology','cardiology','neurology','immunology','infectious disease'])}\n"
                f"Regulatory filing: {'EMA' if r.random()<0.6 else 'FDA'} — milestone {r.randint(2025,2027)}-Q{r.randint(1,4)}\n"
            ),
            "/srv/qc/batch_release.csv": (
                "batch_id,product,status,released_by\n"
                f"B-{r.randint(1000,9999)},{slug[:6].upper()}-API,released,{owner}\n"
                f"B-{r.randint(1000,9999)},{slug[:6].upper()}-FIN,quarantine,quality\n"
            ),
        })
    elif profile in ("energy", "oil_gas"):
        files.update({
            "/srv/scada/plc_config.conf": (
                f"[SCADA]\nsite={slug}\nmaster_ip={ip}\n"
                f"protocol={'modbus_tcp' if r.random()<0.5 else 'dnp3'}\n"
                f"poll_interval=5\nalarm_threshold=95\n"
            ),
            "/home/dev/grid_status.csv": (
                "unit,output_mw,status\n"
                f"G-{r.randint(1,12)},{r.randint(100,800)},{'online' if r.random()<0.85 else 'maintenance'}\n"
                f"G-{r.randint(1,12)},{r.randint(100,800)},{'online' if r.random()<0.85 else 'standby'}\n"
            ),
            "/home/dev/maintenance_schedule.txt": (
                f"Planned outage: {ref}\nUnit: G-{r.randint(1,12)}\n"
                f"Window: {r.randint(2025,2026)}-{r.randint(1,12):02d}-{r.randint(1,28):02d} 00:00-06:00 UTC\n"
                f"Approved by: {owner}@{slug}.internal\n"
            ),
        })
    elif profile == "logistics":
        files.update({
            "/srv/wms/shipment_log.csv": (
                "shipment_id,origin,dest,status\n"
                f"SHP-{r.randint(10000,99999)},"
                f"{_pick(r,['CDG','FRA','LHR','AMS'])},{_pick(r,['JFK','ORD','LAX','MIA'])},"
                f"{'in_transit' if r.random()<0.7 else 'delivered'}\n"
            ),
            "/home/dev/fleet_tracking.txt": (
                f"Fleet update — Ref: {ref}\nActive units: {r.randint(10,500)}\n"
                f"Delayed routes: {r.randint(0,20)}\nLast GPS sync: {r.randint(0,23):02d}:{r.randint(0,59):02d} UTC\n"
            ),
        })
    elif profile == "defense":
        files.update({
            "/srv/contracts/classified_index.txt": (
                f"CONTRACT INDEX — {ref}\nClassification: RESTRICTED\n"
                f"Active contracts: {r.randint(3,40)}\n"
                f"Procurement officer: {owner}@{slug}.internal\n"
            ),
            "/home/dev/procurement_brief.txt": (
                f"Procurement Brief — Ref: {ref}\n"
                f"Line item: {_pick(r,['secure comms upgrade','radar maintenance','logistics software','network hardening'])}\n"
                f"Budget: EUR {r.randint(1,50)*1_000_000:,}\n"
                f"Approval: {'approved' if r.random()<0.5 else 'pending clearance'}\n"
            ),
        })
    elif profile in ("media", "streaming"):
        files.update({
            "/srv/cms/content_schedule.csv": (
                "content_id,title,publish_at,status\n"
                f"C-{r.randint(1000,9999)},{slug[:8].title()} Weekly,"
                f"2026-{r.randint(1,12):02d}-{r.randint(1,28):02d},scheduled\n"
                f"C-{r.randint(1000,9999)},Highlights Reel,"
                f"2026-{r.randint(1,12):02d}-{r.randint(1,28):02d},draft\n"
            ),
            "/home/dev/ad_revenue.txt": (
                f"Ad Revenue Report — Ref: {ref}\n"
                f"Q{r.randint(1,4)} CPM avg: EUR {round(r.uniform(0.5, 8.0), 2)}\n"
                f"Impressions served: {r.randint(1,500)*1_000_000:,}\nFill rate: {r.randint(72,99)}%\n"
            ),
        })
    elif profile == "adtech":
        files.update({
            "/srv/bidder/rtb_config.json": (
                f'{{"endpoint":"https://rtb.{slug}.internal/bid",'
                f'"timeout_ms":{r.randint(50,150)},'
                f'"floor_price_cpm":{round(r.uniform(0.1, 2.0), 2)}}}\n'
            ),
            "/home/dev/campaign_report.csv": (
                "campaign_id,impressions,clicks,spend_eur\n"
                f"CAM-{r.randint(1000,9999)},{r.randint(100000,5000000)},"
                f"{r.randint(500,50000)},{r.randint(200,20000)}\n"
            ),
        })
    elif profile == "manufacturing":
        files.update({
            "/srv/mes/production_log.csv": (
                "line,units_today,defect_rate_pct,shift\n"
                f"L-{r.randint(1,8)},{r.randint(200,5000)},{round(r.uniform(0.1,3.5),2)},morning\n"
                f"L-{r.randint(1,8)},{r.randint(200,5000)},{round(r.uniform(0.1,3.5),2)},evening\n"
            ),
            "/home/dev/quality_memo.txt": (
                f"QC Memo — Ref: {ref}\nNCR count this week: {r.randint(0,15)}\n"
                f"ISO 9001 audit: {r.randint(2025,2027)}-Q{r.randint(1,4)}\n"
                f"Corrective actions pending: {r.randint(0,8)}\n"
            ),
        })
    elif profile == "ngo":
        files.update({
            "/srv/donors/contribution_log.csv": (
                "donor_id,amount_eur,date,program\n"
                f"D-{r.randint(1000,9999)},{r.randint(500,50000)},"
                f"2026-{r.randint(1,12):02d}-{r.randint(1,28):02d},field_ops\n"
                f"D-{r.randint(1000,9999)},{r.randint(100,5000)},"
                f"2026-{r.randint(1,12):02d}-{r.randint(1,28):02d},admin\n"
            ),
            "/home/dev/field_report.txt": (
                f"Field Report — Ref: {ref}\n"
                f"Region: {_pick(r,['West Africa','SEA','MENA','Eastern Europe','LAC'])}\n"
                f"Beneficiaries reached: {r.randint(500,50000)}\n"
                f"Incident: {'none' if r.random()<0.7 else 'security advisory issued'}\n"
            ),
        })
    elif profile == "construction":
        files.update({
            "/srv/projects/site_log.csv": (
                "project_id,site,progress_pct,safety_incidents\n"
                f"PRJ-{r.randint(100,999)},{slug[:8].upper()} Tower,{r.randint(10,95)},{r.randint(0,5)}\n"
            ),
            "/home/dev/procurement_orders.csv": (
                "po_id,supplier,material,value_eur\n"
                f"PO-{r.randint(1000,9999)},SupplierCo,"
                f"{_pick(r,['steel','concrete','copper wiring','HVAC units'])},{r.randint(10000,500000)}\n"
            ),
        })
    elif profile == "robotics":
        files.update({
            "/srv/fleet/robot_status.csv": (
                "robot_id,model,status,battery_pct\n"
                f"R-{r.randint(100,999)},{slug[:6].upper()}-MK{r.randint(1,5)},"
                f"{'operational' if r.random()<0.8 else 'maintenance'},{r.randint(20,100)}\n"
            ),
            "/home/dev/firmware_notes.txt": (
                f"Firmware Notes — Ref: {ref}\n"
                f"Version: fw-{r.randint(2,8)}.{r.randint(0,15)}.{r.randint(0,9)}\n"
                f"Pending rollout: {r.randint(12,80)} units — rollback window {r.randint(24,72)}h\n"
            ),
        })
    elif profile == "satellite":
        files.update({
            "/srv/ground/telemetry_snapshot.txt": (
                f"SAT-ID: {slug.upper()[:4]}-{r.randint(100,999)}\n"
                f"Orbit: {'LEO' if r.random()<0.6 else 'GEO'} — {r.randint(400,35800)} km\n"
                f"Signal: {'nominal' if r.random()<0.85 else 'degraded'}\n"
                f"Next contact window: {r.randint(0,23):02d}:{r.randint(0,59):02d} UTC\n"
            ),
            "/home/dev/mission_plan.txt": (
                f"Mission Plan — Ref: {ref}\n"
                f"Payload: {_pick(r,['earth observation','comms relay','weather monitoring','navigation'])}\n"
                f"Operator: {owner}@{slug}.internal — Launch: {r.randint(2024,2028)}-Q{r.randint(1,4)}\n"
            ),
        })
    elif profile == "agritech":
        files.update({
            "/srv/sensors/field_data.csv": (
                "field_id,temp_c,soil_humidity_pct,ndvi\n"
                f"F-{r.randint(1,50)},{round(r.uniform(8.0,35.0),1)},{r.randint(20,80)},{round(r.uniform(0.3,0.9),2)}\n"
            ),
            "/home/dev/harvest_forecast.txt": (
                f"Harvest Forecast — Ref: {ref}\n"
                f"Crop: {_pick(r,['wheat','corn','soybean','rapeseed','sunflower'])}\n"
                f"Projected yield: {r.randint(2,12)} t/ha — risk: {_pick(r,['drought','frost','flood','pest'])}\n"
            ),
        })
    elif profile == "mining":
        files.update({
            "/srv/ops/extraction_log.csv": (
                "shaft,ore_grade_pct,tons_extracted,status\n"
                f"S-{r.randint(1,20)},{round(r.uniform(0.5,8.0),2)},{r.randint(100,5000)},"
                f"{'active' if r.random()<0.8 else 'suspended'}\n"
            ),
            "/home/dev/safety_report.txt": (
                f"Safety Report — Ref: {ref}\nLTI incidents this month: {r.randint(0,4)}\n"
                f"Gas readings: {'normal' if r.random()<0.85 else 'elevated — ventilation check required'}\n"
                f"Next inspection: 2026-{r.randint(1,12):02d}-{r.randint(1,28):02d}\n"
            ),
        })
    elif profile == "smart_city":
        files.update({
            "/srv/iot/sensor_map.csv": (
                "sensor_id,type,location,status\n"
                f"SNS-{r.randint(1000,9999)},traffic,{slug[:6]}-junction-{r.randint(1,50)},"
                f"{'online' if r.random()<0.9 else 'offline'}\n"
                f"SNS-{r.randint(1000,9999)},air_quality,{slug[:6]}-park-{r.randint(1,20)},"
                f"{'online' if r.random()<0.9 else 'offline'}\n"
            ),
            "/home/dev/city_ops_brief.txt": (
                f"City Ops Brief — Ref: {ref}\nActive incidents: {r.randint(0,10)}\n"
                f"Traffic congestion index: {round(r.uniform(0.2, 1.0), 2)}\n"
                f"Scheduled maintenance: {r.randint(3,15)} assets\n"
            ),
        })
    elif profile == "healthtech":
        files.update({
            "/srv/platform/patient_api.yml": (
                f"service: patient-api\nversion: v{r.randint(1,4)}.{r.randint(0,9)}\n"
                f"base_url: https://api.{slug}.internal\nauth: oauth2\ndata_residency: EU\n"
            ),
            "/home/dev/interop_notes.txt": (
                f"Interop Notes — Ref: {ref}\n"
                f"HL7 FHIR R{r.randint(3,5)} compliance: {'partial' if r.random()<0.4 else 'full'}\n"
                f"Partner EHR: {_pick(r,['Epic','Cerner','OpenMRS','Medidata'])}\n"
                f"Pending cert: {_pick(r,['ISO 27001','SOC 2 Type II','HDS','HIPAA BAA'])}\n"
            ),
        })
    elif profile == "civil_registry":
        files.update({
            "/srv/registry/birth_index.csv": (
                "record_id,year,district,status\n"
                f"R-{r.randint(10000,99999)},{r.randint(1990,2026)},central,"
                f"{'indexed' if r.random()<0.9 else 'pending'}\n"
                f"R-{r.randint(10000,99999)},{r.randint(1990,2026)},west,indexed\n"
            ),
            "/home/dev/digitisation_memo.txt": (
                f"Digitisation Memo — Ref: {ref}\n"
                f"Records migrated: {r.randint(10000,500000):,} / {r.randint(500000,2000000):,}\n"
                f"Format: {_pick(r,['XML-SDTF','GEDCOM','BP-RNIPP','CSV-ISO8601'])}\n"
                f"Deadline: 2026-Q{r.randint(2,4)}\n"
            ),
        })
    elif profile == "tax":
        files.update({
            "/srv/tax/pending_audits.csv": (
                "case_id,taxpayer_id,year,amount_eur,status\n"
                f"AUD-{r.randint(10000,99999)},TP-{r.randint(100000,999999)},"
                f"{r.randint(2021,2025)},{r.randint(5000,500000)},"
                f"{'open' if r.random()<0.5 else 'closed'}\n"
            ),
            "/home/dev/compliance_notice.txt": (
                f"Compliance Notice — Ref: {ref}\n"
                f"Directive: {_pick(r,['DAC7','FATCA','CRS','BEPS Pillar II'])}\n"
                f"Deadline: 2026-{r.randint(1,12):02d}-{r.randint(1,28):02d}\n"
                f"Contact: {owner}@{slug}.gov\n"
            ),
        })
    elif profile == "police":
        files.update({
            "/srv/dispatch/incident_log.csv": (
                "incident_id,type,district,status\n"
                f"INC-{r.randint(10000,99999)},"
                f"{_pick(r,['disturbance','theft','traffic','suspicious activity'])},"
                f"d{r.randint(1,12):02d},{'closed' if r.random()<0.6 else 'open'}\n"
            ),
            "/home/dev/case_brief.txt": (
                f"Case Brief — Ref: {ref}\n"
                f"Operation: {_pick(r,['IRONGATE','SILENTWATCH','BLUEWALL','NIGHTFALL'])}\n"
                f"Status: {'ongoing' if r.random()<0.5 else 'closed'}\n"
                f"Lead: {owner}@{slug}.gov.int\n"
            ),
        })
    elif profile == "courts":
        files.update({
            "/srv/cases/docket.csv": (
                "case_id,type,filed,status\n"
                f"CASE-{r.randint(1000,9999)}/{r.randint(2022,2026)},"
                f"{_pick(r,['criminal','civil','appeal','administrative'])},"
                f"2026-{r.randint(1,12):02d}-{r.randint(1,28):02d},"
                f"{'pending' if r.random()<0.5 else 'adjourned'}\n"
            ),
            "/home/dev/sentencing_notes.txt": (
                f"Sentencing Notes — Ref: {ref}\nJudge: {owner}@{slug}.courts.int\n"
                f"Open deliberations: {r.randint(2,30)}\n"
                f"Next session: 2026-{r.randint(1,12):02d}-{r.randint(1,28):02d}\n"
            ),
        })
    elif profile == "immigration":
        files.update({
            "/srv/visa/applications_queue.csv": (
                "app_id,nationality,type,status\n"
                f"VA-{r.randint(100000,999999)},"
                f"{_pick(r,['MAR','TUN','UKR','IND','CHN','BRA'])},student,"
                f"{'processing' if r.random()<0.6 else 'approved'}\n"
                f"VA-{r.randint(100000,999999)},"
                f"{_pick(r,['NGA','EGY','PHL','VNM','MEX'])},work,processing\n"
            ),
            "/home/dev/processing_memo.txt": (
                f"Processing Memo — Ref: {ref}\nBacklog: {r.randint(100,5000)} applications\n"
                f"Avg processing time: {r.randint(5,45)} days\nFlag queue: {r.randint(0,80)} cases\n"
            ),
        })
    elif profile == "customs":
        files.update({
            "/srv/manifest/shipment_declarations.csv": (
                "decl_id,origin,hs_code,status\n"
                f"DEC-{r.randint(100000,999999)},{_pick(r,['CN','US','TR','IN','MA'])},"
                f"{r.randint(1000,9999)},{'cleared' if r.random()<0.7 else 'hold'}\n"
            ),
            "/home/dev/seizure_log.txt": (
                f"Seizure Log — Ref: {ref}\nItems detained this week: {r.randint(1,40)}\n"
                f"Category: {_pick(r,['counterfeit goods','undeclared currency','prohibited substances','endangered species'])}\n"
            ),
        })
    elif profile == "elections":
        files.update({
            "/srv/rolls/voter_extract.csv": (
                "district_id,registered,active,last_updated\n"
                f"D-{r.randint(1,50)},{r.randint(5000,200000)},{r.randint(3000,180000)},"
                f"2026-{r.randint(1,12):02d}-{r.randint(1,28):02d}\n"
            ),
            "/home/dev/audit_checklist.txt": (
                f"Election Audit — Ref: {ref}\nObservers accredited: {r.randint(20,500)}\n"
                f"System audit: {'passed' if r.random()<0.8 else 'pending remediation'}\n"
                f"Chain of custody: {'intact' if r.random()<0.9 else 'review required'}\n"
            ),
        })
    elif profile in ("utilities", "water", "environment"):
        files.update({
            "/srv/ops/asset_register.csv": (
                "asset_id,type,zone,status\n"
                f"AST-{r.randint(1000,9999)},"
                f"{_pick(r,['pump station','water tower','treatment plant','substation'])},"
                f"zone-{r.randint(1,12)},{'operational' if r.random()<0.9 else 'maintenance'}\n"
            ),
            "/home/dev/incident_report.txt": (
                f"Incident Report — Ref: {ref}\n"
                f"Event: {_pick(r,['pressure anomaly','chlorine level alert','power fluctuation','sensor fault'])}\n"
                f"Resolution: {'resolved' if r.random()<0.75 else 'ongoing'}\n"
                f"Notified: {owner}@{slug}.gov.int\n"
            ),
        })
    elif profile == "education":
        files.update({
            "/srv/erp/enrollment_stats.csv": (
                "institution_id,enrolled,staff,year\n"
                f"SCH-{r.randint(100,999)},{r.randint(200,5000)},{r.randint(20,400)},2026\n"
            ),
            "/home/dev/inspection_memo.txt": (
                f"Inspection Memo — Ref: {ref}\nInstitutions audited: {r.randint(5,80)}\n"
                f"Non-compliant: {r.randint(0,15)}\n"
                f"Key issue: {_pick(r,['digital infrastructure','staff shortage','curriculum gaps','safety'])}\n"
            ),
        })
    elif profile == "emergency_services":
        files.update({
            "/srv/dispatch/call_log.csv": (
                "call_id,type,units_dispatched,status\n"
                f"CALL-{r.randint(10000,99999)},"
                f"{_pick(r,['fire','medical','rescue','hazmat'])},{r.randint(1,8)},"
                f"{'resolved' if r.random()<0.7 else 'active'}\n"
            ),
            "/home/dev/resource_allocation.txt": (
                f"Resource Allocation — Ref: {ref}\n"
                f"Active units: {r.randint(10,80)}\nOn standby: {r.randint(5,40)}\n"
                f"Mutual aid: {'active' if r.random()<0.3 else 'none'}\n"
            ),
        })
    elif profile == "housing":
        files.update({
            "/srv/registry/property_index.csv": (
                "parcel_id,type,district,status\n"
                f"PAR-{r.randint(100000,999999)},"
                f"{_pick(r,['residential','commercial','mixed'])},d{r.randint(1,12):02d},"
                f"{'registered' if r.random()<0.9 else 'disputed'}\n"
            ),
            "/home/dev/permit_backlog.txt": (
                f"Permit Backlog — Ref: {ref}\nPending applications: {r.randint(50,1500)}\n"
                f"Avg approval time: {r.randint(10,90)} days\nHigh-priority: {r.randint(0,30)}\n"
            ),
        })
    elif profile == "crypto_custody":
        files.update({
            "/srv/custody/wallet_registry.csv": (
                "wallet_id,currency,type,balance_btc_eq\n"
                f"W-{r.randint(10000,99999)},BTC,cold,{round(r.uniform(0.5,250.0),4)}\n"
                f"W-{r.randint(10000,99999)},ETH,hot,{round(r.uniform(1.0,500.0),4)}\n"
            ),
            "/home/dev/cold_storage_memo.txt": (
                f"Cold Storage Memo — Ref: {ref}\n"
                f"HSM model: {_pick(r,['Thales Luna','Utimaco CryptoServer','AWS CloudHSM'])}\n"
                f"Key ceremony: scheduled {r.randint(2025,2027)}-Q{r.randint(1,4)}\n"
                f"Multi-sig quorum: {r.randint(2,5)}-of-{r.randint(5,9)}\n"
            ),
        })
    elif profile == "neobank":
        files.update({
            "/srv/api/rate_limits.json": (
                f'{{"env":"production","limits":{{"transactions_per_sec":{r.randint(100,2000)},'
                f'"onboarding_per_min":{r.randint(10,200)}}}}}\n'
            ),
            "/home/dev/onboarding_stats.csv": (
                "date,signups,kyc_passed,kyc_failed\n"
                f"2026-{r.randint(1,12):02d}-{r.randint(1,28):02d},"
                f"{r.randint(200,5000)},{r.randint(150,4500)},{r.randint(5,200)}\n"
            ),
        })
    elif profile == "brokerage":
        files.update({
            "/srv/trading/positions_snapshot.csv": (
                "account_id,instrument,position,unrealised_pnl_eur\n"
                f"ACC-{r.randint(10000,99999)},"
                f"{_pick(r,['AAPL','MSFT','NVDA','BTC-USD','SPY'])},"
                f"{r.randint(1,500)},{round(r.uniform(-10000,50000),2)}\n"
            ),
            "/home/dev/risk_memo.txt": (
                f"Risk Memo — Ref: {ref}\nVaR (99%, 1d): EUR {r.randint(10000,500000):,}\n"
                f"Margin calls today: {r.randint(0,15)}\nRisk officer: {owner}@{slug}.internal\n"
            ),
        })
    elif profile in ("clearing", "payments", "remittance"):
        files.update({
            "/srv/settlement/batch_log.csv": (
                "batch_id,txn_count,value_eur,status\n"
                f"BATCH-{r.randint(10000,99999)},{r.randint(100,50000)},{r.randint(100000,50000000):,},"
                f"{'settled' if r.random()<0.85 else 'pending'}\n"
            ),
            "/home/dev/reconciliation_note.txt": (
                f"Reconciliation Note — Ref: {ref}\nFailed txns today: {r.randint(0,30)}\n"
                f"Nostro imbalance: EUR {r.randint(0,100000)}\nEscalated to: {owner}@{slug}.internal\n"
            ),
        })
    elif profile in ("wealth", "private_bank"):
        files.update({
            "/srv/clients/portfolio_summary.csv": (
                "client_id,aum_eur,risk_profile,advisor\n"
                f"CLI-{r.randint(1000,9999)},{r.randint(500000,50000000):,},"
                f"{'conservative' if r.random()<0.5 else 'balanced'},{owner}\n"
            ),
            "/home/dev/client_meeting_notes.txt": (
                f"Meeting Notes — Ref: {ref}\nClient: [REDACTED per banking secrecy]\n"
                f"AUM discussed: EUR {r.randint(1,50)*1_000_000:,}\n"
                f"Allocation change: +{r.randint(5,30)}% alternatives\nAdvisor: {owner}@{slug}.internal\n"
            ),
        })
    elif profile == "atm_network":
        files.update({
            "/srv/atm/fleet_status.csv": (
                "atm_id,location,cash_pct,status\n"
                f"ATM-{r.randint(1000,9999)},{slug[:6].upper()}-central,"
                f"{r.randint(10,100)},{'online' if r.random()<0.9 else 'offline'}\n"
                f"ATM-{r.randint(1000,9999)},{slug[:6].upper()}-airport,"
                f"{r.randint(10,100)},{'online' if r.random()<0.9 else 'cash_low'}\n"
            ),
            "/home/dev/replenishment_schedule.txt": (
                f"Replenishment Schedule — Ref: {ref}\nUnits below threshold: {r.randint(0,20)}\n"
                f"Next cash run: 2026-{r.randint(1,12):02d}-{r.randint(1,28):02d} {r.randint(6,10):02d}:00 UTC\n"
                f"Carrier: {_pick(r,['Brinks','G4S','Loomis','Garda'])}\n"
            ),
        })
    return files


def _target_primary_ip(target: Dict[str, Any]) -> str:
    for h in target.get("hosts") or []:
        if isinstance(h, dict) and h.get("ip"):
            return str(h.get("ip"))
    return "0.0.0.0"


def _target_first_files(target: Dict[str, Any]) -> Dict[str, str]:
    for h in target.get("hosts") or []:
        if not isinstance(h, dict):
            continue
        om = h.get("os_model")
        if not isinstance(om, dict):
            continue
        files = om.get("files")
        if isinstance(files, dict):
            return files
    return {}


def _build_world_relations(r: random.Random, targets: List[dict]) -> List[dict]:
    candidates = [t for t in targets if isinstance(t, dict)]
    if len(candidates) < 2:
        return []
    relations: List[dict] = []
    relation_types = [
        ("vendor", "managed service contract"),
        ("client", "recurring data exchange"),
        ("partner", "shared API integration"),
        ("incident", "recent suspicious login review"),
        ("legal", "contract and discovery archive"),
        ("payment", "settlement and billing route"),
        ("supplier", "supplier portal access"),
        ("msp", "managed IT support tunnel"),
        ("subsidiary", "shared corporate identity tenant"),
        ("regulator", "regulatory reporting feed"),
        ("auditor", "quarterly audit evidence exchange"),
        ("insurance_claim", "breach insurance claim package"),
        ("shared_idp", "shared identity provider trust"),
        ("vpn_trust", "site-to-site VPN trust"),
        ("data_processor", "personal data processing agreement"),
        ("breach_response", "incident response coordination"),
        ("hosting_provider", "hosted infrastructure account"),
    ]
    max_rel = min(max(3, len(candidates) // 2), len(candidates) * 2)
    seen = set()
    for _ in range(max_rel):
        a, b = r.sample(candidates, 2)
        aid = str(a.get("target_id", ""))
        bid = str(b.get("target_id", ""))
        if not aid or not bid or (aid, bid) in seen:
            continue
        seen.add((aid, bid))
        rtype, label = _pick(r, relation_types)  # type: ignore[arg-type]
        rel = {
            "relation_id": f"rel_{len(relations):04d}",
            "type": rtype,
            "label": label,
            "source_target_id": aid,
            "target_target_id": bid,
            "source_name": str(a.get("name", "")),
            "target_name": str(b.get("name", "")),
            "target_ip": _target_primary_ip(b),
            "confidence": _pick(r, ["low", "medium", "high"]),
            "since": f"{r.randint(2022, 2026)}-{r.randint(1, 12):02d}-{r.randint(1, 28):02d}",
            "relation_strength": _pick(r, ["weak", "normal", "strong", "critical"]),
            "data_type": _pick(r, ["billing", "identity", "support", "logs", "payments", "health", "legal", "telemetry"]),
            "shared_service": _pick(r, ["vpn", "sso", "api", "sftp", "helpdesk", "billing", "siem", "backup"]),
            "evidence_path": _pick(r, ["/home/dev/relations.md", "/home/dev/osint_notes.txt"]),
        }
        relations.append(rel)
    for rel in relations:
        a = next((t for t in candidates if str(t.get("target_id", "")) == rel["source_target_id"]), None)
        if not isinstance(a, dict):
            continue
        lore = a.setdefault("lore", {})
        if isinstance(lore, dict):
            refs = lore.setdefault("relations", [])
            if isinstance(refs, list):
                refs.append(rel)
        files = _target_first_files(a)
        if files is not None:
            path = "/home/dev/relations.md"
            existing = str(files.get(path, ""))
            files[path] = (
                existing
                + f"- {rel['since']} {rel['label']} with {rel['target_name']} "
                + f"({rel['target_ip']}) confidence={rel['confidence']} relation_id={rel['relation_id']} "
                + f"service={rel['shared_service']} data={rel['data_type']}\n"
            )
            files["/home/dev/osint_notes.txt"] = (
                str(files.get("/home/dev/osint_notes.txt", ""))
                + f"Observed {rel['type']} link: {rel['source_name']} -> {rel['target_name']} via {rel['target_ip']} "
                + f"marker={rel['relation_id']} evidence={rel['evidence_path']}\n"
            )
    return relations


_WALLET_CURRENCIES = ["NXC", "ETH", "BTC", "XMR", "SOL", "LTC"]
_WALLET_BALANCE_RANGES = {
    "company":    (500,   8_000),
    "government": (1_000, 15_000),
    "person":     (50,    800),
    "bank":       (8_000, 60_000),
    "public_wifi":(0,     0),
    "isp":        (0,     0),
    "service":    (0,     0),
}
_WALLET_PROBS = {
    "company": 0.55, "government": 0.20, "person": 0.35,
    "bank": 1.0, "public_wifi": 0.0,
}


def _security_for_balance(balance: int) -> str:
    if balance < 500:
        return "low"
    if balance < 2_000:
        return "medium"
    if balance < 10_000:
        return "high"
    return "elite"


def _gen_wallets(r: random.Random, ttype: str, name: str, tid: str,
                 economy_mult: float = 1.0) -> List[dict]:
    effective_type = "bank" if any(kw in name.lower() for kw in ("bank", "credit", "finance", "capital", "invest")) else ttype
    prob = _WALLET_PROBS.get(effective_type, _WALLET_PROBS.get(ttype, 0.0))
    if r.random() > prob:
        return []
    lo, hi = _WALLET_BALANCE_RANGES.get(effective_type, _WALLET_BALANCE_RANGES.get(ttype, (0, 0)))
    if hi == 0:
        return []
    lo = int(lo * economy_mult)
    hi = int(hi * economy_mult)
    n_wallets = 1 if effective_type in ("person",) else r.randint(1, 3 if effective_type == "bank" else 2)
    wallets: List[dict] = []
    for wi in range(n_wallets):
        balance = r.randint(lo, hi)
        currency = _pick(r, _WALLET_CURRENCIES)
        sec = _security_for_balance(balance)
        addr_seed = hashlib.sha256(f"{tid}:{wi}:{balance}".encode("utf-8")).hexdigest()[:16]
        address = "0x" + addr_seed.upper()
        # Key file path — embedded in target's primary host filesystem
        kf_candidates = [
            f"/home/dev/.{currency.lower()}/wallet.key",
            f"/root/.{currency.lower()}/private.key",
            f"C/Users/admin/AppData/Roaming/{currency}/wallet.key",
        ]
        key_file = _pick(r, kf_candidates)
        wallets.append({
            "wallet_id": f"{tid}_w{wi:02d}",
            "currency": currency,
            "balance": balance,
            "address": address,
            "security": sec,
            "key_file": key_file,
        })
    return wallets


def generate_world_auto(
    seed: int,
    size: str,
    difficulty: str,
    types: List[str],
    region_id: str = "eu",
    wifi_density: str = "medium",
    districts_mode: str = "auto",
    economy_mult: float = 1.0,
) -> Dict[str, Any]:
    r = random.Random(int(seed))
    n_targets = {"S": 15, "M": 45, "L": 140, "XL": 550}.get(str(size).upper(), 45)

    base_districts = {"S": 3, "M": 6, "L": 12, "XL": 24}.get(str(size).upper(), 6)
    dmode = str(districts_mode or "auto").lower()
    if dmode == "low":
        n_districts = max(2, int(round(base_districts * 0.6)))
    elif dmode == "high":
        n_districts = int(round(base_districts * 1.4))
    else:
        n_districts = int(base_districts)

    world = make_empty_world(seed)
    world["generated_at"] = _now_ts()
    world["regions"] = [{"region_id": region_id, "name": region_id.upper()}]
    world["difficulty"] = str(difficulty)

    _district_name_pool = [
        "Downtown","OldTown","Riverside","WestSide","EastSide","Harbor","Uptown","Industrial",
        "Midtown","NorthGate","SouthEnd","FinancialDistrict","TechHub","GreenwoodPark",
        "CentralStation","UnionSquare","MarketPlace","Docklands","Suburbs","SiliconFlats",
        "CopperHill","BayArea","CrestView","NightCity","Waterfront","GlassQuarter",
        "NeonAlley","RedLight","Sector7","HighGround","LowerCity","InnerRing","OuterRing",
        "NewHaven","Crossroads","Junction","TheGrid","BlackMarket","UpperEast","LowerWest",
        "ArcLight","CrimsonHills","SteelYard","GranitePark","IvoryTower","ShadowBend",
        "VaultRow","DataPlaza","Nexus","Terminus",
        "CanalWard","HospitalQuarter","CampusNorth","AeroCorridor","Portside",
        "CivicCenter","CourtRow","WarehouseBelt","FoundryBlocks","GardenLoop",
        "MuseumMile","StadiumWalk","MetroSpine","EnergyPark","RailYard",
        "InsuranceRow","MerchantArcade","CloudCampus","ResearchTriangle",
    ]
    _shuffled_names = list(_district_name_pool)
    r.shuffle(_shuffled_names)
    _kind_weights = {
        "residential": 3, "business": 3, "mixed": 4, "industrial": 2,
        "financial": 2, "civic": 2, "campus": 1, "transport": 1,
        "medical": 1, "nightlife": 1,
    }
    _kinds_bag: List[str] = []
    for k, w in _kind_weights.items():
        _kinds_bag += [k] * w

    def _district_center(di: int, total: int) -> dict:
        cols = max(1, int(math.ceil(math.sqrt(float(total)))))
        rows = max(1, int(math.ceil(float(total) / float(cols))))
        col = di % cols
        row = di // cols
        cell_w = 1.0 / float(cols)
        cell_h = 1.0 / float(rows)
        jx = (r.random() - 0.5) * cell_w * 0.42
        jy = (r.random() - 0.5) * cell_h * 0.42
        x = (float(col) + 0.5) * cell_w + jx
        y = (float(row) + 0.5) * cell_h + jy
        return {"x": float(max(0.06, min(0.94, x))), "y": float(max(0.06, min(0.94, y)))}

    def _district_radius(total: int) -> float:
        base = 0.22 / max(1.0, math.sqrt(float(total) / 6.0))
        return float(max(0.045, min(0.18, base * (0.82 + r.random() * 0.28))))

    districts: List[dict] = []
    for di in range(int(n_districts)):
        if di < len(_shuffled_names):
            dname = _shuffled_names[di]
        else:
            dname = _shuffled_names[di % len(_shuffled_names)] + f"-{di // len(_shuffled_names) + 1}"
        districts.append(
            {
                "district_id": f"d{di:02d}",
                "name": dname,
                "kind": _pick(r, _kinds_bag),
                "center": _district_center(di, int(n_districts)),
                "radius": _district_radius(int(n_districts)),
            }
        )
    world["districts"] = districts
    _districts_by_id: Dict[str, dict] = {
        str(d.get("district_id", "")): d for d in districts if isinstance(d, dict)
    }

    from core.worldgen.places import compose_name, district_place_plan

    places: List[dict] = []
    _used_place_names: set = set()      # unicité des enseignes à l'échelle du monde
    for di in range(int(n_districts)):
        did = f"d{di:02d}"
        dref = _districts_by_id.get(did)
        cx = float((dref or {}).get("center", {}).get("x", r.random()))
        cy = float((dref or {}).get("center", {}).get("y", r.random()))
        rad = float((dref or {}).get("radius", 0.15))
        place_seq = 0

        def pxy() -> dict:
            nonlocal place_seq
            place_seq += 1
            golden = math.pi * (3.0 - math.sqrt(5.0))
            angle = float(place_seq) * golden + r.random() * 0.18
            ring = math.sqrt((float(place_seq % 17) + 0.5) / 17.5)
            dist = rad * min(0.92, 0.18 + ring * 0.74)
            return {
                "x": float(max(0.0, min(1.0, cx + math.cos(angle) * dist))),
                "y": float(max(0.0, min(1.0, cy + math.sin(angle) * dist))),
            }

        # Composition dictée par le type de quartier. Auparavant chaque district
        # recevait le même mélange (1 banque, 2-6 boutiques, 1-3 lieux divers)
        # quel que soit son type : un quartier « nightlife » comptait neuf
        # boutiques et aucun bar, un quartier « residential » aucun logement.
        # Les noms sont également composés plutôt que tirés de listes fixes,
        # trop courtes (7 noms pour 31 banques, « ByteCafe » neuf fois).
        _kind = str((dref or {}).get("kind", "mixed"))
        _seq: Dict[str, int] = {}
        for category in district_place_plan(r, _kind):
            idx = _seq.get(category, 0)
            _seq[category] = idx + 1
            places.append({
                "place_id": f"{did}:{category}:{idx}",
                "district_id": did,
                "category": category,
                "name": compose_name(r, category, _used_place_names),
                **pxy(),
            })

    weights: Dict[str, float] = {}
    for tname in types:
        weights[tname] = 1.0

    wmode = str(wifi_density or "medium").lower()
    wifi_private_p = 0.75
    if wmode == "low":
        wifi_private_p = 0.35
    elif wmode == "high":
        wifi_private_p = 0.95
    if "public_wifi" in weights:
        if wmode == "low":
            weights["public_wifi"] = 0.75
        elif wmode == "high":
            weights["public_wifi"] = 2.15
        else:
            weights["public_wifi"] = 1.4
    if "person" in weights:
        weights["person"] = 1.2
    if "government" in weights:
        weights["government"] = 0.8
    if "bank" in weights:
        weights["bank"] = 0.5  # banks are rare but impactful

    bag: List[str] = []
    for _tk, _tw in weights.items():
        bag += [_tk] * int(max(1, round(_tw * 10)))

    targets: List[dict] = []
    host_idx_by_network: Dict[str, int] = {}

    def new_host_id(nid: str) -> str:
        host_idx_by_network[nid] = host_idx_by_network.get(nid, 0)
        hid = f"{nid}:{host_idx_by_network[nid]}"
        host_idx_by_network[nid] += 1
        return hid

    def vuln_prob() -> float:
        d = str(difficulty).lower()
        if d == "easy":
            return 0.75
        if d == "hard":
            return 0.35
        if d == "insane":
            return 0.18
        return 0.55

    _district_ids = [str(d.get("district_id", "")) for d in districts if isinstance(d, dict) and d.get("district_id")] or ["d00"]
    _vp = vuln_prob()

    for i in range(int(n_targets)):
        ttype = str(bag[int(r.randrange(0, len(bag)))] if bag else "company")
        tid = f"t_{ttype}_{i:04d}"
        name = _make_target_name(r, ttype)
        profile = _target_profile(r, ttype, name)
        slug = _slug_name(name)

        did = str(_pick(r, _district_ids))
        place_id = f"{did}:{tid}"

        dref = _districts_by_id.get(did)
        cx = float((dref or {}).get("center", {}).get("x", r.random()))
        cy = float((dref or {}).get("center", {}).get("y", r.random()))
        rad = float((dref or {}).get("radius", 0.15))

        def txy() -> dict:
            return {
                "x": float(max(0.0, min(1.0, cx + (r.random() - 0.5) * 2.0 * rad))),
                "y": float(max(0.0, min(1.0, cy + (r.random() - 0.5) * 2.0 * rad))),
            }

        networks: List[dict] = []
        hosts: List[dict] = []
        ssid_name: str = "HOME"
        venue_kind: str = "cafe"
        venue: Dict[str, Any] = {}
        wifi_profile: Dict[str, Any] = {}

        def nid(suffix: str) -> str:
            return f"{tid}:{suffix}"

        def add_host(nid: str, hostname: str, os_name: str, ip: str, services: List[dict], files: Dict[str, str]) -> None:
            # Les comptes sont attribués par assign_host_accounts(), passe
            # finale qui couvre toutes les branches de création. Les poser ici
            # serait redondant, et surtout consommerait des tirages au milieu
            # de la génération : le flux aléatoire décalerait tout ce qui suit,
            # changeant le monde produit pour une seed donnée.
            hosts.append(
                {
                    "host_id": new_host_id(nid),
                    "network_id": nid,
                    "ip": ip,
                    "hostname": hostname,
                    "os": os_name,
                    "services": services,
                    "os_model": {"users": ["root", "dev"], "files": files, "suid_bins": ["/usr/bin/find"] if r.random() < 0.2 else []},
                }
            )

        if ttype == "company":
            lan_id = nid("lan")
            wifi_id = nid("wifi_staff")
            networks = [{"network_id": lan_id, "type": "lan", "district_id": did, "place_id": place_id}]
            _has_wifi_staff = r.random() < float(wifi_private_p)
            if _has_wifi_staff:
                networks.append({"network_id": wifi_id, "type": "wifi_private", "ssid": f"{slug[:12].upper()}-STAFF", "security": "wpa2", "district_id": did, "place_id": place_id})
            # Core server: git or gitlab
            git_hostname = _host_label(r, "company", "git", profile)
            git_os = _pick(r, ["Debian", "Ubuntu"])
            core_svcs = [
                {"port": 22, "name": "ssh", "version": f"OpenSSH_{r.choice(['8.4','9.0','9.3'])}", "vuln_tags": ["bruteforce"] if r.random() < _vp else []},
                {"port": 80, "name": "http", "version": f"nginx_{r.choice(['1.20','1.22','1.24'])}", "vuln_tags": ["rce_http"] if r.random() < _vp * 0.35 else []},
            ]
            add_host(lan_id, git_hostname, git_os, f"10.0.{i%200}.10", core_svcs,
                     {**_rich_files(r, "company", profile, name),
                      "/srv/git/README.md": f"# {name} internal repos\nProfile: {profile}\n",
                      "/home/dev/report.txt": _generate_doc("company", "report.txt", r)})
            # DB server (50%)
            if r.random() < 0.50:
                db_engine, db_port, db_ver = _pick(r, [("mysql",3306,"MySQL_5.7"),("postgres",5432,"PostgreSQL_14"),("mariadb",3306,"MariaDB_10.6")])  # type: ignore[arg-type]
                add_host(lan_id, _host_label(r, "company", "db", profile), "Ubuntu", f"10.0.{i%200}.21",
                         [{"port": db_port, "name": db_engine, "version": db_ver, "vuln_tags": ["weak_creds"] if r.random() < _vp else []}],
                         {**_rich_files(r, "company", profile, name),
                          "/home/dev/db_export.csv": _generate_doc("company", "db_export.csv", r)})
            # Mail server (30%)
            if r.random() < 0.30:
                add_host(lan_id, _host_label(r, "company", "mail", profile), "Debian", f"10.0.{i%200}.25",
                         [{"port": 25, "name": "smtp", "version": "Postfix_3.7", "vuln_tags": ["relay_open"] if r.random() < _vp * 0.3 else []},
                          {"port": 143, "name": "imap", "version": "Dovecot_2.3", "vuln_tags": []}],
                         {**_rich_files(r, "company", profile, name),
                          "/home/dev/inbox_summary.txt": _generate_doc("company", "inbox_summary.txt", r)})
            # Web server (40%)
            if r.random() < 0.40:
                web_os = _pick(r, ["Debian", "Ubuntu", "Alpine"])
                add_host(lan_id, _host_label(r, "company", "web", profile), web_os, f"10.0.{i%200}.80",
                         [{"port": 443, "name": "https", "version": f"nginx_{r.choice(['1.20','1.22'])}", "vuln_tags": ["rce_http"] if r.random() < _vp * 0.2 else []},
                          {"port": 80, "name": "http", "version": "redirect", "vuln_tags": []}],
                         {"/var/www/html/index.html": f"<html><title>{name}</title></html>\n",
                          "/home/dev/deploy_notes.txt": _generate_doc("company", "deploy_notes.txt", r)})
            # VPN server (20%)
            if r.random() < 0.20:
                add_host(lan_id, _host_label(r, "company", "vpn", profile), "Debian", f"10.0.{i%200}.11",
                         [{"port": 1194, "name": "openvpn", "version": "OpenVPN_2.5", "vuln_tags": ["bruteforce"] if r.random() < _vp * 0.25 else []}],
                         {"/etc/openvpn/server.conf": "port 1194\nproto udp\n"})
            # Windows workstation(s) on LAN (0–2)
            n_ws = r.randint(0, 2)
            for wi in range(n_ws):
                ws_user = _pick(r, ["alice","bob","carol","david","emma","frank","netops"])
                add_host(lan_id, _host_label(r, "company", "ws", profile, wi + 1), "Windows", f"10.0.{i%200}.{100+wi}",
                         [{"port": 445, "name": "smb", "version": "SMB_3.1", "vuln_tags": ["weak_creds"] if r.random() < _vp * 0.4 else []},
                          {"port": 3389, "name": "rdp", "version": "RDP_10", "vuln_tags": ["bruteforce"] if r.random() < _vp * 0.3 else []}],
                         {f"C/Users/{ws_user}/Documents/notes.txt": _generate_doc("company", "notes.txt", r),
                          f"C/Users/{ws_user}/Documents/work_report.txt": _generate_doc("company", "work_report.txt", r)})
            # AP host wifi_staff (last, to preserve hosts[0..N-1] ordering
            # expected by StoryEngine which uses hosts[host_index]).
            if _has_wifi_staff:
                add_host(wifi_id, _host_label(r, "company", "ap", profile), "OpenWRT", f"10.77.{i%200}.1",
                         [{"port": 80, "name": "http", "version": "uhttpd_1.0",
                           "vuln_tags": ["rce_http"] if r.random() < _vp * 0.3 else []},
                          {"port": 22, "name": "ssh", "version": "OpenSSH_7.6",
                           "vuln_tags": ["bruteforce"] if r.random() < _vp * 0.4 else []}],
                         {"/etc/config/wireless": f"config wifi-iface\n option ssid '{slug[:12].upper()}-STAFF'\n option encryption 'wpa2'\n",
                          "/root/maintenance.txt": f"AP {slug[:12].upper()}-STAFF — reboot weekly\n"})

        elif ttype == "government":
            lan_admin_id = nid("lan_admin")
            lan_ops_id = nid("lan_ops")
            wifi_id = nid("wifi_staff")
            networks = [
                {"network_id": lan_ops_id, "type": "lan", "district_id": did, "place_id": place_id},
                {"network_id": lan_admin_id, "type": "lan", "district_id": did, "place_id": place_id},
            ]
            _has_gov_wifi = r.random() < float(wifi_private_p)
            if _has_gov_wifi:
                networks.append({"network_id": wifi_id, "type": "wifi_private", "ssid": f"GOV-{slug[-10:].upper()}", "security": "wpa2", "district_id": did, "place_id": place_id})
            # Files/NAS (always) — hosts[0] must be lan_ops to match StoryEngine _NET_SUFFIX
            add_host(lan_ops_id, _host_label(r, "government", "files", profile), "Debian", f"10.11.{i%200}.10",
                     [{"port": 445, "name": "smb", "version": "Samba_4.15", "vuln_tags": ["weak_creds"] if r.random() < _vp * 0.4 else []},
                      {"port": 22, "name": "ssh", "version": "OpenSSH_8.9", "vuln_tags": []}],
                     {**_rich_files(r, "government", profile, name),
                      "/srv/docs/procedure.txt": _generate_doc("government", "procedure.txt", r),
                      "/srv/docs/classified.txt": _generate_doc("government", "classified.txt", r)})
            # Gateway (always) — hosts[1] = lan_admin
            gw_os = _pick(r, ["Windows Server", "Debian"])
            add_host(lan_admin_id, _host_label(r, "government", "gw", profile), gw_os, f"10.10.{i%200}.1",
                     [{"port": 443, "name": "https", "version": f"nginx_{r.choice(['1.18','1.20'])}", "vuln_tags": ["rce_http"] if r.random() < _vp * 0.25 else []},
                      {"port": 22, "name": "ssh", "version": "OpenSSH_7.9", "vuln_tags": ["bruteforce"] if r.random() < _vp * 0.3 else []}],
                     {"/var/log/auth.log": f"sshd: accepted from 10.10.{i%200}.50\n",
                      "/home/dev/casefile.txt": _generate_doc("government", "casefile.txt", r)})
            # DNS server (60%)
            if r.random() < 0.60:
                add_host(lan_admin_id, _host_label(r, "government", "dns", profile), "Debian", f"10.10.{i%200}.53",
                         [{"port": 53, "name": "dns", "version": "BIND_9.18", "vuln_tags": ["dns_zone_transfer"] if r.random() < _vp * 0.2 else []}],
                         {"/etc/bind/named.conf": "options { recursion yes; };"})
            # VPN server (40%)
            if r.random() < 0.40:
                add_host(lan_admin_id, _host_label(r, "government", "vpn", profile), "Debian", f"10.10.{i%200}.11",
                         [{"port": 1194, "name": "openvpn", "version": "OpenVPN_2.5", "vuln_tags": ["bruteforce"] if r.random() < _vp * 0.2 else []}],
                         {"/etc/openvpn/server.conf": "port 1194\nproto udp\n"})
            # Staff workstations (1–3)
            n_ws = r.randint(1, 3)
            for wi in range(n_ws):
                ws_user = _pick(r, ["agent","officer","analyst","clerk","supervisor","inspector"])
                add_host(lan_ops_id, _host_label(r, "government", "ws", profile, wi + 1), "Windows", f"10.11.{i%200}.{100+wi}",
                         [{"port": 445, "name": "smb", "version": "SMB_3.1", "vuln_tags": ["weak_creds"] if r.random() < _vp * 0.35 else []},
                          {"port": 3389, "name": "rdp", "version": "RDP_10", "vuln_tags": ["bruteforce"] if r.random() < _vp * 0.25 else []}],
                         {f"C/Users/{ws_user}/Documents/memo.txt": _generate_doc("government", "memo.txt", r),
                          f"C/Users/{ws_user}/Documents/report.txt": _generate_doc("government", "report.txt", r)})
            # AP host wifi_staff (last, to preserve hosts[0..N-1] ordering)
            if _has_gov_wifi:
                add_host(wifi_id, _host_label(r, "government", "ap", profile), "OpenWRT", f"10.88.{i%200}.1",
                         [{"port": 80, "name": "http", "version": "uhttpd_1.0",
                           "vuln_tags": ["rce_http"] if r.random() < _vp * 0.2 else []},
                          {"port": 22, "name": "ssh", "version": "OpenSSH_7.6",
                           "vuln_tags": ["bruteforce"] if r.random() < _vp * 0.3 else []}],
                         {"/etc/config/wireless": f"config wifi-iface\n option ssid 'GOV-{slug[-10:].upper()}'\n option encryption 'wpa2'\n",
                          "/root/maintenance.txt": "Government AP — last reboot recorded\n"})

        elif ttype == "person":
            home_id = nid("home_wifi")
            networks = []
            first_name = name.split()[0] if " " in name else name
            ssid_name = _pick(r, [f"{first_name}s_WiFi", f"HOME-{i:03d}", f"Network_{r.randint(100,999)}", f"{first_name.lower()}_home"])
            # Le réseau domestique est toujours déclaré, car les hôtes ci-dessous
            # y sont rattachés inconditionnellement. Le tirage ne décidait avant
            # que de la déclaration du réseau, pas de la création du portable :
            # quand il échouait, la cible gardait ses hôtes sans qu'aucun réseau
            # n'y mène. Mesuré sur un monde XL : 7 cibles et 14 hôtes
            # définitivement injoignables.
            # La densité wifi pilote désormais la sécurité du réseau plutôt que
            # son existence — une box mal configurée reste une box.
            if r.random() < float(wifi_private_p):
                security = "wpa2"
            else:
                security = _pick(r, ["wep", "open"])
            networks.append({"network_id": home_id, "type": "wifi_private",
                             "ssid": ssid_name, "security": security,
                             "district_id": did, "place_id": place_id})
            # Laptop (always)
            lp_os = _pick(r, ["Windows", "Ubuntu", "macOS"])
            lp_user = _pick(r, ["alice","bob","user","dev",name.split()[0].lower()])
            add_host(home_id, _host_label(r, "person", "laptop", profile), lp_os, f"192.168.{i%200}.20",
                     [{"port": 22, "name": "ssh", "version": f"OpenSSH_{r.choice(['8.2','8.4','8.9'])}", "vuln_tags": ["bruteforce"] if r.random() < _vp * 0.6 else []}],
                     {f"/home/{lp_user}/notes.txt": _generate_doc("person", "notes.txt", r),
                      f"/home/{lp_user}/journal.txt": _generate_doc("person", "journal.txt", r)})
            # Home router (50%)
            if r.random() < 0.50:
                hosts.append({
                    "host_id": f"{home_id}:router",
                    "network_id": home_id,
                    "ip": f"192.168.{i%200}.1",
                    "hostname": _host_label(r, "person", "router", profile),
                    "os": "OpenWRT",
                    "services": [
                        {"port": 80, "name": "http", "version": "uhttpd_1.0", "vuln_tags": ["rce_http"] if r.random() < _vp * 0.3 else []},
                        {"port": 22, "name": "ssh", "version": "OpenSSH_7.6", "vuln_tags": ["bruteforce"] if r.random() < _vp * 0.5 else []},
                    ],
                    "os_model": {"users": ["root","admin"], "files": {"/etc/config/wireless": f"option ssid '{ssid_name if networks else 'HOME'}'"},
                                 "suid_bins": ["/usr/bin/busybox"]},
                })
            # NAS (25%)
            if r.random() < 0.25:
                add_host(home_id, _host_label(r, "person", "nas", profile), "Debian", f"192.168.{i%200}.30",
                         [{"port": 445, "name": "smb", "version": "Samba_4.13", "vuln_tags": ["weak_creds"] if r.random() < _vp * 0.5 else []}],
                         {"/mnt/share/backup.txt": _generate_doc("person", "backup.txt", r)})

        elif ttype == "bank":
            lan_id = nid("lan")
            networks = [{"network_id": lan_id, "type": "lan", "district_id": did, "place_id": place_id}]
            _has_bank_wifi = r.random() < float(wifi_private_p) * 0.6
            _bank_wifi_id = nid("wifi_staff")
            if _has_bank_wifi:
                networks.append({"network_id": _bank_wifi_id, "type": "wifi_private",
                                  "ssid": f"{name.split()[0].upper()[:6]}-STAFF", "security": "wpa2",
                                  "district_id": did, "place_id": place_id})
            # Core banking server (always)
            add_host(lan_id, _host_label(r, "bank", "core", profile), "Debian",
                     f"10.20.{i%200}.10",
                     [{"port": 22,   "name": "ssh",   "version": "OpenSSH_9.0",  "vuln_tags": ["bruteforce"] if r.random() < _vp else []},
                      {"port": 443,  "name": "https", "version": "nginx_1.22",   "vuln_tags": ["rce_http"] if r.random() < _vp * 0.3 else []},
                      {"port": 8443, "name": "api",   "version": "express_4.18", "vuln_tags": ["sqli"] if r.random() < _vp * 0.4 else []}],
                     {**_rich_files(r, "bank", profile, name),
                      "/srv/banking/accounts.csv": _generate_doc("bank", "accounts.csv", r),
                      "/home/dev/treasury_report.txt": _generate_doc("bank", "treasury_report.txt", r),
                      "/home/dev/kyc_flags.txt": _generate_doc("bank", "kyc_flags.txt", r)})
            # Database server (always)
            db_engine, db_port, db_ver = _pick(r, [("mysql", 3306, "MySQL_8.0"), ("postgres", 5432, "PostgreSQL_15")])  # type: ignore[arg-type]
            add_host(lan_id, _host_label(r, "bank", "db", profile), "Ubuntu",
                     f"10.20.{i%200}.20",
                     [{"port": db_port, "name": db_engine, "version": db_ver,
                       "vuln_tags": ["weak_creds"] if r.random() < _vp * 0.5 else []}],
                     {"/home/dev/db_dump.sql": _generate_doc("bank", "db_dump.sql", r)})
            # Trader workstations (1-2)
            n_ws = r.randint(1, 2)
            for wi in range(n_ws):
                ws_user = _pick(r, ["trader","analyst","banker","compliance","auditor"])
                add_host(lan_id, _host_label(r, "bank", "ws", profile, wi + 1), "Windows",
                         f"10.20.{i%200}.{100+wi}",
                         [{"port": 445, "name": "smb", "version": "SMB_3.1", "vuln_tags": ["weak_creds"] if r.random() < _vp * 0.45 else []},
                          {"port": 3389,"name": "rdp", "version": "RDP_10",  "vuln_tags": ["bruteforce"] if r.random() < _vp * 0.35 else []}],
                         {f"C/Users/{ws_user}/Documents/trades.csv": _generate_doc("bank", "trades.csv", r),
                          f"C/Users/{ws_user}/Documents/audit_log.txt": _generate_doc("bank", "audit_log.txt", r)})
            # ATM console (40%)
            if r.random() < 0.40:
                add_host(lan_id, "atm-mgmt", "Debian",
                         f"10.20.{i%200}.50",
                         [{"port": 22, "name": "ssh", "version": "OpenSSH_8.2", "vuln_tags": ["bruteforce"] if r.random() < _vp * 0.6 else []},
                          {"port": 502, "name": "modbus", "version": "ATM_ctrl_1.0", "vuln_tags": ["rce_http"] if r.random() < _vp * 0.25 else []}],
                         {"/etc/atm/config.conf": "atm_count=5\nhost=10.20.0.10\n"})
            # AP host wifi_staff (last, to preserve hosts ordering)
            if _has_bank_wifi:
                add_host(_bank_wifi_id, "ap-bank", "OpenWRT", f"10.99.{i%200}.1",
                         [{"port": 80, "name": "http", "version": "uhttpd_1.0",
                           "vuln_tags": ["rce_http"] if r.random() < _vp * 0.2 else []},
                          {"port": 22, "name": "ssh", "version": "OpenSSH_7.6",
                           "vuln_tags": ["bruteforce"] if r.random() < _vp * 0.25 else []}],
                         {"/etc/config/wireless": f"config wifi-iface\n option ssid '{name.split()[0].upper()[:6]}-STAFF'\n option encryption 'wpa2'\n",
                          "/root/maintenance.txt": "Bank staff AP — strict MAC filtering enabled\n"})

        else:  # public_wifi
            venue_kind = _pick(r, ["cafe","restaurant","hotel","library","mall","train_station","bar","hostel","gym","coworking"])
            ssid = f"{name.replace(' ', '_')}_Free_WiFi"
            guest_id = nid("wifi_guest")
            networks = [{"network_id": guest_id, "type": "wifi_public", "ssid": ssid, "security": "open", "district_id": did, "place_id": place_id}]
            wifi_profile = {
                "base_clients": r.randint(4, 20),
                "peaks": {"morning": round(0.6+r.random()*0.6, 2), "noon": round(1.0+r.random()*0.8, 2),
                           "evening": round(1.2+r.random()*0.8, 2), "night": round(0.2+r.random()*0.4, 2)},
                "jitter": round(0.1 + r.random() * 0.3, 2),
            }
            venue = {"kind": venue_kind}

            ap_services = [
                {"port": 80, "name": "http", "version": "uhttpd_1.0", "vuln_tags": ["rce_http"] if r.random() < _vp * 0.4 else []},
                {"port": 22, "name": "ssh", "version": f"OpenSSH_{r.choice(['7.9','8.2'])}", "vuln_tags": ["bruteforce"] if r.random() < _vp * 0.6 else []},
            ]
            hosts.append({
                "host_id": f"{guest_id}:ap",
                "network_id": guest_id,
                "ip": f"10.42.{i%200}.1",
                "hostname": _host_label(r, "public_wifi", "ap", profile),
                "os": "OpenWRT",
                "services": ap_services,
                "os_model": {"users": ["root","admin"],
                             "files": {"/home/admin/ap_log.txt": _generate_doc("public_wifi", "ap_log.txt", r),
                                       "/etc/config/wireless": f"option ssid '{ssid}'\noption encryption 'none'\n"},
                             "suid_bins": ["/usr/bin/busybox"]},
            })
            # Management console (30%)
            if r.random() < 0.30:
                add_host(guest_id, _host_label(r, "public_wifi", "mgmt", profile), "Debian", f"10.42.{i%200}.2",
                         [{"port": 8080, "name": "http-mgmt", "version": "uhttpd_1.0", "vuln_tags": ["rce_http"] if r.random() < vuln_prob() * 0.5 else []},
                          {"port": 22, "name": "ssh", "version": "OpenSSH_8.0", "vuln_tags": ["bruteforce"] if r.random() < vuln_prob() * 0.4 else []}],
                         {"/home/admin/access_log.txt": _generate_doc("public_wifi", "access_log.txt", r)})

        t: Dict[str, Any] = {
            "target_id": tid,
            "type": ttype,
            "name": name,
            "region_id": region_id,
            "district_id": did,
            "place_id": place_id,
            "profile": profile,
            "slug": slug,
            "lore": {
                "sector": profile,
                "risk": _pick(r, ["legacy systems", "rapid growth", "understaffed IT", "outsourced operations", "recent migration"]),
                "contact_domain": f"{slug}.internal",
                **_make_lore_extras(r, ttype, profile, name, slug),
            },
            "networks": networks,
            "hosts": hosts,
        }
        if ttype == "public_wifi":
            t["venue"] = venue
            t["wifi_profile"] = wifi_profile

        wifi_pwds = []
        for n in networks:
            if not isinstance(n, dict):
                continue
            if str(n.get("type", "")) != "wifi_private":
                continue
            _nid = str(n.get("network_id", ""))
            if not _nid:
                continue
            _pwd = "wpa2-" + hashlib.sha256(f"{seed}:wifi:{_nid}".encode("utf-8")).hexdigest()[:10]
            wifi_pwds.append((_nid, str(n.get("ssid", "")), _pwd))
        if wifi_pwds:
            pivot_host = next((h for h in hosts if isinstance(h, dict) and not any(str(h.get("network_id", "")).endswith(s) for s in _WIFI_PIVOT_SUFFIXES)), None)
            if pivot_host is None and hosts:
                pivot_host = hosts[0]
            if isinstance(pivot_host, dict):
                om = pivot_host.setdefault("os_model", {})
                files = om.setdefault("files", {})
                if isinstance(files, dict):
                    host_os = str(pivot_host.get("os", "")).lower()
                    path = "C/Users/admin/Documents/wifi_passwords.txt" if "windows" in host_os else "/home/dev/wifi_passwords.txt"
                    existing = str(files.get(path, ""))
                    lines = [
                        f"WIFI_PASSWORD: {net_id} {pwd} ssid={ssid}"
                        for net_id, ssid, pwd in wifi_pwds
                    ]
                    files[path] = (existing + ("\n" if existing and not existing.endswith("\n") else "") + "\n".join(lines) + "\n")

        # ── crypto wallets ───────────────────────────────────────────────
        wallets = _gen_wallets(r, ttype, name, tid, economy_mult=float(economy_mult))
        if wallets:
            t["crypto_wallets"] = wallets
            # inject key files into the first suitable host's os_model
            for w in wallets:
                key_file = str(w.get("key_file", ""))
                if not key_file or not hosts:
                    continue
                key_content = (
                    f"WALLET_KEY\ncurrency={w['currency']}\n"
                    f"address={w['address']}\n"
                    f"private_key=ENCRYPTED_{w['wallet_id'].upper()}\n"
                )
                injected = False
                # Wallet id suffix garantit l'unicité quand plusieurs wallets
                # d'une même currency coexistent sur un même host.
                _wid_short = str(w["wallet_id"]).rsplit("_", 1)[-1]  # e.g. "w00"
                for h in hosts:
                    if not isinstance(h, dict):
                        continue
                    om = h.get("os_model")
                    if not isinstance(om, dict):
                        continue
                    _h_os = str(h.get("os", "")).lower()
                    _kf = (
                        f"C/Users/admin/AppData/Roaming/{w['currency']}/wallet_{_wid_short}.key"
                        if "windows" in _h_os
                        else f"/home/dev/.{w['currency'].lower()}/wallet_{_wid_short}.key"
                    )
                    w["key_file"] = _kf
                    files = om.get("files")
                    if not isinstance(files, dict):
                        files = {}
                    files[_kf] = key_content
                    om["files"] = files
                    injected = True
                    break
                if not injected and hosts:
                    h0 = hosts[0]
                    if isinstance(h0, dict):
                        _h0_os = str(h0.get("os", "")).lower()
                        _kf = (
                            f"C/Users/admin/AppData/Roaming/{w['currency']}/wallet_{_wid_short}.key"
                            if "windows" in _h0_os
                            else f"/home/dev/.{w['currency'].lower()}/wallet_{_wid_short}.key"
                        )
                        w["key_file"] = _kf
                        om = h0.setdefault("os_model", {})
                        om.setdefault("files", {})[_kf] = key_content

        targets.append(t)

        cat = "office"
        if ttype == "person":
            cat = "home"
        elif ttype == "government":
            cat = "government_building"
        elif ttype == "bank":
            cat = "bank"
        elif ttype == "public_wifi":
            cat = str(venue_kind)
        places.append({"place_id": place_id, "district_id": did, "category": cat, "name": name, "target_id": tid, **txy()})

    world["relations"] = _build_world_relations(r, targets)
    world["targets"] = targets

    # Invariant : aucun hôte sans compte, quelle que soit la branche qui l'a
    # créé (ancres narratives, cibles ordinaires, routeurs domestiques).
    assign_host_accounts(world, r)

    world["places"] = places
    return world


def enrich_world_places(world: Dict[str, Any], seed: int) -> int:
    """Complète chaque lieu du monde : horaires, sécurité, affluence, wifi, PNJ.

    Appelé par le pipeline **après** assemblage complet, et non pendant la
    génération : les lieux d'ancrage narratif sont ajoutés par un autre chemin,
    et enrichir trop tôt en laissait un tiers sans attributs.

    Idempotent : un lieu déjà enrichi est laissé tel quel, ce qui permet de
    ré-enrichir un monde chargé sans écraser des valeurs éditées à la main
    depuis le Dev Hub.
    """
    from core.worldgen.places import enrich_place

    places = world.get("places") or []
    kind_by_district = {
        str(d.get("district_id", "")): str(d.get("kind", "mixed"))
        for d in (world.get("districts") or []) if isinstance(d, dict)
    }
    # RNG dédié : l'enrichissement ne doit pas décaler la séquence aléatoire des
    # étapes précédentes, sous peine de changer tout le monde à seed constante.
    rp = random.Random(int(seed) ^ 0x9E3779B9)
    done = 0
    for place in places:
        if not isinstance(place, dict) or "security" in place:
            continue
        enrich_place(rp, place, kind_by_district.get(str(place.get("district_id", "")), "mixed"))
        done += 1
    return done


def generate_missions_auto(seed: int, world: Dict[str, Any], mission_count: int = 120) -> Dict[str, Any]:
    import random

    r = random.Random(int(seed) ^ 0xA5A5)
    missions: List[dict] = []

    # Index: host_entry = {hid, nid, hostname, ttype, tname, tid, has_files, has_vulns,
    #                       has_login_svc, has_exploitable_vuln, primary_login_svc}
    _LOGIN_SVCS   = {"ssh", "imap", "mysql", "smb", "rdp", "postgres", "ftp", "mariadb"}
    _EXPLOIT_TAGS = {"bruteforce", "rce_http", "weak_creds", "smb_ghost"}
    _LOGIN_PRIORITY = ["ssh", "mysql", "mariadb", "postgres", "smb", "rdp", "imap", "ftp"]

    host_entries: List[Dict[str, Any]] = []
    files_by_host: Dict[str, List[str]] = {}
    difficulty = str(world.get("difficulty", "normal")).lower()

    targets = world.get("targets")
    if isinstance(targets, list):
        for t in targets:
            if not isinstance(t, dict):
                continue
            ttype = str(t.get("type", "company"))
            tname = str(t.get("name", "Target"))
            tid   = str(t.get("target_id", ""))
            hs = t.get("hosts")
            if not isinstance(hs, list):
                continue
            for h in hs:
                if not isinstance(h, dict):
                    continue
                hid = str(h.get("host_id", ""))
                nid = str(h.get("network_id", ""))
                hostname = str(h.get("hostname", "host"))
                if not hid or not nid:
                    continue
                svcs = h.get("services") or []
                svc_names  = {str(s.get("name", "")).lower() for s in svcs if isinstance(s, dict)}
                all_vtags  = set()
                for _s in svcs:
                    if isinstance(_s, dict):
                        all_vtags.update(_s.get("vuln_tags") or [])
                has_vulns          = bool(all_vtags)
                has_login_svc      = bool(svc_names & _LOGIN_SVCS)
                has_exploitable_vuln = bool(all_vtags & _EXPLOIT_TAGS)
                primary_login_svc  = next((s for s in _LOGIN_PRIORITY if s in svc_names), "")
                os_model = h.get("os_model")
                paths: List[str] = []
                if isinstance(os_model, dict) and isinstance(os_model.get("files"), dict):
                    paths = [str(p) for p in os_model["files"].keys()
                             if not str(p).endswith(("/index.json",))]
                    files_by_host[hid] = paths
                host_entries.append({
                    "hid": hid, "nid": nid, "hostname": hostname,
                    "ttype": ttype, "tname": tname, "tid": tid,
                    "has_files": bool(paths), "has_vulns": has_vulns,
                    "has_login_svc": has_login_svc,
                    "has_exploitable_vuln": has_exploitable_vuln,
                    "primary_login_svc": primary_login_svc,
                })

    if not host_entries:
        return make_empty_missions(seed)

    # ── Client operator pool (one per target for narrative coherence) ─────────
    _operator_pool = [
        "PHANTOM", "WRAITH", "CIPHER", "DELTA-7", "SPECTRE", "NOMAD",
        "VORTEX", "SHADE", "IRONCLAD", "NEBULA", "GLITCH", "ECLIPSE",
        "STATIC", "VECTOR", "NEXUS-X", "COBALT", "MIRAGE", "TEMPEST",
        "OUTLAW", "REVENANT", "FAUST", "ARCHIVE",
    ]
    _shuffled_ops = list(_operator_pool)
    r.shuffle(_shuffled_ops)
    _target_clients: Dict[str, str] = {}
    for i, t in enumerate(targets if isinstance(targets, list) else []):
        if isinstance(t, dict):
            tid = str(t.get("target_id", f"t{i}"))
            _target_clients[tid] = _shuffled_ops[i % len(_shuffled_ops)]

    def _client_for(tid: str) -> str:
        return _target_clients.get(tid, _shuffled_ops[0])

    _host_by_tid: Dict[str, List[Dict[str, Any]]] = {}
    for _e in host_entries:
        _host_by_tid.setdefault(str(_e.get("tid", "")), []).append(_e)

    def _first_host_for_tid(tid: str) -> Dict[str, Any]:
        hs = _host_by_tid.get(str(tid), [])
        return hs[0] if hs else (host_entries[0] if host_entries else {})

    # ── Reward ranges by difficulty ───────────────────────────────────────────
    _reward_range = {
        "easy":   (50,  250),
        "normal": (150, 600),
        "hard":   (400, 1800),
        "insane": (1000, 6000),
    }.get(difficulty, (150, 600))

    def _reward(mult: float = 1.0) -> int:
        lo, hi = _reward_range
        return int((lo + r.random() * (hi - lo)) * mult)

    # ── Difficulty tiers per kind × ttype ────────────────────────────────────
    _diff_matrix: Dict[str, Dict[str, str]] = {
        "scan_network": {
            "company": "easy", "government": "easy", "person": "easy",
            "public_wifi": "easy", "bank": "medium",
        },
        "obtain_creds": {
            "company": "medium", "government": "medium", "person": "easy",
            "public_wifi": "medium", "bank": "hard",
        },
        "loot_file": {
            "company": "medium", "government": "hard", "person": "easy",
            "public_wifi": "easy", "bank": "hard",
        },
        "reach_root": {
            "company": "hard", "government": "elite", "person": "medium",
            "public_wifi": "medium", "bank": "elite",
        },
        "drain_wallet": {
            "company": "hard", "government": "elite", "person": "hard",
            "public_wifi": "hard", "bank": "elite",
        },
    }

    def _difficulty(kind: str, ttype: str) -> str:
        return _diff_matrix.get(kind, {}).get(ttype, "medium")

    # ── Tags per kind ─────────────────────────────────────────────────────────
    _tags_map: Dict[str, List[List[str]]] = {
        "scan_network": [
            ["recon", "network"], ["footprint", "passive"], ["recon", "stealth"],
            ["enumeration", "network", "noisy"],
        ],
        "obtain_creds": [
            ["credentials", "bruteforce"], ["creds", "auth", "stealth"],
            ["exploit", "auth-bypass"], ["lateral-movement", "creds"],
        ],
        "loot_file": [
            ["exfil", "stealth", "data"], ["data-theft", "document"],
            ["espionage", "loot"], ["exfil", "sensitive"],
        ],
        "reach_root": [
            ["privesc", "root", "exploit"], ["full-compromise", "root"],
            ["rootkit", "persistence"], ["escalation", "admin"],
        ],
        "drain_wallet": [
            ["crypto", "wallet", "heist"], ["blockchain", "exfil", "high-value"],
            ["financial", "drain", "crypto"], ["wallet", "stealth"],
        ],
    }

    def _tags(kind: str) -> List[str]:
        pool = _tags_map.get(kind, [["generic"]])
        return list(pool[r.randrange(0, len(pool))])

    # ── Hints per kind (contextual with hostname) ─────────────────────────────
    _hints: Dict[str, List[str]] = {
        "scan_network": [
            "Lance un scan réseau sur le segment cible. Cherche les ports 22, 80, 443, 3306.",
            "Utilise l'outil netscan pour cartographier les hôtes actifs sur {nid}.",
            "Un scan ICMP suivi d'un scan SYN sur {hostname} révélera les services exposés.",
            "Commence par identifier les hôtes actifs, puis liste leurs services ouverts.",
        ],
        "obtain_creds": [
            "Cherche un service vulnérable sur {hostname} pouvant exposer des identifiants.",
            "Utilise l'outil bruteforce pour trouver des credentials valides sur {hostname}.",
            "Un couple identifiant/mot de passe par défaut sur {hostname} peut suffire à entrer.",
            "Tente de te connecter avec des credentials faibles — beaucoup de serveurs utilisent des valeurs par défaut.",
        ],
        "obtain_creds_ssh": [
            "Tente une attaque par force brute sur le port SSH de {hostname}.",
            "Utilise l'exploit ssh_legacy sur le port 22 de {hostname} si le tag bruteforce est présent.",
            "Un accès SSH avec username=password est souvent laissé par défaut sur les serveurs générés.",
            "Lance bruteforce sur le port 22 de {hostname} — les serveurs de dev utilisent souvent admin/admin.",
        ],
        "obtain_creds_db": [
            "Le service de base de données sur {hostname} utilise probablement des credentials faibles.",
            "Exploite mysql_weak ou postgres_weak sur {hostname} — credentials par défaut fréquents.",
            "Tente root/root ou admin/admin sur le port de base de données de {hostname}.",
            "Utilise l'exploit mysql_weak sur {hostname} pour extraire les credentials de la DB.",
        ],
        "obtain_creds_smb": [
            "Le partage SMB sur {hostname} accepte souvent des credentials Windows par défaut.",
            "Essaie administrator/administrator sur le port SMB de {hostname}.",
            "Un accès RDP ou SMB avec credentials faibles est courant sur les workstations Windows.",
            "Brute-force le service SMB/RDP sur {hostname} — les comptes locaux sont souvent faibles.",
        ],
        "loot_file": [
            "Une fois l'accès obtenu sur {hostname}, navigue dans /home et /srv pour trouver le fichier.",
            "Cherche le fichier cible dans les répertoires utilisateur de {hostname}.",
            "Utilise l'explorateur de fichiers ou le terminal pour localiser et exfiltrer le document.",
            "Le fichier peut être protégé — compromets d'abord le compte administrateur.",
        ],
        "reach_root": [
            "Cherche des SUID binaires sur {hostname} — un binaire mal configuré peut suffire.",
            "Tente une escalade via sudo -l sur {hostname} après avoir obtenu un accès utilisateur.",
            "Un exploit de kernel ou un SUID misconfigured sont les voies classiques sur {hostname}.",
            "Obtiens d'abord un accès utilisateur valide, puis exploite une vulnérabilité locale.",
        ],
        "drain_wallet": [
            "Compromets {hostname}, puis cherche les fichiers .wallet ou les clés privées crypto.",
            "La clé privée du wallet se trouve souvent dans /home/<user>/.crypto/ sur {hostname}.",
            "Accède à {hostname}, localise le wallet et transfère les fonds avant détection.",
            "Cherche les processus liés aux daemons crypto sur {hostname} pour localiser le wallet.",
        ],
    }

    def _hint(kind: str, hostname: str, nid: str, entry: Optional[Dict[str, Any]] = None) -> str:
        if kind == "obtain_creds" and entry is not None:
            _ps = str(entry.get("primary_login_svc", ""))
            if _ps == "ssh":
                pool = _hints["obtain_creds_ssh"]
            elif _ps in ("mysql", "postgres", "mariadb"):
                pool = _hints["obtain_creds_db"]
            elif _ps in ("smb", "rdp"):
                pool = _hints["obtain_creds_smb"]
            else:
                pool = _hints["obtain_creds"]
        else:
            pool = _hints.get(kind, ["Analyse la cible et trouve une surface d'attaque exploitable."])
        tpl = pool[r.randrange(0, len(pool))]
        return tpl.format(hostname=hostname, nid=nid)

    # ── Lore pools per target type ────────────────────────────────────────────
    _lore: Dict[str, List[str]] = {
        "company": [
            "{tname} est une société privée dont les pratiques comptables soulèvent des questions dans le milieu.",
            "Des rumeurs circulent sur {tname} concernant des contrats gouvernementaux non déclarés.",
            "{tname} a récemment licencié son équipe sécurité — le moment est idéal.",
            "Plusieurs lanceurs d'alerte ont tenté de quitter {tname} ces derniers mois, en vain.",
            "{tname} utilise une infrastructure datant de 2015. Peu de correctifs, beaucoup de portes.",
            "L'opérateur surveille {tname} depuis des semaines. Leur réseau est prévisible.",
        ],
        "government": [
            "{tname} gère des données sensibles sur des citoyens ordinaires. Trop sensibles.",
            "Une fuite interne a confirmé que {tname} stocke des dossiers classifiés sans chiffrement.",
            "{tname} est impliqué dans un programme de surveillance non autorisé. Preuve requise.",
            "Des sources affirment que {tname} couvre une opération qui ne devrait pas exister.",
            "Le réseau de {tname} est isolé en théorie — en pratique, un VPN mal configuré l'expose.",
        ],
        "person": [
            "{tname} est un individu dont les activités en ligne attirent l'attention de plusieurs parties.",
            "Peu savent que {tname} possède des fichiers qui pourraient changer la donne.",
            "{tname} se croit protégé par son anonymat. Il a tort.",
            "L'opérateur a identifié {tname} comme cible secondaire dans une chaîne plus large.",
            "{tname} utilise le même mot de passe depuis des années. Vérifiable facilement.",
        ],
        "public_wifi": [
            "Ce réseau WiFi public est fréquenté par des cibles à haute valeur chaque jour.",
            "L'opérateur a identifié plusieurs sessions non chiffrées sur ce réseau ouvert.",
            "Ce point d'accès n'est pas supervisé. Discrétion maximale conseillée.",
            "Des credentials d'entreprise transitent régulièrement sur ce WiFi public.",
        ],
        "bank": [
            "{tname} gère plusieurs milliards de transactions. Un accès interne vaut une fortune.",
            "Les systèmes de {tname} sont anciens mais leurs wallets sont actifs et bien garnis.",
            "{tname} a refusé d'auditer sa sécurité depuis 3 ans. Opportunité rare.",
            "Une vulnérabilité dans le système de {tname} a été identifiée mais non patchée.",
        ],
    }

    def _lore_txt(ttype: str, tname: str) -> str:
        pool = _lore.get(ttype, ["{tname} est une cible d'intérêt pour l'opérateur."])
        tpl = pool[r.randrange(0, len(pool))]
        return tpl.format(tname=tname)

    # ── Build wallet index ────────────────────────────────────────────────────
    wallets_by_host: Dict[str, List[str]] = {}
    wallets_by_target: Dict[str, List[dict]] = {}
    _wallet_currency: Dict[str, str] = {}
    if isinstance(targets, list):
        for _t in targets:
            if not isinstance(_t, dict):
                continue
            _wl = _t.get("crypto_wallets")
            if not isinstance(_wl, list) or not _wl:
                continue
            _tid = str(_t.get("target_id", ""))
            wallets_by_target[_tid] = list(_wl)
            for _w in _wl:
                if isinstance(_w, dict) and _w.get("wallet_id"):
                    _wallet_currency[str(_w["wallet_id"])] = str(_w.get("currency", "NXC"))
            for _h in (_t.get("hosts") or []):
                if not isinstance(_h, dict):
                    continue
                _hid = str(_h.get("host_id", ""))
                if _hid:
                    wallets_by_host[_hid] = [str(w.get("wallet_id","")) for w in _wl if w.get("wallet_id")]

    hosts_with_wallets = [
        e for e in host_entries
        if wallets_by_host.get(e["hid"]) and (e["has_login_svc"] or e["has_exploitable_vuln"])
    ]

    # ── Weighted kind selection by target type ────────────────────────────────
    _kind_weights: Dict[str, Dict[str, int]] = {
        "company":    {"scan_network": 2, "obtain_creds": 3, "loot_file": 3, "reach_root": 2},
        "government": {"scan_network": 1, "obtain_creds": 2, "loot_file": 3, "reach_root": 4},
        "person":     {"scan_network": 1, "obtain_creds": 2, "loot_file": 5, "reach_root": 2},
        "public_wifi":{"scan_network": 4, "obtain_creds": 3, "loot_file": 2, "reach_root": 1},
        "bank":       {"scan_network": 1, "obtain_creds": 2, "loot_file": 2, "reach_root": 2, "drain_wallet": 3},
    }
    if hosts_with_wallets:
        for _tt in ("company", "person", "government"):
            _kind_weights[_tt]["drain_wallet"] = 1

    _kind_bags: Dict[str, List[str]] = {}
    for _tt, _kw in _kind_weights.items():
        _b: List[str] = []
        for _k, _w in _kw.items():
            _b += [_k] * _w
        _kind_bags[_tt] = _b
    _kind_bag_default = ["scan_network", "obtain_creds", "loot_file", "reach_root"]

    def _pick_kind(ttype: str) -> str:
        bag = _kind_bags.get(ttype, _kind_bag_default)
        return bag[r.randrange(0, len(bag))]

    # ── Title templates (15+ per kind, varied) ───────────────────────────────
    _scan_titles = [
        "Map {tname}'s Network", "Enumerate {tname} Network", "Recon: {tname}",
        "Network Sweep — {hostname}", "Probe {tname} Infrastructure",
        "Scan and Report: {tname}", "Footprint {tname}", "Silent Sweep: {tname}",
        "Network Topology — {tname}", "Expose {tname} Services",
        "Asset Discovery: {hostname}", "Passive Recon — {tname}",
        "Document {tname} Network", "Survey {tname} Network",
        "Initial Footprint: {tname}",
    ]
    _cred_titles = [
        "Extract Credentials from {hostname}", "Bruteforce {hostname}",
        "Credential Harvest: {tname}", "Break Into {hostname}",
        "Obtain Access — {tname}", "Auth Bypass: {hostname}",
        "Steal Login — {tname}", "Password Extraction: {hostname}",
        "Crack {hostname} Auth", "Login Theft: {tname}",
        "Access Keys: {hostname}", "Shadow Dump — {hostname}",
        "Compromise Auth on {hostname}", "Identity Theft: {tname}",
        "Unlock {hostname}", "Hijack Account — {tname}",
    ]
    _loot_titles = [
        "Steal {filename} from {tname}", "Exfiltrate {filename} — {hostname}",
        "Data Theft: {tname}", "Grab {filename} off {tname}",
        "Retrieve Report from {hostname}", "Document Recovery: {hostname}",
        "Silent Exfil: {filename}", "Classified Lift — {tname}",
        "Copy {filename} from {hostname}", "File Heist: {tname}",
        "Extract {filename} — {tname}", "Recover {filename} for Analysis",
        "Sensitive File Retrieval: {hostname}", "Archive Breach: {tname}",
        "Pull {filename} from {hostname}",
    ]
    _root_titles = [
        "Gain Root on {hostname}", "Compromise {hostname} — {tname}",
        "Own {hostname}", "Full Compromise: {hostname}",
        "Escalate to Root — {hostname}", "Root Access: {tname}",
        "Total Control: {hostname}", "Admin Takeover — {tname}",
        "Kernel Exploit: {hostname}", "PrivEsc: {hostname} at {tname}",
        "Break {hostname} Wide Open", "Superuser Access — {hostname}",
        "Silent Root: {tname}", "Dominance: {hostname}",
        "Systemic Compromise — {tname}",
    ]
    _drain_titles = [
        "Drain {currency} Wallet at {tname}", "Crypto Heist: {tname}",
        "Extract Funds — {tname}", "Exfiltrate {currency} from {hostname}",
        "Wallet Drain: {tname}", "Steal {currency} — {tname}",
        "Blockchain Theft: {tname}", "Empty {currency} Reserves — {hostname}",
        "Crypto Sweep: {tname}", "Fund Transfer: {currency} at {tname}",
        "Silent Drain — {hostname}", "Asset Seizure: {tname}",
        "{currency} Extraction: {hostname}", "Liquidate {tname} Wallet",
        "Cold Wallet Breach — {tname}",
    ]

    # ── Description combos (context phrase + action phrase) ──────────────────
    _scan_ctx = [
        "L'opérateur a identifié {tname} comme vecteur d'entrée prioritaire.",
        "Les activités de {tname} nécessitent une cartographie préliminaire.",
        "Avant toute infiltration, {tname} doit être correctement documenté.",
        "Aucun mouvement agressif — reconnaissance silencieuse requise sur {tname}.",
    ]
    _scan_act = [
        "Identifie tous les hôtes actifs et leurs ports sur le réseau cible.",
        "Cartographie les services exposés sans déclencher d'alertes.",
        "Documente la topologie réseau et transmets les résultats à l'opérateur.",
        "Recense les machines visibles et identifie les services potentiellement vulnérables.",
    ]
    _cred_ctx = [
        "{tname} protège ses accès avec des systèmes vieillissants.",
        "L'opérateur a besoin d'une porte d'entrée sur l'infrastructure de {tname}.",
        "Des identifiants valides sur {hostname} ouvriraient tout le réseau.",
        "Plusieurs services d'authentification sur {hostname} n'ont pas été patchés récemment.",
    ]
    _cred_act = [
        "Extrais des identifiants valides pour accéder au système cible.",
        "Force brute, exploit ou interception — obtiens un couple user/pass valide.",
        "Récupère les hashs de mots de passe ou des credentials en clair.",
        "Compromets la couche d'authentification et livre les accès à l'opérateur.",
    ]
    _loot_ctx = [
        "Un fichier critique est stocké sur les systèmes de {tname}.",
        "L'opérateur a besoin d'un document spécifique hébergé sur {hostname}.",
        "{tname} conserve des données sensibles accessibles depuis leur réseau.",
        "Le fichier cible représente une valeur considérable pour l'opérateur.",
    ]
    _loot_act = [
        "Infiltre le système et exfiltre le fichier cible sans laisser de traces.",
        "Accède au dossier cible et transmets le document à l'opérateur.",
        "Récupère le fichier classifié et livre-le via le point de dépôt habituel.",
        "Localise et copie le document — la discrétion est primordiale.",
    ]
    _root_ctx = [
        "Un accès root sur {hostname} donnerait un contrôle total sur l'infrastructure.",
        "L'opérateur exige une compromission complète de {hostname}.",
        "{tname} doit être neutralisé — accès root requis sur leur serveur principal.",
        "Le réseau de {tname} ne peut être contrôlé qu'avec des privilèges administrateur.",
    ]
    _root_act = [
        "Obtiens les droits root et confirme le contrôle total du système.",
        "Escalade les privilèges jusqu'à root — exploite les failles du système.",
        "Compromets entièrement {hostname} et établis un accès persistant.",
        "Prends le contrôle administrateur de {hostname} par tous les moyens nécessaires.",
    ]
    _drain_ctx = [
        "{tname} détient des actifs crypto significatifs sur leurs serveurs.",
        "L'opérateur a localisé un wallet de valeur sur l'infrastructure de {tname}.",
        "Les fonds crypto de {tname} sont accessibles depuis {hostname}.",
        "Un mouvement rapide sur le wallet de {tname} avant qu'ils ne détectent l'intrusion.",
    ]
    _drain_act = [
        "Compromets l'hôte, localise la clé privée et vide le wallet.",
        "Extrais les fonds blockchain avant que la cible ne détecte la brèche.",
        "Transfère silencieusement les actifs crypto vers l'adresse de l'opérateur.",
        "Localise, extrais et transfère les fonds. Discrétion absolue requise.",
    ]

    def _desc(kind: str, tname: str, hostname: str) -> str:
        ctx_map = {
            "scan_network": _scan_ctx, "obtain_creds": _cred_ctx,
            "loot_file": _loot_ctx, "reach_root": _root_ctx, "drain_wallet": _drain_ctx,
        }
        act_map = {
            "scan_network": _scan_act, "obtain_creds": _cred_act,
            "loot_file": _loot_act, "reach_root": _root_act, "drain_wallet": _drain_act,
        }
        ctx_pool = ctx_map.get(kind, _scan_ctx)
        act_pool = act_map.get(kind, _scan_act)
        ctx = _pick(r, ctx_pool).format(tname=tname, hostname=hostname)
        act = _pick(r, act_pool).format(tname=tname, hostname=hostname)
        return f"{ctx} {act}"

    def _add_relation_chains() -> None:
        relations = world.get("relations")
        if not isinstance(relations, list) or not relations:
            return
        budget = max(0, min(12, int(mission_count) // 4))
        for rel in relations[:budget]:
            if not isinstance(rel, dict):
                continue
            rid = str(rel.get("relation_id", ""))
            source_tid = str(rel.get("source_target_id", ""))
            target_tid = str(rel.get("target_target_id", ""))
            src = _first_host_for_tid(source_tid)
            dst = _first_host_for_tid(target_tid)
            if not rid or not src or not dst:
                continue
            chain_id = f"chain_{rid}"
            src_name = str(rel.get("source_name", src.get("tname", "source")))
            dst_name = str(rel.get("target_name", dst.get("tname", "target")))
            intel_path = "/home/dev/relations.md"
            client = _client_for(source_tid)
            base = len(missions)
            m0 = f"rel_{rid}_00"
            m1 = f"rel_{rid}_01"
            m2 = f"rel_{rid}_02"
            missions.extend([
                {
                    "mission_id": m0,
                    "title": f"Trace the Link — {src_name}",
                    "description": f"Map {src_name} before following its {rel.get('label', 'business link')} to {dst_name}.",
                    "network_id": src["nid"],
                    "objective": {"type": "scan_network", "network_id": src["nid"], "min_hosts": 1},
                    "reward": {"money": _reward(0.9)},
                    "client": client,
                    "difficulty": "medium",
                    "tags": ["osint", "recon", "chain"],
                    "hint": f"Commence par scanner {src['nid']} puis cherche les notes relationnelles.",
                    "lore": f"{src_name} semble connecté à {dst_name}.",
                    "target_name": src_name,
                    "chain_id": chain_id,
                    "step": 1,
                    "relation_id": rid,
                },
                {
                    "mission_id": m1,
                    "title": f"Read Relation Intel — {src_name}",
                    "description": f"Compromets {src.get('hostname', 'host')} et lis {intel_path} pour confirmer le lien vers {dst_name}.",
                    "network_id": src["nid"],
                    "objective": {"type": "read_intel_file", "host_id": src["hid"], "path": intel_path, "relation_id": rid},
                    "reward": {"money": _reward(1.2)},
                    "client": client,
                    "difficulty": "hard",
                    "tags": ["osint", "intel", "chain"],
                    "hint": f"Utilise localshell read_file sur {intel_path}; la lecture déclenchera l'intel si le fichier contient {rid}.",
                    "lore": f"Une preuve interne doit mentionner {dst_name}.",
                    "target_name": src_name,
                    "chain_id": chain_id,
                    "step": 2,
                    "requires": m0,
                    "relation_id": rid,
                    "intel_paths": [intel_path],
                },
                {
                    "mission_id": m2,
                    "title": f"Pivot to {dst_name}",
                    "description": f"Utilise l'intel découvert sur {src_name} pour identifier et pivoter vers {dst_name}.",
                    "network_id": dst["nid"],
                    "objective": {"type": "pivot_to_related_target", "relation_id": rid, "target_target_id": target_tid},
                    "reward": {"money": _reward(1.5)},
                    "client": client,
                    "difficulty": "hard",
                    "tags": ["pivot", "relation", "chain"],
                    "hint": f"Relis {intel_path}; l'event de pivot est déclenché quand le relation_id et la cible liée sont détectés.",
                    "lore": f"La relation {rid} ouvre une route vers {dst_name}.",
                    "target_name": dst_name,
                    "chain_id": chain_id,
                    "step": 3,
                    "requires": m1,
                    "relation_id": rid,
                },
            ])

    hosts_with_files     = [e for e in host_entries if e["has_files"]]
    hosts_with_vulns     = [e for e in host_entries if e["has_vulns"]]
    hosts_with_login_svc = [e for e in host_entries if e["has_login_svc"]]
    hosts_exploitable    = [e for e in host_entries if e["has_exploitable_vuln"] or e["has_login_svc"]]

    # Index réseau → nb réel d'hôtes (pour clamp min_hosts)
    hosts_per_network: Dict[str, int] = {}
    for _e in host_entries:
        hosts_per_network[_e["nid"]] = hosts_per_network.get(_e["nid"], 0) + 1

    # Anti-redundancy: track (hid, kind) pairs already used
    _used_combos: Dict[str, int] = {}

    _add_relation_chains()

    remaining_slots = max(0, int(mission_count) - len(missions))
    base_offset = len(missions)
    for i in range(remaining_slots):
        mid = f"m{i + base_offset:04d}"
        entry = host_entries[r.randrange(0, len(host_entries))]
        kind = _pick_kind(entry["ttype"])

        if kind == "loot_file" and hosts_with_files:
            entry = hosts_with_files[r.randrange(0, len(hosts_with_files))]
        elif kind == "loot_file" and not hosts_with_files:
            kind = "scan_network"
        elif kind == "obtain_creds":
            _cred_pool = hosts_with_login_svc or host_entries
            entry = _cred_pool[r.randrange(0, len(_cred_pool))]
        elif kind == "reach_root" and hosts_exploitable:
            entry = hosts_exploitable[r.randrange(0, len(hosts_exploitable))]
        elif kind == "reach_root" and not hosts_exploitable:
            kind = "scan_network"
        elif kind == "drain_wallet" and hosts_with_wallets:
            entry = hosts_with_wallets[r.randrange(0, len(hosts_with_wallets))]
        elif kind == "drain_wallet" and not hosts_with_wallets:
            kind = "reach_root"
            if hosts_exploitable:
                entry = hosts_exploitable[r.randrange(0, len(hosts_exploitable))]

        # Limit same (hid, kind) to 2 occurrences to reduce redundancy
        combo_key = f"{entry['hid']}:{kind}"
        if _used_combos.get(combo_key, 0) >= 2 and len(host_entries) > 1:
            alt_entries = [e for e in host_entries if f"{e['hid']}:{kind}" != combo_key]
            if alt_entries:
                entry = alt_entries[r.randrange(0, len(alt_entries))]
                combo_key = f"{entry['hid']}:{kind}"
        _used_combos[combo_key] = _used_combos.get(combo_key, 0) + 1

        hid, nid = entry["hid"], entry["nid"]
        hostname = entry["hostname"]
        tname, ttype, tid = entry["tname"], entry["ttype"], entry["tid"]

        diff = _difficulty(kind, ttype)
        # Reward scaled by difficulty
        diff_mult = {"easy": 0.6, "medium": 1.0, "hard": 1.8, "elite": 3.2}.get(diff, 1.0)
        money = _reward(diff_mult)

        client = _client_for(tid)
        mission_tags = _tags(kind)
        mission_hint = _hint(kind, hostname, nid, entry)
        mission_lore = _lore_txt(ttype, tname)

        if kind == "scan_network":
            tpl = _pick(r, _scan_titles)
            title = tpl.format(tname=tname, nid=nid, hostname=hostname)
            desc = _desc(kind, tname, hostname)
            _actual = hosts_per_network.get(nid, 1)
            obj: Dict[str, Any] = {"type": "scan_network", "network_id": nid, "min_hosts": r.randint(1, max(1, _actual))}
        elif kind == "obtain_creds":
            tpl = _pick(r, _cred_titles)
            title = tpl.format(tname=tname, hostname=hostname)
            desc = _desc(kind, tname, hostname)
            obj = {"type": "obtain_creds", "host_id": hid}
        elif kind == "reach_root":
            tpl = _pick(r, _root_titles)
            title = tpl.format(tname=tname, hostname=hostname)
            desc = _desc(kind, tname, hostname)
            obj = {"type": "reach_root", "host_id": hid}
        elif kind == "drain_wallet":
            wids = wallets_by_host.get(hid, [])
            wid = wids[r.randrange(0, len(wids))] if wids else ""
            currency = _wallet_currency.get(wid, "NXC")
            tpl = _pick(r, _drain_titles)
            title = tpl.format(tname=tname, hostname=hostname, currency=currency)
            desc = _desc(kind, tname, hostname)
            obj = {"type": "drain_wallet", "host_id": hid, "wallet_id": wid, "currency": currency}
        else:  # loot_file
            paths = files_by_host.get(hid, [])
            doc_paths = [p for p in paths if any(
                p.endswith(ext) for ext in (".txt", ".csv", ".json", ".md", ".log", ".conf")
            )] or paths
            if not doc_paths:
                kind = "scan_network"
                _actual = hosts_per_network.get(nid, 1)
                obj = {"type": "scan_network", "network_id": nid, "min_hosts": r.randint(1, max(1, _actual))}
                tpl = _pick(r, _scan_titles)
                title = tpl.format(tname=tname, nid=nid, hostname=hostname)
                desc = _desc("scan_network", tname, hostname)
                missions.append({
                    "mission_id": mid, "title": title, "description": desc,
                    "network_id": nid, "objective": obj,
                    "reward": {"money": money}, "client": client,
                    "difficulty": diff, "tags": mission_tags,
                    "hint": _hint("scan_network", hostname, nid), "lore": mission_lore,
                    "target_name": tname,
                })
                continue
            path = doc_paths[r.randrange(0, len(doc_paths))]
            filename = path.split("/")[-1]
            tpl = _pick(r, _loot_titles)
            title = tpl.format(tname=tname, hostname=hostname, filename=filename)
            desc = _desc(kind, tname, hostname)
            obj = {"type": "loot_file", "host_id": hid, "path": path}
            if path.startswith("C/"):
                mission_hint = "Utilise le terminal : lis le fichier Windows avec son chemin exact tel qu'affiché dans la fiche mission."

        missions.append({
            "mission_id": mid,
            "title": title,
            "description": desc,
            "network_id": nid,
            "objective": obj,
            "reward": {"money": money},
            "client": client,
            "difficulty": diff,
            "tags": mission_tags,
            "hint": mission_hint,
            "lore": mission_lore,
            "target_name": tname,
        })

    return {"schema": "missions_v2", "seed": int(seed), "missions": missions}


def _legacy_network_index(world_obj: Dict[str, Any]) -> Tuple[List[dict], int]:
    """Build legacy top-level `networks` + `hosts_total` for runtime compatibility.

    Runtime WorldState currently expects:
    - world["networks"]: [{id,name,host_count}, ...]
    - world["seed"]
    """

    nets: Dict[str, int] = {}
    targets = world_obj.get("targets")
    if isinstance(targets, list):
        for t in targets:
            if not isinstance(t, dict):
                continue
            hosts = t.get("hosts")
            if not isinstance(hosts, list):
                continue
            for h in hosts:
                if not isinstance(h, dict):
                    continue
                nid = str(h.get("network_id", ""))
                if not nid:
                    continue
                nets[nid] = int(nets.get(nid, 0)) + 1

    networks = [{"id": "lan", "name": "LAN", "host_count": 0}]
    for nid, count in sorted(nets.items()):
        if str(nid) == "lan":
            continue
        networks.append({"id": nid, "name": str(nid).upper(), "host_count": int(count)})
    total = sum([int(n.get("host_count", 0)) for n in networks])
    return networks, int(total)


def make_empty_missions(seed: int = 123) -> Dict[str, Any]:
    return {"schema": "missions_v2", "seed": int(seed), "missions": []}
