# AUDIT DE SYNCHRONISATION - FILTRAGE /sites

## 1. Résumé

**Défaut identifié :** Désynchronisation critique entre les paramètres d'URL et la requête API `/api/sites`.

**URL :** `/sites?client_id=1`  
**Requête API :** `/api/sites?page=1&per_page=10&search=&status=` ❌ `client_id` manquant

**Cause racine :** Le composable `useSites.js` ne passe pas le filtre `clientFilter` à la requête API, bien que SitesView.vue le capture depuis l'URL.

**Impact :** 
- Les filtres `client_id` en URL ne sont jamais appliqués
- Les utilisateurs reçoivent des données incorrectes
- Les signets/partages d'URL échouent

**Sévérité :** 🔴 HAUTE

---

## 2. Audit Frontend

### 2.1 SitesView.vue - Capture des filtres

✅ **URL reading correct :**
```javascript
// onMounted: capture les paramètres d'URL
if (route.query.client_id) clientFilter.value = route.query.client_id;
if (route.query.status) statusFilter.value = route.query.status;
if (route.query.search) searchQuery.value = route.query.search;
```

✅ **State initialization :** Les ref locales sont correctement initialisées depuis la route.

✅ **Watch updating URL :** Les modifications de filtres mettent à jour l'URL.
```javascript
watch([clientFilter, statusFilter, searchQuery, page, itemsPerPage], ...)
```

### 2.2 SitesView.vue - Binding UI

✅ **Contrôles UI :** Les inputs/select sont liés à `clientFilter`, `statusFilter`, `searchQuery`

✅ **Change handlers :** `@change="loadSites"` et `@input="onSearchInput"` présents

❌ **Problème : Perte de clientFilter** 
```javascript
// Ligne 570 - useSites est destructuré SANS clientFilter !
const {
  sites,
  totalSites,
  loading,
  submissionLoading,
  submissionError,
  listError,
  submissionSuccess,
  searchQuery,
  statusFilter,
  clientFilter: _clientFilter, // ← Capture depuis composable (inexistant)
  itemsPerPage,
  page,
  totalPages,
  loadSites,
  ...
} = useSites();

// Ligne 583 - Fallback de sécurité
const clientFilter = _clientFilter || ref("");
```

**Résultat :** `clientFilter` existe dans SitesView mais est LOCAL et NON PASSÉ à `loadSites()`.

---

## 3. Audit Appel API

### 3.1 useSites.js - Construction des paramètres

❌ **CRITIQUE - client_id manquant :**

```javascript
// Ligne 29-34
const loadSites = async () => {
  loading.value = true;
  try {
    const params = {
      page: page.value,
      per_page: itemsPerPage.value,
      search: searchQuery.value,
      status: statusFilter.value,        // ✅ Présent
      sort_by: sortBy.value.length ? sortBy.value[0].key : undefined,
      order: sortBy.value.length ? sortBy.value[0].order : undefined,
      // ❌ MANQUANT : client_id
    };
    const response = await apiClient.get("/sites", { params });
```

**Impact direct :** Même si `clientFilter` vaut `1`, il n'est jamais envoyé à l'API.

### 3.2 Exports du composable

❌ **client_id n'est pas exposé :**
```javascript
return {
  sites,
  totalSites,
  loading,
  submissionLoading,
  submissionError,
  submissionSuccess,
  searchQuery,
  statusFilter,      // ✅ Exposé
  itemsPerPage,
  page,
  totalPages,
  // ❌ MANQUANT : clientFilter ou client_id
  loadSites,
  ...
};
```

---

## 4. Audit Backend

### 4.1 sites.py - Endpoint `/api/sites` (GET)

✅ **Support client_id présent :**

```python
# Ligne 95-110
# Extraction robuste et infaillible des IDs de client
client_ids = set()

for key in ['client_id', 'client_id[]']:
  values = request.args.getlist(key)
  for val in values:
    if not val or val.lower() in ['null', 'undefined']:
      continue
    for cid in str(val).split(','):
      cid_clean = cid.strip()
      if cid_clean.isdigit():
        client_ids.add(int(cid_clean))

if client_ids:
  query = query.filter(Site.client_id.in_(list(client_ids)))
```

✅ **Support search présent :** 
```python
if search_query:
  search_term = f"%{search_query}%"
  query = query.filter(db.or_(
    Site.nom.ilike(search_term),
    Site.code_site.ilike(search_term)
  ))
```

✅ **Support status présent :**
```python
if status_filter and status_filter.lower() == 'true':
  query = query.filter(Site.is_active == True)
elif status_filter and status_filter.lower() == 'false':
  query = query.filter(Site.is_active == False)
```

**Conclusion :** Le backend est prêt et attend `client_id` dans la requête. ✅

---

## 5. Cause de la Désynchronisation

### Architecture actuelle

```
URL: /sites?client_id=1
  ↓
SitesView.vue (onMounted)
  ├─ Capture: clientFilter.value = "1" ✅
  └─ Appel: loadSites()
    ↓
useSites.loadSites()
  ├─ Construit params: { page, per_page, search, status }
  ├─ ❌ CLIENT_ID OUBLIÉ
  └─ Envoie: GET /api/sites?page=1&per_page=10&search=&status=
    ↓
Backend sites.py
  └─ Pas de client_id reçu → Applique aucun filtre client
```

### Problème structural

1. **Chaîne de responsabilité cassée :** 
   - SitesView gère les filtres localement
   - useSites construit l'API call sans accès à clientFilter
   - Communication manquante entre SitesView et useSites

2. **useSites.js n'a pas clientFilter** en ref locale
   - Seuls `page`, `itemsPerPage`, `searchQuery`, `statusFilter` sont dans useSites
   - `clientFilter` est défini dans SitesView
   - `loadSites()` n'a aucun moyen de l'accéder

---

## 6. Correctifs Frontend

### 6.1 Correction useSites.js

**Action :** Ajouter `clientFilter` en ref locale et l'inclure dans les paramètres API.

```javascript
// AVANT (ligne 12)
const statusFilter = ref("");

// APRÈS
const statusFilter = ref("");
const clientFilter = ref("");  // ← NOUVEAU
```

```javascript
// AVANT (ligne 29-34)
const params = {
  page: page.value,
  per_page: itemsPerPage.value,
  search: searchQuery.value,
  status: statusFilter.value,
  sort_by: sortBy.value.length ? sortBy.value[0].key : undefined,
  order: sortBy.value.length ? sortBy.value[0].order : undefined,
};

// APRÈS
const params = {
  page: page.value,
  per_page: itemsPerPage.value,
  search: searchQuery.value,
  status: statusFilter.value,
  client_id: clientFilter.value,  // ← NOUVEAU
  sort_by: sortBy.value.length ? sortBy.value[0].key : undefined,
  order: sortBy.value.length ? sortBy.value[0].order : undefined,
};
```

```javascript
// AVANT (ligne 154)
return {
  sites,
  totalSites,
  loading,
  submissionLoading,
  submissionError,
  submissionSuccess,
  searchQuery,
  statusFilter,
  itemsPerPage,
  page,
  totalPages,
  loadSites,
  ...
};

// APRÈS
return {
  sites,
  totalSites,
  loading,
  submissionLoading,
  submissionError,
  submissionSuccess,
  searchQuery,
  statusFilter,
  clientFilter,  // ← NOUVEAU
  itemsPerPage,
  page,
  totalPages,
  loadSites,
  ...
};
```

### 6.2 Correction SitesView.vue

**Action :** Utiliser le `clientFilter` du composable au lieu de créer un local.

```javascript
// AVANT (ligne 570)
const {
  sites,
  totalSites,
  loading,
  submissionLoading,
  submissionError,
  listError,
  submissionSuccess,
  searchQuery,
  statusFilter,
  clientFilter: _clientFilter,  // Fallback (pas idéal)
  itemsPerPage,
  page,
  totalPages,
  loadSites,
  onSearchInput,
  onTableOptions,
  createSite,
  updateSite,
  deleteSite,
  resetSubmissionState,
} = useSites();

// Ligne 583 - Fallback de sécurité (plus nécessaire)
const clientFilter = _clientFilter || ref("");

// APRÈS
const {
  sites,
  totalSites,
  loading,
  submissionLoading,
  submissionError,
  listError,
  submissionSuccess,
  searchQuery,
  statusFilter,
  clientFilter,  // ← DIRECT, pas d'alias
  itemsPerPage,
  page,
  totalPages,
  loadSites,
  onSearchInput,
  onTableOptions,
  createSite,
  updateSite,
  deleteSite,
  resetSubmissionState,
} = useSites();
```

---

## 7. Correctifs Backend

### 7.1 sites.py - État actuel

✅ **Aucune correction nécessaire.** Le backend applique déjà les filtres `client_id`, `search`, et `status` correctement.

**Vérification :** 
- `client_id` extracté depuis `request.args.getlist('client_id')`
- `search` appliqué via `ilike()` sur `nom` et `code_site`
- `status` mappé vers `is_active` boolean

---

## 8. Tests de Validation

### 8.1 Test 1 : URL sans filtres
```
URL: /sites
Expected API call: GET /api/sites?page=1&per_page=10&search=&status=&client_id=
Validation: ✅ Tous les sites affichés
```

### 8.2 Test 2 : Filtre client_id
```
URL: /sites?client_id=1
Expected API call: GET /api/sites?page=1&per_page=10&search=&status=&client_id=1
Validation: ✅ Seulement les sites du client_id=1
```

### 8.3 Test 3 : Filtre search
```
URL: /sites?search=test
Expected API call: GET /api/sites?page=1&per_page=10&search=test&status=&client_id=
Validation: ✅ Seulement les sites contenant "test" dans nom/code_site
```

### 8.4 Test 4 : Filtre status
```
URL: /sites?status=true
Expected API call: GET /api/sites?page=1&per_page=10&search=&status=true&client_id=
Validation: ✅ Seulement les sites actifs
```

### 8.5 Test 5 : Filtres combinés
```
URL: /sites?client_id=1&search=depot&status=true
Expected API call: GET /api/sites?page=1&per_page=10&search=depot&status=true&client_id=1
Validation: ✅ Sites du client 1, actifs, contenant "depot"
```

### 8.6 Test 6 : Pagination avec filtres
```
URL: /sites?client_id=2&page=2&per_page=25
Expected API call: GET /api/sites?page=2&per_page=25&search=&status=&client_id=2
Validation: ✅ Page 2 des sites du client 2, 25 par page
```

### 8.7 Test 7 : Changement de filtre via UI
```
Action: Sélectionner "Client A" dans le select
Expected: URL change en /sites?client_id=X&...
Expected API: GET /api/sites?...&client_id=X
Validation: ✅ Liste se met à jour immédiatement
```

### 8.8 Test 8 : Sauvegarde du contexte avec lien direct
```
Action: Partager URL /sites?client_id=1&search=test&status=true
Au rechargement: Filtres restaurés, data correcte
Validation: ✅ Contexte préservé
```

---

## 9. Standard Final de Synchronisation

### Chaîne de synchronisation corrigée

```
URL: /sites?client_id=1&search=test&status=true&page=2&per_page=25
  ↓
SitesView.vue (onMounted)
  ├─ Capture: clientFilter.value = "1" ✅
  ├─ Capture: searchQuery.value = "test" ✅
  ├─ Capture: statusFilter.value = "true" ✅
  ├─ Capture: page.value = 2 ✅
  ├─ Capture: itemsPerPage.value = 25 ✅
  └─ Appel: loadSites()
    ↓
useSites.loadSites()
  ├─ Construit params: {
  │   page: 2,
  │   per_page: 25,
  │   search: "test",
  │   status: "true",
  │   client_id: "1"  ← MAINTENANT INCLUS ✅
  │ }
  └─ Envoie: GET /api/sites?page=2&per_page=25&search=test&status=true&client_id=1
    ↓
Backend sites.py
  ├─ Parse client_id: {1}
  ├─ Parse search: "test"
  ├─ Parse status: true
  ├─ Query: WHERE client_id=1 AND is_active=true AND (nom ILIKE "%test%" OR code_site ILIKE "%test%")
  └─ Retourne: Sites filtrés + paginés (page 2, 25 items)
    ↓
Frontend (response)
  ├─ Met à jour: sites[], totalSites, page
  └─ Affichage: Data correcte ✅
```

### Principe SSOT (Single Source of Truth)

**Source de vérité :** `route.query` (URL)
- ✅ onMounted : Récupère filtres depuis route.query
- ✅ watch : Met à jour route.query lors de changement
- ✅ loadSites : Utilise les valeurs actuelles pour API
- ✅ Backend : Applique les filtres tels que reçus

### Contrat API

```http
GET /api/sites
Query Parameters (tous optionnels, défaut vide):
  ?page=1                    # Pagination (défaut: 1)
  &per_page=10              # Items par page (défaut: 10)
  &search=""                # Texte de recherche (défaut: aucun)
  &status=""                # true|false (défaut: aucun = tous)
  &client_id=1              # ID client (défaut: aucun = tous)
  &sort_by=nom              # Clé de tri (optionnel)
  &order=asc                # Ordre de tri (optionnel)

Response:
  {
    "sites": [...],
    "total": 42,
    "page": 1,
    "per_page": 10,
    "total_pages": 5
  }
```

### Checklist d'implémentation

- [ ] Ajouter `clientFilter` ref dans useSites.js
- [ ] Inclure `client_id` dans params API
- [ ] Exporter `clientFilter` depuis useSites
- [ ] Utiliser `clientFilter` du composable dans SitesView
- [ ] Supprimer la ref locale `clientFilter` dans SitesView
- [ ] Tester chaque cas de validation (8 tests)
- [ ] Vérifier Network tab pour chaque requête
- [ ] Valider en production

---

## Annexes

### Fichiers affectés

1. **frontend/src/composables/useSites.js**
   - Ajouter `clientFilter` ref
   - Inclure dans `params`
   - Exporter dans return

2. **frontend/src/views/SitesView.vue**
   - Supprimer fallback `clientFilter: _clientFilter || ref("")`
   - Destructurer `clientFilter` directement depuis useSites

3. **backend/app/routes/sites.py**
   - ✅ Aucune modification (déjà correct)

### Liens de référence

- **Vue Router Query Params :** https://router.vuejs.org/guide/advanced/navigation-guards.html
- **Flask request.args :** https://flask.palletsprojects.com/en/latest/api/#flask.Request.args
- **Debouncing Search :** lodash-es `debounce()` utilisé pour `onSearchInput`

---

**Audit généré :** 2026-06-07  
**Audité par :** Senior Vue + Flask Filtering Auditor  
**Statut :** 🔴 CRITIQUE - En attente de correctifs
