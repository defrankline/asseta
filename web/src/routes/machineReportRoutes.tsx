import { lazy, type ReactNode } from 'react';
import { Route } from 'react-router';
import { PERMISSIONS } from '../access/permissionCodes';
import { ROUTES } from '../navigation/routes';

/** Machine report pages (ADR-008), code-split like every tenant page. */
const page = <K extends string>(load: () => Promise<Record<K, () => ReactNode>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));

const FieldMachineReportPage = page(
  () => import('../pages/tenant/machineReports/FieldMachineReportPage'),
  'FieldMachineReportPage',
);
const MachineReportsPage = page(
  () => import('../pages/tenant/machineReports/MachineReportsPage'),
  'MachineReportsPage',
);
const MachineReportDetailPage = page(
  () => import('../pages/tenant/machineReports/MachineReportDetailPage'),
  'MachineReportDetailPage',
);
const MachineReportReasonsPage = page(
  () => import('../pages/tenant/machineReports/MachineReportReasonsPage'),
  'MachineReportReasonsPage',
);

type Guard = (permission: string, page: ReactNode) => ReactNode;

/** Field work › Machine report, Approvals › Machine reports (+ detail), Administration › reasons. */
export function machineReportRouteElements(guard: Guard): ReactNode[] {
  const routes: [string, string, ReactNode][] = [
    [
      ROUTES.fieldMachineReport,
      PERMISSIONS.tenantMachineReportSubmit,
      <FieldMachineReportPage key="f" />,
    ],
    [
      ROUTES.tenantMachineReports,
      PERMISSIONS.tenantMachineReportRead,
      <MachineReportsPage key="l" />,
    ],
    [
      ROUTES.tenantMachineReportDetail,
      PERMISSIONS.tenantMachineReportRead,
      <MachineReportDetailPage key="d" />,
    ],
    [
      ROUTES.tenantMachineReportReasons,
      PERMISSIONS.tenantMeterReasons,
      <MachineReportReasonsPage key="r" />,
    ],
  ];
  return routes.map(([path, permission, element]) => (
    <Route key={path} path={path} element={guard(permission, element)} />
  ));
}
