import { lazy, type ReactNode } from 'react';
import { Navigate, Route } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import { recordRoutePattern } from '../navigation/recordRoutes';
import { ROUTES } from '../navigation/routes';

/** Engine-hour detail pages, code-split like every tenant page. */
const page = <K extends string>(load: () => Promise<Record<K, () => ReactNode>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));
const load = () => import('../pages/tenant/engineHours/EngineRecordDetailPages');

const MeterBaselineDetailPage = page(load, 'MeterBaselineDetailPage');
const MeterCorrectionDetailPage = page(load, 'MeterCorrectionDetailPage');
const ClassificationDetailPage = page(load, 'ClassificationDetailPage');

const loadAllocations = () => import('../pages/tenant/engineHours/allocations/WorkAllocationsPage');
const loadAllocationDetail = () =>
  import('../pages/tenant/engineHours/allocations/WorkAllocationDetailPages');
const loadReports = () => import('../pages/tenant/engineHours/allocations/DailyReportsPage');
const loadReportDetail = () =>
  import('../pages/tenant/engineHours/allocations/DailyReportDetailPage');

const WorkAllocationsPage = page(loadAllocations, 'WorkAllocationsPage');
const WorkAllocationDetailPage = page(loadAllocationDetail, 'WorkAllocationDetailPage');
const AllocationCorrectionDetailPage = page(loadAllocationDetail, 'AllocationCorrectionDetailPage');
const DailyReportsPage = page(loadReports, 'DailyReportsPage');
const DailyReportDetailPage = page(loadReportDetail, 'DailyReportDetailPage');

type Guard = (permission: string, page: ReactNode) => ReactNode;

/** Engine-hour records: approvals (baselines, corrections, explanations), allocations, daily reports. */
export function engineHoursDetailRouteElements(guard: Guard): ReactNode[] {
  const read = PERMISSIONS.tenantMeterRead;
  const routes: [string, ReactNode][] = [
    [recordRoutePattern('METER_BASELINE'), <MeterBaselineDetailPage key="b" />],
    [recordRoutePattern('METER_CORRECTION'), <MeterCorrectionDetailPage key="c" />],
    [recordRoutePattern('ENGINE_HOURS_CLASSIFICATION'), <ClassificationDetailPage key="e" />],
    [ROUTES.tenantWorkAllocations, <WorkAllocationsPage key="wa" />],
    [
      ROUTES.tenantWorkAllocationCorrections,
      <Navigate key="wc" to={`${ROUTES.tenantWorkAllocations}?status=PROPOSED`} replace />,
    ],
    [recordRoutePattern('WORK_ALLOCATION_CORRECTION'), <AllocationCorrectionDetailPage key="c2" />],
    [recordRoutePattern('WORK_ALLOCATION'), <WorkAllocationDetailPage key="a" />],
    [ROUTES.tenantDailyReports, <DailyReportsPage key="dr" />],
    [recordRoutePattern('DAILY_REPORT'), <DailyReportDetailPage key="d" />],
  ];
  return routes.map(([path, element]) => (
    <Route key={path} path={path} element={guard(read, element)} />
  ));
}
