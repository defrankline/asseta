import { Chip } from '@mui/material';
import type { SetURLSearchParams } from 'react-router';
import { formatDate } from '../../../utils/dates';

import { urlPeriod } from './urlPeriod';

/** Shows the period a dashboard figure carried into a list; deleting it clears those filters. */
export function UrlPeriodChip({
  params,
  setParams,
}: {
  params: URLSearchParams;
  setParams: SetURLSearchParams;
}) {
  const { dateFrom, dateTo } = urlPeriod(params);
  if (dateFrom === undefined && dateTo === undefined) return null;
  const label =
    dateFrom !== undefined && dateTo !== undefined
      ? `${formatDate(dateFrom)} to ${formatDate(dateTo)}`
      : dateFrom !== undefined
        ? `From ${formatDate(dateFrom)}`
        : `Until ${formatDate(dateTo ?? '')}`;
  return (
    <Chip
      size="small"
      label={label}
      onDelete={() => {
        const next = new URLSearchParams(params);
        next.delete('date_from');
        next.delete('date_to');
        setParams(next, { replace: true });
      }}
    />
  );
}
