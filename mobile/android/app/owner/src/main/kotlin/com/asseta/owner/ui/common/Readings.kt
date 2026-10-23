package com.asseta.owner.ui.common

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.MeterCaptureDto
import com.asseta.core.model.owner.PhotoUrlDto
import com.asseta.core.ui.theme.AssetaType
import com.asseta.core.ui.theme.palette
import com.asseta.owner.data.ActionResult
import java.time.ZoneId

/** Meter reading wording shared with iOS (`ReadingRow`). */
object ReadingText {
    fun title(c: MeterCaptureDto): String = "${OwnerFormat.humanize(c.kind)} · ${c.reading.value.toPlainString()}"

    /** "21 Oct 2026, 14:05 · Ocr · corrected by hand · OCR 93% · GPS ok" */
    fun detail(c: MeterCaptureDto, zone: ZoneId): String = buildString {
        append(OwnerFormat.dateTime(c.capturedAt, zone))
        append(" · ").append(OwnerFormat.humanize(c.captureMode))
        if (c.manuallyCorrected) append(" · corrected by hand")
        c.ocrConfidence?.let { append(" · OCR ${(it * 100).toInt()}%") }
        append(" · GPS ").append(OwnerFormat.humanize(c.gpsStatus).lowercase())
    }

    const val PHOTO_FOOTER = "Evidence photos are downloaded only when you open them and are never saved on this phone."
}

/** One meter reading with its state and an on-demand evidence photo. */
@Composable
fun ReadingRow(c: MeterCaptureDto, zone: ZoneId, photoOnline: Boolean, fetchPhoto: suspend (String) -> ActionResult<PhotoUrlDto>) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(ReadingText.title(c), style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            StatusPill(OwnerFormat.humanize(c.state), if (c.state == "ACCEPTED") OwnerColors.Live else OwnerColors.Warning)
        }
        Text(ReadingText.detail(c, zone), style = AssetaType.caption, color = palette.secondaryText)
        c.photoAttachmentId?.let { id -> EvidencePhoto("evidence photo", photoOnline) { fetchPhoto(id.toString()) } }
    }
}
