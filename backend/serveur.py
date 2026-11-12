"""Serveur web local du comparateur.

Lancement, depuis la racine du projet :

    python -m backend.serveur

Puis, dans un navigateur :

    http://localhost:8000/comparer?depart=Paris&arrivee=Lyon&date=2026-12-01

- /comparer renvoie les options en JSON ;
- toute autre adresse sert les fichiers du dossier frontend/ (index.html, style.css, app.js).

Le serveur n'écoute que sur cet ordinateur (127.0.0.1). Il utilise le serveur web
fourni avec Python : suffisant pour développer, pas pour une mise en ligne.
Les clés restent ici, côté serveur : elles ne sont jamais envoyées au navigateur.
"""

import json
import traceback
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

from backend.comparateur import ErreurDemande, comparer

RACINE = Path(__file__).parent.parent
FICHIER_ENV = RACINE / ".env"
DOSSIER_FRONTEND = RACINE / "frontend"
ADRESSE = "127.0.0.1"
PORT = 8000


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
        return 200, comparer(parametres.get("depart"), parametres.get("arrivee"), parametres.get("date"), cles)
    except ErreurDemande as erreur:
        return erreur.code, {"erreur": str(erreur)}
    except Exception:
        # Erreur imprévue : le détail va dans la console du serveur, pas au navigateur.
        traceback.print_exc()
        return 500, {"erreur": "Erreur interne du serveur. Le détail est dans la console du serveur."}


class Gestionnaire(SimpleHTTPRequestHandler):
    def __init__(self, *arguments, **options):
        super().__init__(*arguments, directory=str(DOSSIER_FRONTEND), **options)

    def do_GET(self):
        adresse = urllib.parse.urlsplit(self.path)
        if adresse.path != "/comparer":
            return super().do_GET()  # fichiers du site

        # parse_qsl décode « depart=Paris&arrivee=Lyon » en {"depart": "Paris", "arrivee": "Lyon"}.
        parametres = dict(urllib.parse.parse_qsl(adresse.query))
        code, reponse = repondre_a_comparer(parametres, lire_env())
        corps = json.dumps(reponse, ensure_ascii=False, indent=1).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)


def main():
    # HTTPServer traite une demande à la fois : deux demandes ne peuvent donc pas
    # écrire dans le fichier de cache en même temps.
    serveur = HTTPServer((ADRESSE, PORT), Gestionnaire)
    print(f"Serveur lancé : http://localhost:{PORT}/comparer?depart=Paris&arrivee=Lyon&date=2026-12-01")
    print("Ctrl+C pour l'arrêter.")
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("Serveur arrêté.")


if __name__ == "__main__":
    main()
