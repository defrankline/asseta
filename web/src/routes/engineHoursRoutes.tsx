import { lazy, type ReactNode } from 'react';
import { Route } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import { recordRoutePattern } from '../navigation/recordRoutes';

/** Engine-hour detail pages, code-split like every tenant page. */
const page = <K extends string>(load: () => Promise<Record<K, () => ReactNode>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));
const load = () => import('../pages/tenant/engineHours/EngineRecordDetailPages');

const MeterBaselineDetailPage = page(load, 'MeterBaselineDetailPage');
const MeterCorrectionDetailPage = page(load, 'MeterCorrectionDetailPage');
const ClassificationDetailPage = page(load, 'ClassificationDetailPage');

type Guard = (permission: string, page: ReactNode) => ReactNode;

/** Detail routes of engine-hour approvals (meter baselines, corrections, hour explanations). */
export function engineHoursDetailRouteElements(guard: Guard): ReactNode[] {
  const read = PERMISSIONS.tenantMeterRead;
  const routes: [string, ReactNode][] = [
    [recordRoutePattern('METER_BASELINE'), <MeterBaselineDetailPage key="b" />],
    [recordRoutePattern('METER_CORRECTION'), <MeterCorrectionDetailPage key="c" />],
    [recordRoutePattern('ENGINE_HOURS_CLASSIFICATION'), <ClassificationDetailPage key="e" />],
  ];
  return routes.map(([path, element]) => (
    <Route key={path} path={path} element={guard(read, element)} />
  ));
}
