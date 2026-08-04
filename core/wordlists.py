"""core.wordlists — espace de mots de passe commun au monde et au marché.

Le bruteforce validait ``password == username`` sur tous les hôtes générés : le
mot de passe *était* l'identifiant. Les six wordlists du marché — jusqu'à
2 200 $ — ne servaient donc strictement à rien.

Ce module définit un espace de mots de passe ordonné par fréquence, du plus
courant au plus rare. Un mot de passe se désigne par son **rang** :

* rang 0-17   : mots de passe universels, présents dans la moindre wordlist ;
* rang élevé  : seules les grandes listes les couvrent.

Le générateur de monde attribue un rang à chaque compte selon le type de cible,
et le marché produit ses échantillons dans le même espace. La couverture d'une
wordlist devient ainsi la vraie variable : acheter plus gros permet d'atteindre
des cibles mieux protégées.

Stdlib uniquement : ce fichier est copié vers ``dev_hub_server`` par
``sync_worldgen.py`` et doit rester importable sans Qt.
"""
from __future__ import annotations

from typing import List

# Tête de liste : mots de passe réellement répandus. Toute wordlist, même la
# plus pauvre, les contient.
COMMON_PASSWORDS: List[str] = [
    "password", "123456", "admin", "qwerty", "letmein", "welcome",
    "monkey", "dragon", "master", "shadow", "sunshine", "princess",
    "iloveyou", "football", "abc123", "michael", "baseball", "superman",
]

# Taille de l'échantillon produit par la plus grande wordlist du marché.
MAX_RANK = 500
# Plancher : la wordlist gratuite couvre les seuls mots de passe universels.
MIN_WORDS = 500
MIN_SAMPLE = 18


def password_at(rank: int) -> str:
    """Mot de passe correspondant à un rang de fréquence."""
    index = max(0, int(rank))
    if index < len(COMMON_PASSWORDS):
        return COMMON_PASSWORDS[index]
    return f"word{index:04d}"


def sample(size: int) -> List[str]:
    """Les ``size`` mots de passe les plus courants, dans l'ordre."""
    count = max(0, int(size))
    return [password_at(i) for i in range(count)]


def sample_size_for(words: int) -> int:
    """Taille d'échantillon jouable pour une wordlist annoncée à ``words``.

    Une wordlist de deux millions d'entrées ne peut pas être parcourue mot à
    mot en jeu : on en dérive un échantillon représentatif et borné.

    L'échelle est logarithmique, et non proportionnelle. Une division linéaire
    (``words / 4000``) écrasait tous les paliers intermédiaires sur le plancher
    de 18 : RockYou 10K, vendue 120 $, offrait exactement le même échantillon
    que la liste gratuite — l'acheter était une perte sèche. Chaque palier du
    catalogue apporte désormais un gain visible.
    """
    count = max(0, int(words))
    if count <= MIN_WORDS:
        return MIN_SAMPLE
    import math

    size = MIN_SAMPLE + 134.0 * math.log10(count / MIN_WORDS)
    return int(min(MAX_RANK, max(MIN_SAMPLE, round(size))))


# ── rangs attribués par le générateur de monde ──────────────────────────────
# Plus la cible est sensible, plus son mot de passe est rare — donc hors de
# portée des petites wordlists.
RANK_RANGES = {
    "person":      (0, 17),
    "public_wifi": (0, 40),
    "company":     (18, 200),
    "government":  (120, 499),
    "bank":        (150, 499),
}
DEFAULT_RANK_RANGE = (0, 60)


def rank_range_for(target_type: str) -> tuple:
    return RANK_RANGES.get(str(target_type or ""), DEFAULT_RANK_RANGE)


def cracked_by(rank: int, wordlist_words: int) -> bool:
    """Une wordlist de ``wordlist_words`` entrées couvre-t-elle ce rang ?"""
    return int(rank) < sample_size_for(wordlist_words)
