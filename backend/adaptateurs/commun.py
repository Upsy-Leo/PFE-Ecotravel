"""Outils partagés par tous les adaptateurs.

- appeler_json()   : interroge une source et renvoie sa réponse JSON.
- avec_repli()     : applique le repli « source en direct, sinon cache ».
- estimer_distance_km(), estimer_duree_min() : troisième niveau du repli (barème),
  quand il n'y a ni source ni cache.
- estimer_duree_avion_min() : durée d'un vol, temps d'aéroport compris.
- estimer_prix()       : fourchette de prix indicative (barème au km).
- construire_option()  : fabrique une Option au format commun.
"""

import json
import math
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.modeles import Option
from backend.moteur_co2 import calculer_co2, trouver_tranche

DOSSIER_BACKEND = Path(__file__).parent.parent
FICHIER_BAREME = DOSSIER_BACKEND / "donnees" / "bareme.json"
FICHIER_BAREME_PRIX = DOSSIER_BACKEND / "donnees" / "bareme_prix.json"

# Le cache est un simple fichier JSON, ignoré par Git. Il ne contient jamais de clé d'API.
FICHIER_CACHE = DOSSIER_BACKEND / "cache" / "reponses.json"
# Tant qu'une réponse en cache est plus récente que ça, on ne réinterroge pas la source
# (cela économise les quotas). Au-delà, on réinterroge, et le cache ne sert que de secours.
FRAICHEUR_CACHE_JOURS = 30


class ErreurSource(Exception):
    """La source n'a pas répondu, a refusé la requête ou a répondu autre chose que prévu."""


# --- Appel d'une source ---


def appeler_json(url, corps=None, entetes=None):
    """Interroge une URL et renvoie la réponse JSON décodée.

    Sans « corps », c'est une requête GET. Avec, c'est un POST en JSON.
    En cas de problème, lève ErreurSource avec la réponse brute (jamais l'URL,
    qui peut contenir une clé).
    """
    entetes = dict(entetes or {})
    donnees = None
    if corps is not None:
        donnees = json.dumps(corps).encode("utf-8")
        entetes["Content-Type"] = "application/json"
    requete = urllib.request.Request(url, data=donnees, headers=entetes)
    try:
        with urllib.request.urlopen(requete, timeout=60) as reponse:
            return json.loads(reponse.read().decode("utf-8"))
    except urllib.error.HTTPError as erreur:
        texte = erreur.read().decode("utf-8", errors="replace")
        raise ErreurSource(f"HTTP {erreur.code} : {texte[:500]}") from erreur
    except (urllib.error.URLError, TimeoutError, ValueError) as erreur:
        raise ErreurSource(f"Pas de réponse exploitable : {erreur}") from erreur


# --- Cache ---


def _lire_cache():
    if not FICHIER_CACHE.exists():
        return {}
    try:
        return json.loads(FICHIER_CACHE.read_text(encoding="utf-8"))
    except ValueError:
        return {}  # fichier abîmé : on repart d'un cache vide


def _ecrire_cache(cle_cache, donnees):
    cache = _lire_cache()
    cache[cle_cache] = {"date": datetime.now(timezone.utc).isoformat(), "donnees": donnees}
    FICHIER_CACHE.parent.mkdir(parents=True, exist_ok=True)
    FICHIER_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def avec_repli(cle_cache, appel_direct):
    """Renvoie (donnees, date_du_cache).

    cle_cache     texte qui identifie la requête, par exemple « tim:CDG:BKK »
    appel_direct  fonction sans argument qui interroge la source ; elle renvoie
                  les données utiles ou lève ErreurSource

    Trois résultats possibles :
    - (donnees, None)        la source vient de répondre ;
    - (donnees, "2026-11-12") les données viennent du cache, enregistré à cette date ;
    - (None, None)           ni source ni cache : à l'adaptateur d'utiliser le barème.
    """
    entree = _lire_cache().get(cle_cache)
    if entree:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(entree["date"])
        if age < timedelta(days=FRAICHEUR_CACHE_JOURS):
            return entree["donnees"], entree["date"][:10]
    try:
        donnees = appel_direct()
    except ErreurSource:
        if entree:  # cache ancien, mais mieux qu'une estimation
            return entree["donnees"], entree["date"][:10]
        return None, None
    _ecrire_cache(cle_cache, donnees)
    return donnees, None


def nommer_source(nom, date_cache):
    """Texte de provenance : « Transitous » ou « Transitous (cache du 2026-11-12) »."""
    return f"{nom} (cache du {date_cache})" if date_cache else nom


def cle_coordonnees(point):
    """Écrit un point [longitude, latitude] de façon stable pour une clé de cache."""
    return f"{point[0]:.4f},{point[1]:.4f}"


# --- Barème ---


def distance_vol_oiseau_km(depart, arrivee):
    """Distance en ligne droite entre deux points [longitude, latitude] (formule de haversine)."""
    lon1, lat1, lon2, lat2 = map(math.radians, [depart[0], depart[1], arrivee[0], arrivee[1]])
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))  # 6371 km : rayon moyen de la Terre


def charger_bareme(chemin=FICHIER_BAREME):
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier)["modes"]


def estimer_distance_km(mode, depart, arrivee):
    """Distance estimée : vol d'oiseau × coefficient de détour du barème."""
    return distance_vol_oiseau_km(depart, arrivee) * charger_bareme()[mode]["coefficient_detour"]


def estimer_duree_min(mode, distance_km):
    """Durée estimée : distance ÷ vitesse moyenne du barème."""
    return distance_km / charger_bareme()[mode]["vitesse_km_h"] * 60


def estimer_duree_avion_min(distance_km):
    """Durée estimée d'un vol direct, temps d'aéroport compris.

    durée = temps d'aéroport + part fixe du vol (roulage, montée, descente)
            + distance ÷ vitesse de croisière
    Les hypothèses sont détaillées dans bareme.json (« duree_avion »).
    """
    avion = charger_bareme()["avion"]
    temps_de_vol = avion["temps_decollage_atterrissage_min"] + distance_km / avion["vitesse_km_h"] * 60
    return avion["temps_aeroport_min"] + temps_de_vol


def estimer_prix(mode, distance_km, chemin=FICHIER_BAREME_PRIX):
    """Fourchette de prix indicative : renvoie (prix_min, prix_max) en euros, arrondis à l'euro.

    prix = distance × prix au km du barème (bareme_prix.json, « à valider »).
    """
    with open(chemin, encoding="utf-8") as fichier:
        tranches = json.load(fichier)["modes"][mode]["tranches"]
    tranche = trouver_tranche(tranches, distance_km)
    return round(distance_km * tranche["prix_min_eur_km"]), round(distance_km * tranche["prix_max_eur_km"])


SOURCE_PRIX_BAREME = "Barème de prix au km (à valider)"


# --- Format commun ---


def construire_option(mode, distance_km, duree_min, source_distance, source_duree):
    """Fabrique une Option : le CO2 est calculé par le moteur (distance × facteur ADEME),
    le prix est une fourchette indicative tirée du barème de prix.
    """
    co2 = calculer_co2(mode, distance_km)
    prix_min, prix_max = estimer_prix(mode, distance_km)
    return Option(
        mode=mode,
        distance_km=distance_km,
        duree_min=duree_min,
        prix_min=prix_min,
        prix_max=prix_max,
        type_prix="indicatif",
        co2_kg=co2.co2_kg,
        intensite_g_pkm=co2.intensite_g_pkm,
        niveau=co2.niveau,
        incertitude=co2.incertitude_kg,
        source={
            "distance": source_distance,
            "duree": source_duree,
            "prix": SOURCE_PRIX_BAREME,
            "co2": f"{co2.source} ({co2.statut})",
        },
    )
