package com.asseta.supervisor.ui

import com.asseta.core.domain.finance.CustodyBalance
import com.asseta.core.domain.finance.CustodyLine
import com.asseta.core.model.sync.CashReconciliationDayDto
import com.asseta.core.model.sync.CashReconciliationDto
import com.asseta.core.sync.data.CashToday
import com.asseta.core.sync.data.OnlineResult
import org.junit.Assert.assertEquals
import org.junit.Test
import java.math.BigDecimal
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

/** The Money tab's "Today" section online, offline with saved office figures, and without them (iOS `TodayCashTests`). */
class TodayCashTest {
    private val today = LocalDate.parse("2026-10-24")
    private val fetchedAt = Instant.parse("2026-10-24T07:05:00Z").toEpochMilli()

    private fun day(outstanding: String) = CashReconciliationDayDto(
        day = "2026-10-24", opening = "0", floatsIssued = "0", collections = outstanding, approvedSpending = "0", verifiedHandovers = "0",
        outstanding = outstanding, claimedUnverifiedHandovers = "0", pendingSpending = "0", unverifiedCollections = "0",
        outstandingIfClaimsVerified = outstanding,
    )

    private fun saved(date: String, vararg currencies: Pair<String, String>) = CashToday(
        date, fetchedAt, currencies.map { (c, out) -> CashReconciliationDto("s", c, "Africa/Lusaka", listOf(day(out))) },
    )

    @Test
    fun `online shows the office figures under Today`() {
        val f = TodayCash.figures(OnlineResult.Fresh(saved("2026-10-24", "TZS" to "1500")), "TZS", today)
        assertEquals(TodayFigures.Live(day("1500")), f)
        assertEquals("Today", TodayCash.header(f, ZoneOffset.UTC))
    }

    @Test
    fun `offline with figures saved today shows them as of the fetch time`() {
        val f = TodayCash.figures(OnlineResult.Cached(saved("2026-10-24", "TZS" to "1500", "USD" to "20"), fetchedAt), "USD", today)
        assertEquals(TodayFigures.SavedToday(day("20"), fetchedAt), f)
        assertEquals("Today (as of 07:05)", TodayCash.header(f, ZoneOffset.UTC))
        assertEquals("Today (as of 09:05)", TodayCash.header(f, ZoneOffset.ofHours(2)))
        assertEquals("Office figures from the last time this phone was online. Not updated while offline.", TodayCash.SAVED_FOOTER)
    }

    @Test
    fun `offline with figures of an earlier day shows that day's outstanding`() {
        val f = TodayCash.figures(OnlineResult.Cached(saved("2026-10-22", "TZS" to "1500"), fetchedAt), "TZS", today)
        assertEquals(TodayFigures.SavedEarlier(day("1500"), LocalDate.parse("2026-10-22")), f)
        assertEquals("Last office figures (22 Oct 2026)", TodayCash.header(f, ZoneOffset.UTC))
    }

    @Test
    fun `nothing saved for the currency keeps the estimate`() {
        val cached = OnlineResult.Cached(saved("2026-10-24", "TZS" to "1500"), fetchedAt)
        listOf(null, OnlineResult.Unavailable("Offline"), cached).forEach { result ->
            val f = TodayCash.figures(result, if (result == null) "TZS" else "USD", today)
            assertEquals(TodayFigures.Estimate, f)
            assertEquals("Today (estimate)", TodayCash.header(f, ZoneOffset.UTC))
        }
        assertEquals(TodayFigures.Estimate, TodayCash.figures(OnlineResult.Fresh(saved("2026-10-24")), "TZS", today))
    }

    @Test
    fun `records not yet synced are listed with their sign, zero ones left out`() {
        val synced = CustodyBalance("TZS", BigDecimal("1000"), BigDecimal.ZERO, BigDecimal.ZERO, null)
        val line = CustodyLine("TZS", synced, BigDecimal("200"), BigDecimal.ZERO, BigDecimal("50"))
        assertEquals("Recorded on this phone, not yet synced", TodayCash.NOT_SYNCED)
        assertEquals(listOf("Collections" to "+200 TZS", "Cash expenses" to "−50 TZS"), TodayCash.notSynced(line))
        assertEquals(BigDecimal("1150"), line.estimatedInHand)
        assertEquals(emptyList<Pair<String, String>>(), TodayCash.notSynced(CustodyLine("TZS", synced, BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO)))
        assertEquals(
            listOf("Handovers" to "−300 TZS"),
            TodayCash.notSynced(CustodyLine("TZS", synced, BigDecimal.ZERO, BigDecimal("300"), BigDecimal.ZERO)),
        )
    }
}
