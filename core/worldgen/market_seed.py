"""Market seed generator — derive ShadowMarket items from a generated world.

This module produces ``save/market_seed.json``: a deterministic catalogue of
items anchored on the actual world (district names, target names, network
SSIDs, real users on hosts). The MarketState reads this file at boot and
exposes the items alongside the static NPC catalogue.

Tiers:

* **Tier 1 (cosmetic)** — almanachs, floor plans, VIP lists. ~80–250 NXC.
  Lore-only files dropped on purchase, optionally a small passive bonus.
* **Tier 2 (hints)**     — recon hint district, insider tip target, employee
  dossier (real ``os_model.users``). 300–800 NXC. Real but partial info.
* **Tier 3 (intel)**     — subnet recon JSON, WPA2 handshake, partial creds.
  1500–3500 NXC. Strong gameplay shortcut.

The generator is purely deterministic: same ``(world, seed)`` → same catalogue.
"""
from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Optional, Tuple


# ── helpers ──────────────────────────────────────────────────────────────────


def _districts(world: Dict[str, Any]) -> List[Dict[str, Any]]:
    ds = world.get("districts")
    return [d for d in ds if isinstance(d, dict)] if isinstance(ds, list) else []


def _targets(world: Dict[str, Any]) -> List[Dict[str, Any]]:
    ts = world.get("targets")
    return [t for t in ts if isinstance(t, dict)] if isinstance(ts, list) else []


def _hosts(t: Dict[str, Any]) -> List[Dict[str, Any]]:
    hs = t.get("hosts")
    return [h for h in hs if isinstance(h, dict)] if isinstance(hs, list) else []


def _networks(t: Dict[str, Any]) -> List[Dict[str, Any]]:
    ns = t.get("networks")
    return [n for n in ns if isinstance(n, dict)] if isinstance(ns, list) else []


def _district_name(world: Dict[str, Any], did: str) -> str:
    for d in _districts(world):
        if str(d.get("district_id", "")) == did:
            return str(d.get("name", did))
    return did or "Unknown"


def _targets_in_district(world: Dict[str, Any], did: str) -> List[Dict[str, Any]]:
    out = []
    for t in _targets(world):
        for n in _networks(t):
            if str(n.get("district_id", "")) == did:
                out.append(t)
                break
    return out


# ── tier 1: cosmetic items ───────────────────────────────────────────────────


def _make_almanac(rng: random.Random, did: str, dname: str) -> Optional[Dict[str, Any]]:
    item_id = f"wld_almanac_{did}"
    price = rng.randint(80, 180)
    body_lines = [
        f"=== {dname.upper()} STREET ALMANAC ===",
        "",
        "A loose collection of street-level intel for operators new to the area.",
        "",
        f"Population estimate : {rng.randint(8, 60)}k",
        f"Average rent        : {rng.randint(900, 4200)} NXC/month",
        f"Police presence     : {rng.choice(['light', 'moderate', 'heavy', 'corrupt'])}",
        f"Common crime        : {rng.choice(['petty theft', 'cyber fraud', 'drug trafficking', 'extortion'])}",
        "",
        "Tips:",
        f"  - {rng.choice(['Avoid the metro after midnight.', 'Use cash, not cards.', 'Wear gloves outdoors in winter.', 'Locals trust foreigners less than crooks.'])}",
        f"  - {rng.choice(['The {} cafe has free wifi.', 'Park benches near the {} station are mics-bugged.', 'The {} mall has off-the-books contractors.']).format(dname)}",
        "",
        "(no actionable tech intel — this is street-level lore)",
    ]
    content = "\n".join(body_lines) + "\n"
    drop_path = f"/home/player/downloads/almanac_{did}.txt"
    return {
        "item": {
            "item_id":   item_id,
            "category":  "intel",
            "name":      f"Street Almanac — {dname}",
            "desc":      f"Lore-only intel about {dname}. +1% scan luck if owned.",
            "price":     int(price),
            "tier":      1,
            "world":     True,
            "effect":    {"scan_luck": 0.01},
        },
        "payload": {"drop_path": drop_path, "content": content},
    }


def _make_floor_plan(rng: random.Random, t: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tid = str(t.get("target_id", ""))
    name = str(t.get("name", tid))
    item_id = f"wld_floorplan_{tid}"
    price = rng.randint(120, 240)
    floors = rng.randint(2, 6)
    rooms = rng.randint(8, 24)
    body_lines = [
        f"=== {name.upper()} — INTERIOR FLOOR PLAN ===",
        "",
        f"Floors        : {floors}",
        f"Total rooms   : {rooms}",
        f"Server room   : Floor {rng.randint(0, floors-1)}, sublevel {rng.randint(0,2)}",
        f"Vault access  : Floor {rng.randint(0, floors-1)}, biometric + pin",
        f"Cameras       : {rng.randint(12, 80)} (motion-triggered after hours)",
        "",
        "Notable points:",
        "  - Main switchboard near rear loading dock",
        f"  - Wifi repeaters on floors {rng.sample(range(floors), min(floors, 3))}",
        f"  - Emergency exit on floor 0 (south corridor)",
        "",
        "(physical intel — not directly hackable, but useful for planning)",
    ]
    content = "\n".join(body_lines) + "\n"
    drop_path = f"/home/player/downloads/floorplan_{tid}.txt"
    return {
        "item": {
            "item_id":   item_id,
            "category":  "intel",
            "name":      f"Floor Plan — {name}",
            "desc":      f"Interior layout of {name}. Cosmetic intel.",
            "price":     int(price),
            "tier":      1,
            "world":     True,
        },
        "payload": {"drop_path": drop_path, "content": content},
    }


def _make_vip_list(rng: random.Random, t: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tid = str(t.get("target_id", ""))
    name = str(t.get("name", tid))
    item_id = f"wld_viplist_{tid}"
    price = rng.randint(100, 220)
    fake_names = ["A. Mendez", "K. Volkov", "S. Chen", "M. O'Brien", "L. Schmidt",
                  "R. Bianchi", "T. Yamamoto", "N. Petrov", "J. Almeida", "F. Dubois"]
    rng.shuffle(fake_names)
    n = rng.randint(4, 8)
    body_lines = [
        f"=== {name.upper()} — VIP / FREQUENT CUSTOMERS ===",
        "",
    ]
    for nm in fake_names[:n]:
        body_lines.append(f"  - {nm:<14}  visits {rng.choice(['daily', 'weekly', 'monthly'])}, "
                          f"spends {rng.randint(80, 1200)} NXC/visit")
    body_lines.append("")
    body_lines.append("(social intel — could help with social engineering pretexts)")
    content = "\n".join(body_lines) + "\n"
    drop_path = f"/home/player/downloads/viplist_{tid}.txt"
    return {
        "item": {
            "item_id":   item_id,
            "category":  "intel",
            "name":      f"VIP List — {name}",
            "desc":      f"Regular customer roster for {name}.",
            "price":     int(price),
            "tier":      1,
            "world":     True,
        },
        "payload": {"drop_path": drop_path, "content": content},
    }


# ── tier 2: hint items ───────────────────────────────────────────────────────


def _make_recon_hint(rng: random.Random, world: Dict[str, Any], did: str, dname: str) -> Optional[Dict[str, Any]]:
    """Reveal one (target, vulnerable service) pair from the district."""
    candidates: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for t in _targets_in_district(world, did):
        for h in _hosts(t):
            for s in (h.get("services") or []):
                if isinstance(s, dict) and s.get("vuln_tags"):
                    candidates.append((t, s))
    if not candidates:
        return None
    t, svc = rng.choice(candidates)
    tid = str(t.get("target_id", ""))
    item_id = f"wld_recon_hint_{did}_{tid}"
    price = rng.randint(280, 520)
    tag = rng.choice(list(svc.get("vuln_tags", [])) or ["weak_creds"])
    body = (
        f"=== RECON HINT — {dname.upper()} ===\n\n"
        f"Heard from a contact: '{t.get('name', tid)}' has a soft spot.\n"
        f"Service: {svc.get('name', 'unknown')} on port {svc.get('port', '?')}\n"
        f"Likely weakness: {tag}\n\n"
        f"No promises this still works — info is < 7 days old.\n"
        f"(actionable: try this service+vuln_tag combo first)\n"
    )
    drop_path = f"/home/player/downloads/recon_hint_{did}_{tid}.txt"
    return {
        "item": {
            "item_id":   item_id,
            "category":  "intel",
            "name":      f"Recon Hint — {dname}",
            "desc":      f"Service-level vulnerability hint on a {dname} target.",
            "price":     int(price),
            "tier":      2,
            "world":     True,
        },
        "payload": {"drop_path": drop_path, "content": body},
    }


def _make_insider_tip(rng: random.Random, t: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Reveal one vuln_tag of one host of the target."""
    hosts_with_vulns = []
    for h in _hosts(t):
        for s in (h.get("services") or []):
            if isinstance(s, dict) and s.get("vuln_tags"):
                hosts_with_vulns.append((h, s))
    if not hosts_with_vulns:
        return None
    h, svc = rng.choice(hosts_with_vulns)
    tid = str(t.get("target_id", ""))
    name = str(t.get("name", tid))
    item_id = f"wld_insider_{tid}"
    price = rng.randint(420, 780)
    tags = list(svc.get("vuln_tags", []) or [])
    body = (
        f"=== INSIDER TIP — {name.upper()} ===\n\n"
        f"From a former employee (paid for silence, then talked):\n\n"
        f"Host         : {h.get('hostname', '?')} ({h.get('ip', '?')})\n"
        f"OS           : {h.get('os', '?')}\n"
        f"Weak service : {svc.get('name', '?')}:{svc.get('port', '?')}\n"
        f"Known issue  : {', '.join(tags)}\n\n"
        f"They never patch this one — IT is overworked.\n"
    )
    drop_path = f"/home/player/downloads/insider_{tid}.txt"
    return {
        "item": {
            "item_id":   item_id,
            "category":  "intel",
            "name":      f"Insider Tip — {name}",
            "desc":      f"Privileged vulnerability info on {name}.",
            "price":     int(price),
            "tier":      2,
            "world":     True,
        },
        "payload": {"drop_path": drop_path, "content": body},
    }


def _make_employee_dossier(rng: random.Random, t: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Expose the real os_model.users of one host of the target."""
    hosts_with_users = [
        h for h in _hosts(t)
        if isinstance(h.get("os_model"), dict) and h["os_model"].get("users")
    ]
    if not hosts_with_users:
        return None
    h = rng.choice(hosts_with_users)
    users = list(h["os_model"].get("users") or [])
    if not users:
        return None
    tid = str(t.get("target_id", ""))
    name = str(t.get("name", tid))
    item_id = f"wld_dossier_{tid}"
    price = rng.randint(380, 720)
    lines = [
        f"=== EMPLOYEE DOSSIER — {name.upper()} ===",
        "",
        f"Host        : {h.get('hostname', '?')} ({h.get('ip', '?')})",
        f"OS          : {h.get('os', '?')}",
        f"Known users : {len(users)}",
        "",
        "username,role_guess,last_seen_days_ago",
    ]
    for u in users:
        role = rng.choice(["admin", "user", "service", "developer", "ops"])
        lines.append(f"{u},{role},{rng.randint(1, 30)}")
    lines.append("")
    lines.append("(use these usernames for brute-force or password-spray)")
    content = "\n".join(lines) + "\n"
    drop_path = f"/home/player/downloads/dossier_{tid}.csv"
    return {
        "item": {
            "item_id":   item_id,
            "category":  "intel",
            "name":      f"Employee Dossier — {name}",
            "desc":      f"Real account list for {name}. Useful for brute-force.",
            "price":     int(price),
            "tier":      2,
            "world":     True,
        },
        "payload": {"drop_path": drop_path, "content": content},
    }


# ── tier 3: high-value intel ──────────────────────────────────────────────────


def _make_subnet_recon(rng: random.Random, world: Dict[str, Any], did: str, dname: str) -> Optional[Dict[str, Any]]:
    """Full host enumeration of a district as a JSON file."""
    tlist = _targets_in_district(world, did)
    if not tlist:
        return None
    enum: List[Dict[str, Any]] = []
    for t in tlist:
        for h in _hosts(t):
            services = []
            for s in (h.get("services") or []):
                if isinstance(s, dict):
                    services.append({"port": s.get("port"), "name": s.get("name"),
                                     "version": s.get("version")})
            enum.append({
                "target":   str(t.get("name", t.get("target_id", ""))),
                "host_id":  str(h.get("host_id", "")),
                "ip":       str(h.get("ip", "")),
                "hostname": str(h.get("hostname", "")),
                "os":       str(h.get("os", "")),
                "services": services,
            })
    if not enum:
        return None
    item_id = f"wld_subnet_{did}"
    price = rng.randint(1500, 2800)
    content = json.dumps({"district": dname, "hosts": enum}, indent=2)
    drop_path = f"/home/player/downloads/subnet_{did}.json"
    return {
        "item": {
            "item_id":   item_id,
            "category":  "intel",
            "name":      f"Subnet Recon — {dname}",
            "desc":      f"Full enumeration ({len(enum)} hosts) of {dname}.",
            "price":     int(price),
            "tier":      3,
            "world":     True,
        },
        "payload": {"drop_path": drop_path, "content": content},
    }


def _make_handshake(rng: random.Random, world: Dict[str, Any], seed: int) -> Optional[Dict[str, Any]]:
    """Pre-captured WPA2 handshake for a real network."""
    candidates: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for t in _targets(world):
        for n in _networks(t):
            if str(n.get("type", "")) in ("wifi_private", "wifi_public") and n.get("ssid"):
                candidates.append((t, n))
    if not candidates:
        return None
    t, n = rng.choice(candidates)
    nid = str(n.get("network_id", ""))
    ssid = str(n.get("ssid", ""))
    item_id = f"wld_handshake_{nid.replace(':','_')}"
    price = rng.randint(1700, 3200)
    sha = "".join(rng.choices("0123456789abcdef", k=40))
    bssid = ":".join(f"{rng.randint(0,255):02X}" for _ in range(6))
    content = (
        f"# WPA2 handshake capture (.hccapx-equivalent text format)\n"
        f"network_id: {nid}\n"
        f"ssid: {ssid}\n"
        f"bssid: {bssid}\n"
        f"channel: {rng.randint(1, 11)}\n"
        f"capture_quality: {rng.randint(72, 96)}\n"
        f"sha1: {sha}\n"
        f"# load this in WiFi Suite to skip capture step\n"
    )
    drop_path = f"/home/player/downloads/handshake_{nid.replace(':','_')}.hccapx"
    return {
        "item": {
            "item_id":   item_id,
            "category":  "intel",
            "name":      f"WPA2 Handshake — {ssid}",
            "desc":      f"Pre-captured handshake for '{ssid}'. Skip capture step.",
            "price":     int(price),
            "tier":      3,
            "world":     True,
            "effect":    {"prebaked_handshake": nid},
        },
        "payload": {"drop_path": drop_path, "content": content},
    }


def _make_partial_creds(rng: random.Random, t: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One real (user, password) pair on one host of the target."""
    hosts_with_users = [
        h for h in _hosts(t)
        if isinstance(h.get("os_model"), dict) and h["os_model"].get("users")
    ]
    if not hosts_with_users:
        return None
    h = rng.choice(hosts_with_users)
    users = list(h["os_model"].get("users") or [])
    if not users:
        return None
    user = rng.choice(users)
    tid = str(t.get("target_id", ""))
    hid = str(h.get("host_id", ""))
    name = str(t.get("name", tid))
    item_id = f"wld_creds_{hid.replace(':','_')}"
    price = rng.randint(2000, 3500)
    pwd = rng.choice([
        f"{user}123", f"{user.capitalize()}!", "Password1", "admin", "root",
        f"{user}{rng.randint(2020, 2025)}", f"{user}@{rng.randint(100, 999)}",
        "qwerty123", "letmein!", "Welcome2024",
    ])
    content = (
        f"# Partial credentials — usable in 'login' command\n"
        f"target  : {name}\n"
        f"host    : {h.get('hostname', '?')} ({h.get('ip', '?')})\n"
        f"host_id : {hid}\n"
        f"user    : {user}\n"
        f"pass    : {pwd}\n"
        f"# Tested {rng.randint(2, 30)}h ago, may have rotated.\n"
    )
    drop_path = f"/home/player/downloads/creds_{hid.replace(':','_')}.txt"
    return {
        "item": {
            "item_id":   item_id,
            "category":  "intel",
            "name":      f"Partial Creds — {h.get('hostname', name)}",
            "desc":      f"Working {user}@{name} login. One account.",
            "price":     int(price),
            "tier":      3,
            "world":     True,
            "effect":    {"prebaked_creds": {"host_id": hid, "user": user, "pass": pwd}},
        },
        "payload": {"drop_path": drop_path, "content": content},
    }


def _make_relation_dossier(rng: random.Random, rel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rid = str(rel.get("relation_id", ""))
    if not rid:
        return None
    src = str(rel.get("source_name", "source"))
    dst = str(rel.get("target_name", "target"))
    rtype = str(rel.get("type", "link"))
    target_ip = str(rel.get("target_ip", ""))
    item_id = f"wld_relation_{rid}"
    price = rng.randint(850, 1800)
    content = (
        f"# Relation Graph Dump — {rid}\n"
        f"source: {src}\n"
        f"target: {dst}\n"
        f"type: {rtype}\n"
        f"label: {rel.get('label', 'business relation')}\n"
        f"target_ip: {target_ip}\n"
        f"confidence: {rel.get('confidence', 'medium')}\n"
        f"relation_strength: {rel.get('relation_strength', 'normal')}\n"
        f"shared_service: {rel.get('shared_service', 'api')}\n"
        f"data_type: {rel.get('data_type', 'logs')}\n"
        f"evidence_path: {rel.get('evidence_path', '/home/dev/relations.md')}\n"
        f"since: {rel.get('since', 'unknown')}\n\n"
        f"Operator note: find relation markers in /home/dev/relations.md or osint notes on {src}.\n"
        f"Pivot objective marker: relation_id={rid} target_target_id={rel.get('target_target_id', '')}\n"
    )
    drop_path = f"/home/player/downloads/relation_{rid}.txt"
    return {
        "item": {
            "item_id":  item_id,
            "category": "intel",
            "name":     f"Relation Dossier — {src} <-> {dst}",
            "desc":     f"Actionable {rtype} pivot intel. Includes target IP and relation marker.",
            "price":    int(price),
            "tier":     2,
            "world":    True,
            "effect":   {
                "relation_id": rid,
                "target_ip": target_ip,
                "shared_service": str(rel.get("shared_service", "")),
                "data_type": str(rel.get("data_type", "")),
                "evidence_path": str(rel.get("evidence_path", "")),
            },
        },
        "payload": {"drop_path": drop_path, "content": content},
    }


# ── world thread topics extraction (for forum_world.py) ──────────────────────


def _extract_thread_topics(world: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    """Pre-extract anchored data the forum will reuse."""
    topics: Dict[str, Any] = {
        "districts":    [],
        "ssids":        [],
        "companies":    [],
        "banks":        [],
        "governments":  [],
        "public_wifi":  [],
        "relations":    [],
        "profiles":     [],
    }
    for d in _districts(world):
        nm = str(d.get("name", ""))
        if nm:
            topics["districts"].append(nm)
    for t in _targets(world):
        ttype = str(t.get("type", ""))
        nm = str(t.get("name", ""))
        if not nm:
            continue
        profile = str(t.get("profile", ""))
        if profile and profile not in topics["profiles"]:
            topics["profiles"].append(profile)
        if ttype == "company":
            topics["companies"].append(nm)
        elif ttype == "bank":
            topics["banks"].append(nm)
        elif ttype == "government":
            topics["governments"].append(nm)
        elif ttype == "public_wifi":
            topics["public_wifi"].append(nm)
        for n in _networks(t):
            ssid = str(n.get("ssid", ""))
            if ssid and ssid not in topics["ssids"]:
                topics["ssids"].append(ssid)
    for rel in world.get("relations") or []:
        if isinstance(rel, dict):
            topics["relations"].append({
                "relation_id": str(rel.get("relation_id", "")),
                "type": str(rel.get("type", "")),
                "source": str(rel.get("source_name", "")),
                "target": str(rel.get("target_name", "")),
                "target_ip": str(rel.get("target_ip", "")),
            })
    # Cap each list to keep the file small
    for k in topics:
        rng.shuffle(topics[k])
        topics[k] = topics[k][:24]
    return topics


# ── public entry point ────────────────────────────────────────────────────────


def generate_market_seed(world: Dict[str, Any], seed: int) -> Dict[str, Any]:
    """Produce a deterministic market seed from a generated world."""
    rng = random.Random(int(seed) ^ 0x9E37)

    listings: List[Dict[str, Any]] = []
    payloads: Dict[str, Dict[str, str]] = {}

    def _push(maker_result: Optional[Dict[str, Any]]) -> None:
        if not maker_result:
            return
        item = maker_result["item"]
        listings.append(item)
        payloads[str(item["item_id"])] = maker_result["payload"]

    districts = _districts(world)
    targets = _targets(world)
    rng_d = random.Random(int(seed) ^ 0xA1)
    rng_d.shuffle(districts)
    rng_t = random.Random(int(seed) ^ 0xB2)
    targets_shuffled = list(targets)
    rng_t.shuffle(targets_shuffled)

    # Tier 1 — cosmetic (4-6 items)
    for d in districts[: max(2, min(4, len(districts)))]:
        did = str(d.get("district_id", ""))
        dname = str(d.get("name", did))
        _push(_make_almanac(rng, did, dname))
    banks = [t for t in targets_shuffled if str(t.get("type", "")) == "bank"][:2]
    for t in banks:
        _push(_make_floor_plan(rng, t))
    pwifi = [t for t in targets_shuffled if str(t.get("type", "")) == "public_wifi"][:2]
    for t in pwifi:
        _push(_make_vip_list(rng, t))

    # Tier 2 — hints (4-8 items)
    for d in districts[: max(2, min(5, len(districts)))]:
        did = str(d.get("district_id", ""))
        dname = str(d.get("name", did))
        _push(_make_recon_hint(rng, world, did, dname))
    insider_targets = [t for t in targets_shuffled
                       if str(t.get("type", "")) in ("company", "government", "bank")][:3]
    for t in insider_targets:
        _push(_make_insider_tip(rng, t))
    dossier_targets = [t for t in targets_shuffled
                       if str(t.get("type", "")) in ("company", "government")][:3]
    for t in dossier_targets:
        _push(_make_employee_dossier(rng, t))

    # Tier 3 — intel (2-5 items)
    for d in districts[: max(1, min(3, len(districts)))]:
        did = str(d.get("district_id", ""))
        dname = str(d.get("name", did))
        _push(_make_subnet_recon(rng, world, did, dname))
    for _ in range(min(2, max(1, len(targets_shuffled) // 12))):
        _push(_make_handshake(rng, world, seed))
    high_value = [t for t in targets_shuffled
                  if str(t.get("type", "")) in ("bank", "government")][:2]
    for t in high_value:
        _push(_make_partial_creds(rng, t))
    relation_items = [rel for rel in (world.get("relations") or []) if isinstance(rel, dict)]
    rng.shuffle(relation_items)
    for rel in relation_items[:4]:
        _push(_make_relation_dossier(rng, rel))

    # De-duplicate by item_id (some randoms may collide)
    seen: set = set()
    unique_listings: List[Dict[str, Any]] = []
    for it in listings:
        iid = str(it["item_id"])
        if iid in seen:
            continue
        seen.add(iid)
        unique_listings.append(it)

    return {
        "schema":                "market_seed_v1",
        "world_seed":            int(seed),
        "world_listings":        unique_listings,
        "world_listings_payload": {k: v for k, v in payloads.items() if k in seen},
        "world_threads_seed":    int(seed),
        "world_thread_topics":   _extract_thread_topics(world, random.Random(int(seed) ^ 0xC3)),
    }


__all__ = ["generate_market_seed"]
