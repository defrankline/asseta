/** Data protection policy fields (DATA_PROTECTION; mirrors backend DataProtectionPolicy). */
import type { PolicyFieldDef } from './policyFields';

export const DATA_PROTECTION_FIELDS: readonly PolicyFieldDef[] = [
  {
    key: 'balance_verification_enabled',
    label: 'Scheduled balance verification',
    kind: 'bool',
    help: 'Regularly compare every balance with its records. Verification can always be run by hand.',
  },
  {
    key: 'balance_verification_interval_days',
    label: 'Days between scheduled verifications',
    kind: 'number',
    unit: 'days',
  },
  {
    key: 'data_export_retention_days',
    label: 'Days an export stays available',
    kind: 'number',
    unit: 'days',
  },
];
