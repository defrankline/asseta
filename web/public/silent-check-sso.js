// keycloak-js silent check-sso callback (loaded by silent-check-sso.html). An external file, not an inline script,
// so the console's Content-Security-Policy can stay `script-src 'self'` (deploy/nginx).
/* global parent, location */
parent.postMessage(location.href, location.origin);
