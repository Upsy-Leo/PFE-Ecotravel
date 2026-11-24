"""Moteur de calcul du CO2 d'un trajet.

Une seule formule pour tous les modes :

    CO2 (kg) = distance (km) × facteur d'émission (g CO2e par passager·km) ÷ 1000

Le moteur ne contient aucun chiffre : les facteurs et les seuils des niveaux
A à E sont lus dans deux fichiers du dossier « donnees/ ».

    donnees/facteurs_emission.json   facteurs par mode (provisoires, « à valider »)
    donnees/niveaux_co2.json         seuils des niveaux A à E (provisoires)
    donnees/methode.json             choix de méthode de l'équipe (traînées de l'avion...)

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
FICHIER_METHODE = DOSSIER_DONNEES / "methode.json"


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
    incertitude_kg: tuple[float, float] | None  # (CO2 minimum, CO2 maximum), None si inconnue
    source: str  # d'où vient le facteur utilisé
    statut: str  # « à valider » tant que l'équipe n'a pas validé le facteur


def charger_facteurs(chemin=FICHIER_FACTEURS):
    """Lit les facteurs d'émission et renvoie le dictionnaire {mode: informations}."""
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier)["modes"]


def releve_des_facteurs(chemin=FICHIER_FACTEURS):
    """Renvoie d'où et de quand viennent les facteurs : {"source": ..., "date": "2026-11-24"}.

    La date est celle de la dernière récupération sur l'API Impact CO2
    (scripts/actualiser_facteurs.py). Le site l'affiche à côté de chaque valeur de CO2.
    """
    with open(chemin, encoding="utf-8") as fichier:
        releve = json.load(fichier)["releve"]
    return {"source": releve["source"], "date": releve["date"]}


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


def charger_methode(chemin=FICHIER_METHODE):
    """Lit les choix de méthode de l'équipe (methode.json)."""
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier)


def calculer_co2(mode, distance_km, facteurs=None, niveaux=None, avec_trainees=None):
    """Calcule le CO2 d'un trajet pour un mode et une distance.

    mode           « avion », « train », « bus » ou « voiture »
    distance_km    distance du segment, en kilomètres
    facteurs       facultatif : facteurs à utiliser à la place du fichier (utile pour les tests)
    niveaux        facultatif : niveaux à utiliser à la place du fichier (utile pour les tests)
    avec_trainees  facultatif : compter ou non les traînées de condensation de l'avion.
                   Par défaut, c'est le réglage de methode.json. Sans effet sur les autres modes.
    """
    if facteurs is None:
        facteurs = charger_facteurs()
    if niveaux is None:
        niveaux = charger_niveaux()
    if avec_trainees is None:
        avec_trainees = charger_methode()["options_ademe"]["trainees_de_condensation"]

    if mode not in facteurs:
        modes_connus = ", ".join(sorted(facteurs))
        raise ValueError(f"Mode inconnu : « {mode} ». Modes disponibles : {modes_connus}.")
    if distance_km < 0:
        raise ValueError(f"La distance ne peut pas être négative (reçu : {distance_km} km).")

    infos = facteurs[mode]
    tranche = trouver_tranche(infos["tranches"], distance_km)
    facteur = tranche["facteur_g_pkm"]
    libelle = tranche["libelle"]
    incertitude_kg = (distance_km * infos["min_g_pkm"] / 1000, distance_km * infos["max_g_pkm"] / 1000)

    # Seul l'avion a une part « traînées de condensation » dans son facteur.
    part_trainees = tranche.get("dont_trainees_g_pkm")
    if part_trainees is not None:
        if avec_trainees:
            libelle += ", traînées de condensation incluses"
        else:
            facteur = round(facteur - part_trainees, 3)  # arrondi : évite 123,19999 au lieu de 123,2
            libelle += ", sans les traînées de condensation"
            incertitude_kg = None  # la fourchette du fichier n'a de sens qu'avec les traînées

    return ResultatCO2(
        mode=mode,
        distance_km=distance_km,
        # On divise par 1000 pour passer des grammes aux kilogrammes.
        co2_kg=distance_km * facteur / 1000,
        # Avec un facteur fixe, l'intensité est le facteur lui-même.
        intensite_g_pkm=facteur,
        niveau=trouver_niveau(facteur, niveaux),
        incertitude_kg=incertitude_kg,
        source=f"{infos['source']} : {libelle}",
        statut=infos["statut"],
    )
