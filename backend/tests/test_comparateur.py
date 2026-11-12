"""Tests de la comparaison et de la route /comparer, avec toutes les sources simulées."""

import json
import unittest

from backend import serveur
from backend.adaptateurs import aeroports, commun
from backend.comparateur import ErreurDemande, comparer
from backend.tests.outils import LYON, PARIS, TestAdaptateur

CLES = {"ORS_API_Key": "fausse-cle", "TIM_API_Key": "fausse-cle", "TRANSITOUS_CONTACT": "contact@exemple.fr"}
DATE = "2099-01-15"  # loin dans le futur : le test ne « périme » pas
VILLES = {"Paris": PARIS, "Lyon": LYON}


def fausses_sources(url, corps=None, entetes=None):
    """Joue le rôle des quatre services, d'après l'adresse appelée."""
    if "geocode" in url:
        for ville, point in VILLES.items():
            if f"text={ville}" in url:
                return {"features": [{"geometry": {"coordinates": point}, "properties": {"label": f"{ville}, France"}}]}
        return {"features": []}
    if "directions" in url:
        return {"routes": [{"summary": {"distance": 465000.0, "duration": 16380.0}}]}
    if "transitous" in url:
        if "COACH" in url:
            return {"itineraries": [{"duration": 23280, "legs": [{"mode": "COACH"}]}]}
        return {"itineraries": [{"duration": 8400, "legs": [{"mode": "HIGHSPEED_RAIL"}]}]}
    if "travelimpactmodel" in url:
        trajet = corps["markets"][0]
        if trajet == {"origin": "CDG", "destination": "LYS"}:  # seul vol direct connu
            return {"typicalFlightEmissions": [{"market": trajet, "emissionsGramsPerPax": {"economy": 60000}}]}
        return {"typicalFlightEmissions": [{"market": trajet}]}
    raise commun.ErreurSource(f"Adresse inattendue dans le test : {url.split('?')[0]}")


class TestComparer(TestAdaptateur):
    def test_quatre_options(self):
        self.simuler_sources(fausses_sources)
        resultat = comparer("Paris", "Lyon", DATE, CLES)

        self.assertEqual([option["mode"] for option in resultat["options"]], ["avion", "train", "bus", "voiture"])
        self.assertEqual(resultat["sans_option"], {})
        self.assertEqual(resultat["depart"]["nom"], "Paris, France")
        self.assertEqual(resultat["date"], DATE)
        for option in resultat["options"]:
            with self.subTest(mode=option["mode"]):
                self.assertEqual(option["type_prix"], "indicatif")
                self.assertLess(option["prix_min"], option["prix_max"])
                self.assertIn(option["niveau"], "ABCDE")
                self.assertTrue(option["source"]["co2"])
        json.dumps(resultat)  # tout doit pouvoir partir en JSON

    def test_train_au_tarif_sncf(self):
        self.simuler_sources(fausses_sources)
        train = comparer("Paris", "Lyon", DATE, CLES)["options"][1]
        self.assertEqual((train["prix_min"], train["prix_max"]), (16.0, 115.0))
        self.assertIn("SNCF", train["source"]["prix"])

    def test_avion_garde_la_paire_d_aeroports_connue(self):
        # Orly est plus près de Paris, mais seul Roissy-Lyon est connu de Travel Impact Model.
        self.simuler_sources(fausses_sources)
        avion = comparer("Paris", "Lyon", DATE, CLES)["options"][0]
        self.assertIn("CDG", avion["source"]["distance"])
        self.assertIn("LYS", avion["source"]["distance"])
        self.assertAlmostEqual(avion["co2_kg"], 60.0)
        self.assertIn("Travel Impact Model", avion["source"]["co2"])

    def test_la_date_part_chez_transitous(self):
        faux_appel = self.simuler_sources(fausses_sources)
        comparer("Paris", "Lyon", DATE, CLES)
        adresses = [appel.args[0] for appel in faux_appel.call_args_list if "transitous" in appel.args[0]]
        self.assertEqual(len(adresses), 2)  # train et bus
        for adresse in adresses:
            self.assertIn("time=2099-01-15T05", adresse)

    def test_mode_sans_trajet_signale(self):
        def sans_train(url, corps=None, entetes=None):
            if "transitous" in url and "COACH" not in url:
                return {"itineraries": []}
            return fausses_sources(url, corps, entetes)

        self.simuler_sources(sans_train)
        resultat = comparer("Paris", "Lyon", DATE, CLES)
        self.assertEqual([option["mode"] for option in resultat["options"]], ["avion", "bus", "voiture"])
        self.assertIn("train", resultat["sans_option"])

    def test_sources_en_panne_sauf_geocodage_repli_sur_les_baremes(self):
        def panne(url, corps=None, entetes=None):
            if "geocode" in url:
                return fausses_sources(url)
            raise commun.ErreurSource("panne simulée")

        self.simuler_sources(panne)
        resultat = comparer("Paris", "Lyon", DATE, CLES)
        self.assertEqual(len(resultat["options"]), 4)  # le site ne plante pas : il dégrade la précision
        self.assertIn("Barème", resultat["options"][3]["source"]["distance"])
        self.assertIn("Repli", resultat["options"][0]["source"]["co2"])

    def test_demandes_refusees(self):
        self.simuler_sources(fausses_sources)
        cas = [
            (("Paris", "", DATE, CLES), 400),  # paramètre manquant
            (("Paris", "Lyon", "15/01/2099", CLES), 400),  # mauvais format de date
            (("Paris", "Lyon", "2020-01-01", CLES), 400),  # date passée
            (("Paris", "Paris", DATE, CLES), 400),  # même ville
            (("Paris", "Nullepart", DATE, CLES), 404),  # ville introuvable
            (("Paris", "Lyon", DATE, {}), 503),  # clé de géocodage absente
        ]
        for arguments, code in cas:
            with self.subTest(arguments=arguments[:3]):
                with self.assertRaises(ErreurDemande) as contexte:
                    comparer(*arguments)
                self.assertEqual(contexte.exception.code, code)


class TestRoute(TestAdaptateur):
    def test_reponse_correcte(self):
        self.simuler_sources(fausses_sources)
        code, reponse = serveur.repondre_a_comparer({"depart": "Paris", "arrivee": "Lyon", "date": DATE}, CLES)
        self.assertEqual(code, 200)
        self.assertEqual(len(reponse["options"]), 4)

    def test_parametre_manquant(self):
        code, reponse = serveur.repondre_a_comparer({"depart": "Paris"}, CLES)
        self.assertEqual(code, 400)
        self.assertIn("erreur", reponse)


class TestAeroports(unittest.TestCase):
    def test_paris(self):
        self.assertEqual([aeroport["iata"] for aeroport in aeroports.aeroports_proches(PARIS)], ["ORY", "CDG"])

    def test_plein_ocean(self):
        self.assertEqual(aeroports.aeroports_proches([-30.0, 40.0]), [])


if __name__ == "__main__":
    unittest.main()
