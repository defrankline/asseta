package com.asseta.core.auth

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class AuthConfigTest {
    private fun cfg(issuer: String, insecure: Boolean = false, scheme: String = "com.asseta.supervisor") =
        AuthConfig(issuer, "asseta-mobile", scheme, insecure)

    @Test
    fun `supervisor redirect uris use its private scheme`() {
        val c = cfg("https://id.example.com/realms/asseta", scheme = "com.asseta.supervisor")
        assertEquals("com.asseta.supervisor:/oauth2redirect", c.redirectUri)
        assertEquals("com.asseta.supervisor:/logout", c.postLogoutRedirectUri)
    }

    @Test
    fun `owner redirect uris use its private scheme`() {
        val c = cfg("https://id.example.com/realms/asseta", scheme = "com.asseta.owner")
        assertEquals("com.asseta.owner:/oauth2redirect", c.redirectUri)
        assertEquals("com.asseta.owner:/logout", c.postLogoutRedirectUri)
    }

    @Test
    fun `apps never share a callback while sharing the client`() {
        val supervisor = cfg("https://id.example.com/realms/asseta", scheme = "com.asseta.supervisor")
        val owner = cfg("https://id.example.com/realms/asseta", scheme = "com.asseta.owner")
        assertEquals(supervisor.clientId, owner.clientId)
        assertNotEquals(supervisor.redirectUri, owner.redirectUri)
        assertNotEquals(supervisor.postLogoutRedirectUri, owner.postLogoutRedirectUri)
    }

    @Test
    fun `invalid redirect scheme is rejected`() {
        assertThrows(IllegalArgumentException::class.java) { cfg("https://id.example.com/realms/asseta", scheme = "") }
        assertThrows(IllegalArgumentException::class.java) {
            cfg("https://id.example.com/realms/asseta", scheme = "Com.Asseta:/x")
        }
    }

    @Test
    fun `http issuer only allowed when explicitly insecure`() {
        assertThrows(IllegalArgumentException::class.java) { cfg("http://10.0.2.2:8080/realms/asseta") }
        cfg("http://10.0.2.2:8080/realms/asseta", insecure = true)
    }

    @Test
    fun `issuer must be the asseta realm and non blank`() {
        assertThrows(IllegalArgumentException::class.java) { cfg("https://id.example.com/realms/master") }
        assertThrows(IllegalArgumentException::class.java) { cfg("") }
    }
}
