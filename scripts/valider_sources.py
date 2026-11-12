"""Vérifie que les sources de données externes répondent avec les clés du .env.

Lancement, depuis la racine du projet :

    python scripts/valider_sources.py

Deux tests pour l'instant :

    1. Travel Impact Model (Google) : émissions typiques d'un vol CDG-BKK.
    2. OpenRouteService : distance et durée de Paris-Lyon en voiture.

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
    """Travel Impact Model : émissions typiques du vol CDG-BKK."""
    print("Travel Impact Model : vol CDG-BKK")
    if not cle:
        print("  ECHEC : la clé TIM_API_Key est absente du fichier .env")
        return False

    url = URL_TIM + "?key=" + urllib.parse.quote(cle)
    corps = {"markets": [{"origin": "CDG", "destination": "BKK"}]}
    code, texte = envoyer_json(url, corps)

    if code != 200:
        afficher_echec("la source a refusé la requête", code, texte)
        return False
    try:
        vol = json.loads(texte)["typicalFlightEmissions"][0]
        grammes = vol["emissionsGramsPerPax"]["economy"]
    except (ValueError, KeyError, IndexError):
        # La doc prévient : si le trajet est inconnu, la réponse arrive sans émissions.
        afficher_echec("réponse reçue, mais sans émissions pour ce trajet", code, texte)
        return False

    version = json.loads(texte).get("modelVersion", {})
    print(f"  OK : {grammes / 1000:.0f} kg CO2e par passager en classe économique")
    print(f"  Toutes les classes (grammes) : {vol['emissionsGramsPerPax']}")
    print(f"  Version du modèle : {version}")
    return True


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


def main():
    cles = lire_env()
    if not cles:
        print(f"Attention : fichier .env introuvable ou vide ({FICHIER_ENV})")

    resultats = [
        tester_tim(cles.get("TIM_API_Key")),
        tester_ors(cles.get("ORS_API_Key")),
    ]

    print()
    print(f"Bilan : {sum(resultats)} source(s) sur {len(resultats)} répondent correctement.")
    # Code de sortie 1 si au moins une source échoue : pratique pour l'automatiser plus tard.
    return 0 if all(resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
