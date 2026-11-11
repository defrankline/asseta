import type { PettyCashBalanceDto, PettyCashFundDto } from '../../../../api/pettyCashTypes';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { withErrorCode } from '../../shared/errorHints';
import { PETTY_CASH_ERROR_HINTS } from './pettyCashDisplay';
import { fundLabel } from './pettyCashState';

export const hinted = (err: unknown) => withErrorCode(err, PETTY_CASH_ERROR_HINTS);
export const decimal = { htmlInput: { inputMode: 'decimal' as const } };

export const fundSummary = (
  f: Pick<PettyCashFundDto, 'code' | 'name' | 'currency'>,
  b?: PettyCashBalanceDto | null,
) => (
  <KeyValueGrid
    columns={2}
    items={[
      { label: 'Fund', value: fundLabel(f) },
      ...(b == null
        ? []
        : [
            { label: 'Balance', value: <MoneyText amount={b.balance} currency={b.currency} /> },
            {
              label: 'Available to spend',
              value: <MoneyText amount={b.available_to_spend} currency={b.currency} />,
            },
            {
              label: 'Approved limit',
              value: <MoneyText amount={b.approved_limit} currency={b.currency} />,
            },
          ]),
    ]}
  />
);
