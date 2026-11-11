"""Moteur de calcul du CO2 d'un trajet.

Une seule formule pour tous les modes :

    CO2 (kg) = distance (km) × facteur d'émission (g CO2e par passager·km) ÷ 1000

Le moteur ne contient aucun chiffre : les facteurs et les seuils des niveaux
A à E sont lus dans deux fichiers du dossier « donnees/ ».

    donnees/facteurs_emission.json   facteurs par mode (provisoires, « à valider »)
    donnees/niveaux_co2.json         seuils des niveaux A à E (provisoires)

Exemple :

    from backend.moteur_co2 import calculer_co2

    resultat = calculer_co2("train", 750)
    print(resultat.co2_kg, resultat.niveau, resultat.incertitude_kg)
"""

import json
from dataclasses import dataclass
from pathlib import Path

DOSSIER_DONNEES = Path(__file__).parent / "donnees"
FICHIER_FACTEURS = DOSSIER_DONNEES / "facteurs_emission.json"
FICHIER_NIVEAUX = DOSSIER_DONNEES / "niveaux_co2.json"


@dataclass(frozen=True)
class ResultatCO2:
    """Résultat du calcul pour un mode et une distance.

    Les noms reprennent ceux du format commun d'une option (voir CLAUDE.md).
    """

    mode: str
    distance_km: float
    co2_kg: float  # émissions totales par passager
    intensite_g_pkm: float  # g CO2e par passager·km
    niveau: str  # lettre A à E
    incertitude_kg: tuple[float, float]  # (CO2 minimum, CO2 maximum)
    source: str  # d'où vient le facteur utilisé
    statut: str  # « à valider » tant que l'équipe n'a pas validé le facteur


def charger_facteurs(chemin=FICHIER_FACTEURS):
    """Lit les facteurs d'émission et renvoie le dictionnaire {mode: informations}."""
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier)["modes"]


def charger_niveaux(chemin=FICHIER_NIVEAUX):
    """Lit les seuils et renvoie la liste des niveaux, du moins au plus émetteur."""
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier)["niveaux"]


def trouver_niveau(intensite_g_pkm, niveaux):
    """Renvoie la lettre (A à E) qui correspond à une intensité en g CO2e/passager·km.

    On parcourt les niveaux dans l'ordre et on s'arrête au premier dont le seuil
    est strictement au-dessus de l'intensité. Le dernier niveau n'a pas de seuil
    (None) : il prend tout ce qui reste.
    """
    for niveau in niveaux:
        seuil = niveau["en_dessous_de"]
        if seuil is None or intensite_g_pkm < seuil:
            return niveau["lettre"]
    raise ValueError("La liste des niveaux doit se terminer par un niveau sans seuil (null).")


def trouver_tranche(tranches, distance_km):
    """Renvoie la tranche de distance qui s'applique.

    La plupart des modes n'ont qu'une tranche. L'avion en a plusieurs, car son
    facteur dépend de la longueur du vol.
    """
    for tranche in tranches:
        limite = tranche["jusqu_a_km"]
        if limite is None or distance_km <= limite:
            return tranche
    raise ValueError("La liste des tranches doit se terminer par une tranche sans limite (null).")


def calculer_co2(mode, distance_km, facteurs=None, niveaux=None):
    """Calcule le CO2 d'un trajet pour un mode et une distance.

    mode         « avion », « train », « bus » ou « voiture »
    distance_km  distance du segment, en kilomètres
    facteurs     facultatif : facteurs à utiliser à la place du fichier (utile pour les tests)
    niveaux      facultatif : niveaux à utiliser à la place du fichier (utile pour les tests)
    """
    if facteurs is None:
        facteurs = charger_facteurs()
    if niveaux is None:
        niveaux = charger_niveaux()

    if mode not in facteurs:
        modes_connus = ", ".join(sorted(facteurs))
        raise ValueError(f"Mode inconnu : « {mode} ». Modes disponibles : {modes_connus}.")
    if distance_km < 0:
        raise ValueError(f"La distance ne peut pas être négative (reçu : {distance_km} km).")

    infos = facteurs[mode]
    tranche = trouver_tranche(infos["tranches"], distance_km)
    facteur = tranche["facteur_g_pkm"]

    # On divise par 1000 pour passer des grammes aux kilogrammes.
    co2_kg = distance_km * facteur / 1000
    co2_min_kg = distance_km * infos["min_g_pkm"] / 1000
    co2_max_kg = distance_km * infos["max_g_pkm"] / 1000

    return ResultatCO2(
        mode=mode,
        distance_km=distance_km,
        co2_kg=co2_kg,
        # Avec un facteur fixe, l'intensité est le facteur lui-même.
        intensite_g_pkm=facteur,
        niveau=trouver_niveau(facteur, niveaux),
        incertitude_kg=(co2_min_kg, co2_max_kg),
        source=f"{infos['source']} : {tranche['libelle']}",
        statut=infos["statut"],
    )
