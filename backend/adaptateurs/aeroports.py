"""Aéroports : trouver ceux qui desservent une ville.

    from backend.adaptateurs import aeroports

    aeroports.aeroports_proches([2.3522, 48.8566])   # Paris -> ORY puis CDG

Ce n'est pas une API : le fichier est embarqué dans backend/donnees/aeroports.csv.
Source : OurAirports, airports.csv (domaine public), téléchargé le 2026-11-12 et
réduit par scripts/preparer_aeroports.py aux grands et moyens aéroports ayant des
vols réguliers et un code IATA.

Hypothèses (à valider en équipe) :
- un aéroport dessert une ville s'il est à moins de 100 km à vol d'oiseau ;
- on préfère les grands aéroports ; les moyens ne servent que s'il n'y a aucun grand ;
- on garde les 2 plus proches. Le fichier ne dit pas lequel a le plus de vols.
"""

import csv
import functools

from backend.adaptateurs import commun

FICHIER_AEROPORTS = commun.DOSSIER_BACKEND / "donnees" / "aeroports.csv"
SOURCE = "OurAirports (domaine public)"

RAYON_KM = 100
NOMBRE_MAX = 2


# functools.cache : le fichier n'est lu qu'une fois, puis gardé en mémoire.
@functools.cache
def charger_aeroports(chemin=FICHIER_AEROPORTS):
    with open(chemin, encoding="utf-8", newline="") as fichier:
        return [
            {
                "iata": ligne["iata_code"],
                "nom": ligne["name"],
                "grand": ligne["type"] == "large_airport",
                "point": [float(ligne["longitude_deg"]), float(ligne["latitude_deg"])],
            }
            for ligne in csv.DictReader(fichier)
        ]


def aeroports_proches(point, chemin=FICHIER_AEROPORTS):
    """Renvoie les aéroports qui desservent un point [longitude, latitude], du plus proche au plus loin.

    Chaque aéroport est un dictionnaire {"iata", "nom", "grand", "point", "eloignement_km"}.
    La liste est vide s'il n'y a aucun aéroport à moins de 100 km.
    """
    proches = []
    for aeroport in charger_aeroports(chemin):
        eloignement_km = commun.distance_vol_oiseau_km(point, aeroport["point"])
        if eloignement_km <= RAYON_KM:
            proches.append({**aeroport, "eloignement_km": eloignement_km})
    grands = [aeroport for aeroport in proches if aeroport["grand"]]
    retenus = grands or proches
    return sorted(retenus, key=lambda aeroport: aeroport["eloignement_km"])[:NOMBRE_MAX]
