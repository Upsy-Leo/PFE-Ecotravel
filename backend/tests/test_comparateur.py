"""Tests de la comparaison et de la route /comparer, avec toutes les sources simulées."""

import json
import unittest

from backend import serveur
from backend.adaptateurs import aeroports, commun
from backend.comparateur import ErreurDemande, comparer
from backend.tests.outils import LYON, PARIS, TestAdaptateur, ville_geocodee

CLES = {"ORS_API_Key": "fausse-cle", "TIM_API_Key": "fausse-cle", "TRANSITOUS_CONTACT": "contact@exemple.fr"}
DATE = "2099-01-15"  # loin dans le futur : le test ne « périme » pas
POINT_BREST_FRANCE = "-4.4861,48.3904"  # « longitude,latitude », comme le site l'envoie
# Ce que le géocodage renvoie pour chaque nom. « Brest » a deux homonymes.
VILLES = {
    "Paris": [ville_geocodee("paris", "Paris", "Paris", "France", PARIS)],
    "Lyon": [ville_geocodee("lyon", "Lyon", "Rhône", "France", LYON)],
    "Brest": [
        ville_geocodee("whosonfirst:locality:421195835", "Brest", "Brest", "Biélorussie", [23.6884, 52.0976]),
        ville_geocodee("whosonfirst:locality:101750111", "Brest", "Finistère", "France", [-4.4861, 48.3904]),
    ],
}


def fausses_sources(url, corps=None, entetes=None):
    """Joue le rôle des quatre services, d'après l'adresse appelée."""
    if "geocode" in url:
        for ville, resultats in VILLES.items():
            if f"text={ville}" in url:
                return {"features": resultats}
        return {"features": []}
    if "directions" in url:
        return {"routes": [{"summary": {"distance": 465000.0, "duration": 16380.0}}]}
    if "transitous" in url:
        if "COACH" in url:
            return {"itineraries": [{"duration": 23280, "legs": [{"mode": "COACH"}]}]}
        return {"itineraries": [{"duration": 8400, "legs": [{"mode": "HIGHSPEED_RAIL"}]}]}
    if "travelimpactmodel" in url:
        trajet = corps["markets"][0]
        if trajet == {"origin": "ORY", "destination": "LYS"}:
            return {"typicalFlightEmissions": [{"market": trajet, "emissionsGramsPerPax": {"economy": 60000}}]}
        return {"typicalFlightEmissions": [{"market": trajet}]}
    raise commun.ErreurSource(f"Adresse inattendue dans le test : {url.split('?')[0]}")


class TestComparer(TestAdaptateur):
    def test_quatre_options(self):
        self.simuler_sources(fausses_sources)
        resultat = comparer("Paris", "Lyon", DATE, CLES)

        self.assertEqual([option["mode"] for option in resultat["options"]], ["avion", "train", "bus", "voiture"])
        self.assertEqual(resultat["sans_option"], {})
        self.assertNotIn("a_preciser", resultat)  # une seule ville de chaque nom : pas de question
        self.assertEqual(resultat["depart"]["nom"], "Paris, France")
        self.assertEqual(resultat["arrivee"]["nom"], "Lyon, Rhône, France")
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

    def test_avion_calcule_avec_ademe_valeur_tim_indicative(self):
        self.simuler_sources(fausses_sources)
        avion = comparer("Paris", "Lyon", DATE, CLES)["options"][0]

        # Aéroports les plus proches de chaque ville : Orly et Lyon-Saint-Exupéry (environ 392 km).
        self.assertIn("ORY", avion["source"]["distance"])
        self.assertIn("LYS", avion["source"]["distance"])
        # CO2 et niveau par le calcul ADEME (224,2 g/km sur un vol court : niveau E).
        self.assertAlmostEqual(avion["co2_kg"], avion["distance_km"] * 224.2 / 1000)
        self.assertEqual(avion["niveau"], "E")
        self.assertIn("ADEME", avion["source"]["co2"])
        # La valeur du Travel Impact Model accompagne l'option, sans servir au classement.
        self.assertAlmostEqual(avion["co2_indicatif"]["co2_kg"], 60.0)
        self.assertIn("Travel Impact Model", avion["co2_indicatif"]["source"])
        self.assertIn("Vol direct non vérifié", avion["remarques"][0])

    def test_l_avion_est_le_mode_le_plus_emetteur(self):
        # Avec la méthode homogène, l'avion ne passe plus sous la voiture.
        self.simuler_sources(fausses_sources)
        co2 = {option["mode"]: option["co2_kg"] for option in comparer("Paris", "Lyon", DATE, CLES)["options"]}
        self.assertEqual(max(co2, key=co2.get), "avion")
        self.assertEqual(sorted(co2, key=co2.get), ["train", "bus", "voiture", "avion"])

    def test_un_seul_appel_au_travel_impact_model(self):
        faux_appel = self.simuler_sources(fausses_sources)
        comparer("Paris", "Lyon", DATE, CLES)
        appels = [appel for appel in faux_appel.call_args_list if "travelimpactmodel" in appel.args[0]]
        self.assertEqual(len(appels), 1)

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
        # L'avion ne dépend plus de sa source : calcul ADEME, simplement sans valeur indicative.
        self.assertIn("ADEME", resultat["options"][0]["source"]["co2"])
        self.assertIsNone(resultat["options"][0]["co2_indicatif"])

    def test_geocodage_en_panne(self):
        def panne(url, corps=None, entetes=None):
            raise commun.ErreurSource("panne simulée")

        self.simuler_sources(panne)
        with self.assertRaises(ErreurDemande) as contexte:
            comparer("Paris", "Lyon", DATE, CLES)
        self.assertEqual(contexte.exception.code, 503)  # service indisponible, pas « ville introuvable »

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


class TestHomonymes(TestAdaptateur):
    def test_plusieurs_villes_on_demande_au_lieu_de_choisir(self):
        faux_appel = self.simuler_sources(fausses_sources)
        resultat = comparer("Brest", "Lyon", DATE, CLES)

        self.assertNotIn("options", resultat)  # rien n'est comparé tant que le lieu n'est pas choisi
        self.assertEqual(list(resultat["a_preciser"]), ["depart"])  # Lyon, lui, est sans ambiguïté
        self.assertEqual(
            [lieu["nom"] for lieu in resultat["a_preciser"]["depart"]],
            ["Brest, Biélorussie", "Brest, Finistère, France"],
        )
        # Aucun quota dépensé en itinéraires ou en horaires avant le choix.
        self.assertTrue(all("geocode" in appel.args[0] for appel in faux_appel.call_args_list))
        json.dumps(resultat)

    def test_ville_choisie_dans_une_liste(self):
        # Le site renvoie le nom complet de la ville choisie et sa position.
        faux_appel = self.simuler_sources(fausses_sources)
        resultat = comparer("Brest, Finistère, France", "Lyon", DATE, CLES, point_depart=POINT_BREST_FRANCE)

        self.assertEqual(resultat["depart"]["nom"], "Brest, Finistère, France")
        self.assertEqual(resultat["depart"]["ville"], "Brest")
        self.assertAlmostEqual(resultat["depart"]["lon"], -4.4861)
        self.assertAlmostEqual(resultat["depart"]["lat"], 48.3904)
        self.assertTrue(resultat["options"])
        # Brest n'est plus cherché par son nom : un seul géocodage, celui de Lyon.
        geocodages = [appel.args[0] for appel in faux_appel.call_args_list if "geocode" in appel.args[0]]
        self.assertEqual(len(geocodages), 1)
        self.assertIn("text=Lyon", geocodages[0])

    def test_position_illisible_on_cherche_par_le_nom(self):
        # Un lien abîmé ne doit pas faire planter : la position est ignorée, la question reposée.
        self.simuler_sources(fausses_sources)
        for point in ("n'importe quoi", "12", "500,48", "-4.48,95", ""):
            with self.subTest(point=point):
                resultat = comparer("Brest", "Lyon", DATE, CLES, point_depart=point)
                self.assertIn("depart", resultat["a_preciser"])

    def test_les_deux_villes_a_preciser(self):
        self.simuler_sources(fausses_sources)
        resultat = comparer("Brest", "Brest", DATE, CLES)
        self.assertEqual(sorted(resultat["a_preciser"]), ["arrivee", "depart"])

    def test_la_route_transmet_le_choix(self):
        self.simuler_sources(fausses_sources)
        demande = {"depart": "Brest", "arrivee": "Lyon", "date": DATE}
        code, reponse = serveur.repondre_a_comparer(demande, CLES)
        self.assertEqual(code, 200)
        self.assertIn("a_preciser", reponse)

        demande = {**demande, "depart": "Brest, Finistère, France", "depart_point": POINT_BREST_FRANCE}
        code, reponse = serveur.repondre_a_comparer(demande, CLES)
        self.assertEqual(code, 200)
        self.assertEqual(reponse["depart"]["nom"], "Brest, Finistère, France")
        self.assertEqual(len(reponse["options"]), 4)


class TestRouteLieux(TestAdaptateur):
    REPONSE = {"features": [ville_geocodee("x", "Brest", "Finistère", "France", [-4.4861, 48.3904])]}

    def test_propositions(self):
        self.simuler_reponse(self.REPONSE)
        code, reponse = serveur.repondre_a_lieux({"texte": "Bres"}, CLES)
        self.assertEqual(code, 200)
        self.assertEqual([lieu["nom"] for lieu in reponse["lieux"]], ["Brest, Finistère, France"])
        json.dumps(reponse)

    def test_moins_de_trois_lettres_la_source_n_est_pas_interrogee(self):
        faux_appel = self.simuler_reponse(self.REPONSE)
        for texte in ("", "B", "Br", "  Br  "):
            with self.subTest(texte=texte):
                self.assertEqual(serveur.repondre_a_lieux({"texte": texte}, CLES), (200, {"lieux": []}))
        faux_appel.assert_not_called()  # le quota de géocodage est préservé

    def test_panne_liste_vide(self):
        self.simuler_panne()
        self.assertEqual(serveur.repondre_a_lieux({"texte": "Bres"}, CLES), (200, {"lieux": []}))


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
