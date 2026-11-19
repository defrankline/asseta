import { Stack, Typography } from '@mui/material';
import type { MachineReportDto } from '../../../api/machineReportTypes';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { formatInstantIn } from '../../../utils/time';
import { machineText } from '../shared/names';
import { hoursLabel } from './machineReportDisplay';
import { ReportStatusChip } from './MachineReportParts';
import { formatVisitGap, visitGapFlagged } from './visitDisplay';

/** Report list columns shared by My reports and the approval list. */
export function reportColumns(
  timeZone: string,
  options: {
    submitter: boolean;
    /**
     * Show "Since last visit" (the approval list), flagged in the warning colour over this many hours
     * (CUSTOMER_HOURS `visit_gap_warning_hours`; null = never flag). Undefined: no column.
     */
    visitGapWarningHours?: number | null;
  },
): DataColumn<MachineReportDto>[] {
  const warningHours = options.visitGapWarningHours;
  return [
    { id: 'number', header: 'Report', render: (r) => <strong>{r.report_number}</strong> },
    {
      id: 'machine',
      header: 'Machine',
      render: (r) => machineText(r.machine_code, r.machine_name, r.machine_id),
    },
    {
      id: 'meter',
      header: 'Meter',
      render: (r) => `${hoursLabel(r.start_reading)} → ${hoursLabel(r.end_reading)}`,
    },
    {
      id: 'hours',
      header: 'Hours',
      align: 'right',
      render: (r) => (
        <Stack sx={{ alignItems: 'flex-end' }}>
          <strong>{hoursLabel(r.hours)}</strong>
          <Typography variant="caption" color="text.secondary">
            {hoursLabel(r.customer_hours)} customers · {hoursLabel(r.non_productive_hours)}{' '}
            non-productive
          </Typography>
        </Stack>
      ),
    },
    ...(warningHours === undefined
      ? []
      : [
          {
            id: 'visit',
            header: 'Since last visit',
            render: (r: MachineReportDto) => {
              const flagged = visitGapFlagged(r.since_previous_visit_seconds, warningHours);
              return (
                <Typography
                  variant="body2"
                  color={flagged ? 'warning.main' : 'text.primary'}
                  sx={flagged ? { fontWeight: 600 } : undefined}
                >
                  {formatVisitGap(r.since_previous_visit_seconds)}
                </Typography>
              );
            },
          },
        ]),
    ...(options.submitter
      ? [
          {
            id: 'by',
            header: 'Submitted by',
            render: (r: MachineReportDto) => r.submitted_by_name ?? '—',
          },
        ]
      : []),
    {
      id: 'at',
      header: 'Submitted',
      sortField: 'submitted_at',
      render: (r) => formatInstantIn(r.submitted_at, timeZone),
    },
    {
      id: 'status',
      header: 'Status',
      render: (r) => (
        <Stack spacing={0.5}>
          <ReportStatusChip report={r} />
          {r.status === 'REJECTED' && r.decision_note !== null && (
            <Typography variant="caption" color="text.secondary">
              {r.decision_note}
            </Typography>
          )}
        </Stack>
      ),
    },
  ];
}
