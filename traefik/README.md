# Traefik — reverse-proxy partagé du serveur

Ce dossier est un stack Docker Compose **indépendant** de PERMATEL. Il tourne
en permanence sur le serveur et sert de point d'entrée unique (ports 80/443,
TLS Let's Encrypt) pour PERMATEL et pour toute autre application déployée sur
la même machine. Aucune application ne démarre "son propre Traefik" — chacune
se contente de rejoindre le réseau Docker partagé `traefik_public` et de
porter ses labels `traefik.*` sur son conteneur exposé.

## Démarrage (une seule fois par serveur)

```bash
docker network create traefik_public
cd traefik/
cp .env.example .env      # renseigner ACME_EMAIL
docker compose up -d
docker compose ps         # doit être "healthy"
```

Le réseau `traefik_public` a un nom fixe et n'est jamais recréé par les stacks
applicatifs (ils le déclarent `external: true`) : si vous le supprimez par
erreur, recréez-le puis relancez `docker compose up -d` sur chaque appli pour
qu'elle s'y rattache à nouveau.

## Brancher une application existante (ex. PERMATEL)

Dans le `docker-compose.yml` de l'appli, le conteneur exposé publiquement
(généralement le frontend/reverse-proxy Nginx de l'appli) doit :

1. Rejoindre `traefik_public` **en plus** de son propre réseau interne :
   ```yaml
   networks:
     - mon_appli_internal   # DB/backend — jamais exposé à Traefik
     - traefik_public       # déclaré external: true, voir ci-dessous
   ```
2. Porter les labels de routage :
   ```yaml
   labels:
     - "traefik.enable=true"
     - "traefik.http.routers.mon-appli.rule=Host(`mon-appli.exemple.com`)"
     - "traefik.http.routers.mon-appli.entrypoints=websecure"
     - "traefik.http.routers.mon-appli.tls=true"
     - "traefik.http.routers.mon-appli.tls.certresolver=le"
     - "traefik.http.services.mon-appli.loadbalancer.server.port=<port interne du conteneur>"
   ```
3. Déclarer le réseau externe en bas du fichier :
   ```yaml
   networks:
     mon_appli_internal:
       driver: bridge
     traefik_public:
       external: true
   ```

Chaque domaine (`Host(...)`) doit pointer (DNS A/AAAA) vers l'IP du serveur
**avant** le premier démarrage, sinon le challenge ACME HTTP-01 échoue.

## Fichiers

- `docker-compose.yml` — le service Traefik lui-même (image, entrypoints 80/443, résolveur ACME).
- `dynamic.yml` — configuration statique additionnelle (durcissement TLS : version min, suites de chiffrement). Monté en lecture seule, rechargé à chaud (`--providers.file.watch=true`).
- `.env` (non versionné) — `ACME_EMAIL`.

## Notes

- **`sniStrict`** (`dynamic.yml`) est laissé à `false` : avec plusieurs domaines
  derrière ce Traefik, ne l'activer qu'une fois que **tous** ont un certificat
  ACME émis — sinon un domaine sans certificat encore prêt renvoie
  `SSL_ERROR_UNRECOGNIZED_NAME_ALERT` au lieu du fallback attendu.
- **Un middleware par appli** : les en-têtes de sécurité et rate-limits (voir
  `permatel/docker-compose.yml` → labels `permatel-sec`, `permatel-ratelimit`,
  etc.) sont définis par chaque application sur ses propres labels, pas ici de
  façon centralisée. C'est volontaire (isolation entre applis) mais duplique
  la configuration si vous ajoutez beaucoup d'applications — envisager un
  middleware commun via `dynamic.yml` (`http.middlewares` du provider fichier)
  si la duplication devient pénible.
- **Un seul `docker.sock` monté, en lecture seule**, par cette stack — ne
  montez jamais le socket Docker dans un service applicatif : seul Traefik en
  a besoin pour découvrir les conteneurs labellisés.
