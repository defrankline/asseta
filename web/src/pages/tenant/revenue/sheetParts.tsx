import { Box, Chip, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { SheetFlag, SheetFlagRefDto, SheetJobDto, SheetMoneyDto } from '../../../api/types';
import { MoneyText } from '../../../components/display/MoneyText';
import {
  dailySheetDayPath,
  engineHoursMachinePath,
  jobDetailPath,
} from '../../../navigation/routes';
import { isZeroDecimal } from '../../../utils/money';
import { SHEET_FLAG_LABELS } from './revenueDisplay';
import { flagRecordPath } from './sheetLinks';

const FLAG_COLOR: Readonly<Record<SheetFlag, 'warning' | 'error' | 'info'>> = {
  MISSING_DAILY_REPORT: 'warning',
  UNEXPLAINED_HOURS: 'warning',
  ENGINE_ON_WITHOUT_JOB: 'warning',
  FUEL_ABOVE_NORM: 'warning',
  REVENUE_DIFFERENCE: 'error',
};

interface RowFlagsProps {
  flags: readonly SheetFlag[];
  machineId: string;
  day: string;
}

/** Flag chips of a sheet row: unexplained hours open the ledger, the rest the machine-day's records. */
export function RowFlags({ flags, machineId, day }: RowFlagsProps) {
  if (flags.length === 0) return <>—</>;
  return (
    <Box className="flex flex-wrap gap-1">
      {[...new Set(flags)].map((f) => (
        <Chip
          key={f}
          size="small"
          color={FLAG_COLOR[f]}
          label={SHEET_FLAG_LABELS[f]}
          component={RouterLink}
          to={
            f === 'UNEXPLAINED_HOURS'
              ? engineHoursMachinePath(machineId)
              : dailySheetDayPath(machineId, day)
          }
          clickable
          onClick={(e: React.MouseEvent) => {
            e.stopPropagation();
          }}
        />
      ))}
    </Box>
  );
}

/** Flag chips of one machine-day, each linking to its own record. */
export function RecordFlags({
  flags,
  refs,
  machineId,
}: {
  flags: readonly SheetFlag[];
  refs: readonly SheetFlagRefDto[];
  machineId: string;
}) {
  const withRecord = new Set(refs.map((r) => r.flag));
  const loose = [...new Set(flags)].filter((f) => !withRecord.has(f));
  if (refs.length === 0 && loose.length === 0)
    return (
      <Typography variant="body2" color="text.secondary">
        No flags for this day.
      </Typography>
    );
  return (
    <Box className="flex flex-wrap gap-1">
      {refs.map((r) => (
        <Chip
          key={`${r.flag}:${r.record_id}`}
          size="small"
          color={FLAG_COLOR[r.flag]}
          label={SHEET_FLAG_LABELS[r.flag]}
          component={RouterLink}
          to={flagRecordPath(r, machineId)}
          clickable
        />
      ))}
      {loose.map((f) => (
        <Chip
          key={f}
          size="small"
          color={FLAG_COLOR[f]}
          label={SHEET_FLAG_LABELS[f]}
          component={RouterLink}
          to={engineHoursMachinePath(machineId)}
          clickable
        />
      ))}
    </Box>
  );
}

/** Money of one machine-day, one line per currency (never added across currencies). */
export function MoneyLines({ money }: { money: readonly SheetMoneyDto[] }) {
  if (money.length === 0) return <>—</>;
  return (
    <Box className="flex flex-col gap-0.5">
      {money.map((m) => (
        <Typography key={m.currency} variant="body2" component="div" sx={{ whiteSpace: 'nowrap' }}>
          <MoneyText amount={m.expected} currency={m.currency} /> expected ·{' '}
          <MoneyText amount={m.attributed} currency={m.currency} /> attributed
          {!isZeroDecimal(m.in_progress) && (
            <>
              {' '}
              · <MoneyText amount={m.in_progress} currency={m.currency} /> in progress
            </>
          )}
          {!isZeroDecimal(m.difference) && (
            <>
              {' '}
              · <MoneyText amount={m.difference} currency={m.currency} strong /> difference
            </>
          )}
        </Typography>
      ))}
    </Box>
  );
}

/** Job numbers (linked) with their customers. */
export function JobLinks({ jobs }: { jobs: readonly SheetJobDto[] }) {
  if (jobs.length === 0) return <>—</>;
  return (
    <Box className="flex flex-col gap-0.5">
      {jobs.map((j) => (
        <Typography key={j.job_id} variant="body2" component="div">
          <RouterLink
            to={jobDetailPath(j.job_id)}
            onClick={(e) => {
              e.stopPropagation();
            }}
          >
            {j.job_number ?? 'Job'}
          </RouterLink>
          {j.customer_name != null && ` · ${j.customer_name}`}
        </Typography>
      ))}
    </Box>
  );
}
