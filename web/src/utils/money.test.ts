import { describe, expect, it } from 'vitest';
import {
  formatEnteredMoney,
  compareDecimal,
  formatMoney,
  formatPercent,
  isZeroDecimal,
  minorUnits,
  multiplyDecimals,
  roundDecimal,
  signOfDecimal,
  sumDecimals,
} from './money';

describe('money formatting', () => {
  it('uses currency minor units (UGX has 0 decimals)', () => {
    expect(minorUnits('TZS')).toBe(2);
    expect(minorUnits('USD')).toBe(2);
    expect(minorUnits('KES')).toBe(2);
    expect(minorUnits('EUR')).toBe(2);
    expect(minorUnits('UGX')).toBe(0);
    expect(formatMoney('1500.0000', 'UGX')).toBe('UGX 1,500');
    expect(formatMoney('1500.5000', 'UGX')).toBe('UGX 1,501');
    expect(formatMoney('1234567.8950', 'TZS')).toBe('TZS 1,234,567.90');
  });

  it('has no floating point drift on values floats cannot represent', () => {
    // 0.1 + 0.2 style traps and values beyond Number.MAX_SAFE_INTEGER stay exact.
    expect(formatMoney('0.3000', 'USD')).toBe('USD 0.30');
    expect(formatMoney('1.005', 'USD')).toBe('USD 1.01'); // float would give 1.00
    expect(formatMoney('123456789012345678.9950', 'TZS')).toBe('TZS 123,456,789,012,345,679.00');
    expect(formatMoney('-10.0050', 'KES')).toBe('-KES 10.01');
    expect(formatMoney('0.0040', 'EUR')).toBe('EUR 0.00');
  });

  it('shows invalid input verbatim instead of guessing', () => {
    expect(formatMoney('abc', 'TZS')).toBe('TZS abc');
  });

  it('rounds, compares and detects zero exactly', () => {
    expect(roundDecimal('2.675', 2)).toBe('2.68');
    expect(roundDecimal('-0.004', 2)).toBe('0.00');
    expect(compareDecimal('100.0000', '100')).toBe(0);
    expect(compareDecimal('99.9999', '100')).toBe(-1);
    expect(compareDecimal('0.30', '0.1')).toBe(1);
    expect(isZeroDecimal('0.0000')).toBe(true);
    expect(isZeroDecimal('0.0001')).toBe(false);
  });

  it('formats percentages without trailing zeros', () => {
    expect(formatPercent('12.5000')).toBe('12.5%');
    expect(formatPercent('18.0000')).toBe('18%');
    expect(formatPercent('0')).toBe('0%');
  });
});

describe('sumDecimals / signOfDecimal', () => {
  it('adds decimal strings exactly with the widest scale', () => {
    expect(sumDecimals(['0.1', '0.2'])).toBe('0.3');
    expect(sumDecimals(['10.5', '0.25', '-1'])).toBe('9.75');
    expect(sumDecimals([])).toBe('0');
    expect(sumDecimals(['-0.5', '0.25'])).toBe('-0.25');
  });
  it('reports the sign', () => {
    expect(signOfDecimal('-0.01')).toBe(-1);
    expect(signOfDecimal('0.0000')).toBe(0);
    expect(signOfDecimal('3')).toBe(1);
  });
});

describe('multiplyDecimals', () => {
  it('multiplies exactly without floating point', () => {
    expect(multiplyDecimals('2.5', '1000.10')).toBe('2500.250');
    expect(multiplyDecimals('0.1', '0.2')).toBe('0.02');
    expect(multiplyDecimals('3', '33333333333333333.3333')).toBe('99999999999999999.9999');
    expect(multiplyDecimals('-2', '0.5')).toBe('-1.0');
    expect(multiplyDecimals('0', '-5')).toBe('0');
  });

  it('rejects non-decimals', () => {
    expect(() => multiplyDecimals('1e3', '2')).toThrow();
  });
});

describe('formatEnteredMoney', () => {
  it('formats with the currency when one is chosen', () => {
    expect(formatEnteredMoney('200000', 'TZS')).toBe('TZS 200,000.00');
    expect(formatEnteredMoney('1500.5', 'UGX')).toBe('UGX 1,501');
  });

  it('groups but never re-scales when the tenant base currency applies', () => {
    expect(formatEnteredMoney('200000', '')).toBe('200,000 (tenant base currency)');
    expect(formatEnteredMoney('1234.5', '')).toBe('1,234.5 (tenant base currency)');
    expect(formatEnteredMoney('abc', '')).toBe('abc (tenant base currency)');
  });
});
