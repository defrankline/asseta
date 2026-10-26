import { Box, TextField } from '@mui/material';
import type { AmountByCurrencyDto } from '../../../api/oversightTypes';
import { MoneyText } from '../../../components/display/MoneyText';

/** "n" plus amounts per currency under it. */
export function AmountsCell({
  count,
  totals,
}: {
  count: number;
  totals: readonly AmountByCurrencyDto[];
}) {
  if (count === 0) return <span>0</span>;
  return (
    <Box>
      <span>{count}</span>
      {totals.map((t) => (
        <Box key={t.currency} sx={{ fontSize: 12, color: 'text.secondary' }}>
          <MoneyText amount={t.amount} currency={t.currency} />
        </Box>
      ))}
    </Box>
  );
}

/** Two date fields for a period (empty = the server's default). */
export function PeriodFields({
  from,
  to,
  onFrom,
  onTo,
}: {
  from: string;
  to: string;
  onFrom: (v: string) => void;
  onTo: (v: string) => void;
}) {
  return (
    <>
      <TextField
        size="small"
        type="date"
        label="From"
        value={from}
        onChange={(e) => {
          onFrom(e.target.value);
        }}
        slotProps={{ inputLabel: { shrink: true } }}
      />
      <TextField
        size="small"
        type="date"
        label="To"
        value={to}
        onChange={(e) => {
          onTo(e.target.value);
        }}
        slotProps={{ inputLabel: { shrink: true } }}
      />
    </>
  );
}
