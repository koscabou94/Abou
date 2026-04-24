"""
Chatbot Éducatif - Ministère de l'Éducation du Sénégal
Version démo : fonctionne sans Docker, sans modèles lourds.
Lancer : python demo.py
Accès  : http://localhost:8000
"""

import json
import re
import uuid
import webbrowser
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# ─────────────────────────────────────────────
# BASE DE CONNAISSANCE (FAQ intégrée)
# ─────────────────────────────────────────────
FAQ = [
    # ── INSCRIPTIONS ──
    {
        "patterns": ["inscription", "inscrire", "s'inscrire", "inscris", "enregistrement"],
        "response": "Les inscriptions scolaires au Sénégal se déroulent généralement entre juillet et septembre avant la rentrée. Pour inscrire un élève :\n1. Rendez-vous dans l'école souhaitée\n2. Fournissez l'extrait de naissance de l'élève\n3. Fournissez le carnet de santé (vaccinations à jour)\n4. Payer les frais d'inscription (variables selon l'établissement)\nPour les écoles publiques, l'inscription est gratuite au primaire.",
        "category": "inscription",
        "lang": "fr"
    },
    {
        "patterns": ["waaw inscription", "doxali", "jël ci kanam"],
        "response": "Ci Sénégaal, lañuy defar inscription yi ci juillet ak septembre. Jël na ko ci dëkk bi ak extrait de naissance, carnet de santé ak jox ko directeur bi.",
        "category": "inscription",
        "lang": "wo"
    },
    # ── CALENDRIER ──
    {
        "patterns": ["rentrée", "rentree", "début cours", "debut cours", "vacances", "calendrier scolaire", "congé", "conge"],
        "response": "Calendrier scolaire type au Sénégal :\n• Rentrée scolaire : premier lundi d'octobre\n• Vacances de Toussaint : fin octobre (1 semaine)\n• Vacances de Noël : fin décembre (2 semaines)\n• Vacances de février : mi-février (1 semaine)\n• Vacances de Pâques : avril (2 semaines)\n• Fin d'année : fin juin\nLes dates exactes sont publiées chaque année par le Ministère de l'Éducation Nationale.",
        "category": "calendrier",
        "lang": "fr"
    },
    # ── EXAMENS ──
    {
        "patterns": ["bfem", "brevet", "fin études moyennes"],
        "response": "Le BFEM (Brevet de Fin d'Études Moyennes) :\n• Niveau : fin de 3ème (collège)\n• Épreuves : Français, Mathématiques, Sciences, Histoire-Géographie, Langues vivantes, EPS\n• Se passe en juin\n• Résultats : environ 2 semaines après\n• Permet d'accéder au lycée (seconde)\nSi vous avez des questions sur les matières ou la préparation, je suis là !",
        "category": "examen",
        "lang": "fr"
    },
    {
        "patterns": ["bac", "baccalauréat", "baccalaureat", "terminale"],
        "response": "Le BAC (Baccalauréat) au Sénégal :\n• Niveau : fin de terminale (lycée)\n• Séries : L (Littéraire), S1/S2 (Scientifique), G (Technique)\n• Organisé par l'Office du Bac en juin\n• Coefficient et matières varient selon la série\n• Permet l'accès à l'université\n📞 Office du Bac : www.officedubac.sn\nQuelle série vous intéresse ?",
        "category": "examen",
        "lang": "fr"
    },
    {
        "patterns": ["cfee", "certificat fin études élémentaires", "elementaires", "cm2"],
        "response": "Le CFEE (Certificat de Fin d'Études Élémentaires) :\n• Niveau : fin de CM2 (école primaire)\n• Épreuves : Dictée, Calcul, Rédaction, Lecture\n• Se passe en juin\n• Permet l'entrée en 6ème (collège)\nC'est le premier grand examen national de la scolarité au Sénégal.",
        "category": "examen",
        "lang": "fr"
    },
    # ── ORIENTATION ──
    {
        "patterns": ["orientation", "choisir", "filière", "filiere", "série", "serie", "après bfem", "apres bfem"],
        "response": "Orientation après le BFEM :\n• Série L (Littéraire) : si vous aimez le Français, les langues, la philosophie\n• Série S1 : si vous êtes fort en Maths et Sciences physiques\n• Série S2 : si vous préférez les Sciences naturelles et la Biologie\n• Série G (Gestion) : si vous visez le commerce ou l'administration\n💡 Conseil : choisissez selon vos matières fortes ET votre projet professionnel. Voulez-vous que je vous aide à choisir ?",
        "category": "orientation",
        "lang": "fr"
    },
    {
        "patterns": ["université", "universite", "après bac", "apres bac", "études supérieures", "etudes superieures"],
        "response": "Universités publiques au Sénégal :\n• UCAD (Dakar) : plus grande université, toutes les filières\n• UGB (Saint-Louis) : sciences et lettres\n• UASZ (Ziguinchor) : sciences et technologies\n• UdM (Bambey) : agro-environnement\n• UT (Thiès) : sciences et techniques\n\nAdmission : via le Bac et les concours d'entrée selon la filière.\nPour l'orientation en licence, rendez-vous sur le site du MESRI.",
        "category": "orientation",
        "lang": "fr"
    },
    # ── BOURSES ──
    {
        "patterns": ["bourse", "aide financière", "aide financiere", "allocation", "argent études", "argent etudes"],
        "response": "Les bourses d'études au Sénégal :\n\n🎓 Bourses nationales :\n• FONSIS / CROUS : pour étudiants universitaires\n• Critères : résultats scolaires + situation sociale\n\n📋 Comment postuler :\n1. S'inscrire à l'université d'abord\n2. Déposer dossier au CROUS de votre région\n3. Documents : attestation inscription, extrait naissance, certificat de scolarité parents\n\n🌍 Bourses internationales : via Campus France pour la France.\n\nVoulez-vous plus d'infos sur un type de bourse spécifique ?",
        "category": "bourse",
        "lang": "fr"
    },
    # ── PROGRAMMES ──
    {
        "patterns": ["programme", "matière", "matiere", "cours", "leçon", "lecon", "enseigner", "apprendre"],
        "response": "Les matières principales au Sénégal :\n\n🏫 Primaire (CP → CM2) :\nFrançais, Mathématiques, Sciences, Histoire-Géographie, Éducation civique, EPS, Arts\n\n📚 Collège (6ème → 3ème) :\nFrançais, Mathématiques, Sciences de la vie, Physique-Chimie, Histoire-Géo, Anglais, EPS\n\n🎓 Lycée : dépend de la série choisie.\n\nQuelle matière ou quel niveau vous intéresse ?",
        "category": "programme",
        "lang": "fr"
    },
    # ── DOCUMENTS ADMINISTRATIFS ──
    {
        "patterns": ["certificat scolarité", "certificat de scolarite", "document", "attestation", "diplôme", "diplome"],
        "response": "Documents scolaires courants :\n\n📄 Certificat de scolarité :\n→ Demandez à votre directeur d'école ou proviseur\n→ Gratuit, délivré dans la journée\n\n📄 Relevé de notes :\n→ Fin de trimestre ou fin d'année\n→ Récupérer à l'école\n\n📄 Diplômes (CFEE, BFEM, BAC) :\n→ Retrait à la DEXCO (Direction des Examens et Concours)\n→ Après publication des résultats officiels\n\nQuel document vous faut-il exactement ?",
        "category": "administratif",
        "lang": "fr"
    },
    # ── ENSEIGNANTS ──
    {
        "patterns": ["enseignant", "professeur", "prof", "recrutement", "devenir enseignant", "concours enseignant"],
        "response": "Devenir enseignant au Sénégal :\n\n🎓 Formation :\n• FASTEF (ex-ENS) : pour le secondaire\n• CRFPE (Centres régionaux) : pour le primaire\n• Durée : 2 ans après le BAC ou une licence\n\n📝 Concours :\n• Concours d'entrée à la FASTEF ou CRFPE\n• Organisé chaque année\n• Conditions : BAC minimum\n\n💼 Statut : fonctionnaire après titularisation\n\nVoulez-vous des infos sur le concours ?",
        "category": "enseignant",
        "lang": "fr"
    },
    # ── PRIMAIRE / MATERNELLE ──
    {
        "patterns": ["maternelle", "préscolaire", "prescolaire", "petite section", "enfant", "3 ans", "4 ans", "5 ans"],
        "response": "Éducation préscolaire au Sénégal :\n\n🌱 Cases des tout-petits (CTP) :\n• Pour enfants de 3 à 6 ans\n• Financées par l'État\n• Gratuit dans les zones rurales\n\n🏫 Écoles maternelles :\n• Petite section (3-4 ans)\n• Moyenne section (4-5 ans)\n• Grande section (5-6 ans)\n\nL'inscription se fait directement à l'école la plus proche avec l'extrait de naissance.",
        "category": "prescolaire",
        "lang": "fr"
    },
    # ── PARENTS ──
    {
        "patterns": ["parent", "aider enfant", "suivi scolaire", "résultats enfant", "resultats enfant", "notes enfant"],
        "response": "Conseils pour les parents :\n\n✅ Suivi scolaire :\n• Demandez le carnet de correspondance régulièrement\n• Assistez aux réunions parents-professeurs\n• Vérifiez les cahiers chaque soir\n\n✅ Soutien à la maison :\n• Établir un horaire fixe pour les devoirs\n• Créer un espace calme pour étudier\n• Lire 15 minutes par jour avec votre enfant\n\n📞 Contact école :\nParlez directement au directeur ou au professeur principal en cas de problème.",
        "category": "parents",
        "lang": "fr"
    },
    # ── GÉNÉRAL ──
    {
        "patterns": ["bonjour", "bonsoir", "salut", "hello", "hi", "salam", "assalamu"],
        "response": "Bonjour ! Je suis l'assistant educatif du Ministere de l'Education Nationale du Senegal.\n\nJe peux vous aider sur :\n- Les inscriptions et les examens (CFEE, BFEM, BAC)\n- L'orientation scolaire et les bourses\n- La plateforme PLANETE (connexion, eleves, emploi du temps, notes, bulletins)\n- La carriere des enseignants (mutations, avancements, salaire, conges)\n- Les structures du MEN (IEF, IA, DRH)\n- L'education inclusive, les cantines, les infrastructures\n- Le numerique educatif (PLANETE, MIRADOR, DPTIC)\n\nQuelle est votre question ?",
        "category": "accueil",
        "lang": "fr"
    },
    {
        "patterns": ["merci", "thank", "xéew", "xeew"],
        "response": "De rien, c'est avec plaisir ! N'hésitez pas si vous avez d'autres questions. Bonne continuation dans vos études ! 🎓",
        "category": "accueil",
        "lang": "fr"
    },
    {
        "patterns": ["aide", "help", "je ne sais pas", "je sais pas", "perdu"],
        "response": "Bien sur, je suis la pour vous aider ! Voici ce que je peux faire :\n\n1. Inscriptions, examens (CFEE, BFEM, BAC) et orientation\n2. Bourses et aides financieres\n3. PLANETE : connexion, eleves, emploi du temps, notes, evaluations, bulletins, conseils de classe\n4. Carriere enseignant : mutations, avancements, salaire, conges, retraite\n5. Structures du MEN : IEF, IA, DRH, DPTIC\n6. Documents administratifs et certificats\n7. Education inclusive, cantines, securite scolaire\n8. Numerique educatif : PLANETE, MIRADOR\n9. Daaras, ecoles franco-arabes, education non formelle\n\nPosez votre question !",
        "category": "aide",
        "lang": "fr"
    },
    {
        "patterns": ["wolof", "pulaar", "langue locale"],
        "response": "Support des langues locales :\n\n🇸🇳 Wolof : support partiel disponible (en cours d'amélioration)\n🇸🇳 Pulaar : en développement\n🌍 Arabe : en développement\n\nPour l'instant, posez vos questions en **français** pour une meilleure précision. Le support complet des langues nationales est prévu dans la prochaine version.",
        "category": "langue",
        "lang": "fr"
    },

    # ══════════════════════════════════════════════
    # PLANETE - Plateforme de gestion scolaire
    # ══════════════════════════════════════════════

    # ── PLANETE GÉNÉRAL ──
    {
        "patterns": ["planete", "planète", "plateforme planete", "planete 3", "planete3", "c'est quoi planete", "simen"],
        "response": "PLANETE (version 3.0) est la plateforme officielle de gestion scolaire du Ministere de l'Education nationale du Senegal.\n\nElle permet de :\n- Gerer les eleves (inscriptions, transferts, affectations)\n- Gerer le personnel (import, pointage, dossiers)\n- Construire les emplois du temps\n- Saisir les cahiers de texte et suivre les cours\n- Evaluer les eleves et saisir les notes\n- Organiser les conseils de classe\n- Produire les bulletins\n- Suivre les absences et les incidents\n\nAcces : https://planete3.education.sn\n\nQuelle fonctionnalite vous interesse ?",
        "category": "planete",
        "lang": "fr"
    },

    # ── PLANETE CONNEXION ──
    {
        "patterns": ["connexion planete", "connecter planete", "se connecter planete", "login planete", "mot de passe planete", "acceder planete", "ouvrir planete", "lien planete", "url planete", "adresse planete", "connecter a planete", "connexion a planete"],
        "response": "Pour vous connecter a PLANETE :\n\n1. Ouvrez votre navigateur et allez sur https://planete3.education.sn\n2. Saisissez votre e-mail professionnel (ex : prenom.nom@education.sn)\n3. Cliquez sur Continuer\n4. Saisissez votre mot de passe\n5. Cliquez sur Connexion\n\nSi vous avez oublie votre mot de passe, contactez votre administrateur ou le support technique de votre IEF.\n\nChaque acteur (chef d'etablissement, enseignant, parent) a un acces adapte a son role.",
        "category": "planete_connexion",
        "lang": "fr"
    },
    {
        "patterns": ["mot de passe oublié", "oublié mot de passe", "reinitialiser mot de passe", "password perdu", "je n'arrive pas à me connecter"],
        "response": "Si vous avez oublie votre mot de passe PLANETE :\n\n1. Contactez le chef d'etablissement ou le referent numerique de votre ecole\n2. Il peut reinitialiser votre mot de passe depuis la rubrique Utilisateurs de PLANETE\n3. Si le probleme persiste, contactez le support de votre IEF ou IA\n\nAssurez-vous d'utiliser votre e-mail professionnel (@education.sn) et non un e-mail personnel.",
        "category": "planete_connexion",
        "lang": "fr"
    },

    # ── PLANETE TABLEAU DE BORD ──
    {
        "patterns": ["tableau de bord planete", "dashboard planete", "accueil planete", "indicateurs planete"],
        "response": "Le tableau de bord PLANETE donne une vue rapide de la situation de l'etablissement.\n\nVous pouvez y voir :\n- Les effectifs par classe\n- Les absences du jour\n- Les cours prevus\n- Les evaluations en cours\n- Les demandes de transfert\n- Les messages recus\n- Des raccourcis vers les fonctions principales\n\nLes donnees se mettent a jour en temps reel au fil de la journee.",
        "category": "planete_dashboard",
        "lang": "fr"
    },

    # ── PLANETE ÉTABLISSEMENT ──
    {
        "patterns": ["fiche etablissement", "informations etablissement", "modifier etablissement", "editer fiche", "mise a jour etablissement", "cycle etablissement"],
        "response": "La rubrique Etablissement dans PLANETE permet de consulter et modifier les informations de votre ecole/lycee.\n\nPour acceder a la fiche :\n1. Ouvrez le menu de gauche\n2. Cliquez sur Etablissement\n\nPour modifier les informations :\n1. Cliquez sur le bouton Editer fiche\n2. Modifiez les champs (adresse, contacts, etc.)\n3. Cliquez sur Enregistrer\n\nPour changer le cycle (ex: college vers lycee) :\n- Cliquez sur Mise a jour pour actualiser le cycle et faire apparaitre les niveaux du secondaire.",
        "category": "planete_etablissement",
        "lang": "fr"
    },
    {
        "patterns": ["bst", "bloc scientifique", "polarisation bst", "bloc scientifique et technologique"],
        "response": "La polarisation BST (Bloc Scientifique et Technologique) dans PLANETE :\n\nLes colleges qui envoient leurs eleves de 4eme et 3eme vers un BST doivent le declarer.\n\n1. Allez dans la fiche Etablissement\n2. Choisissez Oui pour indiquer la polarisation\n3. Selectionnez le BST polarisateur dans la liste nationale\n\nCette declaration est obligatoire pour les colleges d'enseignement moyen concernes.",
        "category": "planete_etablissement",
        "lang": "fr"
    },

    # ── PLANETE CONFIGURATION ──
    {
        "patterns": ["configuration planete", "parametrage planete", "configurer planete", "paramètres planete"],
        "response": "La rubrique Configuration de PLANETE permet de parametrer votre etablissement.\n\nVous pouvez configurer :\n- Batiments : creer les batiments de l'ecole\n- Salles : ajouter les salles dans chaque batiment\n- Programmes : voir les disciplines et coefficients\n- Classes pedagogiques : creer les classes\n- Groupage de classes : regrouper des classes\n- Gestion des semestres : activer le 2nd semestre\n- Compte bancaire : renseigner les infos bancaires\n- Scolarite : parametrer les frais d'inscription\n\nQuel parametre souhaitez-vous configurer ?",
        "category": "planete_config",
        "lang": "fr"
    },
    {
        "patterns": ["batiment planete", "ajouter batiment", "creer batiment", "batiments"],
        "response": "Pour creer un batiment dans PLANETE :\n\n1. Allez dans Configuration > Batiments\n2. Cliquez sur Ajouter\n3. Renseignez le type (virtuel, physique ou aire de jeu)\n4. Saisissez le nom du batiment\n5. Les coordonnees sont facultatives\n6. Cliquez sur Enregistrer\n\nUne fois cree, le batiment apparait dans une liste ou vous pouvez le modifier ou le supprimer.",
        "category": "planete_config",
        "lang": "fr"
    },
    {
        "patterns": ["salle planete", "ajouter salle", "creer salle", "salles de classe"],
        "response": "Pour creer une salle dans PLANETE :\n\n1. Allez dans Configuration > Salle\n2. Cliquez sur Ajouter\n3. Selectionnez le batiment\n4. Choisissez le type de salle (classe, labo, bureau...)\n5. Saisissez le nom et les dimensions (longueur/largeur)\n6. Cliquez sur Enregistrer\n\nApres creation, vous pouvez indiquer les equipements de la salle, la modifier ou la supprimer.",
        "category": "planete_config",
        "lang": "fr"
    },
    {
        "patterns": ["classe pedagogique", "creer classe", "ajouter classe", "classes planete", "supprimer classe"],
        "response": "Pour creer une classe pedagogique dans PLANETE :\n\n1. Allez dans Configuration > Classe pedagogique\n2. Cliquez sur Ajouter\n3. Renseignez le niveau, la serie, le nom de la classe et la salle\n4. Cliquez sur Enregistrer\n\nApres creation, il faut affecter :\n- Les professeurs de la classe\n- Le surveillant\n- L'eleve responsable\n\n⚠️ Attention : la suppression d'une classe entraine la suppression des affectations des eleves, des professeurs et de l'emploi du temps. C'est irreversible !",
        "category": "planete_config",
        "lang": "fr"
    },
    {
        "patterns": ["groupage classe", "regrouper classes", "lv2", "disciplines optionnelles groupage"],
        "response": "Le groupage de classes dans PLANETE permet de regrouper 2 classes tenues par un meme professeur dans une seule salle.\n\nC'est utile pour :\n- Les disciplines optionnelles (LV2)\n- Les classes de series differentes avec des disciplines communes (francais/franco-arabe, S1/S2)\n\nPour grouper :\n1. Allez dans Configuration > Groupage classe\n2. Cliquez sur le bouton +\n3. Renseignez le libelle, le niveau, la discipline et le professeur\n4. Enregistrez puis liez les classes concernees.",
        "category": "planete_config",
        "lang": "fr"
    },
    {
        "patterns": ["semestre planete", "activer semestre", "second semestre", "2eme semestre", "gestion semestres"],
        "response": "La gestion des semestres dans PLANETE :\n\n- Le 1er semestre est active par defaut\n- Pour activer le 2nd semestre :\n  1. Allez dans Configuration > Gestion des semestres\n  2. Cliquez sur la carte Second Semestre\n  3. Cliquez sur Activer\n  4. Precisez la date de debut du 2nd semestre\n\nSi vous devez modifier la date :\n- Cliquez d'abord sur Purger pour effacer l'ancienne date\n- Puis saisissez la nouvelle date.",
        "category": "planete_config",
        "lang": "fr"
    },
    {
        "patterns": ["scolarite planete", "frais scolarite", "paiement scolarite", "parametrage scolarite", "frais inscription planete"],
        "response": "Parametrage des frais de scolarite dans PLANETE :\n\n1. Allez dans Configuration > Parametrage scolarite > Ajouter\n2. Choisissez le mode de facturation :\n   - Par rubrique (tenue, GOSCO, IME, examen...)\n   - Ou montant unique (inscription)\n3. Fixez le montant\n4. Definissez les echeances (paiement a la rentree ou differe)\n5. Vous pouvez facturer par niveau (6e, 5e, 4e...) ou par cycle\n\nCela permet de suivre les inscriptions et les paiements des eleves.",
        "category": "planete_config",
        "lang": "fr"
    },
    {
        "patterns": ["compte bancaire planete", "rib planete", "banque etablissement"],
        "response": "Pour ajouter le compte bancaire de l'etablissement dans PLANETE :\n\n1. Allez dans Configuration > Compte bancaire\n2. Cliquez sur Ajouter\n3. Renseignez : code banque, code guichet, numero compte, RIB, nom banque\n4. Cliquez sur Enregistrer\n\nChaque etablissement dispose d'un identifiant unique (IEN) pour le suivi financier.",
        "category": "planete_config",
        "lang": "fr"
    },
    {
        "patterns": ["programme planete", "disciplines planete", "coefficients", "credits horaires", "disciplines obligatoires", "disciplines optionnelles"],
        "response": "Les programmes dans PLANETE :\n\nAllez dans Configuration > Programme pour voir les disciplines du cycle.\n\nCliquez sur Discipline pour afficher les coefficients et credits horaires.\n\nIl y a deux blocs :\n- Disciplines obligatoires : une fois cochees, elles s'appliquent a tous les eleves\n- Disciplines optionnelles : apres les avoir cochees, il faut les affecter individuellement aux eleves qui les ont choisies\n\nLes coefficients et credits horaires sont pre-programmes par le Ministere.",
        "category": "planete_config",
        "lang": "fr"
    },

    # ── PLANETE PERSONNEL ──
    {
        "patterns": ["personnel planete", "import personnel", "agents planete", "enseignants planete", "mirador", "mise a jour personnel"],
        "response": "La gestion du personnel dans PLANETE :\n\nPLANETE distingue 2 categories :\n- Agents titulaires : importes depuis MIRADOR via le bouton Mis a Jour Personnel\n- Complements horaires : importes via le bouton Complement horaire (saisir l'IEN ou l'email)\n\nApres import :\n1. Consultez la liste du personnel\n2. Procedez au pointage (date de prise de service)\n3. Accedez au dossier de chaque agent\n\nLe dossier agent contient : fiche, infos administratives, emploi du temps, rubriques de suivi.",
        "category": "planete_personnel",
        "lang": "fr"
    },
    {
        "patterns": ["pointage personnel", "pointage planete", "prise de service", "pointer agent"],
        "response": "Le pointage du personnel dans PLANETE :\n\n1. Affichez la liste des agents\n2. Cliquez sur le bouton Pointage\n3. Indiquez la date de prise de service de chaque agent\n\nLe pointage doit etre fait en debut d'annee scolaire pour tous les agents de l'etablissement.\n\nC'est une etape obligatoire apres l'importation du personnel.",
        "category": "planete_personnel",
        "lang": "fr"
    },
    {
        "patterns": ["complement horaire", "complément horaire", "agent autre etablissement"],
        "response": "Pour importer un complement horaire dans PLANETE :\n\nCe sont les enseignants qui viennent d'un autre etablissement pour completer leur service.\n\n1. Cliquez sur le bouton Complement horaire\n2. Saisissez l'IEN ou l'e-mail de l'agent\n3. Dans le dossier qui s'affiche, completez :\n   - Numero de l'OS (Ordre de Service)\n   - Date de l'OS\n   - Date de prise de service\n4. Enregistrez",
        "category": "planete_personnel",
        "lang": "fr"
    },
    {
        "patterns": ["dossier agent", "fiche agent", "archiver agent", "archivage personnel"],
        "response": "Le dossier agent dans PLANETE comprend :\n\n- Identification et contact (colonne gauche)\n- Fiche agent : date/lieu de naissance, fonction, specialite, diplomes, corps, grade, telephone, email\n- Rubriques de suivi (bloc Dossier)\n- Emploi du temps de l'agent\n\nActions possibles :\n- Mettre a jour : synchroniser avec MIRADOR\n- Edition : modifier les informations\n- Archiver : retirer un agent qui n'est plus en service (choisir type de sortie + date + observation)\n- Naviguer entre les dossiers avec Precedent / Suivant",
        "category": "planete_personnel",
        "lang": "fr"
    },

    # ── PLANETE ÉLÈVES ──
    {
        "patterns": ["eleves planete", "gestion eleves", "module eleves", "dossier eleve", "fiche eleve"],
        "response": "Le module Eleves de PLANETE permet de :\n\n- Inscrire de nouveaux eleves\n- Gerer les transferts (entrants et sortants)\n- Affecter les eleves aux classes\n- Importer des eleves par fichier Excel\n- Gerer les examens d'entree et reprises de scolarite\n- Consulter les dossiers individuels (identite, notes, absences, parcours)\n- Generer les certificats de scolarite, quitus bibliotheque, autorisations d'absence\n\nLe tableau de bord affiche les effectifs, les redoublants et les eleves sans acte d'etat civil.",
        "category": "planete_eleves",
        "lang": "fr"
    },
    {
        "patterns": ["transfert eleve", "transfert entrant", "transfert sortant", "demande transfert", "transferer eleve", "transfert d'eleve", "transfert", "transférer"],
        "response": "Les transferts d'eleves dans PLANETE :\n\n📥 Transfert entrant (eleve qui arrive) :\n1. Allez dans Eleves > Transfert entrant\n2. Consultez les demandes recues\n3. Verifiez le profil, l'etablissement d'origine et le motif\n4. Cliquez sur Accepter transfert ou Rejeter transfert\n\n📤 Transfert sortant (eleve qui part) :\n1. Allez dans Eleves > Transfert sortant\n2. Cliquez sur + pour creer une demande\n3. Saisissez l'IEN de l'eleve\n4. Renseignez l'IA d'accueil, l'IEF d'accueil, l'etablissement d'accueil et le motif\n5. Validez la demande\n\nLe transfert suit un circuit de validation : etablissement d'origine > IA origine > IA accueil > etablissement accueil.",
        "category": "planete_eleves",
        "lang": "fr"
    },
    {
        "patterns": ["affectation eleve", "affecter eleve", "eleve non affecte", "rattacher classe"],
        "response": "Pour affecter des eleves a une classe dans PLANETE :\n\n1. Allez dans Eleves > Affectation Eleves\n2. Vous verrez le nombre d'eleves non affectes par niveau\n3. Cliquez sur le niveau concerne (6e, 5e, 4e, 3e, 2nde, 1ere, Tle)\n4. Cochez le(s) eleve(s) a affecter\n5. Selectionnez la classe d'accueil dans la liste deroulante\n6. Cliquez sur Affecter",
        "category": "planete_eleves",
        "lang": "fr"
    },
    {
        "patterns": ["import eleves", "importer eleves", "fichier excel eleves", "template import", "template xlsx"],
        "response": "Pour importer des eleves par fichier Excel dans PLANETE :\n\n1. D'abord telecharger le template :\n   - Allez dans Eleves > Template xlsx\n   - Telechargez le modele Excel\n\n2. Remplissez le fichier avec les donnees des eleves\n\n3. Chargez le fichier :\n   - Allez dans Eleves > Import eleves\n   - Selectionnez le niveau et la classe\n   - Choisissez le fichier Excel rempli\n   - Cliquez sur Charger\n\n4. Verifiez les donnees affichees (IEN, nom, prenom, date de naissance...)\n5. Cliquez sur Enregistrer & Continuer",
        "category": "planete_eleves",
        "lang": "fr"
    },
    {
        "patterns": ["ien", "identifiant education nationale", "identifiant eleve", "numero ien"],
        "response": "L'IEN (Identifiant de l'Education Nationale) est un numero unique attribue a chaque eleve dans le systeme educatif senegalais.\n\nIl sert a :\n- Identifier l'eleve de maniere unique dans PLANETE\n- Rechercher un eleve pour les transferts, inscriptions, reprises de scolarite\n- Suivre le parcours scolaire de l'eleve\n\nL'IEN est utilise dans presque toutes les operations de PLANETE : transferts, examens d'entree, import, inscription, etc.",
        "category": "planete_eleves",
        "lang": "fr"
    },
    {
        "patterns": ["examen entree", "examen d'entree", "concours entree"],
        "response": "L'examen d'entree dans PLANETE :\n\n1. Allez dans Eleves > Examen d'entree\n2. Saisissez l'IEN ou l'identifiant de l'eleve\n3. Cliquez sur Rechercher\n4. Le dossier de l'eleve s'affiche\n5. Poursuivez le traitement de la demande d'inscription\n\nCette procedure est reservee aux candidats soumis a l'examen d'entree dans l'etablissement.",
        "category": "planete_eleves",
        "lang": "fr"
    },
    {
        "patterns": ["reprise scolarite", "reinscription", "retour ecole", "reprendre etudes"],
        "response": "La reprise de scolarite dans PLANETE :\n\n1. Allez dans Eleves > Reprise Scolarite\n2. Recherchez l'eleve par son IEN\n3. Cliquez sur Rechercher\n4. Le dossier de l'eleve s'affiche\n5. Engagez la procedure de reinscription\n\nCette fonction est destinee aux eleves qui reprennent leurs etudes apres une interruption.",
        "category": "planete_eleves",
        "lang": "fr"
    },
    {
        "patterns": ["candidats bfem", "bfem planete", "inscription bfem"],
        "response": "La rubrique Candidats BFEM dans PLANETE donne acces aux operations relatives aux eleves concernes par l'examen du BFEM.\n\nDepuis le tableau de bord du module Eleves, cliquez sur l'icone Candidats BFEM pour ouvrir cette fonctionnalite et gerer les inscriptions a l'examen.",
        "category": "planete_eleves",
        "lang": "fr"
    },
    {
        "patterns": ["inscription planete", "nouvelle inscription planete", "paiement inscription", "suivi inscriptions"],
        "response": "Les inscriptions dans PLANETE :\n\nLa rubrique Inscriptions permet de suivre les operations et les montants.\n\nVous pouvez voir :\n- Les inscriptions du jour et le montant du jour\n- Le total des inscrits et le montant total\n- Des graphiques par objet et mode de paiement\n\nPour enregistrer une inscription :\n1. Cliquez sur Ajouter une inscription\n2. Saisissez l'IEN de l'eleve > Rechercher\n3. Renseignez le montant, le mode de paiement et la date\n4. Cliquez sur Enregistrer\n\nVous pouvez filtrer par date avec les champs Du et Au puis Actualiser.",
        "category": "planete_eleves",
        "lang": "fr"
    },
    {
        "patterns": ["certificat scolarite planete", "quitus bibliotheque", "autorisation absence planete", "documents eleve planete"],
        "response": "Les documents administratifs dans PLANETE :\n\nDepuis le dossier d'un eleve ou la liste des eleves, vous pouvez generer :\n- Certificat de scolarite\n- Quitus bibliotheque\n- Autorisation d'absence\n\nCes documents sont accessibles via les boutons en haut du dossier de l'eleve ou dans la colonne Documents administratifs de la liste des eleves.",
        "category": "planete_eleves",
        "lang": "fr"
    },

    # ── PLANETE EMPLOI DU TEMPS ──
    {
        "patterns": ["emploi du temps", "emploi temps planete", "edt", "grille horaire", "planning cours", "emploi temps", "horaire", "planning"],
        "response": "L'emploi du temps dans PLANETE :\n\nPour construire un emploi du temps :\n1. Allez dans la rubrique Emploi du temps\n2. Selectionnez la classe\n3. Faites glisser un enseignant depuis le panneau lateral vers une cellule de la grille\n4. Choisissez la duree (1h ou 2h)\n5. Cliquez sur Enregistrer\n\nAstuces :\n- Double-cliquez sur un cours pour le supprimer\n- Cliquez sur le nom d'un enseignant place pour ajuster la duree\n- Utilisez Export EDT ou Export cours pour telecharger\n\nVous pouvez aussi utiliser le bouton Generer EDT pour une generation automatique par niveau.",
        "category": "planete_edt",
        "lang": "fr"
    },
    {
        "patterns": ["generer emploi temps", "generation automatique", "generer edt"],
        "response": "La generation automatique de l'emploi du temps dans PLANETE :\n\n1. Cliquez sur le bouton Generer EDT\n2. L'ecran affiche les niveaux de l'etablissement (6eme a Terminale)\n3. Cliquez sur le niveau souhaite pour lancer la generation\n\nLe systeme genere automatiquement l'emploi du temps en tenant compte des enseignants affectes et des salles disponibles.",
        "category": "planete_edt",
        "lang": "fr"
    },

    # ── PLANETE COURS ──
    {
        "patterns": ["cours planete", "cahier texte", "cahier de texte", "saisir cours", "gestion cours"],
        "response": "Le module Cours de PLANETE permet de :\n- Renseigner les cahiers de texte\n- Suivre la progression pedagogique\n- Enregistrer les absences et retards des eleves\n\nPour saisir un cahier de texte :\n1. Allez dans Cours > Cours\n2. Repérez le cours dans la liste du jour\n3. Cliquez sur Cahier texte\n4. Selectionnez le type d'activite\n5. Decrivez le deroulement\n6. Verifiez les heures prevues et reelles\n7. Cliquez sur Enregistrer\n\nLe Dashboard Cours affiche les cours prevus, termines, les absences et le taux d'execution.",
        "category": "planete_cours",
        "lang": "fr"
    },
    {
        "patterns": ["absence eleve planete", "retard eleve", "absences cours", "justifier absence", "absence non justifiee", "absence", "retard", "absent", "absences"],
        "response": "La gestion des absences dans PLANETE :\n\nEnregistrer une absence :\n1. Dans Cours > Cours, cliquez sur le bouton rouge au bout de la ligne du cours\n2. Activez Retards ou Absences pour chaque eleve concerne\n\nSuivre les absences :\n- Allez dans Cours > Absences pour voir la synthese mensuelle\n- Chaque mois affiche : nb absences, absences justifiees, retards, taux de justification\n- Utilisez Exporter pour extraire les donnees\n\nJustifier une absence :\n1. Cliquez sur Justifier absence\n2. Recherchez l'eleve par son IEN\n3. Selectionnez l'absence non justifiee\n4. Saisissez les details de justification\n5. Cliquez sur Valider",
        "category": "planete_cours",
        "lang": "fr"
    },

    # ── PLANETE RAPPORT FIN DE JOURNÉE ──
    {
        "patterns": ["rapport fin journee", "rapport journalier", "fin de journee", "incident planete", "declarer incident"],
        "response": "Le rapport de fin de journee dans PLANETE :\n\nPermet de renseigner les activites et faits marquants de la journee.\n\nDashboard :\n- Classes par niveau (colonne gauche)\n- Absences du personnel (zone centrale)\n- Incidents enregistres (panneau droit)\n\nSaisir une absence du personnel :\n- Ouvrez le rapport du jour d'une classe\n- Cliquez sur l'icone en face d'un cours\n- Precisez le type d'absence, l'observation, la date et l'horaire\n\nDeclarer un incident :\n1. Cliquez sur la classe concernee\n2. Cliquez sur Declarer un incident\n3. Decrivez le fait observe\n4. Cliquez sur Enregistrer",
        "category": "planete_rapport",
        "lang": "fr"
    },

    # ── PLANETE ÉVALUATIONS ──
    {
        "patterns": ["evaluation planete", "evaluer planete", "ajouter evaluation", "saisir notes", "saisir les notes", "notation planete", "notes planete", "noter eleves", "notes eleves", "evaluation", "devoir", "composition"],
        "response": "Les evaluations dans PLANETE :\n\nAjouter une evaluation :\n1. Allez dans Evaluations\n2. Selectionnez la classe\n3. Cliquez sur Ajouter\n4. Renseignez : semestre, salle, type d'evaluation, date, discipline, matiere, professeur, heures debut/fin\n5. Cliquez sur Enregistrer\n\nSaisir les notes :\n1. Dans la liste des evaluations, cliquez sur Notation\n2. Saisissez la note de chaque eleve\n3. Indiquez les exemptions et absences si necessaire\n4. Validez\n\nLe dashboard affiche : evaluations planifiees, en attente, partielles, completes et les alertes de performance.",
        "category": "planete_evaluations",
        "lang": "fr"
    },

    # ── PLANETE CONSEILS DE CLASSE ──
    {
        "patterns": ["conseil de classe", "conseils classes", "planifier conseil", "appreciations", "conseil classe", "appreciation", "saisir appreciations"],
        "response": "Les conseils de classe dans PLANETE :\n\nPlanifier un conseil :\n1. Allez dans Conseils classes\n2. Selectionnez la classe\n3. Cliquez sur Ajouter\n4. Choisissez le semestre\n5. Renseignez la date de generation et la date de tenue\n6. Cliquez sur Enregistrer\n\nSaisir les appreciations :\n1. Cliquez sur l'icone Conseil\n2. Pour chaque eleve : consultez moyennes, rang, absences\n3. Saisissez l'appreciation et l'observation\n4. Naviguez avec Precedent/Suivant\n5. Apres le dernier eleve, cliquez sur Valider conseil\n\nActions disponibles : Conseil, Bulletins, Statistiques, Regenerer, Archiver, Supprimer.",
        "category": "planete_conseils",
        "lang": "fr"
    },
    # ── PLANETE BULLETINS ──
    {
        "patterns": ["bulletin", "bulletins", "bulletin de notes", "bulletin planete", "imprimer bulletin", "generer bulletin", "bulletin eleve", "bulletin scolaire", "releve de notes"],
        "response": "Les bulletins de notes dans PLANETE :\n\nPour generer les bulletins :\n1. Allez dans Conseils classes\n2. Selectionnez la classe concernee\n3. Cliquez sur l'icone Bulletins\n4. Les bulletins sont generes automatiquement a partir des notes saisies\n5. Vous pouvez les telecharger ou les imprimer\n\nLe bulletin contient :\n- Les moyennes par matiere\n- La moyenne generale\n- Le rang de l'eleve\n- Les appreciations du conseil de classe\n- Les absences\n\nAssurez-vous que toutes les notes sont saisies et le conseil valide avant de generer les bulletins.",
        "category": "planete_bulletins",
        "lang": "fr"
    },

    # ── PLANETE UTILISATEURS ──
    {
        "patterns": ["utilisateur planete", "ajouter utilisateur", "creer compte planete", "gestion utilisateurs", "profil utilisateur"],
        "response": "La gestion des utilisateurs dans PLANETE :\n\nConsulter les utilisateurs :\n- Allez dans le menu Utilisateurs\n- La liste affiche les comptes, profils, emails et statuts\n\nAjouter un utilisateur :\n1. Cliquez sur le bouton + (Ajouter)\n2. Saisissez l'IEN ou l'e-mail professionnel de l'agent\n3. Cliquez sur IEN / Email pro\n4. Le formulaire affiche les infos : matricule, prenom, nom, etc.\n5. Selectionnez le profil a attribuer\n6. Renseignez le mot de passe initial\n7. Activez Autre structure si necessaire\n8. Cliquez sur Enregistrer",
        "category": "planete_utilisateurs",
        "lang": "fr"
    },

    # ══════════════════════════════════════════════
    # DOMAINES DU MINISTÈRE DE L'ÉDUCATION
    # ══════════════════════════════════════════════

    # ── MUTATIONS / AFFECTATIONS ENSEIGNANTS ──
    {
        "patterns": ["mutation", "affectation enseignant", "demande mutation", "changer etablissement", "muter"],
        "response": "Les mutations et affectations des enseignants :\n\nLa demande de mutation se fait generalement :\n1. Aupres de votre IEF (Inspection de l'Education et de la Formation)\n2. En remplissant le formulaire de demande de mutation\n3. Les mutations sont traitees par la DRH du Ministere\n4. Les mouvements sont prononces chaque annee (generalement avant la rentree)\n\nDocuments necessaires :\n- Demande manuscrite adressee au Ministre\n- Certificat de prise de service\n- Arrete de nomination ou OS\n\nPour les affectations des nouveaux enseignants, elles sont gerees par la DAGE et la DRH.",
        "category": "men_mutations",
        "lang": "fr"
    },

    # ── AVANCEMENT / CARRIÈRE ──
    {
        "patterns": ["avancement", "echelon", "grade", "reclassement", "carriere", "indice", "anciennete"],
        "response": "L'avancement de carriere des enseignants au Senegal :\n\nTypes d'avancement :\n- Avancement d'echelon : automatique tous les 2 ans selon l'anciennete\n- Avancement de grade : par concours professionnel ou au choix\n- Reclassement : apres obtention d'un nouveau diplome\n\nPour suivre votre avancement :\n- Consultez votre bulletin de solde (echelon actuel)\n- Contactez la DRH du Ministere\n- Verifiez sur MIRADOR (si vous avez acces)\n\nLes avancements sont geres par la Direction des Ressources Humaines (DRH) du MEN.",
        "category": "men_carriere",
        "lang": "fr"
    },

    # ── SALAIRE / SOLDE ──
    {
        "patterns": ["salaire", "solde", "bulletin solde", "paie", "paiement salaire", "retard salaire", "prime", "indemnite", "salaire enseignant", "combien gagne enseignant"],
        "response": "Questions sur la solde des enseignants :\n\n- Le bulletin de solde est disponible sur la plateforme du Tresor Public ou aupres de la Solde\n- Pour tout probleme de paiement (retard, erreur, suspension) :\n  1. Contactez d'abord votre IEF\n  2. Puis la Direction de la Solde au Ministere des Finances\n  3. La DRH du MEN peut aussi intervenir\n\nIndemnites courantes :\n- Indemnite de logement\n- Indemnite de sujétion\n- Prime de rendement\n- Indemnite de zone (pour les zones difficiles)\n\nLes primes et indemnites dependent du corps, du grade et de la zone d'affectation.",
        "category": "men_solde",
        "lang": "fr"
    },

    # ── FORMATION CONTINUE ──
    {
        "patterns": ["formation continue", "formation enseignant", "recyclage", "renforcement capacites", "cellule pedagogique", "seminaire"],
        "response": "La formation continue des enseignants :\n\n📚 Cellules pedagogiques :\n- Reunions regulieres entre enseignants d'une meme discipline\n- Organisees par les IEF et les IA\n- Echanges de pratiques et mise a jour des connaissances\n\n🎓 Formations organisees :\n- Par le MEN (seminaires nationaux)\n- Par les IA et IEF (formations regionales/locales)\n- Par les partenaires (ONG, UNESCO, etc.)\n\n💻 Formations numeriques :\n- Formations PLANETE pour les chefs d'etablissement\n- Formations aux outils numeriques\n- Formations en ligne (MOOC)\n\nRenseignez-vous aupres de votre IEF pour le calendrier des formations.",
        "category": "men_formation",
        "lang": "fr"
    },

    # ── IEF / IA / STRUCTURES ──
    {
        "patterns": ["ief", "inspection education", "ia academie", "inspection academique", "inspecteur", "structure men"],
        "response": "Les structures du Ministere de l'Education Nationale :\n\n🏛️ Niveau central :\n- Le Cabinet du Ministre\n- Les Directions (DRH, DAGE, DEE, DEMSG, DPRE, etc.)\n- La DPTIC (Technologies de l'Information)\n\n📍 Niveau regional :\n- IA (Inspections d'Academie) : 16 dans le pays\n- Dirigees par les Inspecteurs d'Academie\n\n📍 Niveau local :\n- IEF (Inspections de l'Education et de la Formation)\n- Dirigees par les IEF\n- Premier interlocuteur pour les enseignants et etablissements\n\nPour toute demarche administrative, commencez par contacter votre IEF.",
        "category": "men_structures",
        "lang": "fr"
    },

    # ── CONGÉS / PERMISSIONS ──
    {
        "patterns": ["congé", "conge", "permission", "absence enseignant", "autorisation absence enseignant", "maladie enseignant", "maternite"],
        "response": "Les conges et permissions pour les enseignants :\n\n📋 Types de conges :\n- Conge annuel : pendant les vacances scolaires\n- Conge de maladie : avec certificat medical (courte ou longue duree)\n- Conge de maternite : 14 semaines (6 avant + 8 apres l'accouchement)\n- Permission d'absence : max 15 jours/an pour evenements familiaux\n\n📝 Procedure :\n1. Adressez une demande ecrite au chef d'etablissement\n2. Le chef d'etablissement transmet a l'IEF\n3. L'IEF transmet a l'IA pour decision\n\nPour les conges de maladie de longue duree, un avis du Conseil de sante est necessaire.",
        "category": "men_conges",
        "lang": "fr"
    },

    # ── RETRAITE ──
    {
        "patterns": ["retraite", "pension", "depart retraite", "fin carriere", "ipres", "fnr"],
        "response": "La retraite des enseignants fonctionnaires :\n\n📅 Age de depart :\n- 60 ans pour les enseignants du corps des fonctionnaires\n- Possibilite de prolongation dans certains cas\n\n📋 Demarches :\n1. Constitution du dossier de retraite (2 ans avant la date prevue)\n2. Pieces : acte de naissance, arrete de nomination, derniers bulletins de solde\n3. Deposer le dossier a la DRH du MEN\n4. Le FNR (Fonds National de Retraite) traite la pension\n\n💰 Pension :\n- Calculee en fonction de l'anciennete et du dernier indice\n- Versee mensuellement par le FNR\n\nContactez la DRH du MEN pour toute question sur votre dossier de retraite.",
        "category": "men_retraite",
        "lang": "fr"
    },

    # ── SYNDICATS / DROITS ──
    {
        "patterns": ["syndicat", "droit enseignant", "greve", "revendication", "statut enseignant"],
        "response": "Droits et statut des enseignants :\n\nLes enseignants au Senegal sont regis par :\n- Le Statut General des Fonctionnaires\n- Les statuts particuliers des corps d'enseignement\n\nDroits fondamentaux :\n- Droit syndical et droit de greve\n- Droit a la formation continue\n- Droit a l'avancement\n- Protection dans l'exercice de leurs fonctions\n\nPrincipaux syndicats :\n- SYPROS, CUSEMS, SAEMSS, UDEN, SELS, SNELAS...\n\nPour toute question sur vos droits, rapprochez-vous de votre syndicat ou de la DRH du MEN.",
        "category": "men_droits",
        "lang": "fr"
    },

    # ── PROJET D'ÉCOLE / PROJET D'ÉTABLISSEMENT ──
    {
        "patterns": ["projet ecole", "projet etablissement", "plan amelioration", "pae", "comite de gestion", "cge"],
        "response": "Le Projet d'Ecole / Projet d'Etablissement :\n\nChaque etablissement doit elaborer un projet qui definit :\n- Les objectifs pedagogiques prioritaires\n- Les strategies d'amelioration\n- Le plan d'action annuel\n\nLe CGE (Comite de Gestion de l'Ecole) :\n- Organe de gouvernance de l'etablissement\n- Compose du chef d'etablissement, des enseignants, des parents et des eleves\n- Gere les fonds de l'etablissement\n- Approuve le budget et le projet d'ecole\n\nLe PAE (Plan d'Amelioration de l'Ecole) est un outil de pilotage pour atteindre les objectifs fixes.",
        "category": "men_projet",
        "lang": "fr"
    },

    # ── ÉDUCATION INCLUSIVE ──
    {
        "patterns": ["handicap", "inclusion", "education inclusive", "eleve handicape", "besoins speciaux", "special"],
        "response": "L'education inclusive au Senegal :\n\nLe Ministere promeut l'inclusion de tous les enfants, y compris ceux en situation de handicap.\n\nDispositifs existants :\n- Classes inclusives dans les ecoles ordinaires\n- Assistants de vie scolaire dans certains etablissements\n- Adaptation des examens pour les eleves en situation de handicap\n- Etablissements specialises (INEFJA, centres d'education specialisee)\n\nDans PLANETE :\n- Le dossier eleve permet de renseigner le type de handicap\n- Le champ Exemption EPS permet de dispenser un eleve\n\nContactez votre IEF pour les dispositifs disponibles dans votre zone.",
        "category": "men_inclusion",
        "lang": "fr"
    },

    # ── CANTINE / ALIMENTATION SCOLAIRE ──
    {
        "patterns": ["cantine", "alimentation scolaire", "repas ecole", "dcej", "nourriture"],
        "response": "L'alimentation scolaire au Senegal :\n\nLa DCEJ (Division des Cantines et de l'Education a la Jeunesse) gere les cantines scolaires.\n\nProgramme national :\n- Cantines scolaires dans les ecoles primaires (surtout en zone rurale)\n- Financees par l'Etat et les partenaires (PAM, etc.)\n- Repas gratuits pour les eleves\n\nPour les etablissements :\n- Le CGE peut organiser une cantine communautaire\n- Les parents d'eleves peuvent contribuer\n- L'IEF coordonne la distribution dans sa zone\n\nPour toute question sur la cantine de votre ecole, contactez le directeur ou votre IEF.",
        "category": "men_cantine",
        "lang": "fr"
    },

    # ── VIOLENCE / SÉCURITÉ SCOLAIRE ──
    {
        "patterns": ["violence", "securite", "agression", "harcelement", "discipline", "punition", "exclusion", "sanction"],
        "response": "Securite et discipline scolaire :\n\n🚫 En cas de violence ou harcelement :\n1. Signalez immediatement au chef d'etablissement\n2. Le chef d'etablissement saisit l'IEF\n3. Un proces-verbal est dresse\n4. En cas de gravite, saisir les autorites judiciaires\n\n📋 Sanctions disciplinaires (Reglement interieur) :\n- Avertissement\n- Blame\n- Exclusion temporaire (conseil de discipline)\n- Exclusion definitive (conseil de discipline)\n\nDans PLANETE, les incidents peuvent etre declares via le Rapport de fin de journee.\n\nLe Ministere a mis en place un numero vert pour signaler les cas de violence en milieu scolaire.",
        "category": "men_securite",
        "lang": "fr"
    },

    # ── FOURNITURES / MANUELS ──
    {
        "patterns": ["manuel scolaire", "livre", "fourniture", "materiel", "equipement scolaire"],
        "response": "Manuels et fournitures scolaires :\n\n📚 Manuels scolaires :\n- Les manuels sont fournis par le Ministere via les IA et IEF\n- Distribution gratuite dans les ecoles publiques\n- La liste des manuels agrees est fixee par arrete ministeriel\n\n🎒 Fournitures :\n- La liste des fournitures est communiquee en debut d'annee\n- Certaines ONG distribuent des kits scolaires en zone rurale\n\n💻 Equipement numerique :\n- Le MEN equipe progressivement les etablissements en materiel informatique\n- Les BST disposent d'equipements scientifiques et technologiques\n\nContactez votre IEF pour les dotations en manuels de votre etablissement.",
        "category": "men_fournitures",
        "lang": "fr"
    },

    # ── CONSTRUCTION / INFRASTRUCTURE ──
    {
        "patterns": ["construction", "infrastructure", "nouveau batiment", "rehabilitation", "salle classe", "toilettes", "eau", "electricite"],
        "response": "Infrastructures scolaires :\n\nPour les constructions et rehabilitations :\n- La DAGE (Direction de l'Administration Generale et de l'Equipement) gere les constructions\n- L'IA et l'IEF transmettent les besoins des etablissements\n- Les projets sont finances par l'Etat et les partenaires (BM, BAD, JICA, etc.)\n\nPour signaler un besoin :\n1. Le chef d'etablissement fait un rapport a l'IEF\n2. L'IEF transmet a l'IA\n3. L'IA inclut dans la programmation regionale\n\nLes CGE peuvent aussi financer des petits travaux avec leurs fonds propres.\n\nDans PLANETE, les batiments et salles sont declares dans la rubrique Configuration.",
        "category": "men_infrastructure",
        "lang": "fr"
    },

    # ── DAARA / ÉDUCATION RELIGIEUSE ──
    {
        "patterns": ["daara", "ecole coranique", "education religieuse", "franco-arabe", "arabe"],
        "response": "Les daaras et l'education religieuse au Senegal :\n\n🕌 Daaras modernises :\n- Le Ministere a lance un programme de modernisation des daaras\n- Integration du programme scolaire national + enseignement coranique\n- Les daaras modernises sont reconnus par l'Etat\n\n📚 Ecoles franco-arabes :\n- Combinent enseignement en francais et en arabe\n- Programmes reconnus par le MEN\n- Examens specifiques (CFEE, BFEM en franco-arabe)\n\nDans PLANETE, les programmes franco-arabes sont disponibles dans la rubrique Configuration > Programme.\n\nPour plus d'infos, contactez la Direction de l'Enseignement Arabe du MEN.",
        "category": "men_daara",
        "lang": "fr"
    },

    # ── ÉDUCATION NON FORMELLE / ALPHABÉTISATION ──
    {
        "patterns": ["alphabetisation", "education non formelle", "adulte", "analphabete", "ecole communautaire"],
        "response": "L'education non formelle et l'alphabetisation :\n\nLa DAENF (Direction de l'Alphabetisation et de l'Education Non Formelle) gere :\n\n- Programmes d'alphabetisation en langues nationales\n- Ecoles communautaires de base (ECB)\n- Formation professionnelle de base\n- Cours du soir pour adultes\n\nPublic cible :\n- Adultes non scolarises\n- Jeunes decrocheurs\n- Femmes et filles hors du systeme\n\nPour trouver un centre d'alphabetisation, contactez votre IEF ou la DAENF au niveau central.",
        "category": "men_alphabetisation",
        "lang": "fr"
    },

    # ── PARTENARIATS / COOPÉRATION ──
    {
        "patterns": ["partenaire", "ong", "cooperation", "unesco", "unicef", "banque mondiale", "projet education"],
        "response": "Partenariats et cooperation dans l'education :\n\nPrincipaux partenaires du MEN :\n- UNESCO : appui technique et normatif\n- UNICEF : education de base, kits scolaires, eau et assainissement\n- Banque mondiale : financement de projets structurants\n- BAD (Banque Africaine de Developpement)\n- AFD (Agence Francaise de Developpement)\n- JICA (Cooperation japonaise)\n- USAID\n- ONG nationales et internationales\n\nCes partenaires appuient la construction d'ecoles, la formation des enseignants, les cantines scolaires et le numerique educatif.\n\nPour les projets en cours dans votre zone, renseignez-vous aupres de votre IA.",
        "category": "men_partenariats",
        "lang": "fr"
    },

    # ── DPTIC / NUMÉRIQUE ÉDUCATIF ──
    {
        "patterns": ["dptic", "numerique", "tic", "informatique education", "ordinateur ecole", "tablette"],
        "response": "Le numerique educatif au Senegal :\n\nLa DPTIC (Division de la Promotion des TIC) gere la strategie numerique pour l'education.\n\nActions principales :\n- Deploiement de PLANETE dans tous les etablissements\n- Equipement en salles informatiques\n- Formation des enseignants au numerique\n- Strategie numerique 2025-2029\n\nOutils numeriques du MEN :\n- PLANETE : gestion scolaire\n- MIRADOR : gestion des ressources humaines\n- SIMEN : systeme d'information global\n\nPour les formations au numerique, contactez votre IEF ou le referent numerique de votre etablissement.",
        "category": "men_numerique",
        "lang": "fr"
    },

    # ── MIRADOR ──
    {
        "patterns": ["mirador", "gestion rh", "ressources humaines", "dossier administratif"],
        "response": "MIRADOR est la plateforme de gestion des ressources humaines du Ministere de l'Education Nationale.\n\nElle contient :\n- Les dossiers administratifs des agents\n- Les informations de carriere (corps, grade, echelon)\n- Les affectations\n- Les ordres de service\n\nLien avec PLANETE :\n- Les agents titulaires sont importes depuis MIRADOR vers PLANETE via le bouton Mis a Jour Personnel\n- La mise a jour d'un dossier agent dans PLANETE peut etre synchronisee avec MIRADOR\n\nSi vous avez un probleme avec votre dossier MIRADOR, contactez la DRH du MEN ou votre IA.",
        "category": "men_mirador",
        "lang": "fr"
    },

    # ── REDOUBLEMENT ──
    {
        "patterns": ["redoublement", "redoubler", "passage", "passage classe", "maintien"],
        "response": "Le redoublement au Senegal :\n\nRegles generales :\n- Au primaire : le redoublement est limite (reforme en cours)\n- Au college et lycee : decision du conseil de classe\n- Les criteres sont bases sur les moyennes et les appreciations\n\nDans PLANETE :\n- Le dossier eleve comporte les champs Dernier redoublement et Annee redoublement\n- Les statistiques du tableau de bord affichent le nombre de redoublants\n\nPour les contestations de decisions de conseil de classe :\n1. Adressez un recours au chef d'etablissement\n2. Puis a l'IEF si necessaire\n3. L'IA peut trancher en dernier ressort.",
        "category": "men_redoublement",
        "lang": "fr"
    },

    # ── GOSCO / FRAIS ──
    {
        "patterns": ["gosco", "frais scolaires", "cotisation", "contribution", "ime"],
        "response": "Les frais scolaires au Senegal :\n\nPrincipaux frais :\n- GOSCO : contribution pour le fonctionnement de l'etablissement\n- IME : frais d'inscription\n- Frais de tenue\n- Frais d'examen\n\nImportant :\n- L'ecole primaire publique est gratuite\n- Au college et lycee, les frais sont fixes par l'etablissement\n- Le CGE valide les montants\n\nDans PLANETE :\n- Les frais sont parametres dans Configuration > Parametrage scolarite\n- Le suivi des paiements se fait dans Eleves > Inscriptions\n- Possibilite de paiement echelonne (differe).",
        "category": "men_frais",
        "lang": "fr"
    },

    # ── Mise à jour du message d'accueil ──
]

# Conversations en mémoire (simple dict)
SESSIONS = {}

# ─────────────────────────────────────────────
# LOGIQUE DU CHATBOT
# ─────────────────────────────────────────────

def normalize(text: str) -> str:
    """Normalise le texte : minuscules, supprime accents et ponctuation."""
    text = text.lower().strip()
    # Remplacer les accents courants
    accents = {'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
               'à': 'a', 'â': 'a', 'ä': 'a',
               'ù': 'u', 'û': 'u', 'ü': 'u',
               'î': 'i', 'ï': 'i',
               'ô': 'o', 'ö': 'o',
               'ç': 'c', 'ñ': 'n'}
    for acc, rep in accents.items():
        text = text.replace(acc, rep)
    # Remplacer apostrophes et ponctuation par des espaces
    text = re.sub(r"[''`?!.,;:\-/()\"]+", ' ', text)
    # Supprimer les espaces multiples
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def tokenize(text: str) -> list:
    """Découpe le texte normalisé en mots significatifs."""
    # Mots vides (stop words) à ignorer lors du scoring
    STOP_WORDS = {
        'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles',
        'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'au', 'aux',
        'ce', 'cette', 'ces', 'mon', 'ma', 'mes', 'ton', 'ta', 'tes',
        'son', 'sa', 'ses', 'notre', 'nos', 'votre', 'vos', 'leur', 'leurs',
        'qui', 'que', 'quoi', 'quel', 'quelle', 'quels', 'quelles',
        'et', 'ou', 'mais', 'donc', 'car', 'ni', 'ne', 'pas', 'plus',
        'est', 'sont', 'a', 'ont', 'fait', 'faire', 'etre', 'avoir',
        'dans', 'sur', 'sous', 'avec', 'sans', 'pour', 'par', 'en',
        'se', 'si', 'y', 'me', 'te', 'lui', 'eux',
        'comment', 'quand', 'combien', 'pourquoi', 'ou',
        'ca', 'cela', 'ceci', 'ici', 'la', 'tout', 'tous', 'toute', 'toutes',
        'bien', 'tres', 'aussi', 'encore', 'deja', 'jamais', 'toujours',
        'faut', 'peut', 'veux', 'voudrais', 'peux', 'dois',
        'suis', 'es', 'sommes', 'etes',
        'c', 'l', 'd', 'n', 's', 'j', 'm', 't', 'qu',
    }
    words = text.split()
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def word_match_score(pattern_words: list, msg_words: list) -> float:
    """
    Calcule un score de correspondance entre les mots du pattern et du message.
    Utilise la correspondance exacte de mots + correspondance partielle (préfixe/suffixe).
    Retourne un score entre 0 et 1.
    """
    if not pattern_words or not msg_words:
        return 0.0

    matched = 0
    for pw in pattern_words:
        for mw in msg_words:
            # Correspondance exacte de mot
            if pw == mw:
                matched += 1.0
                break
            # Correspondance par préfixe (ex: "inscri" dans "inscription"/"inscrire")
            elif len(pw) >= 4 and len(mw) >= 4:
                # L'un est le début de l'autre (stemming basique)
                if mw.startswith(pw[:4]) or pw.startswith(mw[:4]):
                    matched += 0.7
                    break
                # Vérifier si un mot contient l'autre (pour les mots composés)
                elif pw in mw or mw in pw:
                    matched += 0.5
                    break

    # Score = proportion de mots du pattern qui ont matché
    return matched / len(pattern_words)


def compute_faq_coverage(faq_patterns: list, msg_words: list) -> float:
    """
    Calcule combien de mots significatifs du message sont couverts
    par l'ensemble des patterns d'une FAQ. Retourne un ratio 0-1.
    """
    if not msg_words:
        return 0.0
    covered = set()
    for pattern in faq_patterns:
        pattern_words = tokenize(normalize(pattern))
        for pw in pattern_words:
            for i, mw in enumerate(msg_words):
                if mw == pw or (len(pw) >= 4 and len(mw) >= 4 and (mw.startswith(pw[:4]) or pw.startswith(mw[:4]))):
                    covered.add(i)
    return len(covered) / len(msg_words)


def find_response(message: str) -> str:
    """
    Cherche la meilleure réponse dans la FAQ avec un scoring intelligent.
    Privilégie les correspondances spécifiques (multi-mots) sur les génériques.
    """
    msg = normalize(message)
    msg_words = tokenize(msg)
    msg_all_words = msg.split()
    msg_word_count = len(msg_all_words)  # Nombre total de mots (avant filtrage)

    best_score = 0.0
    best_response = None
    SCORE_THRESHOLD = 0.30

    for faq in FAQ:
        faq_best_pattern_score = 0.0

        for pattern in faq["patterns"]:
            normalized_pattern = normalize(pattern)
            pattern_words = tokenize(normalized_pattern)
            pattern_all_words = normalized_pattern.split()

            # ── 1. Correspondance exacte de phrase entière ──
            if normalized_pattern == msg:
                score = 1.0
            # ── 2. Le pattern multi-mots est contenu comme phrase dans le message ──
            elif len(pattern_all_words) >= 2 and normalized_pattern in msg:
                score = 0.75 + (0.25 * len(pattern_all_words) / max(msg_word_count, 1))
            # ── 3. Le message est contenu dans le pattern ──
            elif len(msg_all_words) >= 2 and msg in normalized_pattern:
                score = 0.65 + (0.25 * len(msg_all_words) / max(len(pattern_all_words), 1))
            else:
                # ── 4. Correspondance par mots significatifs ──
                score = word_match_score(pattern_words, msg_words)

                # ── 5. Bonus quand TOUS les mots d'un pattern multi-mots matchent ──
                if len(pattern_words) >= 2 and score >= 0.5:
                    found_count = sum(
                        1 for pw in pattern_words
                        if any(
                            mw == pw or (len(pw) >= 4 and len(mw) >= 4 and (mw.startswith(pw[:4]) or pw.startswith(mw[:4])))
                            for mw in msg_words
                        )
                    )
                    if found_count == len(pattern_words):
                        score = min(score + 0.35, 0.95)
                    elif found_count >= 2:
                        score = min(score + 0.15, 0.85)

                # ── 6. Pénalité pour patterns d'un seul mot quand le message est long ──
                if len(pattern_words) <= 1 and msg_word_count >= 3:
                    score *= 0.55  # Forte pénalité : un seul mot ne décrit pas un message long

            if score > faq_best_pattern_score:
                faq_best_pattern_score = score

        # ── 7. Bonus de couverture : la FAQ qui couvre le plus de mots du message gagne ──
        coverage = compute_faq_coverage(faq["patterns"], msg_words)
        # Score final = meilleur score pattern + petit bonus couverture
        faq_score = faq_best_pattern_score + (coverage * 0.15)

        if faq_score > best_score:
            best_score = faq_score
            best_response = faq["response"]

    if best_score >= SCORE_THRESHOLD and best_response:
        return best_response

    # Réponse par défaut améliorée
    return ("Je n'ai pas trouve de reponse precise a votre question. "
            "Voici les sujets sur lesquels je peux vous aider :\n\n"
            "- **PLANETE** : connexion, eleves, emploi du temps, notes, bulletins, evaluations, conseils de classe\n"
            "- **Inscriptions** et **Examens** : CFEE, BFEM, BAC\n"
            "- **Carriere enseignant** : mutations, avancements, salaire, conges, retraite\n"
            "- **Orientation** et **Bourses**\n"
            "- **Structures MEN** : IEF, IA, DRH, DPTIC, MIRADOR\n"
            "- **Education inclusive**, cantines, securite scolaire\n"
            "- **Daaras**, ecoles franco-arabes, education non formelle\n\n"
            "Essayez avec des mots-cles comme : planete, inscription, bourse, mutation, bac, bfem...")


def chat(session_id: str, message: str) -> dict:
    """Traite un message et retourne une réponse."""
    if session_id not in SESSIONS:
        SESSIONS[session_id] = []

    # Sauvegarder le message utilisateur
    SESSIONS[session_id].append({
        "role": "user",
        "content": message,
        "time": datetime.now().strftime("%H:%M")
    })

    # Trouver une réponse
    response_text = find_response(message)

    # Sauvegarder la réponse
    SESSIONS[session_id].append({
        "role": "assistant",
        "content": response_text,
        "time": datetime.now().strftime("%H:%M")
    })

    # Garder max 20 messages en mémoire
    if len(SESSIONS[session_id]) > 20:
        SESSIONS[session_id] = SESSIONS[session_id][-20:]

    return {"response": response_text, "session_id": session_id}


# ─────────────────────────────────────────────
# PAGE HTML DU CHATBOT
# ─────────────────────────────────────────────

HTML_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Assistant Éducatif - Ministère de l'Éducation Nationale</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f4f8; height: 100vh; display: flex; flex-direction: column; }

  /* ─── HEADER ─── */
  header {
    background: linear-gradient(135deg, #006633, #009933);
    color: white;
    padding: 14px 20px;
    display: flex;
    align-items: center;
    gap: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  }
  .flag { font-size: 2rem; }
  header h1 { font-size: 1.1rem; font-weight: 700; }
  header p { font-size: 0.78rem; opacity: 0.88; margin-top: 2px; }
  .status-dot {
    width: 10px; height: 10px; background: #FFCD00;
    border-radius: 50%; margin-left: auto; animation: pulse 2s infinite;
  }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

  /* ─── CHAT AREA ─── */
  #chat-box {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .msg { display: flex; align-items: flex-end; gap: 8px; max-width: 80%; }
  .msg.user { align-self: flex-end; flex-direction: row-reverse; }
  .msg.bot  { align-self: flex-start; }

  .avatar {
    width: 32px; height: 32px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 1rem; flex-shrink: 0;
  }
  .bot .avatar  { background: #006633; color: white; }
  .user .avatar { background: #FFCD00; color: #333; }

  .bubble {
    padding: 10px 14px;
    border-radius: 18px;
    font-size: 0.9rem;
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .bot .bubble  { background: white; border-bottom-left-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); color: #222; }
  .user .bubble { background: #006633; border-bottom-right-radius: 4px; color: white; }

  .time { font-size: 0.68rem; color: #aaa; margin: 0 4px; }

  /* ─── SUGGESTIONS ─── */
  #suggestions {
    padding: 8px 16px;
    display: flex; flex-wrap: wrap; gap: 7px;
  }
  .chip {
    background: white; border: 1.5px solid #006633; color: #006633;
    border-radius: 20px; padding: 5px 13px; font-size: 0.78rem;
    cursor: pointer; transition: all 0.2s;
  }
  .chip:hover { background: #006633; color: white; }

  /* ─── INPUT ─── */
  #input-area {
    padding: 12px 16px;
    background: white;
    border-top: 1px solid #e0e0e0;
    display: flex; gap: 10px; align-items: center;
  }
  #msg-input {
    flex: 1;
    border: 1.5px solid #ddd; border-radius: 24px;
    padding: 10px 18px; font-size: 0.92rem; outline: none;
    transition: border 0.2s;
  }
  #msg-input:focus { border-color: #006633; }
  #send-btn {
    background: #006633; color: white;
    border: none; border-radius: 50%;
    width: 44px; height: 44px;
    font-size: 1.2rem; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: background 0.2s;
  }
  #send-btn:hover { background: #004d26; }
  #send-btn:disabled { background: #ccc; cursor: not-allowed; }

  /* ─── TYPING ─── */
  .typing .bubble { padding: 12px 16px; }
  .dot { display: inline-block; width: 7px; height: 7px; background: #aaa; border-radius: 50%; margin: 0 2px; animation: bounce 1.2s infinite; }
  .dot:nth-child(2) { animation-delay: 0.2s; }
  .dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-6px)} }

  /* ─── WELCOME ─── */
  .welcome {
    text-align: center; padding: 30px 20px; color: #555;
  }
  .welcome .icon { font-size: 3rem; margin-bottom: 10px; }
  .welcome h2 { font-size: 1.1rem; color: #006633; margin-bottom: 8px; }
  .welcome p  { font-size: 0.85rem; line-height: 1.6; }
</style>
</head>
<body>

<header>
  <div class="flag">🇸🇳</div>
  <div>
    <h1>Assistant Éducatif</h1>
    <p>Ministère de l'Éducation Nationale du Sénégal</p>
  </div>
  <div class="status-dot" title="En ligne"></div>
</header>

<div id="chat-box">
  <div class="welcome">
    <div class="icon">🎓</div>
    <h2>Bienvenue !</h2>
    <p>Je suis votre assistant éducatif.<br>Posez-moi vos questions sur l'école,<br>les examens, les inscriptions et plus encore.</p>
  </div>
</div>

<div id="suggestions">
  <span class="chip" onclick="sendChip(this)">💻 PLANETE connexion</span>
  <span class="chip" onclick="sendChip(this)">👨‍🎓 Eleves PLANETE</span>
  <span class="chip" onclick="sendChip(this)">📝 Inscription</span>
  <span class="chip" onclick="sendChip(this)">🎓 Examens BFEM/BAC</span>
  <span class="chip" onclick="sendChip(this)">📊 Evaluation PLANETE</span>
  <span class="chip" onclick="sendChip(this)">💰 Bourses</span>
  <span class="chip" onclick="sendChip(this)">🔄 Mutation enseignant</span>
  <span class="chip" onclick="sendChip(this)">📋 Carriere avancement</span>
</div>

<div id="input-area">
  <input id="msg-input" type="text" placeholder="Posez votre question ici..." autocomplete="off" maxlength="500">
  <button id="send-btn" onclick="sendMessage()" title="Envoyer">➤</button>
</div>

<script>
const SESSION_ID = 'sess_' + Math.random().toString(36).slice(2);
const chatBox = document.getElementById('chat-box');
const input   = document.getElementById('msg-input');
const sendBtn = document.getElementById('send-btn');

// Envoyer avec Entrée
input.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage(); });

function sendChip(el) {
  input.value = el.textContent.replace(/^[^ ]+ /, ''); // enlever l'emoji
  sendMessage();
}

function addMsg(role, text, time) {
  // Supprimer le message de bienvenue au premier message
  const welcome = chatBox.querySelector('.welcome');
  if (welcome) welcome.remove();

  const div = document.createElement('div');
  div.className = 'msg ' + role;
  const avatar = role === 'user' ? '👤' : '🤖';
  // Convertir **bold** en <strong>
  const formatted = text.replace(/[*][*](.*?)[*][*]/g, '<strong>$1</strong>');
  div.innerHTML = `
    <div class="avatar">${avatar}</div>
    <div>
      <div class="bubble">${formatted}</div>
      <div class="time">${time || ''}</div>
    </div>`;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function showTyping() {
  const div = document.createElement('div');
  div.className = 'msg bot typing';
  div.id = 'typing';
  div.innerHTML = `<div class="avatar">🤖</div><div class="bubble"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>`;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function removeTyping() {
  const t = document.getElementById('typing');
  if (t) t.remove();
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  const now = new Date().toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'});
  addMsg('user', text, now);
  input.value = '';
  sendBtn.disabled = true;
  showTyping();

  try {
    const apiUrl = window.location.origin + '/api/chat';
    const res = await fetch(apiUrl, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text, session_id: SESSION_ID})
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    removeTyping();
    const botTime = new Date().toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'});
    addMsg('bot', data.response, botTime);
  } catch(e) {
    removeTyping();
    addMsg('bot', 'Erreur: ' + e.message + '. Verifiez que le serveur tourne (fenetre noire ouverte).', '');
    console.error('Chat error:', e);
  }

  sendBtn.disabled = false;
  input.focus();
}

// Message de bienvenue automatique après 1 seconde
setTimeout(() => {
  const now = new Date().toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'});
  addMsg('bot', "Bonjour ! Je suis l'assistant \\u00e9ducatif du Minist\\u00e8re de l'\\u00c9ducation du S\\u00e9n\\u00e9gal. \\ud83c\\uddf8\\ud83c\\uddf3\\n\\nJe peux vous renseigner sur :\\n\\u2022 Les **inscriptions** et la rentr\\u00e9e\\n\\u2022 Les **examens** (CFEE, BFEM, BAC)\\n\\u2022 L'**orientation** scolaire\\n\\u2022 Les **bourses** d'\\u00e9tudes\\n\\u2022 Les **programmes** et mati\\u00e8res\\n\\nQuelle est votre question ?", now);
}, 800);
</script>

</body>
</html>
"""

# ─────────────────────────────────────────────
# SERVEUR HTTP SIMPLE
# ─────────────────────────────────────────────

class ChatHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Afficher les logs de manière propre
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] {args[0]} {args[1]}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ('/', '/index.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        elif parsed.path == '/health':
            self.send_json({"status": "ok", "version": "demo"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/chat':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                message    = data.get('message', '').strip()
                session_id = data.get('session_id', str(uuid.uuid4()))
                if not message:
                    self.send_json({"error": "Message vide"}, 400)
                    return
                result = chat(session_id, message)
                self.send_json(result)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)


# ─────────────────────────────────────────────
# LANCEMENT
# ─────────────────────────────────────────────

PORT = 5500

def open_browser():
    """Ouvre Chrome après 1.5 secondes."""
    time.sleep(1.5)
    url = f"http://localhost:{PORT}"
    print(f"\n  Ouverture navigateur : {url}\n")
    webbrowser.open(url)


if __name__ == '__main__':
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    print("\n" + "="*55)
    print("  CHATBOT EDUCATIF - MINISTERE DE L'EDUCATION SN")
    print("="*55)
    print(f"\n  Demarrage du serveur sur http://localhost:{PORT}")
    print("  Appuyez sur Ctrl+C pour arreter.\n")

    # Ouvrir le navigateur dans un thread séparé
    threading.Thread(target=open_browser, daemon=True).start()

    # Démarrer le serveur
    server = ThreadingHTTPServer(('0.0.0.0', PORT), ChatHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  Serveur arrêté. À bientôt !")
        server.server_close()
