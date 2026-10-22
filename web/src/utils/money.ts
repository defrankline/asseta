/**
 * Money helpers for decimal strings returned by the API (fixed-point, up to 4 dp).
 * Amounts are never converted to floating point: parsing, rounding and comparison use BigInt
 * over a scaled integer. Formatting only converts the already-rounded integer part for grouping.
 */

/** Scale used by the API for monetary decimals. */
export const API_MONEY_SCALE = 4;

/** Minor units per ISO 4217 currency used by Asseta; unknown currencies fall back to Intl, then 2. */
const MINOR_UNITS: Readonly<Record<string, number>> = { TZS: 2, USD: 2, KES: 2, EUR: 2, UGX: 0 };

/** Currencies offered in selectors; TZS is a seeded option, not a business rule. */
export const SUPPORTED_CURRENCIES = ['TZS', 'USD', 'KES', 'UGX', 'EUR'] as const;

const DECIMAL_RE = /^([+-])?(\d+)(?:\.(\d+))?$/;

export function minorUnits(currency: string): number {
  const known = MINOR_UNITS[currency];
  if (known !== undefined) return known;
  try {
    const digits = new Intl.NumberFormat('en', { style: 'currency', currency }).resolvedOptions()
      .maximumFractionDigits;
    return digits ?? 2;
  } catch {
    return 2;
  }
}

export function isDecimalString(value: string): boolean {
  return DECIMAL_RE.test(value.trim());
}

interface ScaledDecimal {
  /** Integer value of amount * 10^scale. */
  units: bigint;
  scale: number;
}

/** Parse a decimal string exactly into a scaled BigInt. Returns null when not a plain decimal. */
export function parseDecimal(value: string): ScaledDecimal | null {
  const m = DECIMAL_RE.exec(value.trim());
  if (m === null) return null;
  const [, sign, int = '0', frac = ''] = m;
  const units = BigInt(`${int}${frac}` || '0');
  return { units: sign === '-' ? -units : units, scale: frac.length };
}

const TEN = 10n;

function pow10(n: number): bigint {
  return TEN ** BigInt(n);
}

/** Rescale with half-up rounding (away from zero), the same rule displayed amounts follow. */
function rescale(d: ScaledDecimal, scale: number): bigint {
  if (scale >= d.scale) return d.units * pow10(scale - d.scale);
  const divisor = pow10(d.scale - scale);
  const negative = d.units < 0n;
  const abs = negative ? -d.units : d.units;
  let q = abs / divisor;
  if ((abs % divisor) * 2n >= divisor) q += 1n;
  return negative ? -q : q;
}

/**
 * Round a decimal string to `scale` digits (half-up) and return it as a plain decimal string,
 * e.g. roundDecimal('10.005', 2) === '10.01'.
 */
export function roundDecimal(value: string, scale: number): string {
  const d = parseDecimal(value);
  if (d === null) throw new Error(`Not a decimal: ${value}`);
  const units = rescale(d, scale);
  const negative = units < 0n;
  const digits = (negative ? -units : units).toString().padStart(scale + 1, '0');
  const int = digits.slice(0, digits.length - scale);
  const frac = scale > 0 ? `.${digits.slice(digits.length - scale)}` : '';
  return `${negative && units !== 0n ? '-' : ''}${int}${frac}`;
}

/** Exact comparison of two decimal strings: -1, 0 or 1. */
export function compareDecimal(a: string, b: string): -1 | 0 | 1 {
  const da = parseDecimal(a);
  const db = parseDecimal(b);
  if (da === null || db === null) throw new Error('compareDecimal expects decimal strings');
  const scale = Math.max(da.scale, db.scale);
  const x = rescale(da, scale);
  const y = rescale(db, scale);
  return x === y ? 0 : x < y ? -1 : 1;
}

export function isZeroDecimal(value: string): boolean {
  const d = parseDecimal(value);
  return d !== null && d.units === 0n;
}

const groupers = new Map<string, Intl.NumberFormat>();

function groupInteger(int: bigint, locale: string): string {
  let fmt = groupers.get(locale);
  if (fmt === undefined) {
    fmt = new Intl.NumberFormat(locale, { maximumFractionDigits: 0, useGrouping: true });
    groupers.set(locale, fmt);
  }
  return fmt.format(int);
}

/**
 * Format an API money string for display with the currency's minor units, e.g.
 * formatMoney('1234567.8950', 'TZS') === 'TZS 1,234,567.90'; formatMoney('1500.5', 'UGX') === 'UGX 1,501'.
 * Invalid input is shown verbatim so it is never silently misrepresented.
 */
export function formatMoney(amount: string, currency: string, locale = 'en-US'): string {
  const d = parseDecimal(amount);
  if (d === null) return `${currency} ${amount}`;
  const scale = minorUnits(currency);
  const units = rescale(d, scale);
  const negative = units < 0n;
  const abs = negative ? -units : units;
  const divisor = pow10(scale);
  const int = groupInteger(abs / divisor, locale);
  const frac = scale > 0 ? `.${(abs % divisor).toString().padStart(scale, '0')}` : '';
  return `${negative ? '-' : ''}${currency} ${int}${frac}`;
}

/**
 * A form-entered amount for a review step. With a currency it is formatted like formatMoney; with none
 * (the server applies the tenant base currency) the digits are only grouped, never re-scaled, because the
 * minor units are unknown here: formatEnteredMoney('200000', '') === '200,000 (tenant base currency)'.
 */
export function formatEnteredMoney(amount: string, currency: string, locale = 'en-US'): string {
  if (currency !== '') return formatMoney(amount, currency, locale);
  const m = DECIMAL_RE.exec(amount.trim());
  if (m === null) return `${amount} (tenant base currency)`;
  const [, sign = '', int = '0', frac] = m;
  const grouped = groupInteger(BigInt(int), locale);
  return `${sign === '-' ? '-' : ''}${grouped}${frac === undefined ? '' : `.${frac}`} (tenant base currency)`;
}

/** Format a decimal percentage string such as '12.5000' as '12.5%'. */
export function formatPercent(value: string): string {
  const d = parseDecimal(value);
  if (d === null) return `${value}%`;
  const fixed = roundDecimal(value, Math.min(d.scale, 4));
  const trimmed = fixed.includes('.') ? fixed.replace(/0+$/, '').replace(/\.$/, '') : fixed;
  return `${trimmed}%`;
}

/**
 * Exact sum of decimal strings (BigInt, never floats), returned as a plain decimal string with the
 * widest input scale, e.g. sumDecimals(['10.5', '0.25']) === '10.75'. Used only for form checks
 * such as "allocations must not exceed the payment"; displayed totals always come from the API.
 */
export function sumDecimals(values: readonly string[]): string {
  const parsed = values.map((v) => {
    const d = parseDecimal(v);
    if (d === null) throw new Error(`Not a decimal: ${v}`);
    return d;
  });
  const scale = parsed.reduce((m, d) => Math.max(m, d.scale), 0);
  const total = parsed.reduce((acc, d) => acc + rescale(d, scale), 0n);
  const negative = total < 0n;
  const digits = (negative ? -total : total).toString().padStart(scale + 1, '0');
  const int = digits.slice(0, digits.length - scale);
  const frac = scale > 0 ? `.${digits.slice(digits.length - scale)}` : '';
  return `${negative ? '-' : ''}${int}${frac}`;
}

/** Sign of a decimal string: -1, 0 or 1 (e.g. to style a negative outstanding amount). */
export function signOfDecimal(value: string): -1 | 0 | 1 {
  const d = parseDecimal(value);
  if (d === null || d.units === 0n) return 0;
  return d.units < 0n ? -1 : 1;
}

function formatScaled(units: bigint, scale: number): string {
  const negative = units < 0n;
  const digits = (negative ? -units : units).toString().padStart(scale + 1, '0');
  const int = digits.slice(0, digits.length - scale);
  const frac = scale > 0 ? `.${digits.slice(digits.length - scale)}` : '';
  return `${negative && units !== 0n ? '-' : ''}${int}${frac}`;
}

/**
 * Exact product of two decimal strings (BigInt), e.g. multiplyDecimals('2.5', '1000.10') ===
 * '2500.250'. For form checks only (a discount may not exceed quantity × unit price); invoice
 * totals always come from the server.
 */
export function multiplyDecimals(a: string, b: string): string {
  const da = parseDecimal(a);
  const db = parseDecimal(b);
  if (da === null || db === null) throw new Error('multiplyDecimals expects decimal strings');
  return formatScaled(da.units * db.units, da.scale + db.scale);
}
