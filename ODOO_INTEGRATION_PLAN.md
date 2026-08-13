# PERMATEL × Odoo — Plan d'intégration et d'Architecture Globale

**Statut** : Planification et Architecture Validées — prêt pour l'implémentation.
**Date** : 13 Août 2026
**Suivi des tâches** : `docs/suivi_taches_permatel.xlsx` 

*(Note contextuelle : Les Phases 1 à 5 du projet global concernaient le développement du cœur de PERMATEL. L'intégration Odoo constitue le deuxième grand bloc du projet, s'étalant historiquement des Phases 6 à 10 dans le document de suivi).*

---

## 1. Analyse du besoin et Philosophie

L'intégration d'Odoo 18 Community agit comme un service ERP additionnel (CRM/Vente, Comptabilité/Facturation, Planning RH) activable par tenant. 

**Philosophie de synchronisation :**
- PERMATEL est l'unique interface de saisie opérationnelle (Master).
- Odoo assure le traitement financier et RH (Moteur backend).
- Les suppressions PERMATEL se traduisent TOUJOURS par un **Archivage (Soft Delete)** dans Odoo (`active=False`) pour préserver l'intégrité comptable.

---

## 2. Décisions d'architecture technique

### 2.1 Orchestration : Cron + `odoo_sync_queue`
Après le commit d'une action, tentative **synchrone à timeout court (2-3s)** vers Odoo via XML-RPC. Succès → terminé. Échec/timeout → insertion dans `odoo_sync_queue`, reprise par `flask odoo-sync-dispatch` sur cron. Aucun broker Celery n'est requis.

### 2.2 Client Odoo
Utilisation de `xmlrpc.client` (stdlib Python), encapsulé dans `app/services/odoo_client.py`.

---

## 3. Évolution du Modèle de données (PERMATEL)

L'intégration Odoo requiert l'ajout de nouveaux modèles dans PERMATEL pour s'aligner sur les standards ERP.

### A. Modèles Opérationnels (Nouveaux et Modifiés)
* **`Produit`** : Nouveau catalogue de prestations. Remplacera l'enum statique `type_commande`.
* **`TarifClient`** : Nouvelle grille tarifaire négociée par client.
* **`DemandeCommande`** : Modifié. Conserve son rôle de "demande brute" (avec choix multiple de prestations via tableau/JSON).
* **`Devis` / `DevisLigne`** : Nouveaux modèles. Créés par un Manager à partir d'une commande. Miroir exact du `sale.order` et `sale.order.line` d'Odoo.

### B. Tables de Mapping Odoo (`backend/app/models/odoo.py`)
* `odoo_config` : Config de connexion par tenant.
* `odoo_partners` : Mapping CRM (`tenant_id`, type, `permatel_id`, `odoo_partner_id`, `odoo_project_id`, `odoo_task_id`).
* `odoo_employees` : Mapping RH (`tenant_id`, `agent_id`, `odoo_employee_id`).
* `odoo_sync_queue` : File de retry (`flux`, `payload` JSONB, `status`).
* `odoo_factures` : Copie locale en lecture seule des factures Odoo (Pull).

---

## 4. Phasage de l'implémentation (Alignement des Études)

Le détail des tâches est géré dans le fichier de suivi Excel (Phases 6 à 10). Voici l'alignement entre ces phases et les études architecturales (Parties 1, 2 et 3) :

### Phase 6 : Fondations transverses
* Flag `integrations.erp` activable par tenant.
* Création de `OdooConfig` et `odoo_sync_queue`.
* Service XML-RPC `odoo_client.py` et script CLI `flask odoo-sync-dispatch`.

### Phase 7 : Gestion des Partenaires (Partie 1 : CRM)
* **Client PERMATEL** → Odoo `res.partner(is_company=True)` + `project.project`.
* **Site PERMATEL** → Odoo `res.partner(delivery)` + `project.task`.
* **Contact PERMATEL** → Odoo `res.partner(contact)` lié au client principal (résolution de la relation N:N).
* *Phase 7.b (Catalogue)* : Synchronisation des `Produits` vers `product.product` et des `TarifsClient` vers `product.pricelist`.

### Phase 8 : Commandes et Facturation (Partie 2 : Ventes/Compta)
1. **Création (Push)** : Le Manager transforme une `DemandeCommande` en **Devis** dans PERMATEL. Cela pousse un `sale.order` (Brouillon) dans Odoo avec les bonnes lignes de produits.
2. **Validation (Push)** : La validation du devis dans PERMATEL déclenche l'`action_confirm` dans Odoo (transformation en Bon de commande).
3. **Facturation (Pull)** : Le cron PERMATEL récupère l'état des factures (`account.move`) depuis Odoo pour les afficher aux managers.

### Phase 9 : Agents & Temps (Partie 3 : RH/Analytique)
* **Agent** → Mapping vers `hr.employee`. (Les agents sous-traitants reçoivent une étiquette/tag Odoo spécifique pour les différencier).
* **Vacations** : À la **clôture** exacte d'une `PriseDeService` dans PERMATEL, le script calcule la durée en heures et l'injecte comme feuille de temps (`account.analytic.line`) sur le Projet (Client) et la Tâche (Site) Odoo. 
* *Note : Les vacations chevauchant minuit sont scindées en deux feuilles de temps.*

### Phase 10 : Planning agents
* Synchronisation en lecture du planning Odoo (si utilisé) et actions d'affectation. (À détailler après stabilisation de la phase 9).
