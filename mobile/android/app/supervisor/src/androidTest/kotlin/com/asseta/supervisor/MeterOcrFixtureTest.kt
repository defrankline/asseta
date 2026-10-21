package com.asseta.supervisor

import android.graphics.BitmapFactory
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.asseta.supervisor.capture.MeterOcr
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.double
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.math.BigDecimal

/**
 * Bundled ML Kit OCR over every image in contracts/fixtures/ocr (mounted as test assets, read via manifest.json).
 * Hard requirements: zero confident wrong reads (confidence >= 0.85 and value != expected) and the manifest target
 * (`must_read_min_accuracy`) on `must_read`; [REGRESSION_FLOOR] guards the measured level. Accuracy overall and per
 * display style is reported in logcat (tag AssetaOcr) and in the instrumentation output.
 */
@RunWith(AndroidJUnit4::class)
class MeterOcrFixtureTest {
    private val assets = InstrumentationRegistry.getInstrumentation().context.assets

    data class Outcome(val file: String, val style: String, val category: String, val expected: String, val value: String?,
        val confidence: Double, val flags: Set<String>, val raw: String) {
        val correct get() = value != null && BigDecimal(value).compareTo(BigDecimal(expected)) == 0
        val confidentWrong get() = value != null && confidence >= CONFIDENT && !correct
        val acceptedCorrect get() = correct && confidence >= CONFIDENT
    }

    @Test
    fun fixturesHaveNoConfidentWrongReadsAndReportAccuracy() = runBlocking {
        val manifest = Json.parseToJsonElement(assets.open("manifest.json").use { it.readBytes().decodeToString() }).jsonObject
        val minAccuracy = manifest["acceptance"]!!.jsonObject["must_read_min_accuracy"]!!.jsonPrimitive.double
        val images = manifest["images"]!!.jsonArray.map { it.jsonObject }
        val ocr = MeterOcr(InstrumentationRegistry.getInstrumentation().targetContext)
        val outcomes = images.map { img ->
            val file = img["file"]!!.jsonPrimitive.content
            val bitmap = assets.open(file).use { BitmapFactory.decodeStream(it) }!!
            val r = ocr.read(bitmap, img["decimal_places"]!!.jsonPrimitive.int, CONFIDENT)
            fun field(name: String) = img[name]!!.jsonPrimitive.content
            Outcome(file, field("style"), field("category"), field("expected_reading"),
                r.value, r.confidence, r.flags, r.rawText.replace('\n', '|'))
        }
        outcomes.forEach {
            Log.i(TAG, "${it.file} [${it.style}/${it.category}] expected=${it.expected} got=${it.value} conf=${"%.3f".format(java.util.Locale.ROOT, it.confidence)} " +
                "correct=${it.correct} accepted=${it.acceptedCorrect} confidentWrong=${it.confidentWrong} flags=${it.flags} raw='${it.raw}'")
        }
        val must = outcomes.filter { it.category == "must_read" }
        val accepted = must.count { it.acceptedCorrect }
        val parsedCorrect = must.count { it.correct }
        val confidentWrong = outcomes.filter { it.confidentWrong }
        val fallback = outcomes.filter { it.category == "fallback_ok" }
        val summary = "must_read: accepted-correct $accepted/${must.size} (${"%.3f".format(java.util.Locale.ROOT, accepted.toDouble() / must.size)}), " +
            "value-correct $parsedCorrect/${must.size}; fallback_ok: accepted-correct ${fallback.count { it.acceptedCorrect }}/${fallback.size}; " +
            "confident wrong reads: ${confidentWrong.size} ${confidentWrong.map { it.file }}"
        val byStyle = must.groupBy { it.style }.entries.joinToString(", ") { (style, list) ->
            "$style ${list.count { it.acceptedCorrect }}/${list.size}"
        }
        Log.i(TAG, "SUMMARY $summary")
        Log.i(TAG, "BY STYLE (must_read accepted-correct): $byStyle")
        InstrumentationRegistry.getInstrumentation().sendStatus(0, android.os.Bundle().apply { putString("stream", "AssetaOcr $summary\nAssetaOcr by style: $byStyle\n") })
        assertEquals(24, outcomes.size)
        assertEquals("confident wrong reads: $summary", 0, confidentWrong.size)
        val accuracy = accepted.toDouble() / must.size
        Log.i(TAG, if (accuracy >= minAccuracy) "manifest target $minAccuracy met" else "BELOW manifest target $minAccuracy")
        assertTrue("must_read accuracy below manifest target $minAccuracy: $summary", accuracy >= minAccuracy)
        assertTrue("must_read accuracy regressed below $REGRESSION_FLOOR: $summary", accuracy >= REGRESSION_FLOOR)
    }

    /** The shared parse spec must hold on the device runtime (ICU regex), not only on the JVM. */
    @Test
    fun sharedParseCasesPassOnDevice() {
        val root = Json.parseToJsonElement(assets.open("parse_cases.json").use { it.readBytes().decodeToString() }).jsonObject
        val failures = root["cases"]!!.jsonArray.map { it.jsonObject }.mapNotNull { c ->
            val text = c["text"]!!.jsonPrimitive.content
            val dp = c["decimal_places"]!!.jsonPrimitive.int
            val expected = c["value"]?.let { if (it is kotlinx.serialization.json.JsonNull) null else it.jsonPrimitive.content }
            val reason = c["reason"]!!.jsonPrimitive.content
            val actual = com.asseta.core.domain.ocr.MeterReadingParser.parse(text, dp)
            if (actual.value == expected && actual.reason == reason) null else "'$text' -> (${actual.value}, ${actual.reason})"
        }
        assertEquals(emptyList<String>(), failures)
    }

    private companion object {
        const val TAG = "AssetaOcr"
        const val CONFIDENT = 0.85
        /**
         * Measured 17/17 = 1.0 on the API 35 arm64 emulator (2026-10-21, geometric pipeline, repeated runs). One fixture
         * of headroom for ML Kit model or device variation; the manifest target still applies.
         */
        const val REGRESSION_FLOOR = 16.0 / 17
    }
}
