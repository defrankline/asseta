import { Box, Button, Typography } from '@mui/material';
import type { AccountabilitySummaryDto } from '../../../../api/custodyTypes';
import { PeriodFields } from '../../oversight/oversightParts';
import { CashGroup } from './CashGroup';
import { CustomerHoursGroup } from './CustomerHoursGroup';
import { ExceptionsGroup } from './ExceptionsGroup';
import { OperationsGroup } from './OperationsGroup';

/** Period picker of the management dashboard (tenant-local days; empty = no limit). */
export function DashboardPeriod({
  from,
  to,
  onFrom,
  onTo,
  onClear,
}: {
  from: string;
  to: string;
  onFrom: (v: string) => void;
  onTo: (v: string) => void;
  onClear: () => void;
}) {
  return (
    <Box className="flex flex-wrap items-center gap-3">
      <PeriodFields from={from} to={to} onFrom={onFrom} onTo={onTo} />
      {(from !== '' || to !== '') && (
        <Button size="small" onClick={onClear}>
          Clear period
        </Button>
      )}
      <Typography variant="body2" color="text.secondary">
        Totals follow the period. Balances and open queues always show the position now.
      </Typography>
    </Box>
  );
}

/** The four groups of guideline section 8; a group the tenant hides or switched off is left out. */
export function ManagementDashboard({ data }: { data: AccountabilitySummaryDto }) {
  const hours = data.hours_section ?? null;
  const ops = data.operations_section ?? null;
  const cash = data.cash_section ?? null;
  const exceptions = data.exceptions_section ?? null;
  if (hours === null && ops === null && cash === null && exceptions === null) return null;
  return (
    <Box className="flex flex-col gap-6">
      {hours !== null && <CustomerHoursGroup section={hours} />}
      {ops !== null && <OperationsGroup section={ops} />}
      {cash !== null && <CashGroup section={cash} />}
      {exceptions !== null && <ExceptionsGroup section={exceptions} />}
    </Box>
  );
}
