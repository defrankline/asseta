import type { HoursQuoteDto } from '../../../api/hoursTypes';
import { formatMoney, isZeroDecimal } from '../../../utils/money';

export const QUOTE_DEBOUNCE_MS = 400;
export const NO_RATE_QUOTE_TEXT =
  'No hourly rate is set for this machine type yet; the office sets it.';

/** formatMoney without a zero fraction: 'TZS 570,000' rather than 'TZS 570,000.00'. */
function money(amount: string, currency: string): string {
  return formatMoney(amount, currency).replace(/\.0+$/, '');
}

function plain(amount: string, currency: string): string {
  return money(amount, currency).slice(currency.length + 1);
}

function trimHours(hours: string): string {
  return hours.includes('.') ? hours.replace(/\.?0+$/, '') : hours;
}

/** "Total: TZS 513,000 (6 h × 95,000/h, less 10% discount)". */
export function quoteText(q: HoursQuoteDto): string {
  const discount = isZeroDecimal(q.discount_percent)
    ? ''
    : `, less ${trimHours(q.discount_percent)}% discount`;
  return `Total: ${money(q.amount, q.currency)} (${trimHours(q.hours)} h × ${plain(q.hourly_rate, q.currency)}/h${discount})`;
}
