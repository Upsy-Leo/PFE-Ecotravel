"""Réduit le fichier airports.csv d'OurAirports aux aéroports utiles au comparateur.

Le fichier complet (13 Mo, 80 000 lignes) contient aussi les héliports et les
aérodromes privés. On ne garde que les grands et moyens aéroports qui ont des
vols réguliers et un code IATA, et seulement les colonnes dont on se sert.

Pour mettre à jour backend/donnees/aeroports.csv :
1. télécharger https://davidmegginson.github.io/ourairports-data/airports.csv
2. lancer, depuis la racine du projet :
       python scripts/preparer_aeroports.py chemin/vers/airports.csv
"""

import csv
import sys
from pathlib import Path

SORTIE = Path(__file__).parent.parent / "backend" / "donnees" / "aeroports.csv"
COLONNES = ["iata_code", "name", "municipality", "iso_country", "type", "latitude_deg", "longitude_deg"]


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    with open(sys.argv[1], encoding="utf-8-sig", newline="") as entree:
        gardes = [
            {colonne: ligne[colonne] for colonne in COLONNES}
            for ligne in csv.DictReader(entree)
            if ligne["type"] in ("large_airport", "medium_airport")
            and ligne["scheduled_service"] == "yes"
            and ligne["iata_code"]
        ]
    gardes.sort(key=lambda ligne: ligne["iata_code"])
    with open(SORTIE, "w", encoding="utf-8", newline="") as sortie:
        ecrivain = csv.DictWriter(sortie, fieldnames=COLONNES)
        ecrivain.writeheader()
        ecrivain.writerows(gardes)
    print(f"{len(gardes)} aéroports écrits dans {SORTIE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
