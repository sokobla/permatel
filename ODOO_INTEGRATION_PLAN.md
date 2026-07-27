# PERMATEL × Odoo — Plan d'intégration (add-on activable par tenant)

**Statut** : Planification validée — implémentation non démarrée.
**Date** : 27 juillet 2026
**Source** : `CDC-Permatel-Odoo.md` (v1.0, 27 juillet 2026)
**Suivi des tâches** : `docs/suivi_taches_permatel.xlsx` (Phases 6 à 10)

---

## 1. Analyse du besoin

Le CDC décrit l'intégration d'Odoo 18 Community comme un service ERP additionnel
(CRM/Vente, Comptabilité/Facturation, Planning RH), jamais bloquant, avec
réplication locale des données côté PERMATEL et file de retry pour les écritures.

En le regardant à travers le code existant, cette intégration **n'est pas un
concept nouveau pour PERMATEL** — c'est l'extension de patterns déjà en place :

- **Add-on activable par tenant** : existe déjà via `Tenant.channel_telephonie
  /email/chat` (`backend/app/models/tenant.py:25-27`) + la dérivation centralisée
  `tenant_features()` (`backend/app/services/tenant_features.py`), consommée
  telle quelle par le frontend sans recalcul (`GET /api/tenant/features`).
- **Config externe chiffrée par tenant** : existe déjà via `SmtpSetting`/IMAP
  (`backend/app/models/setting.py`, `backend/app/routes/settings.py`), chiffrement
  Fernet (`backend/app/utils/crypto.py`), endpoint de test de connexion qui
  renvoie `200 {"ok": bool}` même en échec, écriture réservée à
  `@tenant_admin_required`.
- **Traitement asynchrone + retry** : existe déjà, mais **pas via Celery** — tout
  le travail différé de PERMATEL (`sessions-sweep`, `sla-sweep`,
  `notifications-dispatch`, `mail-fetch`) est une commande Flask CLI + cron
  système documentée dans le README, pas un worker dédié.

Le seul point de désaccord réel avec le CDC est l'orchestration (§3.1/§3.6 du
CDC prescrivent Celery + Redis) — tranché au §2 ci-dessous.

---

## 2. Décisions d'architecture

### 2.1 Orchestration : Celery+Redis vs. Cron+table de queue

| Critère | A. Celery + Redis | B. Cron + `odoo_sync_queue` | **C. Hybride (retenu)** |
|---|---|---|---|
| Latence F2/F3 (Odoo up) | Quasi immédiate | Jusqu'à l'intervalle cron (15 min) | **Quasi immédiate** |
| Résilience si Odoo down | Retry auto (backoff Celery) | Retry au prochain cron | Retry au prochain cron |
| Nouveaux process à opérer | Worker + Beat (+Flower) | **Aucun** | **Aucun** |
| Cohérence avec l'existant | Rupture (aucun worker de ce type dans PERMATEL) | 100% cohérent (CLI + cron déjà établi) | Cohérent (étend le pattern déjà visible dans `demandes.py` : notification best-effort après commit) |
| Isolation multi-tenant en panne | Nécessite des queues nommées | Naturelle (`tenant_id` en colonne) | Naturelle |
| Charge d'implémentation | Élevée | Faible | Faible-moyenne |

**Retenu : Option C.** Après le commit de la demande/vacation, tentative
**synchrone à timeout court (2-3s)** vers Odoo (même style que le bloc
"notifications non bloquant" déjà présent dans `demandes.py`). Succès → terminé.
Échec/timeout → insertion dans `odoo_sync_queue`, reprise par
`flask odoo-sync-dispatch` sur cron (même cadence que `sessions-sweep`). Aucun
broker de tâches, aucun nouveau process à superviser.

Céder à Celery seulement si le volume/la complexité d'orchestration dépasse un
jour ce qu'une table + un cron peuvent absorber — non justifié au périmètre F1-F5.

### 2.2 Client Odoo : `xmlrpc.client` (stdlib) vs. `odoorpc` vs. `requests`+JSON-RPC

| Critère | **`xmlrpc.client`** (retenu) | `odoorpc` | `requests` + JSON-RPC brut |
|---|---|---|---|
| Dépendance ajoutée | **Aucune** (stdlib) | Package tiers | `requests` (à ajouter) |
| Ergonomie | Bas niveau, explicite | ORM-like, plus haut niveau | Bas niveau, tout à coder |
| Cohérence style codebase | **Oui** (le projet préfère l'explicite au framework magique partout ailleurs) | Non | Oui, mais sans bénéfice vs. stdlib |
| Risque dépréciation (§3.6 CDC) | Ne dépend d'aucun mainteneur tiers | Dépend de la réactivité du mainteneur | Dépend entièrement de nous |

**Retenu : `xmlrpc.client`**, encapsulé dans un service interne fin
`app/services/odoo_client.py` pour ne pas disperser les appels `execute_kw`
dans les routes.

### 2.3 Flag d'activation par tenant

**Retenu : `integrations.erp`** (dans `tenant_features()`), et non `channel_odoo` —
ce n'est pas un canal de communication (téléphonie/email/chat) mais une
intégration back-office, à côté de `integrations.slack`/`integrations.telephony`
déjà existants.

---

## 3. Modèle de données (nouvelles tables, `backend/app/models/odoo.py`)

| Table | Rôle |
|---|---|
| `odoo_config` | Config de connexion par tenant (base, URL API, identifiants). Secrets via `EncryptedText` (`crypto.py`, TypeDecorator existant mais jamais utilisé jusqu'ici — préférer ce mécanisme au chiffrement manuel de `settings.py`). |
| `odoo_partners` | Copie locale des partenaires (`odoo_id`, `sync_status`, `last_synced_at`). |
| `odoo_devis` / `odoo_factures` | Copie locale en lecture. |
| `odoo_planning_slots` | Copie locale des créneaux de planning. |
| `odoo_sync_queue` | File de retry (`tenant_id`, `flux`, `payload` JSONB, `status`, `attempts`, `next_retry_at`, `last_error`). |

Toutes ces tables suivent le modèle d'isolation multi-tenant existant
(`tenant_id` + FK composites), et les migrations suivent la convention déjà en
place (docstring français, garde-fou données explicite, jamais de suppression
silencieuse — voir `a3178519ad55_tenant_id_not_null_clients_sites.py` comme
référence).

---

## 4. Phasage détaillé

Le détail tâche-par-tâche est dans `docs/suivi_taches_permatel.xlsx`, onglet
« Tâches » (IDs `6.x` à `10.x`). Résumé :

| Phase | Contenu | Détail |
|---|---|---|
| **Phase 6** | Fondations transverses | Flag `integrations.erp`, `OdooConfig` + migration, `odoo_sync_queue` + migration, route `/api/settings/odoo` (GET/PUT/test), service `odoo_client.py`, commande `flask odoo-sync-dispatch` |
| **Phase 7** | Infra Odoo + Partenaires (F1) | Conteneur Odoo 18 + Postgres dédié (réseau interne, jamais exposé), multi-database (`dbfilter`, `list_db=False`, rôle Postgres par tenant), `odoo_partners` + migration, `flask odoo-sync-partners`, indicateur de fraîcheur frontend |
| **Phase 8** | Commande → Devis / Facture (F2/F4) | Hook best-effort sur création demande commande, `odoo_devis`/`odoo_factures` + migration, sync retour via dispatch cron, affichage frontend |
| **Phase 9** | Vacation → Feuille de temps (F3) | Hook best-effort sur clôture `PriseDeService` |
| **Phase 10** | Planning agents (F5) | Sync lecture planning, action d'affectation → écriture Odoo, vue frontend dédiée (EF à détailler après stabilisation 6-9) |

---

## 5. Hors périmètre (inchangé du CDC)

- Développement de modules Odoo custom.
- Interface Odoo visible aux utilisateurs finaux (masquée par défaut, accès
  direct réservé au dépannage).
- Facturation multi-devises/multi-fiscalité avancée.

---

## 6. Prochaines étapes

1. Validation de ce plan (fait — décisions §2 actées avec le porteur de projet).
2. Détail des exigences fonctionnelles module par module (format EF-XXX-NN),
   en particulier pour la Phase 10 (planning agents, la plus couplée UI).
3. Détail des exigences non fonctionnelles (sécurité, performance,
   disponibilité) — notamment le dimensionnement serveur pour le conteneur
   Odoo + Postgres dédié (CDC §3.6).
4. Démarrage effectif : **Phase 6** (fondations), sur confirmation explicite —
   aucune implémentation n'a été lancée à ce stade.
