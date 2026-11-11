import { Typography } from '@mui/material';
import { useEffect, useState } from 'react';
import { ApiError } from '../../../api/ApiError';
import type { HoursQuoteDto } from '../../../api/hoursTypes';
import { hoursService } from '../../../api/services/hoursService';
import { useDebouncedValue } from '../../../hooks/useDebouncedValue';
import { parseDecimal, signOfDecimal } from '../../../utils/money';
import { NO_RATE_QUOTE_TEXT, QUOTE_DEBOUNCE_MS, quoteText } from './hoursQuote';

type QuoteState =
  | { key: string; kind: 'ok'; quote: HoursQuoteDto }
  | { key: string; kind: 'error'; message: string };

function isQuotable(key: string): boolean {
  const [m, h] = JSON.parse(key) as [string, string, string];
  return m !== '' && parseDecimal(h) !== null && signOfDecimal(h) > 0;
}

function errorText(err: unknown): string {
  if (err instanceof ApiError && err.code === 'NO_RATE') return NO_RATE_QUOTE_TEXT;
  return `Could not work out the total: ${err instanceof Error ? err.message : String(err)}`;
}

/**
 * Live, debounced price of an hours sale (quoteHoursPurchase), priced by the same rule as the sale.
 * Informational only: a failed quote never blocks saving.
 */
export function HoursQuoteLine({
  machineId,
  hours,
  customerId,
}: {
  machineId: string;
  hours: string;
  /** Empty for a walk-in or while no customer is chosen (no discount). */
  customerId: string;
}) {
  const key = useDebouncedValue(
    JSON.stringify([machineId, hours.trim(), customerId]),
    QUOTE_DEBOUNCE_MS,
  );
  const [state, setState] = useState<QuoteState | null>(null);
  useEffect(() => {
    if (!isQuotable(key)) return;
    const [m, h, c] = JSON.parse(key) as [string, string, string];
    const ctrl = new AbortController();
    hoursService
      .quotePurchase({ machine_id: m, hours: h, customer_id: c || undefined }, ctrl.signal)
      .then(
        (quote) => {
          if (ctrl.signal.aborted) return;
          setState({ key, kind: 'ok', quote });
        },
        (err: unknown) => {
          if (ctrl.signal.aborted) return;
          setState({ key, kind: 'error', message: errorText(err) });
        },
      );
    return () => {
      ctrl.abort();
    };
  }, [key]);
  if (state === null || state.key !== key || !isQuotable(key)) return null;
  if (state.kind === 'error') {
    return (
      <Typography variant="body2" color="warning.main" role="status">
        {state.message}
      </Typography>
    );
  }
  return (
    <Typography variant="body2" sx={{ fontWeight: 600 }} role="status">
      {quoteText(state.quote)}
    </Typography>
  );
}
