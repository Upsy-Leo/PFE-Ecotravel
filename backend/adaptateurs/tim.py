"""Adaptateur Travel Impact Model (Google) : émissions d'un vol.

    from backend.adaptateurs import tim

    option = tim.option_vol("CDG", "BKK", 9450, cle)

On utilise la méthode « computeTypicalFlightEmissions » : elle ne demande que
les deux aéroports (codes IATA) et renvoie des grammes de CO2e par passager.

La distance est fournie par l'appelant : Travel Impact Model ne la donne pas.
Le comparateur la calcule à vol d'oiseau entre les deux aéroports (aeroports.py).
"""

import urllib.parse

from backend.adaptateurs import commun
from backend.modeles import Option
from backend.moteur_co2 import calculer_co2, charger_niveaux, trouver_niveau

URL = "https://travelimpactmodel.googleapis.com/v1/flights:computeTypicalFlightEmissions"


def connait_le_trajet(option):
    """Vrai si le CO2 de cette option vient bien de Travel Impact Model, pas du repli ADEME."""
    return not option.source["co2"].startswith("Repli")


def option_vol(origine, destination, distance_km, cle):
    """Renvoie l'Option « avion » entre deux aéroports (codes IATA, par exemple « CDG »).

    Si Travel Impact Model ne répond pas ou ne connaît pas ce trajet, le CO2 est
    calculé avec le facteur ADEME du moteur. Attention : les deux méthodes donnent
    des résultats très différents (voir « Point de méthode » dans CLAUDE.md).

    La durée (vol direct + temps d'aéroport) et le prix (fourchette indicative)
    sont des estimations par barème, quelle que soit la réponse de la source.
    """
    if distance_km <= 0:
        raise ValueError(f"La distance du vol doit être positive (reçu : {distance_km} km).")
    origine, destination = origine.upper(), destination.upper()

    def appel_direct():
        reponse = commun.appeler_json(
            f"{URL}?key={urllib.parse.quote(cle)}",
            corps={"markets": [{"origin": origine, "destination": destination}]},
        )
        try:
            vol = reponse["typicalFlightEmissions"][0]
        except (KeyError, IndexError, TypeError) as erreur:
            raise commun.ErreurSource(f"Réponse inattendue : {reponse}") from erreur
        # Si la source ne connaît pas ce trajet (pas de vol direct entre ces aéroports),
        # elle répond sans « emissionsGramsPerPax ». Ce n'est pas une panne : on le
        # met en cache aussi, pour ne pas reposer la question à chaque fois.
        return {"grammes": vol.get("emissionsGramsPerPax", {}).get("economy")}

    donnees, date_cache = commun.avec_repli(f"tim:{origine}:{destination}", appel_direct)

    if donnees is None or donnees["grammes"] is None:
        # Source en panne sans cache, ou trajet inconnu de la source : repli sur le facteur ADEME.
        raison = "indisponible" if donnees is None else "ne connaît pas ce trajet"
        co2 = calculer_co2("avion", distance_km)
        co2_kg, intensite, niveau, incertitude = co2.co2_kg, co2.intensite_g_pkm, co2.niveau, co2.incertitude_kg
        source_co2 = f"Repli, Travel Impact Model {raison}. {co2.source} ({co2.statut})"
    else:
        co2_kg = donnees["grammes"] / 1000
        intensite = donnees["grammes"] / distance_km
        niveau = trouver_niveau(intensite, charger_niveaux())
        incertitude = None  # Travel Impact Model ne fournit pas de fourchette
        source_co2 = commun.nommer_source("Travel Impact Model (Google), vol typique, classe économique", date_cache)

    # Durée et prix ne viennent d'aucune source : ce sont des estimations par barème.
    prix_min, prix_max = commun.estimer_prix("avion", distance_km)
    return Option(
        mode="avion",
        distance_km=distance_km,
        duree_min=commun.estimer_duree_avion_min(distance_km),
        prix_min=prix_min,
        prix_max=prix_max,
        type_prix="indicatif",
        co2_kg=co2_kg,
        intensite_g_pkm=intensite,
        niveau=niveau,
        incertitude=incertitude,
        source={
            "distance": f"Vol d'oiseau entre les aéroports {origine} et {destination}",
            "duree": "Barème (à valider) : vol direct + temps d'aéroport",
            "prix": commun.SOURCE_PRIX_BAREME,
            "co2": source_co2,
        },
    )
