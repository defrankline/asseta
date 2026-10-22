import ErrorOutline from '@mui/icons-material/ErrorOutlined';
import InfoOutlined from '@mui/icons-material/InfoOutlined';
import WarningAmber from '@mui/icons-material/WarningAmber';
import type { ReactNode } from 'react';
import type { NotificationDto, NotificationSeverity, NotificationTarget } from '../../api/types';
import type { SelectOption } from '../../components/forms/FormikSelectField';
import {
  caseDetailPath,
  exceptionsPath,
  financeTabPath,
  hireInvoiceDetailPath,
  jobDetailPath,
  machineDetailPath,
  platformInvoiceDetailPath,
  ROUTES,
  tenantDetailPath,
} from '../../navigation/routes';
import { ENTITY } from '../../realtime/entities';
import type { NotificationSeverity as ToastSeverity } from '../NotificationContext';

interface SeverityMeta {
  label: string;
  /** MUI palette colour of the icon / accent. */
  color: 'info' | 'warning' | 'error';
  toast: ToastSeverity;
  icon: ReactNode;
}

export const SEVERITY_META: Readonly<Record<NotificationSeverity, SeverityMeta>> = {
  INFO: { label: 'Information', color: 'info', toast: 'info', icon: <InfoOutlined /> },
  WARNING: { label: 'Warning', color: 'warning', toast: 'warning', icon: <WarningAmber /> },
  CRITICAL: { label: 'Critical', color: 'error', toast: 'error', icon: <ErrorOutline /> },
};

export const SEVERITY_OPTIONS: readonly SelectOption[] = [
  { value: 'CRITICAL', label: 'Critical' },
  { value: 'WARNING', label: 'Warning' },
  { value: 'INFO', label: 'Information' },
];

export const READ_STATE_OPTIONS: readonly SelectOption[] = [{ value: 'unread', label: 'Unread' }];

/** High-priority notifications also pop up as a toast when pushed. */
export function isHighPriority(n: NotificationDto): boolean {
  return n.priority === 'HIGH' || n.severity === 'CRITICAL';
}

/** Internal console path only (never an external or protocol-relative URL). */
function isInternalPath(path: string): boolean {
  return path.startsWith('/') && !path.startsWith('//') && !path.includes('\\');
}

const BY_ENTITY: Readonly<Record<string, (id: string | null) => string>> = {
  [ENTITY.alert]: () => ROUTES.tenantAlerts,
  [ENTITY.approval]: () => ROUTES.tenantApprovals,
  [ENTITY.expense]: () => ROUTES.tenantExpenses,
  [ENTITY.meterException]: () => exceptionsPath(),
  [ENTITY.customerPayment]: () => financeTabPath('payments'),
  [ENTITY.cashHandover]: () => financeTabPath('handovers'),
  [ENTITY.hireInvoice]: (id) =>
    id === null ? financeTabPath('invoices') : hireInvoiceDetailPath(id),
  [ENTITY.platformInvoice]: (id) =>
    id === null ? ROUTES.platformInvoices : platformInvoiceDetailPath(id),
  [ENTITY.platformPayment]: () => ROUTES.platformPayments,
  [ENTITY.anomalyCase]: (id) => (id === null ? ROUTES.tenantCases : caseDetailPath(id)),
  [ENTITY.job]: (id) => (id === null ? ROUTES.tenantJobs : jobDetailPath(id)),
  machine: (id) => (id === null ? ROUTES.tenantMachines : machineDetailPath(id)),
  tenant: (id) => (id === null ? ROUTES.platformTenants : tenantDetailPath(id)),
};

/** Screen a notification opens, or null when it is informational only. */
export function notificationTargetPath(target: NotificationTarget | null): string | null {
  if (target === null) return null;
  if (target.path !== null && isInternalPath(target.path)) return target.path;
  return BY_ENTITY[target.entity]?.(target.id) ?? null;
}
