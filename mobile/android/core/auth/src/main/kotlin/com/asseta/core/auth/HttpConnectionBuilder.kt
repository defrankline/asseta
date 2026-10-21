package com.asseta.core.auth

import android.net.Uri
import net.openid.appauth.connectivity.ConnectionBuilder
import net.openid.appauth.connectivity.DefaultConnectionBuilder
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

/**
 * AppAuth only permits https by default. Debug builds talk to the local Keycloak over http, so this
 * builder allows http strictly when [AuthConfig.allowInsecureHttp] is set (never in release).
 */
internal class HttpConnectionBuilder(private val allowInsecure: Boolean) : ConnectionBuilder {
    override fun openConnection(uri: Uri): HttpURLConnection {
        if (uri.scheme == "https" || !allowInsecure) return DefaultConnectionBuilder.INSTANCE.openConnection(uri)
        require(uri.scheme == "http") { "Unsupported scheme ${uri.scheme}" }
        return (URL(uri.toString()).openConnection() as HttpURLConnection).apply {
            connectTimeout = TimeUnit.SECONDS.toMillis(15).toInt()
            readTimeout = TimeUnit.SECONDS.toMillis(15).toInt()
            instanceFollowRedirects = false
        }
    }
}
