package com.asseta.supervisor.ui.report

import com.asseta.core.domain.reports.MachineReportRules
import com.asseta.core.domain.reports.ReportState
import java.math.BigDecimal

/**
 * Wording of the ADR-008 machine report (approved designs MachineReading, Reconcile, ReviewSubmit), shared with iOS word
 * for word (docs/requirements/accountability-mobile-strings.md, "ADR-008 apps").
 */
object ReportTexts {
    const val TITLE = "Machine report"
    const val STEP_READING = "Step 1 of 3 · New reading"
    const val STEP_SPLIT = "Step 2 of 3 · Account for hours"
    const val STEP_REVIEW = "Step 3 of 3 · Review & submit"
    const val REVIEW_TITLE = "Review & submit"

    // Step 1
    const val MACHINE = "Machine"
    const val CHOOSE_MACHINE = "Choose a machine"
    const val NO_MACHINES = "No machines are assigned to you. The office assigns machines to supervisors."
    const val LAST_READING = "Last reading"
    const val APPROVED = "approved"
    const val TAKE_PHOTO = "Take a photo of the meter"
    const val RETAKE_PHOTO = "Retake photo"
    const val READING_PHONE = "Reading the meter on this phone…"
    const val NEW_READING = "New reading (check the number)"
    const val HOURS_TO_ACCOUNT = "Hours to account for"
    const val NOTHING_TO_REPORT = "No difference since the last reading? Nothing to report."
    const val GETTING_GPS = "Getting a fresh location fix…"
    const val NO_GPS = "No location"

    /** "Meter photo · read by the phone · GPS ±6 m". */
    fun photoCaption(readByPhone: Boolean, gps: String?): String =
        listOfNotNull("Meter photo", "read by the phone".takeIf { readByPhone }, gps).joinToString(" · ")

    fun gpsAccuracy(meters: Double?): String = if (meters == null) "GPS" else "GPS ±${Math.round(meters)} m"

    /** "Next: account for 300 h". */
    fun nextAccount(hours: BigDecimal) = "Next: account for ${h(hours)} h"
    const val NEXT = "Next"

    // Opening report (no starting reading yet)
    const val OPENING_TITLE = "First reading for this machine"
    const val OPENING_BODY = "This machine has no starting reading yet. Record the meter now; the next report counts the hours from it."
    const val SUBMIT_OPENING = "Submit the reading"

    // Rejected report: the same reading, a new split
    fun rejected(reason: String?) = "Rejected" + (reason?.takeIf { it.isNotBlank() }?.let { ": $it" } ?: "") + ". Split the same reading again."

    // Step 2
    const val ACCOUNTED = "Accounted for"
    fun ofTotal(hours: BigDecimal) = "/ ${h(hours)} h"
    fun left(hours: BigDecimal) = "${h(hours)} h still to account for"
    fun over(hours: BigDecimal) = "${h(hours)} h more than the meter shows"
    const val ALL_ACCOUNTED = "All hours accounted for"
    const val CUSTOMERS = "Customers (from hours they bought)"
    const val NON_PRODUCTIVE = "Non-productive (reason needed)"
    const val ADD_CUSTOMER = "+ Customer"
    const val ADD_NON_PRODUCTIVE = "+ Non-productive"
    const val CAP_FOOTER = "A customer can only get hours they have bought and that are usable."
    const val NO_CUSTOMER_HOURS = "No customer has usable hours on this phone. Sync, or account for the hours as non-productive."
    const val CHOOSE_CUSTOMER = "Customer"
    const val CHOOSE_REASON = "Reason"
    const val HOURS = "Hours"
    const val WHAT_HAPPENED = "What happened (required)"
    const val REMOVE = "Remove"
    const val DONE = "Done"

    /** "EX-01 · 1,210 → 1,510". */
    fun splitHeader(code: String, from: BigDecimal, to: BigDecimal) = "$code · ${h(from)} → ${h(to)}"

    /** "Available 140 h · after this 20 h". */
    fun available(available: BigDecimal, after: BigDecimal) = "Available ${h(available)} h · after this ${h(after)} h"

    /** "Review — 15 h left to account for", "Review". */
    fun reviewButton(left: BigDecimal) = if (left.signum() > 0) "Review — ${h(left)} h left to account for" else "Review"

    // Step 3
    fun readings(from: String, to: String) = "$from h → $to h"
    fun period(from: String?, to: String) = (if (from != null) "$from → $to" else to) + " · photo + GPS"
    fun productive(hours: BigDecimal) = "PRODUCTIVE · ${h(hours)} h"
    fun nonProductive(hours: BigDecimal) = "NON-PRODUCTIVE · ${h(hours)} h"
    const val TOTAL = "Total"
    fun matches(hours: BigDecimal) = "${h(hours)} h ✓ matches meter"
    fun approvalNote(customerHours: BigDecimal) =
        "The owner or manager approves this report. Until then the ${h(customerHours)} customer hours are reserved; on approval they come off each customer’s purchased hours."
    const val NOTE = "Note for the approver (optional)"
    const val SUBMIT = "Submit for approval"
    const val SUBMITTING = "Submitting…"
    const val QUEUED = "Saved on this phone. It is sent when you are online."
    const val OUTBOX = "Machine report"
    const val OUTBOX_INVOICE_PAYMENT = "Credit invoice payment"

    // Status of a machine
    fun state(s: ReportState): String = when (s) {
        ReportState.OPENING -> "First reading needed"
        ReportState.AWAITING_APPROVAL -> "Awaiting approval"
        ReportState.REJECTED -> "Rejected · redo the split"
        ReportState.DUE -> "Report due"
        ReportState.UP_TO_DATE -> "Up to date"
    }

    /** "2 due" on the home tile; null when nothing is due. */
    fun dueBadge(count: Int): String? = if (count > 0) "$count due" else null

    /** "2 machines", "1 machine", "None". */
    fun machines(count: Int): String = when (count) {
        0 -> "None"
        1 -> "1 machine"
        else -> "$count machines"
    }

    /** "EX-01 report · 300 h". */
    fun recentReport(code: String, hours: BigDecimal?) = "$code report" + (hours?.let { " · ${h(it)} h" } ?: "")

    /** Server refusals of a MACHINE_REPORT or CREDIT_INVOICE_PAYMENT kept for review (sync status, Inbox). */
    fun conflict(code: String?): String? = when (code) {
        "MACHINE_NOT_ASSIGNED" -> "This machine is no longer assigned to you. The report is kept for review."
        "MACHINE_NOT_FOUND" -> "This machine is no longer on record. The report is kept for review."
        "REPORT_PENDING" -> "Another report on this machine waits for approval. Send this one after it is decided."
        "REPORT_ID_CONFLICT" -> "This report was already sent with other details. It is kept for review."
        "BASELINE_REQUIRED" -> "This machine has no starting reading yet. The office sets it first; the report is kept for review."
        "READING_NOT_HIGHER" -> "The new reading is below the machine's last reading. The report is kept for review."
        "NOTHING_TO_REPORT" -> "The reading is the same as the last one, so there is nothing to report."
        "REPORT_SUM_MISMATCH" -> "The hours do not add up to the meter difference. Redo the split."
        "HOURS_NOT_AVAILABLE" -> "A customer no longer has enough usable hours. Redo the split."
        "HOURS_DISABLED" -> "Your company has switched off customer hours, so customer lines were not accepted."
        "REASON_INVALID", "REASON_NOT_FOUND" -> "A reason you chose is no longer in use. Redo the split."
        "CUSTOMER_NOT_FOUND" -> "A customer you chose is no longer on record. Redo the split."
        "CAPTURE_REJECTED" -> "The meter reading was not accepted. Take the reading again."
        "CAPTURE_ALREADY_REPORTED" -> "This reading already has a report."
        "CORRECTS_INVALID" -> "The rejected report could not be corrected. The report is kept for review."
        "HOURS_PRECISION" -> "The hours have more decimals than the meter shows."
        "DUPLICATE_CUSTOMER_LINE" -> "A customer appears twice. Redo the split."
        "INVOICE_PAID" -> "This invoice is already paid. The payment is kept for review."
        "INVOICE_OVERPAYMENT" -> "The payment is more than the invoice still owes. It is kept for review."
        "INVOICE_CANCELLED" -> "This invoice was cancelled. The payment is kept for review."
        "INVOICE_NOT_FOUND" -> "This invoice is no longer on record. The payment is kept for review."
        "PAYMENT_NOT_PERMITTED" -> "Bank and mobile-money payments are recorded by the office."
        else -> null
    }

    private fun h(v: BigDecimal) = MachineReportRules.formatHours(v)
}
