import { Alert, Stack, Typography } from '@mui/material';
import type { AvailableHoursDto, MachineReportReasonDto } from '../../../api/machineReportTypes';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { hoursLabel } from './machineReportDisplay';
import { accountedFor, meterDifference, type ReportRules, type ReportValues } from './reportForm';

interface ReportReviewProps {
  values: ReportValues;
  rules: ReportRules;
  machineLabel: string;
  customers: readonly AvailableHoursDto[];
  reasons: readonly MachineReportReasonDto[];
  photoAttached: boolean;
}

/** Review & submit: the readings, productive and non-productive lines, and the total check. */
export function ReportReview({
  values,
  rules,
  machineLabel,
  customers,
  reasons,
  photoAttached,
}: ReportReviewProps) {
  const end = rules.fixedReading ?? values.reading.trim();
  const difference = meterDifference(rules, values.reading);
  const customerLines = values.lines.filter((l) => l.kind === 'CUSTOMER');
  const otherLines = values.lines.filter((l) => l.kind === 'NON_PRODUCTIVE');
  const productive = accountedFor(customerLines);
  const customerName = (id: string) =>
    customers.find((c) => c.customer_id === id)?.customer_name ?? id;
  const reasonName = (id: string) => reasons.find((r) => r.id === id)?.name ?? id;
  return (
    <Stack spacing={2}>
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Machine', value: machineLabel },
          {
            label: 'Meter',
            value:
              rules.opening || rules.previous === null
                ? `${hoursLabel(end)} (opening reading)`
                : `${hoursLabel(rules.previous)} → ${hoursLabel(end)}`,
          },
          { label: 'Evidence', value: photoAttached ? 'Photo + GPS' : 'GPS only (no photo)' },
        ]}
      />
      {!rules.opening && (
        <>
          <Typography variant="subtitle2" component="h3">
            Productive · {hoursLabel(productive)}
          </Typography>
          {customerLines.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No customer hours.
            </Typography>
          ) : (
            <KeyValueGrid
              columns={2}
              items={customerLines.map((l) => ({
                label: customerName(l.customer_id),
                value: hoursLabel(l.hours.trim()),
              }))}
            />
          )}
          <Typography variant="subtitle2" component="h3">
            Non-productive · {hoursLabel(accountedFor(otherLines))}
          </Typography>
          {otherLines.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No non-productive hours.
            </Typography>
          ) : (
            <KeyValueGrid
              columns={2}
              items={otherLines.map((l) => ({
                label: reasonName(l.reason_id),
                value: `${hoursLabel(l.hours.trim())} · “${l.note.trim()}”`,
              }))}
            />
          )}
          {difference !== null && (
            <Typography variant="body1" sx={{ fontWeight: 600 }}>
              Total {hoursLabel(accountedFor(values.lines))} · matches the meter
            </Typography>
          )}
        </>
      )}
      {values.note.trim() !== '' && (
        <KeyValueGrid columns={1} items={[{ label: 'Note', value: values.note.trim() }]} />
      )}
      <Alert severity="info">
        {rules.opening
          ? 'The owner or manager approves this reading; it then becomes the starting point of the next report.'
          : `The owner or manager approves this report. Until then the ${hoursLabel(productive)} of customer hours are reserved; on approval they come off each customer’s hours.`}
      </Alert>
    </Stack>
  );
}
