import { string } from 'yup';
import { compareDecimal, isZeroDecimal } from '../../../utils/money';
import { isIsoDate } from '../../../utils/dates';

/** Non-negative decimal with up to 4 dp, kept as a string (never parsed to float). */
const DECIMAL_4DP = /^\d+(\.\d{1,4})?$/;
const SIGNED_DECIMAL_4DP = /^-?\d+(\.\d{1,4})?$/;

export const decimalField = (label: string) =>
  string()
    .trim()
    .required(`${label} is required`)
    .matches(DECIMAL_4DP, `${label} must be a number with at most 4 decimal places`);

export const signedDecimalField = (label: string) =>
  string()
    .trim()
    .required(`${label} is required`)
    .matches(SIGNED_DECIMAL_4DP, `${label} must be a number with at most 4 decimal places`);

export const positiveDecimalField = (label: string) =>
  decimalField(label).test(
    'positive',
    `${label} must be greater than 0`,
    (v) => !DECIMAL_4DP.test(v) || !isZeroDecimal(v),
  );

export const percentField = (label: string) =>
  decimalField(label).test(
    'max-100',
    `${label} must be between 0 and 100`,
    (v) => !DECIMAL_4DP.test(v) || compareDecimal(v, '100') <= 0,
  );

export const integerField = (label: string, min: number, max?: number) =>
  string()
    .trim()
    .required(`${label} is required`)
    .matches(/^\d+$/, `${label} must be a whole number`)
    .test(
      'range',
      max === undefined
        ? `${label} must be at least ${String(min)}`
        : `${label} must be between ${String(min)} and ${String(max)}`,
      (v) => {
        if (!/^\d+$/.test(v)) return true;
        const n = Number(v);
        return n >= min && (max === undefined || n <= max);
      },
    );

export const isoDateField = (label: string) =>
  string()
    .required(`${label} is required`)
    .test('iso-date', `${label} must be a valid date`, (v) => isIsoDate(v));

/** Free-text reason/note: 3..1000 chars, as enforced by the API. */
export const reasonField = (label = 'Reason') =>
  string()
    .trim()
    .required(`${label} is required`)
    .min(3, `${label} must be at least 3 characters`)
    .max(1000, `${label} must be at most 1000 characters`);
