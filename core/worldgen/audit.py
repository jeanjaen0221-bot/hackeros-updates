"""core.worldgen.audit — vérification de cohérence inter-artefacts.

Vérifie les invariants qui relient ``world``, ``missions``, ``story.json``,
``story_state.json`` et le filesystem externe (``save/world_fs/``).

6 catégories :
    A. World        — unicité / graphe réseau / index legacy
    B. Missions     — références résolvables (host/network/file/wallet)
    C. Story        — rôles, ancres, assignations, file_map
    D. Filesystem   — sync disque ⇄ os_model.files
    E. Wallets      — key_file, unicité, cohérence
    F. WiFi pivot   — APs présents, mots de passe WPA2 en pivot

Usage::

    from core.worldgen.audit import audit_world
    report = audit_world(
        world=world_obj,
        missions=missions_obj,
        save_dir=Path("save"),    # pour vérifier world_fs/ (optionnel)
        story=story_obj,          # contenu de story.json (optionnel)
        story_state=state_obj,    # contenu de story_state.json (optionnel)
    )
    for issue in report.errors:
        print(issue)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


# ── Issue model ────────────────────────────────────────────────────────────

SEVERITY_ERROR = "ERR"
SEVERITY_WARNING = "WARN"

# Catégories (code → label lisible)
CAT_WORLD      = "A"
CAT_MISSIONS   = "B"
CAT_STORY      = "C"
CAT_FILESYSTEM = "D"
CAT_WALLETS    = "E"
CAT_WIFI       = "F"
CAT_SEMANTIC   = "G"
CAT_MARKET     = "H"

CATEGORY_NAMES = {
    CAT_WORLD:      "World structural",
    CAT_MISSIONS:   "Missions references",
    CAT_STORY:      "Story anchors",
    CAT_FILESYSTEM: "Filesystem sync",
    CAT_WALLETS:    "Wallets",
    CAT_WIFI:       "WiFi pivot",
    CAT_SEMANTIC:   "Semantic content",
    CAT_MARKET:     "Market world-seed",
}


@dataclass
class AuditIssue:
    category: str   # "A".."F"
    severity: str   # "ERR" | "WARN"
    code: str       # short slug, e.g. "missing_host_id"
    message: str
    context: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        ctx = ""
        if self.context:
            ctx = " " + " ".join(f"{k}={v!r}" for k, v in self.context.items())
        return f"[{self.severity}] {self.category}/{self.code}: {self.message}{ctx}"


@dataclass
class AuditReport:
    issues: List[AuditIssue] = field(default_factory=list)

    def add(self, issue: AuditIssue) -> None:
        self.issues.append(issue)

    @property
    def errors(self) -> List[AuditIssue]:
        return [i for i in self.issues if i.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> List[AuditIssue]:
        return [i for i in self.issues if i.severity == SEVERITY_WARNING]

    def by_category(self) -> Dict[str, List[AuditIssue]]:
        out: Dict[str, List[AuditIssue]] = {c: [] for c in CATEGORY_NAMES}
        for i in self.issues:
            out.setdefault(i.category, []).append(i)
        return out

    def summary(self) -> str:
        n_err = len(self.errors)
        n_warn = len(self.warnings)
        n_cats = len(CATEGORY_NAMES)
        n_ok = max(0, n_cats - len({i.category for i in self.issues}))
        return f"{n_ok} category OK · {n_warn} WARN · {n_err} ERR"


# ── Helpers ────────────────────────────────────────────────────────────────

def _targets(world: Dict[str, Any]) -> List[dict]:
    t = world.get("targets")
    return [x for x in t if isinstance(x, dict)] if isinstance(t, list) else []


def _hosts(target: dict) -> List[dict]:
    h = target.get("hosts")
    return [x for x in h if isinstance(x, dict)] if isinstance(h, list) else []


def _networks(target: dict) -> List[dict]:
    n = target.get("networks")
    return [x for x in n if isinstance(x, dict)] if isinstance(n, list) else []


def _wallets(target: dict) -> List[dict]:
    w = target.get("crypto_wallets")
    return [x for x in w if isinstance(x, dict)] if isinstance(w, list) else []


# ── Category A : World structural ──────────────────────────────────────────

def _audit_world(report: AuditReport, world: Dict[str, Any]) -> Dict[str, Any]:
    """Retourne un index partagé (hosts/networks/wallets) pour les autres checks."""
    allowed_types = {"company", "government", "person", "public_wifi", "bank"}

    target_ids: Dict[str, int] = {}
    host_ids: Dict[str, int] = {}
    wallet_ids: Dict[str, int] = {}
    wallet_addrs: Dict[str, int] = {}
    hosts_by_nid: Dict[str, List[dict]] = {}
    hosts_by_id: Dict[str, dict] = {}
    host_target: Dict[str, dict] = {}   # host_id → parent target
    target_by_id: Dict[str, dict] = {}

    for t in _targets(world):
        tid = str(t.get("target_id", ""))
        if not tid:
            report.add(AuditIssue(CAT_WORLD, SEVERITY_ERROR, "target_no_id",
                                  "target without target_id", {"name": t.get("name")}))
            continue
        target_ids[tid] = target_ids.get(tid, 0) + 1
        target_by_id[tid] = t

        ttype = str(t.get("type", ""))
        if ttype not in allowed_types:
            report.add(AuditIssue(CAT_WORLD, SEVERITY_ERROR, "bad_target_type",
                                  f"unknown target type {ttype!r}", {"target_id": tid}))

        declared_nids = {str(n.get("network_id", "")) for n in _networks(t)}

        for h in _hosts(t):
            hid = str(h.get("host_id", ""))
            if not hid:
                report.add(AuditIssue(CAT_WORLD, SEVERITY_ERROR, "host_no_id",
                                      "host without host_id", {"target_id": tid}))
                continue
            host_ids[hid] = host_ids.get(hid, 0) + 1
            hosts_by_id[hid] = h
            host_target[hid] = t

            nid = str(h.get("network_id", ""))
            if not nid:
                report.add(AuditIssue(CAT_WORLD, SEVERITY_ERROR, "host_no_network",
                                      "host missing network_id", {"host_id": hid}))
            else:
                hosts_by_nid.setdefault(nid, []).append(h)
                if declared_nids and nid not in declared_nids:
                    report.add(AuditIssue(
                        CAT_WORLD, SEVERITY_ERROR, "host_network_not_declared",
                        "host.network_id not in target.networks[]",
                        {"host_id": hid, "network_id": nid, "target_id": tid,
                         "declared": sorted(declared_nids)},
                    ))

        for w in _wallets(t):
            wid = str(w.get("wallet_id", ""))
            if not wid:
                report.add(AuditIssue(CAT_WALLETS, SEVERITY_ERROR, "wallet_no_id",
                                      "wallet without wallet_id", {"target_id": tid}))
                continue
            wallet_ids[wid] = wallet_ids.get(wid, 0) + 1
            addr = str(w.get("address", ""))
            if addr:
                wallet_addrs[addr] = wallet_addrs.get(addr, 0) + 1

    # Uniqueness
    for tid, n in target_ids.items():
        if n > 1:
            report.add(AuditIssue(CAT_WORLD, SEVERITY_ERROR, "duplicate_target_id",
                                  f"target_id used {n} times", {"target_id": tid}))
    for hid, n in host_ids.items():
        if n > 1:
            report.add(AuditIssue(CAT_WORLD, SEVERITY_ERROR, "duplicate_host_id",
                                  f"host_id used {n} times", {"host_id": hid}))
    for wid, n in wallet_ids.items():
        if n > 1:
            report.add(AuditIssue(CAT_WALLETS, SEVERITY_ERROR, "duplicate_wallet_id",
                                  f"wallet_id used {n} times", {"wallet_id": wid}))
    for addr, n in wallet_addrs.items():
        if n > 1:
            report.add(AuditIssue(CAT_WALLETS, SEVERITY_WARNING, "duplicate_wallet_address",
                                  f"wallet address reused {n} times", {"address": addr}))

    # Legacy index
    declared_networks = world.get("networks")
    if isinstance(declared_networks, list):
        declared_ids = {str(n.get("id", "")) for n in declared_networks if isinstance(n, dict)}
        used_nids = set(hosts_by_nid.keys())
        missing = used_nids - declared_ids - {"lan"}  # "lan" is a conventional seed row
        if missing:
            report.add(AuditIssue(
                CAT_WORLD, SEVERITY_WARNING, "legacy_index_missing_networks",
                "world['networks'] does not cover all used network_ids",
                {"missing_sample": sorted(list(missing))[:5], "missing_count": len(missing)},
            ))
    declared_total = world.get("hosts_total")
    if isinstance(declared_total, int) and declared_total != len(host_ids):
        report.add(AuditIssue(
            CAT_WORLD, SEVERITY_WARNING, "legacy_index_host_count_mismatch",
            "world['hosts_total'] ≠ actual host count",
            {"declared": declared_total, "actual": len(host_ids)},
        ))

    return {
        "hosts_by_id": hosts_by_id,
        "hosts_by_nid": hosts_by_nid,
        "host_target": host_target,
        "target_by_id": target_by_id,
    }


# ── Category B : Missions ───────────────────────────────────────────────────

_LOGIN_SVCS = {"ssh", "imap", "mysql", "smb", "rdp", "postgres", "ftp", "mariadb"}
_EXPLOIT_TAGS = {
    "bruteforce", "rce_http", "weak_creds", "smb_ghost",
    "sqli", "relay_open", "dns_zone_transfer", "local_privesc",
}


def _audit_missions(
    report: AuditReport,
    world: Dict[str, Any],
    missions: Dict[str, Any],
    idx: Dict[str, Any],
) -> None:
    mission_list = missions.get("missions") if isinstance(missions, dict) else None
    if not isinstance(mission_list, list):
        report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "no_missions_list",
                              "missions object has no 'missions' list"))
        return

    hosts_by_id: Dict[str, dict] = idx["hosts_by_id"]
    hosts_by_nid: Dict[str, List[dict]] = idx["hosts_by_nid"]
    target_by_id: Dict[str, dict] = idx["target_by_id"]

    # Build wallet index host-level
    wallets_by_id: Dict[str, dict] = {}
    wallet_to_target: Dict[str, str] = {}
    for tid, t in target_by_id.items():
        for w in _wallets(t):
            wid = str(w.get("wallet_id", ""))
            if wid:
                wallets_by_id[wid] = w
                wallet_to_target[wid] = tid

    # Target names (for target_name cross-check)
    target_names = {str(t.get("name", "")) for t in target_by_id.values() if t.get("name")}

    mission_ids: Dict[str, int] = {}
    for m in mission_list:
        if not isinstance(m, dict):
            report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "bad_mission_entry",
                                  "mission entry is not a dict"))
            continue
        mid = str(m.get("mission_id", ""))
        if not mid:
            report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "mission_no_id",
                                  "mission without mission_id",
                                  {"title": m.get("title", "")}))
            continue
        mission_ids[mid] = mission_ids.get(mid, 0) + 1

        obj = m.get("objective")
        if not isinstance(obj, dict):
            report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "no_objective",
                                  "mission missing objective", {"mission_id": mid}))
            continue
        otype = str(obj.get("type", ""))
        declared_nid = str(m.get("network_id", ""))

        # target_name cross-check
        tname = str(m.get("target_name", ""))
        if tname and tname not in target_names:
            report.add(AuditIssue(CAT_MISSIONS, SEVERITY_WARNING, "target_name_unknown",
                                  "mission.target_name does not match any target.name",
                                  {"mission_id": mid, "target_name": tname}))

        if otype == "scan_network":
            nid = str(obj.get("network_id", ""))
            if not nid:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "scan_no_network",
                                      "scan_network without network_id", {"mission_id": mid}))
            elif nid not in hosts_by_nid:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "scan_unknown_network",
                                      "scan_network targets a network with 0 host",
                                      {"mission_id": mid, "network_id": nid}))
            else:
                min_hosts = int(obj.get("min_hosts", 1))
                actual = len(hosts_by_nid[nid])
                if min_hosts > actual:
                    report.add(AuditIssue(
                        CAT_MISSIONS, SEVERITY_ERROR, "scan_min_hosts_too_high",
                        "min_hosts exceeds actual host count",
                        {"mission_id": mid, "network_id": nid,
                         "min_hosts": min_hosts, "actual": actual},
                    ))

        elif otype in ("obtain_creds", "reach_root"):
            hid = str(obj.get("host_id", ""))
            if not hid:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, f"{otype}_no_host",
                                      f"{otype} without host_id", {"mission_id": mid}))
            elif hid not in hosts_by_id:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, f"{otype}_unknown_host",
                                      f"{otype} targets non-existent host",
                                      {"mission_id": mid, "host_id": hid}))
            else:
                host = hosts_by_id[hid]
                svcs = host.get("services") or []
                svc_names = {str(s.get("name", "")).lower() for s in svcs if isinstance(s, dict)}
                all_tags = set()
                for s in svcs:
                    if isinstance(s, dict):
                        all_tags.update(s.get("vuln_tags") or [])
                if otype == "obtain_creds" and not (svc_names & _LOGIN_SVCS):
                    report.add(AuditIssue(
                        CAT_MISSIONS, SEVERITY_WARNING, "obtain_creds_no_login_svc",
                        "obtain_creds on host without a login-capable service",
                        {"mission_id": mid, "host_id": hid, "services": sorted(svc_names)},
                    ))
                if otype == "reach_root" and not (all_tags & _EXPLOIT_TAGS) and not (svc_names & _LOGIN_SVCS):
                    report.add(AuditIssue(
                        CAT_MISSIONS, SEVERITY_WARNING, "reach_root_not_exploitable",
                        "reach_root on host with no exploitable vuln nor login service",
                        {"mission_id": mid, "host_id": hid},
                    ))

        elif otype == "loot_file":
            hid = str(obj.get("host_id", ""))
            path = str(obj.get("path", ""))
            if not hid:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "loot_no_host",
                                      "loot_file without host_id", {"mission_id": mid}))
            elif hid not in hosts_by_id:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "loot_unknown_host",
                                      "loot_file targets non-existent host",
                                      {"mission_id": mid, "host_id": hid}))
            elif not path:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "loot_no_path",
                                      "loot_file without path", {"mission_id": mid}))
            else:
                host = hosts_by_id[hid]
                files = (host.get("os_model") or {}).get("files") or {}
                if path not in files:
                    report.add(AuditIssue(
                        CAT_MISSIONS, SEVERITY_ERROR, "loot_path_not_in_host",
                        "loot_file path not present in host's os_model.files",
                        {"mission_id": mid, "host_id": hid, "path": path},
                    ))

        elif otype == "drain_wallet":
            wid = str(obj.get("wallet_id", ""))
            hid = str(obj.get("host_id", ""))
            currency = str(obj.get("currency", ""))
            if not wid:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "drain_no_wallet",
                                      "drain_wallet without wallet_id", {"mission_id": mid}))
            elif wid not in wallets_by_id:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "drain_unknown_wallet",
                                      "drain_wallet references unknown wallet_id",
                                      {"mission_id": mid, "wallet_id": wid}))
            else:
                wallet = wallets_by_id[wid]
                if currency and str(wallet.get("currency", "")) != currency:
                    report.add(AuditIssue(
                        CAT_MISSIONS, SEVERITY_WARNING, "drain_currency_mismatch",
                        "mission.currency ≠ wallet.currency",
                        {"mission_id": mid, "wallet_id": wid,
                         "mission": currency, "wallet": wallet.get("currency")},
                    ))
                if hid:
                    expected_tid = wallet_to_target.get(wid, "")
                    actual_t = idx["host_target"].get(hid)
                    actual_tid = str(actual_t.get("target_id", "")) if actual_t else ""
                    if actual_tid and expected_tid and actual_tid != expected_tid:
                        report.add(AuditIssue(
                            CAT_MISSIONS, SEVERITY_ERROR, "drain_host_target_mismatch",
                            "drain_wallet host does not belong to wallet's target",
                            {"mission_id": mid, "wallet_id": wid,
                             "host_id": hid, "host_target": actual_tid,
                             "wallet_target": expected_tid},
                        ))

        elif otype == "read_intel_file":
            hid = str(obj.get("host_id", ""))
            path = str(obj.get("path", ""))
            if not hid:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "intel_no_host",
                                      "read_intel_file without host_id", {"mission_id": mid}))
            elif hid not in hosts_by_id:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "intel_unknown_host",
                                      "read_intel_file targets non-existent host",
                                      {"mission_id": mid, "host_id": hid}))
            elif not path:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "intel_no_path",
                                      "read_intel_file without path", {"mission_id": mid}))
            else:
                host = hosts_by_id[hid]
                files = (host.get("os_model") or {}).get("files") or {}
                if path not in files:
                    report.add(AuditIssue(
                        CAT_MISSIONS, SEVERITY_ERROR, "intel_path_not_in_host",
                        "read_intel_file path not present in host's os_model.files",
                        {"mission_id": mid, "host_id": hid, "path": path},
                    ))

        elif otype == "pivot_to_related_target":
            rel_id = str(obj.get("relation_id", ""))
            target_id = str(obj.get("target_target_id", ""))
            rels = world.get("relations") or []
            rel = next((x for x in rels if isinstance(x, dict) and str(x.get("relation_id", "")) == rel_id), None)
            if not rel_id:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "pivot_no_relation",
                                      "pivot_to_related_target without relation_id", {"mission_id": mid}))
            elif not isinstance(rel, dict):
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "pivot_unknown_relation",
                                      "pivot_to_related_target references unknown relation",
                                      {"mission_id": mid, "relation_id": rel_id}))
            elif target_id and str(rel.get("target_target_id", "")) != target_id:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "pivot_target_mismatch",
                                      "pivot target does not match relation target",
                                      {"mission_id": mid, "relation_id": rel_id, "target_target_id": target_id}))

        elif otype == "clean_logs":
            hid = str(obj.get("host_id", ""))
            if not hid:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "clean_logs_no_host",
                                      "clean_logs without host_id", {"mission_id": mid}))
            elif hid not in hosts_by_id:
                report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "clean_logs_unknown_host",
                                      "clean_logs targets non-existent host",
                                      {"mission_id": mid, "host_id": hid}))

        # network_id at mission level
        if declared_nid and declared_nid not in hosts_by_nid:
            report.add(AuditIssue(
                CAT_MISSIONS, SEVERITY_WARNING, "mission_nid_no_hosts",
                "mission.network_id has no host in the world",
                {"mission_id": mid, "network_id": declared_nid},
            ))

    for mid, n in mission_ids.items():
        if n > 1:
            report.add(AuditIssue(CAT_MISSIONS, SEVERITY_ERROR, "duplicate_mission_id",
                                  f"mission_id used {n} times", {"mission_id": mid}))


# ── Category C : Story ─────────────────────────────────────────────────────

_STORY_FILES_EXPECTED: Dict[str, List[str]] = {
    "company": [
        "/srv/git/README.md", "/srv/git/deploy_notes.txt",
        "/home/dev/report.txt", "/home/dev/db_export.csv", "/home/dev/inbox_summary.txt",
        "/home/dev/relations.md", "/var/log/audit.log", "/srv/git/nexus_arch.md",
        "/etc/prism/node.conf",
    ],
    "government": [
        "/srv/docs/classified.txt", "/srv/docs/procedure.txt",
        "/home/dev/casefile.txt", "/srv/docs/access_review.log",
        "/srv/docs/intercept_policy.md", "/var/log/gateway.log",
    ],
    "public_wifi": ["/home/admin/ap_log.txt", "/home/admin/beacon_cache.log", "/home/admin/clients.csv"],
    "person":      ["/home/user/notes.txt", "/home/user/contacts.json", "/home/user/dead_drop.txt"],
    "bank": [
        "/srv/banking/accounts.csv", "/home/dev/treasury_report.txt",
        "/home/dev/kyc_flags.txt", "/srv/banking/custody_ledger.csv",
        "/var/log/aml_review.log",
    ],
}


def _audit_story(
    report: AuditReport,
    world: Dict[str, Any],
    idx: Dict[str, Any],
    story: Optional[Dict[str, Any]],
    story_state: Optional[Dict[str, Any]],
) -> None:
    if not story:
        return  # no story.json → skip (category stays empty)

    roles = story.get("roles")
    if not isinstance(roles, dict):
        report.add(AuditIssue(CAT_STORY, SEVERITY_ERROR, "no_roles",
                              "story.json has no 'roles' dict"))
        return
    beats = story.get("beats")
    if not isinstance(beats, list):
        report.add(AuditIssue(CAT_STORY, SEVERITY_ERROR, "no_beats",
                              "story.json has no 'beats' list"))
        return
    supported_objectives = {
        "scan_network", "obtain_creds", "loot_file", "reach_root", "drain_wallet",
        "read_intel_file", "pivot_to_related_target", "clean_logs",
    }
    beat_ids: Dict[str, int] = {}
    objective_counts: Dict[str, int] = {}
    acts_seen = set()
    file_map_all = story.get("file_map") or {}
    if not isinstance(file_map_all, dict):
        file_map_all = {}
    for b in beats:
        if not isinstance(b, dict):
            continue
        bid = str(b.get("beat_id", ""))
        if not bid:
            report.add(AuditIssue(CAT_STORY, SEVERITY_ERROR, "beat_no_id",
                                  "story beat without beat_id"))
            continue
        beat_ids[bid] = beat_ids.get(bid, 0) + 1
        try:
            acts_seen.add(int(b.get("act", 1)))
        except Exception:
            acts_seen.add(1)
        obj_type = str(b.get("objective_type", ""))
        objective_counts[obj_type] = objective_counts.get(obj_type, 0) + 1
        if obj_type not in supported_objectives:
            report.add(AuditIssue(CAT_STORY, SEVERITY_ERROR, "unsupported_story_objective",
                                  "story beat objective_type is not supported by StoryEngine",
                                  {"beat_id": bid, "objective_type": obj_type}))
        role = str(b.get("target_role", ""))
        if role not in roles:
            report.add(AuditIssue(CAT_STORY, SEVERITY_ERROR, "beat_unknown_role",
                                  "story beat references an unknown target_role",
                                  {"beat_id": bid, "target_role": role}))
        fk = b.get("file_key")
        if fk and str(fk) not in file_map_all:
            report.add(AuditIssue(CAT_STORY, SEVERITY_ERROR, "beat_unknown_file_key",
                                  "story beat references file_key absent from file_map",
                                  {"beat_id": bid, "file_key": fk}))
        if obj_type == "read_intel_file" and not (b.get("intel_path") or b.get("path") or fk):
            report.add(AuditIssue(CAT_STORY, SEVERITY_ERROR, "intel_missing_path",
                                  "read_intel_file beat has no intel_path/path/file_key",
                                  {"beat_id": bid}))
        if obj_type == "pivot_to_related_target" and not (b.get("target_target_id") or b.get("target_target_role")):
            report.add(AuditIssue(CAT_STORY, SEVERITY_ERROR, "pivot_missing_target",
                                  "pivot beat has no target_target_id or target_target_role",
                                  {"beat_id": bid}))
    for bid, count in beat_ids.items():
        if count > 1:
            report.add(AuditIssue(CAT_STORY, SEVERITY_ERROR, "duplicate_beat_id",
                                  "story beat_id is duplicated", {"beat_id": bid, "count": count}))
    for b in beats:
        if not isinstance(b, dict):
            continue
        req = b.get("requires_beat")
        if req and str(req) not in beat_ids:
            report.add(AuditIssue(CAT_STORY, SEVERITY_ERROR, "missing_required_beat",
                                  "requires_beat points to an unknown beat",
                                  {"beat_id": b.get("beat_id"), "requires_beat": req}))
    if len(beats) < 95:
        report.add(AuditIssue(CAT_STORY, SEVERITY_WARNING, "story_short_campaign",
                              "story campaign has fewer than 95 beats",
                              {"beats": len(beats)}))
    if len(acts_seen) < 8:
        report.add(AuditIssue(CAT_STORY, SEVERITY_WARNING, "story_few_acts",
                              "story campaign has fewer than 8 acts",
                              {"acts": sorted(acts_seen)}))
    if objective_counts:
        dominant = max(objective_counts.values())
        if dominant / max(1, sum(objective_counts.values())) > 0.55:
            report.add(AuditIssue(CAT_STORY, SEVERITY_WARNING, "story_low_objective_variety",
                                  "one objective type dominates the story campaign",
                                  {"objective_counts": objective_counts}))

    # Count story targets per type
    target_by_id: Dict[str, dict] = idx["target_by_id"]
    type_counts: Dict[str, int] = {}
    story_targets_by_type: Dict[str, List[str]] = {}
    for tid, t in target_by_id.items():
        ttype = str(t.get("type", ""))
        type_counts[ttype] = type_counts.get(ttype, 0) + 1
        if t.get("story_reserved"):
            story_targets_by_type.setdefault(ttype, []).append(tid)

    # At least 1 target per role-type
    roles_by_type: Dict[str, int] = {}
    for role, ttype in roles.items():
        roles_by_type[ttype] = roles_by_type.get(ttype, 0) + 1

    for ttype, needed in roles_by_type.items():
        available = type_counts.get(ttype, 0)
        if available < needed:
            report.add(AuditIssue(
                CAT_STORY, SEVERITY_ERROR, "not_enough_targets_for_roles",
                f"{needed} role(s) of type {ttype} need a target, only {available} available",
                {"type": ttype, "needed": needed, "available": available},
            ))

    # Story-reserved anchors must have expected files
    for ttype, tids in story_targets_by_type.items():
        expected = _STORY_FILES_EXPECTED.get(ttype, [])
        if not expected:
            continue
        for tid in tids:
            t = target_by_id[tid]
            hosts = _hosts(t)
            if not hosts:
                report.add(AuditIssue(
                    CAT_STORY, SEVERITY_ERROR, "story_anchor_no_host",
                    "story-reserved target has no host",
                    {"target_id": tid, "type": ttype},
                ))
                continue
            first_files = (hosts[0].get("os_model") or {}).get("files") or {}
            missing = [p for p in expected if p not in first_files]
            if missing:
                report.add(AuditIssue(
                    CAT_STORY, SEVERITY_ERROR, "story_anchor_missing_files",
                    "story anchor first-host is missing required files",
                    {"target_id": tid, "type": ttype, "missing": missing},
                ))

    # file_map paths must exist on at least one story-reserved target (by type prefix)
    file_map = story.get("file_map") or {}
    if isinstance(file_map, dict):
        _prefix_to_type = {"company": "company", "gov": "government",
                            "wifi": "public_wifi", "person": "person", "bank": "bank"}
        for key, path in file_map.items():
            for pfx, ttype in _prefix_to_type.items():
                if str(key).startswith(pfx + "_") or str(key) == pfx:
                    tids = story_targets_by_type.get(ttype, [])
                    if not tids:
                        continue
                    found = False
                    for tid in tids:
                        t = target_by_id[tid]
                        hs = _hosts(t)
                        if not hs:
                            continue
                        files = (hs[0].get("os_model") or {}).get("files") or {}
                        if str(path) in files:
                            found = True
                            break
                    if not found:
                        report.add(AuditIssue(
                            CAT_STORY, SEVERITY_WARNING, "story_file_map_not_found",
                            f"story.file_map[{key!r}] not present on any {ttype} anchor",
                            {"file_key": key, "path": path, "type": ttype},
                        ))
                    break

    # story_state assignments cross-check
    if isinstance(story_state, dict):
        assignments = story_state.get("assignments") or {}
        if isinstance(assignments, dict):
            for role, tid in assignments.items():
                if not tid:
                    continue
                ttype_expected = roles.get(role, "")
                t = target_by_id.get(str(tid))
                if t is None:
                    report.add(AuditIssue(
                        CAT_STORY, SEVERITY_ERROR, "assignment_unknown_target",
                        "story_state assignment points to non-existent target",
                        {"role": role, "target_id": tid},
                    ))
                elif ttype_expected and str(t.get("type", "")) != ttype_expected:
                    report.add(AuditIssue(
                        CAT_STORY, SEVERITY_ERROR, "assignment_wrong_type",
                        "story_state assignment points to wrong target type",
                        {"role": role, "target_id": tid,
                         "expected": ttype_expected, "actual": t.get("type")},
                    ))


# ── Category D : Filesystem ────────────────────────────────────────────────

def _audit_filesystem(
    report: AuditReport,
    world: Dict[str, Any],
    idx: Dict[str, Any],
    save_dir: Optional[Path],
) -> None:
    if save_dir is None:
        return
    save_dir = Path(save_dir)
    hosts_by_id: Dict[str, dict] = idx["hosts_by_id"]

    # Locate world_fs root
    fs_root_name: Optional[str] = None
    meta = save_dir / "world.meta.json"
    if meta.exists():
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
            fs_root_name = str(m.get("world_fs_root", ""))
        except Exception:
            fs_root_name = None
    if not fs_root_name:
        # Any host os_model has files_root
        for h in hosts_by_id.values():
            fr = (h.get("os_model") or {}).get("files_root")
            if fr:
                fs_root_name = str(fr).split("/")[0] + "/" + str(fr).split("/")[1]
                break
    if not fs_root_name:
        return  # no filesystem generated → skip

    fs_root = save_dir / fs_root_name
    if not fs_root.is_dir():
        report.add(AuditIssue(CAT_FILESYSTEM, SEVERITY_ERROR, "fs_root_missing",
                              "world_fs directory referenced in meta not found on disk",
                              {"fs_root": str(fs_root)}))
        return

    # Parse manifest
    manifest_path = fs_root / "manifest.json"
    manifest: Dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            report.add(AuditIssue(CAT_FILESYSTEM, SEVERITY_ERROR, "manifest_invalid",
                                  f"manifest.json invalid: {e}"))
            return

    manifest_hosts = set((manifest.get("hosts") or {}).keys()) if isinstance(manifest.get("hosts"), dict) else set()
    world_hosts = set(hosts_by_id.keys())

    # Hosts present on disk but not in world
    for hid in sorted(manifest_hosts - world_hosts):
        report.add(AuditIssue(
            CAT_FILESYSTEM, SEVERITY_WARNING, "fs_orphan_host",
            "manifest references a host that no longer exists in world",
            {"host_id": hid},
        ))

    # Hosts in world but not in manifest
    for hid in sorted(world_hosts - manifest_hosts):
        report.add(AuditIssue(
            CAT_FILESYSTEM, SEVERITY_ERROR, "fs_missing_host",
            "host exists in world but has no filesystem entry",
            {"host_id": hid},
        ))

    # Check os_model.files vs disk (sample: first 3 files per host)
    errors_logged = 0
    max_errors_per_cat = 50  # prevent huge output
    for hid, h in hosts_by_id.items():
        om = h.get("os_model") or {}
        files_root_rel = om.get("files_root")
        if not files_root_rel:
            continue
        host_root = save_dir / str(files_root_rel)
        if not host_root.is_dir():
            report.add(AuditIssue(
                CAT_FILESYSTEM, SEVERITY_ERROR, "host_fs_dir_missing",
                "host.files_root directory does not exist",
                {"host_id": hid, "files_root": files_root_rel},
            ))
            continue
        files_index = om.get("files_index") or []
        if not isinstance(files_index, list):
            continue
        for entry in files_index[:5]:  # sample
            if not isinstance(entry, dict):
                continue
            disk_rel = str(entry.get("disk_rel", ""))
            if not disk_rel:
                continue
            disk_path = host_root / disk_rel
            if not disk_path.is_file():
                if errors_logged < max_errors_per_cat:
                    report.add(AuditIssue(
                        CAT_FILESYSTEM, SEVERITY_ERROR, "fs_file_missing",
                        "file listed in os_model.files_index not present on disk",
                        {"host_id": hid, "disk_rel": disk_rel},
                    ))
                    errors_logged += 1
                continue
            # Check sha256 of a sample
            expected_sha = str(entry.get("sha256", ""))
            if expected_sha:
                try:
                    actual = hashlib.sha256(disk_path.read_bytes()).hexdigest()
                    if actual != expected_sha:
                        if errors_logged < max_errors_per_cat:
                            report.add(AuditIssue(
                                CAT_FILESYSTEM, SEVERITY_ERROR, "fs_sha_mismatch",
                                "file content SHA-256 does not match manifest",
                                {"host_id": hid, "disk_rel": disk_rel},
                            ))
                            errors_logged += 1
                except Exception:
                    pass

        # Ensure os_model.files keys are all in files_index
        om_files = om.get("files") or {}
        idx_paths = {str(e.get("path", "")) for e in files_index if isinstance(e, dict)}
        for p in om_files:
            if str(p) not in idx_paths:
                report.add(AuditIssue(
                    CAT_FILESYSTEM, SEVERITY_WARNING, "fs_file_not_materialized",
                    "os_model.files declares a path that is not in files_index",
                    {"host_id": hid, "path": p},
                ))
                break  # one per host is enough


# ── Category E : Wallets ──────────────────────────────────────────────────

def _audit_wallets(
    report: AuditReport,
    world: Dict[str, Any],
    idx: Dict[str, Any],
) -> None:
    target_by_id: Dict[str, dict] = idx["target_by_id"]
    for tid, t in target_by_id.items():
        for w in _wallets(t):
            wid = str(w.get("wallet_id", ""))
            if not wid:
                continue
            kf = str(w.get("key_file", ""))
            if not kf:
                report.add(AuditIssue(
                    CAT_WALLETS, SEVERITY_WARNING, "wallet_no_key_file",
                    "wallet has no key_file",
                    {"wallet_id": wid, "target_id": tid},
                ))
                continue
            # Must exist in at least 1 host of this target
            found = False
            for h in _hosts(t):
                files = (h.get("os_model") or {}).get("files") or {}
                if kf in files:
                    found = True
                    break
            if not found:
                report.add(AuditIssue(
                    CAT_WALLETS, SEVERITY_ERROR, "wallet_keyfile_not_on_host",
                    "wallet.key_file path is not present on any host of the target",
                    {"wallet_id": wid, "target_id": tid, "key_file": kf},
                ))


# ── Category F : WiFi pivot ───────────────────────────────────────────────

def _audit_wifi(
    report: AuditReport,
    world: Dict[str, Any],
    idx: Dict[str, Any],
    save_dir: Optional[Path] = None,
) -> None:
    target_by_id: Dict[str, dict] = idx["target_by_id"]
    hosts_by_nid: Dict[str, List[dict]] = idx["hosts_by_nid"]

    for tid, t in target_by_id.items():
        wifi_private_nids: List[str] = []
        wifi_public_nids: List[str] = []
        for n in _networks(t):
            ntype = str(n.get("type", ""))
            nid = str(n.get("network_id", ""))
            if not nid:
                continue
            if ntype == "wifi_private":
                wifi_private_nids.append(nid)
            elif ntype == "wifi_public":
                wifi_public_nids.append(nid)

        # Check APs exist
        for nid in wifi_private_nids + wifi_public_nids:
            hs = hosts_by_nid.get(nid, [])
            aps = [h for h in hs if str(h.get("host_id", "")).endswith(":ap") or
                   "wrt" in str(h.get("os", "")).lower() or
                   "router" in str(h.get("hostname", "")).lower()]
            if not hs:
                report.add(AuditIssue(
                    CAT_WIFI, SEVERITY_WARNING, "wifi_network_no_host",
                    "wifi network declared but no host connected",
                    {"network_id": nid, "target_id": tid},
                ))

        # WPA2 password pivot check (wifi_private only).
        # Un pivot n'a de sens que si la cible possède AU MOINS un host sur un
        # réseau non-wifi (LAN) depuis lequel aller récupérer le mot de passe.
        # Pour un "person" dont le seul réseau est home_wifi, il n'y a pas de
        # pivot à chercher (le réseau cible est directement accessible) → skip.
        _WIFI_SUFFIXES = (":wifi_staff", ":wifi_guest", ":home_wifi", ":wifi_ap")
        has_lan_host = any(
            str(h.get("network_id", "")) and not any(
                str(h.get("network_id", "")).endswith(s) for s in _WIFI_SUFFIXES
            )
            for h in _hosts(t)
        )
        if has_lan_host:
            for nid in wifi_private_nids:
                expected_pwd = _expected_wifi_pwd(int(world.get("seed", 0)), nid)
                found_in_pivot = False
                for h in _hosts(t):
                    hnid = str(h.get("network_id", ""))
                    if hnid == nid or any(hnid.endswith(s) for s in _WIFI_SUFFIXES):
                        continue
                    # 1) Check os_model.files (authored content)
                    files = (h.get("os_model") or {}).get("files") or {}
                    for content in files.values():
                        if isinstance(content, str) and expected_pwd in content:
                            found_in_pivot = True
                            break
                    if found_in_pivot:
                        break
                    # 2) Check on-disk wifi_passwords.txt (injected by
                    #    _generate_external_fs, not present in os_model.files).
                    #    Le fichier est cree sous /home/<persona>/, /Users/<persona>/
                    #    ou C/Users/<persona>/Documents/ selon l'OS et la persona
                    #    du host, donc on fait un rglob generique.
                    if save_dir is not None:
                        om = h.get("os_model") or {}
                        files_root_rel = om.get("files_root")
                        if files_root_rel:
                            host_root = Path(save_dir) / str(files_root_rel)
                            if host_root.is_dir():
                                try:
                                    for wp in host_root.rglob("wifi_passwords.txt"):
                                        try:
                                            if expected_pwd in wp.read_text(encoding="utf-8", errors="ignore"):
                                                found_in_pivot = True
                                                break
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                    if found_in_pivot:
                        break
                if not found_in_pivot:
                    report.add(AuditIssue(
                        CAT_WIFI, SEVERITY_WARNING, "wifi_password_no_pivot",
                        "wifi_private password not findable on any LAN host of target",
                        {"network_id": nid, "target_id": tid},
                    ))


def _expected_wifi_pwd(seed: int, nid: str) -> str:
    mix = f"{seed}:wifi:{nid}".encode("utf-8")
    return "wpa2-" + hashlib.sha256(mix).hexdigest()[:10]


# ── Category G : Semantic content ─────────────────────────────────────────

# Markers attendus dans les fichiers story (au moins un par fichier).
_STORY_CONTENT_MARKERS: Dict[str, List[str]] = {
    "/srv/git/README.md":            ["repos", "internal", "#"],
    "/srv/git/deploy_notes.txt":     ["Deploy", "schedule", "deploy"],
    "/home/dev/report.txt":          ["REPORT", "FINANCE", "Summary", "Q"],
    "/home/dev/db_export.csv":       [","],  # CSV separator
    "/home/dev/inbox_summary.txt":   ["From:", "Subject:"],
    "/srv/docs/classified.txt":      ["CLASSIFIED", "NEXUS", "Ref:"],
    "/srv/docs/procedure.txt":       ["PROCEDURE", "Ref:", "Step"],
    "/home/dev/casefile.txt":        ["CASE FILE", "Ref:"],
    "/home/admin/ap_log.txt":        ["AP Log", "beacon", "Timestamp:"],
    "/home/user/notes.txt":          ["Account", "Transfer", "Ref"],
    "/srv/banking/accounts.csv":     ["id,holder", "balance"],
    "/home/dev/treasury_report.txt": ["TREASURY", "Ref:"],
    "/home/dev/kyc_flags.txt":       ["KYC", "AML", "Ref:"],
}

# Map service name (lowercase) mentioned in mission hint → accepted service
# names on the host. SMB et RDP sont groupes : les deux sont des acces remote
# Windows typiquement coexistants, donc un hint qui dit "RDP ou SMB" sur un host
# qui n'a que SMB reste coherent (et inversement).
_SVC_HINT_KEYWORDS: Dict[str, set] = {
    "ssh":       {"ssh"},
    "smb":       {"smb", "rdp"},
    "rdp":       {"rdp", "smb"},
    "mysql":     {"mysql", "mariadb"},
    "mariadb":   {"mysql", "mariadb"},
    "postgres":  {"postgres"},
    "ftp":       {"ftp"},
    "imap":      {"imap"},
}


def _audit_semantic_identity(
    report: AuditReport,
    world: Dict[str, Any],
    idx: Dict[str, Any],
) -> None:
    """G1 — identités (wallet keys, /etc/hosts, SSID, wifi passwords)."""
    target_by_id: Dict[str, dict] = idx["target_by_id"]
    seed = int(world.get("seed", 0))

    for tid, t in target_by_id.items():
        # Wallet key content
        for w in _wallets(t):
            wid = str(w.get("wallet_id", ""))
            kf = str(w.get("key_file", ""))
            if not wid or not kf:
                continue
            # Find the key_file on some host of the target
            content: Optional[str] = None
            for h in _hosts(t):
                files = (h.get("os_model") or {}).get("files") or {}
                if kf in files:
                    content = str(files.get(kf, ""))
                    break
            if content is None:
                continue  # already reported in CAT_WALLETS
            expected_currency = str(w.get("currency", ""))
            expected_address  = str(w.get("address", ""))
            expected_token    = f"ENCRYPTED_{wid.upper()}"
            missing: List[str] = []
            if expected_currency and expected_currency not in content:
                missing.append(f"currency={expected_currency}")
            if expected_address and expected_address not in content:
                missing.append(f"address={expected_address}")
            if expected_token not in content:
                missing.append(expected_token)
            if missing:
                report.add(AuditIssue(
                    CAT_SEMANTIC, SEVERITY_ERROR, "wallet_key_content_mismatch",
                    "wallet.key_file content does not reference the wallet object",
                    {"wallet_id": wid, "target_id": tid, "missing": missing},
                ))

        # /etc/hosts, /etc/config/wireless, /etc/config/network, auth.log
        # Build SSID map for the target
        ssid_by_nid = {
            str(n.get("network_id", "")): str(n.get("ssid", ""))
            for n in _networks(t) if isinstance(n, dict) and n.get("ssid")
        }
        # Expected wifi_private passwords for this target
        wifi_pwds = {
            str(n.get("network_id", "")): _expected_wifi_pwd(seed, str(n.get("network_id", "")))
            for n in _networks(t)
            if isinstance(n, dict) and str(n.get("type", "")) == "wifi_private"
        }

        for h in _hosts(t):
            hid = str(h.get("host_id", ""))
            hip = str(h.get("ip", ""))
            hname = str(h.get("hostname", ""))
            nid = str(h.get("network_id", ""))
            os_name = str(h.get("os", "")).lower()
            files = (h.get("os_model") or {}).get("files") or {}

            # /etc/hosts (Linux only — skipped on Windows where it lives under C/...)
            etc_hosts = files.get("/etc/hosts")
            if isinstance(etc_hosts, str):
                if hip and hip not in etc_hosts:
                    report.add(AuditIssue(
                        CAT_SEMANTIC, SEVERITY_WARNING, "etc_hosts_wrong_ip",
                        "/etc/hosts does not contain the host's real IP",
                        {"host_id": hid, "expected_ip": hip},
                    ))
                if hname and hname not in etc_hosts:
                    report.add(AuditIssue(
                        CAT_SEMANTIC, SEVERITY_WARNING, "etc_hosts_wrong_hostname",
                        "/etc/hosts does not contain the host's real hostname",
                        {"host_id": hid, "expected_hostname": hname},
                    ))

            # /var/log/auth.log : IP (optional / warn)
            auth_log = files.get("/var/log/auth.log")
            if isinstance(auth_log, str) and hip:
                # Accept if the host IP is referenced OR if an IP of the same /24
                # is present (common for "accepted password from 10.0.0.X" log entries).
                prefix = ".".join(hip.split(".")[:3]) + "."
                if hip not in auth_log and prefix not in auth_log:
                    report.add(AuditIssue(
                        CAT_SEMANTIC, SEVERITY_WARNING, "authlog_unrelated_ip",
                        "/var/log/auth.log references an IP unrelated to the host LAN",
                        {"host_id": hid, "host_ip": hip},
                    ))

            # /etc/config/wireless (AP hosts)
            wireless = files.get("/etc/config/wireless")
            if isinstance(wireless, str):
                expected_ssid = ssid_by_nid.get(nid, "")
                if expected_ssid and expected_ssid not in wireless:
                    report.add(AuditIssue(
                        CAT_SEMANTIC, SEVERITY_ERROR, "wireless_ssid_mismatch",
                        "/etc/config/wireless does not reference the declared SSID",
                        {"host_id": hid, "expected_ssid": expected_ssid},
                    ))

            # /etc/config/network (router hosts)
            net_conf = files.get("/etc/config/network")
            if isinstance(net_conf, str) and hip:
                prefix = ".".join(hip.split(".")[:3]) + "."
                if prefix not in net_conf and hip not in net_conf:
                    report.add(AuditIssue(
                        CAT_SEMANTIC, SEVERITY_WARNING, "netconfig_ip_mismatch",
                        "/etc/config/network IP does not match the host's LAN",
                        {"host_id": hid, "host_ip": hip},
                    ))

            # wifi_passwords.txt completeness — must list ALL wifi_private nids
            # of the target. We check any file ending with wifi_passwords.txt.
            for fp, content in files.items():
                if not isinstance(content, str) or not fp.endswith("wifi_passwords.txt"):
                    continue
                missing_nids = [
                    n for n, pwd in wifi_pwds.items() if pwd and pwd not in content
                ]
                if missing_nids:
                    report.add(AuditIssue(
                        CAT_SEMANTIC, SEVERITY_WARNING, "wifi_passwords_incomplete",
                        "wifi_passwords.txt does not list all wifi_private networks",
                        {"host_id": hid, "missing_nids": missing_nids},
                    ))
                    break  # one report per host is enough


def _audit_semantic_missions(
    report: AuditReport,
    world: Dict[str, Any],
    missions: Optional[Dict[str, Any]],
    idx: Dict[str, Any],
) -> None:
    """G2 — cohérence mission.hint / mission.title avec le host et le wallet."""
    if not isinstance(missions, dict):
        return
    mission_list = missions.get("missions")
    if not isinstance(mission_list, list):
        return

    hosts_by_id: Dict[str, dict] = idx["hosts_by_id"]
    target_by_id: Dict[str, dict] = idx["target_by_id"]
    # Rebuild wallet index
    wallets_by_id: Dict[str, dict] = {}
    for t in target_by_id.values():
        for w in _wallets(t):
            wid = str(w.get("wallet_id", ""))
            if wid:
                wallets_by_id[wid] = w

    for m in mission_list:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("mission_id", ""))
        obj = m.get("objective") or {}
        if not isinstance(obj, dict):
            continue
        otype = str(obj.get("type", ""))
        hint = str(m.get("hint", "") or "")
        hint_lc = hint.lower()

        # Mission hint mentions a service → host must expose it
        if otype in ("obtain_creds", "reach_root", "loot_file", "drain_wallet"):
            hid = str(obj.get("host_id", ""))
            host = hosts_by_id.get(hid)
            if host is not None:
                svc_names = {
                    str(s.get("name", "")).lower()
                    for s in (host.get("services") or [])
                    if isinstance(s, dict)
                }
                for kw, accepted in _SVC_HINT_KEYWORDS.items():
                    if kw in hint_lc and not (svc_names & accepted):
                        report.add(AuditIssue(
                            CAT_SEMANTIC, SEVERITY_WARNING,
                            "mission_hint_service_absent",
                            f"mission hint mentions {kw!r} but host has no matching service",
                            {"mission_id": mid, "host_id": hid,
                             "hint_keyword": kw, "services": sorted(svc_names)},
                        ))
                        break  # one report per mission is enough

        # loot_file path extension coherence with filename suggestion
        if otype == "loot_file":
            path = str(obj.get("path", ""))
            # If path ends with .txt but the filename contains .csv or vice versa,
            # that's an obvious mismatch. We keep this lightweight : just check
            # the path actually has an extension.
            unix_config_roots = ("/etc/", "/var/log/", "/srv/", "/root/")
            if path and "." not in path.split("/")[-1] and not path.startswith(unix_config_roots):
                report.add(AuditIssue(
                    CAT_SEMANTIC, SEVERITY_WARNING, "loot_path_no_extension",
                    "loot_file path has no file extension",
                    {"mission_id": mid, "path": path},
                ))

        # drain_wallet currency consistency
        if otype == "drain_wallet":
            wid = str(obj.get("wallet_id", ""))
            expected_cur = str(obj.get("currency", ""))
            wallet = wallets_by_id.get(wid)
            if wallet and expected_cur:
                actual_cur = str(wallet.get("currency", ""))
                if actual_cur and actual_cur != expected_cur:
                    report.add(AuditIssue(
                        CAT_SEMANTIC, SEVERITY_ERROR, "drain_currency_wrong",
                        "mission.objective.currency differs from wallet.currency",
                        {"mission_id": mid, "wallet_id": wid,
                         "mission": expected_cur, "wallet": actual_cur},
                    ))


def _audit_semantic_story_markers(
    report: AuditReport,
    world: Dict[str, Any],
    idx: Dict[str, Any],
) -> None:
    """G3 — les fichiers story-required contiennent leurs marqueurs attendus."""
    target_by_id: Dict[str, dict] = idx["target_by_id"]
    # Only check story-reserved targets (anchors)
    for tid, t in target_by_id.items():
        if not t.get("story_reserved"):
            continue
        hosts = _hosts(t)
        if not hosts:
            continue
        # The story-required files are expected on the FIRST host of the target.
        first_files = (hosts[0].get("os_model") or {}).get("files") or {}
        ttype = str(t.get("type", ""))
        expected_paths = _STORY_FILES_EXPECTED.get(ttype, [])
        for path in expected_paths:
            content = first_files.get(path)
            if not isinstance(content, str):
                continue  # already reported by CAT_STORY
            markers = _STORY_CONTENT_MARKERS.get(path, [])
            if not markers:
                continue
            if not any(m in content for m in markers):
                report.add(AuditIssue(
                    CAT_SEMANTIC, SEVERITY_ERROR, "story_file_no_marker",
                    "story-required file has no expected content marker",
                    {"target_id": tid, "path": path,
                     "expected_any_of": markers,
                     "content_preview": content[:60] + ("…" if len(content) > 60 else "")},
                ))


def _audit_semantic_relations(
    report: AuditReport,
    world: Dict[str, Any],
    idx: Dict[str, Any],
) -> None:
    target_by_id: Dict[str, dict] = idx["target_by_id"]
    for rel in world.get("relations") or []:
        if not isinstance(rel, dict):
            continue
        rid = str(rel.get("relation_id", ""))
        src_id = str(rel.get("source_target_id", ""))
        dst_id = str(rel.get("target_target_id", ""))
        dst_ip = str(rel.get("target_ip", ""))
        src = target_by_id.get(src_id)
        dst = target_by_id.get(dst_id)
        if not rid:
            report.add(AuditIssue(CAT_SEMANTIC, SEVERITY_ERROR, "relation_no_id",
                                  "relation without relation_id", {"source_target_id": src_id}))
            continue
        if src is None:
            report.add(AuditIssue(CAT_SEMANTIC, SEVERITY_ERROR, "relation_unknown_source",
                                  "relation source target does not exist", {"relation_id": rid, "source_target_id": src_id}))
            continue
        if dst is None:
            report.add(AuditIssue(CAT_SEMANTIC, SEVERITY_ERROR, "relation_unknown_target",
                                  "relation target does not exist", {"relation_id": rid, "target_target_id": dst_id}))
            continue
        real_ips = {
            str(h.get("ip", ""))
            for h in _hosts(dst)
            if isinstance(h, dict) and h.get("ip")
        }
        if dst_ip and dst_ip not in real_ips:
            report.add(AuditIssue(CAT_SEMANTIC, SEVERITY_ERROR, "relation_target_ip_mismatch",
                                  "relation target_ip is not an IP of target_target_id",
                                  {"relation_id": rid, "target_ip": dst_ip, "target_target_id": dst_id}))
        found_marker = False
        evidence_path = str(rel.get("evidence_path", ""))
        evidence_found = not evidence_path
        for h in _hosts(src):
            files = (h.get("os_model") or {}).get("files") or {}
            if not isinstance(files, dict):
                continue
            if evidence_path and evidence_path in files:
                evidence_found = True
            for content in files.values():
                if isinstance(content, str) and rid in content:
                    found_marker = True
                    break
            if found_marker and evidence_found:
                break
        if not found_marker:
            report.add(AuditIssue(CAT_SEMANTIC, SEVERITY_WARNING, "relation_marker_missing",
                                  "relation_id is not present in source target files",
                                  {"relation_id": rid, "source_target_id": src_id}))
        if not evidence_found:
            report.add(AuditIssue(CAT_SEMANTIC, SEVERITY_WARNING, "relation_evidence_path_missing",
                                  "relation evidence_path is not present in source target files",
                                  {"relation_id": rid, "evidence_path": evidence_path}))


def _audit_semantic_vuln_tags(
    report: AuditReport,
    world: Dict[str, Any],
    idx: Dict[str, Any],
) -> None:
    runtime_tags = {
        "rce_http", "weak_creds", "bruteforce", "local_privesc", "smb_ghost",
        "sqli", "relay_open", "dns_zone_transfer",
    }
    for hid, h in idx["hosts_by_id"].items():
        for svc in h.get("services") or []:
            if not isinstance(svc, dict):
                continue
            for tag in svc.get("vuln_tags") or []:
                stag = str(tag)
                if stag and stag not in runtime_tags:
                    report.add(AuditIssue(CAT_SEMANTIC, SEVERITY_WARNING, "vuln_tag_no_runtime_exploit",
                                          "service vuln_tag has no known runtime exploit",
                                          {"host_id": hid, "service": svc.get("name"), "vuln_tag": stag}))


# ── Category H : Market world-seed ─────────────────────────────────────────

def _audit_market_seed(
    report: AuditReport,
    world: Dict[str, Any],
    idx: Dict[str, Any],
    save_dir: Optional[Path],
) -> None:
    """H — verify market_seed.json items reference valid world entities."""
    if save_dir is None:
        return
    seed_path = Path(save_dir) / "market_seed.json"
    if not seed_path.exists():
        # Not a hard error — old saves predate market_seed.
        report.add(AuditIssue(
            CAT_MARKET, SEVERITY_WARNING, "market_seed_missing",
            "save/market_seed.json not present (regenerate world to populate market)",
            {"save_dir": str(save_dir)},
        ))
        return

    import json as _json
    try:
        data = _json.loads(seed_path.read_text(encoding="utf-8"))
    except Exception as e:
        report.add(AuditIssue(
            CAT_MARKET, SEVERITY_ERROR, "market_seed_unreadable",
            f"market_seed.json failed to parse: {e}",
            {"path": str(seed_path)},
        ))
        return

    listings = data.get("world_listings") or []
    payloads = data.get("world_listings_payload") or {}

    target_by_id: Dict[str, dict] = idx["target_by_id"]
    hosts_by_id: Dict[str, dict] = idx["hosts_by_id"]

    # Build a set of valid district ids and ssids for cross-check
    valid_dids = {str(d.get("district_id", "")) for d in (world.get("districts") or [])
                  if isinstance(d, dict)}
    valid_ssids = set()
    valid_nids = set()
    valid_relations = {
        str(rel.get("relation_id", ""))
        for rel in (world.get("relations") or [])
        if isinstance(rel, dict) and rel.get("relation_id")
    }
    for t in target_by_id.values():
        for n in _networks(t):
            if isinstance(n, dict):
                if n.get("ssid"):
                    valid_ssids.add(str(n.get("ssid")))
                if n.get("network_id"):
                    valid_nids.add(str(n.get("network_id")))

    # Per-listing checks
    seen_ids: set = set()
    for it in listings:
        if not isinstance(it, dict):
            continue
        iid = str(it.get("item_id", ""))
        if not iid:
            report.add(AuditIssue(
                CAT_MARKET, SEVERITY_ERROR, "listing_missing_item_id",
                "world listing has no item_id",
                {"item": it},
            ))
            continue
        if iid in seen_ids:
            report.add(AuditIssue(
                CAT_MARKET, SEVERITY_ERROR, "listing_duplicate_id",
                "duplicate world listing item_id",
                {"item_id": iid},
            ))
        seen_ids.add(iid)

        # Price + tier sanity
        price = it.get("price")
        tier = it.get("tier")
        if not isinstance(price, int) or price < 0:
            report.add(AuditIssue(
                CAT_MARKET, SEVERITY_ERROR, "listing_bad_price",
                "world listing has invalid price",
                {"item_id": iid, "price": price},
            ))
        if tier not in (1, 2, 3):
            report.add(AuditIssue(
                CAT_MARKET, SEVERITY_WARNING, "listing_bad_tier",
                "world listing has invalid tier (expected 1/2/3)",
                {"item_id": iid, "tier": tier},
            ))

        # Cross-references encoded in item_id : we use prefixes to detect what
        # entity the listing claims to reference and check it exists.
        if iid.startswith("wld_almanac_"):
            did = iid[len("wld_almanac_"):]
            if did not in valid_dids:
                report.add(AuditIssue(
                    CAT_MARKET, SEVERITY_ERROR, "almanac_unknown_district",
                    "almanac listing references an unknown district",
                    {"item_id": iid, "district_id": did},
                ))
        elif iid.startswith("wld_floorplan_") or iid.startswith("wld_viplist_"):
            tid = iid.split("_", 2)[-1]
            if tid not in target_by_id:
                report.add(AuditIssue(
                    CAT_MARKET, SEVERITY_ERROR, "listing_unknown_target",
                    "world listing references an unknown target",
                    {"item_id": iid, "target_id": tid},
                ))
        elif iid.startswith("wld_recon_hint_"):
            rest = iid[len("wld_recon_hint_"):]
            # recon_hint_<did>_<tid>
            parts = rest.split("_", 1)
            if len(parts) == 2:
                did, tid = parts
                if did not in valid_dids:
                    report.add(AuditIssue(
                        CAT_MARKET, SEVERITY_ERROR, "recon_unknown_district",
                        "recon_hint references an unknown district",
                        {"item_id": iid, "district_id": did},
                    ))
                if tid not in target_by_id:
                    report.add(AuditIssue(
                        CAT_MARKET, SEVERITY_ERROR, "recon_unknown_target",
                        "recon_hint references an unknown target",
                        {"item_id": iid, "target_id": tid},
                    ))
        elif iid.startswith("wld_insider_") or iid.startswith("wld_dossier_"):
            tid = iid.split("_", 2)[-1]
            if tid not in target_by_id:
                report.add(AuditIssue(
                    CAT_MARKET, SEVERITY_ERROR, "listing_unknown_target",
                    "world listing references an unknown target",
                    {"item_id": iid, "target_id": tid},
                ))
        elif iid.startswith("wld_subnet_"):
            did = iid[len("wld_subnet_"):]
            if did not in valid_dids:
                report.add(AuditIssue(
                    CAT_MARKET, SEVERITY_ERROR, "subnet_unknown_district",
                    "subnet recon references an unknown district",
                    {"item_id": iid, "district_id": did},
                ))
        elif iid.startswith("wld_handshake_"):
            nid_underscore = iid[len("wld_handshake_"):]
            # network_id was encoded with ':' replaced by '_'
            nid = nid_underscore.replace("_", ":", 1)
            # Actually network_id uses '_' so we need a smarter check —
            # accept if the underscore form appears anywhere in valid_nids.
            ok = any(nid_underscore == n.replace(":", "_") for n in valid_nids)
            if not ok:
                report.add(AuditIssue(
                    CAT_MARKET, SEVERITY_ERROR, "handshake_unknown_network",
                    "handshake listing references an unknown network",
                    {"item_id": iid, "network_id_norm": nid_underscore},
                ))
        elif iid.startswith("wld_creds_"):
            host_norm = iid[len("wld_creds_"):]
            ok = any(host_norm == h.replace(":", "_") for h in hosts_by_id)
            if not ok:
                report.add(AuditIssue(
                    CAT_MARKET, SEVERITY_ERROR, "creds_unknown_host",
                    "partial creds listing references an unknown host",
                    {"item_id": iid, "host_id_norm": host_norm},
                ))
            # Verify the user mentioned in effect.prebaked_creds exists
            eff = it.get("effect") or {}
            pc = eff.get("prebaked_creds") if isinstance(eff, dict) else None
            if isinstance(pc, dict):
                hid = str(pc.get("host_id", ""))
                user = str(pc.get("user", ""))
                host = hosts_by_id.get(hid)
                if host:
                    om = host.get("os_model") or {}
                    users = list(om.get("users") or [])
                    if user and user not in users:
                        report.add(AuditIssue(
                            CAT_MARKET, SEVERITY_ERROR, "creds_user_not_on_host",
                            "prebaked_creds.user is not in os_model.users of the host",
                            {"item_id": iid, "host_id": hid, "user": user,
                             "host_users": users},
                        ))
        elif iid.startswith("wld_relation_"):
            rid = iid[len("wld_relation_"):]
            if rid not in valid_relations:
                report.add(AuditIssue(
                    CAT_MARKET, SEVERITY_ERROR, "relation_listing_unknown_relation",
                    "relation dossier listing references an unknown relation_id",
                    {"item_id": iid, "relation_id": rid},
                ))
            eff = it.get("effect") or {}
            if isinstance(eff, dict):
                effect_rid = str(eff.get("relation_id", ""))
                if effect_rid and effect_rid not in valid_relations:
                    report.add(AuditIssue(
                        CAT_MARKET, SEVERITY_ERROR, "relation_effect_unknown_relation",
                        "relation dossier effect references an unknown relation_id",
                        {"item_id": iid, "relation_id": effect_rid},
                    ))

    # Payload integrity
    for iid, payload in payloads.items():
        if iid not in seen_ids:
            report.add(AuditIssue(
                CAT_MARKET, SEVERITY_WARNING, "payload_orphan",
                "payload entry has no matching listing",
                {"item_id": iid},
            ))
            continue
        if not isinstance(payload, dict):
            report.add(AuditIssue(
                CAT_MARKET, SEVERITY_ERROR, "payload_not_dict",
                "payload entry is not a dict",
                {"item_id": iid},
            ))
            continue
        drop = str(payload.get("drop_path", ""))
        content = str(payload.get("content", ""))
        if not drop:
            report.add(AuditIssue(
                CAT_MARKET, SEVERITY_ERROR, "payload_no_drop_path",
                "payload missing drop_path",
                {"item_id": iid},
            ))
        elif not drop.startswith("/home/player/downloads/"):
            report.add(AuditIssue(
                CAT_MARKET, SEVERITY_WARNING, "payload_unusual_drop_path",
                "payload drop_path not under /home/player/downloads/",
                {"item_id": iid, "drop_path": drop},
            ))
        if not content:
            report.add(AuditIssue(
                CAT_MARKET, SEVERITY_ERROR, "payload_empty_content",
                "payload content is empty",
                {"item_id": iid},
            ))


# ── Public API ─────────────────────────────────────────────────────────────

def audit_world(
    *,
    world: Dict[str, Any],
    missions: Optional[Dict[str, Any]] = None,
    save_dir: Optional[Path] = None,
    story: Optional[Dict[str, Any]] = None,
    story_state: Optional[Dict[str, Any]] = None,
) -> AuditReport:
    """Run the 6-category audit and return a structured report."""
    report = AuditReport()
    idx = _audit_world(report, world)
    if missions is not None:
        _audit_missions(report, world, missions, idx)
    _audit_story(report, world, idx, story, story_state)
    _audit_filesystem(report, world, idx, save_dir)
    _audit_wallets(report, world, idx)
    _audit_wifi(report, world, idx, save_dir=save_dir)
    _audit_semantic_identity(report, world, idx)
    _audit_semantic_missions(report, world, missions, idx)
    _audit_semantic_story_markers(report, world, idx)
    _audit_semantic_relations(report, world, idx)
    _audit_semantic_vuln_tags(report, world, idx)
    _audit_market_seed(report, world, idx, save_dir)
    return report


__all__ = [
    "audit_world",
    "AuditReport",
    "AuditIssue",
    "SEVERITY_ERROR",
    "SEVERITY_WARNING",
    "CAT_WORLD", "CAT_MISSIONS", "CAT_STORY",
    "CAT_FILESYSTEM", "CAT_WALLETS", "CAT_WIFI", "CAT_SEMANTIC", "CAT_MARKET",
    "CATEGORY_NAMES",
]
