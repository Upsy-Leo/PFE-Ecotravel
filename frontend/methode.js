// Page « Méthode et limites » : remplit les tableaux à partir de /reference,
// c'est-à-dire des fichiers de configuration que le calcul utilise vraiment
// (facteurs d'émission, seuils des niveaux, barèmes). Rien n'est recopié ici.

const NOMS_MODES = { train: "Train", bus: "Car", voiture: "Voiture", avion: "Avion" };
const LIBELLES_NIVEAUX = { A: "Très faible", B: "Faible", C: "Moyen", D: "Élevé", E: "Très élevé" };

function creer(balise, texte) {
  const element = document.createElement(balise);
  if (texte !== undefined) element.textContent = texte;
  return element;
}

function nombre(valeur) {
  return valeur.toLocaleString("fr-FR", { maximumFractionDigits: 2 });
}

// Fabrique une ligne de tableau. La première cellule est l'en-tête de la ligne.
function ligne(cellules) {
  const tr = creer("tr");
  cellules.forEach((texte, rang) => {
    const cellule = creer(rang === 0 ? "th" : "td", texte);
    if (rang === 0) cellule.scope = "row";
    tr.append(cellule);
  });
  return tr;
}

// « jusqu'à 1 000 km », « de 1 000 à 2 000 km », « au-delà de 5 000 km », ou « toutes distances ».
function ecrireTranche(tranches, rang) {
  const limite = tranches[rang].jusqu_a_km;
  const debut = rang === 0 ? null : tranches[rang - 1].jusqu_a_km;
  if (debut === null && limite === null) return "Toutes distances";
  if (debut === null) return `Jusqu'à ${nombre(limite)} km`;
  if (limite === null) return `Au-delà de ${nombre(debut)} km`;
  return `De ${nombre(debut)} à ${nombre(limite)} km`;
}

function remplir(id, elements) {
  document.getElementById(id).replaceChildren(...elements);
}

function listeDe(textes) {
  return textes.map((texte) => creer("li", texte));
}

function afficher(reference) {
  // Date de récupération des facteurs sur l'API Impact CO2
  const jour = new Date(`${reference.facteurs_emission.releve.date}T12:00:00`)
    .toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
  document.getElementById("date-facteurs").textContent = `Ils ont été récupérés le ${jour}.`;
  document.getElementById("date-facteurs-sources").textContent = `récupérés le ${jour}`;

  // Facteurs d'émission
  const facteurs = reference.facteurs_emission.modes;
  const lignesFacteurs = [];
  const aVerifier = [];
  for (const mode of Object.keys(NOMS_MODES)) {
    const donnees = facteurs[mode];
    donnees.tranches.forEach((tranche, rang) => {
      lignesFacteurs.push(ligne([
        NOMS_MODES[mode],
        `${tranche.libelle} (${ecrireTranche(donnees.tranches, rang).toLowerCase()})`,
        nombre(tranche.facteur_g_pkm),
        `${nombre(donnees.min_g_pkm)} à ${nombre(donnees.max_g_pkm)}`,
        donnees.source,
        donnees.statut,
      ]));
    });
    (donnees.a_verifier || []).forEach((texte) => aVerifier.push(`${NOMS_MODES[mode]} : ${texte}`));
  }
  remplir("tableau-facteurs", lignesFacteurs);
  remplir("facteurs-a-verifier", listeDe(aVerifier));

  // Réglages actifs du calcul ADEME et méthode de l'avion : lus dans methode.json.
  const methode = reference.methode;
  const options = methode.options_ademe;
  remplir("options-ademe", listeDe([
    options.construction_des_vehicules
      ? "la fabrication des véhicules est comptée ;"
      : "la fabrication des véhicules n'est pas comptée ;",
    options.trainees_de_condensation
      ? "les traînées de condensation de l'avion sont comptées."
      : "les traînées de condensation de l'avion ne sont pas comptées.",
  ]));
  document.getElementById("methode-avion-active").textContent =
    methode.co2_avion.methodes_possibles[methode.co2_avion.methode];

  // Vols de référence : les deux estimations côte à côte.
  remplir("tableau-reference", reference.trajets_reference.trajets.map((trajet) => ligne([
    `${trajet.nom} (${trajet.origine}–${trajet.destination})`,
    `${nombre(trajet.distance_km)} km`,
    `${nombre(Math.round(trajet.co2_ademe_kg))} kg (niveau ${trajet.niveau_attendu})`,
    `${nombre(Math.round(trajet.co2_tim_kg))} kg`,
  ])));

  // Niveaux A à E
  const niveaux = reference.niveaux_co2.niveaux;
  remplir("tableau-niveaux", niveaux.map((niveau, rang) => {
    const mini = rang === 0 ? null : niveaux[rang - 1].en_dessous_de;
    let seuils = `${nombre(mini ?? 0)} et plus`;
    if (mini === null) seuils = `Moins de ${nombre(niveau.en_dessous_de)}`;
    else if (niveau.en_dessous_de !== null) seuils = `De ${nombre(mini)} à moins de ${nombre(niveau.en_dessous_de)}`;
    return ligne([niveau.lettre, LIBELLES_NIVEAUX[niveau.lettre] || "", seuils]);
  }));

  // Barème de distance et de durée
  const bareme = reference.bareme;
  remplir("tableau-bareme", ["voiture", "train", "bus"].map((mode) => ligne([
    NOMS_MODES[mode],
    `× ${nombre(bareme.modes[mode].coefficient_detour)}`,
    `${nombre(bareme.modes[mode].vitesse_km_h)} km/h`,
  ])));
  const avion = bareme.modes.avion;
  remplir("hypotheses-avion", listeDe([
    `Valeurs utilisées : ${nombre(avion.temps_acces_aeroport_min)} min pour aller à l'aéroport et autant pour en revenir, ${nombre(avion.temps_aeroport_min)} min d'aéroport, ${nombre(avion.temps_decollage_atterrissage_min)} min de décollage et d'atterrissage, ${nombre(avion.vitesse_km_h)} km/h en vol.`,
    ...bareme.duree_avion.hypotheses,
  ]));

  // Barème de prix
  const prix = reference.bareme_prix.modes;
  const lignesPrix = [];
  const blocsHypotheses = [];
  for (const mode of Object.keys(NOMS_MODES)) {
    prix[mode].tranches.forEach((tranche, rang) => {
      lignesPrix.push(ligne([
        NOMS_MODES[mode],
        ecrireTranche(prix[mode].tranches, rang),
        `${nombre(tranche.prix_min_eur_km)} € par km`,
        `${nombre(tranche.prix_max_eur_km)} € par km`,
      ]));
    });
    const liste = creer("ul");
    liste.className = "liste";
    liste.append(...listeDe(prix[mode].hypotheses));
    blocsHypotheses.push(creer("h4", NOMS_MODES[mode]), liste);
  }
  remplir("tableau-prix", lignesPrix);
  remplir("hypotheses-prix", blocsHypotheses);
}

async function charger() {
  try {
    const reponse = await fetch("/reference");
    if (!reponse.ok) throw new Error(`HTTP ${reponse.status}`);
    afficher(await reponse.json());
  } catch (erreur) {
    // Le texte de la page reste lisible ; seuls les tableaux manquent, et on le dit.
    document.querySelectorAll("tbody td[colspan]").forEach((cellule) => {
      cellule.textContent = "Valeurs indisponibles : le serveur ne répond pas (python -m backend.serveur).";
    });
  }
}

charger();
