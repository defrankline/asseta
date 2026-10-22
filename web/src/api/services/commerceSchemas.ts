/**
 * Runtime (Yup) schemas for platform commerce (DEC-022, ADR-006): product catalog and SMS wallets.
 * Annotated with the generated contract types so contract drift fails `npm run typecheck`.
 */
import { array, mixed, number, object, string, type Schema } from 'yup';
import type {
  ProductDto,
  ProductType,
  SmsWalletDto,
  SmsWalletEntryDto,
  SmsWalletEntryType,
} from '../types';
import { pageSchema } from './billingSchemas';
import { bool, int, lifecycleFields, nullableText, oneOf, text } from './schemaKit';

export const PRODUCT_TYPES: readonly ProductType[] = ['SUBSCRIPTION_FEE', 'SMS_BUNDLE', 'SERVICE'];
export const SMS_WALLET_ENTRY_TYPES: readonly SmsWalletEntryType[] = [
  'BUNDLE_CREDIT',
  'BUNDLE_REVERSAL',
  'SMS_DEBIT',
  'SMS_REFUND',
];

function isPriceMap(value: unknown): value is Record<string, string> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every((v) => typeof v === 'string')
  );
}

/** `{ "TZS": "100000.0000", ... }` — decimal strings per currency. */
const priceMap = () => mixed<Record<string, string>>(isPriceMap).required();

export const productSchema: Schema<ProductDto> = object({
  id: string().required(),
  code: text(),
  name: text(),
  description: nullableText(),
  product_type: oneOf(PRODUCT_TYPES),
  prices: priceMap(),
  sms_credits: number().integer().nullable().defined(),
  taxable: bool(),
  is_active: bool(),
  created_at: string().required(),
  updated_at: string().required(),
  ...lifecycleFields(),
});

export const productPageSchema = pageSchema(productSchema);

export const smsWalletEntrySchema: Schema<SmsWalletEntryDto> = object({
  id: string().required(),
  entry_type: oneOf(SMS_WALLET_ENTRY_TYPES),
  credits: int(),
  balance_after: int(),
  reference_type: text(),
  reference_id: string().required(),
  note: nullableText(),
  created_at: string().required(),
});

export const smsWalletSchema: Schema<SmsWalletDto> = object({
  tenant_id: string().required(),
  balance: int(),
  low_balance_threshold: int(),
  recent_entries: array(smsWalletEntrySchema).required(),
});

export const smsWalletEntryPageSchema = pageSchema(smsWalletEntrySchema);
