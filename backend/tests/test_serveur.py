"""Tests du serveur web lui-même : on le lance pour de bon, sur un port libre de cet ordinateur.

Aucune source extérieure n'est appelée : seules les routes locales sont demandées.
"""

import json
import socket
import threading
import unittest
import urllib.request

from backend import serveur
from backend.adaptateurs import commun
from backend.tests.outils import TestAdaptateur


class TestServeur(unittest.TestCase):
    def setUp(self):
        # Port 0 : le système choisit un port libre.
        self.serveur = serveur.Serveur(("127.0.0.1", 0), serveur.Gestionnaire)
        self.port = self.serveur.server_address[1]
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()
        self.addCleanup(self.serveur.server_close)
        self.addCleanup(self.serveur.shutdown)

    def demander(self, chemin):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{chemin}", timeout=5) as reponse:
            return reponse.status, reponse.read()

    def test_page_d_accueil_et_reference(self):
        code, corps = self.demander("/")
        self.assertEqual(code, 200)
        self.assertIn(b"<form", corps)
        code, corps = self.demander("/reference")
        self.assertEqual(code, 200)
        self.assertIn("niveaux_co2", json.loads(corps))

    def test_le_navigateur_ne_garde_pas_une_vieille_copie(self):
        # Fichiers du site comme réponses JSON : le navigateur doit revérifier à chaque fois.
        for chemin in ("/app.js", "/index.html", "/reference"):
            with self.subTest(chemin=chemin):
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{chemin}", timeout=5) as reponse:
                    self.assertEqual(reponse.headers["Cache-Control"], "no-cache")

    def test_une_connexion_muette_ne_bloque_pas_les_autres(self):
        # Les navigateurs ouvrent des connexions d'avance, sans rien y envoyer. Avec un
        # serveur qui traite une connexion à la fois, la page chargeait à l'infini
        # (constaté le 2026-11-24 dans un navigateur, pas dans celui de VS Code).
        muette = socket.create_connection(("127.0.0.1", self.port))
        self.addCleanup(muette.close)
        code, _ = self.demander("/reference")  # lèverait une erreur après 5 s si le serveur était bloqué
        self.assertEqual(code, 200)

    def test_refuse_un_port_deja_pris(self):
        with self.assertRaises(OSError):
            serveur.Serveur(("127.0.0.1", self.port), serveur.Gestionnaire)


class TestCachePartage(TestAdaptateur):
    def test_ecritures_simultanees_aucune_reponse_perdue(self):
        # Vingt demandes écrivent en même temps dans le cache : les vingt doivent y être.
        fils = [
            threading.Thread(target=commun.avec_repli, args=(f"essai:{numero}", lambda numero=numero: {"n": numero}))
            for numero in range(20)
        ]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join()
        cache = json.loads(commun.FICHIER_CACHE.read_text(encoding="utf-8"))
        self.assertEqual(len(cache), 20)


if __name__ == "__main__":
    unittest.main()
