"""Adaptateur OpenRouteService : géocodage, distance et durée en voiture.

    from backend.adaptateurs import ors

    paris = ors.geocoder("Paris", cle)          # {"lon": ..., "lat": ..., "nom": ...}
    lyon = ors.geocoder("Lyon", cle)
    option = ors.option_voiture([paris["lon"], paris["lat"]], [lyon["lon"], lyon["lat"]], cle)

Rappels : OpenRouteService attend les points dans l'ordre [longitude, latitude].
Plan gratuit : 2 000 itinéraires et 1 000 géocodages par jour, d'où le cache.
"""

import json
import urllib.parse

from backend.adaptateurs import commun

URL_GEOCODAGE = "https://api.openrouteservice.org/geocode/search"
URL_ITINERAIRE = "https://api.openrouteservice.org/v2/directions/driving-car"
# Codes d'erreur relevés le 2026-11-13 : 2004 = trajet de plus de 6 000 km (Paris-Bangkok),
# 2009 = aucune route entre les deux points (Paris-New York), 2010 = point loin de toute route.
CODES_SANS_ROUTE = (2004, 2009, 2010)
BAREME = "Barème (à valider), OpenRouteService indisponible"


def geocoder(texte, cle):
    """Cherche une ville et renvoie {"lon", "lat", "nom", "source"}.

    Renvoie None si la ville est introuvable ou si la source ne répond pas :
    il n'existe pas de barème pour deviner des coordonnées.
    """

    def appel_direct():
        # layers=locality : on cherche une ville, pas une rue ni un arrondissement.
        parametres = urllib.parse.urlencode({"text": texte, "size": 1, "layers": "locality"})
        reponse = commun.appeler_json(f"{URL_GEOCODAGE}?{parametres}", entetes={"Authorization": cle})
        try:
            resultats = reponse["features"]
            if not resultats:
                return {"trouve": False}
            lon, lat = resultats[0]["geometry"]["coordinates"]
            return {"trouve": True, "lon": lon, "lat": lat, "nom": resultats[0]["properties"]["label"]}
        except (KeyError, TypeError, ValueError) as erreur:
            raise commun.ErreurSource(f"Réponse de géocodage inattendue : {reponse}") from erreur

    donnees, date_cache = commun.avec_repli(f"ors:geocodage:{texte.strip().lower()}", appel_direct)
    if not donnees or not donnees["trouve"]:
        return None
    return {
        "lon": donnees["lon"],
        "lat": donnees["lat"],
        "nom": donnees["nom"],
        "source": commun.nommer_source("OpenRouteService", date_cache),
    }


def _est_un_refus_sans_route(erreur):
    """Vrai si OpenRouteService a répondu « pas d'itinéraire » (ce n'est pas une panne)."""
    try:
        return json.loads(erreur.corps)["error"]["code"] in CODES_SANS_ROUTE
    except (ValueError, KeyError, TypeError):
        return False


def option_voiture(depart, arrivee, cle):
    """Renvoie l'Option « voiture » entre deux points [longitude, latitude].

    Renvoie None si OpenRouteService répond qu'il n'y a pas d'itinéraire routier
    (océan à traverser, ou trajet de plus de 6 000 km). En cas de panne, en
    revanche, la distance et la durée sont estimées avec le barème.
    """

    def appel_direct():
        try:
            reponse = commun.appeler_json(
                URL_ITINERAIRE, corps={"coordinates": [depart, arrivee]}, entetes={"Authorization": cle}
            )
        except commun.ErreurSource as erreur:
            if _est_un_refus_sans_route(erreur):
                return {"route": False}  # mis en cache, comme une réponse normale
            raise
        try:
            resume = reponse["routes"][0]["summary"]
            # La source répond en mètres et en secondes.
            return {"route": True, "distance_km": resume["distance"] / 1000, "duree_min": resume["duration"] / 60}
        except (KeyError, IndexError, TypeError) as erreur:
            raise commun.ErreurSource(f"Réponse d'itinéraire inattendue : {reponse}") from erreur

    cle_cache = f"ors:voiture:{commun.cle_coordonnees(depart)}:{commun.cle_coordonnees(arrivee)}"
    donnees, date_cache = commun.avec_repli(cle_cache, appel_direct)

    # « get » : les réponses mises en cache avant l'ajout de « route » n'ont pas ce champ.
    if donnees is not None and not donnees.get("route", True):
        return None

    if donnees is None:
        # Ni source ni cache : on estime avec le barème, et on le dit.
        distance_km = commun.estimer_distance_km("voiture", depart, arrivee)
        duree_min = commun.estimer_duree_min("voiture", distance_km)
        return commun.construire_option("voiture", distance_km, duree_min, BAREME, BAREME)

    source = commun.nommer_source("OpenRouteService", date_cache)
    return commun.construire_option("voiture", donnees["distance_km"], donnees["duree_min"], source, source)
