/** Stable lifecycle error codes for geofences and job sites, with what the user can do. */
export const GEOFENCE_ERROR_HINTS: Readonly<Record<string, string>> = {
  ALREADY_INACTIVE: 'This geofence is already inactive; reload the list.',
  ALREADY_ACTIVE: 'This geofence is already active; reload the list.',
};

export const JOB_SITE_ERROR_HINTS: Readonly<Record<string, string>> = {
  SITE_IN_USE:
    'The site is still used by an active contract or an open job; close or move those first.',
  ALREADY_INACTIVE: 'This job site is already inactive; reload the list.',
  ALREADY_ACTIVE: 'This job site is already active; reload the list.',
};

export const GEOFENCE_DEACTIVATE_CONSEQUENCES =
  'While inactive it raises no geofence or restricted-area alerts. Its event history is kept.';

export const JOB_SITE_DEACTIVATE_CONSEQUENCES =
  'An inactive site cannot be chosen for new contracts, jobs or geofences. Existing records keep it.';
