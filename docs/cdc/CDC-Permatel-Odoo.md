# Cahier des Charges — Intégration PERMATEL / Odoo

**Version** : 1.0
**Date** : 27 juillet 2026
**Statut** : En cours de rédaction — validation progressive
**Plan d'implémentation associé** : [`ODOO_INTEGRATION_PLAN.md`](../../ODOO_INTEGRATION_PLAN.md)

---

## 1. Contexte et objectifs

PERMATEL est une SaaS multi-tenant de gestion opérationnelle pour agents de sécurité (demandes, clients/sites/contacts, agents, email, sessions/audit, reporting), sur stack Flask/SQLAlchemy/PostgreSQL et Vue 3/Vuetify/Pinia.

L'objectif du projet est d'intégrer **Odoo 18 Community** comme service ERP additionnel pour couvrir les besoins de gestion commerciale (CRM/Vente), comptable (Facturation) et RH (Planification), tout en garantissant que **PERMATEL reste pleinement opérationnel en mode dégradé** si Odoo est indisponible.

### Principes directeurs

- Odoo est un **service additionnel**, jamais une dépendance bloquante.
- PERMATEL maintient une **copie locale** de toutes les données pilotées par Odoo.
- L'interface Odoo est **masquée en production** : toute action métier passe par les vues PERMATEL. Un accès direct à Odoo n'est toléré qu'en cas d'incident/dépannage.
- En cas de conflit de données, **Odoo fait autorité** (source de vérité), sauf action corrective manuelle documentée.

---

## 2. Périmètre fonctionnel

### 2.1 Modules Odoo concernés

| Module Odoo | Usage |
|---|---|
| CRM / Ventes | Gestion des partenaires (clients, prestataires), devis, commandes |
| Comptabilité / Facturation | Facturation client, suivi des règlements |
| Planning (RH) | Élaboration et gestion du planning des agents de sécurité |

### 2.2 Flux fonctionnels

| # | Flux | Sens | Déclencheur | Mode |
|---|---|---|---|---|
| F1 | Partenaires (clients/prestataires/agents) | Bidirectionnel | Création/modification dans PERMATEL ou Odoo | Sync périodique + écriture événementielle |
| F2 | Commande PERMATEL → Devis Odoo | PERMATEL → Odoo | Création d'une commande dans PERMATEL | Écriture événementielle (API) |
| F3 | Vacation terminée → Feuille de temps | PERMATEL → Odoo | Clôture d'une vacation | Écriture événementielle (API) |
| F4 | Devis/Facture mis à jour | Odoo → PERMATEL | Modification côté Odoo (comptabilité) | Sync périodique |
| F5 | Planning des agents | Odoo → PERMATEL (lecture) / PERMATEL → Odoo (action) | Élaboration planning dans Odoo ; actions d'affectation depuis PERMATEL | Sync périodique + écriture événementielle |

### 2.3 Architecture de résilience

- Toutes les données issues d'Odoo (F1, F4, F5) sont **répliquées localement** dans la base PostgreSQL de PERMATEL.
- Les écritures vers Odoo (F2, F3, actions F5) sont envoyées de façon synchrone ; en cas d'échec, la tâche est placée en **file de retry** jusqu'à rétablissement du service Odoo.
- PERMATEL continue de fonctionner avec les dernières données en cache en cas d'indisponibilité d'Odoo ; un indicateur de fraîcheur (`last_synced_at`) est visible pour l'utilisateur.

---

## 3. Architecture technique

### 3.1 Stack et intégration

| Composant | Choix |
|---|---|
| Version Odoo | 18 Community |
| Hébergement Odoo | Conteneurisé (Docker), sur le même serveur que PERMATEL |
| Protocole d'intégration | JSON-RPC / XML-RPC (API externe Odoo) |
| Mécanisme d'orchestration | **Voir décision d'architecture dans `ODOO_INTEGRATION_PLAN.md` §2.1** — le CDC initial proposait Celery + Redis ; retenu à la place : hybride synchrone best-effort + table de retry + cron, cohérent avec le reste de la stack PERMATEL (aucun worker Celery ailleurs dans le projet). |
| Fréquence de synchronisation périodique | Valeur par défaut **15 minutes**, configurable par déploiement/tenant |

### 3.2 Comparatif API directe vs Middleware

| Critère | Appel API direct | Middleware (retenu) |
|---|---|---|
| Résilience aux pannes Odoo | Faible | Forte (retry automatique) |
| Performance perçue utilisateur | Risque de latence bloquante | Traitement asynchrone |
| Traçabilité | Limitée | Native (statut de tâche, historique) |
| Cas d'usage | Lectures ponctuelles simples | Flux critiques, écritures, synchronisation en masse |

> Voir `ODOO_INTEGRATION_PLAN.md` §2.1 pour le choix retenu entre Celery+Redis, cron+table de queue, et l'option hybride finalement adoptée.

### 3.3 Multi-tenance côté Odoo

**Modèle retenu : multi-database Odoo**

- Un seul serveur Odoo, **une base PostgreSQL Odoo dédiée par tenant PERMATEL**, routée via `dbfilter`.
- Chaque tenant PERMATEL stocke en configuration (chiffrée, sur le modèle SMTP/IMAP existant) : nom de la base Odoo, identifiants API, clé.
- `list_db = False` côté Odoo pour empêcher l'énumération des bases depuis l'extérieur.
- Rôles PostgreSQL distincts par base tenant.

### 3.4 Modèle de données PERMATEL (nouvelles tables)

| Table | Rôle |
|---|---|
| `odoo_config` | Configuration de connexion Odoo par tenant (base, identifiants chiffrés) |
| `odoo_partners` | Copie locale des partenaires synchronisés (`odoo_id`, `sync_status`, `last_synced_at`) |
| `odoo_devis` / `odoo_factures` | Copie locale des devis/factures |
| `odoo_planning_slots` | Copie locale des créneaux de planning |
| `odoo_sync_queue` | File de tâches d'écriture en attente/échec (nombre de tentatives, backoff, statut) |

Toutes ces tables respectent le modèle d'isolation multi-tenant existant de PERMATEL (`tenant_id` + FK composites).

### 3.5 Gestion des conflits

- Odoo est la source de vérité pour toute donnée qu'il pilote (partenaires, devis/factures, planning).
- Aucune modification directe dans l'interface Odoo en production (masquée) ; les écarts éventuels ne peuvent survenir qu'en cas d'intervention manuelle exceptionnelle, documentée et tracée.

### 3.6 Points de vigilance

- **Dépréciation XML-RPC/JSON-RPC** : Odoo a annoncé le remplacement de ces API par JSON-2 à partir d'Odoo 19/20. Le choix d'Odoo 18 limite ce risque à court terme mais une veille est nécessaire.
- **Dimensionnement serveur** : ajout d'Odoo + PostgreSQL dédié (+ Redis déjà présent dans la stack) sur le serveur existant → validation de capacité à prévoir.
- **Isolation base de données** : une base PostgreSQL Odoo distincte de celle de PERMATEL, même hébergement.

---

## 4. Hors périmètre (MVP)

- Personnalisation avancée des modules Odoo (développement de modules Odoo custom) → à évaluer en phase ultérieure.
- Interface Odoo visible aux utilisateurs finaux (masquée par défaut).
- Facturation multi-devises / multi-fiscalité avancée (non mentionné dans le périmètre initial).

---

## 5. Phasage

Voir le détail tâche-par-tâche dans `ODOO_INTEGRATION_PLAN.md` §4 et `docs/suivi_taches_permatel.xlsx` (Phases 6-10).

| Phase | Contenu |
|---|---|
| Phase 6 | Fondations (flag tenant, `OdooConfig`, `odoo_sync_queue`, route settings, client `xmlrpc`, commande de dispatch) |
| Phase 7 | Infrastructure Odoo + synchronisation partenaires (F1) |
| Phase 8 | Commande → Devis (F2) + Devis/Facture retour (F4) |
| Phase 9 | Vacation → Feuille de temps (F3) |
| Phase 10 | Planning agents (F5) — lecture + actions d'affectation |

---

## 6. Prochaines étapes

- ✅ Validation de ce cahier des charges macro par le porteur de projet.
- ✅ Décisions d'architecture actées (`ODOO_INTEGRATION_PLAN.md`).
- Détail des exigences fonctionnelles module par module (format EF-XXX-NN).
- Détail des exigences non fonctionnelles (sécurité, performance, disponibilité).
- Démarrage effectif de la Phase 6, sur confirmation explicite.
