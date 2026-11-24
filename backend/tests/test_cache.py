"""Tests de la durée de vie du cache.

Règle : une vraie réponse est gardée 30 jours ; une réponse « rien trouvé »
(pas de trajet, pas de route, vol inconnu, ville inconnue) n'est gardée que 24 heures
et ne sert jamais de secours en cas de panne.
"""

import unittest

from backend.adaptateurs import commun, ors, tim, transitous
from backend.tests.outils import LYON, PARIS, TestAdaptateur

AUCUN_TRAJET = {"itineraries": []}
UN_TRAIN = {"itineraries": [{"duration": 8400, "legs": [{"mode": "HIGHSPEED_RAIL"}]}]}
CONTACT = "contact@exemple.fr"


class TestDureeDeVieDuCache(TestAdaptateur):
    def test_pas_de_trajet_garde_moins_d_un_jour(self):
        faux_appel = self.simuler_reponse(AUCUN_TRAJET)
        self.assertIsNone(transitous.option_train(PARIS, LYON, CONTACT, "2099-01-15"))
        # Dans la foulée : la question n'est pas reposée.
        self.assertIsNone(transitous.option_train(PARIS, LYON, CONTACT, "2099-01-15"))
        self.assertEqual(faux_appel.call_count, 1)

    def test_pas_de_trajet_redemande_apres_deux_jours(self):
        # Cas réel visé : des horaires pas encore publiés le premier jour, publiés ensuite.
        self.simuler_reponse(AUCUN_TRAJET)
        self.assertIsNone(transitous.option_train(PARIS, LYON, CONTACT, "2099-01-15"))
        self.vieillir_cache(jours=2)

        faux_appel = self.simuler_reponse(UN_TRAIN)
        option = transitous.option_train(PARIS, LYON, CONTACT, "2099-01-15")
        self.assertEqual(faux_appel.call_count, 1)  # la source est réinterrogée
        self.assertAlmostEqual(option.duree_min, 140.0)
        self.assertEqual(option.source["duree"], "Transitous")  # réponse fraîche, pas le cache

    def test_vraie_reponse_toujours_gardee_trente_jours(self):
        faux_appel = self.simuler_reponse(UN_TRAIN)
        transitous.option_train(PARIS, LYON, CONTACT, "2099-01-15")
        self.vieillir_cache(jours=2)
        option = transitous.option_train(PARIS, LYON, CONTACT, "2099-01-15")
        self.assertEqual(faux_appel.call_count, 1)  # servie par le cache
        self.assertIn("cache du", option.source["duree"])

    def test_vieille_absence_jamais_utilisee_en_secours(self):
        # « Pas de train » d'il y a deux jours, puis panne : on ne ressort pas la vieille
        # absence, on estime avec le barème et on le dit.
        self.simuler_reponse(AUCUN_TRAJET)
        transitous.option_train(PARIS, LYON, CONTACT, "2099-01-15")
        self.vieillir_cache(jours=2)

        self.simuler_panne()
        option = transitous.option_train(PARIS, LYON, CONTACT, "2099-01-15")
        self.assertIsNotNone(option)
        self.assertIn("Barème", option.source["duree"])

    def test_vieille_vraie_reponse_utilisee_en_secours(self):
        # À l'inverse, une vraie durée de plus de 30 jours reste meilleure qu'une estimation.
        self.simuler_reponse(UN_TRAIN)
        transitous.option_train(PARIS, LYON, CONTACT, "2099-01-15")
        self.vieillir_cache(jours=45)

        self.simuler_panne()
        option = transitous.option_train(PARIS, LYON, CONTACT, "2099-01-15")
        self.assertAlmostEqual(option.duree_min, 140.0)
        self.assertIn("cache du", option.source["duree"])

    def test_meme_regle_pour_les_autres_sources(self):
        # Pas de route (voiture), vol inconnu (avion), ville inconnue (géocodage).
        refus = commun.ErreurSource("HTTP 404", corps='{"error":{"code":2009}}')
        cas = {
            "voiture": (lambda: ors.option_voiture(PARIS, [-74.006, 40.7128], "fausse-cle"), refus),
            "avion": (lambda: tim.option_vol("CDG", "XXX", 1000, "fausse-cle"), {"typicalFlightEmissions": [{}]}),
            "ville": (lambda: ors.chercher_lieux("Xyzzyville", "fausse-cle"), {"features": []}),
        }
        for nom, (demander, reponse) in cas.items():
            with self.subTest(source=nom):
                faux_appel = self.simuler_sources(
                    lambda *arguments, **options: self._repondre(reponse)
                )
                demander()
                demander()
                self.assertEqual(faux_appel.call_count, 1)  # gardée quelques heures
                self.vieillir_cache(jours=2)
                demander()
                self.assertEqual(faux_appel.call_count, 2)  # redemandée après deux jours

    @staticmethod
    def _repondre(reponse):
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


if __name__ == "__main__":
    unittest.main()
