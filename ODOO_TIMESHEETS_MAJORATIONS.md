# Architecture : Gestion des Majorations Tarifaires (Odoo Timesheets)

**Date** : 15 Août 2026
**Contexte** : Dans la sécurité privée, les vacations (Prises de Service) sont facturées différemment selon la plage horaire (Jour, Nuit, Week-end, Férié).
**Problème** : Nativement, une tâche Odoo n'est liée qu'à une seule ligne tarifaire. Sans module custom Odoo, il est impossible pour Odoo de ventiler automatiquement une feuille de temps de 8h en plusieurs tarifs.

Ce document décrit la solution architecturale choisie pour PERMATEL.

> **Statut (15/08)** : ce document est le brouillon d'intention d'origine —
> conservé pour le contexte métier, mais **son contenu technique a été
> revu et corrigé** suite à une évaluation critique le même jour
> (majorations cumulatives et non exclusives, dépendance implicite entre
> facturation client et paie agent, absence de versionnement des règles,
> absence de repli si aucune correspondance, non-alignement avec
> l'idempotence `x_permatel_ref` déjà actée en Phase D, etc.). Le détail
> d'implémentation **faisant foi** est désormais
> `ODOO_IMPLEMENTATION_PLAN.md`, **Phase G.5 — Moteur de majoration
> (TimeSplitter)**. Ne pas implémenter directement à partir de ce document
> seul.

---

## 1. Responsabilités (Séparation des préoccupations)

*   **PERMATEL (Master)** : Porte l'intelligence de découpage du temps. PERMATEL connaît les dates exactes, applique les règles de majoration temporelles, et découpe la durée totale en segments qualifiés.
*   **Odoo (Moteur de facturation)** : Ne fait aucun calcul de plage horaire. Odoo reçoit des heures déjà qualifiées et les impute bêtement sur la ligne tarifaire (`so_line`) exacte fournie par PERMATEL.

## 2. Le Moteur de Règles ("TimeSplitter")

PERMATEL intègrera un moteur de règles temporelles (configurable par tenant dans un futur modèle `tenant_majoration_rules`).
*Exemple de règles par défaut :*
*   **Jour** : 06h00 - 21h00
*   **Nuit** : 21h00 - 06h00
*   **Week-end** : Du Samedi 00h00 au Dimanche 23h59

À la **clôture d'une vacation** (Prise de Service), la fonction Python `split_vacation_time(start, end, rules)` sera appelée. 
Si un agent badge de Vendredi 18h00 à Samedi 02h00 (8 heures au total), le moteur génèrera 3 segments :
1.  18h00 - 21h00 ➔ **3h Jour**
2.  21h00 - 00h00 ➔ **3h Nuit Semaine**
3.  00h00 - 02h00 ➔ **2h Nuit Week-end**

## 3. Le Lien avec Odoo (Forcer le `so_line`)

Pour qu'Odoo facture ces 3 segments à des tarifs différents, le Devis (créé par le Manager dans PERMATEL) doit préalablement contenir plusieurs lignes de facturation pour le même site.

Lors du push de la feuille de temps via XML-RPC, le cron PERMATEL va rechercher les IDs des lignes de vente Odoo (`sale.order.line`) correspondant aux prestations du devis validé, et envoyer un *payload multiple*.

### Exemple de Payload XML-RPC généré par PERMATEL :
```python
[
    # Ligne 1 : 3h de Jour
    {
        'project_id': 45,
        'task_id': 12,
        'employee_id': 8,
        'unit_amount': 3.0,
        'so_line': 105, # <--- ID de la ligne Odoo "Gardiennage Jour (25€)"
        'name': 'Vacation - Jour'
    },
    # Ligne 2 : 3h de Nuit
    {
        'project_id': 45,
        'task_id': 12,
        'employee_id': 8,
        'unit_amount': 3.0,
        'so_line': 106, # <--- ID de la ligne Odoo "Gardiennage Nuit (32€)"
        'name': 'Vacation - Nuit Semaine'
    },
    # Ligne 3 : 2h de Nuit Week-end
    {
        'project_id': 45,
        'task_id': 12,
        'employee_id': 8,
        'unit_amount': 2.0,
        'so_line': 107, # <--- ID de la ligne Odoo "Nuit Week-end (40€)"
        'name': 'Vacation - Nuit Week-end'
    }
]
```

## 4. Impact sur le Modèle de Données PERMATEL

1.  **Devis (Multi-lignes)** : Le modèle `DevisLigne` doit stocker la nature de la prestation (Jour, Nuit) pour pouvoir faire la correspondance (`mapping`) lors du pointage.
2.  **Configuration Tenant** : Ajouter une interface dans l'onglet "Paramètres" pour permettre au client SaaS de définir à quelle heure commence sa "Nuit" contractuelle.
3.  **Traçabilité** : Dans `prises_de_service`, il sera intéressant de stocker le JSON du découpage retourné par le *TimeSplitter* pour justifier la facturation en cas de litige avec un client.
