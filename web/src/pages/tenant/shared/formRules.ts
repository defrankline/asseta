/** Yup building blocks shared by tenant forms. Decimal inputs stay strings (never parsed to float). */
import { string } from 'yup';
import { compareDecimal, isDecimalString } from '../../../utils/money';

const DECIMAL_4DP = /^\d+(\.\d{1,4})?$/;

const decimalMessage = (label: string) =>
  `${label} must be a non-negative number with at most 4 decimal places`;

export const requiredDecimal = (label: string) =>
  string().trim().required(`${label} is required`).matches(DECIMAL_4DP, decimalMessage(label));

export const optionalDecimal = (label: string) =>
  string()
    .trim()
    .ensure()
    .test('decimal', decimalMessage(label), (v) => v === '' || DECIMAL_4DP.test(v));

/** 0–100 percentage as a decimal string. */
export const percentDecimal = (label: string) =>
  requiredDecimal(label).test(
    'max-100',
    `${label} must be at most 100`,
    (v) => !isDecimalString(v) || compareDecimal(v, '100') <= 0,
  );

export const optionalText = (label: string, max: number) =>
  string()
    .trim()
    .ensure()
    .max(max, `${label} must be at most ${String(max)} characters`);

/** Required UTC ISO instant ('' when empty in Formik). */
export const requiredInstant = (label: string) =>
  string()
    .required(`${label} is required`)
    .test('instant', `${label} must be a valid date and time`, (v) => !Number.isNaN(Date.parse(v)));

export const optionalInstant = () =>
  string()
    .ensure()
    .test(
      'instant',
      'Enter a valid date and time',
      (v) => v === '' || !Number.isNaN(Date.parse(v)),
    );

/** True when `end` is empty or strictly after `start` (instants compared as times, not money). */
export function isAfter(start: string, end: string): boolean {
  if (end === '' || start === '') return true;
  return Date.parse(end) > Date.parse(start);
}

export const orNull = (v: string): string | null => (v.trim() === '' ? null : v.trim());
