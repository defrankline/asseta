# Live deployment: https://asseta.co.tz on the shared server

Audience: the platform owner deploying Asseta to the shared Linux server that already runs bnbtracker the same way.
Related: [operating runbook](operating-runbook.md) (services, upgrades, backup/restore, incidents),
[security](security.md), [GPS commissioning](gps-hardware.md).

## 1. How it fits on the shared server

| Piece | Where | Notes |
|---|---|---|
| Code | `/home/asseta` (git clone of `main`) | `scripts/deploy-live.sh` fetches `origin/main` and accepts incoming changes |
| Secrets | `/home/asseta/.env.production` (mode 600) | written by `scripts/generate-production-secrets.sh`; never in git or in backups |
| Console | `/var/www/html/asseta.co.tz/releases/<tag>` + `current` symlink | static files served by host nginx; the 2 newest releases are kept |
| nginx site | `/etc/nginx/sites-available/asseta.co.tz.conf` (+ `sites-enabled` link), or `/etc/nginx/conf.d/asseta.co.tz.conf` | rendered from `deploy/nginx/host-{http-only,ssl}.conf.template`; other sites' files are never touched |
| Certificates | `/etc/letsencrypt/live/asseta.co.tz/` | host certbot, webroot `/var/www/html/asseta.co.tz/certbot` |
| Docker stack | `compose.prod.yaml`, project `asseta`, images `asseta/*` | volumes `asseta_pgdata`, `asseta_kafkadata`, `asseta_miniodata`, `asseta_traccardata`, `asseta_redisdata` |
| Deploy state | `/home/asseta/.deploy/state.env` | current/previous image tag, trusted proxy address (not secret) |
| Backups | `/home/asseta/backups/<UTC timestamp>/` | `scripts/backup-live.sh`, 7 days kept |

Ports (all `127.0.0.1` only; bnbtracker uses 5010):

| Port | Service | Reached by |
|---|---|---|
| 5020 | API (`/api/`, WebSocket `/api/v1/ws`) | host nginx |
| 5021 | Keycloak (`/auth/`) | host nginx; admin console via SSH tunnel |
| 5022 | MinIO S3 API (presigned evidence GETs `/asseta-evidence/`) | host nginx |
| 5023 | Traccar web UI | SSH tunnel only |
| 5024 | MLflow UI (only with `ENABLE_MLFLOW=1`) | SSH tunnel only |
| 5055 | Traccar OsmAnd device port | `127.0.0.1` by default; `0.0.0.0` only with `TRACCAR_PUBLIC_DEVICE_PORTS=1` (§8) |

Postgres, Redis, Kafka and the MinIO console are not published at all. Public URLs: console
`https://asseta.co.tz`, API `https://asseta.co.tz/api/v1`, OIDC issuer `https://asseta.co.tz/auth/realms/asseta`.

Memory: the stack's limits add up to more than 8 GB, but they are ceilings, not reservations. The idle stack used
about 3.1 GB in the pre-release rehearsal (Keycloak ~600 MB, MLflow ~640 MB, Kafka ~390 MB, API ~260 MB, each
worker 60-220 MB); expect more under load. Check with `docker stats --no-stream` after the first deploy, and leave
room for bnbtracker.

## 2. Prerequisites (once)

* Docker Engine with the Compose v2 plugin (`docker compose version`), nginx and certbot on the host (already there
  for bnbtracker), `git`, `curl`, `rsync` (only for off-host backups).
* The deploying user (for example `asseta`) can run `docker` (member of the `docker` group) and `sudo` (for nginx,
  certbot and `/var/www/html`).
* DNS: an `A` record (and `AAAA` if the server has IPv6) for `asseta.co.tz` pointing at the server. Check with
  `getent hosts asseta.co.tz`. Let's Encrypt fails until it resolves.
* Firewall: 80 and 443 open (they already are for bnbtracker). Nothing else for now.
* At least 10 GB free disk (the deploy checks; `MIN_FREE_DISK_GB`).

## 3. First deploy

1. **Clone with a read-only deploy key** (GitHub → repository → Settings → Deploy keys):
   ```bash
   sudo mkdir -p /home/asseta && sudo chown "$USER": /home/asseta
   ssh-keygen -t ed25519 -f ~/.ssh/asseta_deploy -N "" -C "asseta deploy key"   # add the .pub as a deploy key
   cat >> ~/.ssh/config <<'EOF'
   Host github-asseta
     HostName github.com
     User git
     IdentityFile ~/.ssh/asseta_deploy
     IdentitiesOnly yes
   EOF
   git clone github-asseta:<owner>/asseta.git /home/asseta
   cd /home/asseta
   ```
2. **Generate the secrets** (prints only the key names, never the values):
   ```bash
   scripts/generate-production-secrets.sh          # writes .env.production, mode 600; refuses to overwrite
   ```
3. **Fill in the external values** in `.env.production`: `LETSENCRYPT_EMAIL` (required). Optional now, required
   before you rely on them: SMTP (`ASSETA_EMAIL_*`), NextSMS (`ASSETA_NEXTSMS_*` + `ASSETA_SMS_PROVIDER=nextsms`),
   FCM/APNs (`ASSETA_PUSH_*`). Until set, those channels log to the console and send nothing. Values with spaces
   or `<>` go in double quotes; values containing `$` in single quotes. Keep an encrypted copy of the finished file
   off the server (password manager): it is the only copy of the database and Keycloak secrets.
4. **Deploy:**
   ```bash
   scripts/deploy-live.sh
   ```
   Preflight checks (fails before changing anything): required commands, Docker Compose v2, `.env.production`
   present with no `CHANGE_ME`, free disk, ports 5020-5024 and 5055 not used by anything but this project, and a
   DNS check (warning only). Then it builds the images (`asseta/api:<sha>-<timestamp>`), builds the console into
   a new release directory, installs the HTTP site, obtains the certificate, switches to the HTTPS site, starts
   the data services, runs `migrate`, starts api + workers, waits for `/api/v1/health/ready`, activates the
   console and cleans up. The first run takes 10-20 minutes (image builds, Keycloak's first start and realm
   import).
5. **Create the first platform owner** (production has no demo data and no users):
   ```bash
   scripts/create-platform-owner.sh you@example.com "First" "Last"
   ```
   It prints a temporary password once, to your terminal only. Run it from an interactive SSH session.
6. **Sign in** at https://asseta.co.tz with that e-mail and the temporary password. Keycloak asks for a new
   password and for an authenticator app (TOTP); pass `--no-totp` to the script to skip the second.
7. **Set up backups** (§6) and check §7 (health) once.

## 4. Updating

Push to `main`, then on the server:
```bash
cd /home/asseta && scripts/deploy-live.sh
```
The deploy never runs `docker compose down` and never removes a volume. Data services (Postgres, Keycloak, Kafka,
Redis, MinIO, MLflow) are `up -d`'d, which is a no-op when their configuration is unchanged. Only the app image is
rebuilt. `migrate` runs before the new api and workers replace the old ones, so a failed migration leaves the
running version untouched. The console switches to the new release only after the API is ready. Back up first
(`scripts/backup-live.sh`) before a release with migrations.

Configuration-only change (for example SMTP credentials): edit `.env.production` and run `scripts/deploy-live.sh`
again. Compose recreates only the services whose environment changed.

## 5. Rolling back

```bash
scripts/deploy-live.sh status            # current and previous tag
scripts/deploy-live.sh rollback          # api + workers + console back to the previous tag
scripts/deploy-live.sh rollback <tag>    # a specific kept tag (docker image ls asseta/api)
```
The 2 newest app images and console releases are kept. A rollback does **not** revert database migrations. Roll
back only between releases without new migrations. Otherwise restore the pre-upgrade backup (§6,
[runbook §4](operating-runbook.md#4-upgrades-and-migrations)).

Console only (for example a broken UI build with a good API):
```bash
ls -1t /var/www/html/asseta.co.tz/releases/
sudo ln -sfn /var/www/html/asseta.co.tz/releases/<tag> /var/www/html/asseta.co.tz/current
```

## 6. Backups

```bash
scripts/backup-live.sh                   # -> /home/asseta/backups/<UTC timestamp>/
```
It contains `pg_dump -Fc` of `asseta`, `keycloak` and `mlflow`, the alembic version, a Keycloak realm config
record, and a MinIO mirror of `asseta-evidence` and `asseta-mlflow` taken after the dumps. A `MANIFEST` and
`SHA256SUMS` are included. These are the same commands the backup/restore drill verified
([runbook §6](operating-runbook.md#6-backup-and-restore-production-procedure)). Backups older than
`BACKUP_RETENTION_DAYS` (7) are deleted. Set `BACKUP_REMOTE=user@host:/path` to rsync each backup off the
server, and make the target encrypted storage.

Daily at 02:15 (`crontab -e` as the deploying user):
```cron
15 2 * * * cd /home/asseta && scripts/backup-live.sh >> /home/asseta/backups/backup.log 2>&1
```

Restore (destructive; asks twice and offers a safety backup first):
```bash
scripts/restore-live.sh /home/asseta/backups/<UTC timestamp>
```
It stops the writers, recreates and restores the three databases, mirrors the objects back, then starts Keycloak,
`migrate`, api and workers. Traccar starts last. Then verify as in
[runbook §6.2](operating-runbook.md#62-restore-order-matters) step 5.

## 7. Health and logs

```bash
scripts/deploy-live.sh status                                   # tag, containers, readiness
curl -s http://127.0.0.1:5020/api/v1/health/ready               # every dependency "ok"
curl -sI https://asseta.co.tz/ | head -n 1
curl -s https://asseta.co.tz/auth/realms/asseta/.well-known/openid-configuration | grep -o '"issuer":"[^"]*"'
scripts/compose-live.sh ps
scripts/compose-live.sh logs -f --tail=200 api                  # also: keycloak, notification-worker, traccar ...
sudo tail -f /var/log/nginx/error.log                           # 429s are logged as "limiting requests"
```
`scripts/compose-live.sh` is `docker compose` with this deployment's files, project, env and image tag. Use it
for every manual command so nothing drifts. It refuses `down -v`.

Operator UIs, never public, through an SSH tunnel from your laptop:
```bash
ssh -L 5021:127.0.0.1:5021 -L 5023:127.0.0.1:5023 -L 5024:127.0.0.1:5024 <user>@<server>
# Keycloak admin console: http://localhost:5021/auth/admin/  (user KEYCLOAK_ADMIN_USER from .env.production)
# Traccar: http://localhost:5023                            MLflow: http://localhost:5024
```
`/auth/admin/` and the `master` realm are blocked on the public site. To allow fixed office IPs instead, set
`KEYCLOAK_ADMIN_ALLOW_IPS="203.0.113.10"` and deploy again. Keycloak 26 marks the bootstrap admin as temporary.
After the first sign-in to the admin console, create a permanent admin in the `master` realm. If you then
delete the bootstrap admin, update `KEYCLOAK_ADMIN_USER`/`KEYCLOAK_ADMIN_PASSWORD` to the new admin, because
`create-platform-owner.sh` and the backup's realm export use them.

**Traccar UI first use:** the first account registered in Traccar becomes its administrator. Open the tunnel and
register your admin account right after the first deploy, then disable registration (Settings → Server →
uncheck *Registration*).

Keycloak e-mails (password reset, verify e-mail) are configured in the admin console (realm `asseta` → Realm
settings → Email), separately from the app's SMTP variables.

### Keycloak admin console (through an SSH tunnel)

The admin console and the `master` realm are blocked publicly. Run once after the first deploy:
```bash
scripts/keycloak-admin-tunnel.sh          # serves the master realm at http://localhost:5021/auth
```
then from your computer `ssh -L 5021:127.0.0.1:5021 root@<server>` and open http://localhost:5021/auth/admin/.
Without it the console shows "Timeout when waiting for 3rd party check iframe message". Sign in with
`KEYCLOAK_ADMIN_USER` / `KEYCLOAK_ADMIN_PASSWORD` from `.env.production`, create a permanent admin in the master
realm (Users → Create user → Credentials → Role mapping: `admin`), sign in as it, then delete the temporary
bootstrap admin.

### MLflow (optional)

Off by default (`ENABLE_MLFLOW=0`) to save ~1.4 GB of RAM on the shared server: model training and governance
keep working and record every run in the database. Set `ENABLE_MLFLOW=1` in `.env.production` and run
`scripts/deploy-live.sh` to start it (UI through the tunnel on 5024); set it back to 0 to stop it again (its
database and bucket are kept). Backups include MLflow only once it has been enabled.

## 8. GPS trackers (when the first device is commissioned)

Traccar's OsmAnd port 5055 is bound to `127.0.0.1` by default. To accept devices from the internet:
1. Set `TRACCAR_PUBLIC_DEVICE_PORTS=1` in `.env.production` and run `scripts/deploy-live.sh`. Traccar then
   publishes 5055 on `0.0.0.0`.
2. Open only that port: `sudo ufw allow 5055/tcp` (or the provider's security group). Docker-published ports
   bypass ufw's default rules on many setups, so also check reachability from outside with `nc -vz <server> 5055`
   and close it again if you turn the flag back off.
3. Other protocols (Teltonika 5027, GT06 5023 inside the container, ...): create `compose.prod.local.yaml`
   (gitignored; the scripts pick it up automatically). Choose a host port that is not 5020-5024:
   ```yaml
   services:
     traccar:
       ports: ["0.0.0.0:5027:5027"]
   ```
   Open that port in the firewall.
4. Production registers each device in Traccar explicitly (`TRACCAR_REGISTER_UNKNOWN=false`, DEC-017). Follow
   [gps-hardware.md](gps-hardware.md).

The Traccar web UI (5023) is never public.

## 9. Push key files

FCM service-account JSON and the APNs `.p8` key are files, not variables. Put them in `/home/asseta/secrets/`
(mode 600, outside git) and mount them in `compose.prod.local.yaml`:
```yaml
services:
  notification-worker:
    volumes:
      - /home/asseta/secrets/fcm.json:/run/secrets/fcm.json:ro
      - /home/asseta/secrets/apns.p8:/run/secrets/apns.p8:ro
```
Then set `ASSETA_PUSH_FCM_SERVICE_ACCOUNT_FILE=/run/secrets/fcm.json`, `ASSETA_PUSH_APNS_KEY_FILE=/run/secrets/apns.p8`
and the providers (`fcm`, `apns`) in `.env.production`, and deploy.

## 10. Mobile apps and other clients

Production builds of the mobile apps point at API `https://asseta.co.tz` and issuer
`https://asseta.co.tz/auth/realms/asseta` (note the `/auth` path; iOS `ASSETA_OIDC_ISSUER`, Android equivalent).
The realm's `asseta-mobile` client already allows the app redirect schemes.

## 11. What the templates enforce (reference)

* Static console: `/assets/*` (hashed) cached for a year; `index.html` and other files `no-cache`; SPA fallback.
* `/api/` → `127.0.0.1:5020`, with `/api/v1/ws` upgraded to WebSocket (120 s read timeout).
* Rate limits per client IP (F-5): `/api/` 30 r/s with a burst of 150. Report exports, ML training, invoice
  generation and test sends get an extra 1 r/s, burst 10. Gateway ingest 50 r/s. Keycloak 10 r/s, burst 40.
  Evidence 20 r/s, burst 100. Excess gets 429 `RATE_LIMITED` in the API's JSON envelope. Bodies over 11 MiB get
  413 `PAYLOAD_TOO_LARGE` (F-6). All zone and map names are prefixed `asseta_`, and `limit_req_status` is set per
  server, so other sites keep their own settings.
* The API trusts `X-Forwarded-For`/`-Proto` only from the Docker bridge gateway, which is how host nginx reaches
  the published port (`FORWARDED_ALLOW_IPS`, detected at deploy time). nginx overwrites `X-Forwarded-For`, so
  clients cannot spoof their address. Keycloak trusts the same address (`KC_PROXY_TRUSTED_ADDRESSES`).
* Presigned evidence URLs are signed for `https://asseta.co.tz` (`ASSETA_S3_PUBLIC_ENDPOINT`). nginx proxies
  only `GET`/`HEAD` on `/asseta-evidence/` to MinIO and passes the client's `Host` unchanged, which the SigV4
  signature covers. The MLflow bucket is not exposed.
* Headers: HSTS (1 year, subdomains), `nosniff`, `SAMEORIGIN`, `strict-origin-when-cross-origin`, a
  `Permissions-Policy`, and a CSP for the console that allows MapLibre (blob workers, the origins in
  `NGINX_MAP_CSP_ORIGINS`) and the same-origin Keycloak silent-SSO iframe. Keycloak's own pages keep Keycloak's
  CSP. If you change `VITE_MAP_STYLE_URL` to another tile provider, add its origins to `NGINX_MAP_CSP_ORIGINS`.
