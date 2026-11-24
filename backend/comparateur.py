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


def comparer(depart, arrivee, date, cles, point_depart=None, point_arrivee=None):
    """Renvoie les options de transport entre deux villes pour un jour donné.

    depart, arrivee  noms de villes, par exemple « Paris » ou « Brest, Finistère, France »
    date             jour du voyage, au format « 2026-12-01 »
    point_depart, point_arrivee
                     position « longitude,latitude » de la ville, quand l'utilisateur
                     l'a choisie dans une liste proposée par le site. Elle évite toute
                     ambiguïté, et un appel au géocodage.

    Sans position, la ville est cherchée par son nom. Si ce nom désigne plusieurs
    villes, la fonction ne compare rien : elle renvoie
    {"a_preciser": {"depart": [lieux…]}} pour que le site pose la question.
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

    lieu_depart, homonymes_depart = _situer(depart, cle_ors, point_depart)
    lieu_arrivee, homonymes_arrivee = _situer(arrivee, cle_ors, point_arrivee)
    a_preciser = {}
    if lieu_depart is None:
        a_preciser["depart"] = homonymes_depart
    if lieu_arrivee is None:
        a_preciser["arrivee"] = homonymes_arrivee
    if a_preciser:
        return {"a_preciser": a_preciser, "date": date}

    a = [lieu_depart["lon"], lieu_depart["lat"]]
    b = [lieu_arrivee["lon"], lieu_arrivee["lat"]]
    if commun.distance_vol_oiseau_km(a, b) < 1:
        raise ErreurDemande(400, "Le départ et l'arrivée sont au même endroit.")

    contact = cles.get("TRANSITOUS_CONTACT")
    train = transitous.option_train(a, b, contact, date)
    train = sncf.appliquer_tarif(train, lieu_depart["ville"], lieu_arrivee["ville"])
    avion, raison_avion = _option_avion(a, b, cles.get("TIM_API_Key", ""))

    trouvees = {
        "avion": (avion, raison_avion),
        "train": (train, "Aucun trajet en train trouvé par Transitous ce jour-là."),
        "bus": (transitous.option_bus(a, b, contact, date), "Aucun trajet en car trouvé par Transitous ce jour-là."),
        "voiture": (
            ors.option_voiture(a, b, cle_ors),
            "Pas d'itinéraire routier proposé par OpenRouteService (mer à traverser ou trajet de plus de 6 000 km).",
        ),
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


def _lire_point(texte):
    """Lit « longitude,latitude ». Renvoie [lon, lat], ou None si le texte n'est pas une position valable."""
    try:
        lon, lat = (float(morceau) for morceau in (texte or "").split(","))
    except ValueError:
        return None
    return [lon, lat] if -180 <= lon <= 180 and -90 <= lat <= 90 else None


def _situer(ville, cle_ors, point):
    """Renvoie (lieu, None) si la ville est connue sans ambiguïté, sinon (None, homonymes)."""
    position = _lire_point(point)
    if position:
        # L'utilisateur a choisi cette ville dans une liste : son nom complet est dans « ville ».
        return {
            "nom": ville,
            "ville": ville.split(",")[0].strip(),
            "lon": position[0],
            "lat": position[1],
            "source": "OpenRouteService (ville choisie dans la liste proposée)",
        }, None

    lieux = ors.chercher_lieux(ville, cle_ors)
    if lieux is None:
        raise ErreurDemande(503, "Le service qui situe les villes ne répond pas. Réessayez dans un moment.")
    if not lieux:
        raise ErreurDemande(404, f"Ville introuvable : « {ville} ». Vérifiez l'orthographe.")
    if len(lieux) == 1:
        return lieux[0], None
    # Plusieurs villes de ce nom et aucun choix : on demande au lieu de garder la première.
    return None, lieux


def _option_avion(a, b, cle_tim):
    """Renvoie (option, None), ou (None, raison) s'il n'y a pas de vol à proposer.

    On retient l'aéroport le plus proche de chaque ville (Orly pour Paris). Ce choix
    ne sert qu'à mesurer la distance du vol : aucune de nos sources ne dit entre quels
    aéroports un vol direct existe, et l'option le signale (voir tim.REMARQUE_VOL_DIRECT).
    """
    paires = [
        (origine, destination)
        for origine in aeroports.aeroports_proches(a)
        for destination in aeroports.aeroports_proches(b)
        if origine["iata"] != destination["iata"]
    ]
    if not paires:
        return None, "Pas d'aéroport à moins de 100 km d'une des deux villes, ou même aéroport pour les deux."
    origine, destination = min(
        paires, key=lambda paire: paire[0]["eloignement_km"] + paire[1]["eloignement_km"]
    )
    distance_km = commun.distance_vol_oiseau_km(origine["point"], destination["point"])
    return tim.option_vol(origine["iata"], destination["iata"], distance_km, cle_tim), None
