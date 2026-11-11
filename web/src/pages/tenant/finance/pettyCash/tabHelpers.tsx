import { Box } from '@mui/material';
import { useState } from 'react';
import type { PettyCashFundDto } from '../../../../api/pettyCashTypes';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { FundFilter } from './pettyCashPickers';

export interface TabProps {
  timeZone: string;
  /** The fund page shows the lists of one fund (no fund filter). */
  fundId?: string;
  holds: (fundId: string) => boolean;
  reloadKey: number;
  onChanged: () => void;
  initialStatus?: string | undefined;
}

export const menu = (label: string, view: () => void, extra: RowAction[]) => (
  <RowActionsMenu
    label={label}
    actions={[{ key: 'view', label: 'View details', onClick: view }, ...extra]}
  />
);

export function useFundFilter(fixed: string | undefined) {
  const [fund, setFund] = useState<PettyCashFundDto | null>(null);
  const fundId = fixed ?? fund?.id;
  const filter =
    fixed === undefined ? (
      <Box sx={{ minWidth: 240 }}>
        <FundFilter value={fund} onChange={setFund} />
      </Box>
    ) : null;
  return { fundId, filter };
}
