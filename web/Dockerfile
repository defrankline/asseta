# Admin console: static build served by nginx (SPA fallback). Build-time VITE_* config.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci
COPY . .
ARG VITE_KEYCLOAK_URL VITE_KEYCLOAK_REALM=asseta VITE_KEYCLOAK_CLIENT_ID=asseta-web
RUN npm run build

FROM nginx:1.28.0-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
