"""Serveur web local du comparateur.

Lancement, depuis la racine du projet :

    python -m backend.serveur

Puis, dans un navigateur :

    http://localhost:8000/index.html?depart=Paris&arrivee=Lyon&date=2026-12-01

- /comparer renvoie les options en JSON, ou la liste des villes homonymes à
  départager (la position choisie revient alors dans depart_point ou arrivee_point) ;
- /lieux?texte=Bre renvoie les villes proposées pendant la frappe ;
- /reference renvoie les facteurs, seuils et barèmes (pour la page « Méthode et limites ») ;
- toute autre adresse sert les fichiers du dossier frontend/ (index.html, style.css, app.js).

Le serveur n'écoute que sur cet ordinateur (127.0.0.1). Il utilise le serveur web
fourni avec Python : suffisant pour développer, pas pour une mise en ligne.
Les clés restent ici, côté serveur : elles ne sont jamais envoyées au navigateur.
"""

import json
import traceback
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from backend.adaptateurs import ors
from backend.comparateur import ErreurDemande, comparer

RACINE = Path(__file__).parent.parent
FICHIER_ENV = RACINE / ".env"
DOSSIER_FRONTEND = RACINE / "frontend"
ADRESSE = "127.0.0.1"
PORT = 8000
LETTRES_MINIMUM = 3  # nombre de lettres à partir duquel des villes sont proposées


def lire_env(chemin=FICHIER_ENV):
    """Lit le fichier .env et renvoie un dictionnaire {NOM: valeur}. Ne jamais l'afficher."""
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


def repondre_a_comparer(parametres, cles):
    """Traite une demande /comparer. Renvoie (code HTTP, dictionnaire à envoyer en JSON)."""
    try:
        return 200, comparer(
            parametres.get("depart"),
            parametres.get("arrivee"),
            parametres.get("date"),
            cles,
            point_depart=parametres.get("depart_point"),
            point_arrivee=parametres.get("arrivee_point"),
        )
    except ErreurDemande as erreur:
        return erreur.code, {"erreur": str(erreur)}
    except Exception:
        # Erreur imprévue : le détail va dans la console du serveur, pas au navigateur.
        traceback.print_exc()
        return 500, {"erreur": "Erreur interne du serveur. Le détail est dans la console du serveur."}


def repondre_a_lieux(parametres, cles):
    """Traite une demande /lieux?texte=Bre : villes proposées pendant la frappe."""
    texte = (parametres.get("texte") or "").strip()
    # Moins de 3 lettres : trop de villes possibles, on n'interroge pas la source (quota).
    if len(texte) < LETTRES_MINIMUM or not cles.get("ORS_API_Key"):
        return 200, {"lieux": []}
    try:
        return 200, {"lieux": ors.suggerer_lieux(texte, cles["ORS_API_Key"])}
    except Exception:
        traceback.print_exc()
        return 200, {"lieux": []}  # pas de propositions, mais la saisie reste possible


def lire_reference():
    """Fichiers de configuration affichés par la page « Méthode et limites ».

    La page lit les facteurs, les seuils et les barèmes ici plutôt que de les
    recopier : si l'équipe change une valeur dans un fichier JSON, la page suit.
    """
    donnees = RACINE / "backend" / "donnees"
    return {
        nom: json.loads((donnees / f"{nom}.json").read_text(encoding="utf-8"))
        for nom in ("facteurs_emission", "niveaux_co2", "bareme", "bareme_prix", "methode", "trajets_reference")
    }


class Gestionnaire(SimpleHTTPRequestHandler):
    def __init__(self, *arguments, **options):
        super().__init__(*arguments, directory=str(DOSSIER_FRONTEND), **options)

    def end_headers(self):
        # « no-cache » : le navigateur doit vérifier à chaque fois que sa copie est à jour.
        # Sans cela, il peut garder un vieil app.js pendant des heures et l'utiliser avec
        # un serveur plus récent (constaté le 2026-11-24 : menu absent, comparaison en erreur).
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        adresse = urllib.parse.urlsplit(self.path)
        if adresse.path == "/comparer":
            # parse_qsl décode « depart=Paris&arrivee=Lyon » en {"depart": "Paris", "arrivee": "Lyon"}.
            parametres = dict(urllib.parse.parse_qsl(adresse.query))
            code, reponse = repondre_a_comparer(parametres, lire_env())
        elif adresse.path == "/lieux":
            code, reponse = repondre_a_lieux(dict(urllib.parse.parse_qsl(adresse.query)), lire_env())
        elif adresse.path == "/reference":
            code, reponse = 200, lire_reference()
        else:
            return super().do_GET()  # fichiers du site

        corps = json.dumps(reponse, ensure_ascii=False, indent=1).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)


class Serveur(ThreadingHTTPServer):
    """Serveur qui traite chaque connexion à part.

    Un navigateur ouvre souvent des connexions d'avance, sans rien y envoyer tout de
    suite. Un serveur qui traite une connexion à la fois reste bloqué sur l'une d'elles
    et ne répond plus à personne : la page « charge à l'infini ». Ici, chaque connexion
    a son propre fil d'exécution (les écritures du cache sont protégées par un verrou,
    voir adaptateurs/commun.py).
    """

    daemon_threads = True  # les connexions en attente ne retiennent pas l'arrêt du serveur
    # Refuser de démarrer si le port est déjà pris : sous Windows, deux serveurs pouvaient
    # sinon écouter sur le même port, et on ne savait plus lequel répondait.
    allow_reuse_address = False


def main():
    try:
        serveur = Serveur((ADRESSE, PORT), Gestionnaire)
    except OSError:
        print(f"Le port {PORT} est déjà utilisé : un autre serveur tourne sans doute déjà. Arrêtez-le (Ctrl+C) puis relancez.")
        return
    print(f"Serveur lancé : http://localhost:{PORT}/")
    print("Ctrl+C pour l'arrêter.")
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("Serveur arrêté.")


if __name__ == "__main__":
    main()
