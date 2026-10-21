package com.asseta.core.domain.ocr

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.JsonNull
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Runs every shared case from contracts/fixtures/ocr/parse_cases.json (read in place, never copied). */
class MeterReadingParserTest {
    private val casesFile: File = File(
        System.getProperty("asseta.contracts.dir") ?: error("asseta.contracts.dir not set by Gradle"),
        "fixtures/ocr/parse_cases.json",
    )

    @Test
    fun passesEverySharedParseCase() {
        val root = Json.parseToJsonElement(casesFile.readText()).jsonObject
        assertEquals(MeterReadingParser.SPEC_VERSION, root["spec_version"]!!.jsonPrimitive.content)
        val cases = root["cases"]!!.jsonArray.map { it.jsonObject }
        assertTrue("expected shared cases", cases.size >= 12)
        val failures = cases.mapNotNull { c -> check(c) }
        assertEquals("Failing shared OCR cases:\n" + failures.joinToString("\n"), emptyList<String>(), failures)
    }

    private fun check(case: JsonObject): String? {
        val text = case["text"]!!.jsonPrimitive.content
        val dp = case["decimal_places"]!!.jsonPrimitive.int
        val expectedValue = case["value"].let { if (it == null || it is JsonNull) null else it.jsonPrimitive.content }
        val expectedReason = case["reason"]!!.jsonPrimitive.content
        val actual = MeterReadingParser.parse(text, dp)
        return if (actual.value == expectedValue && actual.reason == expectedReason) null
        else "'$text' dp=$dp expected ($expectedValue, $expectedReason) got (${actual.value}, ${actual.reason})"
    }

    @Test
    fun reportsHowTheFractionWasEstablished() {
        assertTrue(MeterReadingParser.parse("4521.7", 1).explicitSeparator)
        assertTrue(MeterReadingParser.parse("08765 3", 1).drumSplit)
        val merged = MeterReadingParser.parse("202641", 1)
        assertEquals("202641.0", merged.value)
        assertTrue(!merged.explicitSeparator && !merged.drumSplit)
    }
}
