import { Box, Chip } from '@mui/material';
import type { DailyReportDto } from '../../../../api/allocationTypes';
import { StatusChip } from '../../../../components/display/StatusChip';
import { REPORT_STATUS_LABELS, REPORT_STATUS_TONES } from './allocationDisplay';

/** Review status with the late and repeat-report flags. */
export function ReportChips({ report }: { report: DailyReportDto }) {
  return (
    <Box className="flex flex-wrap gap-1">
      <StatusChip
        status={report.status}
        tones={REPORT_STATUS_TONES}
        label={REPORT_STATUS_LABELS[report.status]}
      />
      {report.is_late && <Chip size="small" color="warning" variant="outlined" label="Late" />}
      {report.is_duplicate && (
        <Chip size="small" color="warning" variant="outlined" label="Duplicate" />
      )}
    </Box>
  );
}
