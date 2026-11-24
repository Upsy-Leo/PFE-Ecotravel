"""Tests de l'adaptateur OpenRouteService, avec des réponses simulées."""

import unittest
from unittest import mock

from backend.adaptateurs import commun, ors
from backend.moteur_co2 import calculer_co2
from backend.tests.outils import LYON, PARIS, TestAdaptateur, ville_geocodee

# Extrait d'une vraie réponse d'itinéraire (Paris-Lyon, relevé du 2026-11-12, arrondi).
REPONSE_ITINERAIRE = {"routes": [{"summary": {"distance": 465000.0, "duration": 16380.0}}]}

# Vraie réponse pour « Brest » (relevé du 2026-11-24), réduite aux champs lus et aux
# quatre premiers résultats. La Biélorussie arrive avant la France, et la même ville
# de Bosnie apparaît deux fois.
REPONSE_BREST = {
    "features": [
        ville_geocodee("whosonfirst:locality:421195835", "Brest", "Brest", "Biélorussie", [23.6884, 52.0976]),
        ville_geocodee("whosonfirst:locality:101750111", "Brest", "Finistère", "France", [-4.4861, 48.3904]),
        ville_geocodee("whosonfirst:locality:1360197455", "Brest", "République serbe de Bosnie", "Bosnie-Herzégovine", [17.6, 44.8]),
        ville_geocodee("whosonfirst:locality:1343870903", "Brest", "République serbe de Bosnie", "Bosnie-Herzégovine", [17.7, 44.9]),
    ]
}

# Pour « Lyon », la source renvoie aussi des noms seulement voisins.
REPONSE_LYON = {
    "features": [
        ville_geocodee("whosonfirst:locality:101749431", "Lyon", "Rhône", "France", LYON),
        ville_geocodee("whosonfirst:locality:1344027601", "Lion", "Sabah", "Malaisie", [117.0, 5.5]),
        ville_geocodee("whosonfirst:locality:1326759389", "Lion", "Aube", "France", [4.0, 48.3]),
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


    def test_pas_de_route_pas_d_option(self):
        # Vraie forme du refus pour Paris-New York (relevé du 2026-11-13) : ce n'est pas une panne.
        refus = commun.ErreurSource("HTTP 404", corps='{"error":{"code":2009,"message":"Route could not be found"}}')
        faux_appel = self.simuler_sources(mock.Mock(side_effect=refus))
        self.assertIsNone(ors.option_voiture(PARIS, [-74.006, 40.7128], "fausse-cle"))
        # Le refus est mis en cache : la question n'est pas reposée.
        self.assertIsNone(ors.option_voiture(PARIS, [-74.006, 40.7128], "fausse-cle"))
        self.assertEqual(faux_appel.call_count, 1)


class TestChercherLieux(TestAdaptateur):
    def test_homonymes_tous_proposes(self):
        self.simuler_reponse(REPONSE_BREST)
        lieux = ors.chercher_lieux("Brest", "fausse-cle")

        # Trois villes : le doublon de Bosnie n'est proposé qu'une fois.
        self.assertEqual(
            [lieu["nom"] for lieu in lieux],
            ["Brest, Biélorussie", "Brest, Finistère, France", "Brest, République serbe de Bosnie, Bosnie-Herzégovine"],
        )
        france = lieux[1]
        self.assertEqual((france["ville"], france["region"], france["pays"]), ("Brest", "Finistère", "France"))
        self.assertAlmostEqual(france["lon"], -4.4861)
        self.assertAlmostEqual(france["lat"], 48.3904)
        self.assertEqual(france["source"], "OpenRouteService")

    def test_noms_voisins_ecartes(self):
        # « Lion » n'est pas un homonyme de « Lyon » : une seule ville, pas de question à poser.
        self.simuler_reponse(REPONSE_LYON)
        lieux = ors.chercher_lieux("Lyon", "fausse-cle")
        self.assertEqual([lieu["nom"] for lieu in lieux], ["Lyon, Rhône, France"])

    def test_requete_envoyee(self):
        faux_appel = self.simuler_reponse(REPONSE_LYON)
        ors.chercher_lieux("Lyon", "fausse-cle")
        url = faux_appel.call_args.args[0]
        self.assertIn("text=Lyon", url)
        self.assertIn("layers=locality", url)  # des villes seulement
        self.assertIn("size=10", url)  # plusieurs résultats, pour voir les homonymes
        self.assertIn("lang=fr", url)  # pays et régions en français

    def test_ville_introuvable(self):
        self.simuler_reponse({"features": []})
        self.assertEqual(ors.chercher_lieux("Xyzzyville", "fausse-cle"), [])

    def test_panne(self):
        self.simuler_panne()
        self.assertIsNone(ors.chercher_lieux("Paris", "fausse-cle"))


class TestSuggererLieux(TestAdaptateur):
    """Villes proposées pendant la frappe."""

    # Forme d'une vraie réponse pour « Bres » (relevé du 2026-11-24) : des villes qui
    # commencent par ces lettres, mais aussi une fiche qui n'est pas une ville, une
    # fiche sans pays et un doublon.
    REPONSE = {
        "features": [
            ville_geocodee("a", "Brest", "Brest", "Biélorussie", [23.6884, 52.0976]),
            ville_geocodee("b", "Brescia", None, "Italie", [10.2118, 45.5416]),
            ville_geocodee("c", "Brest", "Finistère", "France", [-4.4861, 48.3904]),
            {**ville_geocodee("d", "Bresse", "Ain", "France", [5.2, 46.2]), "properties": {
                "gid": "d", "name": "Bresse", "region": "Ain", "country": "France", "layer": "county"}},
            ville_geocodee("e", "Bressoneta", None, None, [1.0, 41.0]),
            ville_geocodee("f", "Brest", "Finistère", "France", [-4.49, 48.39]),
        ]
    }

    def test_propositions(self):
        self.simuler_reponse(self.REPONSE)
        lieux = ors.suggerer_lieux("Bres", "fausse-cle")

        # Villes seulement, avec un pays, sans doublon ; dans l'ordre de la source.
        self.assertEqual(
            [lieu["nom"] for lieu in lieux], ["Brest, Biélorussie", "Brescia, Italie", "Brest, Finistère, France"]
        )
        self.assertAlmostEqual(lieux[2]["lon"], -4.4861)  # la position sert ensuite à comparer
        self.assertAlmostEqual(lieux[2]["lat"], 48.3904)

    def test_requete_envoyee(self):
        faux_appel = self.simuler_reponse(self.REPONSE)
        ors.suggerer_lieux("Bres", "fausse-cle")
        url = faux_appel.call_args.args[0]
        self.assertIn("/geocode/autocomplete?", url)
        self.assertIn("text=Bres", url)
        self.assertIn("layers=locality", url)
        self.assertIn("lang=fr", url)

    def test_meme_debut_servi_par_le_cache(self):
        faux_appel = self.simuler_reponse(self.REPONSE)
        ors.suggerer_lieux("Bres", "fausse-cle")
        ors.suggerer_lieux("bres ", "fausse-cle")  # majuscules et espaces ne comptent pas
        self.assertEqual(faux_appel.call_count, 1)

    def test_panne_aucune_proposition_mais_pas_d_erreur(self):
        self.simuler_panne()
        self.assertEqual(ors.suggerer_lieux("Bres", "fausse-cle"), [])


if __name__ == "__main__":
    unittest.main()
