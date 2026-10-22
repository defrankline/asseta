# Admin console: static build served by nginx (SPA fallback). Build-time VITE_* config.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci
COPY . .
ARG VITE_KEYCLOAK_URL VITE_KEYCLOAK_REALM=asseta VITE_KEYCLOAK_CLIENT_ID=asseta-web
RUN npm run build

FROM nginx:1.28.0-alpine
# A template: the image's entrypoint renders it to conf.d/default.conf, substituting only ASSETA_* variables.
ENV NGINX_ENVSUBST_FILTER=^ASSETA_ ASSETA_TRUSTED_PROXY_CIDR=127.0.0.1/32
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
