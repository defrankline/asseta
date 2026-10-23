package com.asseta.core.auth

import com.asseta.core.model.SyncAccount
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.util.Base64

class AccountClaimsTest {
    private fun jwt(payload: String): String {
        val enc = Base64.getUrlEncoder().withoutPadding()
        return enc.encodeToString("""{"alg":"RS256"}""".toByteArray()) + "." + enc.encodeToString(payload.toByteArray()) + ".sig"
    }

    @Test
    fun readsSubjectAndReadableLabel() {
        assertEquals(
            SyncAccount("8d1c-user", "sam@example.com"),
            AccountClaims.fromJwt(jwt("""{"sub":"8d1c-user","email":"sam@example.com","preferred_username":"sam"}""")),
        )
        assertEquals(SyncAccount("u2", "sam"), AccountClaims.fromJwt(jwt("""{"sub":"u2","preferred_username":"sam"}""")))
        assertEquals(SyncAccount("u3", null), AccountClaims.fromJwt(jwt("""{"sub":"u3"}""")))
    }

    @Test
    fun malformedOrSubjectlessTokensHaveNoAccount() {
        assertNull(AccountClaims.fromJwt(null))
        assertNull(AccountClaims.fromJwt("not-a-jwt"))
        assertNull(AccountClaims.fromJwt(jwt("""{"email":"x@example.com"}""")))
        assertNull(AccountClaims.fromJwt("a.%%%.c"))
    }
}
