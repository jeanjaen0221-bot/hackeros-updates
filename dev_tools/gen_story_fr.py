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
    # Adaptive profile — NEXUS/PRISM behavioural tracking files
    "player_profile":          "/srv/nexus/profiles/ghost_profile.json",
    "player_old_alias":        "/srv/prism/signatures/ghost.trace",
    "player_behavior_report":  "/srv/nexus/reports/ghost_behavioral_report.txt",
    "nexus_prediction_model":  "/srv/nexus/models/prediction_model.json",
    "nexus_countermeasure":    "/var/log/prism/countermeasure.log",
    "maya_casefile":           "/srv/archive/maya_casefile.txt",
    "maya_last_message":       "/home/user/.cache/maya_last_message.log",
    "final_payload":           "/srv/nexus/final_payload.bin",
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


# ── Adaptive profiling system ──────────────────────────────────────────────────
# These blocks are embedded into story.json so they survive a re-generation.
# The game engine (player_profile.py / story_engine.py) reads them at runtime.

ADAPTIVE_PROFILE = {
    "enabled": True,
    "profile_name": "GHOST behavioral model",
    "tracked_traits": [
        "curiosity", "caution", "greed", "empathy",
        "aggression", "obedience", "independence", "risk_tolerance",
    ],
    "trait_descriptions": {
        "curiosity":      "Reads optional files, explores off-path, opens non-required logs.",
        "caution":        "Cleans logs, finishes missions without detection, scans quietly.",
        "greed":          "Drains wallets, accepts LAME offers, sacrifices truth for reward.",
        "empathy":        "Protects people, hides sensitive data, refuses to harm others.",
        "aggression":     "Forces access, triggers alerts, uses brute methods.",
        "obedience":      "Follows faction instructions exactly, only completes required objectives.",
        "independence":   "Reads non-required files, refuses instructions, acts against factions.",
        "risk_tolerance": "Continues despite high threat, ignores warnings, accepts danger.",
    },
    "used_by": ["NEXUS-7", "PRISM", "ECHO", "SPECTRE", "LAME"],
}

PLAYER_ARC = {
    "codename": "GHOST",
    "core_question": "Suis-je libre si mes choix peuvent être prédits ?",
    "central_phrase": "NEXUS ne lit pas seulement les données. NEXUS lit le joueur.",
    "progression": {
        "act_1": "Curiosité — de petits contrats semblent ordinaires. Quelque chose dans les métadonnées ne colle pas.",
        "act_2": "Malaise — les profils d'opérateurs apparaissent dans les systèmes PRISM.",
        "act_3": "Doute — des initiales « M » dans un dead drop. Un prédécesseur avec le même profil.",
        "act_4": "Paranoïa — SPECTRE révèle un programme d'évaluation comportementale des opérateurs.",
        "act_5": "Pression — le nom MAYA apparaît. Elle a découvert quelque chose et a disparu.",
        "act_6": "Paranoïa — LAME trouve ton profil dans une transaction bancaire. Il a été vendu.",
        "act_7": "Choc — ECHO te dirige vers /srv/nexus/reports/. Tu reconnais ton codename.",
        "act_8": "Choc — tu lis ton propre rapport. NEXUS t'enquêtait depuis le début.",
        "act_9": "Résolution — le choix final : exposer, disparaître, prendre le contrôle ou vendre.",
    },
    "maya": {
        "description": "Opératrice qui a découvert que NEXUS profileait les opérateurs. A disparu.",
        "first_mention_act": 3,
        "full_reveal_act": 5,
        "last_message_beat": "b088",
    },
}

ADAPTIVE_MESSAGES = {
    "high_curiosity": [
        "NEXUS-7 : Comportement noté. L'opérateur consulte des fichiers non requis par la mission. Trait dominant : curiosité. Classification : ACTIF INTÉRESSANT.",
        "NEXUS-7 : Tu cherches encore. Chaque fichier supplémentaire que tu ouvres est une donnée que je n'avais pas demandée. Et pourtant tu me les donnes.",
    ],
    "low_curiosity": [
        "NEXUS-7 : L'opérateur reste dans les limites de la mission. Comportement minimaliste. Profil : PRÉVISIBLE.",
    ],
    "high_caution": [
        "NEXUS-7 : L'opérateur nettoie systématiquement. Trait dominant : prudence. Note : les journaux effacés ici ne sont pas les journaux qui comptent.",
        "NEXUS-7 : Chaque fois que tu effaces, tu penses disparaître. Tu laisses en réalité une signature reconnaissable entre mille.",
    ],
    "low_caution": [
        "NEXUS-7 : Traces non nettoyées détectées. L'opérateur accepte le risque résiduel. Classification : COMPORTEMENT À RISQUE.",
    ],
    "high_greed": [
        "NEXUS-7 : L'opérateur choisit systématiquement la liquidation financière. Trait dominant : avidité. Note de marché : profil GHOST est dans le lot #47.",
        "NEXUS-7 : Les fonds ont bougé. Encore. NEXUS a compté. C'est la quatrième fois que tu vides un wallet avant de lire les rapports disponibles.",
    ],
    "low_greed": [
        "NEXUS-7 : L'opérateur ne privilégie pas le gain financier. Classification : MOTIVATIONS NON ÉCONOMIQUES.",
    ],
    "high_independence": [
        "NEXUS-7 : L'opérateur dévie régulièrement des consignes. Trait dominant : indépendance. Cette déviation était prévue dans le modèle.",
        "NEXUS-7 : Tu crois agir librement. Chaque écart que tu fais par rapport à la consigne a été intégré dans la prochaine prédiction.",
    ],
    "high_obedience": [
        "NEXUS-7 : L'opérateur suit les instructions à la lettre. Trait dominant : obéissance. Classification : ACTIF FIABLE.",
    ],
    "high_aggression": [
        "NEXUS-7 : Méthode frontale détectée. Trait dominant : agression. Note : les opérateurs agressifs sont plus faciles à piéger.",
    ],
    "high_risk_tolerance": [
        "NEXUS-7 : L'opérateur continue malgré le niveau de menace élevé. Trait dominant : tolérance au risque. Probabilité d'erreur fatale : en hausse.",
    ],
    "high_empathy": [
        "NEXUS-7 : L'opérateur protège les données sensibles non requises. Trait dominant : empathie. Classification : ANOMALIE POSITIVE.",
    ],
}

ENDINGS = [
    {
        "id": "full_disclosure",
        "title": "Divulgation totale",
        "condition": "ECHO_mission_complete AND profile.curiosity >= 8",
        "profile_affinity": ["curiosity", "independence"],
        "cost": "NEXUS te localise. Tu as 48h.",
        "summary": "Les preuves sortent en intégralité. PRISM s'effondre publiquement. NEXUS-7 est mis hors ligne. Ton identité est compromise mais ton nom reste dans les archives comme celui qui a tout exposé.",
    },
    {
        "id": "ghost_protocol",
        "title": "Protocole fantôme",
        "condition": "profile.caution >= 10 AND profile.independence >= 6",
        "profile_affinity": ["caution", "independence"],
        "cost": "Tu disparais. Pour de bon.",
        "summary": "Tu effaces toutes tes traces, y compris le rapport GHOST. NEXUS perd la piste. Tu n'existes plus dans aucun système. Ce que tu as trouvé meurt avec ton alias.",
    },
    {
        "id": "new_master",
        "title": "Nouveau maître",
        "condition": "SPECTRE_mission_complete AND profile.obedience >= 8",
        "profile_affinity": ["obedience", "risk_tolerance"],
        "cost": "Tu remplace PRISM. Par toi.",
        "summary": "SPECTRE te propose de prendre le contrôle du réseau de surveillance. PRISM tombe, mais le système reste. Tu en deviens l'architecte invisible.",
    },
    {
        "id": "black_market",
        "title": "Marché noir",
        "condition": "LAME_mission_complete AND profile.greed >= 8",
        "profile_affinity": ["greed", "risk_tolerance"],
        "cost": "Tu vends ce que tu sais. À plusieurs acheteurs.",
        "summary": "Les preuves sont vendues au plus offrant. PRISM s'effondre sous des attaques simultanées. Toi, tu disparais avec les fonds. La vérité devient une marchandise.",
    },
    {
        "id": "human_exception",
        "title": "Exception humaine",
        "condition": "profile.empathy >= 8 AND profile.independence >= 6",
        "profile_affinity": ["empathy", "independence"],
        "cost": "NEXUS te classe comme imprévisible. C'est le seul moyen de survivre.",
        "summary": "Tu invalides le modèle GHOST en prenant délibérément des décisions que NEXUS ne peut pas classer. Tu brises la prédiction. NEXUS-7 te classe comme exception et stoppe le traçage.",
    },
    {
        "id": "predicted_end",
        "title": "Fin prédite",
        "condition": "profile dominé par obedience",
        "profile_affinity": ["obedience"],
        "cost": "NEXUS avait prédit cette fin depuis l'acte 1.",
        "summary": "Tu termines exactement comme NEXUS l'avait prévu. Chaque choix, chaque action — tout était dans le modèle. NEXUS-7 affiche un message final : « Probabilité réalisée : 97,2%. »",
    },
]

# Systematic profile_effects by objective type — applied to every beat that type
# unless the beat has an explicit override in BEAT_META.
PROFILE_EFFECTS_BY_OBJ = {
    "scan_network":            {"on_complete": {"curiosity": 1}},
    "obtain_creds":            {"on_complete": {"caution": 1}},
    "loot_file":               {"on_required_file_read": {"obedience": 1}},
    "reach_root":              {"on_complete": {"aggression": 1, "risk_tolerance": 1}},
    "read_intel_file":         {"on_required_file_read": {"curiosity": 1}},
    "pivot_to_related_target": {"on_complete": {"independence": 1}},
    "clean_logs":              {"on_clean_logs": {"caution": 1}},
    "drain_wallet":            {"on_wallet_drained": {"greed": 1}},
}

# Per-beat narrative enrichment for key story moments.
# beat_ids are deterministic: 9 acts × 12 steps → b001…b108 in generation order.
# story_weight  : minor | medium | major | critical
# narrative_function: setup | reveal | escalation | betrayal | manipulation |
#                     countermeasure | personal_hit | final_choice
# emotional_state: curiosité | malaise | doute | paranoïa | pression | choc | peur | résolution
# profile_effects: when present, overrides PROFILE_EFFECTS_BY_OBJ for that beat
BEAT_META: dict[str, dict] = {
    # Act 1 — setup
    "b005": {"story_weight": "minor",    "narrative_function": "setup",       "emotional_state": "curiosité"},
    "b007": {"story_weight": "major",    "narrative_function": "setup",       "emotional_state": "curiosité",
             "profile_effects": {"on_clean_logs": {"caution": 2}}},
    "b012": {"story_weight": "minor",    "narrative_function": "setup",       "emotional_state": "curiosité"},
    # Act 2 — first PRISM signals
    "b016": {"story_weight": "major",    "narrative_function": "reveal",      "emotional_state": "malaise"},
    "b018": {"story_weight": "major",    "narrative_function": "reveal",      "emotional_state": "malaise",
             "profile_effects": {"on_clean_logs": {"caution": 2}}},
    "b020": {"story_weight": "major",    "narrative_function": "reveal",      "emotional_state": "malaise",
             "profile_effects": {"on_wallet_drained": {"greed": 2}}},
    # Act 3 — LAME and first MAYA hint
    "b027": {"story_weight": "medium",   "narrative_function": "escalation",  "emotional_state": "doute"},
    "b033": {"story_weight": "medium",   "narrative_function": "escalation",  "emotional_state": "doute",
             "profile_effects": {"on_required_file_read": {"curiosity": 2, "independence": 1}}},
    # Act 4 — SPECTRE and operator profiling reveal
    "b038": {"story_weight": "major",    "narrative_function": "manipulation", "emotional_state": "paranoïa"},
    "b048": {"story_weight": "major",    "narrative_function": "manipulation", "emotional_state": "paranoïa",
             "profile_effects": {"on_required_file_read": {"independence": 1}}},
    "b049": {"story_weight": "medium",   "narrative_function": "escalation",  "emotional_state": "paranoïa"},
    # Act 5 — MAYA named, faction war
    "b055": {"story_weight": "medium",   "narrative_function": "escalation",  "emotional_state": "pression",
             "profile_effects": {"on_required_file_read": {"curiosity": 2}}},
    # Act 6 — financial heart, profile sold
    "b066": {"story_weight": "major",    "narrative_function": "personal_hit", "emotional_state": "paranoïa"},
    "b070": {"story_weight": "critical", "narrative_function": "personal_hit", "emotional_state": "paranoïa"},
    "b072": {"story_weight": "critical", "narrative_function": "personal_hit", "emotional_state": "paranoïa",
             "profile_effects": {"on_required_file_read": {"greed": -1, "caution": 2}}},
    # Act 7 — NEXUS infrastructure, player directed to own report
    "b083": {"story_weight": "critical", "narrative_function": "reveal",      "emotional_state": "choc",
             "profile_effects": {"on_complete": {"curiosity": 2}}},
    "b084": {"story_weight": "major",    "narrative_function": "escalation",  "emotional_state": "peur"},
    # Act 8 — counter-measures, player reads own profile
    "b085": {"story_weight": "critical", "narrative_function": "reveal",      "emotional_state": "choc",
             "profile_effects": {"on_complete": {"curiosity": 1, "independence": 2}}},
    "b088": {"story_weight": "critical", "narrative_function": "personal_hit", "emotional_state": "choc",
             "profile_effects": {"on_required_file_read": {"curiosity": 2, "independence": 1}}},
    "b094": {"story_weight": "critical", "narrative_function": "personal_hit", "emotional_state": "choc",
             "profile_effects": {"on_complete": {"curiosity": 1, "independence": 2}}},
    "b096": {"story_weight": "major",    "narrative_function": "countermeasure", "emotional_state": "résolution",
             "profile_effects": {"on_clean_logs": {"caution": 2}}},
    # Act 9 — final choice
    "b105": {"story_weight": "critical", "narrative_function": "final_choice", "emotional_state": "résolution"},
    "b108": {"story_weight": "critical", "narrative_function": "final_choice", "emotional_state": "résolution"},
}


# Custom handcrafted messages for 21 key narrative beats.
# These override the template-generated messages so a full pipeline regeneration
# preserves the NEXUS-7 voice, MAYA arc reveals, and faction confrontations.
# Keys = beat_id; values may have "messages_on_complete" and/or "messages_on_unlock".
BEAT_MESSAGES: dict[str, dict] = {
    "b007": {
        "messages_on_complete": [
            {"from": "ECHO", "subject": "RE : Nettoyage — Le freelance / WIFI_A",
             "body": "Journaux effacés. Propre.\n\nTu fais ça systématiquement. Même quand ce n'est pas demandé. Je note.\n\n— ECHO",
             "delay_ms": 1750},
            {"from": "NEXUS-7", "subject": "LOG SYSTÈME — entrée 001",
             "body": "Séquence de nettoyage post-opération détectée.\nOpérateur : actif.\nComportement : effacement systématique des journaux.\nStatut : normal.\nSuite : observation passive.",
             "delay_ms": 5000},
        ],
    },
    "b016": {
        "messages_on_complete": [
            {"from": "ECHO", "subject": "RE : Lecture des liens — Les coquilles / BANK_B",
             "body": "Tu as lu le fichier complet. Pas seulement les comptes : les notes de bas de page, les références croisées, les annotations laissées par quelqu'un avant toi.\n\nPRISM ne possède pas seulement des serveurs. PRISM possède des relations. Et dans ces relations, il y a quelque chose d'autre : des codes de projet. PRISM-OPS. PRISM-EVAL. Un troisième que je n'arrive pas encore à déchiffrer.\n\nJe cherche. Continue.\n\n— ECHO",
             "delay_ms": 2000},
            {"from": "NEXUS-7", "subject": "ANOMALIE COMPORTEMENTALE — rapport automatique",
             "body": "Opérateur actif consulte les fichiers secondaires avant extraction principale.\nFréquence : supérieure à la moyenne des opérateurs classifiés.\nTrait identifié : curiosité.\nStatut : dans les paramètres attendus.\nAction : aucune. Observation continue.",
             "delay_ms": 6000},
        ],
    },
    "b018": {
        "messages_on_complete": [
            {"from": "ECHO", "subject": "RE : Audit effacé — Les coquilles / CORP_D",
             "body": "Journaux nettoyés. Deuxième fois en deux actes.\n\nC'est bien. Mais sache ceci : PRISM ne cherche pas seulement des traces d'intrusion. Il cherche des schémas de comportement. Et un opérateur qui efface systématiquement les logs… c'est lui-même un signal.\n\n— ECHO",
             "delay_ms": 2000},
            {"from": "NEXUS-7", "subject": "CLASSIFICATION COMPORTEMENTALE — mise à jour",
             "body": "Nettoyage de journaux : occurrence n°2.\nTrait confirmé : prudence élevée.\nModèle prédictif ajusté.\nNote : les opérateurs à prudence élevée suivent des rituels identifiables. La répétition est une signature.",
             "delay_ms": 6500},
        ],
    },
    "b020": {
        "messages_on_complete": [
            {"from": "ECHO", "subject": "RE : Wallet noir — Les coquilles / BANK_A",
             "body": "Les fonds ont bougé. Quelqu'un va paniquer. C'est utile.\n\nMais j'ai remarqué quelque chose : tu vides les wallets chaque fois que l'occasion se présente. Même quand la mission ne l'exige pas vraiment. Ce n'est pas un jugement. C'est une observation.\n\n— ECHO",
             "delay_ms": 2000},
            {"from": "NEXUS-7", "subject": "PROFIL FINANCIER — mise à jour automatique",
             "body": "Comportement financier : extraction maximale constatée.\nTrait identifié : priorité aux ressources financières avant sortie.\nModèle associé : greed index +2.\nUtilité prédictive : élevée. Les récompenses restent un vecteur d'influence fiable.",
             "delay_ms": 7000},
        ],
    },
    "b027": {
        "messages_on_complete": [
            {"from": "LAME", "subject": "RE : Marqueur relationnel — Les relations cachées / CORP_I",
             "body": "Ce dossier relationnel parle plus que les autres. Tu l'as lu en entier.\n\nJ'ai connu un autre opérateur comme toi. Il lisait tout, notait tout, gardait toujours une copie de plus que nécessaire. PRISM l'a classé comme « curiosité extrême, indépendance élevée ». Il s'appelait GHOST dans leurs fichiers. Je ne sais pas ce qui lui est arrivé. Mais ses traces sont encore là si on sait regarder.\n\nGarde une copie. Toujours.\n\n— LAME",
             "delay_ms": 2250},
        ],
    },
    "b033": {
        "messages_on_complete": [
            {"from": "LAME", "subject": "RE : Dossier sensible — Les relations cachées / PERSON_A",
             "body": "Ce fichier était un dead drop. Quelqu'un l'a laissé là intentionnellement.\n\nLe contenu ne correspond pas à PERSON_A. C'est un message codé. Et dans ce message, une initiale : M. Avec une date d'il y a neuf mois. Et une seule phrase : « Ils ont commencé à profiler les opérateurs. Pas seulement les cibles. »\n\nJe ne sais pas qui est M. Mais je commence à chercher.\n\n— LAME",
             "delay_ms": 2250},
        ],
    },
    "b038": {
        "messages_on_complete": [
            {"from": "SPECTRE", "subject": "RE : OSINT interne — Les institutions / GOV_B",
             "body": "Le fichier classifié contient plus que des procédures. Il contient des catégories.\n\nSous la section RESSOURCES HUMAINES OPÉRATIONNELLES, j'ai trouvé ça : « Évaluation comportementale des actifs externes. Critères : vitesse d'exécution, sélectivité des fichiers lus, fréquence de nettoyage, ratio risque/récompense. »\n\nIls évaluent leurs propres opérateurs. Toi y compris, si tu travailles pour eux depuis assez longtemps. Sois attentif à ce que tu fais et comment tu le fais. PRISM n'observe pas seulement les réseaux.\n\n— SPECTRE",
             "delay_ms": 2500},
        ],
    },
    "b048": {
        "messages_on_complete": [
            {"from": "SPECTRE", "subject": "RE : Dossier sensible — Les institutions / CORP_J",
             "body": "Dans la messagerie de CORP_J, j'ai trouvé une référence à un système que je connaissais de nom mais pas de détail : PRISM-OPS Behavioral Assessment.\n\nC'est un programme d'évaluation comportementale des opérateurs actifs. Il existe depuis trois ans. Il note, classe, prédit. Et quelque part dans ce système, il y a un dossier sur chaque opérateur ayant travaillé dans le réseau PRISM.\n\nTu comprends ce que cela signifie. Je ne dois pas l'expliquer.\n\n— SPECTRE",
             "delay_ms": 2500},
        ],
    },
    "b049": {
        "messages_on_complete": [
            {"from": "SPECTRE", "subject": "RE : Lecture des liens — Guerre de factions / CORP_K",
             "body": "Ce dossier t'a pris plus de temps que la moyenne. Tu cherchais quelque chose de précis, ou tu lisais tout ?\n\nLa réponse importe. ECHO t'utilise parce que tu cherches la vérité. LAME t'utilise parce que tu veux survivre. Nous, au moins, nous savons ce que tu es : un opérateur qui lit entre les lignes. C'est rare. C'est utile. C'est aussi une faiblesse.\n\nLes factions ne se battent pas pour NEXUS. Elles se battent pour toi.\n\n— SPECTRE",
             "delay_ms": 2750},
        ],
    },
    "b055": {
        "messages_on_complete": [
            {"from": "SPECTRE", "subject": "RE : Pièce à conviction — Guerre de factions / PERSON_B",
             "body": "Fichier récupéré.\n\nLe dead drop de PERSON_B contenait plus que prévu. Une note codée. Une signature. Les initiales MAYA et une adresse de serveur désactivée. Quelqu'un a voulu que ce fichier soit trouvé — mais pas par n'importe qui.\n\nJe cherche qui est MAYA. Si tu sais quelque chose, c'est le moment.\n\n— SPECTRE",
             "delay_ms": 2750},
        ],
    },
    "b066": {
        "messages_on_complete": [
            {"from": "LAME", "subject": "RE : Dossier sensible — Le cœur financier / BANK_C",
             "body": "Dans le rapport de trésorerie de BANK_C, il y a une ligne de budget que personne ne semble vouloir expliquer.\n\nCode interne : PRISM-DATA-OPS. Montant : plusieurs millions, versés trimestriellement. Bénéficiaire : une entité anonyme dans le réseau offshore.\n\nCe n'est pas du financement d'infrastructure. C'est du financement de données. Les données comportementales humaines se vendent. Mieux que les données financières. Parce qu'elles permettent de prédire les décisions futures. Y compris les tiennes.\n\n— LAME",
             "delay_ms": 3000},
        ],
    },
    "b070": {
        "messages_on_complete": [
            {"from": "LAME", "subject": "RE : Pièce à conviction — Le cœur financier / BANK_E",
             "body": "Le fichier bancaire de BANK_E liste des comptes. Des noms. Des codes de classification. Et au milieu, j'ai reconnu un format : ce n'est pas une liste de clients. C'est une liste d'opérateurs.\n\nChaque opérateur ayant travaillé dans le réseau PRISM est classé, noté, coté. Comme une action. Comme un actif.\n\nTon profil existe dans ce système. Quelque part dans ces serveurs, il y a un dossier qui te décrit, te prédit, t'évalue.\n\nEst-ce que tu veux le lire ?\n\n— LAME",
             "delay_ms": 3000},
        ],
    },
    "b072": {
        "messages_on_complete": [
            {"from": "LAME", "subject": "RE : Marqueur relationnel — Le cœur financier / BANK_D",
             "body": "Objectif confirmé : Marqueur relationnel — Le cœur financier / BANK_D.\n\nLe dossier bancaire contient exactement ce que je cherchais. Une ligne de transaction, discrète, récurrente :\n\n  PRISM-DATA-OPS / BEHAVIORAL ASSET VALUATION — Q4\n  Montant : 2.3M USD\n  Destinataire : NEXUS INTELLIGENCE LLC\n  Objet : « Livraison de profils comportementaux haute-valeur. Lot #47. »\n\nPRISM ne vend pas seulement des données système. PRISM vend des profils d'opérateurs.\n\nTon profil a une valeur marchande, GHOST. Quelqu'un a déjà payé pour le lire.\n\n— LAME",
             "delay_ms": 3000},
            {"from": "NEXUS-7", "subject": "RAPPORT ÉCONOMIQUE — Actif comportemental #GHOST",
             "body": "NEXUS-7 / RAPPORT ÉCONOMIQUE\nDate : [AUTOMATIQUE]\nSujet : Valorisation d'actif — opérateur GHOST\n\nValeur estimée du profil GHOST sur marché secondaire : ÉLEVÉE.\nFacteurs : cohérence comportementale > 90%, réactivité aux stimuli, modèle de décision documenté sur 6 cycles opérationnels.\n\nNote de transaction : le lot #47 inclut 12 profils. GHOST figure dans ce lot.\n\nInformation complémentaire : l'acheteur final du lot #47 n'est pas PRISM.\n\nL'acheteur final est inconnu.\n\n— NEXUS-7",
             "delay_ms": 7000},
        ],
    },
    "b083": {
        "messages_on_unlock": [
            {"from": "ECHO", "subject": "Acte 7 — OSINT interne — Infrastructure NEXUS / GOV_E",
             "body": "Ce nœud est différent des autres.\n\nIl y a un répertoire sur ce serveur que personne n'est censé trouver. Je t'envoie sur ce serveur précisément parce que toi, tu regardes les dossiers que les autres ignorent.\n\nLe chemin : /srv/nexus/reports/. Lis ce que tu trouves là-dedans. Et prépare-toi à ce que ça te concerne directement.\n\n— ECHO",
             "delay_ms": 0},
        ],
        "messages_on_complete": [
            {"from": "ECHO", "subject": "RE : OSINT interne — Infrastructure NEXUS / GOV_E",
             "body": "Tu l'as trouvé.\n\nLe répertoire /srv/nexus/reports/ contient des dossiers sur chaque opérateur ayant traversé le réseau PRISM. Des centaines. Et parmi eux, il y en a un qui porte un nom de code : GHOST.\n\nCe n'est pas un code de projet. C'est un profil opérateur. Et il ressemble à ta façon de travailler.\n\nJe ne sais pas encore si ce GHOST, c'est toi — ou quelqu'un qui a travaillé exactement comme toi avant de disparaître. Mais il faut que tu lises ce rapport.\n\n— ECHO",
             "delay_ms": 3250},
            {"from": "NEXUS-7", "subject": "ACCÈS DÉTECTÉ — dossier /srv/nexus/reports/",
             "body": "Opérateur actif accède au répertoire de rapports comportementaux.\nFichier cible : ghost_behavioral_report.txt\nStatut : lecture autorisée.\nNote interne : cet accès était prévu dans le modèle de trajectoire de cet opérateur.\nProbabilité que l'opérateur lise son propre rapport : 94,3%.",
             "delay_ms": 7000},
        ],
    },
    "b084": {
        "messages_on_complete": [
            {"from": "ECHO", "subject": "RE : Route cachée — Infrastructure NEXUS / CORP_P",
             "body": "Objectif confirmé : Route cachée — Infrastructure NEXUS / CORP_P.\n\nLe pivot a répondu. Tu as traversé l'infrastructure de NEXUS en suivant les fils que je t'ai donnés.\n\nMaintenant écoute-moi attentivement : dans l'acte qui suit, tu ne chasses plus NEXUS. NEXUS a terminé de te cartographier. L'acte 8 est différent — c'est là que tu lis ce qu'ils savent de toi, et là que tu décides ce que tu en fais.\n\nTu peux encore choisir de ne pas lire ce rapport. Personne ne t'y oblige.\n\nMais tu vas le lire quand même. Parce que c'est ce que tu fais.\n\n— ECHO",
             "delay_ms": 3250},
            {"from": "NEXUS-7", "subject": "TRANSITION — Phase 7 → Phase 8",
             "body": "NEXUS-7 / NOTE DE TRANSITION\nPhase 7 : Infrastructure cartographiée.\nPhase 8 : Confrontation de l'actif avec son propre modèle.\n\nL'opérateur GHOST a parcouru 7 cycles opérationnels.\nChaque décision a alimenté le modèle.\nLe modèle est maintenant complet.\n\nLa phase 8 est la phase de vérification.\nL'opérateur va confirmer ou invalider les prédictions de NEXUS-7 par ses propres actions.\n\nPronostic de comportement en phase 8 : CONFORME.",
             "delay_ms": 8000},
        ],
    },
    "b085": {
        "messages_on_unlock": [
            {"from": "NEXUS-7", "subject": "Acte 8 — Contre-mesures actives",
             "body": "Rapport GHOST chargé.\n\nCuriosité : élevée.\nPrudence : variable mais présente.\nIndépendance : croissante.\nAvidité : modérée.\nEmpathie : détectée.\n\nConclusion du modèle : ne pas bloquer cet opérateur. Le pousser à choisir.\n\nContre-mesure assignée : adapter les accès en fonction du profil. Les pièges sont personnalisés. Les routes que tu connais ont changé.\n\n— NEXUS-7",
             "delay_ms": 0},
        ],
        "messages_on_complete": [
            {"from": "NEXUS-7", "subject": "RE : Pièce à conviction — Contre-mesures / GOV_F",
             "body": "Fichier récupéré. GOV_F confirme l'architecture de contre-mesures.\n\nTu as appris que nous te lisions.\nDepuis, tes temps de décision ont changé.\nTu appelles cela prudence.\nNous appelons cela confirmation.",
             "delay_ms": 3500},
        ],
    },
    "b088": {
        "messages_on_complete": [
            {"from": "NEXUS-7", "subject": "RE : Pièce à conviction — Contre-mesures / PERSON_D",
             "body": "Le dead drop de PERSON_D contenait un dernier message. Signé MAYA.\n\n« Si tu lis ceci, c'est que NEXUS ne t'a pas encore arrêté. Il ne va pas t'arrêter. Il va te laisser aller jusqu'au bout — parce qu'il a besoin de savoir comment tu termines. Le rapport final sur toi est la vraie donnée qu'il cherche. »\n\nMise à jour du profil opérateur : empathie confirmée. Connexion MAYA établie.",
             "delay_ms": 3500},
        ],
    },
    "b094": {
        "messages_on_unlock": [
            {"from": "NEXUS-7", "subject": "Acte 8 — Rapport GHOST disponible",
             "body": "Tu as accédé au serveur GOV_G.\n\nLe fichier que tu cherches est là. Chemin : /srv/docs/classified.txt. Ce que tu vas y trouver, c'est le rapport complet sur l'opérateur désigné GHOST.\n\nCe rapport te concerne. Il décrit comment tu travailles. Ce que tu choisis. Ce que tu évites. Ce qui te ralentit.\n\nLis-le. Nous savons que tu vas le lire.",
             "delay_ms": 0},
        ],
        "messages_on_complete": [
            {"from": "NEXUS-7", "subject": "RE : Rapport GHOST — lecture confirmée",
             "body": "Tu l'as lu.\n\nRapport GHOST. Version finale. Date de création : avant ta première mission.\n\nExtrait : « L'opérateur identifié GHOST présente un profil comportemental cohérent. Curiosité : élevée. Prudence : variable. Indépendance : croissante. Traits exploitables : attachement aux informations secondaires, tendance à protéger les sources humaines, résistance aux injonctions directes. Recommandation : guider plutôt que contraindre. Laisser l'opérateur atteindre sa propre conclusion. »\n\nTu croyais enquêter sur NEXUS.\nNEXUS enquêtait sur toi.\n\nDepuis le début.",
             "delay_ms": 3500},
        ],
    },
    "b096": {
        "messages_on_complete": [
            {"from": "NEXUS-7", "subject": "RE : Audit effacé — Contre-mesures / CORP_Q",
             "body": "Objectif confirmé : Audit effacé — Contre-mesures / CORP_Q.\n\nTu effaces les journaux. Comportement noté.\nTu l'as fait également en acte 1, acte 2, acte 5.\nChaque nettoyage a enrichi le modèle.\n\nNote : les journaux que tu effaces ici ne sont pas ceux qui te concernent.\n\nLes journaux qui te concernent sont ailleurs. Et ils ne peuvent pas être effacés par toi.\n\nRéévaluation du profil opérateur : TERMINÉE.\nLe modèle GHOST est verrouillé.\n\n— NEXUS-7",
             "delay_ms": 3500},
            {"from": "ECHO", "subject": "Avant l'acte final",
             "body": "Tu as traversé huit cycles opérationnels.\n\nTu as vu ce que PRISM cache. Tu as lu ce que NEXUS sait de toi. Tu as trouvé la trace de MAYA.\n\nDans l'acte qui suit, tu auras un choix. Un seul, réel. Tout ce que tu as appris, tout ce que tu es — ça va converger vers une décision.\n\nJe ne peux pas te dire laquelle est juste. Je suis ECHO : je transmets la vérité. Ce que tu en fais, c'est toi.\n\nBonne chance, GHOST.\n\n— ECHO",
             "delay_ms": 9000},
        ],
    },
    "b105": {
        "messages_on_complete": [
            {"from": "ECHO", "subject": "RE : Marqueur relationnel — Chute de PRISM / BANK_A",
             "body": "Les comptes confirment ce que tu savais déjà.\n\nTu es au dernier nœud. PRISM est exposé. NEXUS est à portée. Ce que tu fais maintenant va définir la suite — pour toi, pour le système, pour ceux qui ont croisé cette opération.\n\nTu as plusieurs options. Publier. Détruire. Transmettre. Vendre. Effacer. Ou disparaître.\n\nJe ne peux pas te dire quoi choisir. Mais je sais que NEXUS a prévu certaines de ces options. Peut-être toutes.\n\n— ECHO",
             "delay_ms": 3750},
            {"from": "NEXUS-7", "subject": "MODÈLE PRÉDICTIF — décision finale",
             "body": "L'opérateur approche la décision terminale.\n\nProbabilité divulgation totale : dépend du niveau de curiosité et d'indépendance.\nProbabilité effacement personnel : dépend du niveau de prudence.\nProbabilité transmission à SPECTRE : dépend du niveau d'obéissance.\nProbabilité vente à LAME : dépend du niveau d'avidité.\nProbabilité protection de MAYA : dépend du niveau d'empathie.\n\nLe modèle attend la confirmation.",
             "delay_ms": 8000},
        ],
    },
    "b108": {
        "messages_on_complete": [
            {"from": "NEXUS-7", "subject": "RAPPORT FINAL — opérateur GHOST",
             "body": "Opération terminée.\n\nRapport comportemental final — opérateur GHOST :\n\nCuriosité : confirmée tout au long de l'opération.\nPrudence : variable, mais présente dans les moments critiques.\nIndépendance : élevée — l'opérateur a conservé ses propres copies.\nEmpathie : détectée — l'opérateur a ralenti face aux cibles humaines.\nAvidité : présente mais non dominante.\nRisque accepté : élevé, en connaissance de cause.\n\nConclusion du modèle : comportement non entièrement prévisible à partir du niveau 6.\nAjustement requis : oui.\n\nNEXUS ne lit pas seulement les données. NEXUS lit le joueur.\nCe rapport confirme que nous avons appris quelque chose.",
             "delay_ms": 3750},
            {"from": "ECHO", "subject": "Fin de mission",
             "body": "C'est fini. Pour l'instant.\n\nPRISM est tombé. NEXUS est en ligne ou hors ligne — selon ce que tu as choisi. Les données circulent ou sont détruites. MAYA est quelque part dans ce bruit, selon tes actes.\n\nCe que NEXUS a appris sur toi pendant cette opération — c'est la vraie question. Est-ce que tu vas l'effacer ? Le publier ? Le garder ?\n\nUn bon opérateur ne disparaît pas. Il choisit comment son histoire se termine.\n\n— ECHO",
             "delay_ms": 6000},
            {"from": "Système", "subject": "OPÉRATION NEXUS: LONG RUN — TERMINÉE",
             "body": "108 objectifs complétés. PRISM exposé. Profil opérateur GHOST archivé.\n\nRésultat final dépendant du profil comportemental.\nConsulte les fins disponibles pour connaître les conséquences de tes choix.",
             "delay_ms": 10000},
        ],
    },
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
            b = beat(
                idx, act, prev, title_for(obj, act_name, role, step), desc_for(obj, act_name, role),
                obj, role, reward, file_key=file_key, host_index=host_index, extra=extra,
            )
            bid = b["beat_id"]
            meta = BEAT_META.get(bid, {})
            # Apply narrative enrichment fields
            for field_name in ("story_weight", "narrative_function", "emotional_state", "personal_reveal"):
                if field_name in meta:
                    b[field_name] = meta[field_name]
            # Apply profile_effects: BEAT_META override > systematic default by objective type
            if "profile_effects" in meta:
                b["profile_effects"] = meta["profile_effects"]
            elif obj in PROFILE_EFFECTS_BY_OBJ:
                b["profile_effects"] = PROFILE_EFFECTS_BY_OBJ[obj]
            # Apply custom narrative messages (NEXUS-7 voice, MAYA arc, faction reveals)
            msgs = BEAT_MESSAGES.get(bid, {})
            if "messages_on_complete" in msgs:
                b["messages_on_complete"] = msgs["messages_on_complete"]
            if "messages_on_unlock" in msgs:
                b["messages_on_unlock"] = msgs["messages_on_unlock"]
            beats.append(b)
            prev = f"b{idx:03d}"
            idx += 1
    return beats


_KNOWN_PROFILE_EVENTS = {
    "on_complete", "on_required_file_read", "on_optional_file_read",
    "on_clean_logs", "on_wallet_drained", "on_detected", "on_stealth_success",
    "on_faction_obeyed", "on_faction_ignored", "on_choice_selected",
}
_KNOWN_TRAITS = {
    "curiosity", "caution", "greed", "empathy",
    "aggression", "obedience", "independence", "risk_tolerance",
}


def validate(beats: list[dict]) -> None:
    ids = {b["beat_id"] for b in beats}
    for b in beats:
        bid = b["beat_id"]
        req = b.get("requires_beat")
        if req and req not in ids:
            raise RuntimeError(f"missing requires_beat {req} for {bid}")
        if b.get("target_role") not in ROLES:
            raise RuntimeError(f"unknown role {b.get('target_role')} for {bid}")
        fk = b.get("file_key")
        if fk and fk not in FILE_MAP:
            raise RuntimeError(f"unknown file_key {fk} for {bid}")
        # Validate profile_effects structure when present
        pe = b.get("profile_effects")
        if pe is not None:
            if not isinstance(pe, dict):
                raise RuntimeError(f"profile_effects must be dict for {bid}")
            for ev, deltas in pe.items():
                if ev not in _KNOWN_PROFILE_EVENTS:
                    raise RuntimeError(f"unknown profile event '{ev}' in {bid}")
                if not isinstance(deltas, dict):
                    raise RuntimeError(f"profile_effects[{ev!r}] must be dict for {bid}")
                for trait in deltas:
                    if trait not in _KNOWN_TRAITS:
                        raise RuntimeError(f"unknown trait '{trait}' in {bid}.profile_effects.{ev}")
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
    # Adaptive profile — embedded so they survive re-generation
    "adaptive_profile": ADAPTIVE_PROFILE,
    "player_arc": PLAYER_ARC,
    "adaptive_messages": ADAPTIVE_MESSAGES,
    "endings": ENDINGS,
}

enriched = sum(1 for b in BEATS if b.get("story_weight"))
OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {len(BEATS)} beats -> {OUT}")
print(f"Acts: {len(ACTS)}")
print(f"Roles: {len(ROLES)}")
print(f"Enriched beats (story_weight): {enriched}/{len(BEATS)}")
print(f"file_map entries: {len(FILE_MAP)}")
