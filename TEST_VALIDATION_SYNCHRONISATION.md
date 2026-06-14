# TEST DE VALIDATION - SYNCHRONISATION FILTRAGE /sites

## Environnement de test

**Date :** 2026-06-07  
**Frontend :** Vue 3 + Vite  
**Backend :** Flask + SQLAlchemy  
**Navigateur :** Chrome DevTools (Network Tab)

---

## Pré-requis de test

1. ✅ Backend démarré : `python app.py` sur `http://localhost:5000`
2. ✅ Frontend démarré : `npm run dev` sur `http://localhost:5173`
3. ✅ Database peuplée avec données de test (clients, sites)
4. ✅ Chrome DevTools ouvert (F12 → Network Tab)

---

## PLAN DE TEST

### Test 1 : URL sans filtres
**Cas :** Charger la page sans paramètres d'URL  
**URL :** `http://localhost:5173/sites`  

**Étapes :**
1. Naviguer vers `/sites`
2. Ouvrir Chrome DevTools → Network Tab
3. Observer la requête GET vers `/api/sites`

**Résultats attendus :**
- URL dans le browser: `/sites` (pas de query params)
- Requête API: `GET /api/sites?page=1&per_page=10&search=&status=&client_id=`
- Tableau affiche TOUS les sites
- Compte total correct

**Validation :** ✅ PASS si requête API contient `client_id=` (vide)

---

### Test 2 : Filtre client_id seul
**Cas :** Filtrer par client depuis URL  
**URL :** `http://localhost:5173/sites?client_id=1`  

**Étapes :**
1. Naviguer vers `/sites?client_id=1`
2. Observer la requête API dans Network Tab
3. Vérifier le select CLIENT dans l'UI

**Résultats attendus :**
- URL dans le browser: `/sites?client_id=1`
- Requête API: `GET /api/sites?page=1&per_page=10&search=&status=&client_id=1`
- Select CLIENT affiche le client sélectionné
- Tableau affiche SEULEMENT les sites du client 1

**Validation :** ✅ PASS si `client_id=1` dans la requête API ET affichage filtré

---

### Test 3 : Filtre search seul
**Cas :** Rechercher par texte  
**URL :** `http://localhost:5173/sites?search=depot`  

**Étapes :**
1. Naviguer vers `/sites?search=depot`
2. Observer la requête API
3. Vérifier le champ RECHERCHER dans l'UI

**Résultats attendus :**
- URL dans le browser: `/sites?search=depot`
- Requête API: `GET /api/sites?page=1&per_page=10&search=depot&status=&client_id=`
- Champ search affiche "depot"
- Tableau affiche SEULEMENT les sites avec "depot" dans le nom ou code_site

**Validation :** ✅ PASS si `search=depot` dans la requête API ET résultats filtrés

---

### Test 4 : Filtre status seul
**Cas :** Filtrer par statut (actif/inactif)  
**URL :** `http://localhost:5173/sites?status=true`  

**Étapes :**
1. Naviguer vers `/sites?status=true`
2. Observer la requête API
3. Vérifier le select STATUT dans l'UI

**Résultats attendus :**
- URL dans le browser: `/sites?status=true`
- Requête API: `GET /api/sites?page=1&per_page=10&search=&status=true&client_id=`
- Select STATUT affiche "ACTIF"
- Tableau affiche SEULEMENT les sites actifs (is_active=true)

**Validation :** ✅ PASS si `status=true` dans la requête API ET affichage filtré aux actifs

**Test alternatif - Inactifs :**
```
URL: /sites?status=false
Requête: /api/sites?...&status=false&client_id=
Résultat: Seulement sites inactifs
```

---

### Test 5 : Filtres combinés (client_id + search + status)
**Cas :** Combiner plusieurs filtres  
**URL :** `http://localhost:5173/sites?client_id=1&search=depot&status=true`  

**Étapes :**
1. Naviguer vers `/sites?client_id=1&search=depot&status=true`
2. Observer la requête API
3. Vérifier tous les filtres dans l'UI

**Résultats attendus :**
- URL dans le browser: `/sites?client_id=1&search=depot&status=true`
- Requête API: `GET /api/sites?page=1&per_page=10&search=depot&status=true&client_id=1`
- Select CLIENT affiche client 1
- Champ RECHERCHER affiche "depot"
- Select STATUT affiche "ACTIF"
- Tableau affiche SEULEMENT les sites:
  - Du client 1 ET
  - Contenant "depot" ET
  - Actifs

**Validation :** ✅ PASS si tous les paramètres dans API ET affichage correct

---

### Test 6 : Pagination avec filtres
**Cas :** Paginer tout en gardant les filtres  
**URL :** `http://localhost:5173/sites?client_id=2&page=2&per_page=25`  

**Étapes :**
1. Naviguer vers `/sites?client_id=2&page=2&per_page=25`
2. Vérifier le select CLIENT
3. Vérifier le numéro de page et items par page
4. Observer la requête API

**Résultats attendus :**
- URL dans le browser: `/sites?client_id=2&page=2&per_page=25`
- Requête API: `GET /api/sites?page=2&per_page=25&search=&status=&client_id=2`
- Tableau affiche page 2 (items 26-50 du client 2)
- Items par page: 25
- Filtre CLIENT est appliqué

**Validation :** ✅ PASS si pagination + filtre combinés dans la requête

---

### Test 7 : Changement de filtre via UI
**Cas :** Modifier un filtre via le select/input  
**URL de départ :** `/sites`  

**Étapes :**
1. Charger `/sites` (aucun filtre)
2. Cliquer sur le select CLIENT
3. Sélectionner "Client A" (client_id=1)
4. Observer Network Tab immédiatement

**Résultats attendus :**
- URL change en: `/sites?client_id=1` (automatiquement)
- Requête API envoyée: `GET /api/sites?page=1&per_page=10&search=&status=&client_id=1`
- Tableau se met à jour avec les sites du client 1

**Validation :** ✅ PASS si URL update automatique ET API call déclenché

**Test alternatif - Recherche :**
```
1. Charger /sites
2. Taper "test" dans RECHERCHER
3. Observer que URL change en /sites?search=test
4. Requête API: /api/sites?...&search=test&client_id=
```

---

### Test 8 : Sauvegarde et restoration du contexte
**Cas :** Partager un lien avec filtres appliqués  
**URL :** `http://localhost:5173/sites?client_id=3&search=securite&status=true`  

**Étapes :**
1. Naviguer vers URL avec filtres
2. Copier l'URL depuis la barre d'adresse
3. Ouvrir un nouvel onglet/fenêtre incognito
4. Coller l'URL et naviguer
5. Vérifier les filtres sont restaurés

**Résultats attendus :**
- Nouveau chargement: Tous les filtres appliqués
- Select CLIENT affiche client 3
- Champ RECHERCHER affiche "securite"
- Select STATUT affiche "ACTIF"
- Requête API correcte: `GET /api/sites?page=1&per_page=10&search=securite&status=true&client_id=3`
- Données correctes affichées

**Validation :** ✅ PASS si contexte sauvegardé/restauré correctement

---

## TESTS EDGE CASE

### Test 9 : Filtre avec valeurs vides
**Cas :** Paramètres d'URL vides  
**URL :** `http://localhost:5173/sites?client_id=&search=&status=`  

**Résultats attendus :**
- Requête API: `GET /api/sites?page=1&per_page=10&search=&status=&client_id=`
- Tableau affiche TOUS les sites (aucun filtre actif)
- Pas de sélection dans les dropdowns

**Validation :** ✅ PASS si valeurs vides traitées comme "sans filtre"

---

### Test 10 : Filtre client_id invalide
**Cas :** client_id inexistant  
**URL :** `http://localhost:5173/sites?client_id=99999`  

**Résultats attendus :**
- URL contient `client_id=99999`
- Requête API envoyée: `GET /api/sites?...&client_id=99999`
- Tableau affiche "AUCUN SITE TROUVÉ" (ou vide)
- Pas d'erreur JavaScript/réseau

**Validation :** ✅ PASS si requête valide, résultat vide correct

---

### Test 11 : Déselectionner un filtre via UI
**Cas :** Sélectionner "TOUS" dans un dropdown après avoir filtré  
**URL de départ :** `/sites?client_id=1`  

**Étapes :**
1. Charger `/sites?client_id=1`
2. Vérifier que CLIENT affiche client 1
3. Cliquer sur le select CLIENT
4. Sélectionner "TOUS" (option première)
5. Observer Network Tab

**Résultats attendus :**
- URL change en: `/sites` (client_id supprimé)
- Requête API: `GET /api/sites?page=1&per_page=10&search=&status=&client_id=`
- Tableau affiche TOUS les sites

**Validation :** ✅ PASS si déselection fonctionne

---

## VERIFICATION NETWORK TAB

Pour chaque test, vérifier dans Chrome DevTools → Network Tab :

```
✅ Colonne Method: GET
✅ Colonne Status: 200
✅ URL: /api/sites (avant la requête)
✅ Query String (après clic): Contient page, per_page, search, status, client_id
```

**Exemple de requête correct :**
```
GET /api/sites?page=1&per_page=10&search=&status=&client_id=1 HTTP/1.1
Host: localhost:5000
```

---

## MATRIX DE VALIDATION

| Test | Description | Status | Notes |
|------|-------------|--------|-------|
| 1 | Sans filtres | [ ] | |
| 2 | client_id seul | [ ] | CRITIQUE |
| 3 | search seul | [ ] | CRITIQUE |
| 4 | status seul | [ ] | CRITIQUE |
| 5 | Filtres combinés | [ ] | CRITIQUE |
| 6 | Pagination + filtres | [ ] | |
| 7 | Changement UI | [ ] | |
| 8 | Sauvegarde contexte | [ ] | |
| 9 | Valeurs vides | [ ] | Edge case |
| 10 | ID invalide | [ ] | Edge case |
| 11 | Déselection | [ ] | |

**Tous les tests CRITIQUES doivent passer avant production.**

---

## COMMANDES UTILES

### Démarrer l'environnement

```bash
# Terminal 1 - Backend
cd backend
source .venv/Scripts/Activate.ps1  # Windows
python app.py

# Terminal 2 - Frontend
cd frontend
npm run dev
```

### Inspecter la base de données

```bash
# Backend terminal
sqlite3 instance/app.db
SELECT id, nom FROM client LIMIT 5;
SELECT id, nom, client_id FROM site LIMIT 5;
```

### Clear cache du navigateur

```
Ctrl+Shift+Delete → All time → Cookies and cached images → Clear
```

---

## RÉSOLUTION DE PROBLÈMES

### Requête API n'inclut pas client_id

**Symptôme :** Même après correction, `client_id` n'apparaît pas dans l'URL de la requête  
**Diagnostic :**
1. Vérifier useSites.js export clientFilter ✅
2. Vérifier SitesView.vue le destructure ✅
3. Vérifier le Network Tab montre la vraie requête (pas le cache)

**Solution :**
- Hard refresh: `Ctrl+Shift+R`
- Vider le cache: `Ctrl+Shift+Delete`
- Redémarrer le serveur frontend: `npm run dev`

---

### Filtres ne se mettent pas à jour en URL

**Symptôme :** Je clique sur un select, rien ne change en URL  
**Diagnostic :**
1. Vérifier que le `watch` est présent dans SitesView.vue
2. Vérifier que `router.replace()` est appelé
3. Ouvrir la console (F12) pour les erreurs

**Solution :**
- Redémarrer Vue: `npm run dev`
- Vérifier qu'il n'y a pas d'erreur de compilation TypeScript

---

### Backend retourne 200 mais données vides

**Symptôme :** Requête API correcte, mais tableau vide  
**Diagnostic :**
1. Vérifier que la base de données a des données
2. Vérifier le filtre client_id correspond aux données
3. Vérifier que le backend applique le filtre

**Solution :**
```bash
# Dans le backend, ajouter un print() de debug
print(f"client_ids filter: {client_ids}")
print(f"Query result count: {pagination.items}")
```

---

## CHECKLIST FINALE

Avant de déployer en production :

- [ ] Test 1-5 ✅ PASS
- [ ] Test 6-8 ✅ PASS
- [ ] Test 9-11 ✅ PASS
- [ ] Network Tab montre client_id dans TOUS les appels
- [ ] URL se met à jour automatiquement au changement de filtre
- [ ] Aucune erreur console (F12)
- [ ] Pagination fonctionne avec filtres
- [ ] Partage d'URL fonctionne (contexte sauvegardé)
- [ ] Hard refresh ne perd pas le contexte
- [ ] Backend logs montrent les filtres appliqués

---

**Document créé :** 2026-06-07  
**Dernière mise à jour :** 2026-06-07  
**Version :** 1.0 - Initial
