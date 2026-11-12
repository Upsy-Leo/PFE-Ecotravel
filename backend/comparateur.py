"""Comparaison d'un trajet : assemble les quatre options (avion, train, bus, voiture).

    from backend.comparateur import comparer

    resultat = comparer("Paris", "Lyon", "2026-12-01", cles)

« cles » est le dictionnaire lu dans le fichier .env (voir serveur.py) :
ORS_API_Key (obligatoire), TIM_API_Key et TRANSITOUS_CONTACT (sinon repli sur le barème).

Ce fichier ne fait aucun calcul : il appelle les adaptateurs dans l'ordre et
range leurs réponses. Le résultat est un dictionnaire prêt à être envoyé en JSON.
"""

import dataclasses
from datetime import date as Date

from backend.adaptateurs import aeroports, commun, ors, sncf, tim, transitous

AVERTISSEMENTS = [
    "La date ne sert qu'à la durée en train et en bus. Prix, CO2 et durées en voiture et en avion n'en dépendent pas.",
    "Les prix sont indicatifs : ce sont des fourchettes, pas des tarifs à la date demandée.",
    "Facteurs d'émission et barèmes sont provisoires (« à valider »).",
]


class ErreurDemande(Exception):
    """La demande ne peut pas être traitée. « code » est le code HTTP à renvoyer."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def comparer(depart, arrivee, date, cles):
    """Renvoie les options de transport entre deux villes pour un jour donné.

    depart, arrivee  noms de villes, par exemple « Paris »
    date             jour du voyage, au format « 2026-12-01 »
    """
    depart, arrivee, date = (depart or "").strip(), (arrivee or "").strip(), (date or "").strip()
    if not depart or not arrivee or not date:
        raise ErreurDemande(400, "Il faut les trois paramètres : depart, arrivee et date.")
    try:
        jour = Date.fromisoformat(date)
    except ValueError:
        raise ErreurDemande(400, "La date doit être au format AAAA-MM-JJ, par exemple 2026-12-01.") from None
    if jour < Date.today():
        raise ErreurDemande(400, "La date du voyage est déjà passée.")

    cle_ors = cles.get("ORS_API_Key")
    if not cle_ors:
        raise ErreurDemande(503, "La clé ORS_API_Key manque dans le fichier .env : impossible de situer les villes.")

    lieu_depart = _situer(depart, cle_ors)
    lieu_arrivee = _situer(arrivee, cle_ors)
    a = [lieu_depart["lon"], lieu_depart["lat"]]
    b = [lieu_arrivee["lon"], lieu_arrivee["lat"]]
    if commun.distance_vol_oiseau_km(a, b) < 1:
        raise ErreurDemande(400, "Le départ et l'arrivée sont au même endroit.")

    contact = cles.get("TRANSITOUS_CONTACT")
    train = transitous.option_train(a, b, contact, date)
    # Le nom renvoyé par le géocodage ressemble à « Lyon, France » : on garde la ville.
    train = sncf.appliquer_tarif(train, lieu_depart["nom"].split(",")[0], lieu_arrivee["nom"].split(",")[0])
    avion, raison_avion = _option_avion(a, b, cles.get("TIM_API_Key", ""))

    trouvees = {
        "avion": (avion, raison_avion),
        "train": (train, "Aucun trajet en train trouvé par Transitous ce jour-là."),
        "bus": (transitous.option_bus(a, b, contact, date), "Aucun trajet en car trouvé par Transitous ce jour-là."),
        "voiture": (ors.option_voiture(a, b, cle_ors), None),
    }
    return {
        "depart": lieu_depart,
        "arrivee": lieu_arrivee,
        "date": date,
        "options": [dataclasses.asdict(option) for option, _ in trouvees.values() if option is not None],
        # Modes sans option, avec la raison : le site doit le dire plutôt que de les cacher.
        "sans_option": {mode: raison for mode, (option, raison) in trouvees.items() if option is None},
        "avertissements": AVERTISSEMENTS,
    }


def _situer(ville, cle_ors):
    lieu = ors.geocoder(ville, cle_ors)
    if lieu is None:
        raise ErreurDemande(404, f"Ville introuvable, ou service de géocodage indisponible : « {ville} ».")
    return lieu


def _option_avion(a, b, cle_tim):
    """Renvoie (option, None), ou (None, raison) s'il n'y a pas de vol à proposer.

    Chaque ville peut avoir deux aéroports (Paris : Orly et Roissy). On essaie les
    paires d'aéroports, des plus proches des villes aux plus éloignées, et on garde
    la première que Travel Impact Model connaît. Si aucune n'est connue, on garde la
    paire la plus proche avec le facteur ADEME.

    Attention : « connue » ne prouve pas qu'un vol direct existe entre ces deux
    aéroports précis. Constaté le 2026-11-12 : Orly–Don Mueang reçoit exactement
    la même valeur que Roissy–Suvarnabhumi (la source semble raisonner par ville).
    """
    paires = [
        (origine, destination)
        for origine in aeroports.aeroports_proches(a)
        for destination in aeroports.aeroports_proches(b)
        if origine["iata"] != destination["iata"]
    ]
    if not paires:
        return None, "Pas d'aéroport à moins de 100 km d'une des deux villes, ou même aéroport pour les deux."
    paires.sort(key=lambda paire: paire[0]["eloignement_km"] + paire[1]["eloignement_km"])

    premiere = None
    for origine, destination in paires:
        distance_km = commun.distance_vol_oiseau_km(origine["point"], destination["point"])
        option = tim.option_vol(origine["iata"], destination["iata"], distance_km, cle_tim)
        if tim.connait_le_trajet(option):
            return option, None
        premiere = premiere or option
    return premiere, None
