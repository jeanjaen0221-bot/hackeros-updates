"""core.worldgen.places — enrichissement des lieux et peuplement en PNJ.

Un lieu généré ne portait que six champs : identifiant, district, catégorie,
nom, x, y. Rien d'autre. Le joueur pouvait voyager jusqu'à lui et n'y trouver
strictement rien — un tiers des lieux n'héberge d'ailleurs aucune cible.

Ce module donne au lieu une existence propre : horaires, sécurité, affluence,
réseau sans fil, ambiance, et occupants. Ces attributs ne sont pas décoratifs,
ils sont exploitables :

- ``hours``     : un lieu fermé est désert — moins d'observation, mais accès
                  physique impossible ;
- ``footfall``  : la foule masque le joueur mais sature le wifi ;
- ``security``  : conditionne le risque et le bruit d'une intrusion ;
- ``wifi``      : un point d'accès public est une porte d'entrée ;
- ``npcs``      : des occupants, dont certains portent des identifiants ou des
                  informations exploitables.

Tout est dérivé d'un ``random.Random`` fourni par l'appelant : à seed constante
le monde est identique.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List

# ── Profils par catégorie ────────────────────────────────────────────────────
# security  : 1 (portes ouvertes) → 5 (sas, biométrie, vigiles)
# footfall  : fréquentation typique aux heures d'ouverture, 0.0 → 1.0
# hours     : (ouverture, fermeture) en heures locales ; (0, 24) = toujours
# wifi      : probabilité d'un point d'accès, et s'il est public
_PROFILES: Dict[str, Dict[str, Any]] = {
    "bank":                {"security": (4, 5), "footfall": (0.3, 0.6), "hours": (9, 17),  "wifi": 0.9, "public_wifi": False},
    "government_building": {"security": (4, 5), "footfall": (0.3, 0.7), "hours": (8, 18),  "wifi": 0.9, "public_wifi": False},
    "office":              {"security": (3, 4), "footfall": (0.4, 0.8), "hours": (8, 19),  "wifi": 0.95, "public_wifi": False},
    "coworking":           {"security": (2, 3), "footfall": (0.5, 0.9), "hours": (7, 22),  "wifi": 1.0, "public_wifi": True},
    "clinic":              {"security": (3, 4), "footfall": (0.4, 0.8), "hours": (7, 20),  "wifi": 0.8, "public_wifi": True},
    "shop":                {"security": (1, 3), "footfall": (0.4, 0.9), "hours": (9, 20),  "wifi": 0.6, "public_wifi": True},
    "mall":                {"security": (2, 4), "footfall": (0.7, 1.0), "hours": (10, 21), "wifi": 1.0, "public_wifi": True},
    "cafe":                {"security": (1, 2), "footfall": (0.5, 1.0), "hours": (7, 19),  "wifi": 1.0, "public_wifi": True},
    "restaurant":          {"security": (1, 2), "footfall": (0.4, 0.9), "hours": (11, 23), "wifi": 0.9, "public_wifi": True},
    "bar":                 {"security": (1, 3), "footfall": (0.5, 1.0), "hours": (17, 2),  "wifi": 0.8, "public_wifi": True},
    "venue":               {"security": (2, 3), "footfall": (0.3, 1.0), "hours": (18, 2),  "wifi": 0.8, "public_wifi": True},
    "library":             {"security": (2, 3), "footfall": (0.2, 0.6), "hours": (9, 19),  "wifi": 1.0, "public_wifi": True},
    "gym":                 {"security": (2, 3), "footfall": (0.3, 0.8), "hours": (6, 23),  "wifi": 0.9, "public_wifi": True},
    "hotel":               {"security": (3, 4), "footfall": (0.3, 0.7), "hours": (0, 24),  "wifi": 1.0, "public_wifi": True},
    "hostel":              {"security": (1, 2), "footfall": (0.4, 0.9), "hours": (0, 24),  "wifi": 1.0, "public_wifi": True},
    "transit":             {"security": (2, 3), "footfall": (0.6, 1.0), "hours": (5, 1),   "wifi": 0.7, "public_wifi": True},
    "train_station":       {"security": (3, 4), "footfall": (0.7, 1.0), "hours": (5, 1),   "wifi": 0.9, "public_wifi": True},
    "home":                {"security": (1, 2), "footfall": (0.0, 0.2), "hours": (0, 24),  "wifi": 0.85, "public_wifi": False},
}
_DEFAULT_PROFILE = {"security": (2, 3), "footfall": (0.3, 0.7), "hours": (9, 18),
                    "wifi": 0.7, "public_wifi": False}

# Catégories ajoutées pour donner un caractère propre à chaque type de quartier.
_PROFILES.update({
    "warehouse":  {"security": (2, 4), "footfall": (0.1, 0.4), "hours": (6, 20),  "wifi": 0.5, "public_wifi": False},
    "pharmacy":   {"security": (2, 3), "footfall": (0.4, 0.8), "hours": (8, 20),  "wifi": 0.7, "public_wifi": False},
    "school":     {"security": (2, 3), "footfall": (0.5, 0.9), "hours": (8, 18),  "wifi": 0.9, "public_wifi": False},
    "workshop":   {"security": (1, 3), "footfall": (0.2, 0.5), "hours": (8, 18),  "wifi": 0.6, "public_wifi": False},
    "datacenter": {"security": (5, 5), "footfall": (0.0, 0.2), "hours": (0, 24),  "wifi": 0.4, "public_wifi": False},
    "police":     {"security": (5, 5), "footfall": (0.3, 0.6), "hours": (0, 24),  "wifi": 0.8, "public_wifi": False},
})

# ── Composition d'un quartier ────────────────────────────────────────────────
# Le type de quartier n'était que décoratif : la génération produisait partout
# le même mélange (1 banque, 2-6 boutiques, 1-3 lieux divers), si bien qu'un
# quartier « nightlife » comptait neuf boutiques et aucun bar, et qu'un quartier
# « residential » n'abritait aucun logement. Chaque type reçoit désormais une
# composition plausible, exprimée en (catégorie, minimum, maximum).
_DISTRICT_PLANS: Dict[str, List[tuple]] = {
    "residential": [("home", 5, 10), ("shop", 2, 4), ("cafe", 1, 3),
                    ("pharmacy", 0, 2), ("clinic", 0, 1), ("gym", 0, 2),
                    ("school", 0, 1), ("transit", 1, 2)],
    "business":    [("office", 4, 8), ("coworking", 1, 3), ("cafe", 2, 4),
                    ("bank", 1, 3), ("restaurant", 1, 3), ("hotel", 0, 1),
                    ("transit", 1, 2)],
    "financial":   [("bank", 4, 7), ("office", 3, 6), ("cafe", 1, 2),
                    ("restaurant", 0, 2), ("police", 0, 1), ("transit", 1, 2)],
    "nightlife":   [("bar", 3, 6), ("restaurant", 2, 4), ("venue", 1, 3),
                    ("hostel", 1, 2), ("shop", 1, 3), ("cafe", 0, 2),
                    ("transit", 1, 2)],
    "industrial":  [("warehouse", 3, 6), ("workshop", 2, 4), ("transit", 1, 3),
                    ("shop", 0, 2), ("cafe", 0, 1), ("datacenter", 0, 1)],
    "campus":      [("library", 1, 3), ("school", 1, 3), ("cafe", 2, 4),
                    ("coworking", 1, 3), ("gym", 1, 2), ("hostel", 0, 2),
                    ("shop", 1, 2)],
    "civic":       [("government_building", 3, 6), ("library", 1, 2),
                    ("clinic", 1, 2), ("police", 0, 1), ("cafe", 0, 2),
                    ("transit", 1, 2)],
    "transport":   [("train_station", 1, 2), ("transit", 3, 5), ("hotel", 1, 2),
                    ("shop", 2, 4), ("cafe", 1, 3), ("warehouse", 0, 2)],
    "medical":     [("clinic", 3, 6), ("pharmacy", 2, 4), ("cafe", 0, 2),
                    ("shop", 0, 2), ("transit", 1, 2)],
    "mixed":       [("shop", 2, 5), ("home", 2, 5), ("cafe", 1, 3),
                    ("office", 1, 3), ("bank", 0, 2), ("clinic", 0, 1),
                    ("transit", 1, 2), ("venue", 0, 1)],
}


def district_place_plan(r: random.Random, kind: str) -> List[str]:
    """Liste des catégories à instancier pour un quartier de ce type.

    L'ordre est mélangé pour que la disposition sur la carte ne trahisse pas
    l'ordre du plan.
    """
    plan = _DISTRICT_PLANS.get(str(kind), _DISTRICT_PLANS["mixed"])
    out: List[str] = []
    for category, lo, hi in plan:
        for _ in range(r.randint(int(lo), int(hi))):
            out.append(category)
    r.shuffle(out)
    return out

# Traits physiques observables, tirés selon la sécurité du lieu.
_TAGS_BY_SECURITY: Dict[int, List[str]] = {
    1: ["accès libre", "porte simple", "pas de caméra"],
    2: ["caméra à l'entrée", "accès libre en journée", "personnel réduit"],
    3: ["badge requis", "caméras intérieures", "accueil filtrant"],
    4: ["badge + code", "vidéosurveillance continue", "vigile en poste"],
    5: ["sas d'entrée", "biométrie", "vigiles 24 h/24", "zone sous alarme"],
}

_AMBIANCE = {
    "bank": ["file d'attente aux guichets", "hall marbré, écrans de cotation",
             "distributeurs en façade, caméra orientée sur le trottoir"],
    "government_building": ["couloirs administratifs, portes numérotées",
                            "salle d'attente saturée", "archives au sous-sol"],
    "office": ["open space éclairé tard", "plateau ouvert, badges sur les bureaux",
               "salles de réunion vitrées"],
    "coworking": ["bureaux partagés, casques sur les oreilles",
                  "cabines téléphoniques occupées", "imprimante en libre-service"],
    "clinic": ["salle d'attente calme", "bornes d'accueil tactiles",
               "couloir vers l'imagerie"],
    "shop": ["rayons serrés, caisse unique", "vitrine sur rue, arrière-boutique",
             "terminal de paiement en évidence"],
    "mall": ["galerie centrale, musique diffuse", "escalators, boutiques alignées",
             "food court à l'étage"],
    "cafe": ["comptoir bondé, prises rares", "terrasse sur rue, wifi affiché",
             "tables serrées, conversations audibles"],
    "restaurant": ["salle en service, cuisine ouverte", "réservations affichées à l'entrée"],
    "bar": ["lumière basse, musique forte", "arrière-salle discrète"],
    "venue": ["hall d'accueil, vestiaire", "salle modulable, régie technique"],
    "library": ["salles de lecture silencieuses", "postes publics en libre accès",
                "rayonnages, coin numérique"],
    "gym": ["vestiaires, casiers à code", "plateau cardio, écrans muets"],
    "hotel": ["réception ouverte la nuit", "ascenseurs à badge, couloirs feutrés"],
    "hostel": ["dortoirs, communs bruyants", "réception improvisée, tableau d'annonces"],
    "transit": ["quais, flux constant", "guichets automatiques, panneaux d'affichage"],
    "train_station": ["hall des départs, annonces continues", "consignes automatiques"],
    "home": ["immeuble résidentiel, interphone", "pavillon, boîte aux lettres pleine",
             "étage calme, paillasson usé"],
}

# ── Composition des noms ─────────────────────────────────────────────────────
# Les listes fixes d'origine étaient trop courtes : 7 noms de banque pour 31
# banques, d'où des doublons visibles dans un même district. La composition
# porte le nombre de combinaisons à plusieurs milliers par catégorie.
_NAME_PARTS: Dict[str, Dict[str, List[str]]] = {
    "bank": {
        "a": ["Union", "Civic", "Metro", "Nova", "Harbor", "Crescent", "Omni",
              "Meridian", "Sterling", "Aegis", "Clearwater", "Northgate"],
        "b": ["Bank", "Trust", "Clearing", "Capital", "Finance", "Savings",
              "Credit", "Holdings"],
    },
    "shop": {
        "a": ["Tech", "Corner", "Quick", "Electro", "Pharma", "Market", "Byte",
              "Med", "Parcel", "Data", "Metro", "Volt", "Urban", "Prime"],
        "b": ["Mart", "Shop", "Buy", "Hub", "Plus", "One", "Point", "Depot",
              "Store", "Kiosk", "Supply"],
    },
    "cafe": {
        "a": ["Byte", "Roast", "Steam", "Corner", "Loop", "Static", "Amber", "Pixel"],
        "b": ["Café", "Coffee", "Brew", "Bar", "House", "Roasters"],
    },
    "office": {
        "a": ["Vertex", "Summit", "Atlas", "Pinnacle", "Beacon", "Keystone",
              "Lumen", "Corvus", "Halcyon", "Ridge"],
        "b": ["Tower", "Plaza", "Center", "Works", "House", "Building", "Court"],
    },
    "coworking": {
        "a": ["Hive", "Desk", "Node", "Bright", "Loft", "Forge", "Nest"],
        "b": ["Works", "Forge", "House", "Desk", "Space", "Lab"],
    },
    "clinic": {
        "a": ["Care", "North Ward", "Pulse", "Meridian", "Saint-Marc", "Riverside"],
        "b": ["Clinic", "Care", "Health", "Medical", "Center"],
    },
    "transit": {
        "a": ["Metro", "Central", "North", "Harbor", "East", "Parcel"],
        "b": ["Gate", "Stop", "Depot", "Terminal", "Interchange"],
    },
    "venue": {
        "a": ["Forum", "Arcade", "Rooftop", "Echo", "Prism", "Vault"],
        "b": ["Hall", "Loft", "Lounge", "Stage", "Room"],
    },
}
_NAME_PARTS.update({
    "home":        {"a": ["Résidence", "Villa", "Immeuble", "Cité", "Le Clos"],
                    "b": ["des Tilleuls", "Beaulieu", "Nord", "Saint-Roch",
                          "du Canal", "Verte", "Haute", "des Acacias"]},
    "bar":         {"a": ["Le", "Chez", "L'"], "b": ["Sextant", "Néon", "Comptoir",
                    "Refuge", "Zinc", "Alibi", "Décibel", "Fuseau"]},
    "restaurant":  {"a": ["Table", "Maison", "Bistrot", "Cantine"],
                    "b": ["du Port", "Rossi", "Nord", "Verdier", "Bleue", "Populaire"]},
    "library":     {"a": ["Bibliothèque", "Médiathèque"],
                    "b": ["Centrale", "Diderot", "du Nord", "Curie", "Ampère"]},
    "gym":         {"a": ["Iron", "Pulse", "Urban", "Core"], "b": ["Gym", "Club", "Fit", "Box"]},
    "hotel":       {"a": ["Hôtel", "Résidence"], "b": ["Central", "du Port", "Meridian",
                    "Continental", "Nord", "Astoria"]},
    "hostel":      {"a": ["Auberge", "Hostel"], "b": ["du Canal", "Nord", "Central", "Nomade"]},
    "warehouse":   {"a": ["Entrepôt", "Dépôt", "Hangar"],
                    "b": ["Nord", "Est", "12", "Portuaire", "Central", "B4"]},
    "workshop":    {"a": ["Atelier", "Garage", "Fonderie"],
                    "b": ["Marchand", "du Canal", "Nord", "Bertin", "Central"]},
    "pharmacy":    {"a": ["Pharmacie"], "b": ["Centrale", "du Marché", "Saint-Roch",
                    "de la Gare", "Nord"]},
    "school":      {"a": ["École", "Lycée", "Collège"],
                    "b": ["Jean-Moulin", "Curie", "du Parc", "Voltaire", "Nord"]},
    "datacenter":  {"a": ["DC", "Datacenter", "Nexus"], "b": ["Nord", "Alpha", "B2", "Est"]},
    "police":      {"a": ["Commissariat", "Poste"], "b": ["Central", "du 3e", "Nord", "de Quartier"]},
    "train_station": {"a": ["Gare"], "b": ["Centrale", "du Nord", "Saint-Marc", "de l'Est"]},
    "mall":        {"a": ["Centre", "Galerie"], "b": ["Commercial", "Marchande", "Atrium", "Forum"]},
    "government_building": {"a": ["Préfecture", "Mairie", "Direction", "Service"],
                            "b": ["Centrale", "du Cadastre", "des Impôts", "Régionale"]},
})

_GENERIC_PARTS = {
    "a": ["Central", "North", "South", "East", "West", "Old", "New", "Grand",
          "Union", "Harbor", "Park", "River"],
    "b": ["Place", "House", "Point", "Corner", "Gallery", "Court", "Center"],
}


def compose_name(r: random.Random, category: str, used: set) -> str:
    """Nom composé, unique dans la limite du raisonnable."""
    parts = _NAME_PARTS.get(str(category), _GENERIC_PARTS)
    a, b = parts["a"], parts["b"]
    # Les enseignes commerciales se collent (« NovaTrust »), les toponymes
    # français gardent leur espace (« Résidence des Tilleuls »).
    glued = str(category) in ("bank", "shop", "cafe", "coworking", "gym",
                              "datacenter", "office")
    for _ in range(24):
        sep = "" if glued else " "
        name = f"{r.choice(a)}{sep}{r.choice(b)}".strip()
        if name not in used:
            used.add(name)
            return name
    # Toutes les combinaisons proches sont prises : on distingue par un suffixe
    # d'agence, ce qui reste crédible pour une enseigne.
    base = f"{r.choice(a)} {r.choice(b)}".strip()
    n = 2
    while f"{base} {n}" in used:
        n += 1
    name = f"{base} {n}"
    used.add(name)
    return name


# ── PNJ ──────────────────────────────────────────────────────────────────────
_FIRST = ["Léa", "Marc", "Sofia", "Yanis", "Claire", "Idriss", "Nora", "Hugo",
          "Amel", "Tom", "Rita", "Samuel", "Inès", "Victor", "Maya", "Karim",
          "Elsa", "Bruno", "Nadia", "Théo", "Lucie", "Anton", "Sarah", "Malik"]
_LAST = ["Vasseur", "Merlin", "Abadi", "Nowak", "Kestrel", "Dorsay", "Faure",
         "Lindqvist", "Barros", "Chen", "Okafor", "Rovel", "Marchetti",
         "Sandoval", "Weiss", "Petit", "Haddad", "Novak"]

_ROLES: Dict[str, List[str]] = {
    "bank": ["conseiller clientèle", "responsable d'agence", "agent de sécurité",
             "analyste conformité"],
    "government_building": ["agent d'accueil", "archiviste", "chef de service",
                            "technicien informatique"],
    "office": ["développeur", "assistante de direction", "comptable",
               "administrateur système", "stagiaire"],
    "coworking": ["freelance", "gestionnaire de site", "consultant"],
    "clinic": ["infirmier", "médecin", "secrétaire médicale", "technicien"],
    "shop": ["vendeur", "gérant", "livreur"],
    "mall": ["agent de sécurité", "vendeur", "technicien de maintenance"],
    "cafe": ["barista", "gérante", "habitué"],
    "restaurant": ["serveur", "chef de rang", "gérant"],
    "bar": ["barman", "videur", "habitué"],
    "venue": ["régisseur", "agent d'accueil", "technicien son"],
    "library": ["bibliothécaire", "étudiant", "agent d'entretien"],
    "gym": ["coach", "réceptionniste", "abonné"],
    "hotel": ["réceptionniste", "gouvernante", "concierge de nuit"],
    "hostel": ["gérant", "voyageur", "bénévole"],
    "transit": ["agent de quai", "contrôleur", "voyageur"],
    "train_station": ["agent d'escale", "contrôleur", "commerçant"],
    "home": ["résident", "voisin", "gardien d'immeuble"],
}
_DEFAULT_ROLES = ["employé", "visiteur", "agent d'entretien"]

# Un PNJ peut porter quelque chose d'exploitable. Rare, sinon l'information
# perd sa valeur et le monde devient un distributeur.
_LEAK_KINDS = [
    ("badge", "laisse son badge sur le comptoir"),
    ("credentials", "note ses identifiants sur un carnet"),
    ("gossip", "parle trop fort d'un incident interne"),
    ("schedule", "commente les horaires de l'équipe technique"),
    ("wifi_key", "dicte la clé wifi à un collègue"),
]


def _npc_count(r: random.Random, category: str, footfall: float) -> int:
    if category == "home":
        return r.randint(1, 3)
    base = 1 + int(round(footfall * 4))
    return max(1, min(6, r.randint(max(1, base - 1), base + 1)))


def generate_npcs(r: random.Random, place: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Occupants d'un lieu, avec rôle, présence horaire et fuite éventuelle."""
    category = str(place.get("category", ""))
    roles = _ROLES.get(category, _DEFAULT_ROLES)
    footfall = float(place.get("footfall", 0.5))
    open_h, close_h = place.get("hours", {}).get("open", 9), place.get("hours", {}).get("close", 18)

    npcs: List[Dict[str, Any]] = []
    for i in range(_npc_count(r, category, footfall)):
        role = r.choice(roles)
        # Le personnel suit les horaires du lieu ; les visiteurs passent.
        staff = role not in ("visiteur", "habitué", "abonné", "voyageur",
                             "étudiant", "voisin", "résident")
        npc = {
            "npc_id": f"{place.get('place_id', 'p')}:npc:{i}",
            "name": f"{r.choice(_FIRST)} {r.choice(_LAST)}",
            "role": role,
            "staff": staff,
            "present": {"from": int(open_h), "to": int(close_h)} if staff
                       else {"from": 0, "to": 24},
        }
        # 18 % des PNJ laissent quelque chose d'exploitable.
        if r.random() < 0.18:
            kind, detail = r.choice(_LEAK_KINDS)
            npc["leak"] = {"kind": kind, "detail": detail}
        npcs.append(npc)
    return npcs


# ── Enrichissement ───────────────────────────────────────────────────────────

def _footfall_label(value: float) -> str:
    if value < 0.15:
        return "désert"
    if value < 0.35:
        return "calme"
    if value < 0.6:
        return "modéré"
    if value < 0.85:
        return "dense"
    return "bondé"


def enrich_place(r: random.Random, place: Dict[str, Any],
                 district_kind: str = "mixed") -> Dict[str, Any]:
    """Complète un lieu avec ses attributs exploitables. Modifie et renvoie."""
    category = str(place.get("category", ""))
    profile = _PROFILES.get(category, _DEFAULT_PROFILE)

    sec_lo, sec_hi = profile["security"]
    security = r.randint(sec_lo, sec_hi)
    # Un quartier d'affaires durcit ce qu'il abrite ; un quartier résidentiel
    # l'assouplit. La sécurité cesse d'être uniforme d'un bout à l'autre du monde.
    if district_kind in ("business", "financial", "government", "civic"):
        security = min(5, security + 1)
    elif district_kind in ("residential", "nightlife"):
        security = max(1, security - 1)

    foot_lo, foot_hi = profile["footfall"]
    footfall = round(r.uniform(foot_lo, foot_hi), 2)

    open_h, close_h = profile["hours"]
    always = (open_h == 0 and close_h == 24)

    place["security"] = int(security)
    place["footfall"] = footfall
    place["footfall_label"] = _footfall_label(footfall)
    place["hours"] = {"open": int(open_h), "close": int(close_h), "always": bool(always)}
    place["tags"] = sorted(r.sample(_TAGS_BY_SECURITY[security],
                                    k=min(2, len(_TAGS_BY_SECURITY[security]))))
    place["ambiance"] = r.choice(_AMBIANCE.get(category, ["lieu sans particularité"]))

    if r.random() < float(profile["wifi"]):
        public = bool(profile["public_wifi"])
        # Un wifi public saturé par la foule est plus lent : la fréquentation
        # devient un paramètre tactique et non un simple décor.
        quality = round(max(0.15, min(1.0, r.uniform(0.45, 0.95) - footfall * 0.25)), 2)
        place["wifi"] = {
            "present": True,
            "public": public,
            "ssid": _wifi_ssid(r, place, public),
            "quality": quality,
        }
    else:
        place["wifi"] = {"present": False}

    place["npcs"] = generate_npcs(r, place)
    return place


def _wifi_ssid(r: random.Random, place: Dict[str, Any], public: bool) -> str:
    name = str(place.get("name", "AP")).replace(" ", "")
    if public:
        return f"{name}-Guest"
    return f"{name}-{r.choice(['NET', 'CORP', 'INT', 'SEC'])}"
