"""Tests des barèmes : prix indicatifs au km et durée d'avion."""

import json
import unittest

from backend.adaptateurs import commun

MODES = ["avion", "train", "bus", "voiture"]


class TestBaremePrix(unittest.TestCase):
    def test_fichier_marque_a_valider_avec_hypotheses(self):
        bareme = json.loads(commun.FICHIER_BAREME_PRIX.read_text(encoding="utf-8"))
        self.assertEqual(bareme["statut"], "à valider")
        for mode in MODES:
            with self.subTest(mode=mode):
                self.assertTrue(bareme["modes"][mode]["hypotheses"])

    def test_toujours_une_fourchette(self):
        # Règle de fiabilité : un prix indicatif n'est jamais une valeur unique.
        for mode in MODES:
            for distance in (50, 430, 3000, 9450):
                with self.subTest(mode=mode, distance=distance):
                    prix_min, prix_max = commun.estimer_prix(mode, distance)
                    self.assertGreater(prix_min, 0)
                    self.assertGreater(prix_max, prix_min)

    def test_voiture_paris_lyon(self):
        # 465 km × 0,10 à 0,28 €/km, arrondi à l'euro.
        self.assertEqual(commun.estimer_prix("voiture", 465), (46, 130))

    def test_avion_change_de_tranche_avec_la_distance(self):
        self.assertEqual(commun.estimer_prix("avion", 1000), (60, 300))  # jusqu'à 1 000 km : 0,06 à 0,30
        self.assertEqual(commun.estimer_prix("avion", 10000), (300, 1000))  # long-courrier : 0,03 à 0,10

    def test_option_porte_un_prix_indicatif_et_sa_source(self):
        option = commun.construire_option("bus", 472, 380, "essai", "essai")
        self.assertEqual(option.type_prix, "indicatif")
        self.assertLess(option.prix_min, option.prix_max)
        self.assertIn("à valider", option.source["prix"])


class TestDureeAvion(unittest.TestCase):
    def test_formule(self):
        # 150 min d'aéroport + 40 min de décollage et d'atterrissage + 880 km à 880 km/h (60 min).
        self.assertAlmostEqual(commun.estimer_duree_avion_min(880), 250.0)

    def test_paris_bangkok(self):
        # Environ 11 h 24 de vol + 2 h 30 d'aéroport, soit près de 14 h.
        self.assertAlmostEqual(commun.estimer_duree_avion_min(9450), 834.3, places=1)


if __name__ == "__main__":
    unittest.main()
