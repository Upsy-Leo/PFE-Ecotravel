"""Tests du moteur CO2.

Pour les lancer, depuis la racine du projet :

    python -m unittest -v

Les tests de calcul utilisent des facteurs fictifs et ronds, écrits ci-dessous.
Ils restent donc valables quand l'équipe corrige les vrais facteurs.
Les tests de la dernière classe vérifient que les vrais fichiers sont bien formés.
"""

import unittest

from backend.moteur_co2 import (
    calculer_co2,
    charger_facteurs,
    charger_niveaux,
    trouver_niveau,
)

# Facteurs fictifs : des chiffres ronds pour vérifier les calculs de tête.
FACTEURS_TEST = {
    "train": {
        "tranches": [{"jusqu_a_km": None, "facteur_g_pkm": 5, "libelle": "Train de test"}],
        "min_g_pkm": 2,
        "max_g_pkm": 30,
        "source": "Source de test",
        "statut": "à valider",
    },
    "avion": {
        "tranches": [
            {"jusqu_a_km": 1000, "facteur_g_pkm": 250, "libelle": "Vol court de test"},
            {"jusqu_a_km": None, "facteur_g_pkm": 150, "libelle": "Vol long de test"},
        ],
        "min_g_pkm": 100,
        "max_g_pkm": 300,
        "source": "Source de test",
        "statut": "validé",
    },
}

NIVEAUX_TEST = [
    {"lettre": "A", "en_dessous_de": 10},
    {"lettre": "B", "en_dessous_de": 50},
    {"lettre": "C", "en_dessous_de": 120},
    {"lettre": "D", "en_dessous_de": 200},
    {"lettre": "E", "en_dessous_de": None},
]


def calculer(mode, distance_km):
    """Raccourci : calcule avec les facteurs et niveaux fictifs."""
    return calculer_co2(mode, distance_km, facteurs=FACTEURS_TEST, niveaux=NIVEAUX_TEST)


class TestCalcul(unittest.TestCase):
    def test_distance_fois_facteur(self):
        # 800 km × 5 g = 4 000 g = 4 kg
        resultat = calculer("train", 800)
        self.assertAlmostEqual(resultat.co2_kg, 4.0)
        self.assertEqual(resultat.intensite_g_pkm, 5)
        self.assertEqual(resultat.mode, "train")
        self.assertEqual(resultat.distance_km, 800)

    def test_incertitude_encadre_la_valeur(self):
        # 800 km × 2 g = 1,6 kg ; 800 km × 30 g = 24 kg
        resultat = calculer("train", 800)
        co2_min, co2_max = resultat.incertitude_kg
        self.assertAlmostEqual(co2_min, 1.6)
        self.assertAlmostEqual(co2_max, 24.0)
        self.assertLessEqual(co2_min, resultat.co2_kg)
        self.assertLessEqual(resultat.co2_kg, co2_max)

    def test_distance_nulle(self):
        resultat = calculer("train", 0)
        self.assertEqual(resultat.co2_kg, 0)
        self.assertEqual(resultat.niveau, "A")

    def test_source_et_statut_suivent_le_fichier(self):
        self.assertEqual(calculer("train", 100).source, "Source de test : Train de test")
        self.assertEqual(calculer("train", 100).statut, "à valider")
        self.assertEqual(calculer("avion", 100).statut, "validé")

    def test_avion_change_de_facteur_selon_la_distance(self):
        court = calculer("avion", 1000)  # pile sur la limite : encore un vol court
        long = calculer("avion", 1001)
        self.assertEqual(court.intensite_g_pkm, 250)
        self.assertAlmostEqual(court.co2_kg, 250.0)
        self.assertEqual(court.niveau, "E")
        self.assertEqual(long.intensite_g_pkm, 150)
        self.assertAlmostEqual(long.co2_kg, 150.15)
        self.assertEqual(long.niveau, "D")
        self.assertIn("Vol long de test", long.source)


class TestErreurs(unittest.TestCase):
    def test_mode_inconnu(self):
        with self.assertRaises(ValueError) as erreur:
            calculer("fusee", 100)
        # Le message doit aider : il cite le mode refusé et les modes possibles.
        self.assertIn("fusee", str(erreur.exception))
        self.assertIn("train", str(erreur.exception))

    def test_distance_negative(self):
        with self.assertRaises(ValueError):
            calculer("train", -1)


class TestNiveaux(unittest.TestCase):
    def test_chaque_niveau(self):
        cas = [(0, "A"), (9.9, "A"), (30, "B"), (80, "C"), (150, "D"), (250, "E")]
        for intensite, lettre in cas:
            with self.subTest(intensite=intensite):
                self.assertEqual(trouver_niveau(intensite, NIVEAUX_TEST), lettre)

    def test_valeur_pile_sur_un_seuil(self):
        # Une valeur pile sur un seuil passe au niveau le plus émetteur.
        cas = [(10, "B"), (50, "C"), (120, "D"), (200, "E")]
        for intensite, lettre in cas:
            with self.subTest(intensite=intensite):
                self.assertEqual(trouver_niveau(intensite, NIVEAUX_TEST), lettre)

    def test_liste_sans_dernier_niveau(self):
        niveaux_incomplets = [{"lettre": "A", "en_dessous_de": 10}]
        with self.assertRaises(ValueError):
            trouver_niveau(500, niveaux_incomplets)


class TestFichiersReels(unittest.TestCase):
    """Vérifie que les vrais fichiers de « donnees/ » sont bien formés."""

    def setUp(self):
        self.facteurs = charger_facteurs()
        self.niveaux = charger_niveaux()

    def test_les_quatre_modes_sont_presents(self):
        self.assertEqual(set(self.facteurs), {"avion", "train", "bus", "voiture"})

    def test_chaque_facteur_est_coherent(self):
        for mode, infos in self.facteurs.items():
            with self.subTest(mode=mode):
                self.assertIn(infos["statut"], {"à valider", "validé"})
                self.assertTrue(infos["source"])
                self.assertGreater(infos["min_g_pkm"], 0)
                for tranche in infos["tranches"]:
                    facteur = tranche["facteur_g_pkm"]
                    self.assertLessEqual(infos["min_g_pkm"], facteur)
                    self.assertLessEqual(facteur, infos["max_g_pkm"])

    def test_les_tranches_sont_dans_l_ordre(self):
        for mode, infos in self.facteurs.items():
            with self.subTest(mode=mode):
                limites = [tranche["jusqu_a_km"] for tranche in infos["tranches"]]
                # La dernière tranche n'a pas de limite, les autres sont croissantes.
                self.assertIsNone(limites[-1])
                self.assertEqual(limites[:-1], sorted(limites[:-1]))

    def test_les_niveaux_vont_de_a_a_e(self):
        lettres = [niveau["lettre"] for niveau in self.niveaux]
        seuils = [niveau["en_dessous_de"] for niveau in self.niveaux]
        self.assertEqual(lettres, ["A", "B", "C", "D", "E"])
        self.assertIsNone(seuils[-1])
        self.assertEqual(seuils[:-1], sorted(seuils[:-1]))

    def test_calcul_avec_les_vrais_fichiers(self):
        # Aucun chiffre attendu ici (les facteurs sont provisoires) : on vérifie
        # seulement que le moteur répond pour chaque mode, à courte et longue distance.
        for mode in self.facteurs:
            for distance_km in (300, 9450):
                with self.subTest(mode=mode, distance_km=distance_km):
                    resultat = calculer_co2(mode, distance_km)
                    co2_min, co2_max = resultat.incertitude_kg
                    self.assertGreater(resultat.co2_kg, 0)
                    self.assertLessEqual(co2_min, resultat.co2_kg)
                    self.assertLessEqual(resultat.co2_kg, co2_max)
                    self.assertIn(resultat.niveau, "ABCDE")


if __name__ == "__main__":
    unittest.main()
