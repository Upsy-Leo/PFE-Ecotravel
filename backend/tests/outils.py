"""Base commune aux tests des adaptateurs.

Ces tests n'appellent jamais Internet : la réponse de la source est simulée,
et le cache est écrit dans un dossier temporaire, effacé après chaque test.
"""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from backend.adaptateurs import commun

PARIS = [2.3522, 48.8566]
LYON = [4.8357, 45.7640]


def ville_geocodee(identifiant, ville, region, pays, point):
    """Fabrique un résultat de géocodage, réduit aux champs lus par l'adaptateur."""
    return {
        "geometry": {"coordinates": point},
        "properties": {"gid": identifiant, "name": ville, "region": region, "country": pays},
    }


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

    def vieillir_cache(self, jours):
        """Fait comme si tout le contenu du cache avait été enregistré il y a « jours » jours."""
        ancienne_date = (datetime.now(timezone.utc) - timedelta(days=jours)).isoformat()
        cache = json.loads(commun.FICHIER_CACHE.read_text(encoding="utf-8"))
        for entree in cache.values():
            entree["date"] = ancienne_date
        commun.FICHIER_CACHE.write_text(json.dumps(cache), encoding="utf-8")

    def simuler_sources(self, fonction):
        """Chaque appel est traité par « fonction(url, corps=None, entetes=None) »."""
        return self._remplacer_appel(mock.Mock(side_effect=fonction))

    def _remplacer_appel(self, faux_appel):
        remplacement = mock.patch.object(commun, "appeler_json", faux_appel)
        remplacement.start()
        self.addCleanup(remplacement.stop)
        return faux_appel
