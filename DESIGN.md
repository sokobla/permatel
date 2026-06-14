# DESIGN

## Vue d'ensemble

PERMATEL Operational Suite repose sur un design system de back-office premium, pensé pour les centres de supervision, la sécurité opérationnelle et la supervision VoIP. L'esthétique générale privilégie la lisibilité, la densité utile, la précision visuelle et une sensation d'autorité fonctionnelle plutôt qu'un rendu marketing ou décoratif.

Le système visuel s'inscrit dans une logique de console opérationnelle moderne baptisée **The Digital Architect**. L'interface doit donner l'impression d'un outil de production robuste, technique, structuré et immédiatement exploitable par des opérateurs métier.

## Principes fondateurs

### Operational Authority

L'interface doit ressembler à un outil métier et non à un template générique. Le design favorise la rigueur structurelle, la hiérarchie nette et la sobriété visuelle.

### Cognitive Efficiency

L'information doit être organisée en couches lisibles, en privilégiant les contrastes de surface, les niveaux tonals et les alignements précis plutôt que les ombres lourdes ou les cadres décoratifs.

### Data Integrity

Les données techniques importantes, comme les identifiants, métriques, extensions, timestamps ou codes d'erreur, doivent utiliser une typographie monospace afin de garantir un alignement visuel parfait et une lecture rapide dans des interfaces denses.

## Palette

### Couleurs principales

| Rôle | Couleur | Usage |
|---|---|---|
| Primary Navy | `#000B23` / `#15223A` | Header, zones d'autorité, profondeur visuelle |
| Action Teal | `#00A8A8` | États actifs, actions principales, mise en avant fonctionnelle |
| Alert Red | `#E74C3C` | Erreurs critiques, actions destructives, statuts négatifs |
| Surface Light Gray | `#F2F2F2` | Fond principal de l'application |
| Surface White | `#FFFFFF` | Cartes, tableaux, panneaux et champs |

### Règles d'usage

- Le contraste noir / blanc / cyan structure l'expérience.
- Le teal est réservé aux actions et états actifs, jamais utilisé comme simple décoration.
- Le rouge doit rester rare et réservé aux signaux d'alerte ou de danger.
- Les surfaces claires servent de base neutre à l'ensemble de l'interface.

## Typographie

### Familles de police

- **Fira Sans** : police principale pour les titres, libellés, navigation, textes d'interface et contenus généraux.
- **Fira Code** : police monospace pour identifiants, métriques, extensions, timestamps, erreurs techniques et toute donnée nécessitant un alignement exact.

### Hiérarchie typographique

- Les titres sont forts, compacts, lisibles et orientés fonction.
- Les libellés de navigation et de contrôle peuvent être en uppercase pour renforcer le caractère technique.
- Les sous-textes utilisent un gris atténué et une taille réduite.
- Les données critiques utilisent la monospace avec un contraste élevé.

## Layout et grille

- Système basé sur une grille **8pt**.
- Densité compacte mais lisible.
- Espacements réguliers, sans luxe inutile.
- Rayons de bord limités à **4px / 8px** lorsque nécessaire.
- Préférence pour les surfaces plates et les séparations discrètes.

## Navigation Drawer

### Structure

- Colonne latérale gauche fixe sur toute la hauteur.
- Fond blanc cassé / gris très clair uniforme.
- Pas de shadow forte, pas d'élévation marquée.

### Bloc profil

- Badge compact affichant le nom utilisateur, par exemple `@adm_admin`.
- Identifiant utilisateur au format `@username`.
- Affichage du nom et prénom de l'utilisateur.
- Sous-texte correspondant au rôle de l'utilisateur, par exemple `ADMINISTRATEUR`.
- Hiérarchie typographique : technique, visible, secondaire.

### Menu vertical

- Items de navigation compacts.
- Espacement vertical régulier.
- Icônes linéaires fines monochromes gris/noir.
- Libellés uppercase, alignés à droite des icônes.
- Police condensée et nette.

### Item actif

- Fond légèrement plus blanc que le reste du drawer.
- Indicateur vertical fin cyan/turquoise sur le bord gauche.
- Contraste lisible mais discret.
- Pas de rondeur excessive.


### Style global

- Design plat, administratif, technique.
- Très peu d'arrondis.
- Alignement horizontal rigoureux entre icône et texte.
- Densité compacte mais lisible.
- Esthétique de console de supervision premium.

## Barre supérieure

### Structure

- Barre horizontale fixe sur toute la largeur.
- Fond noir profond uniforme.
- Hauteur compacte, sans effet massif.

### Zone gauche

- Logo texte `PERMATEL OPS` en blanc, gras, très lisible.
- Alignement vertical centré.

### Navigation principale

- Navigation horizontale directement intégrée à la barre.
- Couleur par défaut gris clair ou blanc atténué.
- Onglet actif mis en avant en teal/cyan avec soulignement visible.

### Zone droite

- Champ de recherche compact intégré.
- Fond bleu nuit / noir bleuté légèrement distinct du header.
- Libellé ou placeholder `GLOBAL_SEARCH` discret.
- Icône loupe à gauche.

### Icônes d'action

- Série d'icônes blanches minimalistes à droite du champ de recherche.
- Icônes fines, monochromes, sans fond décoratif fort.
- Espacement horizontal propre et régulier.

### Avatar utilisateur

- Petit bloc avatar en extrémité droite.
- Format carré ou presque carré.
- Sert de terminaison visuelle à la barre.

### Style global

- Design très plat, premium, technique.
- Contraste fort noir / blanc / cyan.
- Très peu d'ombres et d'effets décoratifs.
- Alignements rigoureux et densité compacte.
- Ambiance de console d'administration ou de supervision.

## Modules produit

### Command Center (Security Ops)

**Objectif** : supervision temps réel des menaces et de l'état réseau.

**Éléments attendus** :
- flux de logs en direct,
- graphiques d'analyse de menaces,
- compteurs de nœuds actifs,
- alertes incidents critiques.

**Micro-copy** : terminologie de sécurité professionnelle, par exemple Main courante, Escalade, Prise de poste.

### VoIP Supervision Dashboard

**Objectif** : supervision opérationnelle de la performance du centre d'appels.

**Éléments attendus** :
- graphes temps réel de volume d'appels,
- suivi d'état des agents,
- suivi SLA,
- logs d'erreurs techniques au format `ERR-XXX`.

### User & Access Management

**Objectif** : administration rigoureuse des utilisateurs et des permissions.

**Éléments attendus** :
- tableaux denses et triables,
- side-drawers pour création / édition,
- modes distincts de gestion de mot de passe.

## Règles de composants

### Boutons

- Formes sobres et fonctionnelles.
- Accent teal pour les actions principales.
- Rouge réservé aux actions destructives.
- Densité compacte.
- Peu d'arrondis.

### Champs et formulaires

- Champs compacts.
- Surface blanche avec séparation discrète.
- Labels nets et lisibles.
- Alignement rigoureux dans les formulaires denses.

### Tableaux

- Haute densité d'information.
- Lecture rapide favorisée par la hiérarchie visuelle et l'usage de la monospace pour les données techniques.
- États et badges discrets mais clairs.

## Ton produit

Le ton général doit rester professionnel, rigoureux, technique et crédible. L'interface doit inspirer le contrôle, la fiabilité et la rapidité de lecture. Chaque composant doit sembler pensé pour une exploitation quotidienne en contexte métier critique.

## Roadmap

- Finaliser l'intégration de la Security Main Courante avec le Command Center.
- Étendre le module VoIP avec des vues de détail pour les SIP Traces.
- Consolider les variantes Material 3 dans un design system secondaire unifié pour les applications compagnons mobile et tablette.
