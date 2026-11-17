package com.asseta.core.auth

import java.net.URI

/**
 * Keycloak OIDC settings. Keycloak is authoritative for authentication and authorization; the app only
 * obtains tokens and never derives permissions from them locally.
 */
data class AuthConfig(
    val issuer: String,
    val clientId: String,
    val redirectScheme: String,
    val allowInsecureHttp: Boolean,
    val scopes: List<String> = DEFAULT_SCOPES,
) {
    init {
        require(issuer.isNotBlank()) { "Keycloak issuer is not configured (gradle property asseta.<buildType>.keycloakIssuer)" }
        val uri = URI(issuer)
        require(uri.scheme == "https" || (allowInsecureHttp && uri.scheme == "http")) { "Issuer must use https: $issuer" }
        require(uri.path.trimEnd('/').endsWith("/realms/asseta")) { "Issuer must point at the 'asseta' realm: $issuer" }
        require(clientId.isNotBlank())
        require(redirectScheme.matches(Regex("^[a-z][a-z0-9+.-]*$"))) { "Invalid redirect scheme" }
    }

    /** Private-use URI scheme redirect (RFC 8252 section 7.1). */
    val redirectUri: String get() = "$redirectScheme:/oauth2redirect"
    val postLogoutRedirectUri: String get() = "$redirectScheme:/logout"

    companion object {
        /**
         * `offline_access`: the refresh token is an offline token, kept by Keycloak for 14 days of non-use (the realm's
         * offline idle timeout, matching the DEVICE_SYNC offline grant) instead of dying with the 30-minute browser
         * session. Field users work offline for days.
         */
        val DEFAULT_SCOPES = listOf("openid", "profile", "email", "offline_access")

        /**
         * [redirectScheme] is app-specific (e.g. `com.asseta.supervisor`) and supplied by each app module, so two
         * installed Asseta apps never share an OIDC callback; it is deliberately not defined in this shared module.
         */
        fun fromBuildConfig(redirectScheme: String): AuthConfig = AuthConfig(
            issuer = BuildConfig.KEYCLOAK_ISSUER,
            clientId = BuildConfig.OIDC_CLIENT_ID,
            redirectScheme = redirectScheme,
            allowInsecureHttp = BuildConfig.ALLOW_INSECURE_HTTP,
        )
    }
}
