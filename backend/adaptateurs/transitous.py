"""Adaptateur Transitous (API MOTIS) : durée en train et en bus longue distance.

    from backend.adaptateurs import transitous

    option = transitous.option_train([2.3522, 48.8566], [4.8357, 45.7640], contact)
    option = transitous.option_bus([2.3522, 48.8566], [4.8357, 45.7640], contact)

Transitous est gratuit pour un usage non commercial, à condition de s'identifier :
« contact » (une adresse de l'équipe) est envoyé dans l'en-tête User-Agent.
Sans contact, l'adaptateur n'interroge pas Transitous.

Durée retenue : le trajet le plus rapide, de porte à porte, parmi les départs
du lendemain matin et midi. C'est une durée typique, pas un horaire.

Transitous ne donne pas la distance des trajets : elle est estimée avec le
barème (vol d'oiseau × coefficient de détour).
"""

import urllib.parse
from datetime import datetime, timedelta, timezone

from backend.adaptateurs import commun

URL = "https://api.transitous.org/api/v6/plan"

# « demandes » : modes envoyés à Transitous (on autorise métro, tram et bus de ville
# pour rejoindre la gare). « principaux » : un itinéraire n'est retenu que s'il
# contient au moins une étape dans un de ces modes.
MODES = {
    "train": {
        "demandes": "RAIL,TRAM,BUS",
        "principaux": {"HIGHSPEED_RAIL", "LONG_DISTANCE", "NIGHT_RAIL", "REGIONAL_RAIL", "REGIONAL_FAST_RAIL"},
    },
    "bus": {
        "demandes": "COACH,BUS,TRAM,SUBWAY,SUBURBAN",
        "principaux": {"COACH"},
    },
}


def option_train(depart, arrivee, contact):
    """Option « train » entre deux points [longitude, latitude]. None s'il n'y a pas de train."""
    return _option("train", depart, arrivee, contact)


def option_bus(depart, arrivee, contact):
    """Option « bus » (car longue distance) entre deux points. None s'il n'y a pas de car."""
    return _option("bus", depart, arrivee, contact)


def _option(mode, depart, arrivee, contact):
    def appel_direct():
        if not contact:
            raise commun.ErreurSource("Contact manquant : Transitous demande de s'identifier.")
        demain = datetime.now(timezone.utc).date() + timedelta(days=1)
        parametres = urllib.parse.urlencode({
            # Attention : Transitous attend « latitude,longitude », l'inverse d'OpenRouteService.
            "fromPlace": f"{depart[1]},{depart[0]}",
            "toPlace": f"{arrivee[1]},{arrivee[0]}",
            "time": f"{demain.isoformat()}T05:00:00Z",
            "searchWindow": 12 * 3600,  # on regarde 12 heures de départs
            "transitModes": MODES[mode]["demandes"],
        })
        reponse = commun.appeler_json(
            f"{URL}?{parametres}", entetes={"User-Agent": f"comparateur-itineraires-pfe ({contact})"}
        )
        try:
            durees_s = [
                itineraire["duration"]
                for itineraire in reponse["itineraries"]
                if any(etape["mode"] in MODES[mode]["principaux"] for etape in itineraire["legs"])
            ]
        except (KeyError, TypeError) as erreur:
            raise commun.ErreurSource(f"Réponse inattendue : {str(reponse)[:500]}") from erreur
        # Aucun itinéraire : ce n'est pas une panne, c'est que ce mode ne dessert pas le trajet.
        return {"duree_min": min(durees_s) / 60 if durees_s else None}

    cle_cache = f"transitous:{mode}:{commun.cle_coordonnees(depart)}:{commun.cle_coordonnees(arrivee)}"
    donnees, date_cache = commun.avec_repli(cle_cache, appel_direct)

    distance_km = commun.estimer_distance_km(mode, depart, arrivee)
    source_distance = "Barème (à valider) : vol d'oiseau × coefficient de détour"

    if donnees is None:
        # Ni source ni cache : la durée aussi vient du barème, et on le dit.
        duree_min = commun.estimer_duree_min(mode, distance_km)
        source_duree = "Barème (à valider), Transitous indisponible"
        return commun.construire_option(mode, distance_km, duree_min, source_distance, source_duree)

    if donnees["duree_min"] is None:
        return None
    source_duree = commun.nommer_source("Transitous", date_cache)
    return commun.construire_option(mode, distance_km, donnees["duree_min"], source_distance, source_duree)
