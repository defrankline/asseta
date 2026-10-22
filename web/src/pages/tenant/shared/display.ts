import type {
  AlertSeverity,
  AlertStatus,
  AlertType,
  Capability,
  GeofenceKind,
  IngestionStatus,
  MachineStatus,
  Ownership,
  ProvisioningState,
  QuarantineReason,
  StaffKind,
} from '../../../api/types';
import type { StatusTone } from '../../../components/display/StatusChip';

export interface Option<T extends string = string> {
  value: T;
  label: string;
}

export const MACHINE_STATUS_TONES: Readonly<Record<MachineStatus, StatusTone>> = {
  ACTIVE: 'success',
  OUT_OF_SERVICE: 'warning',
  DISPOSED: 'default',
};
export const MACHINE_STATUS_OPTIONS: readonly Option<MachineStatus>[] = [
  { value: 'ACTIVE', label: 'Active' },
  { value: 'OUT_OF_SERVICE', label: 'Out of service' },
  { value: 'DISPOSED', label: 'Disposed' },
];
export const OWNERSHIP_OPTIONS: readonly Option<Ownership>[] = [
  { value: 'OWNED', label: 'Owned' },
  { value: 'LEASED', label: 'Leased' },
  { value: 'HIRED_IN', label: 'Hired in' },
];
export const STAFF_KIND_OPTIONS: readonly Option<StaffKind>[] = [
  { value: 'SUPERVISOR', label: 'Supervisor' },
  { value: 'OPERATOR', label: 'Operator' },
  { value: 'OTHER', label: 'Other' },
];

export const TRACKER_STATE_TONES: Readonly<Record<ProvisioningState, StatusTone>> = {
  REGISTERED: 'info',
  VERIFIED_REPORTING: 'success',
  SUSPENDED: 'warning',
  RETIRED: 'default',
};
export const TRACKER_STATE_OPTIONS: readonly Option<ProvisioningState>[] = [
  { value: 'REGISTERED', label: 'Registered' },
  { value: 'VERIFIED_REPORTING', label: 'Verified reporting' },
  { value: 'SUSPENDED', label: 'Suspended' },
  { value: 'RETIRED', label: 'Retired' },
];

export const CAPABILITY_LABELS: Readonly<Record<Capability, string>> = {
  GNSS: 'GNSS position',
  ACCURACY: 'Position accuracy',
  IGNITION: 'Ignition',
  ENGINE_HOURS: 'Engine hours',
  FUEL_LEVEL: 'Fuel level',
  EXTERNAL_POWER: 'External power',
  BATTERY: 'Battery',
  TAMPER: 'Tamper',
  MOTION: 'Motion',
  ODOMETER: 'Odometer',
  OFFLINE_BUFFERING: 'Offline buffering',
};

export const INGESTION_STATUS_TONES: Readonly<Record<IngestionStatus, StatusTone>> = {
  ACCEPTED: 'success',
  ACCEPTED_NO_FIX: 'info',
  DUPLICATE: 'default',
  QUARANTINED: 'error',
};
export const INGESTION_STATUS_OPTIONS: readonly Option<IngestionStatus>[] = [
  { value: 'ACCEPTED', label: 'Accepted' },
  { value: 'ACCEPTED_NO_FIX', label: 'Accepted (no GPS fix)' },
  { value: 'DUPLICATE', label: 'Duplicate' },
  { value: 'QUARANTINED', label: 'Quarantined' },
];

/** Plain-language explanation of each quarantine reason. */
export const QUARANTINE_REASON_HELP: Readonly<Record<QuarantineReason, string>> = {
  MALFORMED: 'The message could not be parsed or was missing required fields.',
  UNKNOWN_DEVICE: 'The device identity is not registered to any tracker.',
  TRACKER_INACTIVE: 'The tracker is suspended or retired, so its data is not accepted.',
  UNASSIGNED: 'The tracker is not assigned to a machine at the observation time.',
  NOT_ENROLLED: 'The machine is not an enrolled billable asset at the observation time.',
  CLOCK_FUTURE: 'The device timestamp is further in the future than the tolerance allows.',
  TOO_OLD: 'The observation is older than the maximum replay age in the tracking policy.',
};

export const ALERT_STATUS_TONES: Readonly<Record<AlertStatus, StatusTone>> = {
  OPEN: 'error',
  ACKNOWLEDGED: 'warning',
  RESOLVED: 'success',
  SUPERSEDED: 'default',
};
export const ALERT_STATUS_OPTIONS: readonly Option<AlertStatus>[] = [
  { value: 'OPEN', label: 'Open' },
  { value: 'ACKNOWLEDGED', label: 'Acknowledged' },
  { value: 'RESOLVED', label: 'Resolved' },
  { value: 'SUPERSEDED', label: 'Superseded' },
];
export const ALERT_SEVERITY_OPTIONS: readonly Option<AlertSeverity>[] = [
  { value: 'CRITICAL', label: 'Critical' },
  { value: 'WARNING', label: 'Warning' },
  { value: 'INFO', label: 'Info' },
];
export const ALERT_SEVERITY_TONES: Readonly<Record<AlertSeverity, StatusTone>> = {
  INFO: 'info',
  WARNING: 'warning',
  CRITICAL: 'error',
};
export const ALERT_TYPE_OPTIONS: readonly Option<AlertType>[] = [
  { value: 'GEOFENCE_EXIT', label: 'Geofence exit' },
  { value: 'RESTRICTED_AREA_ENTRY', label: 'Restricted area entry' },
  { value: 'UNAUTHORIZED_MOVEMENT', label: 'Unauthorized movement' },
  { value: 'GPS_ANOMALY', label: 'GPS anomaly' },
  { value: 'TRACKER_STALE', label: 'Tracker stale' },
  { value: 'TRACKER_OFFLINE', label: 'Tracker offline' },
  { value: 'LOW_POWER', label: 'Low power' },
  { value: 'TAMPER', label: 'Tamper' },
];
export const SUPERSEDED_HELP =
  'Superseded: re-evaluated after late telemetry arrived; kept for audit, no action needed.';

export const GEOFENCE_KIND_OPTIONS: readonly Option<GeofenceKind>[] = [
  { value: 'ALLOWED_AREA', label: 'Allowed area' },
  { value: 'RESTRICTED_AREA', label: 'Restricted area' },
  { value: 'SITE_BOUNDARY', label: 'Site boundary' },
];
export const GEOFENCE_KIND_COLORS: Readonly<Record<GeofenceKind, string>> = {
  ALLOWED_AREA: '#16a34a',
  RESTRICTED_AREA: '#dc2626',
  SITE_BOUNDARY: '#2563eb',
};

export function machineLabel(m: { asset_code: string; name: string }): string {
  return `${m.asset_code} · ${m.name}`;
}

export function labelOf(options: readonly Option[], value: string): string {
  return options.find((o) => o.value === value)?.label ?? value;
}

/** Default map center before data arrives (configurable via data; not a business rule). */
export const DEFAULT_MAP_CENTER: readonly [number, number] = [39.2083, -6.7924];
