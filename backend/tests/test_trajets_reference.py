"""Contrôle des trajets de référence en avion (donnees/trajets_reference.json).

Sans Internet : on vérifie le calcul ADEME, qui est la méthode retenue pour la
comparaison. La valeur du Travel Impact Model, elle, se contrôle en réel avec
« python scripts/valider_sources.py ».

Les comparaisons se font avec une tolérance, jamais sur une valeur exacte.
"""

import json
import unittest

from backend.adaptateurs import aeroports, commun
from backend.moteur_co2 import DOSSIER_DONNEES, calculer_co2, charger_methode

REFERENCE = json.loads((DOSSIER_DONNEES / "trajets_reference.json").read_text(encoding="utf-8"))
TOLERANCE = REFERENCE["tolerances"]["ademe"]
POINTS = {aeroport["iata"]: aeroport["point"] for aeroport in aeroports.charger_aeroports()}


class TestTrajetsDeReference(unittest.TestCase):
    def test_la_methode_active_est_celle_des_valeurs_de_reference(self):
        # Les valeurs attendues valent pour : calcul ADEME, traînées incluses.
        methode = charger_methode()
        self.assertEqual(methode["co2_avion"]["methode"], "ademe")
        self.assertTrue(
            methode["options_ademe"]["trainees_de_condensation"],
            "Réglage des traînées modifié : recalculer « co2_ademe_kg » dans trajets_reference.json.",
        )

    def test_distance_entre_aeroports(self):
        for trajet in REFERENCE["trajets"]:
            with self.subTest(trajet=trajet["nom"]):
                distance = commun.distance_vol_oiseau_km(POINTS[trajet["origine"]], POINTS[trajet["destination"]])
                self.assertAlmostEqual(distance, trajet["distance_km"], delta=trajet["distance_km"] * 0.01)

    def test_co2_ademe_dans_la_tolerance(self):
        for trajet in REFERENCE["trajets"]:
            with self.subTest(trajet=trajet["nom"]):
                distance = commun.distance_vol_oiseau_km(POINTS[trajet["origine"]], POINTS[trajet["destination"]])
                resultat = calculer_co2("avion", distance)
                attendu = trajet["co2_ademe_kg"]
                self.assertAlmostEqual(resultat.co2_kg, attendu, delta=attendu * TOLERANCE)
                self.assertEqual(resultat.niveau, trajet["niveau_attendu"])

    def test_repere_google_flights_dans_la_tolerance_du_travel_impact_model(self):
        # 616 kg (portfolio) contre la valeur relevée : l'écart doit rester sous la tolérance.
        bangkok = next(trajet for trajet in REFERENCE["trajets"] if trajet["nom"] == "Paris-Bangkok")
        ecart = abs(616 - bangkok["co2_tim_kg"]) / bangkok["co2_tim_kg"]
        self.assertLess(ecart, REFERENCE["tolerances"]["tim"])

    def test_l_avion_emet_plus_que_la_voiture_a_distance_egale(self):
        # But de la méthode homogène : l'avion ne ressort plus sous la voiture (une personne à bord).
        for distance in (400, 800, 1500, 3000, 9000):
            with self.subTest(distance=distance):
                self.assertGreater(calculer_co2("avion", distance).co2_kg, calculer_co2("voiture", distance).co2_kg)


if __name__ == "__main__":
    unittest.main()
