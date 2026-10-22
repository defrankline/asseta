/**
 * Runtime (Yup) schemas for notifications (DEC-022, ADR-005), annotated with the generated contract
 * types. Also used by the realtime codec to validate pushed notifications.
 */
import { array, mixed, object, string, type Schema } from 'yup';
import type {
  NotificationDto,
  NotificationMarkReadResultDto,
  NotificationPreferenceDto,
  NotificationPriority,
  NotificationProfileDto,
  NotificationSeverity,
  NotificationTarget,
  NotificationTestSendResultDto,
  NotificationUnreadCountDto,
  SmsDeliveryDto,
  SmsDeliveryStatus,
} from '../types';
import { pageSchema } from './billingSchemas';
import { bool, int, nullableText, oneOf, record, text } from './schemaKit';

export const NOTIFICATION_SEVERITIES: readonly NotificationSeverity[] = [
  'INFO',
  'WARNING',
  'CRITICAL',
];
export const NOTIFICATION_PRIORITIES: readonly NotificationPriority[] = ['NORMAL', 'HIGH'];
export const SMS_DELIVERY_STATUSES: readonly SmsDeliveryStatus[] = [
  'PENDING',
  'SENT',
  'FAILED',
  'REFUSED_NO_CREDIT',
  'INVALID_NUMBER',
];

const targetSchema: Schema<NotificationTarget | null> = object({
  entity: text(),
  id: nullableText(),
  path: nullableText(),
})
  .nullable()
  .defined();

const notificationFields = {
  id: string().required(),
  type: text(),
  category: text(),
  severity: oneOf(NOTIFICATION_SEVERITIES),
  priority: mixed<NotificationPriority>().oneOf(NOTIFICATION_PRIORITIES).required(),
  title: text(),
  body: text(),
  created_at: string().required(),
  read_at: nullableText(),
  target: targetSchema,
  tenant_id: nullableText(),
  data: record(),
};

export const notificationSchema: Schema<NotificationDto> = object(notificationFields);

export const notificationPageSchema = pageSchema(notificationSchema);

export const unreadCountSchema: Schema<NotificationUnreadCountDto> = object({ count: int() });

export const markReadResultSchema: Schema<NotificationMarkReadResultDto> = object({
  updated: int(),
  unread: int(),
});

export const notificationPreferenceSchema: Schema<NotificationPreferenceDto> = object({
  type: text(),
  label: text(),
  description: text(),
  category: text(),
  in_app: bool(),
  sms: bool(),
  mandatory: bool(),
  mandatory_channels: array(string().required()).required(),
  low_priority: bool(),
  sms_available: bool(),
});

export const notificationPreferencesSchema = array(notificationPreferenceSchema).required();

export const notificationProfileSchema: Schema<NotificationProfileDto> = object({
  user_id: string().required(),
  msisdn: nullableText(),
});

const smsDeliveryFields = {
  id: string().required(),
  tenant_id: nullableText(),
  notification_id: nullableText(),
  notification_type: text(),
  msisdn: text(),
  status: oneOf(SMS_DELIVERY_STATUSES),
  segments: int(),
  attempts: int(),
  billable: bool(),
  provider: nullableText(),
  last_error: nullableText(),
  created_at: string().required(),
  sent_at: nullableText(),
  next_attempt_at: string().required(),
};

export const smsDeliverySchema: Schema<SmsDeliveryDto> = object(smsDeliveryFields);

export const smsDeliveryPageSchema = pageSchema(smsDeliverySchema);

export const testSendResultSchema: Schema<NotificationTestSendResultDto> = object({
  notification: object(notificationFields).required(),
  delivery: object(smsDeliveryFields).nullable().defined().default(null),
});
