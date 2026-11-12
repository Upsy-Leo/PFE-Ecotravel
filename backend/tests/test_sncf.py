"""Tests du chargement des tarifs SNCF."""

import tempfile
import unittest
from pathlib import Path

from backend.adaptateurs import commun, sncf

# Petit fichier d'essai, au même format que le vrai.
EXTRAIT = """transporteur;gare_origine;gare_origine_code_uic;gare_destination;gare_destination_code_uic;classe;profil_tarifaire;prix_minimum;prix_maximum
OUIGO;PARIS GARE DE LYON;87686006;LYON PART DIEU;87723197;2;Tarif Normal;16.0;99.0
TGV INOUI;LYON PERRACHE;87722025;PARIS GARE DE LYON;87686006;2;Tarif Normal;25.5;115.0
TGV INOUI;LYON PERRACHE;87722025;PARIS GARE DE LYON;87686006;1;Tarif Normal;29.5;178.0
TGV INOUI;LYON PERRACHE;87722025;PARIS GARE DE LYON;87686006;2;Tarif Avantage;17.5;80.0
TGV INOUI;ST ETIENNE CHATEAUCREUX;87726000;PARIS GARE DE LYON;87686006;2;Tarif Normal;30.0;120.0
"""


class TestPrixTrain(unittest.TestCase):
    def setUp(self):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.fichier = Path(dossier.name) / "tarifs.csv"
        self.fichier.write_text(EXTRAIT, encoding="utf-8")

    def test_fourchette_tous_transporteurs_2de_classe_plein_tarif(self):
        # Moins cher des minimums (OUIGO, 16 €), plus cher des maximums (INOUI, 115 €).
        # La 1re classe (178 €) et le tarif Avantage (80 €) sont ignorés.
        self.assertEqual(sncf.prix_train("Paris", "Lyon", self.fichier), (16.0, 115.0))

    def test_meme_prix_dans_les_deux_sens(self):
        self.assertEqual(sncf.prix_train("Lyon", "Paris", self.fichier), (16.0, 115.0))

    def test_accents_tirets_et_saint(self):
        self.assertEqual(sncf.prix_train("Saint-Étienne", "paris", self.fichier), (30.0, 120.0))

    def test_gare_de_lyon_n_est_pas_a_lyon(self):
        # Saint-Étienne -> « PARIS GARE DE LYON » ne doit pas compter comme un trajet vers Lyon.
        self.assertIsNone(sncf.prix_train("Saint-Étienne", "Lyon", self.fichier))

    def test_trajet_absent(self):
        self.assertIsNone(sncf.prix_train("Paris", "Bangkok", self.fichier))
        self.assertIsNone(sncf.prix_train("", "Lyon", self.fichier))


class TestFichierEmbarque(unittest.TestCase):
    """Vérifie le vrai fichier backend/donnees/tarifs_sncf.csv (version du 2026-03-17)."""

    def test_paris_lyon(self):
        prix_min, prix_max = sncf.prix_train("Paris", "Lyon")
        self.assertEqual((prix_min, prix_max), (16.0, 115.0))

    def test_appliquer_tarif_remplace_le_prix_au_bareme(self):
        option = commun.construire_option("train", 433, 140, "essai", "essai")
        option = sncf.appliquer_tarif(option, "Paris", "Lyon")

        self.assertEqual((option.prix_min, option.prix_max), (16.0, 115.0))
        self.assertEqual(option.type_prix, "indicatif")  # une grille tarifaire n'est pas un prix de billet
        self.assertIn("SNCF", option.source["prix"])
        self.assertEqual(option.source["duree"], "essai")  # le reste de l'option ne change pas

    def test_trajet_inconnu_garde_le_bareme(self):
        option = commun.construire_option("train", 1000, 600, "essai", "essai")
        self.assertIs(sncf.appliquer_tarif(option, "Paris", "Bangkok"), option)
        self.assertIn("Barème", option.source["prix"])

    def test_ne_touche_pas_aux_autres_modes(self):
        option = commun.construire_option("bus", 472, 380, "essai", "essai")
        self.assertIs(sncf.appliquer_tarif(option, "Paris", "Lyon"), option)
        self.assertIsNone(sncf.appliquer_tarif(None, "Paris", "Lyon"))


if __name__ == "__main__":
    unittest.main()
