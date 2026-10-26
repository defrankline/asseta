import { lazy, type ReactNode } from 'react';
import { Route } from 'react-router';
import { CAPABILITY, CAPABILITY_FEATURE, type CapabilityCode } from '../access/capabilities';
import { PERMISSIONS } from '../access/permissionCodes';
import { RequireCapability } from '../access/RequireCapability';
import { OVERSIGHT_ROUTES } from '../navigation/oversightRoutes';

/** Oversight pages (DEC-031 Phase 5), code-split like every tenant page. */
const page = <K extends string>(load: () => Promise<Record<K, () => ReactNode>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));

const ScorecardPage = page(
  () => import('../pages/tenant/oversight/ScorecardPage'),
  'ScorecardPage',
);
const ScorecardPersonPage = page(
  () => import('../pages/tenant/oversight/ScorecardPersonPage'),
  'ScorecardPersonPage',
);
const UnbilledWorkPage = page(
  () => import('../pages/tenant/oversight/UnbilledWorkPage'),
  'UnbilledWorkPage',
);
const IdleMachinesPage = page(
  () => import('../pages/tenant/oversight/IdleMachinesPage'),
  'IdleMachinesPage',
);
const loadCheckins = () => import('../pages/tenant/oversight/SiteCheckinsPage');
const SiteCheckinsPage = page(loadCheckins, 'SiteCheckinsPage');
const SiteCheckinDetailPage = page(loadCheckins, 'SiteCheckinDetailPage');
const FieldCheckinPage = page(
  () => import('../pages/tenant/oversight/FieldCheckinPage'),
  'FieldCheckinPage',
);

type Guard = (permission: string, page: ReactNode) => ReactNode;

/**
 * Routes of the oversight pages; each is permission-guarded (deny by default) and shows a plain
 * "not enabled" state while the tenant's OVERSIGHT policy switches its capability off.
 */
export function oversightRouteElements(guard: Guard): ReactNode[] {
  const routes: [string, CapabilityCode, string, ReactNode][] = [
    [
      OVERSIGHT_ROUTES.scorecard,
      CAPABILITY.scorecard,
      PERMISSIONS.tenantOversightScorecardRead,
      <ScorecardPage key="s" />,
    ],
    [
      OVERSIGHT_ROUTES.scorecardPerson,
      CAPABILITY.scorecard,
      PERMISSIONS.tenantOversightScorecardRead,
      <ScorecardPersonPage key="sp" />,
    ],
    [
      OVERSIGHT_ROUTES.unbilledWork,
      CAPABILITY.unbilledWork,
      PERMISSIONS.tenantOversightRead,
      <UnbilledWorkPage key="u" />,
    ],
    [
      OVERSIGHT_ROUTES.idleMachines,
      CAPABILITY.idleMachines,
      PERMISSIONS.tenantOversightRead,
      <IdleMachinesPage key="i" />,
    ],
    [
      OVERSIGHT_ROUTES.siteCheckins,
      CAPABILITY.siteCheckin,
      PERMISSIONS.tenantOversightRead,
      <SiteCheckinsPage key="c" />,
    ],
    [
      OVERSIGHT_ROUTES.siteCheckinDetail,
      CAPABILITY.siteCheckin,
      PERMISSIONS.tenantOversightRead,
      <SiteCheckinDetailPage key="cd" />,
    ],
    [
      OVERSIGHT_ROUTES.fieldCheckin,
      CAPABILITY.siteCheckin,
      PERMISSIONS.tenantSiteCheckinRecord,
      <FieldCheckinPage key="f" />,
    ],
  ];
  return routes.map(([path, capability, permission, element]) => (
    <Route
      key={path}
      path={path}
      element={
        <RequireCapability capability={capability} feature={CAPABILITY_FEATURE[capability]}>
          {guard(permission, element)}
        </RequireCapability>
      }
    />
  ));
}
