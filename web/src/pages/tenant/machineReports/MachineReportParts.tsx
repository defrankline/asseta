import { Chip, Stack } from '@mui/material';
import type { MachineReportDto } from '../../../api/machineReportTypes';
import { StatusChip } from '../../../components/display/StatusChip';
import { REPORT_STATUS_LABELS, REPORT_STATUS_TONES } from './machineReportDisplay';

/** Status chip of a report, with "Corrected" when a later report replaced a rejected one. */
export function ReportStatusChip({ report }: { report: MachineReportDto }) {
  return (
    <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap' }}>
      <StatusChip
        status={report.status}
        tones={REPORT_STATUS_TONES}
        label={REPORT_STATUS_LABELS[report.status]}
      />
      {report.corrected_by_id != null && <Chip size="small" variant="outlined" label="Corrected" />}
    </Stack>
  );
}
