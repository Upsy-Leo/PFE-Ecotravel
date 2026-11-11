# Contexte du projet — Comparateur d'itinéraires (PFE ECE, PFE27-P-3523)

Ce fichier donne à Claude Code le contexte du projet. Il est lu automatiquement à chaque session.

## Le projet

Comparateur web qui aide un voyageur à arbitrer entre **prix, durée et empreinte carbone** quand il construit son itinéraire. L'enjeu n'est pas seulement d'afficher des kg de CO₂, mais de les rendre **compréhensibles** (repères de lecture) et **comparables côte à côte**.

- Équipe de cinq étudiants, livraison en **décembre 2026**, budget nul.
- Cible : voyageurs réguliers, longs voyages en plusieurs étapes, conscience écologique déjà présente.
- Pas de compte utilisateur, pas de donnée personnelle, pas de réservation.

## Décisions prises

- **Backend : Python.** Rôle : garder les clés d'API, calculer le CO₂, ramener toutes les sources à un format commun.
- **Front : HTML, CSS, JavaScript sans framework**, responsive, conforme **WCAG 2.2 niveau AA** (la couleur n'est jamais le seul porteur d'information, contrastes 4,5:1, champs étiquetés, navigation clavier).
- **Premier incrément : un seul segment (A → B) et quatre modes** : avion, train, bus, voiture.
- Le **modèle de données est multi-segments dès le départ** (Voyage → Segments → Options), même si l'interface n'en gère qu'un pour l'instant. Plafond prévu : 6 segments.
- Ferry, vélo, marche, tri/filtres, pondération des critères : plus tard.

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
| source | origine de chaque valeur (API, fichier, barème) |

Le prix, la durée et le CO₂ s'additionnent d'un segment à l'autre.

## Calcul et lecture du CO₂

- Formule unique pour tous les modes : **distance × facteur d'émission ADEME**.
- Vols : Travel Impact Model en priorité, repli sur ADEME si indisponible.
- Niveaux provisoires (g CO₂e/passager·km) : A < 10, B 10–50, C 50–120, D 120–200, E > 200. **À garder en configuration, pas en dur.**
- Affichage : kg totaux + niveau A–E + part d'un budget carbone annuel (valeur de référence encore à sourcer).
- Les facteurs d'émission doivent venir de la Base Empreinte ADEME et être **validés par l'équipe** avant d'être considérés comme définitifs. Ne pas inventer de facteur : mettre une valeur marquée « à valider » et le signaler.

## Sources de données

| Besoin | Source | État |
|---|---|---|
| CO₂ tous modes | API Impact CO2 (ADEME) ou facteurs embarqués en JSON | Clé demandée, en attente → commencer avec un fichier local |
| CO₂ vols | Travel Impact Model (Google) | Clé disponible : `TIM_API_Key` |
| Géocodage, distance et durée voiture | OpenRouteService | Clé disponible : `ORS_API_Key` |
| Durée train et bus | Transitous (API MOTIS) | À tester ; usage non commercial, User-Agent avec contact requis |
| Prix train France | Jeu SNCF « Tarifs TGV INOUI et OUIGO » (CSV) | À télécharger et embarquer |
| Aéroports (position, IATA) | OurAirports `airports.csv` (domaine public) | À télécharger et embarquer |
| Prix vols | Travelpayouts Data API, sinon barème | Optionnel |
| Prix bus, voiture | Barème maison (€/km ; carburant + péages) | À construire et documenter |
| Durée avion | Estimation : distance ÷ vitesse moyenne + temps d'aéroport | À construire |

Écartés : Google Routes (payant), Amadeus Self-Service (fermé en juillet 2026), extraction automatique de Kayak ou Google Flights.

### Travel Impact Model

- Service : `https://travelimpactmodel.googleapis.com`, clé passée en `?key=`.
- `POST /v1/flights:computeFlightEmissions` exige un vol précis (origine, destination, code compagnie, numéro de vol, date) : **pas adapté** tant qu'on n'a pas d'horaires de vols.
- La méthode « typical flight emissions » prend seulement des paires d'aéroports (jusqu'à 1 000 par requête) : **c'est celle à utiliser**. Le nom exact de la méthode et des champs est à vérifier dans la documentation officielle avant de coder l'adaptateur.
- Résultat en grammes par passager, par classe de voyage. Vol avec escale : additionner les tronçons.

### OpenRouteService

- Plan gratuit : 2 000 itinéraires/jour (40/min), 1 000 géocodages/jour. Mettre les réponses en cache.
- Coordonnées dans l'ordre `[longitude, latitude]`.

## Règles de fiabilité

1. Chaque valeur porte sa provenance, et le site l'affiche.
2. Les prix indicatifs sont toujours des fourchettes.
3. Repli à trois niveaux : source en direct → cache de la même requête → estimation par barème. Le site ne plante pas : il dégrade la précision et le dit.
4. Une page « Méthode et limites » détaille sources, formules et exclusions (traînées de condensation, hébergement).
5. Un jeu d'une dizaine de trajets de référence sert de test de non-régression.

## Point de méthode à trancher en équipe

Sur Paris–Bangkok (environ 9 450 km), Google Flights affiche 616 kg CO₂e, soit environ 65 g/passager·km. Les ordres de grandeur ADEME retenus pour l'avion (145 à 290 g/passager·km) donneraient au moins 1 370 kg. **Mélanger Travel Impact Model pour les vols et ADEME pour les autres modes peut donc avantager l'avion dans la comparaison.** L'écart et le choix retenu sont à documenter dans « Méthode et limites ».

## Secrets

- Les clés sont dans `.env` à la racine, **jamais dans le code ni dans Git**.
- `.gitignore` est un **fichier** à la racine qui contient au minimum `.env`.
- Ne jamais afficher, journaliser ou committer le contenu de `.env`.

## Structure visée

```
backend/
  moteur_co2.py        # calcul local : distance × facteur, niveau A–E, incertitude
  modeles.py           # Voyage, Segment, Option (format commun)
  adaptateurs/         # un fichier par source : tim.py, ors.py, transitous.py…
  donnees/             # facteurs ADEME (JSON), aéroports, tarifs SNCF
  tests/               # tests du moteur + trajets de référence
frontend/
  index.html, style.css, app.js
scripts/
  valider_sources.py   # interroge chaque source sur les trajets de référence
```

## Premières tâches

1. Créer la structure ci-dessus
2. Écrire `moteur_co2.py` et ses tests, avec des facteurs en JSON marqués « à valider ».
3. Écrire `scripts/valider_sources.py` : tester Travel Impact Model et OpenRouteService avec les clés du `.env`, afficher la réponse brute en cas d'échec.
4. Écran de comparaison statique avec des données fictives, accessible AA.

## Façon de travailler

- Répondre et commenter le code en français.
- Expliquer simplement : une partie de l'équipe débute en développement.
- Rester au plus simple : pas de dépendance ni d'abstraction qui ne sert pas le premier incrément.
- Signaler toute valeur estimée ou non vérifiée plutôt que de la présenter comme sûre.
