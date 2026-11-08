import { Alert, Box, Link, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { AdjustmentRequestDto } from '../../../../api/adjustmentTypes';
import { StaticTable } from '../../../../components/data/StaticTable';
import { KeyValueGrid, type KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { hireInvoiceDetailPath } from '../../../../navigation/routes';
import { caseDetailPath } from '../../../../navigation/routes';
import { hoursPurchasePath } from '../../../../navigation/hoursRoutes';
import { hoursText } from '../../hours/hoursDisplay';
import {
  ADJUSTMENT_ERROR_HINTS,
  adjustedRecordPath,
  SETTLEMENT_LABELS,
  TREATMENT_LABELS,
} from './adjustmentDisplay';

/** Link to a record named by the ledger, or its plain reference when it has no page. */
export function RecordLink({
  type,
  id,
  label,
}: {
  type: string;
  id: string;
  label: string | null;
}) {
  const text = label ?? 'Open the record';
  const to = adjustedRecordPath(type, id);
  return to === null ? (
    <>{label ?? '—'}</>
  ) : (
    <Link component={RouterLink} to={to}>
      {text}
    </Link>
  );
}

const str = (v: unknown): string | null => (typeof v === 'string' && v !== '' ? v : null);

const HOURS_EFFECTS: readonly [string, string][] = [
  ['lot_hours_before', 'Hours on the machine before'],
  ['lot_hours_after', 'Hours on the machine after'],
  ['hours_refunded', 'Hours refunded'],
  ['purchase_remaining', 'Purchase hours remaining'],
  ['unused_hours_removed', 'Hours deactivated'],
  ['used_hours', 'Hours already used'],
  ['used_hours_kept', 'Used hours kept'],
];

const MONEY_EFFECTS: readonly [string, string][] = [
  ['value', 'Value'],
  ['money_owed', 'Money owed'],
  ['hire_allocations_released', 'Released from invoices'],
  ['money_released_to_credit', 'Returned to credit'],
  ['released', 'Released'],
  ['payment_amount', 'Payment amount'],
  ['custody_balance_after', 'Custody balance after'],
  ['customer_balance', 'Customer balance after'],
];

interface PurchaseEffect {
  purchase_id: string;
  purchase_number: string;
  unused_hours: string;
  used_hours: string;
  money_owed: string;
}

const purchasesOf = (effects: Record<string, unknown>): PurchaseEffect[] =>
  Array.isArray(effects.purchases) ? (effects.purchases as PurchaseEffect[]) : [];

/** What approving will do (forecast while proposed) or what approval did. */
export function RequestEffects({ request: r }: { request: AdjustmentRequestDto }) {
  const e = r.effects;
  const refused = str(e.refused);
  if (refused !== null) {
    return (
      <Alert severity="warning">
        As things stand this cannot be approved: {ADJUSTMENT_ERROR_HINTS[refused] ?? refused}
      </Alert>
    );
  }
  const currency = r.currency;
  const money = (v: string) =>
    currency === null ? v : <MoneyText amount={v} currency={currency} />;
  const items: KeyValueItem[] = [
    ...HOURS_EFFECTS.flatMap(([key, label]) => {
      const v = str(e[key]);
      return v === null ? [] : [{ label, value: hoursText(v) }];
    }),
    ...MONEY_EFFECTS.flatMap(([key, label]) => {
      const v = str(e[key]);
      return v === null ? [] : [{ label, value: money(v) }];
    }),
  ];
  const settlement = str(e.settlement);
  if (settlement === 'CREDIT' || settlement === 'PAY_OUT') {
    items.push({ label: 'Settlement', value: SETTLEMENT_LABELS[settlement] });
  }
  const treatment = str(e.treatment);
  if (treatment !== null) {
    items.push({
      label: 'Used hours are',
      value: TREATMENT_LABELS[treatment] ?? treatment,
    });
  }
  const invoiceId = str(e.recovery_invoice_id);
  if (invoiceId !== null) {
    items.push({
      label: 'Recovery invoice',
      value: (
        <Link component={RouterLink} to={hireInvoiceDetailPath(invoiceId)}>
          {str(e.recovery_invoice_number) ?? 'Open the invoice'}
        </Link>
      ),
    });
  }
  const caseId = str(e.case_id);
  if (caseId !== null) {
    items.push({
      label: 'Investigation case',
      value: (
        <Link component={RouterLink} to={caseDetailPath(caseId)}>
          Open the case
        </Link>
      ),
    });
  }
  const purchases = purchasesOf(e);
  if (items.length === 0 && purchases.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        Nothing further to show.
      </Typography>
    );
  }
  return (
    <Box className="flex flex-col gap-3">
      <KeyValueGrid columns={3} items={items} />
      {purchases.length > 0 && (
        <StaticTable
          ariaLabel="Purchases affected"
          rows={purchases}
          getRowId={(p) => p.purchase_id}
          columns={[
            {
              id: 'p',
              header: 'Purchase',
              render: (p) => (
                <Link component={RouterLink} to={hoursPurchasePath(p.purchase_id)}>
                  {p.purchase_number}
                </Link>
              ),
            },
            {
              id: 'un',
              header: 'Hours deactivated',
              align: 'right',
              render: (p) => hoursText(p.unused_hours),
            },
            {
              id: 'us',
              header: 'Hours already used',
              align: 'right',
              render: (p) => hoursText(p.used_hours),
            },
            { id: 'o', header: 'Money owed', align: 'right', render: (p) => money(p.money_owed) },
          ]}
        />
      )}
    </Box>
  );
}
