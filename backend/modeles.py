"""Modèles de données : Voyage, Segment, Option (format commun).

À écrire. Rappel de ce qui est décidé (voir CLAUDE.md) :

- Voyage  : liste ordonnée d'étapes, 6 segments au maximum.
- Segment : trajet entre deux étapes consécutives.
- Option  : un mode possible pour un segment, au format commun
            (mode, distance_km, duree_min, prix_min, prix_max, type_prix,
            co2_kg, intensite_g_pkm, niveau, incertitude, source).

La partie CO2 d'une option est déjà calculée par moteur_co2.calculer_co2().
"""
