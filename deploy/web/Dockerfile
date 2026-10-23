# Production console build for host nginx (scripts/deploy-live.sh). Build context: ./web
#   docker build -f deploy/web/Dockerfile --build-arg VITE_KEYCLOAK_URL=https://asseta.co.tz/auth ... web
# The final stage only carries the static files (/dist); deploy-live.sh copies them into
# /var/www/html/<domain>/releases/<tag>. VITE_* values are public build-time config, never secrets.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_KEYCLOAK_URL
ARG VITE_KEYCLOAK_REALM=asseta
ARG VITE_KEYCLOAK_CLIENT_ID=asseta-web
ARG VITE_REALTIME_URL=
ARG VITE_MAP_STYLE_URL=
ARG VITE_CONTACT_EMAIL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} VITE_KEYCLOAK_URL=${VITE_KEYCLOAK_URL} \
    VITE_KEYCLOAK_REALM=${VITE_KEYCLOAK_REALM} VITE_KEYCLOAK_CLIENT_ID=${VITE_KEYCLOAK_CLIENT_ID} \
    VITE_REALTIME_URL=${VITE_REALTIME_URL} VITE_MAP_STYLE_URL=${VITE_MAP_STYLE_URL} \
    VITE_CONTACT_EMAIL=${VITE_CONTACT_EMAIL}
RUN test -n "$VITE_KEYCLOAK_URL" || { echo "VITE_KEYCLOAK_URL is required" >&2; exit 1; }
RUN rm -f .env.local .env.production.local && npm run build

FROM busybox:1.37.0
COPY --from=build /app/dist /dist
CMD ["true"]
