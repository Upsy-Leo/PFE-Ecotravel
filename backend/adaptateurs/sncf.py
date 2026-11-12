"""Tarifs SNCF : fourchette de prix d'un trajet en TGV INOUI ou OUIGO.

    from backend.adaptateurs import sncf

    sncf.prix_train("Paris", "Lyon")        # (16.0, 115.0)
    option = sncf.appliquer_tarif(option, "Paris", "Lyon")

Ce n'est pas une API : le fichier est embarqué dans backend/donnees/tarifs_sncf.csv.
Source : SNCF Voyageurs, jeu « Tarifs TGV INOUI et OUIGO », licence ODbL
(https://ressources.data.sncf.com/explore/dataset/tarifs-tgv-inoui-ouigo/).
Version embarquée : mise à jour du 2026-03-17, téléchargée le 2026-11-12.
Pour la rafraîchir : exporter le jeu en CSV (séparateur « ; ») et remplacer le fichier.

Chaque ligne du fichier donne, pour un trajet de gare à gare, un transporteur,
une classe et un profil tarifaire, un prix minimum et un prix maximum.

Hypothèses (à valider en équipe) :
- on garde la 2de classe et le « Tarif Normal » (adulte sans carte de réduction) ;
- on mélange TGV INOUI et OUIGO : du moins cher des minimums au plus cher des maximums ;
- une ville regroupe toutes ses gares (« Lyon » = Part-Dieu, Perrache, Saint-Exupéry…) ;
- le prix est le même dans les deux sens : beaucoup de trajets ne figurent dans le
  fichier que dans un sens ;
- le prix reste « indicatif » : c'est la fourchette de la grille tarifaire, pas le
  prix d'un billet à une date donnée.
"""

import csv
import dataclasses
import functools
import unicodedata

from backend.adaptateurs import commun

FICHIER_TARIFS = commun.DOSSIER_BACKEND / "donnees" / "tarifs_sncf.csv"
SOURCE = "SNCF Voyageurs, Tarifs TGV INOUI et OUIGO (ODbL), 2de classe plein tarif, fichier du 2026-03-17"

CLASSE = "2"
PROFIL = "Tarif Normal"


def _simplifier(nom):
    """Écrit un nom de ville ou de gare comme dans le fichier : « Saint-Étienne » -> « ST ETIENNE »."""
    sans_accents = unicodedata.normalize("NFD", nom).encode("ascii", "ignore").decode("ascii")
    mots = sans_accents.upper().replace("-", " ").replace("'", " ").split()
    return " ".join("ST" if mot == "SAINT" else mot for mot in mots)


def _est_dans_la_ville(gare, ville):
    """« LYON PART DIEU » est une gare de « LYON » ; « PARIS GARE DE LYON » n'en est pas une."""
    return gare == ville or gare.startswith(ville + " ")


# functools.cache : le fichier (36 000 lignes) n'est lu qu'une fois, puis gardé en mémoire.
@functools.cache
def charger_tarifs(chemin=FICHIER_TARIFS):
    """Lit le fichier et renvoie la liste des tarifs retenus : (gare_origine, gare_destination, min, max)."""
    tarifs = []
    # « utf-8-sig » : accepte le marqueur invisible que certains exports mettent en début de fichier.
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        for ligne in csv.DictReader(fichier, delimiter=";"):
            if ligne["classe"] == CLASSE and ligne["profil_tarifaire"] == PROFIL:
                tarifs.append((
                    _simplifier(ligne["gare_origine"]),
                    _simplifier(ligne["gare_destination"]),
                    float(ligne["prix_minimum"]),
                    float(ligne["prix_maximum"]),
                ))
    return tarifs


def prix_train(ville_depart, ville_arrivee, chemin=FICHIER_TARIFS):
    """Renvoie (prix_min, prix_max) en euros entre deux villes, ou None si le trajet n'est pas dans le fichier."""
    depart, arrivee = _simplifier(ville_depart), _simplifier(ville_arrivee)
    if not depart or not arrivee:
        return None
    trouves = [
        (prix_min, prix_max)
        for origine, destination, prix_min, prix_max in charger_tarifs(chemin)
        if (_est_dans_la_ville(origine, depart) and _est_dans_la_ville(destination, arrivee))
        or (_est_dans_la_ville(origine, arrivee) and _est_dans_la_ville(destination, depart))
    ]
    if not trouves:
        return None
    return min(prix[0] for prix in trouves), max(prix[1] for prix in trouves)


def appliquer_tarif(option, ville_depart, ville_arrivee):
    """Remplace le prix au barème d'une Option « train » par la fourchette SNCF, si le trajet est connu.

    Si le trajet n'est pas dans le fichier, l'option est renvoyée telle quelle
    (elle garde son prix au barème, et sa source le dit).
    """
    prix = prix_train(ville_depart, ville_arrivee)
    if option is None or option.mode != "train" or prix is None:
        return option
    return dataclasses.replace(
        option,
        prix_min=prix[0],
        prix_max=prix[1],
        type_prix="indicatif",
        source={**option.source, "prix": SOURCE},
    )
