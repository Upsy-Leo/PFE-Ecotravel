"""Tests de l'adaptateur Transitous, avec des réponses simulées."""

import unittest

from backend.adaptateurs import transitous
from backend.tests.outils import LYON, PARIS, TestAdaptateur


def itineraire(duree_s, modes):
    """Fabrique un itinéraire réduit aux champs lus par l'adaptateur."""
    return {"duration": duree_s, "legs": [{"mode": mode} for mode in modes]}


# Forme d'une vraie réponse Paris-Lyon (relevé du 2026-11-12), réduite à l'essentiel.
REPONSE_TRAIN = {
    "itineraries": [
        itineraire(9000, ["WALK", "SUBWAY", "HIGHSPEED_RAIL", "BUS", "WALK"]),
        itineraire(8400, ["WALK", "SUBWAY", "HIGHSPEED_RAIL", "SUBWAY", "WALK"]),  # le plus rapide : 140 min
        itineraire(3000, ["WALK", "BUS", "WALK"]),  # sans train : à ignorer
    ]
}
REPONSE_BUS = {
    "itineraries": [
        itineraire(23280, ["WALK", "SUBWAY", "COACH", "SUBWAY", "WALK"]),  # 388 min
        itineraire(24180, ["WALK", "SUBWAY", "COACH", "WALK"]),
    ]
}


class TestTransitous(TestAdaptateur):
    def test_train_garde_le_trajet_le_plus_rapide(self):
        self.simuler_reponse(REPONSE_TRAIN)
        option = transitous.option_train(PARIS, LYON, "contact@exemple.fr")

        self.assertEqual(option.mode, "train")
        self.assertAlmostEqual(option.duree_min, 140.0)  # secondes converties en minutes
        self.assertEqual(option.source["duree"], "Transitous")
        # La distance ne vient pas de Transitous : elle est estimée, et c'est dit.
        self.assertGreater(option.distance_km, 392)
        self.assertIn("Barème", option.source["distance"])
        self.assertEqual(option.niveau, "A")

    def test_bus(self):
        self.simuler_reponse(REPONSE_BUS)
        option = transitous.option_bus(PARIS, LYON, "contact@exemple.fr")

        self.assertEqual(option.mode, "bus")
        self.assertAlmostEqual(option.duree_min, 388.0)
        self.assertEqual(option.niveau, "B")

    def test_requete_envoyee(self):
        faux_appel = self.simuler_reponse(REPONSE_TRAIN)
        transitous.option_train(PARIS, LYON, "contact@exemple.fr")

        url = faux_appel.call_args.args[0]
        # Transitous attend « latitude,longitude » (la virgule devient %2C dans une URL).
        self.assertIn("fromPlace=48.8566%2C2.3522", url)
        self.assertIn("toPlace=45.764%2C4.8357", url)
        # Le contact part dans l'en-tête User-Agent, comme Transitous le demande.
        self.assertIn("contact@exemple.fr", faux_appel.call_args.kwargs["entetes"]["User-Agent"])

    def test_aucun_itineraire_pas_d_option(self):
        self.simuler_reponse({"itineraries": []})
        self.assertIsNone(transitous.option_train(PARIS, LYON, "contact@exemple.fr"))

    def test_deuxieme_demande_servie_par_le_cache(self):
        faux_appel = self.simuler_reponse(REPONSE_TRAIN)
        transitous.option_train(PARIS, LYON, "contact@exemple.fr")
        option = transitous.option_train(PARIS, LYON, "contact@exemple.fr")

        self.assertEqual(faux_appel.call_count, 1)
        self.assertAlmostEqual(option.duree_min, 140.0)
        self.assertIn("cache du", option.source["duree"])

    def test_panne_sans_cache_repli_sur_le_bareme(self):
        self.simuler_panne()
        option = transitous.option_bus(PARIS, LYON, "contact@exemple.fr")

        self.assertGreater(option.duree_min, 0)
        self.assertIn("Barème", option.source["duree"])
        self.assertIn("indisponible", option.source["duree"])

    def test_sans_contact_la_source_n_est_pas_interrogee(self):
        faux_appel = self.simuler_reponse(REPONSE_TRAIN)
        option = transitous.option_train(PARIS, LYON, None)

        faux_appel.assert_not_called()
        self.assertIn("Barème", option.source["duree"])


if __name__ == "__main__":
    unittest.main()
