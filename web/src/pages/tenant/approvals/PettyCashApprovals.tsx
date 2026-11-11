import { Alert, Box, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useMyFunds } from '../finance/pettyCash/pettyCashState';
import { MovementsTab } from '../finance/pettyCash/PettyCashTabs';
import { AdjustmentsTab } from '../finance/pettyCash/RecordTabs';

/**
 * Petty cash items waiting for a decision (DEC-033): fundings and top-ups, and fund adjustments.
 * Decided by permission (`tenant.pettycash.approve`); never by the proposer or the fund's holder.
 */
export function PettyCashApprovals() {
  const timeZone = useDisplayTimeZone();
  const [reloadKey, setReloadKey] = useState(0);
  const mine = useMyFunds(reloadKey);
  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  const common = { timeZone, holds: mine.holds, reloadKey, onChanged: reload };
  return (
    <Box className="flex flex-col gap-3">
      <Alert severity="info">
        You never decide your own proposal or money for a fund you hold; those wait for a colleague.
      </Alert>
      <Typography variant="h6" component="h2">
        Fundings and top-ups
      </Typography>
      <MovementsTab {...common} group="fundings" initialStatus="PROPOSED" />
      <Typography variant="h6" component="h2">
        Fund adjustments
      </Typography>
      <AdjustmentsTab {...common} initialStatus="PENDING" />
    </Box>
  );
}
