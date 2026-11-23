# Suite du plan — du prototype au MVP livrable

Ce fichier complète `CLAUDE.md`. Les étapes 1 à 7 sont faites (socle, moteur CO₂, validation des sources, adaptateurs, barèmes, route `/comparer`, interface). Les étapes 8 à 15 mènent au MVP décrit dans le portfolio.

## Règles pour toute la suite

- **Une étape à la fois.** Ne pas commencer la suivante avant que les tests de l'étape en cours passent et que l'équipe ait validé.
- À la fin de chaque étape : lancer tous les tests, résumer ce qui a changé, donner les commandes pour vérifier à la main, puis proposer un message de commit.
- **Ne jamais inventer une valeur** (facteur, seuil, prix, budget carbone). Si une valeur manque, la mettre en configuration, la marquer « à valider » et le signaler.
- Avant de coder un appel d'API, **vérifier le nom des paramètres dans la documentation officielle**. Ne pas se fier à la mémoire.
- Ne jamais afficher ni committer le contenu de `.env`. Clés disponibles : `TIM_API_Key`, `ORS_API_Key`, `IMPACT_API_Key`.
- Expliquer simplement chaque choix : l'équipe doit pouvoir présenter ce code en soutenance.

---

## Étape 8 — État des lieux

**Objectif.** Savoir exactement où en est le code avant d'ajouter quoi que ce soit.

**À faire.**
- Lire `CLAUDE.md`, le portfolio et l'ensemble du code.
- Lancer tous les tests.
- Produire `ETAT_DES_LIEUX.md` : ce qui fonctionne, ce qui repose encore sur des données fictives ou sur le barème, les écarts avec le portfolio (Must have du MoSCoW, règles de fiabilité), les valeurs marquées « à valider », les points fragiles.
- Ne rien modifier d'autre.

**Terminé quand.** Le fichier existe et l'équipe l'a relu.

---

## Étape 9 — Brancher l'API Impact CO2

**Objectif.** Remplacer les facteurs d'émission provisoires par ceux de l'ADEME.

**À faire.**
- Lire la documentation de l'API Impact CO2 (endpoint transport, paramètres, authentification, identifiants des modes).
- Écrire `adaptateurs/impact_co2.py` : pour une distance et un mode, renvoyer les émissions et la source.
- Repérer dans la documentation les options qui changent le résultat (prise en compte de la construction des véhicules, traînées de condensation pour l'avion, nombre de passagers pour la voiture) et **lister ces options à l'équipe sans choisir à sa place**.
- Enregistrer les facteurs obtenus dans le fichier JSON local, avec la date de récupération : c'est le repli quand l'API ne répond pas.
- Tests avec réponses simulées + un test réel sur 100 km pour chaque mode.

**Terminé quand.** Les quatre modes ont un facteur dont la source est « Impact CO2 (ADEME) » et la date de récupération est affichée.

---

## Étape 10 — Trancher la méthode pour l'avion

**Objectif.** Une comparaison avion / train honnête et documentée.

**Contexte.** Travel Impact Model donne environ 616 kg pour Paris–Bangkok ; le calcul par facteur ADEME donne nettement plus. Mélanger les deux méthodes avantage l'avion.

**À faire.**
- Calculer, pour les trajets de référence aériens, les deux valeurs côte à côte (Travel Impact Model et ADEME, avec et sans traînées si l'API le permet) et présenter le tableau à l'équipe.
- **Attendre la décision de l'équipe**, puis l'appliquer. Proposition par défaut : ADEME pour tous les modes dans la comparaison (méthode homogène), valeur Travel Impact Model affichée à titre indicatif avec sa source.
- Rendre le choix configurable, pas codé en dur.
- Mettre à jour la règle de contrôle sur les trajets de référence pour qu'elle corresponde à la méthode retenue.

**Terminé quand.** La méthode retenue est écrite dans `CLAUDE.md` et dans la page « Méthode et limites ».

---

## Étape 11 — Repères de lecture du CO₂

**Objectif.** Le cœur du projet : rendre le chiffre compréhensible (fonction F4).

**À faire.**
- Échelle A à E : seuils en configuration, chaque niveau avec sa lettre et un libellé en mots, jamais la couleur seule.
- Part d'un budget carbone annuel : la valeur de référence et sa source sont **à fournir par l'équipe** ; prévoir le paramètre et demander la valeur.
- Fourchette d'incertitude affichée à côté de chaque valeur de CO₂.
- Phrase de comparaison explicite entre options, en langage simple (par exemple « émet 12 fois moins que l'avion sur ce trajet »), calculée, jamais écrite à la main.
- Chaque valeur affiche sa source et, pour le prix, la mention « réel » ou « indicatif ».

**Terminé quand.** Une personne extérieure au projet classe correctement les quatre options de la moins à la plus émettrice en regardant l'écran.

---

## Étape 12 — Itinéraire en plusieurs segments

**Objectif.** Le différenciateur du projet (Must have du portfolio).

**À faire.**
- Interface : ajouter et retirer des étapes (plafond : 6 segments), choisir un mode par segment.
- Backend : la route accepte une liste d'étapes et renvoie les options de chaque segment.
- Totaux cumulés du prix, de la durée et du CO₂, mis à jour quand on change un mode.
- Raccourcis « le moins cher », « le plus rapide », « le moins émetteur » : meilleure option de chaque segment.
- Temps d'attente entre deux segments : valeur par défaut en configuration, marquée « à valider ».
- Mettre en cache les appels pour respecter les quotas (OpenRouteService : 2 000 itinéraires et 1 000 géocodages par jour).

**Terminé quand.** Paris → Barcelone → Madrid fonctionne de bout en bout, avec les totaux justes vérifiés à la main.

---

## Étape 13 — Robustesse et trajets de référence

**Objectif.** Le site ne plante pas et les calculs sont contrôlés.

**À faire.**
- Jeu d'une dizaine de trajets de référence en test automatique (courts, moyens, longs ; avec et sans train possible).
- Vérifier le repli à trois niveaux en simulant une panne de chaque API : le site doit répondre et dire qu'il a dégradé la précision.
- Cas limites : ville introuvable, départ égal à l'arrivée, trajet sans route (île, autre continent), mode indisponible, quota dépassé. Messages d'erreur clairs pour l'utilisateur.
- Tri des résultats par prix, durée ou CO₂ si le temps le permet (Should have).

**Terminé quand.** Tous les tests passent, y compris avec les API coupées.

---

## Étape 14 — Accessibilité et page « Méthode et limites »

**Objectif.** Tenir l'engagement WCAG 2.2 niveau AA et la transparence.

**À faire.**
- Audit de l'interface contre le tableau 1.3.5 du portfolio : contrastes, étiquettes de formulaire, textes alternatifs, navigation complète au clavier, ordre de tabulation, focus visible, responsive.
- Corriger, puis lister ce qui reste non conforme.
- Page « Méthode et limites » complète : sources, formules, méthode retenue pour l'avion, ce qui est exclu (traînées de condensation selon la décision, hébergement), nature indicative des prix, date des données.

**Terminé quand.** Une recherche complète se fait sans souris, et un outil d'audit automatique (par exemple Lighthouse ou axe) ne signale plus d'erreur.

---

## Étape 15 — Mise en ligne

**Objectif.** Une adresse publique pour les tests utilisateurs et la soutenance.

**À faire.**
- Proposer deux ou trois hébergements gratuits adaptés à un backend Python, avec leurs limites, et **laisser l'équipe choisir**.
- Clés d'API en variables d'environnement chez l'hébergeur, jamais dans le dépôt.
- `README.md` : installation, lancement en local, tests, déploiement.
- Vérifier le site en ligne sur ordinateur et sur téléphone.
- Documenter ce que l'hébergeur enregistre dans ses journaux (section vie privée du portfolio).

**Terminé quand.** Quelqu'un hors de l'équipe fait une recherche depuis son téléphone.

---

## Décisions qui restent à l'équipe

Le code ne peut pas les prendre à votre place ; il faut les trancher au fil des étapes.

| Décision | Étape concernée |
|---|---|
| Options de calcul ADEME (construction des véhicules, traînées, nombre de passagers en voiture) | 9 |
| Méthode de référence pour l'avion | 10 |
| Seuils de l'échelle A à E | 11 |
| Valeur et source du budget carbone annuel | 11 |
| Temps d'attente par défaut entre deux segments | 12 |
| Hébergeur | 15 |

## Après l'étape 15

- Tests utilisateurs auprès de la cible (critère de réussite de F4 : le voyageur classe correctement les options).
- Mise à jour du portfolio : sources réellement utilisées, résultats des tests, méthode retenue.
