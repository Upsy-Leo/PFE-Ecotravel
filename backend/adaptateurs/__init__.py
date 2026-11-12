"""Adaptateurs : un fichier par source de données (tim.py, ors.py, transitous.py…).

Chaque adaptateur interroge une source et ramène sa réponse au format commun.
Tous suivent le même repli : source en direct, sinon cache, sinon barème
(voir commun.py).
"""
