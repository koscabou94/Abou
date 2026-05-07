"""
Script de peuplement de la base de données avec les leçons et exercices EduBot.
Aligné sur le Curriculum CEB officiel du Sénégal (CI → CM2).

Lancer depuis le dossier backend :
    python -m app.services.seed_lessons

Matières couvertes : Français, Mathématiques, Sciences, Anglais, Histoire-Géo
Niveaux : CI, CP, CE1, CE2, CM1, CM2
"""

import asyncio
import json
from app.database.connection import AsyncSessionLocal, create_tables
from app.database.models import Lesson, Exercise


# ═══════════════════════════════════════════════════════════════
# CONTENU DES LEÇONS PAR NIVEAU ET MATIÈRE
# ═══════════════════════════════════════════════════════════════

LESSONS_DATA = [

    # ───────────────────────────────────────────────────────────
    # NIVEAU CI — Cours d'Initiation
    # ───────────────────────────────────────────────────────────
    {
        "level": "CI", "subject": "francais", "order": 1,
        "title": "Les salutations",
        "summary": "Apprendre à saluer et se présenter en français.",
        "duration_minutes": 15,
        "content": """## Les salutations

Bonjour ! Saluer quelqu'un est la première chose que l'on apprend.

### Comment saluer ?

- **Le matin** → on dit : *Bonjour !*
- **L'après-midi** → on dit : *Bonsoir !*
- **Pour partir** → on dit : *Au revoir !*

### Se présenter

Pour dire qui tu es, tu dis :
> *Je m'appelle Fatou. J'ai 6 ans. J'habite à Dakar.*

### Demander des nouvelles

- *Comment tu t'appelles ?*
- *Comment ça va ?* → On répond : *Ça va bien, merci !*

### À retenir

Toujours saluer poliment les adultes et les camarades !""",
        "exercises": [
            {
                "question": "Comment dit-on bonjour le matin ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Bonsoir"}, {"label": "B", "text": "Bonjour"}, {"label": "C", "text": "Au revoir"}],
                "correct": "B",
                "explanation": "On dit 'Bonjour' le matin et 'Bonsoir' l'après-midi ou le soir.",
                "points": 1
            },
            {
                "question": "Pour dire qui tu es, tu commences par : 'Je m'___ ...'",
                "type": "qcm",
                "options": [{"label": "A", "text": "appel"}, {"label": "B", "text": "appelle"}, {"label": "C", "text": "nomme"}],
                "correct": "B",
                "explanation": "On dit 'Je m'appelle' suivi de son prénom pour se présenter.",
                "points": 1
            },
            {
                "question": "Quand tu pars de chez ton ami, tu lui dis :",
                "type": "qcm",
                "options": [{"label": "A", "text": "Bonjour !"}, {"label": "B", "text": "Bonsoir !"}, {"label": "C", "text": "Au revoir !"}],
                "correct": "C",
                "explanation": "'Au revoir' est la formule de politesse pour quitter quelqu'un.",
                "points": 1
            }
        ]
    },
    {
        "level": "CI", "subject": "francais", "order": 2,
        "title": "Les lettres de l'alphabet",
        "summary": "Reconnaître et nommer les lettres de l'alphabet français.",
        "duration_minutes": 20,
        "content": """## Les lettres de l'alphabet

L'alphabet français a **26 lettres**.

### Les voyelles
Les voyelles sont : **A, E, I, O, U, Y**

Ce sont des sons que l'on peut chanter tout seul.

### Les consonnes
Toutes les autres lettres sont des consonnes : B, C, D, F, G, H, J, K, L, M, N, P, Q, R, S, T, V, W, X, Z

### Minuscules et majuscules

Chaque lettre existe en deux formes :
- **Majuscule** : A, B, C ... (grande lettre, au début d'un nom ou d'une phrase)
- **Minuscule** : a, b, c ... (petite lettre, dans les mots)

### Exercice de mémorisation

Répète l'alphabet en chantant : A-B-C-D-E-F-G-H-I-J-K-L-M-N-O-P-Q-R-S-T-U-V-W-X-Y-Z""",
        "exercises": [
            {
                "question": "Combien de lettres y a-t-il dans l'alphabet français ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "24"}, {"label": "B", "text": "25"}, {"label": "C", "text": "26"}],
                "correct": "C",
                "explanation": "L'alphabet français contient exactement 26 lettres.",
                "points": 1
            },
            {
                "question": "Parmi ces lettres, laquelle est une voyelle ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "B"}, {"label": "B", "text": "O"}, {"label": "C", "text": "D"}],
                "correct": "B",
                "explanation": "Les voyelles sont A, E, I, O, U, Y. La lettre O est une voyelle.",
                "points": 1
            },
            {
                "question": "La lettre majuscule de 'a' est :",
                "type": "qcm",
                "options": [{"label": "A", "text": "A"}, {"label": "B", "text": "Â"}, {"label": "C", "text": "À"}],
                "correct": "A",
                "explanation": "La majuscule de 'a' est 'A'. Les majuscules sont les grandes lettres.",
                "points": 1
            }
        ]
    },
    {
        "level": "CI", "subject": "mathematiques", "order": 1,
        "title": "Les nombres de 1 à 10",
        "summary": "Compter, lire et écrire les nombres de 1 à 10.",
        "duration_minutes": 20,
        "content": """## Les nombres de 1 à 10

Apprendre à compter est très important !

### Les chiffres

| Chiffre | Mot | Exemple |
|---------|-----|---------|
| 1 | un | 1 mangue |
| 2 | deux | 2 yeux |
| 3 | trois | 3 roues de tricycle |
| 4 | quatre | 4 pattes du chat |
| 5 | cinq | 5 doigts d'une main |
| 6 | six | 6 oeufs |
| 7 | sept | 7 jours dans une semaine |
| 8 | huit | 8 pattes de l'araignée |
| 9 | neuf | 9 planètes |
| 10 | dix | 10 doigts des deux mains |

### Compter avec les doigts

Lève les doigts un par un en comptant : 1, 2, 3, 4, 5... jusqu'à 10 !

### Ordre des nombres

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

Le nombre qui vient **avant** 5 est 4. Le nombre qui vient **après** 5 est 6.""",
        "exercises": [
            {
                "question": "Combien font 3 + 2 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "4"}, {"label": "B", "text": "5"}, {"label": "C", "text": "6"}],
                "correct": "B",
                "explanation": "3 + 2 = 5. Compte sur tes doigts : 1, 2, 3 ... puis 4, 5 !",
                "points": 1
            },
            {
                "question": "Quel nombre vient après 7 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "6"}, {"label": "B", "text": "8"}, {"label": "C", "text": "9"}],
                "correct": "B",
                "explanation": "Après 7 vient 8. L'ordre est : 6, 7, 8, 9, 10.",
                "points": 1
            },
            {
                "question": "J'ai 4 mangues. J'en donne 1 à ma sœur. Combien m'en reste-t-il ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "2"}, {"label": "B", "text": "3"}, {"label": "C", "text": "5"}],
                "correct": "B",
                "explanation": "4 - 1 = 3. Si tu enlèves 1 mangue sur 4, il en reste 3.",
                "points": 1
            }
        ]
    },

    # ───────────────────────────────────────────────────────────
    # NIVEAU CP — Cours Préparatoire
    # ───────────────────────────────────────────────────────────
    {
        "level": "CP", "subject": "francais", "order": 1,
        "title": "Le nom et l'article",
        "summary": "Reconnaître les noms et les articles (le, la, les, un, une, des).",
        "duration_minutes": 20,
        "content": """## Le nom et l'article

### Qu'est-ce qu'un nom ?

Un **nom** désigne une personne, un animal, une chose ou un lieu.

Exemples :
- *Fatou* est un nom de personne
- *chat* est un nom d'animal
- *maison* est un nom de chose
- *Dakar* est un nom de lieu

### Les articles

L'article accompagne toujours le nom. Il y en a deux familles :

**Articles définis** (on sait de quoi on parle) :
- **le** → le garçon, le livre
- **la** → la fille, la mangue
- **les** → les enfants, les fleurs

**Articles indéfinis** (on ne sait pas encore lequel) :
- **un** → un garçon, un stylo
- **une** → une fille, une table
- **des** → des enfants, des fruits

### Masculin ou féminin ?

- Les noms masculins prennent **le** ou **un**
- Les noms féminins prennent **la** ou **une**""",
        "exercises": [
            {
                "question": "Quel est l'article correct pour le mot 'maison' ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "le"}, {"label": "B", "text": "la"}, {"label": "C", "text": "les"}],
                "correct": "B",
                "explanation": "'Maison' est un nom féminin. On dit 'la maison'.",
                "points": 1
            },
            {
                "question": "Dans 'Le chat mange une souris', quel mot est un nom d'animal ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "mange"}, {"label": "B", "text": "chat"}, {"label": "C", "text": "une"}],
                "correct": "B",
                "explanation": "'Chat' est un nom d'animal. 'Mange' est un verbe, 'une' est un article.",
                "points": 1
            },
            {
                "question": "Quel article faut-il mettre devant 'livre' ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "la"}, {"label": "B", "text": "le"}, {"label": "C", "text": "une"}],
                "correct": "B",
                "explanation": "'Livre' est un nom masculin. On dit 'le livre' ou 'un livre'.",
                "points": 1
            }
        ]
    },
    {
        "level": "CP", "subject": "francais", "order": 2,
        "title": "La phrase : sujet et verbe",
        "summary": "Identifier le sujet et le verbe dans une phrase simple.",
        "duration_minutes": 20,
        "content": """## La phrase : sujet et verbe

### Qu'est-ce qu'une phrase ?

Une phrase est un ensemble de mots qui a un **sens complet**. Elle commence par une **majuscule** et se termine par un **point**.

Exemple : *Aminata joue dans la cour.*

### Le sujet

Le **sujet** est celui qui fait l'action. Pour le trouver, on pose la question : **Qui est-ce qui... ?**

*Aminata joue.* → Qui est-ce qui joue ? → **Aminata** est le sujet.

### Le verbe

Le **verbe** indique l'action ou l'état. Pour le trouver, on pose la question : **Qu'est-ce qu'il/elle fait ?**

*Aminata joue.* → Qu'est-ce qu'elle fait ? → **joue** est le verbe.

### Exemples

| Phrase | Sujet | Verbe |
|--------|-------|-------|
| *Le chien court.* | Le chien | court |
| *Mamadou mange du pain.* | Mamadou | mange |
| *Les enfants chantent.* | Les enfants | chantent |""",
        "exercises": [
            {
                "question": "Dans 'Oumar lit un livre', quel est le sujet ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "lit"}, {"label": "B", "text": "livre"}, {"label": "C", "text": "Oumar"}],
                "correct": "C",
                "explanation": "Le sujet est celui qui fait l'action. Qui est-ce qui lit ? → Oumar.",
                "points": 1
            },
            {
                "question": "Dans 'Le soleil brille', quel est le verbe ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Le"}, {"label": "B", "text": "soleil"}, {"label": "C", "text": "brille"}],
                "correct": "C",
                "explanation": "'Brille' est le verbe, il indique ce que fait le soleil.",
                "points": 1
            },
            {
                "question": "Quelle phrase commence correctement ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "fatou mange du riz."}, {"label": "B", "text": "Fatou mange du riz."}, {"label": "C", "text": "fatou Mange du riz."}],
                "correct": "B",
                "explanation": "Une phrase commence toujours par une majuscule. Seul 'Fatou' prend une majuscule au début.",
                "points": 1
            }
        ]
    },
    {
        "level": "CP", "subject": "mathematiques", "order": 1,
        "title": "Les nombres jusqu'à 100",
        "summary": "Lire, écrire et comparer les nombres de 10 à 100.",
        "duration_minutes": 25,
        "content": """## Les nombres jusqu'à 100

### Les dizaines

Quand on compte 10 unités, on forme une **dizaine**.

| Dizaines | Nombre | En lettres |
|----------|--------|------------|
| 1 dizaine | 10 | dix |
| 2 dizaines | 20 | vingt |
| 3 dizaines | 30 | trente |
| 4 dizaines | 40 | quarante |
| 5 dizaines | 50 | cinquante |
| 6 dizaines | 60 | soixante |
| 7 dizaines | 70 | soixante-dix |
| 8 dizaines | 80 | quatre-vingts |
| 9 dizaines | 90 | quatre-vingt-dix |
| 10 dizaines | 100 | cent |

### Décomposer un nombre

**45 = 4 dizaines + 5 unités**

On dit : quarante-cinq

**73 = 7 dizaines + 3 unités**

On dit : soixante-treize

### Comparer les nombres

Le signe **>** signifie "plus grand que" : 52 > 35

Le signe **<** signifie "plus petit que" : 27 < 48""",
        "exercises": [
            {
                "question": "Combien y a-t-il de dizaines dans le nombre 60 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "5"}, {"label": "B", "text": "6"}, {"label": "C", "text": "60"}],
                "correct": "B",
                "explanation": "60 = 6 dizaines + 0 unités. Il y a 6 dizaines dans 60.",
                "points": 1
            },
            {
                "question": "Comment écrit-on le nombre 'quarante-deux' en chiffres ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "24"}, {"label": "B", "text": "42"}, {"label": "C", "text": "40"}],
                "correct": "B",
                "explanation": "Quarante-deux = 4 dizaines et 2 unités = 42.",
                "points": 1
            },
            {
                "question": "Quel nombre est le plus grand ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "37"}, {"label": "B", "text": "73"}, {"label": "C", "text": "57"}],
                "correct": "B",
                "explanation": "73 est le plus grand. Il a 7 dizaines, alors que 37 a 3 dizaines et 57 en a 5.",
                "points": 1
            }
        ]
    },

    # ───────────────────────────────────────────────────────────
    # NIVEAU CE1
    # ───────────────────────────────────────────────────────────
    {
        "level": "CE1", "subject": "francais", "order": 1,
        "title": "Le verbe : conjugaison au présent",
        "summary": "Conjuguer les verbes du 1er groupe au présent de l'indicatif.",
        "duration_minutes": 25,
        "content": """## Le verbe : conjugaison au présent

### Les verbes du 1er groupe

Les verbes du 1er groupe se terminent par **-ER** à l'infinitif.
Exemples : *manger, jouer, chanter, parler, travailler*

### Conjugaison au présent

Voici les terminaisons pour les verbes en -ER :

| Pronom | Terminaison | Exemple (chanter) |
|--------|-------------|-------------------|
| Je | -e | je chant**e** |
| Tu | -es | tu chant**es** |
| Il/Elle | -e | il chant**e** |
| Nous | -ons | nous chant**ons** |
| Vous | -ez | vous chant**ez** |
| Ils/Elles | -ent | ils chant**ent** |

### Comment conjuguer ?

1. Prendre l'infinitif : *chanter*
2. Enlever **-er** : *chant-*
3. Ajouter la terminaison selon le pronom

**Exemple avec MANGER :**
- Je mange, tu manges, il mange, nous mangeons, vous mangez, ils mangent

> Attention : avec NOUS, les verbes en -GER prennent un **e** : *nous mangeons*""",
        "exercises": [
            {
                "question": "Conjugue le verbe 'jouer' à la 1ère personne du singulier (je) :",
                "type": "qcm",
                "options": [{"label": "A", "text": "je jouez"}, {"label": "B", "text": "je joue"}, {"label": "C", "text": "je joues"}],
                "correct": "B",
                "explanation": "Je + verbe en -er = je jou-e. On enlève -er et on ajoute -e.",
                "points": 1
            },
            {
                "question": "Quelle est la bonne conjugaison ? 'Nous _____ (parler) français.'",
                "type": "qcm",
                "options": [{"label": "A", "text": "parlons"}, {"label": "B", "text": "parlez"}, {"label": "C", "text": "parlent"}],
                "correct": "A",
                "explanation": "Avec 'nous', la terminaison est -ons : nous parl-ons.",
                "points": 1
            },
            {
                "question": "Complète : 'Elles _____ (chanter) une belle chanson.'",
                "type": "qcm",
                "options": [{"label": "A", "text": "chante"}, {"label": "B", "text": "chantez"}, {"label": "C", "text": "chantent"}],
                "correct": "C",
                "explanation": "Avec 'elles', la terminaison est -ent : elles chant-ent.",
                "points": 1
            }
        ]
    },
    {
        "level": "CE1", "subject": "mathematiques", "order": 1,
        "title": "L'addition et la soustraction",
        "summary": "Effectuer des additions et soustractions avec des nombres jusqu'à 999.",
        "duration_minutes": 30,
        "content": """## L'addition et la soustraction

### L'addition

L'addition consiste à **réunir** des quantités.

**Technique de calcul posé :**

```
  247
+ 135
-----
  382
```

Règle : on additionne colonne par colonne en commençant par les **unités** (à droite).

**Exemple :** 247 + 135
- Unités : 7 + 5 = 12, on écrit 2 et on **retient** 1
- Dizaines : 4 + 3 + 1 (retenu) = 8
- Centaines : 2 + 1 = 3
- Résultat : **382**

### La soustraction

La soustraction consiste à **enlever** une quantité.

**Exemple :** 543 - 218
- Unités : 3 - 8 impossible → on emprunte : 13 - 8 = 5
- Dizaines : 4 - 1 (emprunté) - 1 = 2
- Centaines : 5 - 2 = 3
- Résultat : **325**

### Vérification

Pour vérifier une soustraction, on additionne :
325 + 218 = 543 ✓""",
        "exercises": [
            {
                "question": "Combien font 345 + 248 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "583"}, {"label": "B", "text": "593"}, {"label": "C", "text": "593"}],
                "correct": "B",
                "explanation": "345 + 248 : unités 5+8=13 (pose 3 retiens 1), dizaines 4+4+1=9, centaines 3+2=5. Résultat : 593.",
                "points": 2
            },
            {
                "question": "Combien font 700 - 253 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "447"}, {"label": "B", "text": "457"}, {"label": "C", "text": "453"}],
                "correct": "A",
                "explanation": "700 - 253 = 447. Vérifie : 447 + 253 = 700 ✓",
                "points": 2
            },
            {
                "question": "Fatou a 450 F CFA. Elle achète un cahier à 175 F CFA. Combien lui reste-t-il ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "275 F"}, {"label": "B", "text": "285 F"}, {"label": "C", "text": "265 F"}],
                "correct": "A",
                "explanation": "450 - 175 = 275 F CFA. Vérifie : 275 + 175 = 450 ✓",
                "points": 2
            }
        ]
    },

    # ───────────────────────────────────────────────────────────
    # NIVEAU CE2
    # ───────────────────────────────────────────────────────────
    {
        "level": "CE2", "subject": "mathematiques", "order": 1,
        "title": "La multiplication",
        "summary": "Comprendre et pratiquer la multiplication, les tables de 2 à 9.",
        "duration_minutes": 30,
        "content": """## La multiplication

### Qu'est-ce que la multiplication ?

La multiplication est une **addition répétée**.

**Exemple :** 4 × 3 = 4 + 4 + 4 = 12

On dit : "4 fois 3 égale 12"

### Les tables de multiplication

| × | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| 2 | 2 | 4 | 6 | 8 | 10 | 12 | 14 | 16 | 18 |
| 3 | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 27 |
| 4 | 4 | 8 | 12 | 16 | 20 | 24 | 28 | 32 | 36 |
| 5 | 5 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 45 |
| 6 | 6 | 12 | 18 | 24 | 30 | 36 | 42 | 48 | 54 |
| 7 | 7 | 14 | 21 | 28 | 35 | 42 | 49 | 56 | 63 |
| 8 | 8 | 16 | 24 | 32 | 40 | 48 | 56 | 64 | 72 |
| 9 | 9 | 18 | 27 | 36 | 45 | 54 | 63 | 72 | 81 |

### Propriétés importantes

- **Commutativité** : 3 × 4 = 4 × 3 = 12
- **Élément neutre** : n × 1 = n (ex: 7 × 1 = 7)
- **Zéro** : n × 0 = 0 (ex: 8 × 0 = 0)

### Problème type

*Un marchand vend 6 boîtes de 8 oranges. Combien d'oranges au total ?*
→ 6 × 8 = **48 oranges**""",
        "exercises": [
            {
                "question": "Combien font 7 × 8 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "54"}, {"label": "B", "text": "56"}, {"label": "C", "text": "63"}],
                "correct": "B",
                "explanation": "7 × 8 = 56. Mémorise : 7 fois 8 font 56.",
                "points": 1
            },
            {
                "question": "Un poulailler a 9 rangées de 6 poules. Combien y a-t-il de poules au total ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "54"}, {"label": "B", "text": "45"}, {"label": "C", "text": "63"}],
                "correct": "A",
                "explanation": "9 × 6 = 54 poules.",
                "points": 2
            },
            {
                "question": "Que vaut 6 × 0 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "6"}, {"label": "B", "text": "1"}, {"label": "C", "text": "0"}],
                "correct": "C",
                "explanation": "Tout nombre multiplié par 0 donne 0. C'est la propriété du zéro.",
                "points": 1
            }
        ]
    },
    {
        "level": "CE2", "subject": "francais", "order": 1,
        "title": "Le passé composé",
        "summary": "Former et utiliser le passé composé avec avoir et être.",
        "duration_minutes": 25,
        "content": """## Le passé composé

Le passé composé exprime une action **terminée** dans le passé.

### Formation

Le passé composé = **auxiliaire** (avoir ou être) + **participe passé**

**Avec AVOIR :**
- *j'ai mangé, tu as joué, il a chanté*

**Avec ÊTRE :** (verbes de déplacement et pronominaux)
- *je suis allé(e), tu es arrivé(e), il est parti*

### Les participes passés courants

| Infinitif | Participe passé |
|-----------|----------------|
| manger | mangé |
| jouer | joué |
| finir | fini |
| prendre | pris |
| faire | fait |
| aller | allé |
| partir | parti |

### Accord avec ÊTRE

Quand on utilise être, le participe s'accorde avec le sujet :
- *Elle est arrivée* (féminin → -e)
- *Ils sont partis* (pluriel → -s)

### Exemples

- *Ce matin, Aminata **a mangé** du pain.*
- *Hier, nous **sommes allés** au marché.*""",
        "exercises": [
            {
                "question": "Mets au passé composé : 'Je mange du riz.'",
                "type": "qcm",
                "options": [{"label": "A", "text": "J'avais mangé du riz."}, {"label": "B", "text": "J'ai mangé du riz."}, {"label": "C", "text": "Je mangeais du riz."}],
                "correct": "B",
                "explanation": "Passé composé = avoir/être + participe passé. Manger → j'ai mangé.",
                "points": 1
            },
            {
                "question": "Quel auxiliaire prend le verbe 'aller' au passé composé ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "avoir"}, {"label": "B", "text": "être"}, {"label": "C", "text": "les deux"}],
                "correct": "B",
                "explanation": "'Aller' est un verbe de déplacement. Il prend l'auxiliaire 'être' : je suis allé(e).",
                "points": 1
            },
            {
                "question": "Choisis la bonne forme : 'Fatou et Aminata _____ (partir) tôt.'",
                "type": "qcm",
                "options": [{"label": "A", "text": "sont partis"}, {"label": "B", "text": "sont parties"}, {"label": "C", "text": "ont parti"}],
                "correct": "B",
                "explanation": "Fatou et Aminata sont féminins pluriel → sont parties (accord avec être).",
                "points": 2
            }
        ]
    },

    # ───────────────────────────────────────────────────────────
    # NIVEAU CM1
    # ───────────────────────────────────────────────────────────
    {
        "level": "CM1", "subject": "mathematiques", "order": 1,
        "title": "La division",
        "summary": "Effectuer des divisions euclidiennes et comprendre quotient et reste.",
        "duration_minutes": 35,
        "content": """## La division

### Qu'est-ce que la division ?

Diviser c'est **partager équitablement** une quantité.

**Exemple :** 24 ÷ 6 = 4

On dit : 24 divisé par 6 égale 4

### Vocabulaire

- **24** = dividende (ce qu'on divise)
- **6** = diviseur (par combien on divise)
- **4** = quotient (le résultat)
- **0** = reste (ce qui reste si la division n'est pas exacte)

### Division avec reste (division euclidienne)

**Exemple :** 29 ÷ 4

```
29 | 4
9  | 7  ← quotient
1  ← reste
```

Vérification : 4 × 7 + 1 = 28 + 1 = 29 ✓

On dit : **29 = 4 × 7 + 1**

### Technique posée

Pour diviser 528 par 4 :
- 5 ÷ 4 = 1, reste 1
- 12 ÷ 4 = 3, reste 0
- 8 ÷ 4 = 2, reste 0
- Résultat : **132**

### Problème type

*On répartit 96 élèves en groupes de 8. Combien de groupes ?*
→ 96 ÷ 8 = **12 groupes**""",
        "exercises": [
            {
                "question": "Combien font 72 ÷ 9 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "7"}, {"label": "B", "text": "8"}, {"label": "C", "text": "9"}],
                "correct": "B",
                "explanation": "72 ÷ 9 = 8. Vérifie : 9 × 8 = 72 ✓",
                "points": 1
            },
            {
                "question": "On distribue 85 cahiers à 7 élèves. Combien de cahiers chaque élève reçoit-il ? Quel est le reste ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "12 cahiers, reste 1"}, {"label": "B", "text": "12 cahiers, reste 2"}, {"label": "C", "text": "11 cahiers, reste 8"}],
                "correct": "A",
                "explanation": "85 ÷ 7 = 12 reste 1. Vérifie : 7 × 12 + 1 = 84 + 1 = 85 ✓",
                "points": 2
            },
            {
                "question": "Un bus transporte 48 personnes par voyage. Combien de voyages faut-il pour transporter 192 personnes ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "3"}, {"label": "B", "text": "4"}, {"label": "C", "text": "5"}],
                "correct": "B",
                "explanation": "192 ÷ 48 = 4 voyages.",
                "points": 2
            }
        ]
    },
    {
        "level": "CM1", "subject": "francais", "order": 1,
        "title": "Les compléments du verbe (COD et COI)",
        "summary": "Identifier et utiliser les compléments d'objet direct et indirect.",
        "duration_minutes": 30,
        "content": """## Les compléments du verbe

### Le Complément d'Objet Direct (COD)

Le **COD** est directement relié au verbe, **sans préposition**.

Pour le trouver : on pose la question **Qui ?** ou **Quoi ?** après le verbe.

**Exemple :** *Oumar mange une mangue.*
→ Oumar mange **quoi ?** → *une mangue* est le COD.

### Le Complément d'Objet Indirect (COI)

Le **COI** est relié au verbe par une **préposition** (à, de, pour...).

Pour le trouver : on pose la question **À qui ?**, **De qui ?**, **À quoi ?**

**Exemple :** *Aminata parle à sa mère.*
→ Elle parle **à qui ?** → *à sa mère* est le COI.

### Tableau récapitulatif

| Complément | Préposition | Question | Exemple |
|------------|-------------|----------|---------|
| COD | Aucune | Qui ? Quoi ? | *Il lit **un livre**.* |
| COI | à, de, pour... | À qui ? De qui ? | *Il parle **à son ami**.* |

### Comment ne pas confondre ?

- COD : verbe → directement le complément
- COI : verbe → **préposition** → complément""",
        "exercises": [
            {
                "question": "Dans 'Fatou regarde le tableau', quel est le COD ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Fatou"}, {"label": "B", "text": "regarde"}, {"label": "C", "text": "le tableau"}],
                "correct": "C",
                "explanation": "Fatou regarde quoi ? → le tableau. C'est le COD (sans préposition).",
                "points": 1
            },
            {
                "question": "Dans 'Il écrit à son père', quel est le COI ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Il"}, {"label": "B", "text": "à son père"}, {"label": "C", "text": "écrit"}],
                "correct": "B",
                "explanation": "Il écrit à qui ? → à son père. C'est le COI (avec la préposition 'à').",
                "points": 1
            },
            {
                "question": "Quelle phrase contient un COD ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Il pense à ses amis."}, {"label": "B", "text": "Il mange du pain."}, {"label": "C", "text": "Il parle de son voyage."}],
                "correct": "B",
                "explanation": "'Du pain' répond à 'mange quoi ?' sans préposition → c'est un COD.",
                "points": 2
            }
        ]
    },

    # ───────────────────────────────────────────────────────────
    # NIVEAU CM2
    # ───────────────────────────────────────────────────────────
    {
        "level": "CM2", "subject": "mathematiques", "order": 1,
        "title": "Les fractions",
        "summary": "Comprendre, comparer et calculer avec les fractions simples.",
        "duration_minutes": 35,
        "content": """## Les fractions

### Qu'est-ce qu'une fraction ?

Une fraction représente une **partie d'un tout**.

**Exemple :** Si on coupe une orange en 4 parts égales et qu'on en prend 3, on a pris **3/4** de l'orange.

```
3   ← numérateur (nombre de parts prises)
-
4   ← dénominateur (nombre de parts au total)
```

### Fractions égales à 1 et supérieures à 1

- **4/4 = 1** (le tout entier)
- **5/4 > 1** (plus d'un entier = fraction impropre)

### Comparer des fractions

**Même dénominateur :** comparer les numérateurs
→ 3/7 < 5/7 (car 3 < 5)

**Dénominateurs différents :** trouver le dénominateur commun
→ 1/2 et 1/3 → 3/6 et 2/6 → 3/6 > 2/6 donc 1/2 > 1/3

### Addition de fractions (même dénominateur)

**1/5 + 2/5 = 3/5** → On additionne les numérateurs, le dénominateur reste le même.

### Problème type

*Une famille a mangé 3/8 d'un pain le matin et 2/8 l'après-midi. Quelle fraction du pain ont-ils mangée ?*
→ 3/8 + 2/8 = **5/8** du pain""",
        "exercises": [
            {
                "question": "Dans la fraction 5/8, quel est le numérateur ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "8"}, {"label": "B", "text": "5"}, {"label": "C", "text": "3"}],
                "correct": "B",
                "explanation": "Dans 5/8, le numérateur est 5 (en haut). Le dénominateur est 8 (en bas).",
                "points": 1
            },
            {
                "question": "Quelle fraction est la plus grande : 3/7 ou 5/7 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "3/7"}, {"label": "B", "text": "5/7"}, {"label": "C", "text": "Elles sont égales"}],
                "correct": "B",
                "explanation": "Même dénominateur (7) : on compare les numérateurs. 5 > 3, donc 5/7 > 3/7.",
                "points": 1
            },
            {
                "question": "Calcule : 2/9 + 4/9 = ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "6/18"}, {"label": "B", "text": "6/9"}, {"label": "C", "text": "8/9"}],
                "correct": "B",
                "explanation": "Même dénominateur : 2/9 + 4/9 = (2+4)/9 = 6/9.",
                "points": 1
            }
        ]
    },
    {
        "level": "CM2", "subject": "mathematiques", "order": 2,
        "title": "Les pourcentages",
        "summary": "Comprendre et calculer des pourcentages dans des situations concrètes.",
        "duration_minutes": 30,
        "content": """## Les pourcentages

### Qu'est-ce qu'un pourcentage ?

Un **pourcentage** est une fraction dont le dénominateur est **100**.

**25% = 25/100 = 0,25**

### Calculer un pourcentage d'une quantité

**Formule :** Valeur = (Pourcentage × Total) ÷ 100

**Exemple :** 20% de 500 F CFA ?
→ (20 × 500) ÷ 100 = 10 000 ÷ 100 = **100 F CFA**

### Cas pratiques

**Réduction commerciale :**
*Un article coûte 2 000 F CFA avec 10% de réduction.*
→ Réduction = 10% × 2000 = 200 F
→ Prix final = 2000 - 200 = **1 800 F CFA**

**Score scolaire :**
*Aminata a eu 18/20 à un test.*
→ En pourcentage : (18 ÷ 20) × 100 = **90%**

### Pourcentages courants à retenir

| Pourcentage | Fraction | Valeur décimale |
|-------------|----------|----------------|
| 10% | 1/10 | 0,1 |
| 25% | 1/4 | 0,25 |
| 50% | 1/2 | 0,5 |
| 75% | 3/4 | 0,75 |
| 100% | 1 | 1 |""",
        "exercises": [
            {
                "question": "Combien vaut 10% de 300 ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "3"}, {"label": "B", "text": "30"}, {"label": "C", "text": "300"}],
                "correct": "B",
                "explanation": "10% = 1/10. 300 ÷ 10 = 30.",
                "points": 1
            },
            {
                "question": "Un commerçant vend un tissu 5 000 F avec 20% de réduction. Quel est le prix réduit ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "4 000 F"}, {"label": "B", "text": "4 500 F"}, {"label": "C", "text": "3 800 F"}],
                "correct": "A",
                "explanation": "Réduction = 20% × 5000 = 1000 F. Prix = 5000 - 1000 = 4000 F.",
                "points": 2
            },
            {
                "question": "Oumar a eu 15 bonnes réponses sur 20. Quel est son score en pourcentage ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "70%"}, {"label": "B", "text": "75%"}, {"label": "C", "text": "80%"}],
                "correct": "B",
                "explanation": "(15 ÷ 20) × 100 = 75%.",
                "points": 2
            }
        ]
    },

    # ───────────────────────────────────────────────────────────
    # SCIENCES — CE1 et CM1
    # ───────────────────────────────────────────────────────────
    {
        "level": "CE1", "subject": "sciences", "order": 1,
        "title": "Les êtres vivants",
        "summary": "Distinguer les êtres vivants des objets inanimés et comprendre leurs besoins.",
        "duration_minutes": 25,
        "content": """## Les êtres vivants

### Qu'est-ce qu'un être vivant ?

Un **être vivant** est un organisme qui :
- Se **nourrit** pour avoir de l'énergie
- **Respire** (absorbe de l'oxygène)
- **Se reproduit** (fabrique de nouveaux individus semblables à lui)
- **Grandit** et se développe
- **Meurt** à la fin de sa vie

### Les grandes familles d'êtres vivants

**Les animaux :** ils se déplacent et consomment d'autres êtres vivants.
Exemples : le lion, le poisson, l'oiseau, l'être humain

**Les végétaux :** ils fabriquent leur propre nourriture grâce au soleil.
Exemples : le baobab, le manguier, le riz

**Les champignons :** ni animaux, ni végétaux. Ils se nourrissent de matière organique.

### Ce qui N'EST PAS vivant

Une pierre, une voiture, l'eau, l'air, le feu → **ne sont pas** des êtres vivants car ils ne se nourrissent pas, ne respirent pas et ne se reproduisent pas.

### Les besoins des êtres vivants

| Besoin | Animaux | Végétaux |
|--------|---------|----------|
| Eau | ✓ | ✓ |
| Nourriture | ✓ | Lumière solaire |
| Air (O2/CO2) | ✓ | ✓ |
| Chaleur | ✓ | ✓ |""",
        "exercises": [
            {
                "question": "Lequel de ces éléments est un être vivant ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Une pierre"}, {"label": "B", "text": "Un manguier"}, {"label": "C", "text": "L'eau"}],
                "correct": "B",
                "explanation": "Le manguier est un être vivant : il se nourrit, respire, grandit et se reproduit.",
                "points": 1
            },
            {
                "question": "Quelle caractéristique partagent TOUS les êtres vivants ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Se déplacer"}, {"label": "B", "text": "Se reproduire"}, {"label": "C", "text": "Fabriquer leur nourriture"}],
                "correct": "B",
                "explanation": "Tous les êtres vivants se reproduisent. Seuls les animaux se déplacent et seuls les végétaux fabriquent leur nourriture.",
                "points": 1
            },
            {
                "question": "De quoi une plante a-t-elle besoin pour fabriquer sa nourriture ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "De la viande"}, {"label": "B", "text": "De la lumière solaire"}, {"label": "C", "text": "Du feu"}],
                "correct": "B",
                "explanation": "Les végétaux utilisent la lumière du soleil pour fabriquer leur nourriture (photosynthèse).",
                "points": 1
            }
        ]
    },

    # ───────────────────────────────────────────────────────────
    # HISTOIRE-GEO — CM1
    # ───────────────────────────────────────────────────────────
    {
        "level": "CM1", "subject": "histoire-geo", "order": 1,
        "title": "Le Sénégal : géographie et régions",
        "summary": "Connaître la géographie du Sénégal, ses régions et ses caractéristiques.",
        "duration_minutes": 30,
        "content": """## Le Sénégal : géographie et régions

### Situation géographique

Le **Sénégal** est un pays d'Afrique de l'Ouest.
- Il est baigné à l'**ouest** par l'océan Atlantique
- Il est traversé par plusieurs fleuves importants : **Sénégal**, **Gambie**, **Casamance**, **Sine**, **Saloum**
- Superficie : environ **196 722 km²**
- Capitale : **Dakar**

### Les 14 régions du Sénégal

Le Sénégal est divisé en **14 régions** :

Dakar · Thiès · Diourbel · Louga · Saint-Louis · Tambacounda · Kédougou · Kolda · Ziguinchor · Sédhiou · Fatick · Kaolack · Kaffrine · Matam

### Reliefs et zones climatiques

**Zones climatiques :**
- **Nord** : zone sahélienne (sèche, peu de pluies)
- **Centre** : zone soudanienne (pluies moyennes)
- **Sud** (Casamance) : zone soudano-guinéenne (très pluvieuse)

### Économie principale

- **Agriculture** : arachide, mil, riz, coton
- **Pêche** : importante sur la côte atlantique
- **Services** : tourisme, télécommunications
- **Mines** : or (Kédougou), phosphates, zircon""",
        "exercises": [
            {
                "question": "Quelle est la capitale du Sénégal ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Thiès"}, {"label": "B", "text": "Dakar"}, {"label": "C", "text": "Saint-Louis"}],
                "correct": "B",
                "explanation": "Dakar est la capitale et la plus grande ville du Sénégal.",
                "points": 1
            },
            {
                "question": "Combien de régions compte le Sénégal ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "11"}, {"label": "B", "text": "14"}, {"label": "C", "text": "16"}],
                "correct": "B",
                "explanation": "Le Sénégal est divisé en 14 régions depuis 2008.",
                "points": 1
            },
            {
                "question": "Quel fleuve porte le même nom que le pays ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "La Gambie"}, {"label": "B", "text": "La Casamance"}, {"label": "C", "text": "Le Sénégal"}],
                "correct": "C",
                "explanation": "Le fleuve Sénégal traverse le nord du pays et lui a donné son nom.",
                "points": 1
            }
        ]
    },

    # ───────────────────────────────────────────────────────────
    # ANGLAIS — CE1
    # ───────────────────────────────────────────────────────────
    {
        "level": "CE1", "subject": "anglais", "order": 1,
        "title": "Greetings and introductions",
        "summary": "Learn to greet people and introduce yourself in English.",
        "duration_minutes": 20,
        "content": """## Greetings and introductions

### How to say hello

- **Hello!** → Bonjour / Salut
- **Good morning!** → Bonjour (le matin)
- **Good afternoon!** → Bon après-midi
- **Good evening!** → Bonsoir
- **Goodbye!** → Au revoir
- **See you later!** → À plus tard

### Introducing yourself

To say your name:
> **My name is...** + your name
> *My name is Aminata.*

To say your age:
> **I am...** + age + **years old.**
> *I am 9 years old.*

To say where you live:
> **I live in...** + city/village
> *I live in Dakar.*

### Asking someone's name

- **What is your name?** → Comment tu t'appelles ?
- **How old are you?** → Quel âge as-tu ?
- **Where are you from?** → D'où viens-tu ?

### Practice dialogue

A: *Hello! What is your name?*
B: *My name is Oumar. What is your name?*
A: *My name is Fatou. How old are you?*
B: *I am 10 years old. And you?*
A: *I am 9 years old.*""",
        "exercises": [
            {
                "question": "How do you say 'Bonjour' in the morning in English?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Good evening"}, {"label": "B", "text": "Good morning"}, {"label": "C", "text": "Good afternoon"}],
                "correct": "B",
                "explanation": "'Good morning' means Bonjour le matin. 'Good evening' is for the evening.",
                "points": 1
            },
            {
                "question": "How do you say 'Je m'appelle Fatou' in English?",
                "type": "qcm",
                "options": [{"label": "A", "text": "I am Fatou"}, {"label": "B", "text": "My name is Fatou"}, {"label": "C", "text": "Her name is Fatou"}],
                "correct": "B",
                "explanation": "'My name is...' is used to introduce yourself in English.",
                "points": 1
            },
            {
                "question": "What does 'How old are you?' mean in French?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Comment tu t'appelles ?"}, {"label": "B", "text": "Où habites-tu ?"}, {"label": "C", "text": "Quel âge as-tu ?"}],
                "correct": "C",
                "explanation": "'How old are you?' asks about someone's age. The answer is 'I am X years old.'",
                "points": 1
            }
        ]
    },

    # ── CI — Éveil / Sciences ──
    {
        "level": "CI", "subject": "sciences", "order": 1,
        "title": "Mon corps",
        "summary": "Découvrir les grandes parties du corps humain.",
        "duration_minutes": 15,
        "content": """## Mon corps

Nous avons tous un corps avec des parties importantes.

### Les grandes parties du corps
- **La tête** : avec les yeux, le nez, la bouche et les oreilles
- **Le tronc** : la poitrine et le ventre
- **Les membres** : 2 bras et 2 jambes

### Les cinq sens
- 👀 Les **yeux** → pour voir
- 👂 Les **oreilles** → pour entendre
- 👃 Le **nez** → pour sentir
- 👅 La **bouche** → pour goûter
- ✋ Les **mains** → pour toucher

### Prendre soin de son corps
Se laver les mains avant de manger. Se brosser les dents matin et soir.""",
        "exercises": [
            {
                "question": "Avec quoi voit-on ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Les oreilles"}, {"label": "B", "text": "Les yeux"}, {"label": "C", "text": "Le nez"}],
                "correct": "B",
                "explanation": "Les yeux servent à voir. C'est l'un des cinq sens.",
                "points": 1
            },
            {
                "question": "Combien de jambes avons-nous ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "1"}, {"label": "B", "text": "4"}, {"label": "C", "text": "2"}],
                "correct": "C",
                "explanation": "Nous avons 2 jambes et 2 bras.",
                "points": 1
            },
            {
                "question": "Que faut-il faire avant de manger ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Se coiffer"}, {"label": "B", "text": "Se laver les mains"}, {"label": "C", "text": "Courir"}],
                "correct": "B",
                "explanation": "Se laver les mains avant de manger évite les maladies.",
                "points": 1
            }
        ]
    },

    # ── CP — Sciences ──
    {
        "level": "CP", "subject": "sciences", "order": 1,
        "title": "Les animaux autour de nous",
        "summary": "Classer les animaux et comprendre leur mode de vie.",
        "duration_minutes": 20,
        "content": """## Les animaux autour de nous

### Les animaux domestiques
Ce sont les animaux qui vivent avec nous : le chien, le chat, la poule, le mouton, la vache.

### Les animaux sauvages
Ils vivent dans la nature : le lion, l'éléphant, le singe, le serpent.

### Ce que mangent les animaux
- **Herbivores** : mangent des plantes (vache, chèvre, lapin)
- **Carnivores** : mangent de la viande (lion, chat)
- **Omnivores** : mangent de tout (poule, cochon)

### Les animaux utiles
Le bœuf tire la charrue. La vache donne du lait. La poule pond des œufs.""",
        "exercises": [
            {
                "question": "Lequel est un animal domestique ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Le lion"}, {"label": "B", "text": "La poule"}, {"label": "C", "text": "L'éléphant"}],
                "correct": "B",
                "explanation": "La poule est un animal domestique qui vit avec les humains.",
                "points": 1
            },
            {
                "question": "Un animal qui mange seulement des plantes est :",
                "type": "qcm",
                "options": [{"label": "A", "text": "Carnivore"}, {"label": "B", "text": "Omnivore"}, {"label": "C", "text": "Herbivore"}],
                "correct": "C",
                "explanation": "Les herbivores, comme la vache, mangent uniquement des plantes.",
                "points": 1
            },
            {
                "question": "Que donne la vache ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Des œufs"}, {"label": "B", "text": "Du miel"}, {"label": "C", "text": "Du lait"}],
                "correct": "C",
                "explanation": "La vache est élevée notamment pour le lait qu'elle produit.",
                "points": 1
            }
        ]
    },

    # ── CP — Anglais ──
    {
        "level": "CP", "subject": "anglais", "order": 1,
        "title": "Hello! Greetings",
        "summary": "Learn basic greetings and introductions in English.",
        "duration_minutes": 15,
        "content": """## Hello! Greetings

### How to say hello
- **Good morning** → bonjour (le matin)
- **Good afternoon** → bonsoir (l'après-midi)
- **Goodbye / Bye** → au revoir

### Introducing yourself
> *My name is Fatou. I am 7 years old.*

### Asking questions
- *What is your name?* → Comment tu t'appelles ?
- *How are you?* → Comment ça va ?
- *I am fine, thank you!* → Je vais bien, merci !

### Numbers 1–5
One (1), Two (2), Three (3), Four (4), Five (5)""",
        "exercises": [
            {
                "question": "How do you say 'bonjour' in the morning in English?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Goodbye"}, {"label": "B", "text": "Good morning"}, {"label": "C", "text": "Good night"}],
                "correct": "B",
                "explanation": "'Good morning' is used to greet someone in the morning.",
                "points": 1
            },
            {
                "question": "Complete: 'My ___ is Moussa.'",
                "type": "qcm",
                "options": [{"label": "A", "text": "name"}, {"label": "B", "text": "age"}, {"label": "C", "text": "school"}],
                "correct": "A",
                "explanation": "'My name is...' is used to introduce yourself.",
                "points": 1
            },
            {
                "question": "What number comes after 'three'?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Two"}, {"label": "B", "text": "Five"}, {"label": "C", "text": "Four"}],
                "correct": "C",
                "explanation": "The sequence is: one, two, three, four, five.",
                "points": 1
            }
        ]
    },

    # ── CE2 — Sciences ──
    {
        "level": "CE2", "subject": "sciences", "order": 1,
        "title": "L'eau et ses états",
        "summary": "Comprendre les trois états de l'eau : solide, liquide, gazeux.",
        "duration_minutes": 25,
        "content": """## L'eau et ses états

L'eau peut exister sous trois formes différentes.

### 1. L'état liquide
C'est la forme habituelle : l'eau des rivières, des pluies, du robinet.

### 2. L'état solide
Quand il fait très froid (0°C), l'eau gèle et devient de la **glace**.
- La neige et la grêle sont aussi de l'eau solide.

### 3. L'état gazeux
Quand on chauffe l'eau (100°C), elle bout et s'évapore en **vapeur d'eau**.

### Les changements d'état
| Changement | Nom |
|---|---|
| Liquide → Solide | Solidification (congélation) |
| Solide → Liquide | Fusion |
| Liquide → Gazeux | Évaporation |

### L'eau dans la nature
Le **cycle de l'eau** : l'eau s'évapore, monte dans l'atmosphère, forme des nuages, puis retombe en pluie.""",
        "exercises": [
            {
                "question": "À quelle température l'eau gèle-t-elle ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "100°C"}, {"label": "B", "text": "50°C"}, {"label": "C", "text": "0°C"}],
                "correct": "C",
                "explanation": "L'eau se solidifie (gèle) à 0°C pour former de la glace.",
                "points": 1
            },
            {
                "question": "Quand on chauffe l'eau à 100°C, elle devient :",
                "type": "qcm",
                "options": [{"label": "A", "text": "De la glace"}, {"label": "B", "text": "De la vapeur d'eau"}, {"label": "C", "text": "Du sel"}],
                "correct": "B",
                "explanation": "À 100°C, l'eau bout et s'évapore en vapeur d'eau (état gazeux).",
                "points": 1
            },
            {
                "question": "Comment appelle-t-on le passage de l'état liquide à l'état solide ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Évaporation"}, {"label": "B", "text": "Solidification"}, {"label": "C", "text": "Fusion"}],
                "correct": "B",
                "explanation": "La solidification (ou congélation) est le passage du liquide au solide.",
                "points": 1
            }
        ]
    },

    # ── CE2 — Anglais ──
    {
        "level": "CE2", "subject": "anglais", "order": 1,
        "title": "My family",
        "summary": "Learn vocabulary about family members in English.",
        "duration_minutes": 20,
        "content": """## My family

### Family members
- **father** → père
- **mother** → mère
- **brother** → frère
- **sister** → sœur
- **grandfather** → grand-père
- **grandmother** → grand-mère

### Talking about your family
> *I have one brother and two sisters.*
> *My mother's name is Adja.*

### Adjectives for family
- big family → grande famille
- small family → petite famille
- happy family → famille heureuse

### Possessive adjectives
- **my** → mon/ma
- **his/her** → son/sa""",
        "exercises": [
            {
                "question": "What is 'mère' in English?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Father"}, {"label": "B", "text": "Sister"}, {"label": "C", "text": "Mother"}],
                "correct": "C",
                "explanation": "'Mother' means 'mère' in French.",
                "points": 1
            },
            {
                "question": "How do you say 'frère' in English?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Sister"}, {"label": "B", "text": "Brother"}, {"label": "C", "text": "Uncle"}],
                "correct": "B",
                "explanation": "'Brother' is the translation of 'frère'.",
                "points": 1
            },
            {
                "question": "Complete: '___ name is Oumar.' (son prénom)",
                "type": "qcm",
                "options": [{"label": "A", "text": "My"}, {"label": "B", "text": "His"}, {"label": "C", "text": "Her"}],
                "correct": "B",
                "explanation": "'His' is used for a male person (son/sa pour un garçon).",
                "points": 1
            }
        ]
    },

    # ── CE2 — Histoire-Géographie ──
    {
        "level": "CE2", "subject": "histoire-geo", "order": 1,
        "title": "Le Sénégal — Notre pays",
        "summary": "Découvrir la géographie de base du Sénégal.",
        "duration_minutes": 25,
        "content": """## Le Sénégal — Notre pays

### Situation géographique
Le Sénégal est un pays d'**Afrique de l'Ouest**. Il est bordé par l'océan Atlantique à l'ouest.

### Les régions du Sénégal
Le Sénégal est divisé en **14 régions** :
Dakar, Thiès, Diourbel, Fatick, Kaolack, Kaffrine, Saint-Louis, Louga, Matam, Tambacounda, Kédougou, Kolda, Sédhiou, Ziguinchor

### La capitale
**Dakar** est la capitale et la plus grande ville du Sénégal.

### Les voisins du Sénégal
- Au nord : **Mauritanie**
- À l'est : **Mali**
- Au sud : **Guinée-Bissau** et **Guinée**
- À l'intérieur : **Gambie**

### Le fleuve Sénégal
Le fleuve Sénégal marque la frontière nord avec la Mauritanie.""",
        "exercises": [
            {
                "question": "Quelle est la capitale du Sénégal ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Saint-Louis"}, {"label": "B", "text": "Thiès"}, {"label": "C", "text": "Dakar"}],
                "correct": "C",
                "explanation": "Dakar est la capitale et la plus grande ville du Sénégal.",
                "points": 1
            },
            {
                "question": "En combien de régions le Sénégal est-il divisé ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "10"}, {"label": "B", "text": "14"}, {"label": "C", "text": "12"}],
                "correct": "B",
                "explanation": "Le Sénégal est divisé en 14 régions administratives.",
                "points": 1
            },
            {
                "question": "Quel pays est enclavé à l'intérieur du Sénégal ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Le Mali"}, {"label": "B", "text": "La Mauritanie"}, {"label": "C", "text": "La Gambie"}],
                "correct": "C",
                "explanation": "La Gambie est un petit pays presque entièrement entouré par le Sénégal.",
                "points": 1
            }
        ]
    },

    # ── CM1 — Sciences ──
    {
        "level": "CM1", "subject": "sciences", "order": 1,
        "title": "La chaîne alimentaire",
        "summary": "Comprendre les relations entre les êtres vivants dans un écosystème.",
        "duration_minutes": 30,
        "content": """## La chaîne alimentaire

### Définition
Une chaîne alimentaire montre qui mange qui dans la nature.

### Les maillons de la chaîne
1. **Producteurs** : les plantes (herbe, arbres) — ils produisent leur propre nourriture par photosynthèse
2. **Consommateurs primaires** : les herbivores (lapins, criquets, zèbres) qui mangent les plantes
3. **Consommateurs secondaires** : les carnivores (renard, lion) qui mangent les herbivores
4. **Décomposeurs** : les champignons et bactéries qui décomposent les restes

### Exemple de chaîne alimentaire
> Herbe → Criquet → Grenouille → Serpent → Aigle

### Le réseau trophique
En réalité, les chaînes se croisent et forment un **réseau alimentaire**.

### Importance de l'équilibre
Si un maillon disparaît, tout l'écosystème est perturbé. C'est pourquoi il faut protéger la biodiversité.""",
        "exercises": [
            {
                "question": "Qui sont les producteurs dans une chaîne alimentaire ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Les lions"}, {"label": "B", "text": "Les plantes"}, {"label": "C", "text": "Les lapins"}],
                "correct": "B",
                "explanation": "Les plantes sont les producteurs : elles fabriquent leur nourriture grâce au soleil.",
                "points": 1
            },
            {
                "question": "Dans la chaîne : Herbe → Criquet → Grenouille, le criquet est :",
                "type": "qcm",
                "options": [{"label": "A", "text": "Un producteur"}, {"label": "B", "text": "Un décomposeur"}, {"label": "C", "text": "Un consommateur primaire"}],
                "correct": "C",
                "explanation": "Le criquet mange l'herbe (une plante), il est donc consommateur primaire.",
                "points": 1
            },
            {
                "question": "Que font les décomposeurs ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Ils produisent de l'oxygène"}, {"label": "B", "text": "Ils décomposent les restes d'êtres vivants"}, {"label": "C", "text": "Ils chassent les herbivores"}],
                "correct": "B",
                "explanation": "Les décomposeurs (champignons, bactéries) décomposent la matière organique morte.",
                "points": 1
            }
        ]
    },

    # ── CM1 — Anglais ──
    {
        "level": "CM1", "subject": "anglais", "order": 1,
        "title": "My school and daily routine",
        "summary": "Describe your school life and daily activities in English.",
        "duration_minutes": 25,
        "content": """## My school and daily routine

### School vocabulary
- **classroom** → salle de classe
- **blackboard** → tableau
- **textbook** → manuel scolaire
- **teacher** → enseignant(e)
- **homework** → devoirs

### Daily routine
- I **wake up** at 6 o'clock.
- I **go to school** at 7:30.
- I **study** from 8am to 1pm.
- I **play** with my friends at break time.
- I **do my homework** in the afternoon.

### Telling the time
- It is **8 o'clock**. (Il est 8 heures.)
- It is **half past 10**. (Il est 10h30.)
- It is **quarter to 12**. (Il est 11h45.)

### Asking questions about routine
- *What time do you wake up?*
- *How do you go to school?* → I walk / I take the bus.""",
        "exercises": [
            {
                "question": "What is 'devoirs' in English?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Homework"}, {"label": "B", "text": "Classroom"}, {"label": "C", "text": "Teacher"}],
                "correct": "A",
                "explanation": "'Homework' means 'devoirs' — the work you do at home after school.",
                "points": 1
            },
            {
                "question": "What does 'I wake up' mean?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Je dors"}, {"label": "B", "text": "Je me réveille"}, {"label": "C", "text": "Je mange"}],
                "correct": "B",
                "explanation": "'To wake up' means 'se réveiller'.",
                "points": 1
            },
            {
                "question": "How do you say 'Il est 10h30' in English?",
                "type": "qcm",
                "options": [{"label": "A", "text": "It is 10 o'clock"}, {"label": "B", "text": "It is half past 10"}, {"label": "C", "text": "It is quarter to 10"}],
                "correct": "B",
                "explanation": "'Half past 10' means 10h30 — 'half' indicates 30 minutes past the hour.",
                "points": 1
            }
        ]
    },

    # ── CM2 — Français ──
    {
        "level": "CM2", "subject": "francais", "order": 1,
        "title": "La rédaction — écrire un texte clair",
        "summary": "Apprendre à rédiger un texte organisé avec introduction, développement et conclusion.",
        "duration_minutes": 35,
        "content": """## La rédaction

### Qu'est-ce qu'une rédaction ?
Une rédaction est un texte écrit qui développe une idée ou raconte quelque chose.

### La structure d'un texte
Tout bon texte a **3 parties** :
1. **Introduction** : on présente le sujet
2. **Développement** : on développe les idées principales
3. **Conclusion** : on résume et on termine

### Les connecteurs logiques
Pour lier les idées, on utilise :
- **D'abord / Premièrement** → pour commencer
- **Ensuite / Puis** → pour continuer
- **Enfin / Pour conclure** → pour terminer
- **Cependant / Mais** → pour opposer

### Les types de textes
- **Narratif** : raconter une histoire
- **Descriptif** : décrire un lieu ou une personne
- **Argumentatif** : convaincre avec des arguments

### Conseils pour bien rédiger
✅ Fais des phrases courtes et claires.
✅ Relis toujours ton texte.
✅ Vérifie l'accord des noms et des verbes.""",
        "exercises": [
            {
                "question": "Combien de parties doit avoir un texte bien organisé ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "2"}, {"label": "B", "text": "3"}, {"label": "C", "text": "4"}],
                "correct": "B",
                "explanation": "Un texte est structuré en 3 parties : introduction, développement, conclusion.",
                "points": 1
            },
            {
                "question": "Quel connecteur utilise-t-on pour terminer un texte ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "D'abord"}, {"label": "B", "text": "Cependant"}, {"label": "C", "text": "Pour conclure"}],
                "correct": "C",
                "explanation": "'Pour conclure' est utilisé en conclusion pour terminer un texte.",
                "points": 1
            },
            {
                "question": "Un texte qui raconte une histoire est de type :",
                "type": "qcm",
                "options": [{"label": "A", "text": "Argumentatif"}, {"label": "B", "text": "Narratif"}, {"label": "C", "text": "Descriptif"}],
                "correct": "B",
                "explanation": "Un texte narratif raconte une histoire ou une suite d'événements.",
                "points": 1
            }
        ]
    },

    # ── CM2 — Sciences ──
    {
        "level": "CM2", "subject": "sciences", "order": 1,
        "title": "Le système solaire",
        "summary": "Connaître les planètes du système solaire et leur place par rapport au Soleil.",
        "duration_minutes": 30,
        "content": """## Le système solaire

### Le Soleil
Le Soleil est une **étoile** au centre de notre système solaire. C'est lui qui donne la lumière et la chaleur à la Terre.

### Les 8 planètes (par ordre de distance du Soleil)
1. **Mercure** — la plus proche, très chaude le jour, très froide la nuit
2. **Vénus** — la plus brillante vue de la Terre
3. **Terre** — notre planète, la seule avec de la vie
4. **Mars** — la planète rouge
5. **Jupiter** — la plus grande planète
6. **Saturne** — avec ses célèbres anneaux
7. **Uranus** — tourne sur le côté
8. **Neptune** — la plus éloignée

### La Lune
La Lune est le satellite naturel de la Terre. Elle fait le tour de la Terre en 28 jours.

### Moyen mnémotechnique
**M-V-T-M-J-S-U-N** : *Ma Vieille Tante Marie Joue Sur Une Natte*""",
        "exercises": [
            {
                "question": "Combien y a-t-il de planètes dans notre système solaire ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "9"}, {"label": "B", "text": "7"}, {"label": "C", "text": "8"}],
                "correct": "C",
                "explanation": "Il y a 8 planètes : Mercure, Vénus, Terre, Mars, Jupiter, Saturne, Uranus, Neptune.",
                "points": 1
            },
            {
                "question": "Quelle planète est la plus grande du système solaire ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Saturne"}, {"label": "B", "text": "Jupiter"}, {"label": "C", "text": "Neptune"}],
                "correct": "B",
                "explanation": "Jupiter est la plus grande planète du système solaire.",
                "points": 1
            },
            {
                "question": "En combien de jours la Lune fait-elle le tour de la Terre ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "365 jours"}, {"label": "B", "text": "28 jours"}, {"label": "C", "text": "7 jours"}],
                "correct": "B",
                "explanation": "La Lune orbite autour de la Terre en environ 28 jours (1 mois lunaire).",
                "points": 1
            }
        ]
    },

    # ── CM2 — Anglais ──
    {
        "level": "CM2", "subject": "anglais", "order": 1,
        "title": "The environment",
        "summary": "Learn vocabulary about the environment and how to protect it.",
        "duration_minutes": 30,
        "content": """## The environment

### Environmental vocabulary
- **environment** → environnement
- **pollution** → pollution
- **recycling** → recyclage
- **deforestation** → déforestation
- **climate change** → changement climatique

### Problems facing our environment
- Plastic **pollutes** rivers and oceans.
- Cutting trees causes **deforestation**.
- Cars and factories release gases that cause **global warming**.

### What can WE do?
- **Recycle** paper, plastic and glass.
- **Plant** trees in our neighbourhood.
- **Save** water — do not leave the tap running.
- **Use** public transport or walk instead of using cars.

### Speaking about the environment
- *We must protect our environment.*
- *I recycle at home every week.*
- *Deforestation is a serious problem in Senegal.*""",
        "exercises": [
            {
                "question": "What does 'recyclage' mean in English?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Pollution"}, {"label": "B", "text": "Recycling"}, {"label": "C", "text": "Deforestation"}],
                "correct": "B",
                "explanation": "'Recycling' is the process of converting waste into reusable material.",
                "points": 1
            },
            {
                "question": "Which action helps protect the environment?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Cutting trees"}, {"label": "B", "text": "Throwing plastic in rivers"}, {"label": "C", "text": "Planting trees"}],
                "correct": "C",
                "explanation": "Planting trees helps fight deforestation and reduces CO₂ in the atmosphere.",
                "points": 1
            },
            {
                "question": "What causes global warming?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Planting trees"}, {"label": "B", "text": "Gases from cars and factories"}, {"label": "C", "text": "Drinking water"}],
                "correct": "B",
                "explanation": "Gases (CO₂, methane) from vehicles and factories trap heat and cause global warming.",
                "points": 1
            }
        ]
    },

    # ── CM2 — Histoire-Géographie ──
    {
        "level": "CM2", "subject": "histoire-geo", "order": 1,
        "title": "L'Afrique de l'Ouest — Géographie",
        "summary": "Découvrir les pays, capitales et caractéristiques de l'Afrique de l'Ouest.",
        "duration_minutes": 30,
        "content": """## L'Afrique de l'Ouest

### Présentation
L'Afrique de l'Ouest regroupe **15 pays** membres de la CEDEAO (Communauté Économique des États de l'Afrique de l'Ouest).

### Quelques pays et leurs capitales
| Pays | Capitale |
|---|---|
| Sénégal | Dakar |
| Mali | Bamako |
| Côte d'Ivoire | Yamoussoukro |
| Ghana | Accra |
| Nigeria | Abuja |
| Guinée | Conakry |
| Burkina Faso | Ouagadougou |

### Les grands fleuves
- **Le Niger** : traverse le Mali, le Niger et le Nigeria
- **Le Sénégal** : frontière entre le Sénégal et la Mauritanie
- **La Gambie** : traverse la Gambie

### Caractéristiques physiques
- **Le Sahel** : zone semi-aride au nord
- **Les savanes** : vastes prairies au centre
- **La forêt tropicale** : au sud (Côte d'Ivoire, Ghana)

### L'histoire de la région
Grands empires médiévaux : **Empire du Ghana**, **Empire du Mali** (avec Mansa Moussa), **Empire Songhay**.""",
        "exercises": [
            {
                "question": "Quelle est la capitale du Mali ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "Accra"}, {"label": "B", "text": "Bamako"}, {"label": "C", "text": "Conakry"}],
                "correct": "B",
                "explanation": "Bamako est la capitale du Mali, grand pays enclavé d'Afrique de l'Ouest.",
                "points": 1
            },
            {
                "question": "Combien de pays forment la CEDEAO ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "15"}, {"label": "B", "text": "10"}, {"label": "C", "text": "20"}],
                "correct": "A",
                "explanation": "La CEDEAO regroupe 15 États membres d'Afrique de l'Ouest.",
                "points": 1
            },
            {
                "question": "Quel grand empire médiéval a existé en Afrique de l'Ouest ?",
                "type": "qcm",
                "options": [{"label": "A", "text": "L'Empire romain"}, {"label": "B", "text": "L'Empire du Mali"}, {"label": "C", "text": "L'Empire ottoman"}],
                "correct": "B",
                "explanation": "L'Empire du Mali fut l'un des plus grands empires médiévaux d'Afrique de l'Ouest.",
                "points": 1
            }
        ]
    },
]


# ═══════════════════════════════════════════════════════════════
# FONCTION DE PEUPLEMENT
# ═══════════════════════════════════════════════════════════════

async def seed_lessons():
    """Insère toutes les leçons et exercices dans la base de données."""
    await create_tables()

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select, func

        # Vérifier si des leçons existent déjà
        count_result = await db.execute(select(func.count(Lesson.id)))
        existing = count_result.scalar() or 0

        if existing > 0:
            print(f"⚠️  {existing} leçon(s) déjà présente(s) en base. Suppression et réimport...")
            from sqlalchemy import delete
            await db.execute(delete(Exercise))
            await db.execute(delete(Lesson))
            await db.commit()

        print("📚 Insertion des leçons et exercices...")
        lesson_count = 0
        exercise_count = 0

        # Regrouper les leçons par niveau+matière pour gérer les prérequis
        lesson_objects = {}  # (level, subject, order) -> Lesson

        for data in LESSONS_DATA:
            lesson = Lesson(
                title=data["title"],
                subject=data["subject"],
                level=data["level"],
                order_in_subject=data["order"],
                content=data["content"],
                summary=data["summary"],
                duration_minutes=data.get("duration_minutes", 20),
                is_active=True,
            )

            # Prérequis : la leçon précédente dans la même matière
            prev_key = (data["level"], data["subject"], data["order"] - 1)
            if prev_key in lesson_objects:
                lesson.prerequisite_lesson_id = lesson_objects[prev_key].id

            db.add(lesson)
            await db.flush()  # Pour obtenir l'id
            lesson_objects[(data["level"], data["subject"], data["order"])] = lesson
            lesson_count += 1

            # Ajouter les exercices
            for i, ex_data in enumerate(data.get("exercises", []), 1):
                exercise = Exercise(
                    lesson_id=lesson.id,
                    question=ex_data["question"],
                    exercise_type=ex_data.get("type", "qcm"),
                    correct_answer=ex_data["correct"],
                    explanation=ex_data.get("explanation", ""),
                    points=ex_data.get("points", 1),
                    order_in_lesson=i,
                    is_active=True,
                )
                exercise.set_options(ex_data.get("options", []))
                db.add(exercise)
                exercise_count += 1

        await db.commit()
        print(f"✅ {lesson_count} leçons insérées")
        print(f"✅ {exercise_count} exercices insérés")
        print("\n📊 Récapitulatif :")

        # Afficher le bilan
        for level in ["CI", "CP", "CE1", "CE2", "CM1", "CM2"]:
            level_lessons = [d for d in LESSONS_DATA if d["level"] == level]
            if level_lessons:
                subjects = list(set(d["subject"] for d in level_lessons))
                print(f"  {level}: {len(level_lessons)} leçon(s) — Matières: {', '.join(subjects)}")


if __name__ == "__main__":
    asyncio.run(seed_lessons())
