import { Box } from '@mui/material';
import { formatMoney } from '../../utils/money';

interface MoneyTextProps {
  /** Decimal string from the API (never a float). */
  amount: string;
  currency: string;
  /** Emphasise (bold) the amount. */
  strong?: boolean;
}

/** Displays an API money string using the currency's minor units, tabular figures. */
export function MoneyText({ amount, currency, strong = false }: MoneyTextProps) {
  return (
    <Box
      component="span"
      sx={{
        fontVariantNumeric: 'tabular-nums',
        whiteSpace: 'nowrap',
        fontWeight: strong ? 600 : 'inherit',
      }}
    >
      {formatMoney(amount, currency)}
    </Box>
  );
}
