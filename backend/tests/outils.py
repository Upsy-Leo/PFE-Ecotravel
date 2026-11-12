"""Base commune aux tests des adaptateurs.

Ces tests n'appellent jamais Internet : la réponse de la source est simulée,
et le cache est écrit dans un dossier temporaire, effacé après chaque test.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.adaptateurs import commun

PARIS = [2.3522, 48.8566]
LYON = [4.8357, 45.7640]


class TestAdaptateur(unittest.TestCase):
    def setUp(self):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        remplacement = mock.patch.object(commun, "FICHIER_CACHE", Path(dossier.name) / "reponses.json")
        remplacement.start()
        self.addCleanup(remplacement.stop)

    def simuler_reponse(self, reponse):
        """La source répond « reponse » à tous les appels. Renvoie le faux appel, pour l'inspecter."""
        return self._remplacer_appel(mock.Mock(return_value=reponse))

    def simuler_panne(self):
        """La source ne répond plus."""
        return self._remplacer_appel(mock.Mock(side_effect=commun.ErreurSource("panne simulée")))

    def _remplacer_appel(self, faux_appel):
        remplacement = mock.patch.object(commun, "appeler_json", faux_appel)
        remplacement.start()
        self.addCleanup(remplacement.stop)
        return faux_appel
