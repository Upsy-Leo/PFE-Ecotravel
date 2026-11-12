"""Adaptateur OpenRouteService : géocodage, distance et durée en voiture.

    from backend.adaptateurs import ors

    paris = ors.geocoder("Paris", cle)          # {"lon": ..., "lat": ..., "nom": ...}
    lyon = ors.geocoder("Lyon", cle)
    option = ors.option_voiture([paris["lon"], paris["lat"]], [lyon["lon"], lyon["lat"]], cle)

Rappels : OpenRouteService attend les points dans l'ordre [longitude, latitude].
Plan gratuit : 2 000 itinéraires et 1 000 géocodages par jour, d'où le cache.
"""

import urllib.parse

from backend.adaptateurs import commun

URL_GEOCODAGE = "https://api.openrouteservice.org/geocode/search"
URL_ITINERAIRE = "https://api.openrouteservice.org/v2/directions/driving-car"
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


def option_voiture(depart, arrivee, cle):
    """Renvoie l'Option « voiture » entre deux points [longitude, latitude]."""

    def appel_direct():
        reponse = commun.appeler_json(
            URL_ITINERAIRE, corps={"coordinates": [depart, arrivee]}, entetes={"Authorization": cle}
        )
        try:
            resume = reponse["routes"][0]["summary"]
            # La source répond en mètres et en secondes.
            return {"distance_km": resume["distance"] / 1000, "duree_min": resume["duration"] / 60}
        except (KeyError, IndexError, TypeError) as erreur:
            raise commun.ErreurSource(f"Réponse d'itinéraire inattendue : {reponse}") from erreur

    cle_cache = f"ors:voiture:{commun.cle_coordonnees(depart)}:{commun.cle_coordonnees(arrivee)}"
    donnees, date_cache = commun.avec_repli(cle_cache, appel_direct)

    if donnees is None:
        # Ni source ni cache : on estime avec le barème, et on le dit.
        distance_km = commun.estimer_distance_km("voiture", depart, arrivee)
        duree_min = commun.estimer_duree_min("voiture", distance_km)
        return commun.construire_option("voiture", distance_km, duree_min, BAREME, BAREME)

    source = commun.nommer_source("OpenRouteService", date_cache)
    return commun.construire_option("voiture", donnees["distance_km"], donnees["duree_min"], source, source)
