package com.asseta.core.ui.image

import org.junit.Assert.assertEquals
import org.junit.Test

class ExifTransformTest {
    @Test
    fun `camera orientations rotate clockwise`() {
        assertEquals(ExifTransform(0, false), ExifTransform.of(1))
        assertEquals(ExifTransform(90, false), ExifTransform.of(6))
        assertEquals(ExifTransform(180, false), ExifTransform.of(3))
        assertEquals(ExifTransform(270, false), ExifTransform.of(8))
    }

    @Test
    fun `mirrored orientations flip after rotating`() {
        assertEquals(ExifTransform(0, true), ExifTransform.of(2))
        assertEquals(ExifTransform(180, true), ExifTransform.of(4))
        assertEquals(ExifTransform(90, true), ExifTransform.of(5))
        assertEquals(ExifTransform(270, true), ExifTransform.of(7))
    }

    @Test
    fun `missing or unknown orientation leaves the photo as is`() {
        assertEquals(ExifTransform(0, false), ExifTransform.of(0))
        assertEquals(ExifTransform(0, false), ExifTransform.of(99))
    }
}
