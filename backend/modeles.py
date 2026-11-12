"""Modèles de données : format commun d'une option de transport.

Toutes les sources (OpenRouteService, Travel Impact Model, Transitous, barème)
sont ramenées à ce même format : voir le tableau « Format commun » de CLAUDE.md.

Reste à écrire : Voyage (liste d'étapes, 6 segments au maximum) et Segment
(trajet entre deux étapes, avec ses options).
"""

from dataclasses import dataclass


@dataclass
class Option:
    """Une façon de parcourir un segment (un mode de transport).

    Une valeur à None signifie « pas encore connue », jamais zéro.
    """

    mode: str  # « avion », « train », « bus » ou « voiture »
    distance_km: float
    duree_min: float | None  # durée estimée, en minutes
    prix_min: float | None  # fourchette en euros
    prix_max: float | None
    type_prix: str | None  # « reel » ou « indicatif »
    co2_kg: float  # émissions totales par passager
    intensite_g_pkm: float  # g CO2e par passager·km
    niveau: str  # lettre A à E
    incertitude: tuple[float, float] | None  # (CO2 minimum, CO2 maximum) en kg
    source: dict  # origine de chaque valeur : {"distance": ..., "duree": ..., "prix": ..., "co2": ...}
