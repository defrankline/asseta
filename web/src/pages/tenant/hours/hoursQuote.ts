import type { HoursQuoteDto } from '../../../api/hoursTypes';
import { compareDecimal, formatMoney, isZeroDecimal, sumDecimals } from '../../../utils/money';

export const QUOTE_DEBOUNCE_MS = 400;
export const NO_RATE_QUOTE_TEXT =
  'No hourly rate is set for this machine type yet; the office sets it.';

/** formatMoney without a zero fraction: 'TZS 570,000' rather than 'TZS 570,000.00'. */
export function money(amount: string, currency: string): string {
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

function minus(a: string, b: string): string {
  return sumDecimals([a, b.startsWith('-') ? b.slice(1) : `-${b}`]);
}

/**
 * "Paid TZS 570,000 of TZS 570,000 · Balance TZS 0" plus Fully paid / Part paid / Not paid yet. `paid` counts every
 * line; `credit` is the Credit line's part of it (paid later on its invoice), so a sale with credit is never "Fully
 * paid": "Paid TZS 500,000 · on credit TZS 450,000" (nothing in money: "On credit …"; still owed: "… · balance …"),
 * the same wording as the phones.
 */
export function paidSummary(
  paid: string,
  total: string,
  currency: string,
  credit = '0',
): { line: string; status: string; over: boolean } {
  const balance = minus(total, paid);
  const over = compareDecimal(balance, '0') < 0;
  if (compareDecimal(credit, '0') > 0) {
    const cash = minus(paid, credit);
    const hasMoney = compareDecimal(cash, '0') > 0;
    const line = `Paid ${money(hasMoney ? cash : '0', currency)} + ${money(credit, currency)} on credit of ${money(total, currency)} · Balance ${money(over ? '0' : balance, currency)}`;
    const status = [
      hasMoney ? `Paid ${money(cash, currency)}` : null,
      `${hasMoney ? 'on credit' : 'On credit'} ${money(credit, currency)}`,
      compareDecimal(balance, '0') > 0 ? `balance ${money(balance, currency)}` : null,
    ]
      .filter((x) => x !== null)
      .join(' · ');
    return { line, status, over };
  }
  const line = `Paid ${money(paid, currency)} of ${money(total, currency)} · Balance ${money(balance, currency)}`;
  const status = isZeroDecimal(paid)
    ? 'Not paid yet'
    : compareDecimal(balance, '0') <= 0
      ? 'Fully paid'
      : `Part paid (balance ${money(balance, currency)})`;
  return { line, status, over };
}

/** What is left to pay, or '' when unknown or nothing is left. */
export function remainingBalance(paid: string, total: string): string {
  if (total === '') return '';
  const neg = paid.startsWith('-') ? paid.slice(1) : `-${paid}`;
  const balance = sumDecimals([total, neg]);
  return compareDecimal(balance, '0') > 0 ? balance.replace(/\.0+$/, '') : '';
}
