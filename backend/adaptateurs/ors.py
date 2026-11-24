"""Adaptateur OpenRouteService : géocodage, distance et durée en voiture.

    from backend.adaptateurs import ors

    lieux = ors.chercher_lieux("Brest", cle)    # Brest (Finistère), Brest (Biélorussie)…
    paris = ors.chercher_lieux("Paris", cle)[0] # {"lon": ..., "lat": ..., "nom": ..., …}
    lyon = ors.chercher_lieux("Lyon", cle)[0]
    option = ors.option_voiture([paris["lon"], paris["lat"]], [lyon["lon"], lyon["lat"]], cle)

Rappels : OpenRouteService attend les points dans l'ordre [longitude, latitude].
Plan gratuit : 2 000 itinéraires et 1 000 géocodages par jour, d'où le cache.
"""

import json
import urllib.parse

from backend.adaptateurs import commun

URL_GEOCODAGE = "https://api.openrouteservice.org/geocode/search"
URL_SUGGESTIONS = "https://api.openrouteservice.org/geocode/autocomplete"
URL_ITINERAIRE ="https://api.openrouteservice.org/v2/directions/driving-car"
# Codes d'erreur relevés le 2026-11-13 : 2004 = trajet de plus de 6 000 km (Paris-Bangkok),
# 2009 = aucune route entre les deux points (Paris-New York), 2010 = point loin de toute route.
CODES_SANS_ROUTE = (2004, 2009, 2010)
# Nombre de villes demandées au géocodage (10 est la valeur par défaut de la source).
NOMBRE_DE_RESULTATS = 10
BAREME = "Barème (à valider), OpenRouteService indisponible"


def _garder_les_homonymes(lieux):
    """Garde les villes qui portent le même nom que le premier résultat, sans doublon.

    La source renvoie aussi des noms seulement voisins (« Lion » pour « Lyon »,
    « Saint-Etienne-des-Landes » pour « Saint-Étienne ») : on les écarte.
    """
    gardes, deja_vus = [], set()
    for lieu in lieux:
        if lieu["ville"].casefold() != lieux[0]["ville"].casefold():
            continue
        signature = (lieu["region"], lieu["pays"])  # deux fiches identiques pour la même ville
        if signature not in deja_vus:
            deja_vus.add(signature)
            gardes.append(lieu)
    return gardes


def _nom_complet(lieu):
    """« Brest, Finistère, France ». La région est omise si elle manque ou répète la ville."""
    morceaux = [lieu["ville"]]
    if lieu["region"] and lieu["region"].casefold() != lieu["ville"].casefold():
        morceaux.append(lieu["region"])
    if lieu["pays"]:
        morceaux.append(lieu["pays"])
    return ", ".join(morceaux)


def chercher_lieux(texte, cle):
    """Cherche les villes qui portent ce nom. Plusieurs réponses = des homonymes.

    Renvoie une liste de lieux {"ville", "region", "pays", "nom", "lon", "lat", "source"} :
    - un seul lieu : pas d'ambiguïté ;
    - plusieurs : c'est à l'utilisateur de choisir (Brest en France ou en Biélorussie ?) ;
    - liste vide : aucune ville de ce nom ;
    - None : la source ne répond pas et rien n'est en cache. Il n'existe pas de
      barème pour deviner des coordonnées.

    Paramètres vérifiés dans la documentation de Pelias, le moteur de ce service
    (search.md et response.md, lus le 2026-11-24), et sur des réponses réelles.
    """

    def appel_direct():
        parametres = urllib.parse.urlencode({
            "text": texte,
            "size": NOMBRE_DE_RESULTATS,
            "layers": "locality",  # on cherche une ville, pas une rue ni un arrondissement
            "lang": "fr",  # noms de villes, de régions et de pays en français
        })
        reponse = commun.appeler_json(f"{URL_GEOCODAGE}?{parametres}", entetes={"Authorization": cle})
        return {"lieux": _garder_les_homonymes(_lire_lieux(reponse))}

    donnees, date_cache = commun.avec_repli(
        f"ors:lieux:{texte.strip().casefold()}", appel_direct, est_absence=lambda donnees: not donnees["lieux"]
    )
    if donnees is None:
        return None
    source = commun.nommer_source("OpenRouteService", date_cache)
    return [{**lieu, "nom": _nom_complet(lieu), "source": source} for lieu in donnees["lieux"]]


def suggerer_lieux(debut, cle):
    """Propose des villes dont le nom commence par « debut » (menu affiché pendant la frappe).

    Renvoie une liste de lieux {"nom", "ville", "region", "pays", "lon", "lat"}, vide si
    rien ne correspond ou si la source ne répond pas : sans propositions, l'utilisateur
    peut toujours taper le nom en entier.

    Méthode « autocomplete » du même service. Paramètres « text », « layers » et « size »
    lus dans la documentation de Pelias (autocomplete.md, 2026-11-24) ; « lang » n'y
    figure pas pour cette méthode, mais il fonctionne (vérifié sur des réponses réelles).
    """

    def appel_direct():
        parametres = urllib.parse.urlencode({
            "text": debut,
            "size": NOMBRE_DE_RESULTATS,
            "layers": "locality",
            "lang": "fr",
        })
        reponse = commun.appeler_json(f"{URL_SUGGESTIONS}?{parametres}", entetes={"Authorization": cle})
        return {"lieux": _lire_lieux(reponse)}

    # Le cache évite de redemander « Par », « Pari », « Paris » à chaque utilisateur.
    donnees, _ = commun.avec_repli(
        f"ors:suggestions:{debut.strip().casefold()}", appel_direct, est_absence=lambda donnees: not donnees["lieux"]
    )
    suggestions, deja_vus = [], set()
    for lieu in (donnees or {"lieux": []})["lieux"]:
        nom = _nom_complet(lieu)
        if lieu["pays"] and nom not in deja_vus:  # on écarte les fiches sans pays et les doublons
            deja_vus.add(nom)
            suggestions.append({**lieu, "nom": nom})
    return suggestions


def _lire_lieux(reponse):
    """Extrait les villes d'une réponse de géocodage (recherche ou autocomplétion)."""
    try:
        lieux = []
        for resultat in reponse["features"]:
            proprietes = resultat["properties"]
            if proprietes.get("layer", "locality") != "locality":
                continue  # l'autocomplétion renvoie parfois des arrondissements ou des cantons
            lon, lat = resultat["geometry"]["coordinates"]
            lieux.append({
                "ville": proprietes["name"],
                "region": proprietes.get("region"),
                "pays": proprietes.get("country"),
                "lon": lon,
                "lat": lat,
            })
        return lieux
    except (KeyError, TypeError, ValueError) as erreur:
        raise commun.ErreurSource(f"Réponse de géocodage inattendue : {reponse}") from erreur


def _est_un_refus_sans_route(erreur):
    """Vrai si OpenRouteService a répondu « pas d'itinéraire » (ce n'est pas une panne)."""
    try:
        return json.loads(erreur.corps)["error"]["code"] in CODES_SANS_ROUTE
    except (ValueError, KeyError, TypeError):
        return False


def option_voiture(depart, arrivee, cle):
    """Renvoie l'Option « voiture » entre deux points [longitude, latitude].

    Renvoie None si OpenRouteService répond qu'il n'y a pas d'itinéraire routier
    (océan à traverser, ou trajet de plus de 6 000 km). En cas de panne, en
    revanche, la distance et la durée sont estimées avec le barème.
    """

    def appel_direct():
        try:
            reponse = commun.appeler_json(
                URL_ITINERAIRE, corps={"coordinates": [depart, arrivee]}, entetes={"Authorization": cle}
            )
        except commun.ErreurSource as erreur:
            if _est_un_refus_sans_route(erreur):
                return {"route": False}  # mis en cache, mais pour peu de temps (voir commun.avec_repli)
            raise
        try:
            resume = reponse["routes"][0]["summary"]
            # La source répond en mètres et en secondes.
            return {"route": True, "distance_km": resume["distance"] / 1000, "duree_min": resume["duration"] / 60}
        except (KeyError, IndexError, TypeError) as erreur:
            raise commun.ErreurSource(f"Réponse d'itinéraire inattendue : {reponse}") from erreur

    cle_cache = f"ors:voiture:{commun.cle_coordonnees(depart)}:{commun.cle_coordonnees(arrivee)}"
    # « get » : les réponses mises en cache avant l'ajout de « route » n'ont pas ce champ.
    donnees, date_cache = commun.avec_repli(
        cle_cache, appel_direct, est_absence=lambda donnees: not donnees.get("route", True)
    )

    if donnees is not None and not donnees.get("route", True):
        return None

    if donnees is None:
        # Ni source ni cache : on estime avec le barème, et on le dit.
        distance_km = commun.estimer_distance_km("voiture", depart, arrivee)
        duree_min = commun.estimer_duree_min("voiture", distance_km)
        return commun.construire_option("voiture", distance_km, duree_min, BAREME, BAREME)

    source = commun.nommer_source("OpenRouteService", date_cache)
    return commun.construire_option("voiture", donnees["distance_km"], donnees["duree_min"], source, source)
