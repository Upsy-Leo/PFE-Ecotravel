// Page de comparaison : vérifie le formulaire, interroge /comparer et affiche les options.
//
// Fonctionnement : le formulaire recharge la page avec ?depart=…&arrivee=…&date=… .
// Au chargement, si ces trois paramètres sont dans l'adresse, on lance la comparaison.
//
// Sécurité : les textes reçus du serveur sont toujours insérés avec « textContent »,
// jamais avec « innerHTML » (ils viennent de services extérieurs).

// Ordre d'affichage et libellés des modes (ordre de la direction artistique).
const MODES = {
  train: { nom: "Train", note: "De centre à centre" },
  bus: { nom: "Car", note: "Car longue distance, de centre à centre" },
  voiture: { nom: "Voiture", note: "Une personne à bord, voiture thermique" },
  avion: { nom: "Avion", note: "De centre à centre : trajets vers et depuis l'aéroport et temps d'aéroport compris" },
};

// Pictogrammes décoratifs (le nom du mode est toujours écrit à côté).
const PICTOS = {
  train: '<rect x="5" y="3" width="10" height="11" rx="2.5"/><path d="M5 9h10M8 14l-2 3M12 14l2 3"/>',
  bus: '<rect x="3" y="4" width="14" height="10" rx="2"/><path d="M3 9h14M6 14v2M14 14v2"/>',
  voiture: '<path d="M3 13v-2.5l1.6-4A1.5 1.5 0 0 1 6 5.5h8a1.5 1.5 0 0 1 1.4 1l1.6 4V13zM3 10.5h14M5.5 13v2M14.5 13v2"/>',
  avion: '<path d="M10 2.5c.8 0 1.3.9 1.3 2v3.2l5.2 3.3v1.6l-5.2-1.6v3.2l1.7 1.3v1.2L10 16l-3 .7v-1.2l1.7-1.3V11l-5.2 1.6V11l5.2-3.3V4.5c0-1.1.5-2 1.3-2z"/>',
};

const LIBELLES_NIVEAUX = { A: "très faible", B: "faible", C: "moyen", D: "élevé", E: "très élevé" };

const formulaire = document.getElementById("recherche");
const champs = {
  depart: document.getElementById("depart"),
  arrivee: document.getElementById("arrivee"),
  date: document.getElementById("date"),
};
const etat = document.getElementById("etat");
const encartErreur = document.getElementById("erreur");
// Zone du formulaire où l'on demande « quelle ville ? » quand un nom en désigne plusieurs.
const zoneChoix = document.getElementById("choix-lieux");
const ROLES = { depart: "de départ", arrivee: "d'arrivée" };

// --- Petits outils ---

// Fabrique un élément : creer("p", "meta", "texte").
function creer(balise, classe, texte) {
  const element = document.createElement(balise);
  if (classe) element.className = classe;
  if (texte !== undefined) element.textContent = texte;
  return element;
}

// La date du jour au format AAAA-MM-JJ, à l'heure de l'utilisateur.
function aujourdhui() {
  const jour = new Date();
  const deux = (nombre) => String(nombre).padStart(2, "0");
  return `${jour.getFullYear()}-${deux(jour.getMonth() + 1)}-${deux(jour.getDate())}`;
}

function nombre(valeur, decimales = 0) {
  return valeur.toLocaleString("fr-FR", { maximumFractionDigits: decimales });
}

// 272 minutes -> « 4 h 32 »
function ecrireDuree(minutes) {
  const total = Math.round(minutes);
  const heures = Math.floor(total / 60);
  const reste = total % 60;
  if (heures === 0) return `${reste} min`;
  return `${nombre(heures)} h ${String(reste).padStart(2, "0")}`;
}

// En dessous de 10 kg, on garde une décimale (1,0 kg pour le train).
function ecrireKg(kg) {
  return `${nombre(kg, kg < 10 ? 1 : 0)} kg`;
}

function ecrireDate(date) {
  const jour = new Date(`${date}T12:00:00`);
  return jour.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

// « 2026-11-24 » -> « 24 novembre 2026 »
function ecrireJour(date) {
  return new Date(`${date}T12:00:00`).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
}

// Une valeur est une estimation quand sa source est un barème ou un repli.
function estEstimee(source) {
  return /barème|repli/i.test(source || "");
}

// --- Formulaire ---

function montrerErreurChamp(nom, message) {
  const champ = champs[nom];
  const zone = document.getElementById(`erreur-${nom}`);
  if (message) {
    champ.setAttribute("aria-invalid", "true");
    zone.textContent = `Erreur : ${message}`;
    zone.hidden = false;
  } else {
    champ.removeAttribute("aria-invalid");
    zone.textContent = "";
    zone.hidden = true;
  }
}

// Renvoie le premier champ en erreur, ou null si tout est correct.
function verifierFormulaire() {
  const erreurs = {
    depart: champs.depart.value.trim() ? "" : "Renseignez une ville de départ.",
    arrivee: champs.arrivee.value.trim() ? "" : "Renseignez une ville d'arrivée.",
    date: "",
  };
  if (!champs.date.value) {
    erreurs.date = "Choisissez la date du voyage.";
  } else if (champs.date.value < aujourdhui()) {
    erreurs.date = "Cette date est déjà passée.";
  }
  let premier = null;
  for (const nom of Object.keys(erreurs)) {
    montrerErreurChamp(nom, erreurs[nom]);
    if (erreurs[nom] && !premier) premier = champs[nom];
  }
  // Si une question « quelle ville ? » est affichée, il faut y avoir répondu.
  for (const groupe of zoneChoix.querySelectorAll("fieldset")) {
    const manque = !groupe.querySelector("input:checked");
    const message = groupe.querySelector(".message-erreur");
    message.textContent = manque ? "Erreur : choisissez une ville dans la liste." : "";
    message.hidden = !manque;
    if (manque && !premier) premier = groupe.querySelector("input");
  }
  return premier;
}

// --- Choix de la ville ---
//
// Deux façons de désigner une ville sans ambiguïté :
// 1. la choisir dans le menu proposé pendant la frappe ;
// 2. si on a tapé un nom porté par plusieurs villes, répondre à la question posée ensuite.
// Dans les deux cas, le champ reçoit le nom complet (« Brest, Finistère, France ») et un
// champ caché garde la position de la ville, envoyée au serveur avec la recherche.

// Villes proposées pour chaque champ : nom complet -> lieu.
const propositions = { depart: new Map(), arrivee: new Map() };
const minuteries = {};
const LETTRES_MINIMUM = 3; // même valeur que côté serveur
const ATTENTE_MS = 350; // on attend une pause dans la frappe avant d'interroger le serveur

function oublierPosition(nom) {
  zoneChoix.querySelectorAll(`input[name="${nom}_point"]`).forEach((element) => element.remove());
}

// Garde la position de la ville choisie (« longitude,latitude ») dans un champ caché.
function memoriserPosition(nom, position) {
  oublierPosition(nom);
  const cache = creer("input");
  cache.type = "hidden";
  cache.name = `${nom}_point`;
  cache.value = position;
  zoneChoix.append(cache);
}

function oublierQuestion(nom) {
  zoneChoix.querySelectorAll(`fieldset[data-champ="${nom}"]`).forEach((element) => element.remove());
}

// Demande au serveur les villes qui commencent par le texte tapé, et remplit le menu.
async function chargerPropositions(nom, texte) {
  let lieux;
  try {
    lieux = (await (await fetch(`/lieux?texte=${encodeURIComponent(texte)}`)).json()).lieux;
  } catch (erreur) {
    return; // pas de propositions : on peut toujours taper le nom en entier
  }
  // Les réponses peuvent arriver dans le désordre : on ignore celle d'un texte déjà modifié.
  if (champs[nom].value.trim() !== texte) return;
  propositions[nom] = new Map(lieux.map((lieu) => [lieu.nom, lieu]));
  const menu = document.getElementById(`propositions-${nom}`);
  menu.replaceChildren(...lieux.map((lieu) => {
    const ligne = creer("option");
    ligne.value = lieu.nom; // ville, région, pays
    return ligne;
  }));
}

// À chaque modification d'un champ de ville (frappe, ou choix dans le menu).
function surSaisie(nom) {
  oublierQuestion(nom); // le nom a changé : l'ancienne question ne vaut plus
  clearTimeout(minuteries[nom]);
  const texte = champs[nom].value.trim();
  const lieu = propositions[nom].get(texte);
  if (lieu) {
    memoriserPosition(nom, `${lieu.lon},${lieu.lat}`); // ville choisie dans le menu
    return;
  }
  oublierPosition(nom);
  if (texte.length >= LETTRES_MINIMUM) {
    minuteries[nom] = setTimeout(() => chargerPropositions(nom, texte), ATTENTE_MS);
  }
}

for (const nom of ["depart", "arrivee"]) {
  champs[nom].addEventListener("input", () => surSaisie(nom));
}

// Pose la question : un groupe de boutons radio par champ ambigu.
function afficherChoix(aPreciser) {
  for (const [nom, lieux] of Object.entries(aPreciser)) {
    oublierQuestion(nom);
    const groupe = creer("fieldset", "choix");
    groupe.dataset.champ = nom;
    groupe.setAttribute("aria-describedby", `erreur-choix-${nom}`);
    groupe.append(creer("legend", "", `Plusieurs villes s'appellent « ${champs[nom].value.trim()} ». Laquelle est votre ville ${ROLES[nom]} ?`));
    lieux.forEach((lieu, rang) => {
      const ligne = creer("div", "choix-ligne");
      const bouton = creer("input");
      bouton.type = "radio";
      bouton.name = `choix-${nom}`;
      bouton.id = `choix-${nom}-${rang}`;
      // Rattaché à aucun formulaire : la réponse n'est pas envoyée telle quelle,
      // c'est le nom complet et la position (ci-dessous) qui partent.
      bouton.setAttribute("form", "aucun-formulaire");
      bouton.addEventListener("change", () => {
        champs[nom].value = lieu.nom; // le champ affiche la ville retenue
        memoriserPosition(nom, `${lieu.lon},${lieu.lat}`);
      });
      const etiquette = creer("label", "", lieu.nom); // ville, région, pays
      etiquette.htmlFor = bouton.id;
      ligne.append(bouton, etiquette);
      groupe.append(ligne);
    });
    const message = creer("p", "message-erreur");
    message.id = `erreur-choix-${nom}`;
    message.hidden = true;
    groupe.append(message);
    zoneChoix.append(groupe);
  }
  document.getElementById("resultats").hidden = true;
  etat.textContent = "Plusieurs villes portent ce nom : précisez laquelle, puis relancez la comparaison.";
  zoneChoix.querySelector("fieldset input").focus(); // amène le clavier sur la question
}

formulaire.addEventListener("submit", (evenement) => {
  const premierChampEnErreur = verifierFormulaire();
  if (premierChampEnErreur) {
    evenement.preventDefault(); // on reste sur la page
    premierChampEnErreur.focus(); // le lecteur d'écran lit le champ et son message
  }
  // Sinon on laisse le navigateur recharger la page avec les paramètres dans l'adresse.
});

// --- Affichage des résultats ---

function construirePicto(mode) {
  const pastille = creer("span", "picto");
  pastille.setAttribute("aria-hidden", "true");
  // Constante écrite dans ce fichier, pas une donnée reçue : innerHTML est sûr ici.
  pastille.innerHTML = `<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${PICTOS[mode]}</svg>`;
  return pastille;
}

function construireLettre(lettre) {
  const pastille = creer("span", `lettre lettre-${lettre.toLowerCase()}`, lettre);
  pastille.setAttribute("aria-hidden", "true"); // le niveau est aussi écrit en toutes lettres à côté
  return pastille;
}

// Une ligne « nom → valeur » de la carte.
function construireValeur(nom, contenu) {
  const ligne = creer("div", "valeur");
  ligne.append(creer("dt", "", nom));
  const valeur = creer("dd");
  valeur.append(...contenu);
  ligne.append(valeur);
  return ligne;
}

function construireOption(option, badges, facteurs) {
  const mode = MODES[option.mode];
  const carte = creer("li", "carte option");

  // En-tête : pictogramme, nom du mode, badges éventuels.
  const tete = creer("div", "option-tete");
  const nom = creer("div", "option-nom");
  nom.append(creer("h3", "", mode.nom));
  if (badges.length) {
    const liste = creer("ul", "badges");
    badges.forEach((badge) => liste.append(creer("li", "badge", badge)));
    nom.append(liste);
  }
  tete.append(construirePicto(option.mode), nom);

  const valeurs = creer("dl", "valeurs");

  // Prix : toujours une fourchette, toujours dit « indicatif ».
  valeurs.append(construireValeur("Prix", [
    creer("span", "chiffre", `${nombre(option.prix_min)} à ${nombre(option.prix_max)} €`),
    creer("span", "precision", option.type_prix === "reel" ? "Prix réel" : "Prix indicatif, par personne"),
  ]));

  // Durée
  const dureeEstimee = estEstimee(option.source.duree);
  valeurs.append(construireValeur("Durée", [
    creer("span", "chiffre", ecrireDuree(option.duree_min)),
    creer("span", "precision", `${dureeEstimee ? "Estimation. " : ""}${mode.note}`),
  ]));

  // CO2 : la lettre, le niveau en toutes lettres et les kg. Jamais la couleur seule.
  const co2 = creer("div", "co2");
  const texteCo2 = creer("div");
  texteCo2.append(
    creer("span", "chiffre", `${ecrireKg(option.co2_kg)} CO₂e`),
    creer("span", "precision", `Niveau ${option.niveau}, ${LIBELLES_NIVEAUX[option.niveau]} · ${nombre(option.intensite_g_pkm, 1)} g par km`),
  );
  if (option.incertitude) {
    texteCo2.append(creer("span", "precision", `Entre ${ecrireKg(option.incertitude[0])} et ${ecrireKg(option.incertitude[1])} selon les hypothèses`));
  }
  if (estEstimee(option.source.co2)) {
    texteCo2.append(creer("span", "precision", "Estimation de repli."));
  }
  if (facteurs && /ADEME/.test(option.source.co2)) {
    // Date à laquelle le facteur d'émission a été récupéré auprès de l'ADEME.
    texteCo2.append(creer("span", "precision", `Facteur ADEME récupéré le ${ecrireJour(facteurs.date)}`));
  }
  if (option.co2_indicatif) {
    // Seconde estimation, par une autre méthode : affichée pour information seulement.
    const autreMethode = option.co2_indicatif.source.split(",")[0];
    texteCo2.append(creer("span", "precision",
      `À titre indicatif : ${ecrireKg(option.co2_indicatif.co2_kg)} selon ${autreMethode}. Cette valeur ne sert ni au niveau ni au classement.`));
  }
  co2.append(construireLettre(option.niveau), texteCo2);
  valeurs.append(construireValeur("CO₂ par personne", [co2]));

  valeurs.append(construireValeur("Distance", [
    creer("span", "", `${nombre(option.distance_km)} km${estEstimee(option.source.distance) ? " (estimation)" : ""}`),
  ]));

  // Sources : une ligne par valeur, dans un bloc dépliable.
  const sources = creer("details", "sources");
  const titre = creer("summary", "", "Sources des valeurs");
  titre.append(creer("span", "", ` (${mode.nom.toLowerCase()})`));
  sources.append(titre);
  const liste = creer("dl");
  const lignes = [["Prix", option.source.prix], ["Durée", option.source.duree], ["CO₂", option.source.co2], ["Distance", option.source.distance]];
  if (option.co2_indicatif) lignes.splice(3, 0, ["CO₂, valeur indicative", option.co2_indicatif.source]);
  for (const [nomValeur, source] of lignes) {
    liste.append(creer("dt", "", nomValeur), creer("dd", "", source || "Source non précisée"));
  }
  sources.append(liste);

  carte.append(tete);
  // Mises en garde propres à cette option (par exemple : vol direct non vérifié).
  for (const remarque of option.remarques || []) {
    const bloc = creer("p", "remarque");
    bloc.append(creer("strong", "", "À savoir : "), remarque);
    carte.append(bloc);
  }
  carte.append(valeurs, sources);
  return carte;
}

// Badges : seulement quand une option est strictement la meilleure sur un critère.
// Pas de « moins cher » : les prix sont des fourchettes qui se chevauchent.
function calculerBadges(options) {
  const badges = {};
  options.forEach((option) => { badges[option.mode] = []; });
  const meilleur = (champ, libelle) => {
    const tri = [...options].sort((a, b) => a[champ] - b[champ]);
    if (tri.length > 1 && tri[0][champ] < tri[1][champ]) badges[tri[0].mode].push(libelle);
  };
  meilleur("co2_kg", "Le moins émetteur");
  meilleur("duree_min", "Le plus rapide");
  return badges;
}

function afficherResultats(reponse) {
  const ordre = Object.keys(MODES);
  const options = reponse.options
    .filter((option) => MODES[option.mode])
    .sort((a, b) => ordre.indexOf(a.mode) - ordre.indexOf(b.mode));
  const badges = calculerBadges(options);

  const depart = reponse.depart.ville;
  const arrivee = reponse.arrivee.ville;
  const titre = document.getElementById("titre-resultats");
  titre.textContent = `${depart} → ${arrivee}`;
  document.title = `${depart} → ${arrivee} · [NOM]`;
  const pluriel = options.length > 1 ? "s" : "";
  document.getElementById("resume").textContent =
    `${ecrireDate(reponse.date)} · 1 personne · aller simple · ${options.length} option${pluriel}`;

  // Le lieu retenu s'affiche en toutes lettres (ville, région, pays) dans les champs du
  // haut : c'est là qu'on le lit, et là qu'on le modifie. Sa position est gardée, pour
  // qu'une nouvelle recherche (autre date, par exemple) reparte de la même ville.
  for (const nom of ["depart", "arrivee"]) {
    champs[nom].value = reponse[nom].nom;
    memoriserPosition(nom, `${reponse[nom].lon},${reponse[nom].lat}`);
  }

  const liste = document.getElementById("options");
  liste.replaceChildren(...options.map((option) => construireOption(option, badges[option.mode], reponse.facteurs)));

  // Modes sans option : on le dit, avec la raison.
  const absents = Object.entries(reponse.sans_option || {});
  const listeAbsents = document.getElementById("liste-sans-option");
  listeAbsents.replaceChildren(...absents.map(([mode, raison]) => {
    const ligne = creer("li");
    ligne.append(creer("strong", "", `${MODES[mode] ? MODES[mode].nom : mode} : `), raison);
    return ligne;
  }));
  document.getElementById("sans-option").hidden = absents.length === 0;

  document.getElementById("avertissements").replaceChildren(
    ...(reponse.avertissements || []).map((texte) => creer("li", "", texte)),
  );

  document.getElementById("presentation").hidden = true;
  document.getElementById("reperes").hidden = true;
  document.getElementById("resultats").hidden = false;
  etat.textContent = `${options.length} option${pluriel} trouvée${pluriel} pour ${depart} → ${arrivee}.`;
  titre.focus(); // amène le clavier et le lecteur d'écran au début des résultats
}

// Légende A à E : les seuils viennent de la configuration du serveur, pas de ce fichier.
async function afficherEchelle() {
  try {
    const reference = await (await fetch("/reference")).json();
    const niveaux = reference.niveaux_co2.niveaux;
    const lignes = niveaux.map((niveau, rang) => {
      const ligne = creer("li");
      const mini = rang === 0 ? null : niveaux[rang - 1].en_dessous_de;
      let seuils = `${mini} g par km et plus`;
      if (mini === null) seuils = `moins de ${niveau.en_dessous_de} g par km`;
      else if (niveau.en_dessous_de !== null) seuils = `de ${mini} à moins de ${niveau.en_dessous_de} g par km`;
      ligne.append(
        construireLettre(niveau.lettre),
        creer("span", "", `${niveau.lettre}, ${LIBELLES_NIVEAUX[niveau.lettre] || ""} : ${seuils}`),
      );
      return ligne;
    });
    document.getElementById("echelle").replaceChildren(...lignes);
  } catch (erreur) {
    // Sans la légende, les résultats restent lisibles (lettre + niveau écrit) : on ne bloque pas.
    document.getElementById("echelle").replaceChildren(creer("li", "", "Seuils indisponibles pour le moment."));
  }
}

function afficherErreur(message) {
  etat.textContent = "";
  encartErreur.textContent = message;
  encartErreur.hidden = false;
}

async function comparer(parametres) {
  encartErreur.hidden = true;
  etat.textContent = "Comparaison en cours… La première recherche d'un trajet peut prendre quelques secondes.";
  const bouton = formulaire.querySelector("button");
  bouton.disabled = true;
  // Étape 1 : interroger le serveur. Seule une panne de réseau arrive dans ce « catch ».
  let reponse;
  let donnees;
  try {
    reponse = await fetch(`/comparer?${parametres}`);
    donnees = await reponse.json();
  } catch (erreur) {
    console.error("Appel de /comparer impossible :", erreur);
    afficherErreur("Le serveur ne répond pas. Vérifiez qu'il est lancé (python -m backend.serveur), puis réessayez.");
    bouton.disabled = false;
    return;
  }
  bouton.disabled = false;

  // Étape 2 : afficher. Une erreur ici vient de la page, pas du serveur : on le dit,
  // et le détail part dans la console du navigateur (touche F12).
  try {
    if (!reponse.ok) {
      afficherErreur(donnees.erreur || "La comparaison a échoué.");
    } else if (donnees.a_preciser) {
      afficherChoix(donnees.a_preciser); // plusieurs villes du même nom : on demande
    } else {
      afficherResultats(donnees);
    }
  } catch (erreur) {
    console.error("Affichage de la réponse impossible :", erreur);
    afficherErreur("La réponse du serveur n'a pas pu être affichée. Rechargez la page avec Ctrl+F5 ; si le problème persiste, le détail est dans la console du navigateur (F12).");
  }
}

// --- Au chargement de la page ---

champs.date.min = aujourdhui();

const parametres = new URLSearchParams(window.location.search);
if (parametres.has("depart") || parametres.has("arrivee") || parametres.has("date")) {
  // On remet la recherche dans le formulaire, pour pouvoir la modifier.
  for (const nom of Object.keys(champs)) {
    champs[nom].value = parametres.get(nom) || "";
  }
  for (const nom of ["depart", "arrivee"]) {
    if (parametres.get(`${nom}_point`)) memoriserPosition(nom, parametres.get(`${nom}_point`));
  }
  if (verifierFormulaire() === null) {
    afficherEchelle();
    comparer(parametres.toString());
  }
}
