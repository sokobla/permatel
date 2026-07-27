# AUDIT PERMATEL

Ce document rassemble les audits techniques du projet PERMATEL.

## Postgresql Audit

Audit de l'implémentation et de la configuration PostgreSQL (modèles SQLAlchemy, migrations Alembic, pooling, isolation multi-tenant). Constats classés du plus au moins sévère.

### 1. Bug de FK confirmé — `demandes_plannings.agent_concerne_id` / `agent_remplacant_id` ✅ RÉSOLU
**Fichier** : `backend/migrations/versions/c5e10bf50c26_use_varchar_for_enums.py:101`

> Correctif : migration `f1a4c9e6b2d7_fix_demandes_plannings_agent_fk.py` — nullifie les références orphelines puis recrée la FK vers `agents_securite.id`. Le modèle ORM était déjà correct.

En base, la contrainte FK de ces deux colonnes pointe vers `users(id)` (dernière migration à les toucher, confirmé en parcourant tout le graphe de migrations jusqu'à la tête unique `a7fa67a8b0be`), alors que le modèle ORM déclare `ForeignKey('agents_securite.id')` et une relation `agent_concerne = relationship("AgentSecurite", ...)`.

**Scénario de défaillance** : `users.id` et `agents_securite.id` sont tous deux des entiers auto-incrémentés à partir de 1. Une `DemandePlanning` référençant l'agent id=3 passe la contrainte FK tant qu'un *utilisateur* d'id=3 existe — sans jamais valider réellement contre `agents_securite`. Si un agent est supprimé, les lignes `DemandePlanning` conservent une référence pendante que la base considère valide (pointant vers un utilisateur sans rapport) ; un id d'agent d'un autre tenant peut être substitué sans que rien ne l'empêche, cassant silencieusement l'isolation tenant et l'intégrité référentielle que cette colonne est censée garantir.

### 2. Incohérence d'isolation — `tenant_id` nullable sur `clients`/`sites` ✅ RÉSOLU
**Fichier** : `backend/app/models/client.py:32`

> Correctif : migration `a3178519ad55_tenant_id_not_null_clients_sites.py` (garde-fou : avorte si des lignes NULL existent) + modèles `client.py`/`site.py` passés en `nullable=False`.

`clients.tenant_id` et `sites.tenant_id` sont nullable, contrairement à toutes les autres tables tenant-scopées (`demandes`, `interactions`, `fichiers`, `agents_securite`, `emails`, `notifications`, `sla_policies` sont toutes `NOT NULL`).

**Scénario de défaillance** : un chemin d'insertion futur qui oublie de renseigner `tenant_id` (import en masse, bug de route, backfill défectueux) crée un client/site avec `tenant_id=NULL`. Les FK composites depuis `sites`/`demandes` vers `clients` exigent que `(tenant_id, client_id)` corresponde, donc un client à tenant NULL ne peut jamais être référencé légitimement — mais rien ne bloque son écriture, et toute requête de reporting/admin sans filtre tenant explicite (agrégat, jointure malencontreuse, futur écran superadmin) l'exposera across tenants, sans garde-fou applicatif puisque le reste du code suppose `tenant_id` toujours renseigné.

### 3. FK manquantes — `sla_policies.client_id`, `prise_de_service.client_id/site_id`, `emails.demande_id` ✅ RÉSOLU
**Fichier** : `backend/app/models/sla.py:27`

> Correctif : migration `0cf7c58db304_missing_composite_fks_sla_prises_emails.py` (dégrade les références orphelines à NULL sur colonnes nullables, avorte sur `prises_de_service.client_id` NOT NULL) + `ForeignKeyConstraint` ajoutées aux modèles `sla.py`, `prise_de_service.py`, `email.py`.

Ces colonnes sont de simples entiers sans aucune clé étrangère — ni même vers la table locale, encore moins selon le motif de FK composite tenant-scopée utilisé partout ailleurs dans ce schéma.

**Scénario de défaillance** : un admin de tenant modifiant les politiques SLA (ou le code de seeding/backfill) peut fixer `client_id` sur un client d'un autre tenant, ou sur un id inexistant — la base l'accepte silencieusement, aucune contrainte n'existe. La logique de spécificité dans `app/services/sla.py::resolve_policy` appliquerait alors les cibles SLA d'un autre tenant à l'échéance d'une demande, ou ne correspondrait simplement jamais (faute de frappe sur l'id) et retomberait silencieusement sur une politique moins spécifique sans qu'aucune erreur ne remonte.

### 4. Fiabilité opérationnelle — migrations concurrentes au démarrage ✅ RÉSOLU
**Fichier** : `backend/app/__init__.py:66`

> Correctif : verrou advisory Postgres (`pg_advisory_lock`/`unlock`) autour de tout le bloc auto-init (création schéma/seed ou migration), sérialisant les workers concurrents — un seul effectue le travail, les autres attendent puis constatent la base déjà à jour. No-op sous SQLite (tests).

Le bloc auto-migration/seed de `create_app()` s'exécute à chaque process qui importe la factory, mais la production exécute déjà `flask db upgrade heads` + `flask seed` une fois dans `entrypoint.sh` avant de démarrer Gunicorn avec 3 workers — chacun de ces 3 workers rappelle `create_app()` et, `AUTO_MIGRATE` valant `true` par défaut, relance `upgrade(revision='heads')` en concurrence.

**Scénario de défaillance** : lors d'un déploiement ou d'un redémarrage de conteneur, jusqu'à 3 workers Gunicorn démarrent en parallèle et appellent chacun indépendamment `flask_migrate.upgrade(revision='heads')` sur la même instance Postgres à quelques millisecondes d'intervalle. Les versions plus anciennes d'Alembic/Flask-Migrate ne posent pas de verrou consultatif autour de cette opération, donc du DDL concurrent sur la même ligne `alembic_version` peut produire des erreurs de lock-wait, une application partielle du DDL, ou un worker qui crashe au démarrage et redémarre dans la même course — transformant un déploiement ordinaire en échec de démarrage intermittent.

### 5. Absence de tuning du pool de connexions ✅ RÉSOLU
**Fichier** : `backend/app/config.py:62`

> Correctif : `SQLALCHEMY_ENGINE_OPTIONS` (`pool_pre_ping`, `pool_recycle=1800s`, `pool_size=5`, `max_overflow=10`, `pool_timeout=30s`), tous configurables via variables d'env. `TestingConfig` (SQLite `:memory:`) explicitement vidé (`{}`) — ces options QueuePool ne s'appliquent pas au `SingletonThreadPool` de SQLite.

Aucune option `SQLALCHEMY_ENGINE_OPTIONS` (`pool_size`, `max_overflow`, `pool_recycle`, `pool_pre_ping`) n'est configurée, et aucun pooler (PgBouncer) ne se trouve devant Postgres — chacun des 3 workers Gunicorn obtient le pool par défaut de Flask-SQLAlchemy (5 + 10 overflow).

**Scénario de défaillance** : à mesure que le nombre de tenants croît et que `GUNICORN_WORKERS` est augmenté pour la charge, les connexions grimpent vers le `max_connections=100` par défaut de Postgres, sans `pool_recycle` configuré — une connexion inactive qui dépasse un timeout firewall/NAT ou un timeout Postgres échoue au prochain usage avec « server closed the connection unexpectedly » au lieu d'être recyclée silencieusement (pas de `pool_pre_ping` non plus). Il n'y a pas non plus de `statement_timeout` par requête, donc une requête de reporting lente d'un tenant peut retenir une connexion (et des ressources de verrouillage) indéfiniment, affamant le pool partagé pour tous les autres tenants de la même base partagée.

### 6. Index redondants vs. index composites manquants ✅ RÉSOLU
**Fichier** : `backend/app/models/client.py:19`

> Correctif : migration `b4d8e1f3a5c9_index_cleanup_redundant_and_composite.py` — supprime `ix_clients_code_client`, `ix_sites_code_site`, `ix_agents_securite_matricule` (déjà couverts par les contraintes uniques composites) et ajoute `ix_demandes_tenant_statut_created (tenant_id, statut, created_at)`. Modèles (`client.py`, `site.py`, `agent_securite.py`, `demande.py`) alignés.

Les tables tenant-scopées indexent `tenant_id` et la colonne métier de lookup (`code_client`, `code_site`, `matricule`) comme deux index simple-colonne séparés, alors qu'un `UniqueConstraint(tenant_id, code)` existe déjà.

**Scénario de défaillance** : Postgres construit déjà un index unique composite pour `UniqueConstraint('tenant_id', 'code_client')`, qui sert entièrement les lookups filtrés par `tenant_id`+`code_client`. L'`index=True` supplémentaire sur `code_client` seul (motif répété pour `sites.code_site`, `agents_securite.matricule`) est redondant pour tous les patterns de requête tenant-scopés de l'app, mais coûte quand même un B-tree entier à maintenir à chaque INSERT/UPDATE et consomme disque/cache — du pur overhead sans requête qu'il serve uniquement — alors que des tables comme `demandes` (`statut`, `priorite`, `type_demande` tous en index simple-colonne) manquent des index composites du type `(tenant_id, statut, created_at)` qui accéléreraient réellement la requête courante « demandes ouvertes de ce tenant, triées par priorité/date ».

### 7. Isolation multi-tenant sans défense en profondeur (pas de RLS)
**Fichier** : `backend/app/routes/` (tous les blueprints tenant-scopés)

L'isolation tenant est entièrement appliquée au niveau applicatif (filtrage `g.tenant_id` dans chaque route), sans Row-Level Security PostgreSQL en filet de sécurité, malgré une architecture SaaS shared-database/shared-schema.

**Scénario de défaillance** : une seule route qui oublie un `.filter(tenant_id=g.tenant_id)` — facile à manquer puisque le scoping tenant est manuel dans chaque requête à travers une vingtaine de fichiers de routes plutôt qu'automatique — expose ou modifie directement les données d'un autre tenant, sans aucun garde-fou au niveau du moteur de base de données. Les FK composites (ex. `demandes.tenant_id, client_id -> clients.tenant_id, id`) protègent la *liaison* cross-tenant mais n'empêchent en rien un SELECT/UPDATE/DELETE de forme correcte qui aurait simplement omis le prédicat `tenant_id`.

### 8. Incohérences mineures
**Fichier** : `backend/app/models/audit_log.py:25`

`audit_log.old_values`/`new_values` utilisent `JSON` alors que `demande.py` introduit délibérément un wrapper `JSONB_VARIANT` pour le même type de données semi-structurées ; le nom de table `audit_log` (singulier) rompt aussi la convention plurielle utilisée par toutes les autres tables (`clients`, `sites`, `interactions`, `fichiers`, ...).

**Scénario de défaillance** : sévérité faible/cosmétique — sur PostgreSQL, `JSON` stocke une copie texte exacte et n'offre ni indexation ni requêtes de containment (`@>`), donc toute fonctionnalité future nécessitant de rechercher l'historique d'audit par valeur de champ modifié (ex. « trouver tous les changements où l'ancien statut était X ») nécessitera d'abord une migration vers JSONB ; l'incohérence de nommage est une simple charge de maintenance/lisibilité lors de la prise en main du schéma.

## Python Flask Audit

Audit du code applicatif Flask (routes, sécurité, gestion des erreurs, conventions). Constats classés du plus au moins sévère.

### 1. Fuite d'informations — exceptions renvoyées telles quelles au client ✅ RÉSOLU
**Fichier** : `backend/app/routes/demandes.py:464`

Des blocs `except Exception as e` au niveau route renvoient `str(e)` directement dans la réponse JSON, court-circuitant le gestionnaire d'erreurs générique de l'application.

**Scénario de défaillance** : `app/__init__.py:301` définit un `@app.errorhandler(Exception)` global spécifiquement pour éviter de exposer le détail des exceptions aux clients de l'API (« Une erreur interne est survenue. »). Mais `routes/demandes.py:464`, `590` et `725` interceptent chacun largement à l'intérieur de la route elle-même et renvoient `jsonify({"message": ..., "error": str(e)})` avec un code 500 avant que l'exception n'atteigne ce gestionnaire global. Tout échec inattendu lors de la création/mise à jour/suppression d'une demande (erreur du driver DB, `None` inattendu, exception interne d'une librairie) est renvoyé texto à l'appelant authentifié — exposant potentiellement des noms de tables/colonnes, des chemins de fichiers ou des fragments de requête que le gestionnaire global de l'application avait explicitement pour but de masquer.

### 2. Mauvaise configuration CORS — wildcard sur les endpoints métier sensibles ✅ RÉSOLU
**Fichier** : `backend/app/routes/agents_securite.py:36`

6 blueprints (`agents_securite`, `clients`, `contacts`, `demandes`, `interactions`, `sites`) surchargent explicitement CORS avec `origins: "*"`, contournant silencieusement l'allowlist `CORS_ORIGINS` définie globalement dans `app/__init__.py`.

**Scénario de défaillance** : `app/__init__.py:44` initialise `cors.init_app(app, origins=app.config.get('CORS_ORIGINS', ["*"]))`, donc l'application n'est censée accepter des requêtes cross-origin que depuis le(s) origine(s) du frontend configuré(s). Mais ces 6 blueprints — couvrant les données métier centrales (clients, sites, demandes, contacts, agents, interactions) — appellent chacun `CORS(blueprint, resources={r"/api/x/*": {"origins": "*"}})`, ce qui pour Flask-CORS prend le pas pour ces chemins spécifiques et les rouvre à toute origine, quelle que soit la valeur de `CORS_ORIGINS` en production. N'importe quelle page web sur n'importe quel domaine peut émettre des requêtes cross-origin vers ces endpoints (atténué uniquement par le fait que l'attaquant n'a pas le bearer token de l'utilisateur dans son propre contexte JS, mais cela contredit quand même directement l'allowlist configurée de l'application et est incohérent avec les 10 autres blueprints qui s'appuient correctement sur `supports_credentials` + les origines au niveau de l'app).

### 3. Injection de pattern ILIKE dans la recherche de login ✅ RÉSOLU
**Fichier** : `backend/app/routes/auth.py:213`

Le login recherche l'utilisateur via `User.username.ilike(username)` / `User.email.ilike(username)` en utilisant directement la chaîne brute fournie par l'utilisateur comme pattern ILIKE, sans échappement.

**Scénario de défaillance** : ILIKE en SQL traite `%` et `_` dans le pattern comme des jokers. Soumettre `username="%"` transforme la clause WHERE en `username ILIKE '%' OR email ILIKE '%'`, qui matche toutes les lignes utilisateur ; `.first()` renvoie alors un compte arbitraire (celui que le planificateur de requêtes retourne en premier) au lieu d'échouer avec « introuvable ». Bien que `check_password` bloque toujours un contournement complet de l'authentification, cela permet à un attaquant de sonder quel compte arbitraire est matché par différents patterns jokers (ex. `admin_` pour fuzzy-matcher un nom d'utilisateur différent d'un seul caractère) — c'est un cas d'école d'injection de pattern LIKE/ILIKE ; la comparaison littérale devrait échapper `%`/`_` ou utiliser une égalité (`==`/`func.lower()`) plutôt qu'un ilike sur une entrée non assainie.

### 4. Anti-brute-force login dilué par le multi-worker ✅ RÉSOLU
**Fichier** : `backend/app/utils/login_throttle.py:7`

> Correctif : backend Redis partagé entre workers (ZSET fenêtre glissante + clé de verrouillage avec TTL), repli automatique sur le compteur en mémoire si `REDIS_URL` absent/indisponible. Service `redis` ajouté à `docker-compose.yml` (healthcheck, réseau interne) et `redis==5.2.1` à `requirements.txt`.

Le verrouillage anti-brute-force de `/api/auth/login` repose sur un état en mémoire, par processus, alors que l'entrypoint de production démarre Gunicorn avec 3 workers (chacun un processus Python distinct, avec sa propre copie de `_ATTEMPTS`) — un fait reconnu dans le docstring du module lui-même mais jamais corrigé.

**Scénario de défaillance** : les tentatives de connexion d'un attaquant sont réparties par l'OS entre les 3 workers Gunicorn, essentiellement en round-robin. Chaque worker suit indépendamment les échecs par clé (username, ip) et ne verrouille qu'après `LOGIN_MAX_ATTEMPTS` (5 par défaut) échecs *au sein de ce seul worker*. En pratique cela triple à peu près le budget de tentatives effectif avant qu'un worker donné ne verrouille l'attaquant, et même une fois verrouillé sur un worker, les requêtes routées vers les deux autres sont encore évaluées à neuf — affaiblissant la garantie anti-brute-force documentée (section sécurité du README.md) sans aucune protection opérationnelle (ex. compteur partagé sur Redis) actuellement en place.

### 5. `print()` de débogage oublié en production ✅ RÉSOLU
**Fichier** : `backend/app/routes/sites.py:90`

Des instructions `print()` de débogage subsistent dans la route de production `list_sites()`, alors que ce même fichier importe et utilise déjà le module `logging` ailleurs.

**Scénario de défaillance** : la sortie de `print()` va sur stdout, hors du pipeline de logging configuré de l'application (niveaux de log, formatage, agrégation) et n'est pas contrôlable via un niveau de log en production — dans un déploiement Docker/Gunicorn, cela se perd, se mélange aux logs d'accès, ou spam stdout à chaque requête de listing de sites en production, alors que la sortie de débogage équivalente dans les ~19 autres fichiers de routes utilise systématiquement `logger.debug(...)`.

### 6. Canal auxiliaire temporel — énumération de nom d'utilisateur au login ✅ RÉSOLU
**Fichier** : `backend/app/routes/auth.py:216`

Le login renvoie « Identifiants incorrects » rapidement quand le nom d'utilisateur n'existe pas (aucun hash à vérifier) mais prend un temps mesurablement plus long quand l'utilisateur existe et que `check_password` (pbkdf2:sha256, 600 000 itérations) s'exécute — les deux chemins renvoient un corps de réponse identique mais diffèrent en timing.

**Scénario de défaillance** : un attaquant mesurant la latence de réponse sur de nombreuses tentatives de connexion peut distinguer « ce nom d'utilisateur n'existe pas » (rapide, pas de hachage) de « ce nom d'utilisateur existe mais mauvais mot de passe » (lent, une vérification pbkdf2), permettant l'énumération de comptes malgré un message d'erreur générique conçu précisément pour l'empêcher. Une mitigation à temps constant (toujours exécuter une vérification de mot de passe factice quand l'utilisateur n'existe pas) est absente.

### 7. Capture d'exceptions trop large sur le journal d'audit ✅ RÉSOLU
**Fichier** : `backend/app/routes/auth.py:117`

> Correctif : `except Exception` remplacé par `except (TypeError, SQLAlchemyError)`, les seuls modes d'échec réalistes de cette section (kwargs invalides du constructeur `AuditLog`, état de session SQLAlchemy invalide). Les 54 autres occurrences recensées ailleurs dans routes/services/utils/scripts restent une dette technique à traiter au fil de l'eau (hors périmètre de ce correctif ciblé).

L'écrivain du journal d'audit sécurité (`_log_audit`, utilisé pour LOGIN_SUCCESS/FAILED/LOCKED, LOGOUT, SESSION_REVOKED, etc.) avale toutes les exceptions avec un `except Exception` nu — l'une des 55 captures aussi larges recensées à travers routes/services/utils/scripts — contredisant le standard du projet visant des exceptions ciblées.

**Scénario de défaillance** : si l'écriture d'une ligne `AuditLog` échoue un jour (erreur DB transitoire, problème de sérialisation du JSON `new_values`, session déjà dans un état de transaction échouée), l'échec est journalisé localement via `auth_logger.error` mais la route appelante continue comme si l'entrée d'audit avait bien été enregistrée — pour un journal sensible à la sécurité/conformité (le même que `sessions_stats()` utilise pour calculer les KPI d'échecs de connexion et de verrouillages), perdre silencieusement des entrées précisément pendant le type d'événement de stress DB qui coïnciderait aussi avec un incident réel est le pire moment pour que le journal d'audit devienne silencieux.

## Vue Frontend Audit

Audit du code frontend Vue 3 / Vuetify / Pinia (stockage des tokens, surface XSS, isolation multi-tenant côté client, couverture de tests). Constats classés du plus au moins sévère.

### 1. Tokens JWT (access + refresh) persistés dans le localStorage
**Fichier** : `frontend/src/store/auth.js:264`

Le store Pinia `auth` déclare `persist: { paths: ["user", "accessToken", "refreshToken", ...] }` via `pinia-plugin-persistedstate`, dont le moteur de stockage par défaut est le `localStorage` du navigateur.

**Scénario de défaillance** : `accessToken` et surtout `refreshToken` (durée de vie plus longue, `JWT_REFRESH_TOKEN_EXPIRES_DAYS`) sont écrits en clair dans `localStorage` sous la clé du store (`auth`). N'importe quel XSS sur la page — y compris via une dépendance tierce compromise ou une regression future sur l'un des trois `v-html` de l'app — peut lire `localStorage` en JavaScript et exfiltrer ces deux tokens, permettant à l'attaquant de rejouer indéfiniment les requêtes API en tant que l'utilisateur, y compris après fermeture de l'onglet. C'est l'inverse du modèle recommandé (cookies `HttpOnly` + `Secure` + `SameSite`, inaccessibles au JavaScript) ; ici, un seul défaut XSS ailleurs dans l'app suffit à transformer une simple faille d'injection en vol de session complet et persistant.

### 2. Aucune Content-Security-Policy configurée côté frontend ✅ RÉSOLU
**Fichier** : `frontend/index.html:1`

> Correctif : en-tête CSP ajouté au middleware `permatel-sec` de Traefik (`docker-compose.yml`), cohérent avec les autres en-têtes de sécurité déjà en place (HSTS, frameDeny, nosniff…) — `default-src 'self'`, `object-src 'none'`, `frame-ancestors 'none'`, avec les exceptions nécessaires (`style-src 'unsafe-inline'` pour Vuetify, `fonts.googleapis.com`/`fonts.gstatic.com` pour Google Fonts).

Le document HTML racine ne définit aucune balise `<meta http-equiv="Content-Security-Policy">`, et rien dans la configuration Nginx/Traefik documentée (`README.md` § Déploiement) ne mentionne l'ajout d'un en-tête CSP (seuls HSTS, `frameDeny`, `nosniff`, Referrer/Permissions-Policy sont cités).

**Scénario de défaillance** : l'app utilise `v-html` à 3 endroits (`ChatBox.vue`, `MailBox.vue`, `MailChannel.vue`). Le code actuel les protège correctement (échappement HTML puis DOMPurify pour les deux premiers, `sanitizeEmailHtml`/DOMPurify pour le troisième) — ce n'est donc pas une vulnérabilité active aujourd'hui — mais sans CSP, il n'existe aucun filet de sécurité au niveau du navigateur si une régression future retire l'un de ces appels à DOMPurify, si une nouvelle dépendance introduit son propre `v-html` non protégé, ou si une faille est découverte dans DOMPurify lui-même. Une CSP (`script-src 'self'`, `object-src 'none'`, etc.) transformerait une XSS potentielle future en tentative bloquée plutôt qu'en exécution de script réussie — c'est la couche de défense en profondeur qui manque derrière le remède ponctuel déjà en place.

### 3. État d'authentification persistant non namespacé par tenant/utilisateur
**Fichier** : `frontend/src/store/auth.js:264`

La clé de stockage de `pinia-plugin-persistedstate` correspond par défaut à l'id du store (`auth`), sans préfixe par utilisateur ou tenant, malgré une architecture multi-tenant où l'app bascule explicitement de contexte (`switchTenant`, `selectTenant`).

**Scénario de défaillance** : sur un poste partagé (situation plausible pour des permanenciers en rotation d'équipe) où un utilisateur ne se déconnecte pas proprement (fermeture d'onglet plutôt que `logout()`), les tokens et l'état tenant de la session précédente restent dans le même emplacement `localStorage["auth"]` et seraient réutilisés par le prochain utilisateur du même navigateur tant qu'un `logout()` explicite (qui appelle `$reset()`) n'a pas eu lieu — aucun mécanisme ne détecte automatiquement un changement d'utilisateur sur la machine pour purger l'état résiduel.

### 4. Clés `localStorage` métier non namespacées, partagées entre utilisateurs
**Fichier** : `frontend/src/composables/useIdleLogout.js:16`

`useIdleLogout` (clé `permatel_idle_ping`, synchronisation d'activité inter-onglets) et `Menue.vue` (clé `permatel_drawer_collapsed`, préférence UI) écrivent directement dans `localStorage` avec des clés globales fixes, sans préfixe par utilisateur/tenant.

**Scénario de défaillance** : sévérité faible — sur un poste partagé entre deux comptes utilisateur, la préférence d'affichage du menu (repliée/dépliée) ou le signal d'activité d'auto-déconnexion d'un utilisateur affecte silencieusement l'expérience du suivant sur le même navigateur. Impact mineur (pas de fuite de données sensibles) mais contraire au principe de namespacing par utilisateur/tenant attendu dans une architecture SaaS multi-tenant, et source de bugs difficiles à reproduire (« mon menu s'est replié tout seul »).

### 5. Absence totale d'infrastructure de tests automatisés
**Fichier** : `frontend/package.json`

Aucun framework de test n'est configuré : ni Vitest, ni Playwright, ni `@vue/test-utils` dans les dépendances, et aucun fichier `*.spec.js`/`*.test.js` dans `frontend/src`.

**Scénario de défaillance** : contrairement au backend (160+ tests pytest couvrant l'essentiel des routes), le frontend ne dispose d'aucun filet de sécurité automatisé — ni tests unitaires sur les composables critiques (`useIdleLogout`, la logique de refresh token dans `interceptor.js`), ni tests de composants sur les primitives partagées, ni E2E sur les parcours clés (login, sélection de tenant, création d'une demande). Toute régression sur ces flux (ex. une future modification de l'intercepteur Axios cassant silencieusement le refresh automatique, ou un changement de route cassant une garde RBAC) ne serait détectée qu'en test manuel ou en production.

## Remédiation — Suite de tests backend (pytest)

En corrigeant les constats P0/P1/P2 ci-dessus (`tenant_id` NOT NULL, RBAC, etc.), la suite pytest s'est retrouvée en grande partie décorrélée de l'état réel de l'API — les routes avaient évolué (pagination, contrats de payload, enums métier) sans que les tests suivent. Remise à niveau complète : **93 → 172 tests verts sur 172** (0 échec, 0 erreur ; état initial : 93 passants / 67 échecs / 11 erreurs).

### Corrections mécaniques (tests alignés sur le comportement réel, aucun changement d'API)
- **RBAC/fixtures** : `test_clients.py`, `test_sites.py`, `test_contacts.py`, `test_users.py`, `test_demandes.py` utilisaient tous `auth_headers` (rôle PERMANENCIER) même sur des routes `@role_required(MANAGER/ADMIN)` ou `ADMIN` seul → 403 systématique. Ajout de `auth_headers_manager`/`auth_headers_admin` (+ `tokens_manager`/`tokens_admin`) dans `conftest.py` et bascule des tests concernés. Piège découvert au passage : le super-admin global (ADMIN) n'est **jamais** auto-sélectionné sur un tenant au login (même avec un seul tenant accessible, contrairement à un utilisateur standard) — `tokens_admin` doit explicitement appeler `/api/auth/select-tenant` pour obtenir un token avec `tid`.
- **Format de pagination** : `GET /api/clients|sites|contacts|users` renvoient désormais une enveloppe paginée (`{"clients": [...], "total":, "page":, ...}`) plutôt qu'une liste brute — tests mis à jour en conséquence.
- **Contraintes de modèle** : `contacts.adresse/ville/type/telephone/email` NOT NULL + `CheckConstraint` XOR `tenant_id`/`partner_id` non satisfaites par plusieurs fixtures de test construisant des `Contact(...)` a minima.
- **Champs de modèle renommés/supprimés** : `Site.responsable_site` n'existe plus (remplacé par `contact_principal_id`/relation `contact_principal`).
- **Routes disparues** : `/api/contacts/client/<id>` et `/api/contacts/site/<id>` remplacées par `GET /api/contacts?client_id=`/`?site_id=`.
- **Enums métier renommées** : les valeurs de test `nature_anomalie="defaut_materiel"` et `type_commande="licence"` n'existent plus dans les enums actuels (`NatureAnomalie`, `TypeCommande` — ce dernier couvre des missions de sécurité : gardiennage/surveillance_mobile/rondes/intervention, pas des achats logiciels). Scénarios de test réécrits dans le domaine métier réel.

### Vrais bugs applicatifs découverts et corrigés en écrivant/réparant les tests
1. **`GET /api/clients` — défaut de filtre `status` incohérent** (`routes/clients.py`) : défaut `''` (aucun filtre, retourne actifs + inactifs) alors que `list_sites()` et le contrat documenté («liste uniquement les clients actifs») attendent `'true'` par défaut. Corrigé pour aligner sur `sites.py` ; sans impact frontend (`ClientsView.vue` envoie toujours un `status` explicite).
2. **`_parse_user_request` (`routes/users.py`)** : `request.content_type.startswith(...)` plante en `AttributeError` (→ 500) quand `content_type` est `None` (body non-JSON sans en-tête). Corrigé (`(request.content_type or "").startswith(...)`).
3. **`tenant_ids` sur `POST`/`PUT /api/users`** : les UUID de tenant reçus en JSON (donc des `str`) étaient passés tels quels à `Tenant.id.in_(tenant_ids)` sur une colonne `UUID(as_uuid=True)`, qui attend des objets `uuid.UUID` pour le binding SQLAlchemy → `AttributeError: 'str' object has no attribute 'hex'` (jamais exercé avant faute de test). Ajout d'un helper `_parse_tenant_ids()` (conversion + 400 propre si UUID malformé) dans `create_user` et `update_user`.
4. **`create_contact` (`routes/contacts.py`) n'importait aucune validation de champs requis** : un `nom`/`prenom`/`adresse`/... manquant remontait en 500 (IntegrityError NOT NULL brute) au lieu d'un 400 propre. Ajout du même motif `required_fields` que `clients.py`/`sites.py`.
5. **`create_contact` (branche `type='Client'`) ne validait pas que les `client_ids`/`site_ids` fournis existaient réellement** — un ID invalide était silencieusement ignoré (`.filter(...).all()` renvoie juste moins de résultats) au lieu d'échouer, contrairement à `update_contact` qui fait déjà cette vérification (`len(...) != len(set(...))` → 422). Aligné les deux routes.

## Audit PR Sécurité & Performance (skill `pr-security-performance-auditor`)

Audit de l'ensemble des changements de cette session (P0/P1/P2 + remise à niveau de la suite de tests) avant merge, selon le gate strict du skill (zéro tolérance High/Critical, couverture 90%, complexité ≤ 10-14, isolation multi-tenant).

**Statut : 🟢 APPROVED** — Couverture estimée : 53% globale projet / ~58-65% sur les modules touchés (cible : 90%).

### Résumé
| Catégorie | Statut | Constat |
| :--- | :---: | :--- |
| 🔤 Encodage (UTF-8) | Pass | `requirements.txt` : ASCII, LF, aucun octet nul. |
| 🔐 Secrets & Auth | Pass | Politique mot de passe inchangée (12 caractères via `password_error()`), `set_password`/PBKDF2 non touché. Nouveau : hash factice à temps constant contre l'énumération par timing sur `login()`. Aucun secret dans le diff. |
| 🏢 Multi-tenant RBAC | Pass | Aucun `tenant_id`/`role`/`is_active` accepté sans validation depuis un payload — `create_user` rejette explicitement `role=ADMIN` (403), `_parse_tenant_ids` valide chaque UUID de tenant avant usage. CORS wildcard (`origins:"*"`) retiré de 6 blueprints, désormais `supports_credentials=True` cohérent avec l'allowlist `CORS_ORIGINS`. |
| 💉 OWASP & Injections | Pass | `ilike()` de `login()` (risque d'injection de joker `%`/`_`) remplacé par une comparaison exacte `func.lower(...) ==`. Aucun SQL brut ajouté. Les réponses d'erreur ne fuient plus `str(e)`/stack traces (`demandes.py` journalise côté serveur via `logger.exception`/`logger.warning` et renvoie un message générique). |
| ⚡ Performance (N+1) | Pass | `_parse_tenant_ids()` + `Tenant.id.in_(...)`/`Client.id.in_(...)`/`Site.id.in_(...)` : requêtes groupées, aucun lookup unitaire introduit. Nouvel index composite `ix_demandes_tenant_statut_created` ; 3 index simple-colonne redondants supprimés. |
| 🧩 Qualité & Complexité | Pass (1 avertissement) | Aucune fonction ne dépasse le seuil bloquant de 15. `create_app()` atteint 4 niveaux d'imbrication après l'ajout du verrou advisory — signalé en avertissement, pas bloquant. |

### 🔴 BLOCKERS
Aucun.

### 🟠 AVERTISSEMENTS
1. **Imbrication dans `create_app()`** (4 niveaux) — extraction suggérée en `_run_startup_migrations(app)`/`_apply_migrations_or_seed(app)` pour revenir sous 3 niveaux.
2. **Couverture globale à 53%**, tirée vers le bas par des modules non touchés cette session (`settings.py` 19%, `prestataires.py` 19%, `emails.py` 18%, scripts de seeding 11-19%) — aucune régression sur les fichiers modifiés par ce diff.
3. **Aucun test d'isolation dédié** ajouté dans `test_isolation.py` pour la validation `_parse_tenant_ids`/XOR `type` de contact — couvert par les happy-paths et cas d'ID invalide dans `test_users.py`/`test_contacts.py`, mais pas par un scénario cross-tenant explicite.
