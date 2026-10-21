import { object, type Schema } from 'yup';
import type { ExpenseCategoryDto, GatewayCreatedDto, GatewayDto } from '../types';
import { bool, id, int, nullableText, oneOf, text } from './schemaKit';

export const expenseCategorySchema: Schema<ExpenseCategoryDto> = object({
  id: id(),
  code: text(),
  name: text(),
  is_active: bool(),
  sync_revision: int(),
  deactivated_at: nullableText().default(null),
  deactivation_reason: nullableText().default(null),
  version: int(),
});

export const gatewaySchema: Schema<GatewayDto> = object({
  id: id(),
  name: text(),
  adapter: oneOf(['TRACCAR'] as const),
  active: bool(),
  last_seen_at: nullableText(),
  created_at: text(),
});

export const gatewayCreatedSchema: Schema<GatewayCreatedDto> = object({
  id: id(),
  name: text(),
  adapter: oneOf(['TRACCAR'] as const),
  gateway_key: text(),
});
