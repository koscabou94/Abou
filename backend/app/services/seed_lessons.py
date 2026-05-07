"""
Peuplement de la base avec les leçons EduBot alignées sur le
Curriculum de l'Éducation de Base (CEB) officiel du Sénégal — CI à CM2.

Matières :
  CI       : Français, Mathématiques
  CP       : Français, Mathématiques, Anglais
  CE1-CE2  : Français, Mathématiques, Sciences, Anglais, Histoire-Géo
  CM1-CM2  : Français, Mathématiques, Sciences, Anglais, Histoire-Géo
"""

import asyncio
from app.database.connection import AsyncSessionLocal, create_tables
from app.database.models import Lesson, Exercise


# ═══════════════════════════════════════════════════════════════════════
#  DONNÉES DES LEÇONS — CEB SÉNÉGAL
# ═══════════════════════════════════════════════════════════════════════

LESSONS_DATA = [

    # ──────────────────────────────────────────────────────────────────
    # CI — Cours d'Initiation
    # Matières CEB : Langage (Français oral + écriture), Mathématiques
    # ──────────────────────────────────────────────────────────────────

    {
        "level": "CI", "subject": "francais", "order": 1,
        "title": "Les salutations",
        "summary": "Saluer, se présenter et prendre congé en français.",
        "duration_minutes": 20,
        "content": """## Les salutations

Savoir saluer est la première leçon de français au CI.

### Saluer quelqu'un
- Le matin : **Bonjour !**
- L'après-midi/soir : **Bonsoir !**
- Pour partir : **Au revoir !** ou **À demain !**

### Demander des nouvelles
> — Comment ça va ?
> — Ça va bien, merci !

### Se présenter
> Je m'appelle Fatou. J'ai 6 ans. J'habite à Dakar.

### Présenter quelqu'un
> Voici mon ami Moussa. Il s'appelle Moussa.

**À retenir** : On salue toujours les adultes avec respect.""",
        "exercises": [
            {
                "question": "Comment dit-on bonjour le matin ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Bonsoir"}, {"label": "B", "text": "Bonjour"}, {"label": "C", "text": "Au revoir"}],
                "correct": "B", "explanation": "On dit 'Bonjour' le matin.", "points": 1
            },
            {
                "question": "Pour te présenter, tu dis : 'Je m'___ Awa.'",
                "type": "qcm",
                "options": [{"label": "A", "text": "appel"}, {"label": "B", "text": "appelle"}, {"label": "C", "text": "appeles"}],
                "correct": "B", "explanation": "La formule correcte est 'Je m'appelle'.", "points": 1
            },
            {
                "question": "Quand tu quittes l'école, tu dis :",
                "type": "qcm",
                "options": [{"label": "A", "text": "Bonjour !"}, {"label": "B", "text": "Comment ça va ?"}, {"label": "C", "text": "Au revoir !"}],
                "correct": "C", "explanation": "'Au revoir' est la formule pour quitter quelqu'un.", "points": 1
            },
        ]
    },
    {
        "level": "CI", "subject": "francais", "order": 2,
        "title": "Les lettres et les sons",
        "summary": "Reconnaître les lettres de l'alphabet et les voyelles.",
        "duration_minutes": 25,
        "content": """## Les lettres et les sons

L'alphabet français contient **26 lettres**.

### Les voyelles
**A – E – I – O – U – Y**

Les voyelles sont des sons que l'on peut chanter seuls.
Exemples : **a**mi, **é**cole, **i**ci, **o**range, **u**n, **y**eux

### Les consonnes
Toutes les autres lettres sont des consonnes.
Exemples : **b**ateau, **c**hat, **d**ent, **f**eu, **m**aman

### Majuscules et minuscules
- **Majuscule** : A B C → début de phrase ou de nom propre
- **Minuscule** : a b c → à l'intérieur d'un mot

### Former des syllabes
Consonne + Voyelle = syllabe
**m + a = ma** · **p + a = pa** · **b + a = ba** · **l + a = la**""",
        "exercises": [
            {
                "question": "Combien de lettres y a-t-il dans l'alphabet français ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "24"}, {"label": "B", "text": "26"}, {"label": "C", "text": "28"}],
                "correct": "B", "explanation": "L'alphabet français a 26 lettres.", "points": 1
            },
            {
                "question": "Laquelle de ces lettres est une voyelle ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "M"}, {"label": "B", "text": "O"}, {"label": "C", "text": "P"}],
                "correct": "B", "explanation": "Les voyelles sont : A, E, I, O, U, Y. O est une voyelle.", "points": 1
            },
            {
                "question": "Quelle syllabe obtient-on avec 'm' + 'a' ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "am"}, {"label": "B", "text": "ma"}, {"label": "C", "text": "mi"}],
                "correct": "B", "explanation": "Consonne + voyelle : m + a = ma.", "points": 1
            },
        ]
    },
    {
        "level": "CI", "subject": "francais", "order": 3,
        "title": "La famille",
        "summary": "Nommer les membres de la famille et décrire les liens familiaux.",
        "duration_minutes": 20,
        "content": """## La famille

La famille, c'est les personnes qui vivent avec toi et qui t'aiment.

### Les membres de la famille
| Membre | Rôle |
|--------|------|
| **Le père** | Le papa |
| **La mère** | La maman |
| **Le frère** | Le garçon de la famille |
| **La sœur** | La fille de la famille |
| **Le grand-père** | Le papa du père ou de la mère |
| **La grand-mère** | La maman du père ou de la mère |

### Parler de sa famille
> J'ai un père, une mère, un frère et une sœur.
> Ma mère s'appelle Adja. Mon père s'appelle Ousmane.

### La maison
La famille vit dans une **maison** ou un **appartement**.""",
        "exercises": [
            {
                "question": "Comment appelle-t-on la maman du père ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "La tante"}, {"label": "B", "text": "La grand-mère"}, {"label": "C", "text": "La cousine"}],
                "correct": "B", "explanation": "La maman du père ou de la mère s'appelle la grand-mère.", "points": 1
            },
            {
                "question": "Le garçon dans une famille s'appelle :",
                "type": "qcm",
                "options": [{"label": "A", "text": "La sœur"}, {"label": "B", "text": "La mère"}, {"label": "C", "text": "Le frère"}],
                "correct": "C", "explanation": "Le garçon de la famille s'appelle le frère.", "points": 1
            },
            {
                "question": "Pour parler de ta mère tu dis : '**Ma** ___ s'appelle Aminata.'",
                "type": "qcm",
                "options": [{"label": "A", "text": "père"}, {"label": "B", "text": "frère"}, {"label": "C", "text": "mère"}],
                "correct": "C", "explanation": "On dit 'Ma mère' pour parler de sa maman.", "points": 1
            },
        ]
    },

    # CI — Mathématiques
    {
        "level": "CI", "subject": "mathematiques", "order": 1,
        "title": "Les nombres de 0 à 5",
        "summary": "Compter, lire et écrire les nombres de 0 à 5.",
        "duration_minutes": 20,
        "content": """## Les nombres de 0 à 5

Les nombres servent à compter les objets.

### Compter de 0 à 5
0 – zéro · 1 – un · 2 – deux · 3 – trois · 4 – quatre · 5 – cinq

### Écrire les chiffres
| Chiffre | Nom | Exemple |
|---------|-----|---------|
| 0 | zéro | 0 élève absent |
| 1 | un | 1 stylo |
| 2 | deux | 2 mains |
| 3 | trois | 3 livres |
| 4 | quatre | 4 pattes d'un chien |
| 5 | cinq | 5 doigts d'une main |

### Comparer
- 3 > 2 (3 est plus grand que 2)
- 1 < 4 (1 est plus petit que 4)

**À retenir** : 0 c'est rien du tout. 5 c'est une main entière !""",
        "exercises": [
            {
                "question": "Combien de doigts y a-t-il sur une main ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "3"}, {"label": "B", "text": "4"}, {"label": "C", "text": "5"}],
                "correct": "C", "explanation": "Une main a 5 doigts.", "points": 1
            },
            {
                "question": "Quel nombre vient après 3 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "2"}, {"label": "B", "text": "4"}, {"label": "C", "text": "5"}],
                "correct": "B", "explanation": "Après 3 vient 4 : 0, 1, 2, 3, 4, 5.", "points": 1
            },
            {
                "question": "Comment écrit-on le nombre 'deux' en chiffres ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "1"}, {"label": "B", "text": "2"}, {"label": "C", "text": "3"}],
                "correct": "B", "explanation": "Deux s'écrit 2 en chiffres.", "points": 1
            },
        ]
    },
    {
        "level": "CI", "subject": "mathematiques", "order": 2,
        "title": "Les nombres de 6 à 10",
        "summary": "Compter, lire et écrire les nombres de 6 à 10.",
        "duration_minutes": 20,
        "content": """## Les nombres de 6 à 10

### Compter de 6 à 10
6 – six · 7 – sept · 8 – huit · 9 – neuf · 10 – dix

### Représenter les nombres
| Nombre | Représentation |
|--------|----------------|
| 6 | ●●●  ●●● (deux groupes de 3) |
| 7 | ●●●●  ●●● (4 + 3) |
| 8 | ●●●●  ●●●● (deux groupes de 4) |
| 9 | ●●●●●  ●●●● (5 + 4) |
| 10 | ●●●●●  ●●●●● (deux mains) |

### 10 = deux mains
10 doigts = 2 mains × 5 doigts

### Ordre des nombres de 0 à 10
0 1 2 3 4 5 6 7 8 9 10

**À retenir** : 10 est le premier nombre à deux chiffres !""",
        "exercises": [
            {
                "question": "Quel nombre vient après 9 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "8"}, {"label": "B", "text": "10"}, {"label": "C", "text": "11"}],
                "correct": "B", "explanation": "Après 9 vient 10. 10 s'écrit avec deux chiffres : 1 et 0.", "points": 1
            },
            {
                "question": "Combien de doigts as-tu en tout sur les deux mains ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "8"}, {"label": "B", "text": "9"}, {"label": "C", "text": "10"}],
                "correct": "C", "explanation": "2 mains × 5 doigts = 10 doigts.", "points": 1
            },
            {
                "question": "Quel est le plus grand nombre entre 7, 9 et 6 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "6"}, {"label": "B", "text": "7"}, {"label": "C", "text": "9"}],
                "correct": "C", "explanation": "9 est le plus grand : 6 < 7 < 9.", "points": 1
            },
        ]
    },
    {
        "level": "CI", "subject": "mathematiques", "order": 3,
        "title": "Les formes géométriques",
        "summary": "Reconnaître et nommer les formes géométriques de base.",
        "duration_minutes": 20,
        "content": """## Les formes géométriques

Les formes sont partout autour de nous !

### Les formes de base

| Forme | Caractéristiques | Exemple dans la vie |
|-------|-----------------|---------------------|
| **Carré** | 4 côtés égaux, 4 angles droits | Carreau de cahier |
| **Rectangle** | 4 côtés, 2 longs + 2 courts | Porte, fenêtre |
| **Triangle** | 3 côtés, 3 angles | Toit de maison |
| **Cercle** | Rond, pas de côté | Soleil, balle |

### Reconnaître dans la vie quotidienne
- La pièce de monnaie → **cercle**
- La porte → **rectangle**
- La fenêtre → **carré** ou **rectangle**
- Le toit → **triangle**

**Astuce** : Compte les côtés pour trouver la forme !""",
        "exercises": [
            {
                "question": "Combien de côtés a un triangle ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "2"}, {"label": "B", "text": "3"}, {"label": "C", "text": "4"}],
                "correct": "B", "explanation": "Un triangle a 3 côtés et 3 angles.", "points": 1
            },
            {
                "question": "Quelle forme ressemble à une pièce de monnaie ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Carré"}, {"label": "B", "text": "Triangle"}, {"label": "C", "text": "Cercle"}],
                "correct": "C", "explanation": "Une pièce de monnaie est ronde, c'est un cercle.", "points": 1
            },
            {
                "question": "Le carré a :",
                "type": "qcm",
                "options": [{"label": "A", "text": "3 côtés égaux"}, {"label": "B", "text": "4 côtés égaux"}, {"label": "C", "text": "0 côté"}],
                "correct": "B", "explanation": "Le carré a 4 côtés qui sont tous égaux.", "points": 1
            },
        ]
    },

    # ──────────────────────────────────────────────────────────────────
    # CP — Cours Préparatoire
    # Matières CEB : Français (oral, lecture, écriture), Mathématiques, Anglais
    # ──────────────────────────────────────────────────────────────────

    {
        "level": "CP", "subject": "francais", "order": 1,
        "title": "Lire des mots simples",
        "summary": "Lire des mots en assemblant des syllabes.",
        "duration_minutes": 25,
        "content": """## Lire des mots simples

Pour lire, on assemble des **syllabes**.

### Rappel des syllabes
Une syllabe = une consonne + une voyelle
- **pa** (p + a) · **ma** (m + a) · **la** (l + a)
- **pi** (p + i) · **li** (l + i) · **ni** (n + i)

### Former des mots
Syllabe + syllabe = mot
- **pa + pa = papa**
- **ma + ma = mama**
- **li + re = lire**
- **ca + fe = café**
- **ro + be = robe**

### Lire des phrases courtes
> Papa mange du pain.
> Mama lit un livre.
> Le chat dort.

### Sons à connaître
- **ou** : poule, loup, tour
- **an** : maman, enfant, banc
- **in** : lapin, pain, train""",
        "exercises": [
            {
                "question": "Quelle syllabe obtient-on avec les sons 'l' et 'a' ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "al"}, {"label": "B", "text": "la"}, {"label": "C", "text": "li"}],
                "correct": "B", "explanation": "l + a = la. On met d'abord la consonne, puis la voyelle.", "points": 1
            },
            {
                "question": "Quel mot forme-t-on avec 'pa' + 'pa' ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "papi"}, {"label": "B", "text": "papa"}, {"label": "C", "text": "papi"}],
                "correct": "B", "explanation": "pa + pa = papa, le mot pour désigner son père.", "points": 1
            },
            {
                "question": "Dans le mot 'poule', quel son entend-on ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "in"}, {"label": "B", "text": "an"}, {"label": "C", "text": "ou"}],
                "correct": "C", "explanation": "Le mot 'poule' contient le son 'ou' : p-ou-le.", "points": 1
            },
        ]
    },
    {
        "level": "CP", "subject": "francais", "order": 2,
        "title": "Inviter et recommander",
        "summary": "Formuler une invitation et donner des recommandations (CEB Palier 5).",
        "duration_minutes": 25,
        "content": """## Inviter et recommander

### Inviter quelqu'un
Pour inviter un(e) ami(e), on utilise ces formules :
> **Je t'invite** à mon anniversaire.
> **Tu veux** venir jouer avec moi ?
> **Viens** avec moi au marché.

### Répondre à une invitation
> D'accord, j'arrive ! · Merci pour l'invitation. · Désolé(e), je ne peux pas.

### Faire des recommandations
Pour conseiller quelqu'un, on dit :
> **Tu dois** faire attention aux voitures.
> **Il faut** arroser les plantes tous les jours.
> **N'oublie pas** de fermer la porte.

### Situation de communication
*Contexte* : Ton ami(e) ne connaît pas le chemin de ta maison.
> — Je t'invite à mon anniversaire. Tu prends la route du marché, tu tournes à gauche à l'école, c'est la deuxième maison.

**À retenir** : Inviter c'est proposer, recommander c'est conseiller.""",
        "exercises": [
            {
                "question": "Quelle phrase est une invitation ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Tu dois faire attention."}, {"label": "B", "text": "Je t'invite à ma fête."}, {"label": "C", "text": "Il faut rentrer tôt."}],
                "correct": "B", "explanation": "'Je t'invite' est une formule d'invitation.", "points": 1
            },
            {
                "question": "Quelle formule sert à recommander quelque chose ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Je t'invite à..."}, {"label": "B", "text": "Viens avec moi"}, {"label": "C", "text": "Il faut..."}],
                "correct": "C", "explanation": "'Il faut...' est une formule de recommandation.", "points": 1
            },
            {
                "question": "Pour accepter une invitation, on dit :",
                "type": "qcm",
                "options": [{"label": "A", "text": "Non, je ne veux pas."}, {"label": "B", "text": "D'accord, j'arrive !"}, {"label": "C", "text": "Tu dois venir."}],
                "correct": "B", "explanation": "'D'accord, j'arrive !' est une réponse positive à une invitation.", "points": 1
            },
        ]
    },
    {
        "level": "CP", "subject": "francais", "order": 3,
        "title": "Le vocabulaire de l'école",
        "summary": "Nommer les objets et les lieux de l'école.",
        "duration_minutes": 20,
        "content": """## Le vocabulaire de l'école

### Les objets de la classe
| Objet | Utilité |
|-------|---------|
| **Le cahier** | Pour écrire les leçons |
| **Le crayon** | Pour écrire et dessiner |
| **La règle** | Pour tracer des lignes droites |
| **La gomme** | Pour effacer les erreurs |
| **Le cartable** | Pour ranger ses affaires |
| **Le tableau** | La maîtresse y écrit les leçons |

### Les lieux de l'école
- La **classe** : où on apprend
- La **cour de récréation** : où on joue
- La **bibliothèque** : où on lit
- La **cantine** : où on mange

### Les personnes de l'école
- Le/La **maître(esse)** : enseigne les leçons
- Le/La **directeur(trice)** : dirige l'école
- Les **élèves** : viennent apprendre""",
        "exercises": [
            {
                "question": "Quel objet sert à effacer les erreurs ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Le crayon"}, {"label": "B", "text": "La gomme"}, {"label": "C", "text": "La règle"}],
                "correct": "B", "explanation": "La gomme sert à effacer ce qu'on a écrit.", "points": 1
            },
            {
                "question": "Où va-t-on pour manger à l'école ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "La bibliothèque"}, {"label": "B", "text": "La classe"}, {"label": "C", "text": "La cantine"}],
                "correct": "C", "explanation": "La cantine est l'endroit où les élèves mangent à l'école.", "points": 1
            },
            {
                "question": "Qui enseigne les leçons à l'école ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Le directeur"}, {"label": "B", "text": "Le maître/la maîtresse"}, {"label": "C", "text": "L'élève"}],
                "correct": "B", "explanation": "Le maître ou la maîtresse enseigne les leçons aux élèves.", "points": 1
            },
        ]
    },

    # CP — Mathématiques
    {
        "level": "CP", "subject": "mathematiques", "order": 1,
        "title": "Les nombres de 0 à 50",
        "summary": "Lire, écrire et comparer les nombres jusqu'à 50.",
        "duration_minutes": 25,
        "content": """## Les nombres de 0 à 50

### Compter par dizaines
- 10 = **dix** (une dizaine)
- 20 = **vingt** (deux dizaines)
- 30 = **trente** (trois dizaines)
- 40 = **quarante** (quatre dizaines)
- 50 = **cinquante** (cinq dizaines)

### Lire les nombres entre les dizaines
- 11 = onze · 12 = douze · 13 = treize · 14 = quatorze · 15 = quinze
- 16 = seize · 17 = dix-sept · 18 = dix-huit · 19 = dix-neuf
- 21 = vingt et un · 22 = vingt-deux · 25 = vingt-cinq

### Décomposer un nombre
- **34** = 3 dizaines + 4 unités = 30 + 4
- **27** = 2 dizaines + 7 unités = 20 + 7

### Comparer
- 45 > 38 · · · 12 < 21""",
        "exercises": [
            {
                "question": "Comment écrit-on 'trente' en chiffres ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "13"}, {"label": "B", "text": "30"}, {"label": "C", "text": "33"}],
                "correct": "B", "explanation": "Trente = 3 dizaines = 30.", "points": 1
            },
            {
                "question": "34 = 3 dizaines + ___ unités",
                "type": "qcm",
                "options": [{"label": "A", "text": "3"}, {"label": "B", "text": "4"}, {"label": "C", "text": "34"}],
                "correct": "B", "explanation": "34 = 30 + 4, donc 3 dizaines et 4 unités.", "points": 1
            },
            {
                "question": "Quel est le plus grand : 28 ou 35 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "28"}, {"label": "B", "text": "35"}, {"label": "C", "text": "Ils sont égaux"}],
                "correct": "B", "explanation": "35 > 28 car 35 a 3 dizaines et 28 seulement 2.", "points": 1
            },
        ]
    },
    {
        "level": "CP", "subject": "mathematiques", "order": 2,
        "title": "L'addition",
        "summary": "Calculer des additions simples avec des nombres jusqu'à 20.",
        "duration_minutes": 25,
        "content": """## L'addition

L'addition permet de **réunir** des quantités.

### Le signe +
3 + 4 = 7 se lit : « trois **plus** quatre **égal** sept »

### Calculer une addition
**Méthode** : compte d'abord un groupe, puis continue à compter.
- 5 + 3 : pars de 5, compte 3 de plus → 6, 7, 8 → **résultat : 8**
- 7 + 4 = **11**
- 9 + 5 = **14**

### Tables d'addition à mémoriser
| + | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| **5** | 5 | 6 | 7 | 8 | 9 | 10 |
| **6** | 6 | 7 | 8 | 9 | 10 | 11 |
| **7** | 7 | 8 | 9 | 10 | 11 | 12 |

### Problème
> Aminata a 4 mangues. Sa maman lui donne 5 mangues de plus.
> Combien Aminata a-t-elle de mangues en tout ?
> 4 + 5 = **9 mangues**""",
        "exercises": [
            {
                "question": "Combien fait 6 + 4 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "9"}, {"label": "B", "text": "10"}, {"label": "C", "text": "11"}],
                "correct": "B", "explanation": "6 + 4 = 10.", "points": 1
            },
            {
                "question": "Moussa a 3 crayons et en reçoit 7 autres. Il a maintenant :",
                "type": "qcm",
                "options": [{"label": "A", "text": "8 crayons"}, {"label": "B", "text": "10 crayons"}, {"label": "C", "text": "12 crayons"}],
                "correct": "B", "explanation": "3 + 7 = 10 crayons.", "points": 1
            },
            {
                "question": "Quel est le résultat de 8 + 5 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "12"}, {"label": "B", "text": "13"}, {"label": "C", "text": "14"}],
                "correct": "B", "explanation": "8 + 5 = 13.", "points": 1
            },
        ]
    },
    {
        "level": "CP", "subject": "mathematiques", "order": 3,
        "title": "La soustraction",
        "summary": "Calculer des soustractions simples.",
        "duration_minutes": 25,
        "content": """## La soustraction

La soustraction permet d'**enlever** une quantité.

### Le signe –
8 – 3 = 5 se lit : « huit **moins** trois **égal** cinq »

### Calculer une soustraction
- 10 – 4 : pars de 10, retire 4 → 9, 8, 7, 6 → **résultat : 6**
- 15 – 7 = **8**
- 12 – 5 = **7**

### La soustraction, c'est l'inverse de l'addition
Si 5 + 3 = 8, alors 8 – 3 = 5

### Vérification
Soustraction : 9 – 4 = 5
Vérification : 5 + 4 = 9 ✓

### Problème
> Papa a 12 oranges. Il en donne 5 à ses enfants.
> Combien lui en reste-t-il ?
> 12 – 5 = **7 oranges**""",
        "exercises": [
            {
                "question": "Combien fait 10 – 3 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "6"}, {"label": "B", "text": "7"}, {"label": "C", "text": "8"}],
                "correct": "B", "explanation": "10 – 3 = 7.", "points": 1
            },
            {
                "question": "Fatou a 15 bonbons et en mange 6. Il lui en reste :",
                "type": "qcm",
                "options": [{"label": "A", "text": "7"}, {"label": "B", "text": "8"}, {"label": "C", "text": "9"}],
                "correct": "C", "explanation": "15 – 6 = 9 bonbons.", "points": 1
            },
            {
                "question": "Quelle addition permet de vérifier 8 – 5 = 3 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "8 + 5 = 13"}, {"label": "B", "text": "3 + 5 = 8"}, {"label": "C", "text": "5 + 8 = 13"}],
                "correct": "B", "explanation": "On vérifie en ajoutant : 3 + 5 = 8.", "points": 1
            },
        ]
    },

    # CP — Anglais
    {
        "level": "CP", "subject": "anglais", "order": 1,
        "title": "Greetings — Les salutations",
        "summary": "Apprendre à saluer et se présenter en anglais.",
        "duration_minutes": 20,
        "content": """## Greetings — Les salutations

### How to say hello / Comment dire bonjour
| Anglais | Français |
|---------|---------|
| Hello ! | Bonjour ! |
| Good morning ! | Bonjour (le matin) ! |
| Good afternoon ! | Bon après-midi ! |
| Good evening ! | Bonsoir ! |
| Goodbye ! | Au revoir ! |

### How to introduce yourself / Se présenter
> **My name is** Aminata. (Je m'appelle Aminata.)
> **I am** 7 years old. (J'ai 7 ans.)
> **I live in** Dakar. (J'habite à Dakar.)

### Asking names / Demander le prénom
> What is your name ? → My name is ...
> How old are you ? → I am ... years old.

### Useful words / Mots utiles
Yes (oui) · No (non) · Please (s'il vous plaît) · Thank you (merci)""",
        "exercises": [
            {
                "question": "How do you say 'Bonjour' in the morning in English?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Good evening"}, {"label": "B", "text": "Good morning"}, {"label": "C", "text": "Goodbye"}],
                "correct": "B", "explanation": "'Good morning' means 'Bonjour' in the morning.", "points": 1
            },
            {
                "question": "Comment dit-on 'Je m'appelle' en anglais ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "I live in"}, {"label": "B", "text": "I am"}, {"label": "C", "text": "My name is"}],
                "correct": "C", "explanation": "'My name is' = 'Je m'appelle' en anglais.", "points": 1
            },
            {
                "question": "What does 'Thank you' mean?",
                "type": "qcm",
                "options": [{"label": "A", "text": "S'il vous plaît"}, {"label": "B", "text": "Merci"}, {"label": "C", "text": "Au revoir"}],
                "correct": "B", "explanation": "'Thank you' means 'Merci' in French.", "points": 1
            },
        ]
    },

    # ──────────────────────────────────────────────────────────────────
    # CE1 — Cours Élémentaire 1ère année
    # ──────────────────────────────────────────────────────────────────

    {
        "level": "CE1", "subject": "francais", "order": 1,
        "title": "Le nom et le verbe",
        "summary": "Identifier les noms et les verbes dans une phrase.",
        "duration_minutes": 30,
        "content": """## Le nom et le verbe

### Le nom
Le **nom** désigne une personne, un animal, un lieu ou une chose.
- *Dakar* est un nom de lieu.
- *Awa* est un nom de personne.
- *Chien* est un nom d'animal.
- *Livre* est un nom de chose.

**Le déterminant** (un, une, le, la, les) accompagne le nom.
> **le** livre · **une** mangue · **les** enfants

### Le verbe
Le **verbe** exprime une action ou un état.
- Moussa **court** (action).
- La fleur **est** belle (état).

### Le groupe nominal et le groupe verbal
Toute phrase a :
- Un **groupe nominal** (GN) : qui fait l'action = sujet
- Un **groupe verbal** (GV) : ce qu'il fait

> **Awa** (GN) **mange du pain** (GV).
> **Le chien** (GN) **aboie** (GV).""",
        "exercises": [
            {
                "question": "Dans 'Le chat dort', quel est le verbe ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Le"}, {"label": "B", "text": "chat"}, {"label": "C", "text": "dort"}],
                "correct": "C", "explanation": "'Dort' est le verbe : il exprime l'action de dormir.", "points": 1
            },
            {
                "question": "Lequel de ces mots est un nom ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "mange"}, {"label": "B", "text": "mangue"}, {"label": "C", "text": "bien"}],
                "correct": "B", "explanation": "'Mangue' est un nom (fruit). 'Mange' est un verbe.", "points": 1
            },
            {
                "question": "Dans 'Aminata lit un livre', quel est le groupe nominal (sujet) ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "lit un livre"}, {"label": "B", "text": "Aminata"}, {"label": "C", "text": "un livre"}],
                "correct": "B", "explanation": "'Aminata' est le sujet (groupe nominal) de la phrase.", "points": 1
            },
        ]
    },
    {
        "level": "CE1", "subject": "francais", "order": 2,
        "title": "Le présent de l'indicatif",
        "summary": "Conjuguer les verbes au présent de l'indicatif.",
        "duration_minutes": 30,
        "content": """## Le présent de l'indicatif

Le présent décrit ce qui se passe **maintenant** ou **habituellement**.

### Conjugaison du verbe ÊTRE
| Pronom | Conjugaison |
|--------|------------|
| Je | suis |
| Tu | es |
| Il / Elle | est |
| Nous | sommes |
| Vous | êtes |
| Ils / Elles | sont |

### Conjugaison du verbe AVOIR
| Pronom | Conjugaison |
|--------|------------|
| Je | ai |
| Tu | as |
| Il / Elle | a |
| Nous | avons |
| Vous | avez |
| Ils / Elles | ont |

### Verbes en -ER (parler, manger, chanter)
> Je **parle** · Tu **parles** · Il **parle**
> Nous **parlons** · Vous **parlez** · Ils **parlent**

**Astuce** : Au présent, les verbes en -ER ont les terminaisons : -e, -es, -e, -ons, -ez, -ent""",
        "exercises": [
            {
                "question": "Quelle est la bonne conjugaison : 'Il ___ content.' ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "suis"}, {"label": "B", "text": "es"}, {"label": "C", "text": "est"}],
                "correct": "C", "explanation": "Avec 'il', le verbe être se conjugue 'est'.", "points": 1
            },
            {
                "question": "Comment conjugue-t-on 'parler' avec 'nous' ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "nous parle"}, {"label": "B", "text": "nous parlons"}, {"label": "C", "text": "nous parlent"}],
                "correct": "B", "explanation": "Avec 'nous', les verbes en -ER prennent -ons : nous parlons.", "points": 1
            },
            {
                "question": "'Ils ___ trois enfants.' (avoir)",
                "type": "qcm",
                "options": [{"label": "A", "text": "avons"}, {"label": "B", "text": "ont"}, {"label": "C", "text": "avez"}],
                "correct": "B", "explanation": "Avoir avec 'ils' → 'ont' : ils ont.", "points": 1
            },
        ]
    },
    {
        "level": "CE1", "subject": "mathematiques", "order": 1,
        "title": "Les nombres jusqu'à 999",
        "summary": "Lire, écrire et décomposer les nombres jusqu'à 999.",
        "duration_minutes": 30,
        "content": """## Les nombres jusqu'à 999

### Les centaines
- 100 = cent (une centaine)
- 200 = deux cents
- 500 = cinq cents
- 999 = neuf cent quatre-vingt-dix-neuf

### Décomposer un nombre
**534** = 5 centaines + 3 dizaines + 4 unités = 500 + 30 + 4

**Tableau de numération :**
| Centaines | Dizaines | Unités |
|-----------|----------|--------|
| 5 | 3 | 4 |

### Comparer des nombres
- 345 < 435 (car 3 < 4 au rang des centaines)
- 768 > 678 (car 7 > 6 au rang des centaines)

### Ranger dans l'ordre
- Croissant (du plus petit au plus grand) : 102, 215, 350, 489
- Décroissant (du plus grand au plus petit) : 489, 350, 215, 102""",
        "exercises": [
            {
                "question": "Quel est le chiffre des dizaines dans 476 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "4"}, {"label": "B", "text": "7"}, {"label": "C", "text": "6"}],
                "correct": "B", "explanation": "476 = 4 centaines, 7 dizaines, 6 unités. Le chiffre des dizaines est 7.", "points": 1
            },
            {
                "question": "Quel est le plus grand nombre : 389 ou 398 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "389"}, {"label": "B", "text": "398"}, {"label": "C", "text": "Ils sont égaux"}],
                "correct": "B", "explanation": "398 > 389 car au rang des dizaines 9 > 8.", "points": 1
            },
            {
                "question": "245 = 2 centaines + ___ dizaines + 5 unités",
                "type": "qcm",
                "options": [{"label": "A", "text": "2"}, {"label": "B", "text": "4"}, {"label": "C", "text": "5"}],
                "correct": "B", "explanation": "245 = 200 + 40 + 5 = 2 centaines + 4 dizaines + 5 unités.", "points": 1
            },
        ]
    },
    {
        "level": "CE1", "subject": "mathematiques", "order": 2,
        "title": "La multiplication",
        "summary": "Comprendre la multiplication comme addition répétée.",
        "duration_minutes": 30,
        "content": """## La multiplication

### La multiplication = addition répétée
3 × 4 = 4 + 4 + 4 = **12**
(3 fois le nombre 4)

### Le signe ×
3 × 4 = 12 se lit : « trois **fois** quatre **égal** douze »

### Tables de multiplication (× 2, × 3, × 5)
**Table de 2** : 1×2=2, 2×2=4, 3×2=6, 4×2=8, 5×2=10
**Table de 3** : 1×3=3, 2×3=6, 3×3=9, 4×3=12, 5×3=15
**Table de 5** : 1×5=5, 2×5=10, 3×5=15, 4×5=20, 5×5=25

### Propriété
a × b = b × a (l'ordre ne change pas le résultat)
Exemple : 3 × 4 = 4 × 3 = 12

### Problème
> Une boîte contient 6 bonbons. Il y a 4 boîtes.
> Combien y a-t-il de bonbons en tout ?
> 4 × 6 = **24 bonbons**""",
        "exercises": [
            {
                "question": "Combien font 3 × 5 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "8"}, {"label": "B", "text": "15"}, {"label": "C", "text": "12"}],
                "correct": "B", "explanation": "3 × 5 = 15. La table de 5 : 1×5=5, 2×5=10, 3×5=15.", "points": 1
            },
            {
                "question": "4 × 3 est égal à :",
                "type": "qcm",
                "options": [{"label": "A", "text": "3 + 3 + 3 + 3"}, {"label": "B", "text": "4 + 3"}, {"label": "C", "text": "4 + 4 + 4"}],
                "correct": "A", "explanation": "4 × 3 = 3 répété 4 fois = 3+3+3+3 = 12.", "points": 1
            },
            {
                "question": "Il y a 5 rangées de 4 chaises. Combien de chaises en tout ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "9"}, {"label": "B", "text": "20"}, {"label": "C", "text": "24"}],
                "correct": "B", "explanation": "5 × 4 = 20 chaises.", "points": 1
            },
        ]
    },
    {
        "level": "CE1", "subject": "sciences", "order": 1,
        "title": "Les animaux",
        "summary": "Classer les animaux et comprendre leurs modes de vie.",
        "duration_minutes": 25,
        "content": """## Les animaux

### Les grandes familles d'animaux
| Famille | Caractéristiques | Exemples |
|---------|-----------------|---------|
| **Mammifères** | Poils, allaite ses petits | Vache, lion, cheval, dauphin |
| **Oiseaux** | Plumes, bec, ailes | Aigle, poule, hirondelle |
| **Reptiles** | Écailles, sang froid | Serpent, lézard, crocodile |
| **Poissons** | Écailles, vit dans l'eau | Tilapia, sardine, requin |
| **Insectes** | 6 pattes | Abeille, fourmi, moustique |

### Les animaux sauvages et domestiques
- **Domestiques** : vivent avec l'homme → chien, chat, poule, chèvre
- **Sauvages** : vivent dans la nature → lion, éléphant, hippopotame

### Les animaux du Sénégal
Le Sénégal possède de nombreux animaux sauvages : **lion**, **éléphant**, **hippopotame**, **pélican**, **hyène**...""",
        "exercises": [
            {
                "question": "À quelle famille appartient la poule ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Mammifère"}, {"label": "B", "text": "Oiseau"}, {"label": "C", "text": "Reptile"}],
                "correct": "B", "explanation": "La poule est un oiseau : elle a des plumes, un bec et des ailes.", "points": 1
            },
            {
                "question": "Combien de pattes a un insecte ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "4"}, {"label": "B", "text": "6"}, {"label": "C", "text": "8"}],
                "correct": "B", "explanation": "Tous les insectes ont exactement 6 pattes.", "points": 1
            },
            {
                "question": "Le lion est un animal :",
                "type": "qcm",
                "options": [{"label": "A", "text": "Domestique"}, {"label": "B", "text": "Sauvage"}, {"label": "C", "text": "Insecte"}],
                "correct": "B", "explanation": "Le lion vit dans la nature, c'est un animal sauvage.", "points": 1
            },
        ]
    },
    {
        "level": "CE1", "subject": "anglais", "order": 1,
        "title": "My school — Mon école",
        "summary": "Décrire l'école et les objets de la classe en anglais.",
        "duration_minutes": 25,
        "content": """## My school — Mon école

### School objects / Objets de classe
| English | Français |
|---------|---------|
| book | livre |
| pen / pencil | stylo / crayon |
| ruler | règle |
| bag | cartable |
| board | tableau |
| desk | bureau |
| chair | chaise |

### Rooms in the school / Lieux de l'école
- **classroom** = la classe
- **library** = la bibliothèque
- **playground** = la cour de récréation
- **canteen** = la cantine

### Useful sentences / Phrases utiles
> **Open your book.** (Ouvrez votre livre.)
> **Write your name.** (Écrivez votre nom.)
> **Listen to the teacher.** (Écoutez le professeur.)
> **What is this ?** → **It is a book.** (C'est un livre.)""",
        "exercises": [
            {
                "question": "What is 'crayon' in English?",
                "type": "qcm",
                "options": [{"label": "A", "text": "pen"}, {"label": "B", "text": "pencil"}, {"label": "C", "text": "ruler"}],
                "correct": "B", "explanation": "'Pencil' = crayon. 'Pen' = stylo.", "points": 1
            },
            {
                "question": "Comment dit-on 'la cour de récréation' en anglais ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "library"}, {"label": "B", "text": "canteen"}, {"label": "C", "text": "playground"}],
                "correct": "C", "explanation": "'Playground' = cour de récréation.", "points": 1
            },
            {
                "question": "What does 'Open your book' mean?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Fermez votre livre"}, {"label": "B", "text": "Ouvrez votre livre"}, {"label": "C", "text": "Lisez votre livre"}],
                "correct": "B", "explanation": "'Open' = ouvrir. 'Open your book' = Ouvrez votre livre.", "points": 1
            },
        ]
    },
    {
        "level": "CE1", "subject": "histoire-geo", "order": 1,
        "title": "Ma famille et mon quartier",
        "summary": "Décrire sa famille et s'orienter dans son quartier.",
        "duration_minutes": 25,
        "content": """## Ma famille et mon quartier

### La famille
La famille est le premier groupe social auquel on appartient.

**Types de familles au Sénégal :**
- **Famille nucléaire** : père, mère et enfants
- **Famille élargie** : grands-parents, oncles, tantes, cousins

**Les liens familiaux :**
père → fils/fille · oncle → neveu/nièce · grand-père → petit-fils/petite-fille

### Le quartier
Le **quartier** est l'espace autour de ta maison.

**Ce qu'on trouve dans un quartier :**
- École · Marché · Mosquée/Église · Centre de santé · Terrain de jeux

### S'orienter
Les **points cardinaux** : Nord (N) · Sud (S) · Est (E) · Ouest (O)
**Astuce** : Le soleil se lève à l'Est et se couche à l'Ouest.

### Respecter son quartier
- Ne pas jeter les ordures par terre
- Respecter les voisins
- Participer aux activités communautaires""",
        "exercises": [
            {
                "question": "Qu'est-ce qu'une famille élargie ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Père, mère et enfants seulement"}, {"label": "B", "text": "Père, mère, enfants, grands-parents, oncles, tantes..."}, {"label": "C", "text": "Un seul parent et ses enfants"}],
                "correct": "B", "explanation": "La famille élargie comprend la famille nucléaire plus grands-parents, oncles, tantes, cousins.", "points": 1
            },
            {
                "question": "Le soleil se lève dans quelle direction ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Ouest"}, {"label": "B", "text": "Nord"}, {"label": "C", "text": "Est"}],
                "correct": "C", "explanation": "Le soleil se lève toujours à l'Est et se couche à l'Ouest.", "points": 1
            },
            {
                "question": "Lequel de ces éléments trouve-t-on dans un quartier ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Une forêt"}, {"label": "B", "text": "Un marché"}, {"label": "C", "text": "Un désert"}],
                "correct": "B", "explanation": "Un marché est un lieu typique que l'on trouve dans les quartiers au Sénégal.", "points": 1
            },
        ]
    },

    # ──────────────────────────────────────────────────────────────────
    # CE2 — Cours Élémentaire 2ème année
    # ──────────────────────────────────────────────────────────────────

    {
        "level": "CE2", "subject": "francais", "order": 1,
        "title": "Le groupe nominal",
        "summary": "Identifier et enrichir le groupe nominal.",
        "duration_minutes": 30,
        "content": """## Le groupe nominal (GN)

### Qu'est-ce qu'un groupe nominal ?
Le groupe nominal est un mot ou groupe de mots dont le **nom** est le noyau.

### Structure du GN
**Déterminant + Nom (+ adjectif qualificatif)**
- **le** chat (déterminant + nom)
- **une** grande maison (déterminant + adjectif + nom)
- **les** petits enfants joyeux (déterminant + adjectif + nom + adjectif)

### L'accord dans le GN
Le déterminant et l'adjectif s'accordent en **genre** et en **nombre** avec le nom.
- **Le** petit **garçon** → **La** petite **fille** (féminin)
- **Le** chien noir → **Les** chiens noirs (pluriel)

### Enrichir le GN
On peut ajouter des adjectifs pour préciser le nom :
> **Un** beau **jardin** → **Un** beau **jardin** fleuri et parfumé

### Exemple d'analyse
> **Les belles fleurs rouges** poussent dans le jardin.
> GN = **Les belles fleurs rouges** (déterminant + adj + nom + adj)""",
        "exercises": [
            {
                "question": "Dans 'La petite fille joue', quel est le groupe nominal ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "joue"}, {"label": "B", "text": "La petite fille"}, {"label": "C", "text": "petite"}],
                "correct": "B", "explanation": "'La petite fille' est le groupe nominal (déterminant + adjectif + nom).", "points": 1
            },
            {
                "question": "Comment met-on 'le grand arbre' au pluriel ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "le grands arbres"}, {"label": "B", "text": "les grand arbres"}, {"label": "C", "text": "les grands arbres"}],
                "correct": "C", "explanation": "Au pluriel : le → les, grand → grands, arbre → arbres.", "points": 1
            },
            {
                "question": "Comment met-on 'un beau garçon' au féminin ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "une beau fille"}, {"label": "B", "text": "une belle fille"}, {"label": "C", "text": "un belle fille"}],
                "correct": "B", "explanation": "Au féminin : un → une, beau → belle, garçon → fille.", "points": 1
            },
        ]
    },
    {
        "level": "CE2", "subject": "mathematiques", "order": 1,
        "title": "La division",
        "summary": "Comprendre et calculer des divisions simples.",
        "duration_minutes": 30,
        "content": """## La division

### Qu'est-ce que la division ?
La division sert à **partager** une quantité en parts égales.

### Le signe ÷
12 ÷ 4 = 3 se lit : « douze **divisé par** quatre **égal** trois »

### Vocabulaire
- **12** : le dividende (ce qu'on partage)
- **4** : le diviseur (le nombre de parts)
- **3** : le quotient (résultat)

### Calculer une division
**15 ÷ 3 = ?**
On cherche combien de fois 3 entre dans 15.
3 × 1=3, 3×2=6, 3×3=9, 3×4=12, **3×5=15** → 15 ÷ 3 = **5**

### Lien avec la multiplication
La division est l'opération inverse de la multiplication.
Si 4 × 6 = 24, alors 24 ÷ 4 = 6 et 24 ÷ 6 = 4

### Problème
> 20 élèves sont répartis en groupes de 4.
> Combien y a-t-il de groupes ?
> 20 ÷ 4 = **5 groupes**""",
        "exercises": [
            {
                "question": "Combien font 18 ÷ 3 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "5"}, {"label": "B", "text": "6"}, {"label": "C", "text": "7"}],
                "correct": "B", "explanation": "18 ÷ 3 = 6 car 3 × 6 = 18.", "points": 1
            },
            {
                "question": "24 bonbons partagés en 6 groupes égaux donnent :",
                "type": "qcm",
                "options": [{"label": "A", "text": "3 bonbons par groupe"}, {"label": "B", "text": "4 bonbons par groupe"}, {"label": "C", "text": "6 bonbons par groupe"}],
                "correct": "B", "explanation": "24 ÷ 6 = 4 bonbons par groupe.", "points": 1
            },
            {
                "question": "Quelle multiplication permet de trouver 30 ÷ 5 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "5 × 5 = 25"}, {"label": "B", "text": "5 × 6 = 30"}, {"label": "C", "text": "5 × 7 = 35"}],
                "correct": "B", "explanation": "5 × 6 = 30, donc 30 ÷ 5 = 6.", "points": 1
            },
        ]
    },
    {
        "level": "CE2", "subject": "sciences", "order": 1,
        "title": "L'eau",
        "summary": "Comprendre les états de l'eau et le cycle de l'eau.",
        "duration_minutes": 30,
        "content": """## L'eau

### Les états de l'eau
L'eau peut exister sous **3 états** :

| État | Forme | Température |
|------|-------|-------------|
| **Liquide** | Coule, prend la forme du récipient | 0°C à 100°C |
| **Solide** | Glace, forme fixe | En dessous de 0°C |
| **Gazeux** | Vapeur, invisible | Au-dessus de 100°C |

### Les changements d'état
- **Fusion** : glace → eau (la glace fond)
- **Évaporation** : eau → vapeur (l'eau bout et s'évapore)
- **Condensation** : vapeur → eau (la vapeur se refroidit)
- **Solidification** : eau → glace (l'eau gèle)

### Le cycle de l'eau
1. L'eau des mers s'évapore
2. La vapeur monte et forme des nuages
3. Les nuages donnent la pluie
4. La pluie rejoint les rivières et la mer

### L'eau au Sénégal
Le fleuve **Sénégal** et le fleuve **Gambie** sont les principaux cours d'eau.""",
        "exercises": [
            {
                "question": "À quelle température l'eau devient-elle de la glace ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "En dessous de 100°C"}, {"label": "B", "text": "En dessous de 0°C"}, {"label": "C", "text": "À 50°C"}],
                "correct": "B", "explanation": "L'eau se transforme en glace (solidification) en dessous de 0°C.", "points": 1
            },
            {
                "question": "Comment s'appelle le passage de l'eau liquide à la vapeur ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Fusion"}, {"label": "B", "text": "Solidification"}, {"label": "C", "text": "Évaporation"}],
                "correct": "C", "explanation": "L'évaporation est le passage de l'eau liquide à l'état gazeux (vapeur).", "points": 1
            },
            {
                "question": "Quel est le nom du principal fleuve au Sénégal ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Le fleuve Niger"}, {"label": "B", "text": "Le fleuve Sénégal"}, {"label": "C", "text": "Le fleuve Congo"}],
                "correct": "B", "explanation": "Le fleuve Sénégal est le principal cours d'eau du pays.", "points": 1
            },
        ]
    },
    {
        "level": "CE2", "subject": "anglais", "order": 1,
        "title": "My daily routine",
        "summary": "Décrire ses activités quotidiennes en anglais.",
        "duration_minutes": 25,
        "content": """## My daily routine — Ma routine quotidienne

### Daily activities / Activités quotidiennes
| English | Français |
|---------|---------|
| wake up | se réveiller |
| have breakfast | prendre le petit-déjeuner |
| go to school | aller à l'école |
| study / learn | étudier / apprendre |
| have lunch | déjeuner |
| play | jouer |
| have dinner | dîner |
| go to bed | se coucher |

### Telling time / Dire l'heure
> I wake up **at 6 o'clock**. (Je me réveille à 6 heures.)
> School starts **at 8 o'clock**. (L'école commence à 8 heures.)

### Days of the week / Jours de la semaine
Monday · Tuesday · Wednesday · Thursday · Friday · Saturday · Sunday
(Lundi · Mardi · Mercredi · Jeudi · Vendredi · Samedi · Dimanche)

### My routine
> I wake up at 6. I have breakfast. I go to school at 8.""",
        "exercises": [
            {
                "question": "What does 'have breakfast' mean?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Aller à l'école"}, {"label": "B", "text": "Prendre le petit-déjeuner"}, {"label": "C", "text": "Se coucher"}],
                "correct": "B", "explanation": "'Have breakfast' = prendre le petit-déjeuner, le matin.", "points": 1
            },
            {
                "question": "Comment dit-on 'lundi' en anglais ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Sunday"}, {"label": "B", "text": "Friday"}, {"label": "C", "text": "Monday"}],
                "correct": "C", "explanation": "Monday = Lundi. Sunday = Dimanche. Friday = Vendredi.", "points": 1
            },
            {
                "question": "Comment dit-on 'I go to school at 8' en français ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Je rentre à 8 heures"}, {"label": "B", "text": "Je vais à l'école à 8 heures"}, {"label": "C", "text": "L'école finit à 8 heures"}],
                "correct": "B", "explanation": "'I go to school at 8' = Je vais à l'école à 8 heures.", "points": 1
            },
        ]
    },
    {
        "level": "CE2", "subject": "histoire-geo", "order": 1,
        "title": "Le Sénégal — notre pays",
        "summary": "Connaître la géographie et l'organisation du Sénégal.",
        "duration_minutes": 30,
        "content": """## Le Sénégal — notre pays

### Situation géographique
Le Sénégal est un pays d'**Afrique de l'Ouest**.
- Il est entouré par la **Mauritanie** (nord), le **Mali** (est), la **Guinée** et la **Guinée-Bissau** (sud)
- À l'ouest, il est bordé par l'**océan Atlantique**
- La **Gambie** est enclavée dans le Sénégal

### La capitale
**Dakar** est la capitale et la plus grande ville du Sénégal.

### Les régions
Le Sénégal est divisé en **14 régions** :
Dakar, Thiès, Diourbel, Fatick, Kaolack, Louga, Saint-Louis, Tambacounda, Ziguinchor, Kolda, Matam, Kaffrine, Kédougou, Sédhiou.

### Les fleuves principaux
- Le fleuve **Sénégal** (nord)
- Le fleuve **Gambie** (centre)
- La rivière **Casamance** (sud)

### Les ressources
Agriculture (arachide, mil, coton), pêche, tourisme, phosphates.""",
        "exercises": [
            {
                "question": "Quelle est la capitale du Sénégal ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Thiès"}, {"label": "B", "text": "Saint-Louis"}, {"label": "C", "text": "Dakar"}],
                "correct": "C", "explanation": "Dakar est la capitale et la plus grande ville du Sénégal.", "points": 1
            },
            {
                "question": "En combien de régions le Sénégal est-il divisé ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "10"}, {"label": "B", "text": "14"}, {"label": "C", "text": "16"}],
                "correct": "B", "explanation": "Le Sénégal est divisé en 14 régions administratives.", "points": 1
            },
            {
                "question": "Quel océan borde le Sénégal à l'ouest ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "L'océan Indien"}, {"label": "B", "text": "L'océan Pacifique"}, {"label": "C", "text": "L'océan Atlantique"}],
                "correct": "C", "explanation": "Le Sénégal est bordé à l'ouest par l'océan Atlantique.", "points": 1
            },
        ]
    },

    # ──────────────────────────────────────────────────────────────────
    # CM1 — Cours Moyen 1ère année
    # ──────────────────────────────────────────────────────────────────

    {
        "level": "CM1", "subject": "francais", "order": 1,
        "title": "La lecture compréhension",
        "summary": "Lire un texte et répondre aux questions de compréhension (CEB CM1 Palier 1).",
        "duration_minutes": 35,
        "content": """## La lecture et la compréhension

### Lire un texte avec méthode
Quand tu lis un texte, tu dois :
1. **Lire le titre** → anticipe le thème
2. **Lire en entier** une première fois
3. **Relire** en cherchant les informations importantes
4. **Répondre** aux questions en utilisant les mots du texte

### Types de questions
| Type | Exemple |
|------|---------|
| **Littérale** | La réponse est dans le texte. |
| **Déductive** | On déduit à partir du texte. |
| **Personnelle** | On donne son avis. |

### Texte d'exemple
> *La saison des pluies*
> Au Sénégal, la saison des pluies commence en juin et se termine en octobre.
> Les paysans labourent les champs et sèment le mil et l'arachide.
> Les animaux trouvent de l'herbe fraîche à manger. Les rivières reprennent vie.

### Questions sur le texte
1. Quand commence la saison des pluies ? → En juin.
2. Que font les paysans ? → Ils labourent et sèment.
3. Quelles plantes cultivent-ils ? → Le mil et l'arachide.""",
        "exercises": [
            {
                "question": "D'après le texte, quand se termine la saison des pluies au Sénégal ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "En août"}, {"label": "B", "text": "En octobre"}, {"label": "C", "text": "En décembre"}],
                "correct": "B", "explanation": "Le texte dit : 'se termine en octobre'.", "points": 1
            },
            {
                "question": "Que sèment les paysans pendant la saison des pluies ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Le maïs et le riz"}, {"label": "B", "text": "Le mil et l'arachide"}, {"label": "C", "text": "Le coton et le cacao"}],
                "correct": "B", "explanation": "Le texte mentionne 'le mil et l'arachide'.", "points": 1
            },
            {
                "question": "Une question dont la réponse est directement dans le texte est une question :",
                "type": "qcm",
                "options": [{"label": "A", "text": "personnelle"}, {"label": "B", "text": "déductive"}, {"label": "C", "text": "littérale"}],
                "correct": "C", "explanation": "Une question littérale a sa réponse clairement dans le texte.", "points": 1
            },
        ]
    },
    {
        "level": "CM1", "subject": "mathematiques", "order": 1,
        "title": "Les fractions",
        "summary": "Comprendre et manipuler les fractions simples.",
        "duration_minutes": 35,
        "content": """## Les fractions

### Qu'est-ce qu'une fraction ?
Une fraction représente une partie d'un tout.

### Écriture d'une fraction
Une fraction s'écrit avec deux nombres séparés par une barre :
> **3/4** se lit « trois quarts »
- **3** = le **numérateur** (nombre de parties prises)
- **4** = le **dénominateur** (nombre total de parties égales)

### Fractions usuelles
- **1/2** = un demi (la moitié)
- **1/4** = un quart
- **3/4** = trois quarts
- **1/3** = un tiers
- **2/3** = deux tiers

### Représentation
Si on partage une orange en 4 parts égales et qu'on prend 3 parts, on a **3/4** de l'orange.

### Comparer des fractions de même dénominateur
1/4 < 2/4 < 3/4 < 4/4 = 1 (entier)

### Additionner des fractions de même dénominateur
1/5 + 2/5 = **3/5** (on additionne les numérateurs)""",
        "exercises": [
            {
                "question": "Dans la fraction 3/5, que représente le chiffre 5 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Le numérateur"}, {"label": "B", "text": "Le dénominateur"}, {"label": "C", "text": "Le résultat"}],
                "correct": "B", "explanation": "5 est le dénominateur : il indique le nombre total de parties égales.", "points": 1
            },
            {
                "question": "Comment lit-on la fraction 1/2 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Un deuxième"}, {"label": "B", "text": "Un demi"}, {"label": "C", "text": "Deux unités"}],
                "correct": "B", "explanation": "1/2 se lit 'un demi', c'est la moitié.", "points": 1
            },
            {
                "question": "Combien font 2/7 + 3/7 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "5/14"}, {"label": "B", "text": "5/7"}, {"label": "C", "text": "6/7"}],
                "correct": "B", "explanation": "On additionne les numérateurs : 2+3=5, le dénominateur reste 7 → 5/7.", "points": 1
            },
        ]
    },
    {
        "level": "CM1", "subject": "sciences", "order": 1,
        "title": "La chaîne alimentaire",
        "summary": "Comprendre les relations alimentaires entre les êtres vivants.",
        "duration_minutes": 30,
        "content": """## La chaîne alimentaire

### Qu'est-ce qu'une chaîne alimentaire ?
Une chaîne alimentaire montre qui mange qui dans la nature.

### Les maillons de la chaîne
| Niveau | Nom | Exemple |
|--------|-----|---------|
| 1er maillon | **Producteur** (végétal) | Herbe, mil, feuilles |
| 2e maillon | **Consommateur primaire** (herbivore) | Lapin, gazelle, criquet |
| 3e maillon | **Consommateur secondaire** (carnivore) | Renard, serpent |
| 4e maillon | **Super-prédateur** | Lion, aigle |

### Exemple de chaîne au Sénégal
Herbe → Criquet → Lézard → Serpent → Aigle

### Les décomposeurs
Les **champignons** et les **bactéries** décomposent les matières mortes et enrichissent le sol.

### Équilibre de la nature
Si un maillon disparaît, toute la chaîne est perturbée.
> Si les serpents disparaissent → les rongeurs se multiplient → les récoltes sont détruites.

**À retenir** : Tout être vivant a un rôle dans l'équilibre naturel.""",
        "exercises": [
            {
                "question": "Qui est le producteur dans une chaîne alimentaire ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Le lion"}, {"label": "B", "text": "L'herbe"}, {"label": "C", "text": "Le lapin"}],
                "correct": "B", "explanation": "Le producteur est toujours un végétal (plante). Il produit sa propre nourriture.", "points": 1
            },
            {
                "question": "Dans la chaîne : Herbe → Criquet → Lézard, le criquet est :",
                "type": "qcm",
                "options": [{"label": "A", "text": "Un producteur"}, {"label": "B", "text": "Un consommateur primaire"}, {"label": "C", "text": "Un décomposeur"}],
                "correct": "B", "explanation": "Le criquet mange l'herbe (végétal) donc il est consommateur primaire (herbivore).", "points": 1
            },
            {
                "question": "Que se passe-t-il si un maillon de la chaîne disparaît ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Rien ne change"}, {"label": "B", "text": "Toute la chaîne est perturbée"}, {"label": "C", "text": "La chaîne devient plus solide"}],
                "correct": "B", "explanation": "La disparition d'un maillon déséquilibre toute la chaîne alimentaire.", "points": 1
            },
        ]
    },
    {
        "level": "CM1", "subject": "anglais", "order": 1,
        "title": "My environment",
        "summary": "Décrire l'environnement et parler de la nature en anglais.",
        "duration_minutes": 30,
        "content": """## My environment — Mon environnement

### Nature vocabulary / Vocabulaire nature
| English | Français |
|---------|---------|
| tree | arbre |
| flower | fleur |
| river | rivière |
| sea / ocean | mer / océan |
| mountain | montagne |
| forest | forêt |
| field | champ |
| sand | sable |

### Environment problems / Problèmes environnementaux
- **deforestation** = déforestation
- **pollution** = pollution
- **drought** = sécheresse
- **flood** = inondation

### Protect nature / Protéger la nature
> **We must** plant trees. (Nous devons planter des arbres.)
> **We must not** throw rubbish. (Nous ne devons pas jeter des ordures.)
> **Let's protect** our environment. (Protégeons notre environnement.)

### Seasons in Senegal / Saisons au Sénégal
- **Dry season** (saison sèche) : November to May
- **Rainy season** (saison des pluies) : June to October""",
        "exercises": [
            {
                "question": "What is 'forêt' in English?",
                "type": "qcm",
                "options": [{"label": "A", "text": "field"}, {"label": "B", "text": "mountain"}, {"label": "C", "text": "forest"}],
                "correct": "C", "explanation": "'Forest' = forêt en français.", "points": 1
            },
            {
                "question": "Comment dit-on 'déforestation' en anglais ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "pollution"}, {"label": "B", "text": "deforestation"}, {"label": "C", "text": "flood"}],
                "correct": "B", "explanation": "'Deforestation' = déforestation. Ce mot est très similaire en anglais et en français.", "points": 1
            },
            {
                "question": "When is the rainy season in Senegal?",
                "type": "qcm",
                "options": [{"label": "A", "text": "November to May"}, {"label": "B", "text": "June to October"}, {"label": "C", "text": "January to March"}],
                "correct": "B", "explanation": "The rainy season (saison des pluies) in Senegal is from June to October.", "points": 1
            },
        ]
    },
    {
        "level": "CM1", "subject": "histoire-geo", "order": 1,
        "title": "L'Afrique de l'Ouest",
        "summary": "Connaître la géographie et les pays d'Afrique de l'Ouest.",
        "duration_minutes": 30,
        "content": """## L'Afrique de l'Ouest

### Situation géographique
L'Afrique de l'Ouest est une sous-région de l'Afrique.
Elle est bordée :
- Au nord : le **Sahara**
- À l'ouest et au sud : l'**océan Atlantique**
- À l'est : l'**Afrique Centrale**

### Les pays d'Afrique de l'Ouest (CEDEAO)
Sénégal · Gambie · Guinée-Bissau · Guinée · Sierra Leone · Libéria · Côte d'Ivoire · Ghana · Togo · Bénin · Nigéria · Niger · Burkina Faso · Mali · Mauritanie · Cap-Vert

### Les grands fleuves
- Le **Niger** : le fleuve le plus long (traversant Mali, Niger, Nigéria)
- Le **Sénégal** : entre Sénégal et Mauritanie
- La **Volta** : au Ghana et Burkina Faso

### La CEDEAO
La **Communauté Économique des États d'Afrique de l'Ouest** (CEDEAO) regroupe 15 pays pour coopérer économiquement.

### Histoire : les grands empires
L'Afrique de l'Ouest fut le berceau de grands empires :
- L'empire du **Ghana** (4e-13e siècle)
- L'empire du **Mali** (13e-16e siècle)
- L'empire **Songhaï** (15e-16e siècle)""",
        "exercises": [
            {
                "question": "Quel est le fleuve le plus long d'Afrique de l'Ouest ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Le fleuve Sénégal"}, {"label": "B", "text": "Le Niger"}, {"label": "C", "text": "La Volta"}],
                "correct": "B", "explanation": "Le Niger est le fleuve le plus long d'Afrique de l'Ouest.", "points": 1
            },
            {
                "question": "Que signifie CEDEAO ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Communauté des États d'Afrique Orientale"}, {"label": "B", "text": "Communauté Économique des États d'Afrique de l'Ouest"}, {"label": "C", "text": "Centre d'Éducation des Enfants d'Afrique Occidentale"}],
                "correct": "B", "explanation": "CEDEAO = Communauté Économique des États d'Afrique de l'Ouest.", "points": 1
            },
            {
                "question": "Quel grand empire africain a existé du 13e au 16e siècle ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "L'empire du Ghana"}, {"label": "B", "text": "L'empire du Mali"}, {"label": "C", "text": "L'empire Romain"}],
                "correct": "B", "explanation": "L'empire du Mali a existé du 13e au 16e siècle, après l'empire du Ghana.", "points": 1
            },
        ]
    },

    # ──────────────────────────────────────────────────────────────────
    # CM2 — Cours Moyen 2ème année
    # ──────────────────────────────────────────────────────────────────

    {
        "level": "CM2", "subject": "francais", "order": 1,
        "title": "La rédaction — raconter un événement",
        "summary": "Rédiger un texte narratif cohérent (CEB CM2 Palier lecture/oral).",
        "duration_minutes": 40,
        "content": """## La rédaction — Raconter un événement

### Qu'est-ce qu'un texte narratif ?
Un texte narratif **raconte** une histoire ou un événement réel ou imaginaire.
Il répond aux questions : **Qui ? Quoi ? Quand ? Où ? Comment ?**

### La structure d'un texte narratif
1. **Introduction** : présente les personnages, le lieu, le moment
2. **Développement** : raconte l'histoire, les événements
3. **Conclusion** : fin de l'histoire, résultat

### Connecteurs de temps pour bien raconter
| Connecteur | Usage |
|------------|-------|
| D'abord, Au début | Commencer |
| Ensuite, Puis, Après | Continuer |
| Enfin, Finalement | Terminer |
| Soudain, Tout à coup | Événement inattendu |

### Le passé composé dans les récits
> Hier, Moussa **a trouvé** un billet dans la rue.
> Il **a cherché** le propriétaire toute la journée.
> Finalement, il **a remis** le billet au commissariat.

### Modèle de rédaction
**Sujet** : Raconte un événement qui t'a marqué(e).
Introduction → Développement avec connecteurs → Conclusion avec ta réaction.""",
        "exercises": [
            {
                "question": "Dans quel ordre se présente un texte narratif ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Conclusion → Développement → Introduction"}, {"label": "B", "text": "Introduction → Développement → Conclusion"}, {"label": "C", "text": "Développement → Introduction → Conclusion"}],
                "correct": "B", "explanation": "Un texte narratif suit toujours : Introduction → Développement → Conclusion.", "points": 1
            },
            {
                "question": "Quel connecteur utilise-t-on pour terminer un récit ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "D'abord"}, {"label": "B", "text": "Ensuite"}, {"label": "C", "text": "Enfin"}],
                "correct": "C", "explanation": "'Enfin' ou 'Finalement' servent à conclure un récit.", "points": 1
            },
            {
                "question": "Quelle question un texte narratif doit-il répondre ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Pourquoi et comment quelque chose fonctionne-t-il ?"}, {"label": "B", "text": "Qui ? Quoi ? Quand ? Où ? Comment ?"}, {"label": "C", "text": "Quelle est ton opinion sur ce sujet ?"}],
                "correct": "B", "explanation": "Un texte narratif répond aux questions : Qui ? Quoi ? Quand ? Où ? Comment ?", "points": 1
            },
        ]
    },
    {
        "level": "CM2", "subject": "mathematiques", "order": 1,
        "title": "Les pourcentages",
        "summary": "Comprendre et calculer des pourcentages.",
        "duration_minutes": 35,
        "content": """## Les pourcentages

### Qu'est-ce qu'un pourcentage ?
Un **pourcentage** exprime une quantité **pour 100**.
Le symbole est **%** (pour cent).

### Comprendre 50%
50% = 50 pour 100 = 50/100 = **1/2** (la moitié)
> Si un article coûte 1000 F et est soldé à **50%**, tu paies : 1000 - 500 = **500 F**

### Calcul d'un pourcentage
**p% d'un nombre N = (p × N) / 100**

Exemples :
- 20% de 500 = (20 × 500) / 100 = 10 000 / 100 = **100**
- 25% de 200 = (25 × 200) / 100 = 5 000 / 100 = **50**
- 10% de 350 = **35** (facile : enlever le dernier chiffre !)

### Pourcentages courants
| % | Fraction | Sens |
|---|----------|------|
| 10% | 1/10 | Un dixième |
| 25% | 1/4 | Un quart |
| 50% | 1/2 | La moitié |
| 75% | 3/4 | Trois quarts |
| 100% | 1 | Le tout entier |

### Problème
> Un élève a eu 15/20 à un devoir. Quel est son score en pourcentage ?
> (15 × 100) / 20 = **75%**""",
        "exercises": [
            {
                "question": "Combien font 10% de 300 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "3"}, {"label": "B", "text": "30"}, {"label": "C", "text": "300"}],
                "correct": "B", "explanation": "10% de 300 = (10 × 300) / 100 = 30.", "points": 1
            },
            {
                "question": "50% est équivalent à quelle fraction ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "1/4"}, {"label": "B", "text": "1/2"}, {"label": "C", "text": "3/4"}],
                "correct": "B", "explanation": "50% = 50/100 = 1/2. C'est la moitié.", "points": 1
            },
            {
                "question": "Un sac coûte 2000 F. Il est soldé à 25%. Combien coûte la réduction ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "250 F"}, {"label": "B", "text": "500 F"}, {"label": "C", "text": "750 F"}],
                "correct": "B", "explanation": "25% de 2000 = (25 × 2000) / 100 = 500 F de réduction.", "points": 1
            },
        ]
    },
    {
        "level": "CM2", "subject": "sciences", "order": 1,
        "title": "Le système solaire",
        "summary": "Connaître les planètes et l'organisation du système solaire.",
        "duration_minutes": 35,
        "content": """## Le système solaire

### Le Soleil
Le **Soleil** est une **étoile** au centre du système solaire.
Il donne chaleur et lumière à la Terre. Sans lui, pas de vie.

### Les 8 planètes
Dans l'ordre du plus proche au plus loin du Soleil :

| Planète | Particularité |
|---------|--------------|
| **Mercure** | La plus petite, la plus proche |
| **Vénus** | La plus chaude |
| **Terre** | Notre planète, avec eau et vie |
| **Mars** | La planète rouge |
| **Jupiter** | La plus grande |
| **Saturne** | Avec ses anneaux |
| **Uranus** | Tourne sur le côté |
| **Neptune** | La plus éloignée |

**Moyen mémo** : Mon Vélo Est Moyen, Je S'en Uis Notré (M-V-E-M-J-S-U-N)

### La Terre dans le système solaire
- La Terre tourne sur elle-même en **24 heures** (1 jour)
- La Terre tourne autour du Soleil en **365 jours** (1 an)
- La Lune tourne autour de la Terre en **29 jours** environ

### L'univers
Le système solaire fait partie de la **Voie Lactée**, notre galaxie.""",
        "exercises": [
            {
                "question": "Quelle est la planète la plus proche du Soleil ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Vénus"}, {"label": "B", "text": "Mercure"}, {"label": "C", "text": "Mars"}],
                "correct": "B", "explanation": "Mercure est la planète la plus proche du Soleil.", "points": 1
            },
            {
                "question": "En combien de temps la Terre fait-elle le tour du Soleil ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "24 heures"}, {"label": "B", "text": "30 jours"}, {"label": "C", "text": "365 jours"}],
                "correct": "C", "explanation": "La Terre tourne autour du Soleil en 365 jours, soit 1 an.", "points": 1
            },
            {
                "question": "Combien y a-t-il de planètes dans le système solaire ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "7"}, {"label": "B", "text": "8"}, {"label": "C", "text": "9"}],
                "correct": "B", "explanation": "Il y a 8 planètes : Mercure, Vénus, Terre, Mars, Jupiter, Saturne, Uranus, Neptune.", "points": 1
            },
        ]
    },
    {
        "level": "CM2", "subject": "anglais", "order": 1,
        "title": "The environment",
        "summary": "Parler de l'environnement et de sa protection en anglais.",
        "duration_minutes": 30,
        "content": """## The environment — L'environnement

### Environmental problems / Problèmes environnementaux
| English | Français |
|---------|---------|
| climate change | changement climatique |
| global warming | réchauffement climatique |
| pollution | pollution |
| deforestation | déforestation |
| drought | sécheresse |
| flooding | inondation |
| waste / rubbish | déchets / ordures |

### Solutions / Solutions
> **We should** reduce waste. (Nous devrions réduire les déchets.)
> **We must** plant more trees. (Nous devons planter plus d'arbres.)
> **We should not** cut down forests. (Nous ne devrions pas couper les forêts.)
> **Recycle** paper, glass and plastic. (Recycler le papier, le verre et le plastique.)

### Talking about the future / Parler du futur
> The Earth **will become** hotter. (La Terre deviendra plus chaude.)
> We **will face** more droughts. (Nous ferons face à plus de sécheresses.)

### Actions for the planet
3R : **Reduce** · **Reuse** · **Recycle**""",
        "exercises": [
            {
                "question": "What does 'global warming' mean?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Déforestation"}, {"label": "B", "text": "Réchauffement climatique"}, {"label": "C", "text": "Sécheresse"}],
                "correct": "B", "explanation": "'Global warming' = réchauffement climatique.", "points": 1
            },
            {
                "question": "What are the 3R in environmental protection?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Reduce, Reuse, Recycle"}, {"label": "B", "text": "Read, Run, Rest"}, {"label": "C", "text": "React, Respond, Report"}],
                "correct": "A", "explanation": "The 3R for environment are : Reduce (réduire), Reuse (réutiliser), Recycle (recycler).", "points": 1
            },
            {
                "question": "Comment dit-on 'Nous devons planter plus d'arbres' en anglais ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "We should cut down trees"}, {"label": "B", "text": "We must plant more trees"}, {"label": "C", "text": "Trees must be reduced"}],
                "correct": "B", "explanation": "'We must plant more trees' = Nous devons planter plus d'arbres.", "points": 1
            },
        ]
    },
    {
        "level": "CM2", "subject": "histoire-geo", "order": 1,
        "title": "Le Sénégal dans l'Afrique et le monde",
        "summary": "Situer le Sénégal dans son contexte africain et mondial.",
        "duration_minutes": 35,
        "content": """## Le Sénégal dans l'Afrique et le monde

### L'Afrique
L'Afrique est le **deuxième plus grand continent** du monde.
- Superficie : 30 millions de km²
- Population : environ 1,4 milliard d'habitants
- **54 pays** indépendants
- Traversée par l'**équateur** et les tropiques

### Le Sénégal dans l'Afrique
- Superficie : **196 722 km²**
- Population : environ **17 millions d'habitants**
- Membre de la **CEDEAO** (Communauté Économique des États d'Afrique de l'Ouest)
- Membre de l'**Union Africaine** (UA)

### Histoire du Sénégal
- Royaumes wolofs (Djolof, Waalo, Cayor, Bawol, Sine, Saloum)
- Colonisation française (1850-1960)
- **Indépendance le 4 août 1960** (Léopold Sédar Senghor, premier président)
- République du Sénégal avec constitution démocratique

### Le Sénégal dans le monde
- Membre de l'**ONU** (Organisation des Nations Unies)
- Membre de l'**OIF** (Organisation Internationale de la Francophonie)
- Langue officielle : **Français** (langues nationales : wolof, pulaar, sérère, mandingue...)

### Ressources et économie
Agriculture, pêche, tourisme, industrie minière (phosphates, zircon, or).""",
        "exercises": [
            {
                "question": "Quand le Sénégal a-t-il obtenu son indépendance ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "4 août 1960"}, {"label": "B", "text": "4 avril 1960"}, {"label": "C", "text": "4 août 1945"}],
                "correct": "A", "explanation": "Le Sénégal a obtenu son indépendance le 4 août 1960.", "points": 1
            },
            {
                "question": "Quel était le premier président du Sénégal ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Abdou Diouf"}, {"label": "B", "text": "Léopold Sédar Senghor"}, {"label": "C", "text": "Abdoulaye Wade"}],
                "correct": "B", "explanation": "Léopold Sédar Senghor fut le premier président du Sénégal (1960-1980).", "points": 1
            },
            {
                "question": "Combien de pays l'Afrique compte-t-elle ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "47"}, {"label": "B", "text": "54"}, {"label": "C", "text": "62"}],
                "correct": "B", "explanation": "L'Afrique compte 54 pays indépendants reconnus.", "points": 1
            },
        ]
    },
]


# ═══════════════════════════════════════════════════════════════════════
#  FONCTIONS DE SEEDING
# ═══════════════════════════════════════════════════════════════════════

async def seed_lessons():
    """Importe toutes les leçons et exercices en base de données."""
    await create_tables()

    async with AsyncSessionLocal() as db:
        created = 0
        for lesson_data in LESSONS_DATA:
            exercises_data = lesson_data.pop("exercises", [])

            lesson = Lesson(
                title=lesson_data["title"],
                subject=lesson_data["subject"],
                level=lesson_data["level"],
                order_in_subject=lesson_data["order"],
                content=lesson_data["content"],
                summary=lesson_data.get("summary", ""),
                duration_minutes=lesson_data.get("duration_minutes", 20),
                is_active=True,
            )
            db.add(lesson)
            await db.flush()

            for i, ex_data in enumerate(exercises_data):
                options_json = __import__("json").dumps(
                    ex_data.get("options", []), ensure_ascii=False
                )
                ex = Exercise(
                    lesson_id=lesson.id,
                    question=ex_data["question"],
                    exercise_type=ex_data.get("type", "qcm"),
                    options=options_json,
                    correct_answer=ex_data["correct"],
                    explanation=ex_data.get("explanation", ""),
                    points=ex_data.get("points", 1),
                    order_in_lesson=i + 1,
                    is_active=True,
                )
                db.add(ex)
            created += 1

        await db.commit()
        print(f"✅ {created} leçons importées ({sum(len(d.get('exercises', [])) for d in LESSONS_DATA)} exercices)")
        return created


if __name__ == "__main__":
    asyncio.run(seed_lessons())
