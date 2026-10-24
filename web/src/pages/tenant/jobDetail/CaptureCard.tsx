import { Box, Chip, Divider, Paper, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';
import type { ExceptionDto, MeterCaptureDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { CaptureLocationMap } from '../../../components/meter/CaptureLocationMap';
import { CaptureStateChip } from '../../../components/meter/CaptureStateChip';
import { EvidenceKeyValues } from '../../../components/meter/EvidenceKeyValues';
import { EXCEPTION_TYPE_LABELS } from '../../../components/meter/exceptionText';
import { GpsEvidence } from '../../../components/meter/GpsEvidence';
import { TrackerComparison } from '../../../components/meter/TrackerComparison';
import { readTrackerComparison } from '../../../components/meter/trackerComparisonView';
import { formatInstantIn } from '../../../utils/time';
import { CapturePhoto } from './CapturePhoto';
import { humanize } from '../../../utils/text';

const EXCEPTION_STATUS_TONES = {
  OPEN: 'warning',
  EXPLAINED: 'success',
  CONFIRMED: 'info',
} as const;

function clockDifference(device: string, server: string): string {
  const d = Date.parse(device);
  const s = Date.parse(server);
  if (Number.isNaN(d) || Number.isNaN(s)) return '—';
  const secs = Math.round((s - d) / 1000);
  return secs >= 0
    ? `received ${String(secs)} s after device time`
    : `device ahead by ${String(-secs)} s`;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Box className="flex flex-col gap-1">
      <Typography variant="subtitle2" component="h4">
        {title}
      </Typography>
      {children}
    </Box>
  );
}

interface CaptureCardProps {
  capture: MeterCaptureDto;
  findings: readonly ExceptionDto[];
  timeZone: string;
}

/** One meter reading with all of its recorded evidence and the exceptions it raised. */
export function CaptureCard({ capture: c, findings, timeZone }: CaptureCardProps) {
  const comparison = readTrackerComparison(c.tracker_comparison);
  const allowedM = comparison.kind === 'compared' ? comparison.allowedM : null;
  const tracker =
    comparison.kind === 'compared' &&
    comparison.trackerLatitude !== null &&
    comparison.trackerLongitude !== null
      ? {
          latitude: comparison.trackerLatitude,
          longitude: comparison.trackerLongitude,
          accuracyM: comparison.trackerAccuracyM,
        }
      : null;
  return (
    <Paper
      variant="outlined"
      className="p-4"
      aria-label={`${humanize(c.kind)} reading ${c.reading}`}
    >
      <Stack spacing={2}>
        <Box className="flex flex-wrap items-center gap-2">
          <Typography variant="subtitle1" component="h3">
            {humanize(c.kind)} reading · {c.reading}
          </Typography>
          <CaptureStateChip state={c.state} />
          <Chip size="small" variant="outlined" label={`Mode: ${humanize(c.capture_mode)}`} />
          {c.manually_corrected && (
            <Chip size="small" color="warning" label="Manually corrected from OCR" />
          )}
        </Box>
        <KeyValueGrid
          columns={4}
          items={[
            { label: 'Reading', value: <span className="font-mono">{c.reading}</span> },
            { label: 'OCR value', value: c.ocr_value ?? 'No OCR result' },
            {
              label: 'OCR confidence',
              value: c.ocr_confidence === null ? '—' : String(c.ocr_confidence),
            },
            {
              label: 'Policy version',
              value: <span className="font-mono">{c.policy_version}</span>,
            },
            { label: 'Device time', value: formatInstantIn(c.captured_at, timeZone, true) },
            { label: 'Server receive time', value: formatInstantIn(c.received_at, timeZone, true) },
            { label: 'Clock difference', value: clockDifference(c.captured_at, c.received_at) },
            {
              label: 'Photo',
              value: <CapturePhoto attachmentId={c.photo_attachment_id} sha256={c.photo_sha256} />,
            },
          ]}
        />
        <Divider />
        <Box className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Stack spacing={2}>
            <Section title="GPS at reading">
              <GpsEvidence value={{ ...c }} timeZone={timeZone} />
            </Section>
            <Section title="Tracker comparison">
              <TrackerComparison comparison={c.tracker_comparison} timeZone={timeZone} />
            </Section>
          </Stack>
          {c.latitude !== null && c.longitude !== null ? (
            <CaptureLocationMap
              sourceId={`capture-${c.id}`}
              latitude={c.latitude}
              longitude={c.longitude}
              accuracyM={c.accuracy_m}
              allowedM={allowedM}
              tracker={tracker}
            />
          ) : (
            <Typography variant="body2" color="text.secondary">
              No map: this reading has no GPS coordinates.
            </Typography>
          )}
        </Box>
        <Section title={`Findings (${String(findings.length)})`}>
          {findings.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No findings were raised for this reading.
            </Typography>
          ) : (
            <Stack spacing={2}>
              {findings.map((f) => (
                <Box key={f.id} className="flex flex-col gap-1">
                  <Box className="flex flex-wrap items-center gap-2">
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {EXCEPTION_TYPE_LABELS[f.exception_type]}
                    </Typography>
                    <StatusChip
                      status={f.status}
                      tones={EXCEPTION_STATUS_TONES}
                      label={f.status === 'OPEN' ? 'Requires review' : humanize(f.status)}
                    />
                    {f.blocking && <Chip size="small" variant="outlined" label="Blocks billing" />}
                  </Box>
                  <EvidenceKeyValues type={f.exception_type} evidence={f.evidence} columns={3} />
                  {f.review_note !== null && (
                    <Typography variant="body2">
                      <strong>Reviewer note:</strong> {f.review_note}
                    </Typography>
                  )}
                </Box>
              ))}
            </Stack>
          )}
        </Section>
      </Stack>
    </Paper>
  );
}
