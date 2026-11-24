"""Tests du script scripts/actualiser_facteurs.py, avec une API Impact CO2 simulée.

Rien n'est écrit dans le vrai fichier des facteurs : on teste la fonction qui
fabrique le nouveau contenu, pas l'écriture.
"""

import importlib.util
import json
import unittest
from pathlib import Path

from backend.adaptateurs import commun
from backend.moteur_co2 import FICHIER_FACTEURS, calculer_co2, releve_des_facteurs
from backend.tests.outils import TestAdaptateur

# Le dossier scripts/ n'est pas un paquet Python : on charge le fichier par son chemin.
CHEMIN = Path(__file__).parent.parent.parent / "scripts" / "actualiser_facteurs.py"
spec = importlib.util.spec_from_file_location("actualiser_facteurs", CHEMIN)
outil = importlib.util.module_from_spec(spec)
spec.loader.exec_module(outil)

FACTEURS = json.loads(FICHIER_FACTEURS.read_text(encoding="utf-8"))

# Facteurs de l'avion selon la distance : (avec traînées, sans traînées). Relevé du 2026-11-24.
AVION = {1000: ("Avion trajet court", 224.2, 123.2), 2000: ("Avion trajet moyen", 184.3, 101.3),
         5000: ("Avion trajet moyen à long", 166.5, 91.5), 5001: ("Avion trajet long", 177.6, 97.6)}


def fausse_api(km, sans_trainees):
    """Ce que répond l'API pour nos quatre modes : {identifiant: (nom, g par km)}."""
    nom, avec, sans = AVION[km]
    return {1: (nom, sans if sans_trainees else avec), 2: ("TGV", 2.3), 6: ("Autocar thermique", 33.14), 4: ("Voiture thermique", 110.56)}


class TestActualiser(unittest.TestCase):
    def test_une_distance_par_tranche_de_l_avion(self):
        self.assertEqual(outil.distances_de_mesure(FACTEURS), [1000, 2000, 5000, 5001])

    def test_facteurs_date_et_source(self):
        nouveaux, _ = outil.actualiser(FACTEURS, fausse_api, False, "2099-01-15")

        avion = nouveaux["modes"]["avion"]["tranches"]
        self.assertEqual([tranche["facteur_g_pkm"] for tranche in avion], [224.2, 184.3, 166.5, 177.6])
        # La part des traînées est la différence entre les deux réponses de l'API.
        self.assertEqual([tranche["dont_trainees_g_pkm"] for tranche in avion], [101.0, 83.0, 75.0, 80.0])
        self.assertEqual(nouveaux["modes"]["train"]["tranches"][0]["facteur_g_pkm"], 2.3)
        self.assertEqual(nouveaux["modes"]["bus"]["tranches"][0]["facteur_g_pkm"], 33.14)
        self.assertEqual(nouveaux["modes"]["voiture"]["tranches"][0]["facteur_g_pkm"], 110.56)
        # La date de récupération est écrite dans le relevé et dans la source de chaque mode.
        self.assertEqual(nouveaux["releve"]["date"], "2099-01-15")
        self.assertEqual(nouveaux["releve"]["source"], "API Impact CO2 (ADEME)")
        for mode, infos in nouveaux["modes"].items():
            with self.subTest(mode=mode):
                self.assertEqual(infos["source"], "Impact CO2 (ADEME), récupéré le 2099-01-15")

    def test_ce_que_l_equipe_a_ecrit_n_est_pas_touche(self):
        nouveaux, _ = outil.actualiser(FACTEURS, fausse_api, False, "2099-01-15")
        for mode, infos in FACTEURS["modes"].items():
            with self.subTest(mode=mode):
                for champ in ("min_g_pkm", "max_g_pkm", "a_verifier", "statut", "id_impact_co2"):
                    self.assertEqual(nouveaux["modes"][mode][champ], infos[champ])
                self.assertEqual(nouveaux["modes"][mode]["statut"], "à valider")  # récupéré ne veut pas dire validé
        self.assertEqual(FACTEURS["modes"]["avion"]["tranches"][0]["jusqu_a_km"], 1000)  # l'original n'est pas modifié

    def test_les_changements_sont_listes(self):
        def api_modifiee(km, sans_trainees):
            reponse = fausse_api(km, sans_trainees)
            reponse[2] = ("TGV", 2.9)
            return reponse

        _, changements = outil.actualiser(FACTEURS, api_modifiee, False, "2099-01-15")
        self.assertEqual(len(changements), 1)
        self.assertIn("train", changements[0])
        self.assertIn("2.9", changements[0])

    def test_mode_manquant_rien_n_est_fabrique(self):
        def api_incomplete(km, sans_trainees):
            reponse = fausse_api(km, sans_trainees)
            del reponse[6]  # l'autocar a disparu de la réponse
            return reponse

        with self.assertRaises(commun.ErreurSource) as contexte:
            outil.actualiser(FACTEURS, api_incomplete, False, "2099-01-15")
        self.assertIn("bus", str(contexte.exception))

    def test_le_reglage_construction_est_note(self):
        sans, _ = outil.actualiser(FACTEURS, fausse_api, False, "2099-01-15")
        avec, _ = outil.actualiser(FACTEURS, fausse_api, True, "2099-01-15")
        self.assertTrue(sans["releve"]["reglages"].startswith("Sans la construction"))
        self.assertTrue(avec["releve"]["reglages"].startswith("Avec la construction"))


class TestInterroger(TestAdaptateur):
    # Forme d'une vraie réponse à 1 000 km pour les identifiants 1, 2, 6 et 4 (« value » en kg).
    REPONSE = {"data": [
        {"id": 1, "name": "Avion trajet court", "value": 224.2},
        {"id": 2, "name": "TGV", "value": 2.3},
        {"id": 4, "name": "Voiture thermique", "value": 110.56},
        {"id": 6, "name": "Autocar thermique", "value": 33.14},
    ]}

    def test_requete_et_conversion(self):
        faux_appel = self.simuler_reponse(self.REPONSE)
        mesure = outil.interroger(1000, False, True, [1, 2, 6, 4], "fausse-cle")

        url = faux_appel.call_args.args[0]
        for morceau in ("km=1000", "transports=1%2C2%2C6%2C4", "includeConstruction=0", "ignoreRadiativeForcing=1"):
            self.assertIn(morceau, url)
        self.assertEqual(faux_appel.call_args.kwargs["entetes"], {"Authorization": "Bearer fausse-cle"})
        self.assertNotIn("fausse-cle", url)  # la clé part dans l'en-tête, jamais dans l'adresse
        # « value » est en kg pour 1 000 km : on retrouve des grammes par km.
        self.assertEqual(mesure[1], ("Avion trajet court", 224.2))
        self.assertEqual(mesure[4], ("Voiture thermique", 110.56))

    def test_reponse_inattendue(self):
        self.simuler_reponse({"erreur": "quota dépassé"})
        with self.assertRaises(commun.ErreurSource):
            outil.interroger(1000, False, False, [1], "fausse-cle")


class TestFichierLocal(unittest.TestCase):
    """Le site lit ce fichier : il doit porter la date de récupération et les identifiants."""

    def test_date_de_recuperation(self):
        releve = releve_des_facteurs()
        self.assertRegex(releve["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn("Impact CO2", releve["source"])

    def test_la_date_est_dans_la_source_de_chaque_calcul(self):
        date = releve_des_facteurs()["date"]
        for mode in ("avion", "train", "bus", "voiture"):
            with self.subTest(mode=mode):
                self.assertIn(f"récupéré le {date}", calculer_co2(mode, 430).source)

    def test_chaque_mode_a_son_identifiant_impact_co2(self):
        identifiants = {mode: infos["id_impact_co2"] for mode, infos in FACTEURS["modes"].items()}
        self.assertEqual(identifiants, {"avion": 1, "train": 2, "bus": 6, "voiture": 4})


if __name__ == "__main__":
    unittest.main()
