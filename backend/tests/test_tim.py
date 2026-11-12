"""Tests de l'adaptateur Travel Impact Model, avec des réponses simulées."""

import unittest

from backend.adaptateurs import tim
from backend.moteur_co2 import calculer_co2
from backend.tests.outils import TestAdaptateur

# Vraie réponse pour CDG-BKK, relevée le 2026-11-12.
REPONSE = {
    "typicalFlightEmissions": [
        {
            "market": {"origin": "CDG", "destination": "BKK"},
            "emissionsGramsPerPax": {
                "first": 3183415,
                "business": 2564709,
                "premiumEconomy": 987980,
                "economy": 667196,
            },
        }
    ],
    "modelVersion": {"major": 3, "minor": 0, "patch": 2, "dated": "20261112"},
}

# Ce que répond la source quand elle ne connaît pas le trajet : pas d'émissions.
REPONSE_TRAJET_INCONNU = {"typicalFlightEmissions": [{"market": {"origin": "CDG", "destination": "XXX"}}]}


class TestOptionVol(TestAdaptateur):
    def test_reponse_de_la_source(self):
        self.simuler_reponse(REPONSE)
        option = tim.option_vol("cdg", "bkk", 9450, "fausse-cle")

        self.assertEqual(option.mode, "avion")
        self.assertEqual(option.distance_km, 9450)
        self.assertAlmostEqual(option.co2_kg, 667.196)  # grammes convertis en kg, classe économique
        self.assertAlmostEqual(option.intensite_g_pkm, 667196 / 9450)  # environ 71 g/passager·km
        self.assertEqual(option.niveau, "C")
        self.assertIsNone(option.incertitude)
        self.assertIn("Travel Impact Model", option.source["co2"])
        # Durée et prix sont estimés par barème, et la source le dit.
        self.assertAlmostEqual(option.duree_min, 834.3, places=1)  # près de 14 h, aéroport compris
        self.assertIn("Barème", option.source["duree"])
        self.assertEqual((option.prix_min, option.prix_max), (284, 945))  # 9 450 km × 0,03 à 0,10 €
        self.assertEqual(option.type_prix, "indicatif")
        self.assertIn("à valider", option.source["prix"])

    def test_requete_envoyee(self):
        faux_appel = self.simuler_reponse(REPONSE)
        tim.option_vol("cdg", "bkk", 9450, "fausse-cle")

        url = faux_appel.call_args.args[0]
        self.assertIn("flights:computeTypicalFlightEmissions", url)
        # Les codes IATA partent en majuscules.
        self.assertEqual(
            faux_appel.call_args.kwargs["corps"], {"markets": [{"origin": "CDG", "destination": "BKK"}]}
        )

    def test_deuxieme_demande_servie_par_le_cache(self):
        faux_appel = self.simuler_reponse(REPONSE)
        tim.option_vol("CDG", "BKK", 9450, "fausse-cle")
        option = tim.option_vol("CDG", "BKK", 9450, "fausse-cle")

        self.assertEqual(faux_appel.call_count, 1)
        self.assertAlmostEqual(option.co2_kg, 667.196)
        self.assertIn("cache du", option.source["co2"])

    def test_panne_sans_cache_repli_sur_ademe(self):
        self.simuler_panne()
        option = tim.option_vol("CDG", "BKK", 9450, "fausse-cle")

        attendu = calculer_co2("avion", 9450)
        self.assertAlmostEqual(option.co2_kg, attendu.co2_kg)
        self.assertEqual(option.niveau, attendu.niveau)
        self.assertEqual(option.incertitude, attendu.incertitude_kg)
        self.assertIn("Repli", option.source["co2"])
        self.assertIn("à valider", option.source["co2"])

    def test_trajet_inconnu_repli_sur_ademe(self):
        self.simuler_reponse(REPONSE_TRAJET_INCONNU)
        option = tim.option_vol("CDG", "XXX", 1000, "fausse-cle")
        self.assertIn("Repli", option.source["co2"])

    def test_distance_nulle_refusee(self):
        with self.assertRaises(ValueError):
            tim.option_vol("CDG", "BKK", 0, "fausse-cle")


if __name__ == "__main__":
    unittest.main()
