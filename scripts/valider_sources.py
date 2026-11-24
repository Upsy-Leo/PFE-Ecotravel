"""Vérifie que les sources de données externes répondent avec les clés du .env.

Lancement, depuis la racine du projet :

    python scripts/valider_sources.py

Trois contrôles :

    1. Travel Impact Model (Google) : émissions typiques des vols de référence,
       à 15 % près (valeur indicative sur le site).
    2. OpenRouteService : distance et durée de Paris-Lyon en voiture.
    3. Impact CO2 (ADEME) : facteurs d'émission des quatre modes, comparés au
       fichier local à 2 % près. S'ils ont changé : scripts/actualiser_facteurs.py.

Si un test échoue, le script affiche la réponse brute de la source pour aider
à comprendre (clé refusée, quota dépassé, mauvais format...).
Les clés ne sont jamais affichées.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RACINE = Path(__file__).parent.parent
FICHIER_ENV = RACINE / ".env"
FICHIER_REFERENCE = RACINE / "backend" / "donnees" / "trajets_reference.json"
# Écart toléré entre l'API Impact CO2 et le fichier local des facteurs (2 %).
TOLERANCE_IMPACT = 0.02

# Méthode vérifiée le 2026-11-12 dans le document officiel de l'API :
# https://travelimpactmodel.googleapis.com/$discovery/rest?version=v1
URL_TIM = "https://travelimpactmodel.googleapis.com/v1/flights:computeTypicalFlightEmissions"
URL_ORS = "https://api.openrouteservice.org/v2/directions/driving-car"

# Coordonnées approximatives des centres-villes.
# Attention : OpenRouteService attend l'ordre [longitude, latitude].
PARIS = [2.3522, 48.8566]
LYON = [4.8357, 45.7640]


def lire_env(chemin=FICHIER_ENV):
    """Lit le fichier .env et renvoie un dictionnaire {NOM: valeur}."""
    cles = {}
    if not chemin.exists():
        return cles
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        nom, valeur = ligne.split("=", 1)
        cles[nom.strip()] = valeur.strip().strip("\"'")
    return cles


def envoyer_json(url, corps, entetes=None):
    """Envoie une requête POST en JSON.

    Renvoie (code HTTP, texte brut de la réponse). Ne lève pas d'erreur :
    en cas de problème réseau, le code vaut None et le texte décrit le problème.
    """
    entetes_complets = {"Content-Type": "application/json"}
    entetes_complets.update(entetes or {})
    requete = urllib.request.Request(
        url, data=json.dumps(corps).encode("utf-8"), headers=entetes_complets, method="POST"
    )
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            return reponse.status, reponse.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as erreur:
        # La source a répondu, mais par un refus (401, 403, 429...). On garde son message.
        return erreur.code, erreur.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as erreur:
        return None, f"Pas de réponse : {erreur}"


def afficher_echec(raison, code, texte):
    print(f"  ECHEC : {raison}")
    print(f"  Code HTTP : {code}")
    print("  Réponse brute :")
    print(texte)


def tester_tim(cle):
    """Travel Impact Model : émissions typiques des trajets de référence, à une tolérance près."""
    print("Travel Impact Model : trajets de référence en avion")
    if not cle:
        print("  ECHEC : la clé TIM_API_Key est absente du fichier .env")
        return False

    # Les trajets de référence et la tolérance sont dans un fichier, pas dans ce script.
    reference = json.loads(FICHIER_REFERENCE.read_text(encoding="utf-8"))
    tolerance = reference["tolerances"]["tim"]
    trajets = reference["trajets"]

    url = URL_TIM + "?key=" + urllib.parse.quote(cle)
    corps = {"markets": [{"origin": t["origine"], "destination": t["destination"]} for t in trajets]}
    code, texte = envoyer_json(url, corps)

    if code != 200:
        afficher_echec("la source a refusé la requête", code, texte)
        return False
    try:
        vols = json.loads(texte)["typicalFlightEmissions"]
        grammes = [vol["emissionsGramsPerPax"]["economy"] for vol in vols]
    except (ValueError, KeyError, IndexError):
        # La doc prévient : si le trajet est inconnu, la réponse arrive sans émissions.
        afficher_echec("réponse reçue, mais sans émissions pour un des trajets", code, texte)
        return False

    # Cette valeur n'est plus qu'indicative sur le site (le CO2 de l'avion est calculé
    # avec les facteurs ADEME). On la contrôle quand même, avec une tolérance : elle
    # change un peu d'un jour à l'autre, une valeur exacte casserait le contrôle.
    tout_va_bien = True
    for trajet, valeur in zip(trajets, grammes):
        obtenu, attendu = valeur / 1000, trajet["co2_tim_kg"]
        ecart = (obtenu - attendu) / attendu
        dans_la_plage = abs(ecart) <= tolerance
        tout_va_bien = tout_va_bien and dans_la_plage
        verdict = "OK" if dans_la_plage else "HORS TOLÉRANCE"
        print(f"  {verdict} : {trajet['nom']} ({trajet['origine']}-{trajet['destination']}) : {obtenu:.0f} kg, "
              f"attendu {attendu:.0f} kg à {tolerance:.0%} près (écart {ecart:+.1%})")
    if not tout_va_bien:
        print("  Un écart hors tolérance signale un changement du modèle ou une erreur : à examiner.")
        print("  Réponse brute :")
        print(texte)
    print(f"  Version du modèle : {json.loads(texte).get('modelVersion', {})}")
    return tout_va_bien


def tester_ors(cle):
    """OpenRouteService : Paris-Lyon en voiture."""
    print("OpenRouteService : Paris-Lyon en voiture")
    if not cle:
        print("  ECHEC : la clé ORS_API_Key est absente du fichier .env")
        return False

    corps = {"coordinates": [PARIS, LYON]}
    code, texte = envoyer_json(URL_ORS, corps, entetes={"Authorization": cle})

    if code != 200:
        afficher_echec("la source a refusé la requête", code, texte)
        return False
    try:
        resume = json.loads(texte)["routes"][0]["summary"]
        distance_km = resume["distance"] / 1000  # la source répond en mètres
        duree_min = resume["duration"] / 60  # la source répond en secondes
    except (ValueError, KeyError, IndexError):
        afficher_echec("réponse reçue, mais sans distance ni durée", code, texte)
        return False

    heures, minutes = divmod(round(duree_min), 60)
    print(f"  OK : {distance_km:.0f} km, {heures} h {minutes:02d} min")
    return True


def tester_impact(cle):
    """Impact CO2 (ADEME) : les facteurs de l'API sont-ils toujours ceux du fichier local ?

    Le site lit le fichier local, pas l'API. Ce contrôle interroge l'API comme le fait
    scripts/actualiser_facteurs.py, sans rien écrire, et compare à une tolérance près.
    """
    print("Impact CO2 (ADEME) : facteurs d'émission des quatre modes")
    if not cle:
        print("  ECHEC : la clé IMPACT_API_Key est absente du fichier .env")
        return False

    # Import fait ici : il charge le code du backend, dont les autres contrôles se passent.
    import actualiser_facteurs as outil

    facteurs = json.loads(outil.FICHIER_FACTEURS.read_text(encoding="utf-8"))
    avec_construction = outil.charger_methode()["options_ademe"]["construction_des_vehicules"]
    identifiants = [infos["id_impact_co2"] for infos in facteurs["modes"].values()]
    try:
        obtenus, _ = outil.actualiser(
            facteurs,
            lambda km, sans_trainees: outil.interroger(km, avec_construction, sans_trainees, identifiants, cle),
            avec_construction,
            facteurs["releve"]["date"],
        )
    except outil.commun.ErreurSource as erreur:
        print("  ECHEC : l'API n'a pas donné tous les facteurs")
        print("  Réponse brute :")
        print(f"  {erreur}")
        return False

    tout_va_bien = True
    for mode, infos in facteurs["modes"].items():
        for tranche, obtenue in zip(infos["tranches"], obtenus["modes"][mode]["tranches"]):
            local, api = tranche["facteur_g_pkm"], obtenue["facteur_g_pkm"]
            dans_la_plage = abs(api - local) <= local * TOLERANCE_IMPACT
            tout_va_bien = tout_va_bien and dans_la_plage
            verdict = "OK" if dans_la_plage else "HORS TOLÉRANCE"
            print(f"  {verdict} : {mode}, {obtenue['libelle']} : {api} g/passager·km (fichier local : {local})")
    print(f"  Fichier local récupéré le {facteurs['releve']['date']}.")
    if not tout_va_bien:
        print("  Les facteurs ont changé à la source : lancer « python scripts/actualiser_facteurs.py ».")
    return tout_va_bien


def main():
    cles = lire_env()
    if not cles:
        print(f"Attention : fichier .env introuvable ou vide ({FICHIER_ENV})")

    resultats = [
        tester_tim(cles.get("TIM_API_Key")),
        tester_ors(cles.get("ORS_API_Key")),
        tester_impact(cles.get("IMPACT_API_Key")),
    ]

    print()
    print(f"Bilan : {sum(resultats)} source(s) sur {len(resultats)} répondent correctement.")
    # Code de sortie 1 si au moins une source échoue : pratique pour l'automatiser plus tard.
    return 0 if all(resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
