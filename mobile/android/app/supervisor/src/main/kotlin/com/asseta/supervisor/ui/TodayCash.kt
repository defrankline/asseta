package com.asseta.supervisor.ui

import com.asseta.core.domain.finance.CustodyLine
import com.asseta.core.model.sync.CashReconciliationDayDto
import com.asseta.core.sync.data.CashToday
import com.asseta.core.sync.data.OnlineResult
import com.asseta.supervisor.ui.finance.MyCashTexts
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** What the Money tab's "Today" section shows for one currency. */
sealed interface TodayFigures {
    /** Online: the office's figures of today. */
    data class Live(val day: CashReconciliationDayDto) : TodayFigures

    /** Offline, saved earlier today: the office's figures as of [fetchedAtMs]. */
    data class SavedToday(val day: CashReconciliationDayDto, val fetchedAtMs: Long) : TodayFigures

    /** Offline, saved on an earlier day ([date]): only that day's outstanding next to the estimate. */
    data class SavedEarlier(val day: CashReconciliationDayDto, val date: LocalDate) : TodayFigures

    /** Nothing from the office: the offline estimate only. */
    data object Estimate : TodayFigures
}

/** Selection and wording of the "Today" section (word for word the iOS `TodayCash`), unit-tested. */
object TodayCash {
    const val SAVED_FOOTER = "Office figures from the last time this phone was online. Not updated while offline."
    const val NOT_SYNCED = "Recorded on this phone, not yet synced"

    private val time = DateTimeFormatter.ofPattern("HH:mm", Locale.ENGLISH)
    private val date = DateTimeFormatter.ofPattern("d MMM yyyy", Locale.ENGLISH)

    /** [result] is null until the first fetch finished; [today] is this phone's local date. */
    fun figures(result: OnlineResult<CashToday>?, currency: String, today: LocalDate): TodayFigures {
        fun dayOf(saved: CashToday) = saved.reconciliations.firstOrNull { it.currency == currency }?.days?.lastOrNull()
        return when (result) {
            is OnlineResult.Fresh -> dayOf(result.value)?.let { TodayFigures.Live(it) } ?: TodayFigures.Estimate
            is OnlineResult.Cached -> {
                val day = dayOf(result.value) ?: return TodayFigures.Estimate
                val savedOn = runCatching { LocalDate.parse(result.value.date) }.getOrNull() ?: return TodayFigures.Estimate
                if (savedOn == today) TodayFigures.SavedToday(day, result.value.fetchedAtMs) else TodayFigures.SavedEarlier(day, savedOn)
            }
            is OnlineResult.Unavailable, null -> TodayFigures.Estimate
        }
    }

    fun header(figures: TodayFigures, zone: ZoneId = ZoneId.systemDefault()): String = when (figures) {
        is TodayFigures.Live -> "Today"
        is TodayFigures.SavedToday -> "Today (as of ${time.format(Instant.ofEpochMilli(figures.fetchedAtMs).atZone(zone))})"
        is TodayFigures.SavedEarlier -> "Last office figures (${date.format(figures.date)})"
        TodayFigures.Estimate -> "Today (estimate)"
    }

    /** This phone's unsynced cash records of the currency (the non-zero ones), signed as they move the cash in hand. */
    fun notSynced(line: CustodyLine): List<Pair<String, String>> = listOfNotNull(
        line.pendingCollections.takeIf { it.signum() > 0 }?.let { "Collections" to MyCashTexts.signed(it, line.currency, +1) },
        line.pendingHandovers.takeIf { it.signum() > 0 }?.let { "Handovers" to MyCashTexts.signed(it, line.currency, -1) },
        line.pendingCashExpenses.takeIf { it.signum() > 0 }?.let { "Cash expenses" to MyCashTexts.signed(it, line.currency, -1) },
    )
}
