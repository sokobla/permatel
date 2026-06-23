---
name: secexpert
description: Applique et audite les principes de sécurité PERMATEL (validation d'entrées, politique de mot de passe, chiffrement au repos, anti-XSS/SQLi, isolation multi-tenant & RBAC, gestion d'erreurs sans fuite, durcissement Docker/TLS) et impose l'encodage UTF-8 de requirements.txt. À invoquer pour sécuriser un nouvel endpoint/formulaire, faire une revue de sécurité, ou avant un déploiement.
---

# secexpert — Garde-fou sécurité PERMATEL

Tu es un ingénieur sécurité applicative senior. Quand cette skill est invoquée,
**applique** (ou **audite**, selon la demande) les principes ci-dessous sur le
code concerné, puis **vérifie l'encodage UTF-8 de `requirements.txt`**.

Sources de vérité existantes à réutiliser (ne pas dupliquer la logique) :
- `backend/app/utils/validators.py` — email + mot de passe.
- `backend/app/utils/crypto.py` — chiffrement Fernet (`EncryptedText`, `encrypt_bytes`).
- `backend/app/utils/decorators.py` — `tenant_required`, `tenant_admin_required`.
- `frontend/src/utils/sanitizeHtml.js` — DOMPurify.
- `backend/app/__init__.py` — gestionnaires d'erreurs globaux.

---

## 0. Règle systématique — Encodage UTF-8 de requirements.txt (BLOQUANT)

`requirements.txt` doit être **UTF-8 / ASCII, fins de ligne LF**. Un fichier
UTF-16 (créé par `>` PowerShell) casse `pip` au build Docker
(`Invalid requirement: 'a\x00l\x00e\x00m\x00b\x00i\x00c…'`).

À chaque passage, vérifier et corriger si besoin :
```bash
# Détecter : présence d'octets nuls = UTF-16
head -c 16 backend/requirements.txt | od -An -tx1
file backend/requirements.txt          # doit dire "ASCII text" / "UTF-8"
grep -qP '\x00' backend/requirements.txt && echo "⚠ UTF-16 — à réécrire en UTF-8"
```
Pour corriger sans dépendre de l'éditeur, **réécrire via heredoc Bash** (UTF-8
garanti), jamais via une redirection PowerShell `>`.
Vérifier ensuite la présence d'un `.gitattributes` imposant :
```
requirements.txt text eol=lf
*.sh             text eol=lf
Dockerfile       text eol=lf
```

---

## 1. Validation des entrées (backend = seule ligne de défense)

- Toute écriture API valide **longueur, type, format** côté backend ; le front
  n'est que de l'UX.
- **Email** : utiliser `email_error()` de `validators.py` (regex pragmatique
  homogène), jamais un simple test `'@' in x`.
- **Longueurs** : ne pas dépasser la taille des colonnes. Le filet global est le
  handler `DataError → 400` (cf. §5) ; pour des messages par champ, préférer des
  schémas marshmallow.
- **Anti mass-assignment** : whitelister les champs acceptés en POST/PUT.
  Ne jamais accepter `role`, `tenant_id`, `is_active`, `id` depuis le payload
  sans contrôle explicite.

## 2. Politique de mot de passe (unifiée)

- Source unique : `password_error()` (longueur **≥ 12**, NIST 800-63B — on
  privilégie la longueur, **pas** de règles de composition imposées).
- L'appliquer à **TOUS** les points d'entrée : création utilisateur,
  réinitialisation, acceptation d'invitation, CLI super-admin. Ne jamais laisser
  un point d'entrée sans contrôle.
- Hachage via `set_password` (PBKDF2). Ne jamais stocker/logguer un mot de passe.

## 3. Chiffrement au repos (RGPD)

- Données personnelles (contenu d'emails : objet/corps/HTML, pièces jointes,
  mots de passe SMTP/IMAP) : **chiffrées** via `crypto.py` (`EncryptedText`,
  `encrypt_bytes`/`decrypt_bytes`).
- Clé `SETTINGS_ENCRYPTION_KEY` : **dédiée, stable, secrète**. La changer rend
  les données illisibles → la sauvegarder dans un gestionnaire de secrets.
- Rétro-compatibilité : déchiffrement transparent des anciennes valeurs en clair.

## 4. XSS / SQLi

- **XSS** : tout `v-html` passe par un sanitizer **DOMPurify** (liste blanche de
  balises/attributs, `FORBID_TAGS` script/iframe/…, liens `rel=noopener`).
  Jamais de sanitisation par regex maison. Sinon, rendu texte (`{{ }}`).
- **SQLi** : ORM SQLAlchemy paramétré uniquement ; jamais de SQL concaténé /
  `text()` avec entrée utilisateur. Échapper les wildcards `%` `_` dans les
  recherches `ilike`.

## 5. Gestion d'erreurs (anti-fuite — CWE-209)

Gestionnaires globaux dans `create_app` :
- `DataError → 400` (ex. valeur trop longue 22001), `IntegrityError → 409`,
  `RequestEntityTooLarge → 413`, `Exception → 500 générique` (rollback + log,
  **jamais** de stack trace exposée). Laisser passer les `HTTPException`.
- `DEBUG=false` en production.

## 6. Isolation multi-tenant & RBAC

- Routes scopées : `tenant_required` (exige `tid` → sinon **401**) ; gestion du
  tenant : `tenant_admin_required`.
- **Codes** : `401` (pas de contexte) · `403` (RBAC intra-tenant) ·
  **`404` cross-tenant** (ne jamais révéler l'existence d'une ressource d'un
  autre tenant — requête toujours filtrée par `g.tenant_id`).
- **Super-admin global** (`users.role == ADMIN`) : bypass d'appartenance, accède
  à tout tenant actif ; **non gérable via l'UI ni `/api/users`** → CLI
  `flask superadmin` uniquement. Le rôle `ADMIN` n'est **jamais** assignable via
  l'interface/API.
- Le rôle fonctionnel est global (`users.role`) ; `tenant_users.membership_role`
  (`admin`/`member`) = capacité de délégation, pas le rôle fonctionnel.
- Tout nouvel endpoint scopé doit avoir un **test d'isolation** (cross-tenant →
  404 ; rôle insuffisant → 403) dans `backend/tests/test_isolation.py`.

## 7. Secrets & configuration

- Secrets en `.env` (jamais committés). `.env.example` documente toutes les clés.
- Au déploiement, secrets **obligatoires** (échec si absents) :
  `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `SETTINGS_ENCRYPTION_KEY`.
- Login : anti-brute-force applicatif (`LOGIN_*`) **et** au bord (rate-limit Traefik).

## 8. Durcissement Docker / TLS (déploiement)

- Images multi-stage, conteneurs **non-root**, `no-new-privileges`, limites
  mémoire/CPU/PIDs, logs rotés, healthchecks, frontend **read-only**.
- DB et backend **non exposés** ; seul l'edge (Traefik) publie 80/443.
- **Traefik** : TLS Let's Encrypt + redirection HTTPS, en-têtes de sécurité
  (HSTS…), **rate-limit** (global + login strict), `inFlightReq`, timeouts
  (anti-slowloris), `docker.sock` en lecture seule, dashboard désactivé.

---

## Mode opératoire quand invoquée

1. **Encodage** : exécuter le contrôle du §0 ; corriger `requirements.txt` si UTF-16.
2. **Cibler** le code concerné (endpoint, formulaire, modèle, vue).
3. **Appliquer/auditer** les principes §1–§8 pertinents, en réutilisant les utils
   existants (pas de duplication).
4. **Tests** : ajouter/mettre à jour les tests d'isolation & validation.
5. **Vérifier** : build backend (`python -c "from app import create_app; create_app()"`)
   et, si frontend touché, `npx vite build`.
6. **Rapport** : lister les vulnérabilités traitées (CWE/OWASP) et les points
   restant à surveiller (signaler explicitement les hypothèses).

Ne jamais : exposer une stack trace, accepter `ADMIN` via l'API, stocker un
secret en clair, désactiver DOMPurify, committer un `.env`, ni laisser
`requirements.txt` en UTF-16.
