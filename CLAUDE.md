# Contexte du projet — Comparateur d'itinéraires (PFE ECE, PFE27-P-3523)

Ce fichier donne à Claude Code le contexte du projet. Il est lu automatiquement à chaque session.

Deux fichiers le complètent : `PLAN_SUITE.md` (étapes 8 à 15, une étape à la fois) et `ETAT_DES_LIEUX.md` (photographie du code au 23 novembre 2026, à ne pas modifier : c'est un bilan daté).

## Le projet

Comparateur web qui aide un voyageur à arbitrer entre **prix, durée et empreinte carbone** quand il construit son itinéraire. L'enjeu n'est pas seulement d'afficher des kg de CO₂, mais de les rendre **compréhensibles** (repères de lecture) et **comparables côte à côte**.

- Équipe de cinq étudiants, livraison en **décembre 2026**, budget nul.
- Cible : voyageurs réguliers, longs voyages en plusieurs étapes, conscience écologique déjà présente.
- Pas de compte utilisateur, pas de donnée personnelle, pas de réservation.

## Décisions prises

- **Backend : Python.** Rôle : garder les clés d'API, calculer le CO₂, ramener toutes les sources à un format commun.
- **Front : HTML, CSS, JavaScript sans framework**, responsive, conforme **WCAG 2.2 niveau AA** (la couleur n'est jamais le seul porteur d'information, contrastes 4,5:1, champs étiquetés, navigation clavier).
- **Premier incrément : un seul segment (A → B) et quatre modes** : avion, train, bus, voiture. **Fait.**
- Le **modèle de données est multi-segments dès le départ** (Voyage → Segments → Options), même si l'interface n'en gère qu'un pour l'instant. Plafond prévu : 6 segments. **Aujourd'hui, seule la classe `Option` existe** ; `Voyage` et `Segment` restent à écrire (étape 12).
- Ferry, vélo, marche, tri/filtres, pondération des critères : plus tard.
- **Aucune dépendance** : bibliothèque standard de Python uniquement, y compris pour le serveur web (`http.server`). `pytest` sert seulement à lancer les tests.
- **Interface d'après la direction artistique** du dossier `DA/` : une carte par mode, police Manrope hébergée sur le site. Le nom du site est encore « [NOM] ». Le mode `bus` s'affiche « Car ».

## Format commun d'une option

Chaque option de transport, quelle que soit sa source, contient :

| Champ | Contenu |
|---|---|
| mode | avion, train, bus, voiture |
| distance_km | distance du segment |
| duree_min | durée estimée |
| prix_min, prix_max | fourchette en euros, jamais une valeur unique si le prix est indicatif |
| type_prix | `reel` ou `indicatif` |
| co2_kg | émissions totales par passager |
| intensite_g_pkm | g CO₂e par passager·km |
| niveau | lettre A à E déduite de l'intensité |
| incertitude | fourchette autour du CO₂ |
| source | origine de chaque valeur (API, fichier, barème) : un texte par valeur, sous les clés `distance`, `duree`, `prix`, `co2` |
| co2_indicatif | seconde estimation du CO₂ par une autre méthode, avec sa source ; affichée pour information, **ne sert ni au niveau, ni au classement, ni aux totaux** (vide s'il n'y en a pas) |
| remarques | mises en garde à afficher sur l'option (par exemple : vol direct non vérifié) |

Le prix, la durée et le CO₂ s'additionnent d'un segment à l'autre.

État réel : `type_prix` vaut toujours `indicatif` (aucune source de prix réel).

## Calcul et lecture du CO₂

- Formule unique pour tous les modes : **distance × facteur d'émission ADEME**.
- Vols : **calcul ADEME, comme les autres modes** (décision de l'équipe du 24 novembre 2026, étape 10). La valeur du Travel Impact Model est jointe à titre indicatif. Le choix est dans `backend/donnees/methode.json` (`co2_avion.methode` : `ademe` ou `tim`), pas dans le code.
- Niveaux provisoires (g CO₂e/passager·km) : A < 10, B 10–50, C 50–120, D 120–200, E > 200. **À garder en configuration, pas en dur.** Ils sont dans `backend/donnees/niveaux_co2.json`. Une valeur pile sur un seuil passe au niveau le plus émetteur (200 donne E).
- Affichage : kg totaux + niveau A–E + part d'un budget carbone annuel (valeur de référence encore à sourcer). **La part du budget annuel n'est pas affichée** tant que l'équipe n'a pas fourni la valeur et sa source (étape 11).
- Les facteurs d'émission doivent venir de la Base Empreinte ADEME et être **validés par l'équipe** avant d'être considérés comme définitifs. Ne pas inventer de facteur : mettre une valeur marquée « à valider » et le signaler.
- État réel des facteurs (`backend/donnees/facteurs_emission.json`) : relevés à la main sur Impact CO2 le 10 novembre 2026, revérifiés avec la clé le 24 novembre (valeurs identiques). **Tous encore « à valider ».** L'étape 9 (appel à l'API) n'est pas faite.
- Options ADEME actives, les mêmes pour tous les modes (`methode.json`, `options_ademe`) : **construction des véhicules non comptée** ; **traînées de condensation de l'avion comptées** ; une personne par voiture ; TGV pour le train.
- **À trancher en équipe : les traînées.** Le facteur ADEME de l'avion = carburant + traînées (224,2 g/km sur un vol court, dont 101 g de traînées, soit 45 %). C'est le réglage par défaut d'Impact CO2 et celui du code depuis le début, alors que le portfolio annonçait les exclure. Passer `trainees_de_condensation` à `false` les retire (Paris–Bangkok : 1 677 kg → 921 kg) ; il faut alors recalculer `trajets_reference.json`.
- Les barèmes (`bareme.json`, `bareme_prix.json`) sont eux aussi « à valider » : calés sur très peu de trajets, souvent le seul Paris–Lyon.

## Sources de données

| Besoin | Source | État au 24 novembre 2026 |
|---|---|---|
| CO₂ tous modes | API Impact CO2 (ADEME) ou facteurs embarqués en JSON | Facteurs embarqués en JSON (relevé manuel). Clé disponible : `IMPACT_API_Key`, **pas encore utilisée par le code** (étape 9) |
| CO₂ vols | Travel Impact Model (Google) | Branché (`adaptateurs/tim.py`). Clé : `TIM_API_Key` |
| Géocodage, distance et durée voiture | OpenRouteService | Branché (`adaptateurs/ors.py`). Clé : `ORS_API_Key` |
| Durée train et bus | Transitous (API MOTIS) | Branché (`adaptateurs/transitous.py`). Contact : `TRANSITOUS_CONTACT`, envoyé dans le User-Agent ; sans lui, la source n'est pas interrogée. **Ne fournit pas la distance** : elle est estimée par barème |
| Prix train France | Jeu SNCF « Tarifs TGV INOUI et OUIGO » (CSV, licence ODbL) | Embarqué (`donnees/tarifs_sncf.csv`, version du 17 mars 2026), lu par `adaptateurs/sncf.py` |
| Aéroports (position, IATA) | OurAirports `airports.csv` (domaine public) | Embarqué, réduit à 3 245 aéroports (`donnees/aeroports.csv`), lu par `adaptateurs/aeroports.py` |
| Prix vols | Travelpayouts Data API, sinon barème | Barème (Travelpayouts non branché) |
| Prix bus, voiture | Barème maison (€/km ; carburant + péages) | Construit (`donnees/bareme_prix.json`), « à valider » |
| Durée avion | Estimation : distance ÷ vitesse moyenne + temps d'aéroport | Construite (`donnees/bareme.json`), « à valider » |

Écartés : Google Routes (payant), Amadeus Self-Service (fermé en juillet 2026), extraction automatique de Kayak ou Google Flights.

Ce qui reste une estimation même quand toutes les sources répondent : tous les prix, la distance du train et du bus, la durée de l'avion.

### Travel Impact Model

- Service : `https://travelimpactmodel.googleapis.com`, clé passée en `?key=`.
- `POST /v1/flights:computeFlightEmissions` exige un vol précis (origine, destination, code compagnie, numéro de vol, date) : **pas adapté** tant qu'on n'a pas d'horaires de vols.
- La méthode « typical flight emissions » prend seulement des paires d'aéroports (jusqu'à 1 000 par requête) : **c'est celle utilisée**. Nom vérifié dans la documentation officielle : `POST /v1/flights:computeTypicalFlightEmissions`, corps `{"markets": [{"origin": "CDG", "destination": "BKK"}]}`, réponse dans `typicalFlightEmissions[0].emissionsGramsPerPax.economy`.
- Résultat en grammes par passager, par classe de voyage. Vol avec escale : additionner les tronçons.
- Un trajet inconnu revient sans émissions (ce n'est pas une erreur) : repli sur le facteur ADEME.
- D'après sa documentation, la valeur « typique » couvre les vols **directs et avec escale** d'un trajet, et les aéroports voisins à moins de 150 km. Elle répond donc pour Lyon–Bangkok, et donne la même valeur pour Orly et Roissy : **une réponse ne prouve pas qu'un vol direct existe**. Aucune de nos sources ne le dit ; l'option avion porte donc toujours la remarque « Vol direct non vérifié ».
- Elle ne compte pas les traînées de condensation (« not yet included »), contrairement au facteur ADEME.
- Les valeurs changent dans le temps : CDG–BKK valait 667 kg le 12 novembre 2026 et 665 kg le 23. Les contrôles se font donc avec une tolérance (15 %), jamais sur une valeur exacte.

### OpenRouteService

- Plan gratuit : 2 000 itinéraires/jour (40/min), 1 000 géocodages/jour. Mettre les réponses en cache.
- Coordonnées dans l'ordre `[longitude, latitude]`.
- Géocodage : on demande 10 villes (`layers=locality`, `lang=fr`). Presque toutes les grandes villes ont des homonymes (7 « Paris », 10 « Londres ») et le premier résultat n'est pas toujours le bon (« Brest » donnait la Biélorussie). **Le site ne garde donc jamais le premier résultat en silence** :
  - pendant la frappe, à partir de 3 lettres, un menu propose des villes avec leur région et leur pays (route `/lieux`, méthode `autocomplete` de la source) ;
  - si l'utilisateur tape un nom sans choisir dans le menu et que ce nom désigne plusieurs villes, le site pose la question avant de comparer ;
  - la ville choisie repart avec son nom complet et sa position (`depart_point`, `arrivee_point` au format « longitude,latitude »), ce qui évite un nouveau géocodage.
- L'autocomplétion consomme le quota de géocodage : le site attend une pause dans la frappe et le serveur met les réponses en cache.
- Itinéraire : les codes d'erreur 2004 (plus de 6 000 km), 2009 (aucune route) et 2010 (point loin de toute route) signifient « pas d'itinéraire », pas une panne : aucune option voiture n'est proposée.

### Transitous

- `GET https://api.transitous.org/api/v6/plan`, coordonnées en « latitude,longitude » (l'inverse d'OpenRouteService).
- Durée retenue : le trajet le plus rapide parmi les départs du jour demandé entre 5 h et 17 h UTC, de centre à centre. C'est le seul endroit où la date du voyage sert.
- Aucun itinéraire trouvé = pas d'option pour ce mode (ce n'est pas une panne).

### Cache

- Un fichier JSON, `backend/cache/reponses.json`, ignoré par Git, sans clé d'API.
- Une vraie réponse est réutilisée pendant 30 jours ; au-delà, la source est réinterrogée et l'ancienne réponse ne sert que de secours.
- Une réponse « rien trouvé » (pas de trajet, pas de route, vol inconnu, ville inconnue) n'est gardée que 24 heures et ne sert jamais de secours.

## Règles de fiabilité

1. Chaque valeur porte sa provenance, et le site l'affiche.
2. Les prix indicatifs sont toujours des fourchettes.
3. Repli à trois niveaux : source en direct → cache de la même requête → estimation par barème. Le site ne plante pas : il dégrade la précision et le dit.
4. Une page « Méthode et limites » détaille sources, formules et exclusions (traînées de condensation, hébergement).
5. Un jeu d'une dizaine de trajets de référence sert de test de non-régression.

État réel : les règles 1, 2 et 4 sont appliquées. Pour la règle 3, il n'existe pas de repli pour le géocodage : si OpenRouteService est en panne et la ville absente du cache, la recherche échoue avec un message clair. **La règle 5 n'est appliquée que pour l'avion** : trois vols de référence dans `backend/donnees/trajets_reference.json`, contrôlés avec une tolérance (2 % pour le calcul ADEME dans les tests, 15 % pour le Travel Impact Model dans `valider_sources.py`). Le jeu complet d'une dizaine de trajets reste à faire (étape 13). Pour la règle 4 : les traînées ne sont pas une exclusion tant que le réglage actif les compte.

## Méthode retenue pour l'avion (décision du 24 novembre 2026)

**Le CO₂ de l'avion est calculé avec les facteurs ADEME (Impact CO2), comme les autres modes.** La valeur du Travel Impact Model reste affichée à titre indicatif, avec sa source, mais ne sert ni au niveau A–E ni au classement.

Raison : une comparaison homogène. Avec le Travel Impact Model pour le seul avion, l'avion ressortait deux à trois fois plus bas que par le calcul ADEME, et parfois sous la voiture (Paris–Barcelone : 85 kg en avion contre 115 kg en voiture).

| Vol | Calcul ADEME (retenu) | Travel Impact Model (indicatif) |
|---|---|---|
| Paris–Lyon, 392 km | 88 kg, niveau E | 62 kg |
| Paris–Barcelone, 827 km | 185 kg, niveau E | 85 kg |
| Paris–Bangkok, 9 441 km | 1 677 kg, niveau D | 665 kg (Google Flights affichait 616 kg dans le portfolio) |

Pourquoi Google Flights affiche moins, en termes simples :

1. **Les traînées de condensation** : le facteur ADEME les compte (45 % du total), le Travel Impact Model non.
2. **Avion moyen contre avion précis** : l'ADEME donne un facteur moyen par longueur de vol ; le Travel Impact Model part des avions, des sièges, du remplissage et du fret de chaque ligne. Sans les traînées, le calcul ADEME donnerait encore 921 kg pour Paris–Bangkok.
3. **Valeur « typique »** : un seul chiffre pour les vols directs et avec escale d'un trajet.

La page « Méthode et limites » l'explique aux utilisateurs.

## Où en est le projet (24 novembre 2026)

Les étapes 1 à 8 de `PLAN_SUITE.md` sont faites, ainsi qu'une étape 8 bis de corrections (menu de villes et choix entre homonymes, durée de vie du cache pour les réponses « rien trouvé », serveur qui ne se bloque plus) et **l'étape 10** (méthode de l'avion). **L'étape 9 (brancher l'API Impact CO2) n'est pas faite** : les facteurs restent ceux du fichier JSON.

Ce qui fonctionne : recherche d'un trajet, quatre modes, prix, durée, kg de CO₂e, niveau A–E, source de chaque valeur, page « Méthode et limites ».

Ce qui manque par rapport aux « Must have » du portfolio :

- l'itinéraire en plusieurs segments (étape 12) ;
- la part d'un budget carbone annuel (étape 11) ;
- la conformité WCAG 2.2 AA, **pas encore mesurée** : ni audit automatique, ni lecteur d'écran, ni parcours complet au clavier (étape 14).

Défauts connus, non corrigés :

- un train et un bus peuvent être proposés là où il n'en existe pas quand Transitous est en panne (le barème ne sait pas si un trajet existe) ;
- le site ne sait pas si un vol direct existe : la durée et le prix de l'avion sont ceux d'un vol direct, et l'option le signale ;
- le trajet vers et depuis l'aéroport est un forfait unique (45 min par trajet, « à valider »), quel que soit l'aéroport ;
- le facteur du train est celui du TGV français, appliqué partout ;
- les sources sont interrogées l'une après l'autre, sans protection des quotas ;
- aucun test du JavaScript de l'interface.

## Secrets

- Les clés sont dans `.env` à la racine, **jamais dans le code ni dans Git**.
- Variables attendues : `TIM_API_Key`, `ORS_API_Key`, `IMPACT_API_Key`, `TRANSITOUS_CONTACT` (une adresse de contact de l'équipe, envoyée à Transitous dans le User-Agent).
- `.gitignore` est un **fichier** à la racine qui contient au minimum `.env`.
- Ne jamais afficher, journaliser ou committer le contenu de `.env`.

## Structure du projet

```
backend/
  moteur_co2.py        # calcul local : distance × facteur, niveau A–E, incertitude
  modeles.py           # Option (format commun) ; Voyage et Segment restent à écrire
  comparateur.py       # assemble les quatre options d'un trajet, gère les villes homonymes
  serveur.py           # serveur web local : /comparer, /lieux, /reference et les fichiers du site
  adaptateurs/
    commun.py          # appel HTTP, cache, repli, barèmes, fabrication d'une Option
    ors.py             # OpenRouteService : villes, distance et durée en voiture
    tim.py             # option avion ; Travel Impact Model pour la valeur indicative
    transitous.py      # Transitous : durée en train et en bus
    sncf.py            # fichier des tarifs SNCF
    aeroports.py       # fichier OurAirports : aéroports proches d'une ville
  donnees/             # methode.json (choix de méthode de l'équipe), facteurs_emission.json,
                       # niveaux_co2.json, bareme.json, bareme_prix.json,
                       # trajets_reference.json, tarifs_sncf.csv, aeroports.csv
  cache/               # réponses des sources (ignoré par Git)
  tests/               # un fichier de tests par module, sources toujours simulées
frontend/
  index.html, app.js   # recherche et comparaison
  methode.html, methode.js  # page « Méthode et limites », tableaux lus dans /reference
  style.css, polices/  # styles de la DA, police Manrope (licence OFL)
scripts/
  valider_sources.py   # interroge Travel Impact Model et OpenRouteService en réel
  preparer_aeroports.py  # réduit airports.csv d'OurAirports
DA/                    # direction artistique (PDF)
```

## Commandes utiles

```
python -m pytest backend/tests -q     # tous les tests, sans Internet
python scripts/valider_sources.py     # vérifie les sources en réel
python -m backend.serveur             # site sur http://localhost:8000/
```

## Tâches

Les quatre premières tâches (structure, moteur, validation des sources, écran de comparaison) sont faites. La suite est dans `PLAN_SUITE.md` : étapes restantes : 9 (brancher l'API Impact CO2), puis 11 à 15, **une étape à la fois**.

## Façon de travailler

- Répondre et commenter le code en français.
- Expliquer simplement : une partie de l'équipe débute en développement.
- Rester au plus simple : pas de dépendance ni d'abstraction qui ne sert pas le premier incrément.
- Signaler toute valeur estimée ou non vérifiée plutôt que de la présenter comme sûre.
