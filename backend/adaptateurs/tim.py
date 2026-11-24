"""Option « avion », et adaptateur Travel Impact Model (Google).

    from backend.adaptateurs import tim

    option = tim.option_vol("CDG", "BKK", 9450, cle)

Deux estimations du CO2 d'un vol existent, et elles ne donnent pas le même résultat :

- le calcul ADEME du moteur (distance × facteur), comme pour les autres modes ;
- la valeur du Travel Impact Model, méthode « computeTypicalFlightEmissions », qui
  ne demande que les deux aéroports (codes IATA) et renvoie des grammes de CO2e
  par passager.

Laquelle sert à la comparaison est un choix de l'équipe, écrit dans
donnees/methode.json (« co2_avion »). L'autre est jointe à l'option à titre
indicatif (champ « co2_indicatif ») : elle ne sert ni au niveau A-E ni au classement.

Ce que le Travel Impact Model ne dit pas (documentation lue le 2026-11-24) : sa valeur
« typique » couvre les vols directs ET avec escale d'un trajet, et les aéroports voisins
à moins de 150 km. Il répond donc pour Lyon-Bangkok, qui n'a pas de vol direct, et
donne la même valeur pour Orly et Roissy. Une réponse ne prouve pas qu'un vol direct existe.

La distance est fournie par l'appelant : le comparateur la calcule à vol d'oiseau
entre les deux aéroports (aeroports.py).
"""

import urllib.parse

from backend.adaptateurs import commun
from backend.modeles import Option
from backend.moteur_co2 import calculer_co2, charger_methode, charger_niveaux, trouver_niveau

URL = "https://travelimpactmodel.googleapis.com/v1/flights:computeTypicalFlightEmissions"

REMARQUE_VOL_DIRECT = (
    "Vol direct non vérifié : aucune de nos sources ne dit si un vol direct relie ces deux aéroports. "
    "La durée et le prix sont ceux d'un vol direct ; avec une escale, comptez davantage."
)


def emissions_typiques(origine, destination, cle):
    """Interroge le Travel Impact Model. Renvoie (grammes, source).

    grammes  émissions par passager en classe économique, ou None si la source ne
             répond pas ou ne connaît pas ce trajet
    source   texte de provenance (avec la date du cache, le cas échéant), ou la
             raison de l'absence de valeur
    """

    def appel_direct():
        reponse = commun.appeler_json(
            f"{URL}?key={urllib.parse.quote(cle)}",
            corps={"markets": [{"origin": origine, "destination": destination}]},
        )
        try:
            vol = reponse["typicalFlightEmissions"][0]
        except (KeyError, IndexError, TypeError) as erreur:
            raise commun.ErreurSource(f"Réponse inattendue : {reponse}") from erreur
        # Si la source ne connaît pas ce trajet, elle répond sans « emissionsGramsPerPax ».
        # Ce n'est pas une panne : on le met en cache aussi, mais pour peu de temps
        # (voir commun.avec_repli).
        return {"grammes": vol.get("emissionsGramsPerPax", {}).get("economy")}

    donnees, date_cache = commun.avec_repli(
        f"tim:{origine}:{destination}", appel_direct, est_absence=lambda donnees: donnees["grammes"] is None
    )
    if donnees is None:
        return None, "Travel Impact Model indisponible"
    if donnees["grammes"] is None:
        return None, "Travel Impact Model ne connaît pas ce trajet"
    return donnees["grammes"], commun.nommer_source(
        "Travel Impact Model (Google), vol typique, classe économique, sans les traînées de condensation", date_cache
    )


def option_vol(origine, destination, distance_km, cle, methode=None):
    """Renvoie l'Option « avion » entre deux aéroports (codes IATA, par exemple « CDG »).

    methode  « ademe » ou « tim » : l'estimation qui sert à la comparaison. Par
             défaut, celle de methode.json. Si « tim » est demandé mais que la source
             ne donne rien, le calcul ADEME prend le relais, et la source le dit.

    La durée (trajets vers et depuis l'aéroport, temps d'aéroport, vol direct) et le
    prix (fourchette indicative) sont des estimations par barème.
    """
    if distance_km <= 0:
        raise ValueError(f"La distance du vol doit être positive (reçu : {distance_km} km).")
    if methode is None:
        methode = charger_methode()["co2_avion"]["methode"]
    if methode not in ("ademe", "tim"):
        raise ValueError(f"Méthode inconnue pour le CO2 de l'avion : « {methode} » (attendu : ademe ou tim).")
    origine, destination = origine.upper(), destination.upper()

    # Les deux estimations, chacune avec sa source.
    ademe = calculer_co2("avion", distance_km)
    source_ademe = f"{ademe.source} ({ademe.statut})"
    grammes, source_tim = emissions_typiques(origine, destination, cle)

    selon_tim = None
    if grammes is not None:
        selon_tim = {"co2_kg": grammes / 1000, "intensite_g_pkm": grammes / distance_km, "source": source_tim}
    selon_ademe = {"co2_kg": ademe.co2_kg, "intensite_g_pkm": ademe.intensite_g_pkm, "source": source_ademe}

    if methode == "tim" and selon_tim:
        retenue, indicative = selon_tim, selon_ademe
        incertitude = None  # le Travel Impact Model ne fournit pas de fourchette
        source_co2 = source_tim
    else:
        retenue, indicative = selon_ademe, selon_tim
        incertitude = ademe.incertitude_kg
        source_co2 = source_ademe if methode == "ademe" else f"Repli, {source_tim}. {source_ademe}"

    prix_min, prix_max = commun.estimer_prix("avion", distance_km)
    return Option(
        mode="avion",
        distance_km=distance_km,
        duree_min=commun.estimer_duree_avion_min(distance_km),
        prix_min=prix_min,
        prix_max=prix_max,
        type_prix="indicatif",
        co2_kg=retenue["co2_kg"],
        intensite_g_pkm=retenue["intensite_g_pkm"],
        # Le niveau A-E vient toujours de l'estimation retenue, jamais de l'indicative.
        niveau=trouver_niveau(retenue["intensite_g_pkm"], charger_niveaux()),
        incertitude=incertitude,
        source={
            "distance": f"Vol d'oiseau entre les aéroports {origine} et {destination}, les plus proches de chaque ville",
            "duree": "Barème (à valider) : trajets vers et depuis l'aéroport, temps d'aéroport, vol direct",
            "prix": commun.SOURCE_PRIX_BAREME,
            "co2": source_co2,
        },
        co2_indicatif=indicative,
        remarques=[REMARQUE_VOL_DIRECT],
    )
