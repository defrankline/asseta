#!/usr/bin/env bash
# Production deploy for a shared Linux host (docs/deployment-live.md). Run from the clone (/home/asseta):
#
#   scripts/deploy-live.sh                    fetch origin/main, build, migrate, roll the app, publish the console
#   scripts/deploy-live.sh rollback [TAG]     app images + console back to TAG (default: the previous deploy)
#   scripts/deploy-live.sh status             current tag, containers, readiness
#   scripts/deploy-live.sh render-nginx MODE [OUT]   render deploy/nginx/host-MODE.conf.template (http-only|ssl)
#
# Strategy (same as the other apps on the host): host nginx + host certbot own 80/443; this script renders and
# installs a dedicated site file, stages the static console under /var/www/html/<domain>/releases/<tag> behind a
# `current` symlink, and runs the Docker stack with every port on 127.0.0.1. Infra services are only ever
# `up -d` (idempotent); the app image is rebuilt, `migrate` runs, then api + workers are recreated. Nothing is
# ever `down`ed, no volume is removed, and only this project's containers/images are cleaned up.
set -Eeuo pipefail

LOG_TAG=deploy
# shellcheck source-path=SCRIPTDIR source=lib/live-common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/live-common.sh"
cd "$REPO_ROOT"

load_config() {
  DEPLOY_BRANCH="$(cfg DEPLOY_BRANCH main)"
  DEPLOY_ACCEPT_INCOMING_RESET="$(cfg DEPLOY_ACCEPT_INCOMING_RESET 1)"
  DEPLOY_SKIP_GIT_UPDATE="$(cfg DEPLOY_SKIP_GIT_UPDATE 0)"
  DOMAIN="$(cfg DOMAIN asseta.co.tz)"
  API_PORT="$(cfg ASSETA_API_HOST_PORT 5020)"
  KEYCLOAK_PORT="$(cfg ASSETA_KEYCLOAK_HOST_PORT 5021)"
  MINIO_PORT="$(cfg ASSETA_MINIO_HOST_PORT 5022)"
  TRACCAR_UI_PORT="$(cfg ASSETA_TRACCAR_UI_HOST_PORT 5023)"
  MLFLOW_PORT="$(cfg ASSETA_MLFLOW_HOST_PORT 5024)"
  OSMAND_PORT="$(cfg ASSETA_TRACCAR_OSMAND_PORT 5055)"
  TRACCAR_PUBLIC_DEVICE_PORTS="$(cfg TRACCAR_PUBLIC_DEVICE_PORTS 0)"
  # Where host nginx and the health probes reach the published ports (a rehearsal in a container overrides it).
  LOCAL_UPSTREAM_HOST="$(cfg LOCAL_UPSTREAM_HOST 127.0.0.1)"
  PUBLIC_KEYCLOAK_URL="$(cfg ASSETA_PUBLIC_KEYCLOAK_URL "https://$DOMAIN/auth")"
  EVIDENCE_BUCKET="$(cfg ASSETA_S3_BUCKET asseta-evidence)"
  MAP_CSP_ORIGINS="$(cfg NGINX_MAP_CSP_ORIGINS "https://demotiles.maplibre.org https://tile.openstreetmap.org https://*.tile.openstreetmap.org")"
  KEYCLOAK_ADMIN_ALLOW_IPS="$(cfg KEYCLOAK_ADMIN_ALLOW_IPS "")"
  WEB_ROOT_BASE="$(cfg WEB_ROOT_BASE "/var/www/html/$DOMAIN")"
  WEB_RELEASES_DIR="$WEB_ROOT_BASE/releases"
  WEB_CURRENT_LINK="$WEB_ROOT_BASE/current"
  WEB_ROOT_OWNER="$(cfg WEB_ROOT_OWNER www-data:www-data)"
  CERTBOT_WEBROOT="$(cfg CERTBOT_WEBROOT "$WEB_ROOT_BASE/certbot")"
  ENABLE_LETSENCRYPT="$(cfg ENABLE_LETSENCRYPT 1)"
  CERTBOT_COMMAND="$(cfg CERTBOT_COMMAND certbot)"
  LETSENCRYPT_EMAIL="$(cfg LETSENCRYPT_EMAIL "")"
  INSTALL_NGINX_CONFIG="$(cfg INSTALL_NGINX_CONFIG 1)"
  NGINX_SITE_MODE="$(cfg NGINX_SITE_MODE auto)"
  NGINX_SITE_NAME="$(cfg NGINX_SITE_NAME "$DOMAIN.conf")"
  KEEP_DOCKER_IMAGES="$(cfg KEEP_DOCKER_IMAGES 2)"
  KEEP_FRONTEND_RELEASES="$(cfg KEEP_FRONTEND_RELEASES 2)"
  ENABLE_DANGLING_PRUNE="$(cfg ENABLE_DANGLING_PRUNE 0)"
  ENABLE_BUILDER_PRUNE="$(cfg ENABLE_BUILDER_PRUNE 0)"
  BUILDER_KEEP_STORAGE="$(cfg BUILDER_KEEP_STORAGE 2GB)"
  MIN_FREE_DISK_GB="$(cfg MIN_FREE_DISK_GB 10)"
  HEALTH_TIMEOUT="$(cfg HEALTH_TIMEOUT 300)"
  VITE_API_BASE_URL="$(cfg VITE_API_BASE_URL /api/v1)"
  VITE_REALTIME_URL="$(cfg VITE_REALTIME_URL "")"
  VITE_MAP_STYLE_URL="$(cfg VITE_MAP_STYLE_URL "")"
  VITE_CONTACT_EMAIL="$(cfg VITE_CONTACT_EMAIL "")"
}

# --- Preflight ------------------------------------------------------------------------------------------------------

check_env_file() {
  require_env_file
  local perms missing key
  perms="$(stat -c %a "$ENV_FILE" 2>/dev/null || stat -f %Lp "$ENV_FILE")"
  [[ "$perms" == "600" || "$perms" == "400" ]] || warn "$ENV_FILE has mode $perms; run: chmod 600 $ENV_FILE"
  missing="$(grep -E '^[A-Za-z0-9_]+=.*CHANGE_ME' "$ENV_FILE" | cut -d= -f1 | tr '\n' ' ' || true)"
  [[ -z "$missing" ]] || fail "$ENV_FILE still has CHANGE_ME for: $missing"
  for key in POSTGRES_SUPERUSER_PASSWORD ASSETA_OWNER_DB_PASSWORD ASSETA_APP_DB_PASSWORD KEYCLOAK_DB_PASSWORD \
    MLFLOW_DB_PASSWORD KEYCLOAK_ADMIN_USER KEYCLOAK_ADMIN_PASSWORD ASSETA_API_CLIENT_SECRET REDIS_PASSWORD \
    MINIO_ROOT_USER MINIO_ROOT_PASSWORD ASSETA_TRACCAR_GATEWAY_KEY; do
    [[ -n "$(env_file_get "$ENV_FILE" "$key")" ]] || fail "$key is empty in $ENV_FILE"
  done
  [[ "$(env_file_get "$ENV_FILE" ASSETA_TRACCAR_GATEWAY_KEY | wc -c)" -ge 24 ]] ||
    fail "ASSETA_TRACCAR_GATEWAY_KEY must be at least 24 characters"
  if [[ "$ENABLE_LETSENCRYPT" == "1" && -z "$LETSENCRYPT_EMAIL" ]]; then
    fail "Set LETSENCRYPT_EMAIL in $ENV_FILE (or ENABLE_LETSENCRYPT=0 when certificates are managed elsewhere)."
  fi
}

check_dns() {
  local resolved local_ips public_ip ip
  if ! command -v getent >/dev/null 2>&1; then
    warn "getent not found; skipping the DNS check for $DOMAIN"
    return 0
  fi
  resolved="$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ' || true)"
  if [[ -z "$resolved" ]]; then
    warn "$DOMAIN does not resolve yet. Let's Encrypt issuance will fail until its A record points here."
    return 0
  fi
  local_ips="$(hostname -I 2>/dev/null || true)"
  public_ip="$(curl -4fsS --max-time 5 https://api.ipify.org 2>/dev/null || true)"
  for ip in $resolved; do
    if [[ " $local_ips $public_ip " == *" $ip "* ]]; then
      log "DNS: $DOMAIN -> $ip (this host)"
      return 0
    fi
  done
  warn "DNS: $DOMAIN -> $resolved, but this host is ${public_ip:-unknown} / ${local_ips:-unknown}. Continuing."
}

free_gb() {
  df -Pk "$1" 2>/dev/null | awk 'NR == 2 {print int($4 / 1048576)}'
}

check_disk() {
  local path free docker_root
  docker_root="$(docker info -f '{{.DockerRootDir}}' 2>/dev/null || true)"
  for path in "$REPO_ROOT" "$docker_root"; do
    [[ -n "$path" && -d "$path" ]] || continue
    free="$(free_gb "$path")"
    [[ -n "$free" ]] || continue
    ((free >= MIN_FREE_DISK_GB)) || fail "Only ${free} GB free on $path (need $MIN_FREE_DISK_GB GB; MIN_FREE_DISK_GB)."
    log "Disk: ${free} GB free on $path"
  done
}

port_listening() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    [[ -n "$(ss -Hltn "sport = :$port" 2>/dev/null)" ]]
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  else
    return 1
  fi
}

check_ports() {
  local ports=("$API_PORT" "$KEYCLOAK_PORT" "$MINIO_PORT" "$TRACCAR_UI_PORT" "$MLFLOW_PORT" "$OSMAND_PORT")
  local port owners
  for port in "${ports[@]}"; do
    owners="$(docker ps --filter "publish=$port" --format '{{.Label "com.docker.compose.project"}}' | sort -u |
      tr '\n' ' ')"
    owners="${owners% }"
    if [[ -n "$owners" && "$owners" != "$COMPOSE_PROJECT_NAME" ]]; then
      fail "Port $port is published by another Docker project ($owners). Change ASSETA_*_HOST_PORT in $ENV_FILE."
    fi
    if [[ -z "$owners" ]] && port_listening "$port"; then
      fail "Port $port is already in use on this host by a non-Docker process. Change ASSETA_*_HOST_PORT."
    fi
  done
  log "Ports free or owned by '$COMPOSE_PROJECT_NAME': ${ports[*]}"
}

preflight() {
  local cmd
  for cmd in git docker sed awk grep find sort curl mktemp date df cut tr; do
    require_cmd "$cmd"
  done
  [[ "${EUID:-$(id -u)}" -eq 0 ]] || require_cmd sudo
  docker info >/dev/null 2>&1 || fail "Cannot talk to the Docker daemon (is this user in the docker group?)."
  require_compose_v2
  check_env_file
  check_dns
  check_disk
  check_ports
}

# --- Code -----------------------------------------------------------------------------------------------------------

update_code_from_git() {
  if [[ "$DEPLOY_SKIP_GIT_UPDATE" == "1" ]]; then
    log "Skipping git update (DEPLOY_SKIP_GIT_UPDATE=1); deploying $(git rev-parse --short HEAD)"
    return 0
  fi
  log "Fetching origin/$DEPLOY_BRANCH"
  git fetch --quiet origin "$DEPLOY_BRANCH"

  if ! git rev-parse --verify --quiet "$DEPLOY_BRANCH" >/dev/null; then
    git checkout --quiet -B "$DEPLOY_BRANCH" "origin/$DEPLOY_BRANCH"
  else
    git checkout --quiet "$DEPLOY_BRANCH"
  fi

  if ! git diff --quiet || ! git diff --cached --quiet; then
    if [[ "$DEPLOY_ACCEPT_INCOMING_RESET" == "1" ]]; then
      log "Local changes detected; resetting the deployment checkout (ignored files such as .env.production stay)"
      git reset --hard --quiet
      git clean -fdq
    else
      fail "Local changes detected. Commit/stash them or set DEPLOY_ACCEPT_INCOMING_RESET=1."
    fi
  fi

  if ! git merge --quiet --no-edit -X theirs "origin/$DEPLOY_BRANCH"; then
    git merge --abort >/dev/null 2>&1 || true
    if [[ "$DEPLOY_ACCEPT_INCOMING_RESET" == "1" ]]; then
      log "Merge conflict; accepting incoming origin/$DEPLOY_BRANCH"
      git reset --hard --quiet "origin/$DEPLOY_BRANCH"
      git clean -fdq
    else
      fail "Merge conflict. Set DEPLOY_ACCEPT_INCOMING_RESET=1 to accept incoming."
    fi
  fi
}

# --- nginx + certificates -------------------------------------------------------------------------------------------

escape_sed() {
  printf '%s' "$1" | sed 's/[\/&|]/\\&/g'
}

keycloak_admin_rules() {
  local ip rules=""
  for ip in $KEYCLOAK_ADMIN_ALLOW_IPS; do
    rules+="allow $ip; "
  done
  printf '%sdeny all;' "$rules"
}

render_nginx_config() {
  local mode="$1" target="${2:-$REPO_ROOT/deploy/nginx/runtime/$DOMAIN.conf}"
  local template="$REPO_ROOT/deploy/nginx/host-$mode.conf.template"
  [[ -f "$template" ]] || fail "Missing nginx template: $template"
  mkdir -p "$(dirname "$target")"
  sed \
    -e "s/__DOMAIN__/$(escape_sed "$DOMAIN")/g" \
    -e "s/__WEB_ROOT__/$(escape_sed "$WEB_CURRENT_LINK")/g" \
    -e "s/__CERTBOT_WEBROOT__/$(escape_sed "$CERTBOT_WEBROOT")/g" \
    -e "s/__UPSTREAM_HOST__/$(escape_sed "$LOCAL_UPSTREAM_HOST")/g" \
    -e "s/__API_PORT__/$(escape_sed "$API_PORT")/g" \
    -e "s/__KEYCLOAK_PORT__/$(escape_sed "$KEYCLOAK_PORT")/g" \
    -e "s/__MINIO_PORT__/$(escape_sed "$MINIO_PORT")/g" \
    -e "s/__EVIDENCE_BUCKET__/$(escape_sed "$EVIDENCE_BUCKET")/g" \
    -e "s/__MAP_CSP_ORIGINS__/$(escape_sed "$MAP_CSP_ORIGINS")/g" \
    -e "s/__KEYCLOAK_ADMIN_RULES__/$(escape_sed "$(keycloak_admin_rules)")/g" \
    "$template" >"$target"
  if grep -q '__[A-Z_]*__' "$target"; then
    fail "Unrendered placeholder left in $target"
  fi
  printf '%s\n' "$target"
}

reload_nginx() {
  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet nginx 2>/dev/null; then
    sudo_cmd systemctl reload nginx
  elif command -v service >/dev/null 2>&1; then
    sudo_cmd service nginx reload
  else
    sudo_cmd nginx -s reload
  fi
}

# Installs only this site's file. If `nginx -t` fails, the previous file is put back (or the new one removed) so a
# later reload by another app on the host cannot pick up a broken Asseta config.
install_nginx_config() {
  local rendered="$1" target link="" backup=""
  if [[ "$INSTALL_NGINX_CONFIG" != "1" ]]; then
    log "Skipping nginx install (INSTALL_NGINX_CONFIG=$INSTALL_NGINX_CONFIG); rendered: $rendered"
    return 0
  fi
  require_cmd nginx
  if [[ "$NGINX_SITE_MODE" == "sites" || ("$NGINX_SITE_MODE" == "auto" && -d /etc/nginx/sites-available && -d /etc/nginx/sites-enabled) ]]; then
    target="/etc/nginx/sites-available/$NGINX_SITE_NAME"
    link="/etc/nginx/sites-enabled/$NGINX_SITE_NAME"
  elif [[ "$NGINX_SITE_MODE" == "conf.d" || "$NGINX_SITE_MODE" == "auto" ]]; then
    target="/etc/nginx/conf.d/$NGINX_SITE_NAME"
  else
    fail "Unsupported NGINX_SITE_MODE=$NGINX_SITE_MODE (auto, sites or conf.d)."
  fi

  if sudo_cmd test -f "$target"; then
    backup="$(mktemp)"
    sudo_cmd cat "$target" >"$backup"
  fi
  sudo_cmd cp "$rendered" "$target"
  sudo_cmd chmod 644 "$target"
  [[ -z "$link" ]] || sudo_cmd ln -sfn "$target" "$link"

  if ! sudo_cmd nginx -t; then
    if [[ -n "$backup" ]]; then
      sudo_cmd cp "$backup" "$target"
      warn "nginx -t failed; restored the previous $target"
    else
      sudo_cmd rm -f "$target"
      [[ -z "$link" ]] || sudo_cmd rm -f "$link"
      warn "nginx -t failed; removed the new $target"
    fi
    rm -f "$backup"
    fail "nginx rejected the rendered config ($rendered). Other sites were not reloaded."
  fi
  rm -f "${backup:-/nonexistent}"
  reload_nginx
  log "Installed nginx site: $target"
}

certificate_exists() {
  sudo_cmd test -s "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" &&
    sudo_cmd test -s "/etc/letsencrypt/live/$DOMAIN/privkey.pem"
}

install_current_nginx_config() {
  local mode="http-only"
  if [[ "$INSTALL_NGINX_CONFIG" == "1" ]] && certificate_exists; then
    mode="ssl"
  fi
  install_nginx_config "$(render_nginx_config "$mode")"
}

issue_or_renew_certificate() {
  [[ "$ENABLE_LETSENCRYPT" == "1" && "$INSTALL_NGINX_CONFIG" == "1" ]] || return 0
  require_cmd "$CERTBOT_COMMAND"
  sudo_cmd mkdir -p "$CERTBOT_WEBROOT"

  if certificate_exists; then
    log "Renewing the Let's Encrypt certificate when due"
    sudo_cmd "$CERTBOT_COMMAND" renew --cert-name "$DOMAIN" --quiet ||
      warn "Certificate renewal skipped or failed; the existing certificate stays in place"
  else
    log "Installing the HTTP-only site for the ACME challenge"
    install_nginx_config "$(render_nginx_config http-only)"
    log "Issuing a Let's Encrypt certificate for $DOMAIN (webroot)"
    sudo_cmd "$CERTBOT_COMMAND" certonly --webroot --webroot-path "$CERTBOT_WEBROOT" \
      --email "$LETSENCRYPT_EMAIL" --agree-tos --no-eff-email --non-interactive -d "$DOMAIN"
  fi
  install_nginx_config "$(render_nginx_config ssl)"
}

# --- Build ----------------------------------------------------------------------------------------------------------

set_deploy_tag() {
  DEPLOY_IMAGE_TAG="${DEPLOY_IMAGE_TAG:-$(git rev-parse --short HEAD)-$(date +%Y%m%d%H%M%S)}"
  export DEPLOY_IMAGE_TAG
  log "Deploy tag: $DEPLOY_IMAGE_TAG"
}

# Infra images are rebuilt only when their inputs change: even a fully cached rebuild gets a new image ID, which
# would make Compose recreate (restart) Postgres and MLflow on every deploy.
infra_inputs_hash() {
  git rev-parse HEAD:infra/postgres HEAD:infra/mlflow HEAD:infra/minio 2>/dev/null | tr '\n' ' '
}

build_images() {
  local marker hash
  marker="$(dirname "$STATE_FILE")/infra-images.sha"
  hash="$(infra_inputs_hash)"
  if [[ -n "$hash" && "$(cat "$marker" 2>/dev/null || true)" == "$hash" ]] &&
    docker image inspect "$DOCKER_IMAGE_PREFIX/postgis:18-3.6" "$DOCKER_IMAGE_PREFIX/mlflow:3.17.0" \
      "$DOCKER_IMAGE_PREFIX/minio:RELEASE.2024-07-16T23-46-41Z" >/dev/null 2>&1; then
    log "Infrastructure images unchanged (infra/postgres, infra/mlflow, infra/minio); not rebuilding"
  else
    log "Building infrastructure images (infra/ changed or images missing)"
    compose build postgres mlflow minio
    mkdir -p "$(dirname "$marker")"
    [[ -z "$hash" ]] || printf '%s\n' "$hash" >"$marker"
  fi
  log "Building the API/worker image $DOCKER_IMAGE_PREFIX/api:$DEPLOY_IMAGE_TAG"
  compose build migrate
}

build_web_release() {
  local image="$DOCKER_IMAGE_PREFIX/web-build:$DEPLOY_IMAGE_TAG"
  local container="${COMPOSE_PROJECT_NAME}-web-export-${DEPLOY_IMAGE_TAG}"
  local staging
  staging="$(mktemp -d)"
  WEB_RELEASE_PATH="$WEB_RELEASES_DIR/$DEPLOY_IMAGE_TAG"

  log "Building the console (VITE_KEYCLOAK_URL=$PUBLIC_KEYCLOAK_URL)"
  docker build -f deploy/web/Dockerfile \
    --build-arg "VITE_API_BASE_URL=$VITE_API_BASE_URL" \
    --build-arg "VITE_KEYCLOAK_URL=$PUBLIC_KEYCLOAK_URL" \
    --build-arg "VITE_KEYCLOAK_REALM=asseta" \
    --build-arg "VITE_KEYCLOAK_CLIENT_ID=asseta-web" \
    --build-arg "VITE_REALTIME_URL=$VITE_REALTIME_URL" \
    --build-arg "VITE_MAP_STYLE_URL=$VITE_MAP_STYLE_URL" \
    --build-arg "VITE_CONTACT_EMAIL=$VITE_CONTACT_EMAIL" \
    -t "$image" web

  docker rm -f "$container" >/dev/null 2>&1 || true
  docker create --name "$container" "$image" >/dev/null
  docker cp "$container:/dist/." "$staging/"
  docker rm "$container" >/dev/null
  [[ -s "$staging/index.html" ]] || fail "Console build produced no index.html"

  sudo_cmd mkdir -p "$WEB_RELEASES_DIR" "$CERTBOT_WEBROOT"
  sudo_cmd rm -rf "$WEB_RELEASE_PATH"
  sudo_cmd mkdir -p "$WEB_RELEASE_PATH"
  sudo_cmd cp -a "$staging/." "$WEB_RELEASE_PATH/"
  sudo_cmd chown -R "$WEB_ROOT_OWNER" "$WEB_RELEASE_PATH" "$CERTBOT_WEBROOT" 2>/dev/null || true
  sudo_cmd chmod -R a+rX "$WEB_RELEASE_PATH"
  rm -rf "$staging"
  log "Console staged at $WEB_RELEASE_PATH"
}

activate_web_release() {
  local release="$1"
  [[ -d "$release" ]] || fail "Console release not found: $release"
  if [[ -e "$WEB_CURRENT_LINK" && ! -L "$WEB_CURRENT_LINK" ]]; then
    fail "$WEB_CURRENT_LINK exists and is not a symlink. Move it before deploying."
  fi
  sudo_cmd ln -sfn "$release" "$WEB_CURRENT_LINK"
  sudo_cmd chown -h "$WEB_ROOT_OWNER" "$WEB_CURRENT_LINK" 2>/dev/null || true
  log "Console live: $WEB_CURRENT_LINK -> $release"
}

# --- Stack ----------------------------------------------------------------------------------------------------------

# The host proxy reaches published ports through the bridge gateway of this project's network; that address is the
# only one the API (uvicorn FORWARDED_ALLOW_IPS) and Keycloak (KC_PROXY_TRUSTED_ADDRESSES) trust for X-Forwarded-*.
detect_proxy_gateway() {
  local override network gw
  override="$(cfg ASSETA_PROXY_TRUSTED_IP_OVERRIDE "")"
  if [[ -n "$override" ]]; then
    ASSETA_PROXY_TRUSTED_IP="$override"
  else
    network="$(docker network ls -q --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME" \
      --filter "label=com.docker.compose.network=default" | head -n 1)"
    [[ -n "$network" ]] || fail "Network ${COMPOSE_PROJECT_NAME}_default not found"
    gw="$(docker network inspect -f '{{range .IPAM.Config}}{{.Gateway}} {{end}}' "$network" |
      tr ' ' '\n' | grep -E '^[0-9]+(\.[0-9]+){3}$' | head -n 1 || true)"
    [[ -n "$gw" ]] || fail "Could not read the gateway of the ${COMPOSE_PROJECT_NAME}_default network; set ASSETA_PROXY_TRUSTED_IP_OVERRIDE."
    ASSETA_PROXY_TRUSTED_IP="$gw"
  fi
  export ASSETA_PROXY_TRUSTED_IP
  log "Trusted proxy address (X-Forwarded-*): $ASSETA_PROXY_TRUSTED_IP"
}

set_device_bind() {
  if [[ "$TRACCAR_PUBLIC_DEVICE_PORTS" == "1" ]]; then
    ASSETA_TRACCAR_DEVICE_BIND=0.0.0.0
    warn "Traccar device port $OSMAND_PORT is published on 0.0.0.0: allow it in the firewall (docs/deployment-live.md)"
  else
    ASSETA_TRACCAR_DEVICE_BIND=127.0.0.1
  fi
  export ASSETA_TRACCAR_DEVICE_BIND
}

start_infra() {
  log "Starting/keeping data services (idempotent; data services are never removed)"
  compose up -d postgres
  detect_proxy_gateway
  set_device_bind
  compose up -d redis kafka minio keycloak
  wait_healthy postgres 300
  wait_healthy redis 120
  wait_healthy minio 180
  wait_healthy kafka 300
  wait_healthy keycloak 900  # first start: optimized build + realm import
  compose up -d mlflow
}

run_migrations() {
  log "Running migrations + bootstrap (alembic upgrade head && asseta-bootstrap)"
  compose run --rm --no-deps migrate || fail "Migration failed; the running API and workers were left unchanged."
}

roll_app() {
  log "Recreating api + workers on $DOCKER_IMAGE_PREFIX/api:$DEPLOY_IMAGE_TAG"
  compose up -d --no-deps "${APP_SERVICES[@]}"
  wait_for_api "$HEALTH_TIMEOUT"
  compose up -d --no-deps traccar
}

# --- Cleanup (this project only) ------------------------------------------------------------------------------------

cleanup_web_releases() {
  [[ -d "$WEB_RELEASES_DIR" ]] || return 0
  local current previous release kept=0
  current="$(readlink "$WEB_CURRENT_LINK" 2>/dev/null || true)"
  previous="$WEB_RELEASES_DIR/${PREVIOUS_IMAGE_TAG:-none}"
  log "Cleaning console releases; keeping the newest $KEEP_FRONTEND_RELEASES"
  # Newest first by modification time (release names are <sha>-<timestamp>).
  while IFS= read -r release; do
    release="${release%/}"
    [[ -n "$release" ]] || continue
    kept=$((kept + 1))
    if ((kept > KEEP_FRONTEND_RELEASES)) && [[ "$release" != "$current" && "$release" != "$previous" ]]; then
      sudo_cmd rm -rf "$release"
    fi
  done < <(ls -1dt "$WEB_RELEASES_DIR"/*/ 2>/dev/null || true)
}

cleanup_images_for_repo() {
  local repo="$1" tag kept=0
  while IFS= read -r tag; do
    [[ -n "$tag" && "$tag" != "<none>" ]] || continue
    kept=$((kept + 1))
    if ((kept > KEEP_DOCKER_IMAGES)) && [[ "$tag" != "$DEPLOY_IMAGE_TAG" && "$tag" != "${PREVIOUS_IMAGE_TAG:-}" ]]; then
      # By tag and without -f: an image a container still uses is refused and kept.
      docker image rm "$repo:$tag" >/dev/null 2>&1 || true
    fi
  done < <(docker image ls "$repo" --format '{{.CreatedAt}}\t{{.Tag}}' | sort -r | cut -f2)
}

cleanup_docker() {
  log "Removing this project's leftover one-off containers"
  docker ps -a -q --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME" \
    --filter "label=com.docker.compose.oneoff=True" --filter status=exited | xargs -r docker rm >/dev/null 2>&1 || true
  log "Cleaning this project's old images; keeping the newest $KEEP_DOCKER_IMAGES per repository"
  cleanup_images_for_repo "$DOCKER_IMAGE_PREFIX/api"
  cleanup_images_for_repo "$DOCKER_IMAGE_PREFIX/web-build"
  if [[ "$ENABLE_DANGLING_PRUNE" == "1" ]]; then
    docker image prune -f --filter "dangling=true" --filter "until=168h" >/dev/null 2>&1 || true
  fi
  if [[ "$ENABLE_BUILDER_PRUNE" == "1" ]]; then
    docker builder prune -f --keep-storage "$BUILDER_KEEP_STORAGE" >/dev/null 2>&1 || true
  fi
}

# --- Commands -------------------------------------------------------------------------------------------------------

deploy() {
  preflight
  local before
  before="$(git rev-parse HEAD)"
  update_code_from_git
  if [[ "$(git rev-parse HEAD)" != "$before" && "${ASSETA_DEPLOY_REEXEC:-0}" != "1" ]]; then
    log "Code updated to $(git rev-parse --short HEAD); restarting with the updated deploy script"
    exec env ASSETA_DEPLOY_REEXEC=1 DEPLOY_SKIP_GIT_UPDATE=1 "$REPO_ROOT/scripts/deploy-live.sh" deploy
  fi
  load_config
  PREVIOUS_IMAGE_TAG="$(state_get DEPLOY_IMAGE_TAG)"
  set_deploy_tag

  build_images
  build_web_release
  install_current_nginx_config
  issue_or_renew_certificate

  start_infra
  run_migrations
  roll_app
  state_write "$DEPLOY_IMAGE_TAG" "$PREVIOUS_IMAGE_TAG" "$ASSETA_PROXY_TRUSTED_IP" "$ASSETA_TRACCAR_DEVICE_BIND"

  activate_web_release "$WEB_RELEASE_PATH"
  install_current_nginx_config
  cleanup_web_releases
  cleanup_docker
  log "Deployment complete: https://$DOMAIN (tag $DEPLOY_IMAGE_TAG; previous ${PREVIOUS_IMAGE_TAG:-none})"
}

rollback() {
  require_env_file
  require_compose_v2
  local target="${1:-$(state_get PREVIOUS_IMAGE_TAG)}" current
  current="$(state_get DEPLOY_IMAGE_TAG)"
  [[ -n "$target" ]] || fail "No previous tag recorded; pass one: scripts/deploy-live.sh rollback <tag>"
  docker image inspect "$DOCKER_IMAGE_PREFIX/api:$target" >/dev/null 2>&1 ||
    fail "Image $DOCKER_IMAGE_PREFIX/api:$target is not on this host (kept: $(docker image ls "$DOCKER_IMAGE_PREFIX/api" --format '{{.Tag}}' | tr '\n' ' '))"
  warn "Rolling back app images to $target. Database migrations are NOT reverted: only roll back across releases"
  warn "without new migrations, otherwise restore the pre-upgrade backup (docs/operating-runbook.md §4)."
  DEPLOY_IMAGE_TAG="$target"
  PREVIOUS_IMAGE_TAG="$current"
  export DEPLOY_IMAGE_TAG
  ASSETA_PROXY_TRUSTED_IP="$(state_get ASSETA_PROXY_TRUSTED_IP)"
  ASSETA_TRACCAR_DEVICE_BIND="$(state_get ASSETA_TRACCAR_DEVICE_BIND)"
  export ASSETA_PROXY_TRUSTED_IP ASSETA_TRACCAR_DEVICE_BIND
  roll_app
  state_write "$target" "$current" "$ASSETA_PROXY_TRUSTED_IP" "$ASSETA_TRACCAR_DEVICE_BIND"
  if [[ -d "$WEB_RELEASES_DIR/$target" ]]; then
    activate_web_release "$WEB_RELEASES_DIR/$target"
  else
    warn "No console release $WEB_RELEASES_DIR/$target; the console stays on $(readlink "$WEB_CURRENT_LINK" || true)"
  fi
  log "Rolled back to $target"
}

status() {
  require_env_file
  log "Tag: $(state_get DEPLOY_IMAGE_TAG) (previous: $(state_get PREVIOUS_IMAGE_TAG))"
  log "Console: $(readlink "$WEB_CURRENT_LINK" 2>/dev/null || echo 'not activated')"
  compose ps
  log "Readiness: $(api_ready_body)"
}

main() {
  load_config
  local command="${1:-deploy}"
  case "$command" in
    deploy) deploy ;;
    rollback) rollback "${2:-}" ;;
    status) status ;;
    render-nginx)
      [[ "${2:-}" == "http-only" || "${2:-}" == "ssl" ]] || fail "Usage: $0 render-nginx http-only|ssl [output]"
      render_nginx_config "$2" "${3:-}"
      ;;
    -h | --help | help) sed -n '2,13p' "$0" ;;
    *) fail "Unknown command '$command' (deploy, rollback [TAG], status, render-nginx MODE [OUT])" ;;
  esac
}

main "$@"
