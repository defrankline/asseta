/** Lifecycle fields of an active, never-deactivated record at its first version. */
export const ACTIVE_RECORD = {
  is_active: true,
  deactivated_at: null,
  deactivation_reason: null,
  version: 1,
} as const;
