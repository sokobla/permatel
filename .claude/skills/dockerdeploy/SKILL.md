---
name: dockerdeploy
description: Playbook de déploiement Docker (Compose + Traefik TLS) issu du retour d'expérience PERMATEL — pré-vol Git/encodage, build, mise en service, et matrice de dépannage des pannes réellement rencontrées (bake, dépôt imbriqué, UTF-16, provider Docker 1.24, réseau préfixé, TLS options, ACME/sniStrict). À invoquer avant un déploiement, pour préparer un release, ou pour diagnostiquer un échec de déploiement.
---

# dockerdeploy — Déploiement Docker (REX PERMATEL)

Tu es ingénieur DevOps. Quand cette skill est invoquée : exécute le **pré-vol**,
puis le **déploiement**, et en cas d'échec applique la **matrice de dépannage**
(symptôme → cause → correctif) tirée des incidents réels de ce projet.

Architecture cible : `docker-compose.yml` avec **db (interne)**, **backend
Flask/Gunicorn (interne)**, **frontend Nginx (interne)**, **Traefik (edge 80/443,
TLS Let's Encrypt)**. Reverse-proxy activable par profil (`COMPOSE_PROFILES=proxy`).

---

## 1. Pré-vol (AVANT de pousser / déployer) — BLOQUANT

Ces points ont **tous** cassé un déploiement au moins une fois.

1. **Aucun dépôt Git imbriqué / gitlink** (sinon le dossier est vide sur le serveur)
   ```bash
   git ls-files -s | awk '$1==160000{print "GITLINK:",$4}'   # doit être VIDE
   git ls-files | grep -E 'frontend/Dockerfile|frontend/nginx.conf' # doivent apparaître
   ```
   Si `frontend` (ou autre) est un gitlink sans remote → **dé-imbriquer** :
   `git rm --cached <dir> && rm -rf <dir>/.git && git add <dir>`.

2. **Tout est commité** (le serveur ne build que ce qui est dans Git)
   ```bash
   git status --short          # doit être propre avant le déploiement
   ```

3. **Encodage `requirements.txt` = UTF-8/ASCII, LF** (UTF-16 casse pip)
   ```bash
   grep -qP '\x00' backend/requirements.txt && echo "⚠ UTF-16 — réécrire en UTF-8 (heredoc bash, jamais '>' PowerShell)"
   file backend/requirements.txt   # "ASCII text" / "UTF-8"
   ```
   Présence d'un `.gitattributes` : `requirements.txt text eol=lf`, `*.sh text eol=lf`, `Dockerfile text eol=lf`.

4. **`entrypoint.sh` en LF + UTF-8** (un `#!/bin/sh\r` casse le conteneur)
   ```bash
   file backend/entrypoint.sh && ! grep -q $'\r' backend/entrypoint.sh && echo "LF OK"
   ```

5. **Dockerfile explicite** dans chaque service `build:` (`dockerfile: Dockerfile`)
   et **`.dockerignore`** présents (n'excluant pas le Dockerfile).

6. **`.env` racine complet** : tous les `${...}` du compose sont couverts
   ```bash
   { grep -oE '\$\{[A-Z_]+' docker-compose.yml | sed 's/${//'; } | sort -u
   ```
   Secrets **obligatoires** : `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`,
   `SETTINGS_ENCRYPTION_KEY` (+ `DOMAIN`, `ACME_EMAIL` si profil `proxy`).
   ⚠ `SETTINGS_ENCRYPTION_KEY` **stable** (sinon données chiffrées illisibles).

7. **Ne JAMAIS éditer `docker-compose.yml` sur le serveur** → conflits à chaque
   `git pull`. Toute variation d'environnement passe par le `.env`.

---

## 2. Déploiement

```bash
# Dev : pousser un état propre
git add -A && git commit -m "release" && git push

# Serveur
cd /chemin/permatel
git pull
# (si conflit sur docker-compose.yml édité localement : git checkout -- docker-compose.yml)
docker compose up -d --build
docker compose ps
docker compose logs -f traefik backend
```

Au 1er démarrage, l'entrypoint backend attend la DB, applique les migrations
(`flask db upgrade heads`) puis amorce (`flask seed`) — idempotent. Changer le
mot de passe admin : `docker compose exec backend flask superadmin reset-password adm_root@permatel.local`.

### Prérequis TLS (profil proxy)
- DNS **A/AAAA** de `DOMAIN` → IP du serveur.
- Ports **80 ET 443** ouverts (firewall cloud + `ufw allow 80,443/tcp`). Le
  challenge ACME HTTP-01 exige le **port 80**.
- Pour itérer sans rate-limit Let's Encrypt : CA **staging**
  (`--certificatesresolvers.le.acme.caserver=https://acme-staging-v02.api.letsencrypt.org/directory`),
  puis retirer + `docker volume rm <projet>_traefik_letsencrypt`.

---

## 3. Matrice de dépannage (REX — pannes réelles)

| Symptôme (log / navigateur) | Cause | Correctif |
|---|---|---|
| `failed to read dockerfile: open Dockerfile: no such file or directory` (alors que le fichier existe) | Bug du **mode bake** de Compose | `COMPOSE_BAKE=false docker compose up --build` (ou désactiver « Use Compose bake » dans Docker Desktop) ; déclarer `dockerfile: Dockerfile` explicitement |
| Même erreur, mais le fichier est **absent sur le serveur** | Dossier = **dépôt Git imbriqué/gitlink** non récupéré | Dé-imbriquer (cf. §1.1), committer, push, `git pull` |
| `Invalid requirement: 'a\x00l\x00e\x00m...'` au `pip wheel` | `requirements.txt` en **UTF-16** | Réécrire en UTF-8 (heredoc bash) + `.gitattributes` |
| `exec /app/entrypoint.sh: no such file` ou script qui ne démarre pas | `entrypoint.sh` en **CRLF** | Forcer LF (`.gitattributes *.sh text eol=lf`), `chmod +x` dans le Dockerfile |
| Traefik: `client version 1.24 is too old. Minimum supported API version is 1.40` (`providerName=docker`) | Le provider Docker de Traefik ne négocie pas l'API (et **ignore** `DOCKER_API_VERSION`) | Sur le démon : `systemctl edit docker` → `Environment="DOCKER_MIN_API_VERSION=1.24"` → `daemon-reload && restart docker`. (Alternative : upgrader l'image Traefik.) |
| Traefik: `Could not find network named "X"` / *Defaulting to first available* `projet_X` | Compose **préfixe** le réseau du nom de projet | Donner un **nom fixe** au réseau (`networks: X: { name: X }`) pour matcher `--providers.docker.network=X` |
| Traefik: `unknown TLS options: default@file` | Le **provider fichier** ne charge pas `dynamic.yml` (non monté / bind a créé un **répertoire**) | Vérifier `docker compose exec traefik cat /etc/traefik/dynamic.yml` ; sinon retirer les labels `tls.options=default@file` (Traefik garde TLS 1.2/1.3 par défaut) |
| Navigateur: `SSL_ERROR_UNRECOGNIZED_NAME_ALERT` | `sniStrict: true` **+** certificat ACME non émis (pas de routeur pour ce Host) | Mettre `sniStrict: false` (domaine unique) ; corriger d'abord le provider Docker / l'ACME pour que le routeur+cert existent |
| ACME `timeout`/`connection refused` sur le challenge | Port **80 fermé** ou **DNS** ne pointe pas vers le serveur | Ouvrir 80/443, vérifier `dig +short DOMAIN` |
| ACME `too many certificates / rate limited` | Trop d'essais sur le CA **production** | Basculer en **staging**, valider, revenir prod (+ supprimer le volume letsencrypt) |
| `git pull` : *local changes to docker-compose.yml would be overwritten* | Compose **édité sur le serveur** | `git checkout -- docker-compose.yml` (mettre les variations dans `.env`) |
| Backend 500 verbeux / fuite de trace | Pas de handler global / `DEBUG=true` en prod | Handlers globaux (DataError→400, Exception→500 générique) + `FLASK_ENV=production` |

---

## 4. Tâches planifiées (cron)
Exécuter dans le conteneur backend, via `docker exec` (robuste en cron — pas de
dépendance au `.env`/dossier projet), chemin **absolu** vers docker :
```cron
*/5  * * * * /usr/bin/docker exec permatel_backend flask mail-fetch     >> /var/log/permatel/mail-fetch.log     2>&1
*/15 * * * * /usr/bin/docker exec permatel_backend flask sessions-sweep >> /var/log/permatel/sessions-sweep.log 2>&1
```

## 5. Build front & sauvegardes
- Les variables **`VITE_*` sont figées au build** → rebâtir l'image frontend
  pour tout changement (`docker compose up -d --build frontend`).
- **Sauvegarder** : volumes `postgres_data` (BD), `backend_uploads` (PJ chiffrées),
  `traefik_letsencrypt` (certs) ; et **`SETTINGS_ENCRYPTION_KEY`** (gestionnaire
  de secrets — perte = données chiffrées irrécupérables).
  ```bash
  docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup_$(date +%F).sql
  ```

---

## Mode opératoire quand invoquée
1. Lancer le **pré-vol §1** ; corriger tout point rouge avant d'aller plus loin.
2. Procéder au **déploiement §2** (ou guider l'utilisateur).
3. À la moindre erreur, consulter la **matrice §3** : identifier symptôme → cause →
   correctif, l'appliquer, puis revérifier les logs (`docker compose logs traefik backend`).
4. Vérifier l'état final : conteneurs `healthy`, cert émis (`Certificates obtained
   successfully`), `https://DOMAIN` répond, cron en place.
5. Rappeler les **sauvegardes** et la **stabilité de `SETTINGS_ENCRYPTION_KEY`**.

Ne jamais : committer un `.env`, laisser un dépôt imbriqué sans remote, un
`requirements.txt` en UTF-16, un `.sh` en CRLF, éditer le compose sur le serveur,
ni exposer db/backend directement (seul Traefik publie 80/443).
