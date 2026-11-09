import type { MoneyFigureDto } from '../../../../api/custodyTypes';
import { MoneyText } from '../../../../components/display/MoneyText';
import { formatMoney } from '../../../../utils/money';
import type { KpiRow } from '../../dashboard/KpiCard';

/** One row per currency, never added together. */
export function moneyRows(key: string, figure: MoneyFigureDto, label?: string): KpiRow[] {
  return figure.lines.map((l) => ({
    key: `${key}-${l.currency}`,
    label: label === undefined ? `${String(l.count)} in ${l.currency}` : `${label} (${l.currency})`,
    value: <MoneyText amount={l.amount} currency={l.currency} />,
    valueText: `${String(l.count)}, ${formatMoney(l.amount, l.currency)}`,
    to: figure.route,
  }));
}
