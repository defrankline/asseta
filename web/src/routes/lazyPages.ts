import { lazy } from 'react';

/**
 * Tenant console pages are code-split so MapLibre and map-heavy views load on demand.
 * Each module keeps its named export; `lazy` needs a default, so we adapt here.
 */
export const FleetMapPage = lazy(() =>
  import('../pages/tenant/fleet/FleetMapPage').then((m) => ({ default: m.FleetMapPage })),
);
export const MachinesPage = lazy(() =>
  import('../pages/tenant/machines/MachinesPage').then((m) => ({ default: m.MachinesPage })),
);
export const MachineDetailPage = lazy(() =>
  import('../pages/tenant/machineDetail/MachineDetailPage').then((m) => ({
    default: m.MachineDetailPage,
  })),
);
export const StaffPage = lazy(() =>
  import('../pages/tenant/staff/StaffPage').then((m) => ({ default: m.StaffPage })),
);
export const TrackersPage = lazy(() =>
  import('../pages/tenant/trackers/TrackersPage').then((m) => ({ default: m.TrackersPage })),
);
export const GeofencesPage = lazy(() =>
  import('../pages/tenant/geofences/GeofencesPage').then((m) => ({ default: m.GeofencesPage })),
);
export const AlertsPage = lazy(() =>
  import('../pages/tenant/alerts/AlertsPage').then((m) => ({ default: m.AlertsPage })),
);
export const PoliciesPage = lazy(() =>
  import('../pages/tenant/policies/PoliciesPage').then((m) => ({ default: m.PoliciesPage })),
);
export const TenantSubscriptionPage = lazy(() =>
  import('../pages/tenant/subscription/TenantSubscriptionPage').then((m) => ({
    default: m.TenantSubscriptionPage,
  })),
);
