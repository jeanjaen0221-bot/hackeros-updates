from __future__ import annotations
import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("--seed", type=int, default=0)
parser.add_argument("--save-dir", default=str(ROOT / "save"))
ARGS, _UNKNOWN = parser.parse_known_args()
OUT = pathlib.Path(ARGS.save_dir) / "story" / "story.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

ECHO = "ECHO"
LAME = "LAME"
SPECTRE = "SPECTRE"
NEXUS = "NEXUS-7"
SYS = "Système"

FILE_MAP = {
    "company_git": "/srv/git/README.md",
    "company_deploy": "/srv/git/deploy_notes.txt",
    "company_arch": "/srv/git/nexus_arch.md",
    "company_db": "/home/dev/db_export.csv",
    "company_mail": "/home/dev/inbox_summary.txt",
    "company_report": "/home/dev/report.txt",
    "company_relations": "/home/dev/relations.md",
    "company_audit": "/var/log/audit.log",
    "company_node": "/etc/prism/node.conf",
    "gov_classified": "/srv/docs/classified.txt",
    "gov_procedure": "/srv/docs/procedure.txt",
    "gov_casefile": "/home/dev/casefile.txt",
    "gov_access": "/srv/docs/access_review.log",
    "gov_policy": "/srv/docs/intercept_policy.md",
    "gov_gateway": "/var/log/gateway.log",
    "wifi_log": "/home/admin/ap_log.txt",
    "wifi_beacon": "/home/admin/beacon_cache.log",
    "wifi_clients": "/home/admin/clients.csv",
    "person_notes": "/home/user/notes.txt",
    "person_contacts": "/home/user/contacts.json",
    "person_drop": "/home/user/dead_drop.txt",
    "bank_accounts": "/srv/banking/accounts.csv",
    "bank_treasury": "/home/dev/treasury_report.txt",
    "bank_kyc": "/home/dev/kyc_flags.txt",
    "bank_custody": "/srv/banking/custody_ledger.csv",
    "bank_aml": "/var/log/aml_review.log",
}

ROLES = {
    **{f"corp_{chr(97+i)}": "company" for i in range(18)},
    **{f"gov_{chr(97+i)}": "government" for i in range(8)},
    **{f"wifi_{chr(97+i)}": "public_wifi" for i in range(4)},
    **{f"person_{chr(97+i)}": "person" for i in range(4)},
    **{f"bank_{chr(97+i)}": "bank" for i in range(5)},
}

ACTS = [
    ("Le freelance", "Tu commences par de petits contrats. Les premières traces PRISM apparaissent."),
    ("Les coquilles", "Les sociétés écrans forment une économie parallèle."),
    ("Les relations cachées", "Les dossiers relationnels ouvrent des pivots entre cibles."),
    ("Les institutions", "Les agences publiques ne sont plus spectatrices."),
    ("Guerre de factions", "ECHO, SPECTRE et LAME racontent chacun une version différente."),
    ("Le cœur financier", "Les banques et wallets financent NEXUS."),
    ("Infrastructure NEXUS", "Tu pénètres le réseau technique du système de surveillance."),
    ("Contre-mesures", "PRISM riposte, te profile et force le nettoyage des traces."),
    ("Chute de PRISM", "Les preuves sortent, NEXUS tombe, les derniers actifs fuient."),
]

PATTERNS = [
    ("scan_network", None),
    ("obtain_creds", None),
    ("loot_file", None),
    ("reach_root", None),
    ("read_intel_file", "company_relations"),
    ("pivot_to_related_target", None),
    ("clean_logs", None),
    ("loot_file", None),
    ("drain_wallet", None),
    ("scan_network", None),
    ("loot_file", None),
    ("reach_root", None),
]

ACT_TARGETS = [
    ["corp_a", "corp_b", "wifi_a", "corp_c"],
    ["corp_d", "corp_e", "bank_a", "bank_b", "corp_f"],
    ["corp_g", "corp_h", "corp_i", "person_a", "wifi_b"],
    ["gov_a", "gov_b", "gov_c", "corp_j"],
    ["corp_k", "person_b", "gov_d", "wifi_c", "corp_l"],
    ["bank_c", "bank_d", "corp_m", "person_c", "bank_e"],
    ["corp_n", "corp_o", "gov_e", "corp_p"],
    ["gov_f", "corp_q", "wifi_d", "person_d", "gov_g"],
    ["corp_r", "gov_h", "corp_a", "bank_a", "person_a"],
]

FILE_BY_ROLE_TYPE = {
    "company": ["company_report", "company_mail", "company_db", "company_git", "company_deploy", "company_arch", "company_node"],
    "government": ["gov_classified", "gov_procedure", "gov_casefile", "gov_access", "gov_policy", "gov_gateway"],
    "public_wifi": ["wifi_log", "wifi_beacon", "wifi_clients"],
    "person": ["person_notes", "person_contacts", "person_drop"],
    "bank": ["bank_accounts", "bank_treasury", "bank_kyc", "bank_custody", "bank_aml"],
}

FACTION_BY_ACT = [ECHO, ECHO, LAME, SPECTRE, SPECTRE, LAME, ECHO, NEXUS, ECHO]

ACT_STAKES = {
    1: "Tu n'es encore qu'un nom dans les marges du réseau, mais quelqu'un observe déjà ta trajectoire. Les premiers contrats semblent ordinaires ; leurs métadonnées, elles, pointent vers PRISM.",
    2: "Les sociétés écrans ne protègent pas seulement de l'argent. Elles masquent des flux, des identités, des accès et des ordres signés par des gens qui n'existent officiellement pas.",
    3: "Chaque relation découverte transforme la carte en toile. Fournisseurs, assureurs, identités partagées : la vérité ne se trouve plus sur une cible, mais entre les cibles.",
    4: "Les institutions entrent dans le champ. Ce qui ressemblait à une fraude privée devient une architecture d'État, avec procédures, autorisations et silences administratifs.",
    5: "Les factions se contredisent. ECHO veut exposer, SPECTRE veut contrôler, LAME veut vendre. Toi, tu dois avancer sans devenir l'outil d'un autre.",
    6: "Le cœur financier pulse sous des couches de conformité mensongère. Les wallets ne sont pas des récompenses : ce sont des preuves, des leviers et des bombes à retardement.",
    7: "NEXUS n'est plus une rumeur. Ses relais, ses nœuds et ses configurations dessinent une machine qui surveille, classe et élimine les anomalies.",
    8: "PRISM te voit. Les journaux changent, les accès se referment, les messages deviennent hostiles. Chaque action doit maintenant laisser moins de bruit que ton silence.",
    9: "La chute commence. Les preuves doivent sortir avant que les derniers actifs ne disparaissent, avant que PRISM ne devienne un autre nom dans un autre système.",
}

FACTION_VOICES = {
    ECHO: "Je ne peux pas te promettre que cette route est propre. Je peux seulement te promettre qu'elle mène quelque part.",
    LAME: "Les gens paient pour des secrets, mais ils paient encore plus pour savoir qui les possède. Garde une copie. Toujours.",
    SPECTRE: "Ne confonds pas exposition et victoire. Une preuve mal livrée devient une arme contre celui qui l'a trouvée.",
    NEXUS: "ANOMALIE SUIVIE. Les comportements persistants sont classés. Les opérateurs isolés sont absorbés ou supprimés.",
}

OBJECTIVE_BRIEF = {
    "scan_network": (
        "Commence par écouter avant de frapper. Un scan propre révélera les hôtes exposés, les services bavards et les chemins que PRISM croyait invisibles.",
        "Quand la topologie sera connue, nous saurons si cette cible est une façade ou une porte d'entrée."
    ),
    "obtain_creds": (
        "Il nous faut une identité valide, pas seulement une vulnérabilité. Les identifiants ouvrent les portes que les exploits referment trop vite.",
        "Avec ces accès, les prochains fichiers auront l'air d'avoir été lus par quelqu'un d'autorisé."
    ),
    "loot_file": (
        "Le fichier demandé est une pièce exploitable. Ne lis pas seulement son contenu : regarde le nom, le chemin, le propriétaire implicite.",
        "Une fois exfiltré, ce document deviendra un point d'ancrage pour recouper les mensonges."
    ),
    "reach_root": (
        "Cette fois, un accès utilisateur ne suffit pas. Il faut contrôler l'hôte assez profondément pour vérifier ce qui est caché aux comptes ordinaires.",
        "Root confirmera si la cible obéit à PRISM ou si elle n'est qu'un relais compromis."
    ),
    "read_intel_file": (
        "Ce dossier n'est pas une preuve finale, c'est une carte pliée en quatre. Les marqueurs relationnels y indiquent qui dépend de qui.",
        "Lis-le attentivement : le pivot suivant naîtra d'une ligne que personne ne devait remarquer."
    ),
    "pivot_to_related_target": (
        "La cible liée est plus importante que la cible visible. PRISM se protège par dépendances : fournisseurs, audits, VPN, identité partagée.",
        "Déclenche le pivot et suis la relation. Si le lien est vrai, la surface d'attaque va changer."
    ),
    "clean_logs": (
        "Tu as laissé assez de traces pour qu'un analyste patient reconstruise ton passage. Efface les journaux avant que la corrélation ne remonte.",
        "Un bon opérateur ne disparaît pas : il rend son histoire trop ennuyeuse pour être suivie."
    ),
    "drain_wallet": (
        "Ce wallet est une caisse noire, pas un simple butin. Le vider coupera un flux et forcera quelqu'un à déplacer ses réserves.",
        "Le transfert produira du bruit. Utilise ce bruit : il révélera qui panique."
    ),
}

COMPLETION_FALLOUT = {
    "scan_network": "La silhouette réseau est nette maintenant. Derrière les ports ouverts, on voit déjà une organisation qui prétendait n'avoir rien à cacher.",
    "obtain_creds": "Les identifiants fonctionnent. Quelqu'un a laissé une clé sous le paillasson numérique, et cette clé porte une empreinte exploitable.",
    "loot_file": "La preuve est sortie. Elle ne suffit pas seule, mais elle parle le même langage que les autres fragments : comptes, relais, procédures, peur.",
    "reach_root": "Contrôle confirmé. À ce niveau de privilège, les mensonges système deviennent difficiles à maintenir.",
    "read_intel_file": "Le dossier relationnel confirme le motif. PRISM ne possède pas seulement des serveurs : PRISM possède des dépendances.",
    "pivot_to_related_target": "Le pivot a répondu. La prochaine cible n'est plus une hypothèse ; elle vient d'apparaître dans la chaîne.",
    "clean_logs": "Les traces immédiates sont nettoyées. Ce n'est pas l'invisibilité, mais c'est assez pour voler quelques heures à leurs analystes.",
    "drain_wallet": "Les fonds ont bougé. Quelque part, une alerte financière vient de passer du jaune au rouge.",
}


def msg(frm: str, sub: str, body: str, delay: int = 0) -> dict:
    return {"from": frm, "subject": sub, "body": body, "delay_ms": int(delay)}


def beat(idx: int, act: int, req: str | None, title: str, desc: str, obj: str, role: str, reward: int,
         file_key: str | None = None, host_index: int = 0, extra: dict | None = None) -> dict:
    bid = f"b{idx:03d}"
    faction = FACTION_BY_ACT[act - 1]
    act_name, act_summary = ACTS[act - 1]
    brief_a, brief_b = OBJECTIVE_BRIEF.get(obj, (
        "L'objectif est simple sur le papier, mais rien ne l'est vraiment une fois connecté.",
        "Accomplis la tâche et observe ce que cela déplace autour de toi."
    ))
    voice = FACTION_VOICES.get(faction, "")
    heat_note = "faible" if act <= 2 else ("élevée" if act >= 7 else "croissante")
    unlock = msg(
        faction,
        f"Acte {act} — {title}",
        (
            f"{act_name.upper()} — {act_summary}\n\n"
            f"{ACT_STAKES.get(act, '')}\n\n"
            f"Situation : {desc}\n\n"
            f"{brief_a}\n\n"
            f"Ce que j'attends de toi : {brief_b}\n\n"
            f"Risque opérationnel : {heat_note}. Avance par étapes : observer, entrer, confirmer, sortir.\n\n"
            f"{voice}\n\n"
            f"— {faction}"
        ),
    )
    done_sender = NEXUS if act >= 8 and idx % 3 == 0 else faction
    fallout = COMPLETION_FALLOUT.get(obj, "L'objectif est validé. La chaîne narrative avance et la pression augmente.")
    next_line = "Je prépare la suite." if done_sender != NEXUS else "Réévaluation du profil opérateur en cours."
    done = msg(
        done_sender,
        f"RE : {title}",
        (
            f"Objectif confirmé : {title}.\n\n"
            f"{fallout}\n\n"
            f"Conséquence immédiate : les signaux autour de l'acte {act} changent. "
            f"Les cibles liées vont réagir, les intermédiaires vont mentir plus vite, et PRISM va resserrer son modèle.\n\n"
            f"{next_line}\n\n"
            f"— {done_sender}"
        ),
        1500 + act * 250,
    )
    out = {
        "beat_id": bid,
        "act": int(act),
        "requires_beat": req,
        "title": title,
        "description": desc,
        "objective_type": obj,
        "target_role": role,
        "host_index": int(host_index),
        "file_key": file_key,
        "reward_money": int(reward),
        "messages_on_unlock": [unlock],
        "messages_on_complete": [done],
        "chapter_tag": ACTS[act - 1][0],
        "faction": faction,
        "threat_level": min(9, max(1, act + idx // 18)),
    }
    if extra:
        out.update(extra)
    return out


def title_for(obj: str, act_name: str, role: str, n: int) -> str:
    names = {
        "scan_network": ["Cartographie", "Reconnaissance", "Balayage silencieux"],
        "obtain_creds": ["Clés d'accès", "Porte entrouverte", "Identifiants"],
        "loot_file": ["Pièce à conviction", "Exfiltration", "Dossier sensible"],
        "reach_root": ["Contrôle total", "Escalade", "Nœud possédé"],
        "read_intel_file": ["Lecture des liens", "OSINT interne", "Marqueur relationnel"],
        "pivot_to_related_target": ["Pivot", "Cible liée", "Route cachée"],
        "clean_logs": ["Nettoyage", "Silence disque", "Audit effacé"],
        "drain_wallet": ["Saisie crypto", "Wallet noir", "Liquidation"],
    }
    return f"{names.get(obj, ['Opération'])[n % len(names.get(obj, ['Opération']))]} — {act_name} / {role.upper()}"


def desc_for(obj: str, act_name: str, role: str) -> str:
    base = {
        "scan_network": "Cartographie le réseau assigné et identifie les services exposés.",
        "obtain_creds": "Obtiens un couple d'identifiants valide sur l'hôte cible.",
        "loot_file": "Récupère le fichier demandé : il contient une preuve exploitable.",
        "reach_root": "Obtiens les privilèges root pour confirmer le contrôle complet.",
        "read_intel_file": "Lis le dossier relationnel pour déclencher une piste de pivot.",
        "pivot_to_related_target": "Utilise le marqueur découvert pour identifier la cible liée.",
        "clean_logs": "Nettoie les journaux de l'hôte avant que PRISM ne corrèle ton passage.",
        "drain_wallet": "Localise la clé privée et vide le wallet associé à la cible.",
    }
    return f"{base.get(obj, 'Accomplis l’objectif assigné.')} Phase : {act_name}. Rôle : {role}."


def build() -> list[dict]:
    beats: list[dict] = []
    prev: str | None = None
    idx = 1
    for act, (act_name, _summary) in enumerate(ACTS, start=1):
        roles = ACT_TARGETS[act - 1]
        for step in range(12):
            obj, forced_file = PATTERNS[(step + act - 1) % len(PATTERNS)]
            role = roles[step % len(roles)]
            rtype = ROLES[role]
            file_key = forced_file
            host_index = 1 if step in (3, 10) and rtype in ("company", "government", "bank") else 0
            extra: dict = {}
            if obj == "loot_file":
                keys = FILE_BY_ROLE_TYPE[rtype]
                file_key = keys[(step + act) % len(keys)]
            elif obj == "read_intel_file":
                file_key = "company_relations" if rtype == "company" else FILE_BY_ROLE_TYPE[rtype][0]
                extra["intel_path"] = FILE_MAP[file_key]
                extra["relation_id"] = "story_rel_core"
            elif obj == "pivot_to_related_target":
                extra["relation_id"] = "story_rel_core"
                extra["target_target_role"] = roles[(step + 1) % len(roles)]
            elif obj == "clean_logs":
                file_key = None
            elif obj == "drain_wallet" and rtype not in ("bank", "company", "person", "government"):
                obj = "reach_root"
            reward = 220 + act * 180 + step * 35
            beats.append(beat(
                idx, act, prev, title_for(obj, act_name, role, step), desc_for(obj, act_name, role),
                obj, role, reward, file_key=file_key, host_index=host_index, extra=extra,
            ))
            prev = f"b{idx:03d}"
            idx += 1
    beats[-1]["messages_on_complete"].append(msg(
        SYS,
        "OPÉRATION NEXUS: LONG RUN TERMINÉE",
        "Les 108 objectifs principaux sont terminés. PRISM est exposé, NEXUS est hors ligne, les actifs financiers sont gelés et les derniers relais ont été neutralisés. Statut : LÉGENDAIRE.",
        8000,
    ))
    return beats


def validate(beats: list[dict]) -> None:
    ids = {b["beat_id"] for b in beats}
    for b in beats:
        req = b.get("requires_beat")
        if req and req not in ids:
            raise RuntimeError(f"missing requires_beat {req} for {b['beat_id']}")
        if b.get("target_role") not in ROLES:
            raise RuntimeError(f"unknown role {b.get('target_role')} for {b['beat_id']}")
        fk = b.get("file_key")
        if fk and fk not in FILE_MAP:
            raise RuntimeError(f"unknown file_key {fk} for {b['beat_id']}")
    if len(beats) < 95:
        raise RuntimeError("story too short")


BEATS = build()
validate(BEATS)

data = {
    "schema": "story_v1",
    "title": "OPÉRATION NEXUS: LONG RUN",
    "name": "OPÉRATION NEXUS: LONG RUN",
    "version": 2,
    "roles": ROLES,
    "file_map": FILE_MAP,
    "acts": [{"act": i + 1, "title": a[0], "summary": a[1]} for i, a in enumerate(ACTS)],
    "beats": BEATS,
}

OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {len(BEATS)} beats -> {OUT}")
print(f"Acts: {len(ACTS)}")
print(f"Roles: {len(ROLES)}")
