/** Runtime (Yup) response schemas for fleet map, history, sites/geofences, alerts and policies. */
import { array, object, type Schema } from 'yup';
import type {
  AlertDto,
  AlertSeverity,
  AlertStatus,
  AlertType,
  Compliance,
  Connectivity,
  EffectivePolicyDto,
  GeofenceDto,
  GeofenceKind,
  GeofenceShape,
  HistoryDto,
  JobSiteDto,
  MachineMapDto,
  Observed,
  PolicyScope,
  PolicyType,
  PolicyVersionDto,
  SiteVisitDto,
  StopDto,
  TrackPointDto,
} from '../types';
import {
  bool,
  id,
  idList,
  int,
  lngLat,
  nullableBool,
  nullableId,
  nullableInt,
  nullableNum,
  nullableText,
  num,
  oneOf,
  record,
  text,
  lifecycleFields,
} from './schemaKit';

export const CONNECTIVITIES: readonly Connectivity[] = [
  'LIVE',
  'RECENT',
  'STALE',
  'OFFLINE',
  'NEVER_REPORTED',
  'NO_TRACKER',
];
export const OBSERVED_VALUES: readonly Observed[] = [
  'ON',
  'OFF',
  'MOVING',
  'STATIONARY',
  'UNKNOWN',
];
export const COMPLIANCE_VALUES: readonly Compliance[] = ['COMPLIANT', 'NON_COMPLIANT', 'UNKNOWN'];
export const GEOFENCE_KINDS: readonly GeofenceKind[] = [
  'ALLOWED_AREA',
  'RESTRICTED_AREA',
  'SITE_BOUNDARY',
];
export const GEOFENCE_SHAPES: readonly GeofenceShape[] = ['POLYGON', 'CORRIDOR'];
export const ALERT_STATUSES: readonly AlertStatus[] = [
  'OPEN',
  'ACKNOWLEDGED',
  'RESOLVED',
  'SUPERSEDED',
];
export const ALERT_TYPES: readonly AlertType[] = [
  'GEOFENCE_EXIT',
  'RESTRICTED_AREA_ENTRY',
  'UNAUTHORIZED_MOVEMENT',
  'GPS_ANOMALY',
  'TRACKER_STALE',
  'TRACKER_OFFLINE',
  'LOW_POWER',
  'TAMPER',
];
export const ALERT_SEVERITIES: readonly AlertSeverity[] = ['INFO', 'WARNING', 'CRITICAL'];
export const POLICY_SCOPES: readonly PolicyScope[] = [
  'PLATFORM',
  'TENANT',
  'MACHINE',
  'SITE',
  'STAFF',
];
// A Record so a policy type added to the API fails typecheck here instead of failing validation at runtime.
const POLICY_TYPE_SET: Readonly<Record<PolicyType, true>> = {
  TRACKING: true,
  METER_CAPTURE: true,
  HIRE_BILLING: true,
  DEVICE_SYNC: true,
  EXPENSE_CAPTURE: true,
  FRAUD_CONTROLS: true,
  CASH_CUSTODY: true,
  OVERSIGHT: true,
  CUSTOMER_HOURS: true,
  ENGINE_HOURS: true,
  REVENUE_RECONCILIATION: true,
};
export const POLICY_TYPES = Object.keys(POLICY_TYPE_SET) as readonly PolicyType[];

export const machineMapSchema: Schema<MachineMapDto> = object({
  machine_id: id(),
  asset_code: text(),
  name: text(),
  machine_status: text(),
  longitude: nullableNum(),
  latitude: nullableNum(),
  accuracy_m: nullableNum(),
  position_time: nullableText(),
  last_message_at: nullableText(),
  last_seen_age_seconds: nullableInt(),
  position_source: nullableText(),
  position_quality: nullableText(),
  connectivity: oneOf(CONNECTIVITIES),
  is_live: bool(),
  reported_work_status: text(),
  observed_engine: oneOf(OBSERVED_VALUES),
  observed_motion: oneOf(OBSERVED_VALUES),
  location_compliance: oneOf(COMPLIANCE_VALUES),
  tracker_id: nullableId(),
  tracker_state: nullableText(),
  supervisor: nullableText(),
  operator: nullableText(),
  open_alerts: int(),
  policy_version: text(),
});

const trackPointSchema: Schema<TrackPointDto> = object({
  event_time: text(),
  longitude: num(),
  latitude: num(),
  accuracy_m: nullableNum(),
  speed_kmh: nullableNum(),
  heading_deg: nullableNum(),
  ignition: nullableBool(),
  quality: text(),
  is_late: bool(),
  received_at: text(),
});

const stopSchema: Schema<StopDto> = object({
  start: text(),
  end: text(),
  duration_seconds: int(),
  longitude: num(),
  latitude: num(),
});

const siteVisitSchema: Schema<SiteVisitDto> = object({
  geofence_id: id(),
  geofence_name: text(),
  entered_at: nullableText(),
  exited_at: nullableText(),
  duration_seconds: int(),
});

export const historySchema: Schema<HistoryDto> = object({
  machine_id: id(),
  points: array(trackPointSchema).required(),
  truncated: bool(),
  stops: array(stopSchema).required(),
  distance_km: num(),
  site_visits: array(siteVisitSchema).required(),
  policy_version: text(),
});

export const jobSiteSchema: Schema<JobSiteDto> = object({
  id: id(),
  code: text(),
  name: text(),
  address: nullableText(),
  center: object({ type: oneOf(['Point'] as const), coordinates: lngLat() }).required(),
  is_active: bool(),
  ...lifecycleFields(),
});

export const geofenceSchema: Schema<GeofenceDto> = object({
  id: id(),
  name: text(),
  kind: oneOf(GEOFENCE_KINDS),
  shape: oneOf(GEOFENCE_SHAPES),
  job_site_id: nullableId(),
  corridor_width_m: nullableNum(),
  source_geometry: record(),
  area_geojson: record(),
  area_m2: num(),
  machine_ids: idList(),
  is_active: bool(),
  ...lifecycleFields(),
});

export const alertSchema: Schema<AlertDto> = object({
  id: id(),
  machine_id: nullableId(),
  tracker_id: nullableId(),
  alert_type: oneOf(ALERT_TYPES),
  severity: oneOf(ALERT_SEVERITIES),
  status: oneOf(ALERT_STATUSES),
  event_time: text(),
  title: text(),
  evidence: record(),
  policy_version: nullableText(),
  created_at: text(),
  acknowledged_at: nullableText(),
  resolved_at: nullableText(),
  resolution_note: nullableText(),
});

export const effectivePolicySchema: Schema<EffectivePolicyDto> = object({
  policy_type: oneOf(POLICY_TYPES),
  version_stamp: text(),
  values: record(),
});

export const policyVersionSchema: Schema<PolicyVersionDto> = object({
  id: id(),
  policy_type: oneOf(POLICY_TYPES),
  scope: oneOf(POLICY_SCOPES),
  scope_ref_id: nullableId(),
  version: int(),
  effective_from: text(),
  values: record(),
  reason: text(),
  created_at: text(),
});
