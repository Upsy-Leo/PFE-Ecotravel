# État des lieux — étape 8

Photographie du code au **23 novembre 2026**, avant de commencer l'étape 9. Rien n'a été modifié pour l'écrire, à part ce fichier.

## En bref

- **Le parcours de base fonctionne de bout en bout** : on saisit départ, arrivée et date, le site affiche jusqu'à quatre modes avec prix, durée, kg de CO₂e, niveau A–E et source de chaque valeur. Les 64 tests passent.
- **Trois « Must have » du portfolio manquent** : l'itinéraire en plusieurs segments, la part d'un budget carbone annuel, et la conformité WCAG 2.2 AA qui n'a pas encore été mesurée.
- **Beaucoup de valeurs affichées sont des estimations.** Aucun prix n'est réel. La durée du train et du car vient aujourd'hui du barème, parce que Transitous n'est jamais interrogé (contact absent du `.env`).
- **Tous les facteurs, seuils et barèmes sont encore « à valider ».**
- **Trois défauts visibles par un utilisateur** : « Brest » est situé en Biélorussie, un train et un car sont proposés pour Paris–Bangkok, et l'avion sort mieux classé que la voiture sur les longues distances à cause du mélange des deux méthodes de calcul.

## Comment cet état des lieux a été fait

| Vérification | Résultat |
|---|---|
| Relecture de `CLAUDE.md`, `PLAN_SUITE.md`, du portfolio (fonctions F1–F5, MoSCoW 2.1, accessibilité 1.3.5, règles de fiabilité, vie privée) et de tout le code | Fait |
| `python -m pytest backend/tests -q` | 64 tests passent (et 56 sous-tests) |
| `python scripts/valider_sources.py` | Travel Impact Model et OpenRouteService répondent |
| Quatre comparaisons réelles pour le 8 décembre 2026 : Paris–Lyon, Paris–Barcelone, Paris–Bangkok, Brest–Nice | Résultats repris plus bas |

Non refait pour cet état des lieux : l'essai de l'interface dans un navigateur (dernier essai le 13 novembre, sur captures d'écran).

## 1. Ce qui fonctionne

| Élément | Fichiers | État |
|---|---|---|
| Moteur CO₂ : distance × facteur, niveau A–E, fourchette | `backend/moteur_co2.py` | Fonctionne, 15 tests |
| Émissions des vols (Travel Impact Model, méthode `computeTypicalFlightEmissions`) | `backend/adaptateurs/tim.py` | Fonctionne en réel |
| Géocodage, distance et durée en voiture (OpenRouteService) | `backend/adaptateurs/ors.py` | Fonctionne en réel |
| Durée en train et en car (Transitous) | `backend/adaptateurs/transitous.py` | Codé et testé le 12 novembre, **mais inactif** : voir § 2 |
| Prix des trains en France (fichier SNCF, 36 349 tarifs) | `backend/adaptateurs/sncf.py` | Fonctionne |
| Choix des aéroports (fichier OurAirports, 3 245 aéroports) | `backend/adaptateurs/aeroports.py` | Fonctionne |
| Barèmes de prix au km, de distance et de durée ; durée d'un vol | `backend/donnees/bareme.json`, `bareme_prix.json` | Fonctionnent, valeurs provisoires |
| Cache et repli (source → cache → barème) | `backend/adaptateurs/commun.py` | Fonctionne |
| Route `/comparer` et serveur local | `backend/comparateur.py`, `backend/serveur.py` | Fonctionne |
| Interface : formulaire, cartes de comparaison, sources dépliables | `frontend/index.html`, `app.js`, `style.css` | Fonctionne |
| Page « Méthode et limites », tableaux lus dans la configuration (`/reference`) | `frontend/methode.html`, `methode.js` | Fonctionne |
| Script de contrôle des sources | `scripts/valider_sources.py` | Fonctionne, mais ne teste que deux sources |

L'interface n'affiche **aucune donnée fictive** : tout ce qui est à l'écran vient du backend.

## 2. D'où vient chaque valeur aujourd'hui

Résultat réel du 23 novembre pour Paris–Lyon :

| Mode | Distance | Durée | Prix | CO₂ | Niveau |
|---|---|---|---|---|---|
| Train | 433 km | 2 h 20 | 16 – 115 € | 1,0 kg | A |
| Car | 472 km | 6 h 45 | 9 – 38 € | 15,6 kg | B |
| Voiture | 465 km | 4 h 32 | 46 – 130 € | 51,4 kg | C |
| Avion (Orly–Lyon) | 392 km | 3 h 37 | 24 – 118 € | 62,5 kg | D |

Provenance de chaque valeur. **Source** = donnée d'une API ou d'un fichier officiel. **Barème** = estimation maison, « à valider ».

| Mode | Distance | Durée | Prix | CO₂ |
|---|---|---|---|---|
| Train | Barème (vol d'oiseau × 1,1) | **Barème** tant que Transitous est inactif | Source SNCF en France pour les trajets du fichier, barème sinon | Facteur ADEME × distance estimée |
| Car | Barème (vol d'oiseau × 1,2) | **Barème** tant que Transitous est inactif | Barème | Facteur ADEME × distance estimée |
| Voiture | Source (OpenRouteService) | Source (OpenRouteService) | Barème | Facteur ADEME × distance réelle |
| Avion | Vol d'oiseau entre deux aéroports | Barème (toujours) | Barème (toujours) | Source (Travel Impact Model), repli ADEME |

Ce qu'il faut retenir :

- **Aucun prix n'est « réel ».** Le champ `type_prix` vaut toujours `indicatif`. Même le tarif SNCF est une fourchette de grille tarifaire, pas le prix d'un billet.
- **Transitous n'est jamais interrogé.** L'adaptateur exige un contact dans le `.env` (`TRANSITOUS_CONTACT`), qui n'y est pas. La durée du train et du car est donc partout « distance estimée ÷ vitesse moyenne ». Sur Paris–Lyon, le barème donne 6 h 45 en car, contre 6 h 16 à 6 h 28 mesurées avec Transitous le 12 novembre.
- **La distance du train et du car est toujours estimée**, même quand Transitous répond : il ne la fournit pas. Leur CO₂ en dépend directement.
- **La durée et le prix de l'avion sont toujours estimés**, quelle que soit la réponse des sources.
- **La clé `IMPACT_API_Key` est maintenant dans le `.env` mais aucun code ne l'utilise** (étape 9). Les facteurs viennent d'un relevé manuel du 10 novembre.

## 3. Écarts avec le portfolio

### Must have (MoSCoW, partie 2.1)

| Exigence | État | Détail |
|---|---|---|
| Saisie d'un trajet (origine, destination, date) et plusieurs options (train, avion, voiture, bus) | Fait | La date ne sert qu'au train et au car, et seulement quand Transitous est actif |
| Prix, durée et CO₂ côte à côte | Fait | Une carte par mode ; côte à côte sur écran large, l'une sous l'autre sur téléphone |
| CO₂ calculé avec des facteurs reconnus (ADEME, Travel Impact Model) | Fait en partie | Facteurs relevés à la main sur Impact CO2, pas encore validés ; méthode avion non tranchée (étape 10) |
| Site responsive, sans compte | Fait | Vérifié sur captures à 320, 390 et 1 280 px |
| Repères de lecture : échelle en cinq niveaux | Fait | Lettre, libellé en mots et légende des seuils |
| Repères de lecture : part d'un budget carbone annuel | **Manque** | Valeur de référence et source à fournir par l'équipe (étape 11) |
| Conformité WCAG 2.2 AA | **Non mesurée** | Voir plus bas |
| Itinéraire par segments avec cumul | **Manque** | Ni dans l'interface ni dans le backend. Seule la classe `Option` existe ; `Voyage` et `Segment` ne sont pas écrits (étape 12) |

### Should have

| Exigence | État |
|---|---|
| Tri et filtrage des résultats | Manque |
| Fourchette d'incertitude sur le CO₂ | Fait pour les calculs ADEME ; **absente pour l'avion** quand la valeur vient du Travel Impact Model, qui n'en fournit pas |

### Fonctions F1 à F5

| Fonction | Critère du portfolio | État |
|---|---|---|
| F1 Une seule recherche | Départ, arrivée et date suffisent, sans compte | Fait |
| F2 Plusieurs options | Au moins trois modes quand ils existent | Fait, mais le site ne sait pas toujours si un mode existe (§ 5) |
| F3 Côte à côte | Trois critères visibles sans clic | Fait |
| F4 CO₂ compréhensible | Le voyageur classe correctement les options | Échelle faite ; phrase de comparaison et budget annuel manquent ; aucun test utilisateur |
| F5 Calcul fiable | Facteurs ADEME et Travel Impact Model, méthode affichée | Méthode affichée ; facteurs non validés |

### Règles de fiabilité

| Règle | État | Détail |
|---|---|---|
| 1. Chaque valeur porte sa provenance et le site l'affiche | Fait | Bloc « Sources des valeurs » sur chaque carte ; mention « Estimation » quand la valeur vient d'un barème |
| 2. Même formule pour tous, Travel Impact Model pour les vols | Fait | C'est justement ce mélange qui pose le problème de méthode (étape 10) |
| 3. Prix indicatifs en fourchette | Fait | Vérifié par un test sur les quatre modes |
| 4. Repli à trois niveaux, le site ne plante pas | Fait en partie | Fonctionne pour la voiture, le train, le car et l'avion. **Pas de repli pour le géocodage** : si OpenRouteService est en panne et la ville absente du cache, la recherche échoue |
| 5. Page « Méthode et limites » | Fait | À compléter après les décisions des étapes 9 à 11 |
| 6. Dizaine de trajets de référence | **Manque** | Aucun jeu de trajets de référence dans les tests. Seuls CDG–BKK et Paris–Lyon en voiture sont contrôlés, à la main, par `valider_sources.py` |

### Accessibilité (tableau 1.3.5)

| Point d'attention | État |
|---|---|
| Couleur jamais seule porteuse d'information | Fait : lettre et libellé écrits à côté de chaque pastille |
| Contraste des textes (4,5:1) | Couleurs de la DA reprises ; **non mesuré avec un outil** |
| Contraste des pictogrammes et de l'échelle (3:1) | **Non mesuré** |
| Champs étiquetés | Fait : étiquette visible, erreur écrite et reliée au champ |
| Texte alternatif des pictogrammes | Pictogrammes décoratifs masqués aux lecteurs d'écran, nom du mode toujours écrit à côté |
| Tout utilisable au clavier | Éléments natifs du navigateur, focus visible, lien d'évitement ; **parcours complet non testé** |
| Langage clair | Libellés simples ; phrases de comparaison manquantes (étape 11) |

Non faits à ce jour : essai avec un lecteur d'écran, zoom à 200 %, audit automatique (Lighthouse ou axe). **On ne peut donc pas encore affirmer la conformité AA.**

### Vie privée

Conforme au portfolio : pas de compte, pas d'identifiant, appels aux API depuis le backend, cache sans lien avec une personne, police hébergée sur le site (aucun appel à Google Fonts). Reste à faire : documenter les journaux de l'hébergeur (étape 15).

### Périmètre

Le portfolio annonce un MVP qui « couvre le monde entier pour le CO₂ et la durée ». Aujourd'hui, hors de France : le facteur du train est celui d'un TGV français, le prix du train vient du barème, et la durée du train et du car vient du barème.

## 4. Valeurs marquées « à valider »

Aucune n'a été validée par l'équipe.

| Valeur | Fichier | Origine |
|---|---|---|
| Facteurs d'émission des quatre modes, et leurs fourchettes | `backend/donnees/facteurs_emission.json` | Relevé Impact CO2 du 10 novembre, sans construction des véhicules ; fourchettes tirées du portfolio |
| Seuils des niveaux A–E (10, 50, 120, 200) | `backend/donnees/niveaux_co2.json` | Proposition provisoire du portfolio |
| Coefficients de détour et vitesses moyennes | `backend/donnees/bareme.json` | Calés sur le seul Paris–Lyon |
| Durée d'un vol : 880 km/h, 40 min de décollage et d'atterrissage, 150 min d'aéroport | `backend/donnees/bareme.json` | Deux durées de vol citées de mémoire, non vérifiées ; temps d'aéroport = convention |
| Prix au km des quatre modes | `backend/donnees/bareme_prix.json` | Voiture : carburant relevé le 12 novembre, consommation et péages non vérifiés. Train : un seul trajet. Car et avion : aucun relevé |
| Lecture du fichier SNCF : 2de classe, plein tarif, toutes gares d'une ville, même prix dans les deux sens | `backend/adaptateurs/sncf.py` | Choix de conception |
| Aéroports : 2 grands aéroports les plus proches, à moins de 100 km | `backend/adaptateurs/aeroports.py` | Choix de conception |
| Durée de vie du cache : 30 jours | `backend/adaptateurs/commun.py` | Choix de conception |
| Fenêtre de recherche Transitous : départs de 5 h à 17 h UTC | `backend/adaptateurs/transitous.py` | Choix de conception |

Points de méthode signalés mais non vérifiés :

- Les facteurs ADEME de l'avion incluent-ils les traînées de condensation ? La page « Méthode et limites » dit que c'est à vérifier.
- Une intensité pile sur un seuil passe au niveau le plus émetteur (200 donne E), alors que le portfolio écrit « E : plus de 200 ».
- La fourchette du car (33,1 à 37,6) est l'écart avec ou sans construction du véhicule, pas une vraie incertitude.

## 5. Points fragiles

Classés du plus gênant au moins gênant pour un utilisateur.

### Résultats faux ou trompeurs

1. **Géocodage : « Brest » est situé en Biélorussie.** Le code garde le premier résultat d'OpenRouteService, sans préférence de pays ni choix proposé à l'utilisateur. Brest–Nice est alors calculé sur 1 553 km en avion depuis l'aéroport de Brest (Biélorussie). Le lieu retenu est affiché sous le titre, mais il est facile de ne pas le voir.
2. **Train et car proposés là où il n'y en a pas.** Sans Transitous, le barème ne sait pas si un trajet existe. Paris–Bangkok affiche un train de 10 388 km (23,9 kg, niveau A) et un car de 11 332 km. Avec Transitous actif, ces modes seraient signalés « sans option » ; mais le défaut reviendrait à chaque panne de Transitous.
3. **L'avion est avantagé par le mélange des méthodes.** Paris–Bangkok : 667 kg avec le Travel Impact Model (niveau C), contre environ 1 680 kg avec le facteur ADEME (niveau D). Paris–Barcelone : l'avion (84,9 kg) ressort sous la voiture (114,5 kg). C'est le point à trancher à l'étape 10.
4. **Le Travel Impact Model « connaît » des trajets sans vol direct.** Il a répondu pour Orly–Don Mueang avec la valeur de Roissy–Suvarnabhumi. Le site affiche donc un vol direct entre deux aéroports qui n'en ont sans doute pas, avec une durée et un prix de vol direct.
5. **La durée de l'avion ne compte pas le trajet vers l'aéroport**, alors que le train et le car sont comptés de centre à centre.
6. **Le facteur du train est celui du TGV français** (2,3 g), appliqué à tous les trains de tous les pays.

### Fragilités techniques

7. **Les valeurs du Travel Impact Model bougent.** CDG–BKK valait 667 kg le 12 novembre et 665 kg le 23 novembre ; le portfolio cite 616 kg. Un test de non-régression sur une valeur exacte casserait tout seul : il faudra une tolérance.
8. **Le cache garde aussi les « pas de trajet » pendant 30 jours.** Une date trop lointaine pour les horaires publiés donnerait « aucun train », et cette réponse resterait en cache.
9. **Le cache est un seul fichier JSON**, réécrit en entier à chaque nouvelle réponse et jamais nettoyé. Suffisant aujourd'hui (4 Ko), à revoir avec le multi-segments.
10. **Aucune protection des quotas.** Une comparaison jamais vue consomme 2 géocodages et 1 itinéraire OpenRouteService, 2 appels Transitous et jusqu'à 4 appels Travel Impact Model. Avec 6 segments, c'est six fois plus.
11. **Les sources sont interrogées l'une après l'autre**, avec 60 secondes d'attente maximum chacune. Une source lente bloque toute la réponse, et le serveur ne traite qu'une demande à la fois.
12. **Le serveur est prévu pour le poste local** : adresse `127.0.0.1`, port 8000 fixe, clés lues dans le fichier `.env`. Tout cela est à adapter pour un hébergeur (étape 15).
13. **Une panne et un mauvais réglage se ressemblent.** Une clé invalide ou un quota dépassé déclenchent le repli sur le barème, sans message distinct.

### Tests

14. **Aucun test du front** (JavaScript) ni de l'accessibilité.
15. **Aucun test automatique n'appelle les vraies sources** : c'est voulu, mais seul `valider_sources.py` détecte un changement d'API, et il ne couvre ni Transitous ni Impact CO2.
16. **La fonction `lire_env` existe en double** (`backend/serveur.py` et `scripts/valider_sources.py`).

## 6. État du dépôt et de la documentation

- **Travail non commité** : tout le front (`frontend/`), la correction « pas de route en voiture », la route `/reference`, le dossier `DA/` et `PLAN_SUITE.md`. Le dernier commit est « ajout routes /comparer pour lier front et back ».
- **Le PDF du portfolio est suivi par Git.** Il contient des noms et des comptes rendus d'entretiens : à retirer si le dépôt est public ou le devient.
- **`CLAUDE.md` n'est plus à jour** sur plusieurs points : la clé Impact CO2 y est « en attente » alors qu'elle est dans le `.env` ; les fichiers SNCF et OurAirports y sont « à télécharger » alors qu'ils sont embarqués ; les « premières tâches » sont faites ; la valeur Paris–Bangkok citée (616 kg) ne correspond plus à ce que renvoie le Travel Impact Model (665 kg).
- **Nom du site** : l'interface affiche encore « [NOM] », comme la direction artistique.

## 7. Ce que l'équipe doit fournir ou décider

| Sujet | Pour quelle étape |
|---|---|
| Une adresse de contact pour Transitous, à mettre dans `.env` (`TRANSITOUS_CONTACT`) | Dès maintenant : sans elle, les durées en train et en car restent des estimations |
| Options de calcul ADEME : construction des véhicules, traînées, nombre de passagers en voiture | 9 |
| Méthode de référence pour l'avion | 10 |
| Seuils A–E, valeur et source du budget carbone annuel | 11 |
| Temps d'attente entre deux segments | 12 |
| Que faire quand une ville a plusieurs homonymes (Brest) | 13, ou plus tôt si l'équipe le juge bloquant |
| Nom du site | Avant la mise en ligne |
