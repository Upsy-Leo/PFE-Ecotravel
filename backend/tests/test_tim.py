"""Tests de l'option « avion » et de l'adaptateur Travel Impact Model, avec des réponses simulées."""

import unittest

from backend.adaptateurs import tim
from backend.moteur_co2 import calculer_co2, charger_methode
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


class TestMethodeAdeme(TestAdaptateur):
    """Méthode retenue par l'équipe : le calcul ADEME sert à la comparaison."""

    def test_la_methode_configuree_est_ademe(self):
        self.assertEqual(charger_methode()["co2_avion"]["methode"], "ademe")

    def test_co2_niveau_et_fourchette_viennent_du_calcul_ademe(self):
        self.simuler_reponse(REPONSE)
        option = tim.option_vol("cdg", "bkk", 9450, "fausse-cle")  # méthode du fichier de configuration

        attendu = calculer_co2("avion", 9450)
        self.assertEqual(option.mode, "avion")
        self.assertAlmostEqual(option.co2_kg, attendu.co2_kg)  # environ 1 678 kg
        self.assertAlmostEqual(option.intensite_g_pkm, 177.6)
        self.assertEqual(option.niveau, "D")  # et non C, le niveau qu'aurait donné la valeur indicative
        self.assertEqual(option.incertitude, attendu.incertitude_kg)
        self.assertIn("ADEME", option.source["co2"])
        self.assertIn("à valider", option.source["co2"])
        self.assertNotIn("Repli", option.source["co2"])  # ce n'est pas un repli : c'est la méthode voulue

    def test_valeur_du_travel_impact_model_jointe_a_titre_indicatif(self):
        self.simuler_reponse(REPONSE)
        option = tim.option_vol("CDG", "BKK", 9450, "fausse-cle")

        indicatif = option.co2_indicatif
        self.assertAlmostEqual(indicatif["co2_kg"], 667.196)  # grammes convertis en kg, classe économique
        self.assertAlmostEqual(indicatif["intensite_g_pkm"], 667196 / 9450)  # environ 71 g/passager·km
        self.assertIn("Travel Impact Model", indicatif["source"])
        # Elle n'a pas déteint sur la valeur retenue.
        self.assertGreater(option.co2_kg, 2 * indicatif["co2_kg"])

    def test_sans_reponse_de_la_source_pas_de_valeur_indicative(self):
        for nom, simuler in (("panne", self.simuler_panne), ("trajet inconnu", lambda: self.simuler_reponse(REPONSE_TRAJET_INCONNU))):
            with self.subTest(cas=nom):
                simuler()
                option = tim.option_vol("CDG", "XXX", 1000, "fausse-cle")
                self.assertIsNone(option.co2_indicatif)
                self.assertAlmostEqual(option.co2_kg, calculer_co2("avion", 1000).co2_kg)  # le calcul ne dépend pas de la source

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
        self.assertAlmostEqual(option.co2_indicatif["co2_kg"], 667.196)
        self.assertIn("cache du", option.co2_indicatif["source"])


class TestMethodeTim(TestAdaptateur):
    """L'autre réglage possible : le choix est configurable, pas codé en dur."""

    def test_co2_et_niveau_viennent_du_travel_impact_model(self):
        self.simuler_reponse(REPONSE)
        option = tim.option_vol("CDG", "BKK", 9450, "fausse-cle", methode="tim")

        self.assertAlmostEqual(option.co2_kg, 667.196)
        self.assertEqual(option.niveau, "C")
        self.assertIsNone(option.incertitude)  # la source ne fournit pas de fourchette
        self.assertIn("Travel Impact Model", option.source["co2"])
        # Le calcul ADEME devient la valeur indicative.
        self.assertAlmostEqual(option.co2_indicatif["co2_kg"], calculer_co2("avion", 9450).co2_kg)
        self.assertIn("ADEME", option.co2_indicatif["source"])

    def test_repli_sur_ademe_si_la_source_ne_donne_rien(self):
        for nom, simuler in (("panne", self.simuler_panne), ("trajet inconnu", lambda: self.simuler_reponse(REPONSE_TRAJET_INCONNU))):
            with self.subTest(cas=nom):
                simuler()
                option = tim.option_vol("CDG", "XXX", 1000, "fausse-cle", methode="tim")
                self.assertAlmostEqual(option.co2_kg, calculer_co2("avion", 1000).co2_kg)
                self.assertIn("Repli", option.source["co2"])  # la précision est dégradée, et c'est dit
                self.assertIsNone(option.co2_indicatif)

    def test_methode_inconnue_refusee(self):
        with self.assertRaises(ValueError):
            tim.option_vol("CDG", "BKK", 9450, "fausse-cle", methode="au hasard")


class TestDureePrixEtVolDirect(TestAdaptateur):
    def test_duree_avec_trajets_vers_et_depuis_l_aeroport(self):
        self.simuler_reponse(REPONSE)
        option = tim.option_vol("CDG", "BKK", 9450, "fausse-cle")
        # 2 × 45 min de trajet ville-aéroport + 150 min d'aéroport + 40 min + 9 450 km à 880 km/h.
        self.assertAlmostEqual(option.duree_min, 924.3, places=1)
        self.assertIn("Barème", option.source["duree"])
        self.assertIn("vers et depuis l'aéroport", option.source["duree"])

    def test_prix_indicatif_au_bareme(self):
        self.simuler_reponse(REPONSE)
        option = tim.option_vol("CDG", "BKK", 9450, "fausse-cle")
        self.assertEqual((option.prix_min, option.prix_max), (284, 945))  # 9 450 km × 0,03 à 0,10 €
        self.assertEqual(option.type_prix, "indicatif")
        self.assertIn("à valider", option.source["prix"])

    def test_vol_direct_signale_comme_non_verifie(self):
        # Que la source réponde ou non, rien ne prouve qu'un vol direct existe : c'est dit sur l'option.
        for nom, simuler in (("réponse", lambda: self.simuler_reponse(REPONSE)), ("panne", self.simuler_panne)):
            with self.subTest(cas=nom):
                simuler()
                option = tim.option_vol("LYS", "BKK", 9300, "fausse-cle")
                self.assertEqual(len(option.remarques), 1)
                self.assertIn("Vol direct non vérifié", option.remarques[0])
                self.assertIn("escale", option.remarques[0])

    def test_distance_nulle_refusee(self):
        with self.assertRaises(ValueError):
            tim.option_vol("CDG", "BKK", 0, "fausse-cle")


if __name__ == "__main__":
    unittest.main()
