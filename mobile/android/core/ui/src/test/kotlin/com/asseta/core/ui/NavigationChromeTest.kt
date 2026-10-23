package com.asseta.core.ui

import com.asseta.core.ui.components.NavigationChrome
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class NavigationChromeTest {
    @Test
    fun `badge hides zero and caps at 99+`() {
        assertNull(NavigationChrome.badge(null))
        assertNull(NavigationChrome.badge(0))
        assertEquals("7", NavigationChrome.badge(7))
        assertEquals("99", NavigationChrome.badge(99))
        assertEquals("99+", NavigationChrome.badge(100))
    }

    @Test
    fun `back label is the previous title when short`() {
        assertEquals("Fleet", NavigationChrome.backLabel("Fleet"))
        assertEquals("Back", NavigationChrome.backLabel("Acme Earthmoving Holdings"))
        assertEquals("Back", NavigationChrome.backLabel(null))
    }
}
