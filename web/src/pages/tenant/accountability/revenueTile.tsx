import { PERMISSIONS } from '../../../access/permissionCodes';
import type { AccountabilitySummaryDto } from '../../../api/custodyTypes';
import { MoneyText } from '../../../components/display/MoneyText';
import { RECORD_LIST_ROUTES, recordPath } from '../../../navigation/recordRoutes';
import { ROUTES } from '../../../navigation/routes';
import { withQuery } from '../../../navigation/urlFilters';
import { formatMoney } from '../../../utils/money';
import {
  asList,
  asNumber,
  asRecord,
  asText,
  count,
  linkIf,
  perCurrency,
  type Can,
  type Tile,
} from './tileKit';

/** Revenue differences (DEC-031 R3): to explain, awaiting a decision, amounts per currency, latest. */
export function revenueDifferencesTile(s: AccountabilitySummaryDto, can: Can): Tile | null {
  if (!s.revenue_differences) return null;
  const r = asRecord(s.revenue_differences);
  const ok = can(PERMISSIONS.tenantRevenueRead);
  const list = (status: string) =>
    linkIf(
      ok,
      withQuery(ROUTES.tenantRevenueDifferences, { status }),
      RECORD_LIST_ROUTES.REVENUE_DIFFERENCE,
    );
  const open = asNumber(r.open);
  const awaiting = asNumber(r.awaiting_decision);
  const oldest = r.oldest_open_days;
  const amounts = asList(r.amounts).map((a) => ({
    currency: asText(a.currency, ''),
    count: asNumber(a.count),
    amount: asText(a.amount),
  }));
  return {
    key: 'revenue_differences',
    title: 'Revenue differences',
    value: open + awaiting,
    valueText: String(open + awaiting),
    to: list('OPEN'),
    description:
      oldest === null || oldest === undefined
        ? 'Engine hours not matched by money, to explain'
        : `Oldest open ${String(asNumber(oldest))} days`,
    rows: [
      count('open', 'To explain', open, list('OPEN')),
      count('awaiting', 'Explanations awaiting decision', awaiting, list('EXPLANATION_PROPOSED')),
      ...perCurrency('amounts', amounts, list('')),
      count(
        'explained',
        `Explained (last ${String(asNumber(r.window_days))} days)`,
        asNumber(r.explained_in_window),
        list('EXPLAINED'),
      ),
      count(
        'confirmed',
        `Confirmed (last ${String(asNumber(r.window_days))} days)`,
        asNumber(r.confirmed_in_window),
        list('CONFIRMED'),
      ),
      ...asList(r.items)
        .slice(0, 5)
        .map((i) => ({
          key: asText(i.id, ''),
          label: `${asText(i.machine_code, '')} · ${asText(i.local_from, '')}`,
          value: <MoneyText amount={asText(i.difference)} currency={asText(i.currency, '')} />,
          valueText: formatMoney(asText(i.difference), asText(i.currency, '')),
          to: ok ? recordPath('REVENUE_DIFFERENCE', asText(i.id, '')) : undefined,
        })),
    ],
  };
}
