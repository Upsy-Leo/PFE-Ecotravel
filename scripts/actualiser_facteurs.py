"""Récupère les facteurs d'émission sur l'API Impact CO2 (ADEME) et réécrit le fichier local.

Le site ne parle jamais à cette API : il lit backend/donnees/facteurs_emission.json.
Ce script sert à rafraîchir ce fichier de temps en temps, à la main.

Lancement, depuis la racine du projet :

    python scripts/actualiser_facteurs.py            # récupère et réécrit le fichier
    python scripts/actualiser_facteurs.py --essai    # montre les changements sans rien écrire

Ce qu'il fait :
1. lit la clé IMPACT_API_Key dans .env et les réglages de methode.json
   (construction des véhicules comptée ou non) ;
2. demande à l'API les émissions de nos quatre modes, à une distance prise dans
   chaque tranche de l'avion ;
3. demande une seconde fois sans les traînées de condensation, pour connaître leur
   part dans le facteur de l'avion ;
4. réécrit le fichier avec les nouveaux facteurs et la date de récupération.

Ce qu'il ne touche pas : les fourchettes (min, max), les notes « à vérifier » et le
statut « à valider », qui sont écrits par l'équipe.

Si l'API ne répond pas ou si un mode manque, rien n'est écrit.

Paramètres de l'API vérifiés le 2026-11-24 dans son code source et sur des réponses
réelles : km, transports (identifiants), includeConstruction, ignoreRadiativeForcing.
Attention : l'API accepte n'importe quelle clé sans le dire ; elle ne signale que
l'absence de clé. Une réponse correcte ne prouve donc pas que la clé est valide.
"""

import copy
import json
import sys
import urllib.parse
from datetime import date
from pathlib import Path

RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE))  # pour pouvoir écrire « from backend... » depuis ce dossier

from backend.adaptateurs import commun  # noqa: E402 (import après la ligne ci-dessus, c'est voulu)
from backend.moteur_co2 import FICHIER_FACTEURS, charger_methode  # noqa: E402
from backend.serveur import lire_env  # noqa: E402

URL = "https://impactco2.fr/api/v1/transport"


def distances_de_mesure(facteurs):
    """Renvoie une distance à interroger par tranche de l'avion, par exemple [1000, 2000, 5000, 5001].

    L'API donne un facteur différent selon la longueur du vol. On l'interroge donc à
    la limite haute de chaque tranche, et juste après la dernière limite pour la
    tranche « au-delà ».
    """
    distances = []
    for tranche in facteurs["modes"]["avion"]["tranches"]:
        limite = tranche["jusqu_a_km"]
        distances.append(limite if limite is not None else distances[-1] + 1)
    return distances


def interroger(km, avec_construction, sans_trainees, identifiants, cle):
    """Demande à l'API les émissions à « km » kilomètres. Renvoie {identifiant: (nom, g par km)}."""
    parametres = urllib.parse.urlencode({
        "km": km,
        "transports": ",".join(str(identifiant) for identifiant in identifiants),
        "includeConstruction": 1 if avec_construction else 0,
        "ignoreRadiativeForcing": 1 if sans_trainees else 0,
    })
    reponse = commun.appeler_json(f"{URL}?{parametres}", entetes={"Authorization": f"Bearer {cle}"})
    try:
        # « value » est en kg pour la distance demandée : on revient à des grammes par km.
        return {ligne["id"]: (ligne["name"], round(ligne["value"] / km * 1000, 2)) for ligne in reponse["data"]}
    except (KeyError, TypeError) as erreur:
        raise commun.ErreurSource(f"Réponse inattendue : {str(reponse)[:500]}") from erreur


def actualiser(facteurs, mesurer, avec_construction, jour):
    """Fabrique le nouveau contenu du fichier. Renvoie (nouveaux_facteurs, changements).

    facteurs  contenu actuel de facteurs_emission.json
    mesurer   fonction (km, sans_trainees) -> {identifiant: (nom, g par km)} ; dans le
              script, elle appelle l'API ; dans les tests, elle est simulée
    jour      date de récupération, au format « 2026-11-24 »

    Lève ErreurSource si un mode manque dans une réponse : le fichier ne doit jamais
    être réécrit à moitié.
    """
    nouveaux = copy.deepcopy(facteurs)
    changements = []

    def lire(mesure, mode, km):
        identifiant = nouveaux["modes"][mode]["id_impact_co2"]
        if identifiant not in mesure:
            raise commun.ErreurSource(f"Le mode « {mode} » (identifiant {identifiant}) manque dans la réponse à {km} km.")
        return mesure[identifiant]

    def noter(libelle, ancien, nouveau):
        if ancien != nouveau:
            changements.append(f"{libelle} : {ancien} -> {nouveau}")

    for rang, km in enumerate(distances_de_mesure(facteurs)):
        avec = mesurer(km, False)
        sans = mesurer(km, True)

        # L'avion : une tranche par distance, et la part des traînées par différence.
        tranche = nouveaux["modes"]["avion"]["tranches"][rang]
        nom, facteur = lire(avec, "avion", km)
        _, facteur_sans_trainees = lire(sans, "avion", km)
        noter(f"avion, {nom}", tranche["facteur_g_pkm"], facteur)
        tranche["facteur_g_pkm"] = facteur
        tranche["dont_trainees_g_pkm"] = round(facteur - facteur_sans_trainees, 2)
        tranche["libelle"] = nom

        # Les autres modes ne dépendent pas de la distance : la première réponse suffit.
        if rang == 0:
            for mode in ("train", "bus", "voiture"):
                nom, facteur = lire(avec, mode, km)
                tranche_unique = nouveaux["modes"][mode]["tranches"][0]
                noter(mode, tranche_unique["facteur_g_pkm"], facteur)
                tranche_unique["facteur_g_pkm"] = facteur

    for infos in nouveaux["modes"].values():
        infos["source"] = f"Impact CO2 (ADEME), récupéré le {jour}"
    nouveaux["releve"] = {
        "source": "API Impact CO2 (ADEME)",
        "url": URL,
        "date": jour,
        "recupere_par": "scripts/actualiser_facteurs.py",
        "reglages": (
            ("Avec" if avec_construction else "Sans") + " la construction des véhicules, une personne par véhicule. "
            "Le facteur de l'avion contient les traînées de condensation ; leur part est notée « dont_trainees_g_pkm », "
            "et methode.json dit si le calcul les compte."
        ),
        "fourchettes": facteurs["releve"].get("fourchettes", ""),
    }
    return nouveaux, changements


def main():
    essai = "--essai" in sys.argv
    cle = lire_env().get("IMPACT_API_Key")
    if not cle:
        print("ECHEC : la clé IMPACT_API_Key est absente du fichier .env. Rien n'a été modifié.")
        return 1

    facteurs = json.loads(FICHIER_FACTEURS.read_text(encoding="utf-8"))
    avec_construction = charger_methode()["options_ademe"]["construction_des_vehicules"]
    identifiants = [infos["id_impact_co2"] for infos in facteurs["modes"].values()]
    jour = date.today().isoformat()

    def mesurer(km, sans_trainees):
        return interroger(km, avec_construction, sans_trainees, identifiants, cle)

    try:
        nouveaux, changements = actualiser(facteurs, mesurer, avec_construction, jour)
    except commun.ErreurSource as erreur:
        print("ECHEC : l'API Impact CO2 n'a pas donné tous les facteurs. Rien n'a été modifié.")
        print(f"Détail : {erreur}")
        return 1

    print(f"Facteurs récupérés le {jour} ({'avec' if avec_construction else 'sans'} la construction des véhicules) :")
    for mode, infos in nouveaux["modes"].items():
        for tranche in infos["tranches"]:
            trainees = f", dont {tranche['dont_trainees_g_pkm']} de traînées" if "dont_trainees_g_pkm" in tranche else ""
            print(f"  {mode:8} {tranche['libelle']:38} {tranche['facteur_g_pkm']:7} g/passager·km{trainees}")
    print("Changements par rapport au fichier :" if changements else "Aucun facteur n'a changé par rapport au fichier.")
    for changement in changements:
        print(f"  {changement}")

    if essai:
        print("Mode essai : le fichier n'a pas été modifié.")
        return 0
    FICHIER_FACTEURS.write_text(json.dumps(nouveaux, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Fichier réécrit : {FICHIER_FACTEURS}")
    if changements:
        print("Des facteurs ont changé : relancez les tests, les trajets de référence sont peut-être à recalculer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
