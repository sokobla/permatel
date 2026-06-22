# 📋 RAPPORT D'AUDIT DE SÉCURITÉ APPLICATIVE : FORMULAIRES & SAISIES
**Projet** : PERMATEL Operational Suite  
**Auditeur** : Auditeur Sécurité Applicative Senior  
**Date de l'audit** : 22 juin 2026  
**Cible** : Formulaires Frontend (Vue 3 / Vuetify) & API Endpoints Backend (Flask / SQLAlchemy)  
**Référentiel** : OWASP Top 10, CWE  

---

## 1. Synthèse Exécutive

L'audit de sécurité de la suite opérationnelle PERMATEL s'est concentré sur l'analyse statique du code source pour évaluer la robustesse des formulaires face aux saisies malveillantes. 

### Conclusions clés :
- **SQL Injection (SQLi) : ✅ Excellent niveau de sécurité.** L'utilisation systématique de l'ORM SQLAlchemy à travers des requêtes paramétrées empêche nativement la construction de requêtes SQL dynamiques non sécurisées. Aucun usage de chaîne SQL brute concaténée n'a été détecté dans les blueprints.
- **Cross-Site Scripting (XSS) : ⚠️ Niveau de sécurité modéré.** Bien que le rendu standard de Vue 3 (`{{ ... }}`) protège la majorité des pages en échappant les variables, l'usage de `v-html` dans les modules collaboratifs (Messagerie, Emails) présente des risques. Une sanitisation basée sur `DOMPurify` est en place pour les emails, mais les bulles de chat reposent sur une expression régulière maison, ce qui est considéré comme fragile (défense en profondeur insuffisante).
- **Validation des données : ❌ Niveau de sécurité faible.** Il y a une confusion marquée entre validation UX (guidage utilisateur) et validation de sécurité (contrôle aux limites). Le backend accepte des données incohérentes (ex: absence de contrôle de longueur sur les champs de texte, regex d'email extrêmement permissive), ce qui permet de provoquer des crashs de base de données (Erreur 500 / Denial of Service) ou de contourner les politiques de sécurité (ex: création de mots de passe d'une seule lettre).

---

## 2. Inventaire des Formulaires et Points d'Entrée (API)

L'application comporte 10 formulaires fonctionnels majeurs répartis entre l'interface utilisateur et les points d'accès API correspondants :

| N° | Formulaire Fonctionnel | Composant Frontend (Saisie) | Endpoint Backend (Traitement) |
|---|---|---|---|
| 1 | Authentification | [LoginView.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/views/LoginView.vue) | `POST /api/auth/login` |
| 2 | Gestion des Clients | [ClientsView.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/views/ClientsView.vue) | `POST /api/clients` & `PUT /api/clients/<id>` |
| 3 | Gestion des Sites | [SitesView.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/views/SitesView.vue) | `POST /api/sites` & `PUT /api/sites/<id>` |
| 4 | Gestion des Utilisateurs | [UsersView.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/views/UsersView.vue) | `POST /api/users` & `PUT/PATCH /api/users/<id>` |
| 5 | Gestion des Contacts | [ContactsView.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/views/ContactsView.vue) | `POST /api/contacts` & `PUT /api/contacts/<id>` |
| 6 | Gestion des Demandes (Tickets) | [AnomaliesView.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/views/AnomaliesView.vue) & [OrdersView.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/views/OrdersView.vue) | `POST /api/demandes` & `PUT /api/demandes/<id>` |
| 7 | Gestion des Prestataires | [PartnerView.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/views/PartnerView.vue) | `POST /api/prestataires` & `PUT /api/prestataires/<id>` |
| 8 | Gestion des Agents | [AgentView.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/views/AgentView.vue) | `POST /api/agents` & `PUT /api/agents/<id>` |
| 9 | Envoi d'Emails Métier | [MailChannel.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/components/workspace/MailChannel.vue) | `POST /api/emails/send` |
| 10| Configuration SMTP / IMAP | [SettingsSmtp.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/components/settings/SettingsSmtp.vue) | `POST /api/settings/smtp` & `POST /api/settings/imap` |

---

## 3. Analyse de la Validation des Données

### A. Analyse Comparative (Validation UX vs Validation Sécurité)
Dans une architecture moderne, la validation frontend sert à l'UX (retour immédiat à l'opérateur), tandis que **la validation backend est l'unique ligne de défense pour la sécurité**.

#### Preuve de Code (Frontend)
Dans [ClientsView.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/views/ClientsView.vue#L678-L694), la validation consiste en une vérification de la présence des champs requis et un format regex d'email standard :
```javascript
function validateForm() {
  Object.keys(formErrors).forEach((k) => (formErrors[k] = ""));
  let isValid = true;
  if (!form.nom) {
    formErrors.nom = "Le nom est requis.";
    isValid = false;
  }
  if (!form.code_client) {
    formErrors.code_client = "Le code est requis.";
    isValid = false;
  }
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    formErrors.email = "Format d'email invalide.";
    isValid = false;
  }
  return isValid;
}
```

#### Preuve de Code (Backend - Contraste)
Dans [prestataires.py](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/backend/app/routes/prestataires.py#L239-L250), la validation de sécurité est quasi-inexistante :
```python
    # ── Validation ────────────────────────────────────────────────────────── #
    required_fields = ["nom", "adresse", "ville", "telephone"]
    missing = [f for f in required_fields if not payload.get(f)]
    if missing:
        return jsonify({"error": f"Champs requis manquants : {', '.join(missing)}"}), 400

    nom = payload["nom"].strip()
    # ...
    email = (payload.get("email") or "").strip() or None
    if email and not '@' in email:
        return jsonify({"error": "Format d'email invalide."}), 400
```
*Faiblesse constatée :* Le format de l'adresse email est validé par un simple check de présence du caractère `@`. Une valeur `"a@b"` ou `"invalide@"` est acceptée par l'API backend.

### B. Risque d'erreur de base de données (DoS par taille d'entrée)
Le backend n'effectue aucun contrôle de longueur sur les chaînes reçues.
- *Exemple :* Le modèle `Client` définit `code_client = Column(String(50))` dans [client.py](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/backend/app/models/client.py).
- Si une requête malveillante envoie un `code_client` de 1000 caractères, l'API tente de l'insérer directement.
- PostgreSQL lève alors une exception de type `value too long for type character varying(50)` (code SQLSTATE 22001), provoquant un plantage complet de la requête avec un code retour `HTTP 500`. C'est une vulnérabilité de **Denial of Service applicatif** par injection de charge utile volumineuse.

### C. Politique de Mots de Passe Insuffisante
Lors de la création d'un utilisateur dans [users.py](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/backend/app/routes/users.py#L197-L247) :
- Le mot de passe fourni par la requête (`data["password"]`) n'est soumis à **aucune vérification de longueur ni de complexité**.
- L'appel direct à `user.set_password(data["password"])` génère le hash (via PBKDF2) même pour un mot de passe d'un seul caractère (ex : `"1"`).
- Seule la mise à jour par l'utilisateur lui-même vérifie une longueur minimale de 8 caractères : `if not new_password or len(new_password) < 8` dans [users.py](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/backend/app/routes/users.py#L441), ce qui laisse une faille majeure lors du provisionnement des comptes par l'administrateur.

---

## 4. Analyse XSS (Cross-Site Scripting)

### A. Rendu par défaut et étanchéité de Vue.js
Sur la quasi-totalité des pages, l'affichage se fait via l'interpolation standard de texte de Vue.js (ex : `{{ item.nom }}`). Vue convertit automatiquement les caractères spéciaux (`<`, `>`, `&`, `"`, `'`) en entités HTML correspondantes. Le risque de XSS réfléchi ou stocké dans les pages classiques est donc nul.

### B. Analyse des usages de `v-html` (Rendu Dynamique)
Nous avons identifié 3 emplacements dans le code frontend utilisant la directive `v-html` pour afficher du texte dynamique, ce qui désactive la protection native de Vue.js.

#### 1. Messagerie Instantanée ([ChatBox.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/components/workspace/ChatBox.vue#L134))
- **Code cible** : `<p class="cbx-msg-text" v-html="formatText(msg.text)"></p>`
- **Logique de formatage** :
  ```javascript
  function formatText(text) {
    return (text ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  }
  ```
- **Évaluation** : La fonction applique un échappement de base (`&`, `<`, `>`) avant de générer des balises `<strong>`. Bien que cela neutralise les balises `<script>` ou les attributs d'événement (`onerror=`), l'usage d'expressions régulières maison pour la sanitisation HTML est considéré comme une mauvaise pratique de sécurité (fragilité face aux contournements de navigateurs).

#### 2. Corps textuel des e-mails ([MailBox.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/components/workspace/MailBox.vue#L126))
- **Code cible** : `<div class="mbx-body-text" v-html="formatBody(activeEmail.body)"></div>`
- **Logique de formatage** : Similaire à `formatText` mais injecte des balises `<p>` et `<br/>`. Échappement initial correct, mais hérite des mêmes limites d'absence de bibliothèque de sanitisation formelle.

#### 3. Rendu HTML des e-mails ([MailChannel.vue](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/components/workspace/MailChannel.vue#L168))
- **Code cible** : `<div class="mc-message__html" v-html="renderedHtml">`
- **Logique de formatage** : 
  `renderedHtml` utilise la fonction `sanitizeEmailHtml` importée de [sanitizeHtml.js](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/frontend/src/utils/sanitizeHtml.js).
  ```javascript
  import DOMPurify from "dompurify";
  
  DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    if (node.tagName === "A") {
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer nofollow");
    }
  });
  
  export function sanitizeEmailHtml(html) {
    if (!html) return "";
    return DOMPurify.sanitize(html, {
      ALLOWED_TAGS: [ ... ],
      ALLOWED_ATTR: [ ... ],
      FORBID_TAGS: ["script", "style", "iframe", "object", "embed", "form", "input"],
      FORBID_ATTR: ["onerror", "onload", "onclick"],
      ALLOW_DATA_ATTR: false,
    });
  }
  ```
- **Évaluation** : **Excellente implémentation.** L'utilisation de `DOMPurify` avec une liste blanche stricte de balises autorisées et le blocage formel des balises et attributs dangereux (`FORBID_TAGS`, `FORBID_ATTR`) offre une protection de niveau industriel contre les XSS stockés via les emails entrants. Le hook forçant les attributs de sécurité des liens (`rel="noopener noreferrer"`) prévient également les failles de type *Reverse Tabnabbing*.

---

## 5. Analyse des Injections SQL

L'application PERMATEL présente une excellente résilience face aux vulnérabilités d'injection SQL.

### Robustesse constatée
Toutes les opérations d'accès aux données dans le backend (consultation, insertion, mise à jour, suppression) s'appuient sur l'ORM **SQLAlchemy 2.0**.
- SQLAlchemy traduit les requêtes de l'application en requêtes SQL paramétrées (Parameterized Queries).
- Les entrées de l'utilisateur ne sont jamais concaténées ou interpolées directement dans une chaîne de requête SQL.

#### Preuve de Code (Recherche Textuelle Sécurisée)
Dans [clients.py](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/backend/app/routes/clients.py#L103-L111) :
```python
    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Client.nom.ilike(search_term),
                Client.code_client.ilike(search_term),
                Client.email.ilike(search_term)
            )
        )
```
Bien que la variable `search_term` contienne des saisies utilisateurs libres, la méthode `.ilike()` génère un paramètre SQL propre (ex : `WHERE clients.nom ILIKE ?`). L'analyseur PostgreSQL traite l'entrée comme une simple donnée littérale et non comme une instruction exécutable.

---

## 6. Vulnérabilités Priorisées

| ID | Vulnérabilité | CWE / OWASP | Impact | criticité | Statut |
|---|---|---|---|---|---|
| **SEC-01** | Politique de mots de passe vide sur l'API de création utilisateur | CWE-521 / A07:2021 | Permet le provisionnement de comptes à mot de passe trivial (faible résistance bruteforce) | **ÉLEVÉE** | 🚨 À corriger |
| **SEC-02** | Absence de validation de longueur des champs de formulaire | CWE-20 / CWE-770 | Erreurs 500 non gérées (plantage DB) provoquant un déni de service applicatif | **MOYENNE** | 🚨 À corriger |
| **SEC-03** | Expression régulière de courriel backend trop permissive | CWE-20 | Stockage d'adresses invalides contournant les contrôles métier | **FAIBLE** | 🚨 À corriger |
| **SEC-04** | Sanisation de texte dynamique basée sur du regex maison | CWE-116 | Risque de contournement de filtre XSS selon l'évolution des moteurs de rendu | **FAIBLE** | ℹ️ À surveiller |

---

## 7. Plan de Correction (Remédiation)

### Correction SEC-01 : Validation du mot de passe à la création
Ajouter un validateur de force de mot de passe dans le point d'accès de création des utilisateurs dans [users.py](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/backend/app/routes/users.py) :
```python
# À insérer dans backend/app/routes/users.py:220
password = data.get("password", "")
if len(password) < 12:
    return jsonify({"message": "Le mot de passe doit comporter au moins 12 caractères."}), 400
if not any(c.isupper() for c in password) or not any(c.islower() for c in password) or not any(c.isdigit() for c in password):
    return jsonify({"message": "Le mot de passe doit contenir des majuscules, des minuscules et des chiffres."}), 400
```

### Correction SEC-02 : Validation des limites de taille (Backend)
Implémenter des décorateurs de validation ou des fonctions utilitaires pour rejeter les requêtes dépassant les tailles SQL déclarées avant d'interroger la base de données.
```python
def validate_string_length(value, max_length, field_name):
    if value and len(str(value)) > max_length:
        raise ValueError(f"Le champ '{field_name}' dépasse la taille maximale autorisée de {max_length} caractères.")
```

### Correction SEC-03 : Regex d'email backend standard
Remplacer le contrôle permissif par une validation formelle dans l'utilitaire de validation (ex : [prestataires.py](file:///C:/Users/Sokobla%20GAZARO/Documents/vscode/Python/permatel/backend/app/routes/prestataires.py)) :
```python
import re

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

if email and not EMAIL_REGEX.match(email):
    return jsonify({"error": "Format de courrier électronique non conforme."}), 400
```

---

## 8. Checklist de Remédiation pour les Développeurs

- [ ] **Mots de passe** : Valider la longueur (min 12) et la complexité lors de la création d'un utilisateur sur le backend.
- [ ] **Limites SQL** : Vérifier que chaque champ texte d'entrée est vérifié contre sa taille maximale de colonne dans le modèle (ex : max 50 caractères pour un `code_client`).
- [ ] **Validation d'email** : Appliquer l'expression régulière standard `EMAIL_REGEX` sur tous les points d'entrée d'email du backend.
- [ ] **Traitement XSS** : Remplacer à terme l'échappement regex custom de `formatText` dans `ChatBox.vue` par un passage dans `DOMPurify` avec des règles strictes adaptées pour le chat en ligne.
- [ ] **Téléchargements de logos/fichiers** : S'assurer que les fichiers reçus passent par la validation stricte d'extension et de type MIME (déjà partiellement en place pour les logos).

---

## 9. Vérifications Complémentaires Recommandées

1. **Audit dynamique (DAST / Fuzzing)** : Exécuter des tests d'intrusion dynamiques (avec des outils comme *OWASP ZAP*) sur les points d'accès des formulaires afin de valider qu'aucune injection de caractères spéciaux ou de charges utiles volumineuses ne provoque de crash ou de fuite d'informations.
2. **Audit des configurations CORS & CSP** : Vérifier la configuration des en-têtes de sécurité HTTP, en particulier la `Content Security Policy` (CSP), pour empêcher l'exécution de scripts injectés si un contournement de protection XSS avait lieu.
3. **Revue de la gestion des uploads** : Analyser si le stockage local des fichiers uploadés (`uploads/`) exécute les scripts côté serveur s'ils sont appelés directement (s'assurer que le serveur web type Nginx désactive l'exécution des scripts PHP/Python/CGI dans ce répertoire).
