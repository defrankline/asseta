/** Runtime (Yup) response schemas for tracker registry, assignments and ingestion events. */
import { array, object, type Schema } from 'yup';
import type {
  Capability,
  CapabilityDto,
  IngestionEventDto,
  IngestionStatus,
  ProvisioningState,
  QuarantineReason,
  TrackerAssignmentDto,
  TrackerDto,
  TrackerModelDto,
} from '../types';
import { bool, id, int, nullableId, nullableOneOf, nullableText, oneOf, text } from './schemaKit';

export const CAPABILITIES: readonly Capability[] = [
  'GNSS',
  'ACCURACY',
  'IGNITION',
  'ENGINE_HOURS',
  'FUEL_LEVEL',
  'EXTERNAL_POWER',
  'BATTERY',
  'TAMPER',
  'MOTION',
  'ODOMETER',
  'OFFLINE_BUFFERING',
];
export const PROVISIONING_STATES: readonly ProvisioningState[] = [
  'REGISTERED',
  'VERIFIED_REPORTING',
  'SUSPENDED',
  'RETIRED',
];
export const INGESTION_STATUSES: readonly IngestionStatus[] = [
  'ACCEPTED',
  'ACCEPTED_NO_FIX',
  'DUPLICATE',
  'QUARANTINED',
];
export const QUARANTINE_REASONS: readonly QuarantineReason[] = [
  'MALFORMED',
  'UNKNOWN_DEVICE',
  'TRACKER_INACTIVE',
  'UNASSIGNED',
  'NOT_ENROLLED',
  'CLOCK_FUTURE',
  'TOO_OLD',
];

const assignmentFields = {
  id: id(),
  tracker_id: id(),
  machine_id: id(),
  is_primary: bool(),
  effective_from: text(),
  effective_to: nullableText(),
  reason: nullableText(),
};
export const trackerAssignmentSchema: Schema<TrackerAssignmentDto> = object(assignmentFields);

const capabilitySchema: Schema<CapabilityDto> = object({
  capability: oneOf(CAPABILITIES),
  declared: bool(),
  verified_at: nullableText(),
  last_observed_at: nullableText(),
});

export const trackerSchema: Schema<TrackerDto> = object({
  id: id(),
  tracker_model_id: id(),
  adapter: oneOf(['TRACCAR'] as const),
  external_id: text(),
  label: text(),
  sim_iccid: nullableText(),
  sim_msisdn: nullableText(),
  carrier: nullableText(),
  provisioning_state: oneOf(PROVISIONING_STATES),
  first_report_at: nullableText(),
  last_report_at: nullableText(),
  capabilities: array(capabilitySchema).required(),
  current_assignment: object(assignmentFields).nullable().optional().default(undefined),
  version: int(),
});

export const trackerModelSchema: Schema<TrackerModelDto> = object({
  id: id(),
  manufacturer: text(),
  model: text(),
  adapter: oneOf(['TRACCAR'] as const),
  protocol: text(),
  declared_capabilities: array(oneOf(CAPABILITIES)).required(),
  approved: bool(),
  notes: nullableText(),
  deactivated_at: nullableText().default(null),
  deactivation_reason: nullableText().default(null),
  version: int(),
});

export const ingestionEventSchema: Schema<IngestionEventDto> = object({
  id: id(),
  received_at: text(),
  external_device_id: nullableText(),
  tracker_id: nullableId(),
  machine_id: nullableId(),
  event_time: nullableText(),
  status: oneOf(INGESTION_STATUSES),
  quarantine_reason: nullableOneOf(QUARANTINE_REASONS),
  detail: nullableText(),
});
