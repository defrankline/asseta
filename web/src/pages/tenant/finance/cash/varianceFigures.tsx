import type { CashVarianceDto } from '../../../../api/custodyTypes';
import { MoneyText } from '../../../../components/display/MoneyText';
import { hoursText } from '../../hours/hoursDisplay';

export type VarianceFigureKey = 'declared_amount' | 'received_amount' | 'amount';

/** A variance figure in its own unit: money, or hours for a customer-hour difference. */
export function varianceFigure(v: CashVarianceDto, key: VarianceFigureKey, strong = false) {
  if (v.unit === 'HOURS') {
    const text = hoursText(v[key]);
    return strong ? <strong>{text}</strong> : text;
  }
  return <MoneyText amount={v[key]} currency={v.currency} strong={strong} />;
}
