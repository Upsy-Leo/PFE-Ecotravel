"""Tests de l'adaptateur OpenRouteService, avec des réponses simulées."""

import unittest

from backend.adaptateurs import ors
from backend.moteur_co2 import calculer_co2
from backend.tests.outils import LYON, PARIS, TestAdaptateur

# Extrait d'une vraie réponse d'itinéraire (Paris-Lyon, relevé du 2026-11-12, arrondi).
REPONSE_ITINERAIRE = {"routes": [{"summary": {"distance": 465000.0, "duration": 16380.0}}]}

# Extrait d'une vraie réponse de géocodage.
REPONSE_GEOCODAGE = {
    "features": [
        {
            "geometry": {"coordinates": [2.342865, 48.858705]},
            "properties": {"label": "Paris, France", "layer": "locality"},
        }
    ]
}


class TestOptionVoiture(TestAdaptateur):
    def test_reponse_de_la_source(self):
        self.simuler_reponse(REPONSE_ITINERAIRE)
        option = ors.option_voiture(PARIS, LYON, "fausse-cle")

        self.assertEqual(option.mode, "voiture")
        self.assertAlmostEqual(option.distance_km, 465.0)  # mètres convertis en km
        self.assertAlmostEqual(option.duree_min, 273.0)  # secondes converties en minutes
        self.assertEqual(option.source["distance"], "OpenRouteService")
        self.assertEqual(option.source["duree"], "OpenRouteService")
        # Le CO2 vient du moteur : même résultat que le calcul direct.
        attendu = calculer_co2("voiture", 465.0)
        self.assertAlmostEqual(option.co2_kg, attendu.co2_kg)
        self.assertEqual(option.niveau, attendu.niveau)
        self.assertEqual(option.incertitude, attendu.incertitude_kg)
        self.assertIn("à valider", option.source["co2"])

    def test_la_cle_part_dans_l_entete_et_les_points_dans_le_bon_ordre(self):
        faux_appel = self.simuler_reponse(REPONSE_ITINERAIRE)
        ors.option_voiture(PARIS, LYON, "fausse-cle")

        arguments = faux_appel.call_args.kwargs
        self.assertEqual(arguments["entetes"], {"Authorization": "fausse-cle"})
        self.assertEqual(arguments["corps"], {"coordinates": [PARIS, LYON]})  # [longitude, latitude]

    def test_deuxieme_demande_servie_par_le_cache(self):
        faux_appel = self.simuler_reponse(REPONSE_ITINERAIRE)
        ors.option_voiture(PARIS, LYON, "fausse-cle")
        option = ors.option_voiture(PARIS, LYON, "fausse-cle")

        self.assertEqual(faux_appel.call_count, 1)  # la source n'est interrogée qu'une fois
        self.assertAlmostEqual(option.distance_km, 465.0)
        self.assertIn("cache du", option.source["distance"])

    def test_panne_sans_cache_repli_sur_le_bareme(self):
        self.simuler_panne()
        option = ors.option_voiture(PARIS, LYON, "fausse-cle")

        # Paris-Lyon fait environ 392 km à vol d'oiseau ; le barème ajoute un détour.
        self.assertGreater(option.distance_km, 392)
        self.assertLess(option.distance_km, 600)
        self.assertGreater(option.duree_min, 0)
        self.assertIn("Barème", option.source["distance"])
        self.assertIn("Barème", option.source["duree"])
        self.assertGreater(option.co2_kg, 0)

    def test_reponse_sans_itineraire_repli_sur_le_bareme(self):
        self.simuler_reponse({"error": {"code": 2010, "message": "point introuvable"}})
        option = ors.option_voiture(PARIS, LYON, "fausse-cle")
        self.assertIn("Barème", option.source["distance"])


class TestGeocoder(TestAdaptateur):
    def test_ville_trouvee(self):
        self.simuler_reponse(REPONSE_GEOCODAGE)
        lieu = ors.geocoder("Paris", "fausse-cle")

        self.assertAlmostEqual(lieu["lon"], 2.342865)
        self.assertAlmostEqual(lieu["lat"], 48.858705)
        self.assertEqual(lieu["nom"], "Paris, France")
        self.assertEqual(lieu["source"], "OpenRouteService")

    def test_ville_introuvable(self):
        self.simuler_reponse({"features": []})
        self.assertIsNone(ors.geocoder("Xyzzyville", "fausse-cle"))

    def test_panne(self):
        self.simuler_panne()
        self.assertIsNone(ors.geocoder("Paris", "fausse-cle"))


if __name__ == "__main__":
    unittest.main()
