import { Box, Paper, Tab, Tabs } from '@mui/material';
import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router';
import { staffService } from '../../../../api/services/staffService';
import type { CashSupervisorSummaryDto, StaffDto } from '../../../../api/types';
import { PageHeader } from '../../../../components/feedback/PageHeader';
import { recordPath, type RecordKind } from '../../../../navigation/recordRoutes';
import { cashTabPath } from '../../../../navigation/routes';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../../notifications/useNotify';
import { AdjustmentsTab } from './AdjustmentsTab';
import { CashReasonsTab } from './CashReasonsTab';
import {
  DECISION_STATUS_OPTIONS,
  TRANSFER_STATUS_OPTIONS,
  VARIANCE_STATUS_OPTIONS,
} from './custodyDisplay';
import { CustodyTab } from './CustodyTab';
import { FloatsTab } from './FloatsTab';
import { HandoversTab } from './HandoversTab';
import { ReconciliationTab } from './ReconciliationTab';
import { RemittanceOverdueTab } from './RemittanceOverdueTab';
import { RetentionsTab } from './RetentionsTab';
import { SupervisorsTab } from './SupervisorsTab';
import { TransfersTab } from './TransfersTab';
import { VariancesTab } from './VariancesTab';

const CASH_TABS = [
  { key: 'supervisors', label: 'All custodians' },
  { key: 'custody', label: 'Custody' },
  { key: 'transfers', label: 'Transfers' },
  { key: 'floats', label: 'Floats' },
  { key: 'handovers', label: 'Remittances' },
  { key: 'overdue', label: 'Overdue remittances' },
  { key: 'variances', label: 'Variances' },
  { key: 'retentions', label: 'Retentions' },
  { key: 'adjustments', label: 'Adjustments' },
  { key: 'reconciliation', label: 'Reconciliation' },
  { key: 'reasons', label: 'Reason lists' },
] as const;

export type CashTabKey = (typeof CASH_TABS)[number]['key'];
type TabKey = CashTabKey;

/** Old `?tab=…&id=…` links (e.g. reconciliation drill-downs) open the record's own page. */
const RECORD_OF_TAB: Partial<Record<TabKey, RecordKind>> = {
  transfers: 'CASH_TRANSFER',
  floats: 'CASH_FLOAT',
  handovers: 'CASH_REMITTANCE',
  overdue: 'REMITTANCE_OVERDUE',
  variances: 'CASH_VARIANCE',
  retentions: 'CASH_RETENTION',
  adjustments: 'CUSTODY_ADJUSTMENT',
};

const isTab = (v: string | null): v is TabKey => CASH_TABS.some((t) => t.key === v);

/**
 * Cash custody chain (accountability design C): custody per custodian, transfers, floats,
 * remittances, variances, retentions, adjustments, reconciliation drill-down and reason lists.
 * URL: `?tab=…` plus `staff_member_id` (custody / reconciliation), `status`; `id` opens the
 * record's page. List routes (`/tenant/finance/cash/transfers`, …) render it on that tab (`tab`).
 */
export function CashCustodyPage({ tab: fixedTab }: { tab?: CashTabKey } = {}) {
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const raw = params.get('tab');
  const tab: TabKey = fixedTab ?? (isTab(raw) ? raw : 'supervisors');
  const focusId = params.get('id');
  const focusKind = RECORD_OF_TAB[tab];
  /** A status filter from the URL, only when it is one of the tab's options (else the tab's default). */
  const status = (options: readonly { value: string }[]): string | undefined => {
    const raw = params.get('status');
    return raw !== null && (raw === '' || options.some((o) => o.value === raw)) ? raw : undefined;
  };
  const staffParam = params.get('staff_member_id');
  /** Shared between custody and reconciliation so switching tabs keeps the custodian. */
  const [custodian, setCustodian] = useState<StaffDto | null>(null);
  useEffect(() => {
    if (staffParam === null || custodian?.id === staffParam) return undefined;
    const controller = new AbortController();
    staffService.get(staffParam, controller.signal).then(setCustodian, () => {
      // Without staff read access the custodian is chosen by hand.
    });
    return () => {
      controller.abort();
    };
  }, [staffParam, custodian?.id]);
  const changeTab = (v: TabKey) => {
    if (fixedTab === undefined) setParams({ tab: v });
    else void navigate(cashTabPath(v));
  };
  const openCustody = (row: CashSupervisorSummaryDto) => {
    staffService.get(row.staff_member_id).then(
      (staff) => {
        setCustodian(staff);
        changeTab('custody');
      },
      (err: unknown) => {
        notify.error(err, `Could not open ${row.staff_name}'s custody`);
      },
    );
  };
  if (focusId !== null && focusKind !== undefined) {
    return <Navigate replace to={recordPath(focusKind, focusId)} />;
  }
  return (
    <>
      <PageHeader
        title="Cash custody"
        subtitle="Cash held by custodians, transfers between them, remittances to the company and their reconciliation"
      />
      <Paper variant="outlined">
        <Tabs
          value={tab}
          variant="scrollable"
          aria-label="Cash custody"
          onChange={(_e, v: TabKey) => {
            changeTab(v);
          }}
        >
          {CASH_TABS.map((t) => (
            <Tab key={t.key} value={t.key} label={t.label} />
          ))}
        </Tabs>
        <Box className="p-3">
          {tab === 'supervisors' && <SupervisorsTab onOpenSupervisor={openCustody} />}
          {tab === 'custody' && (
            <CustodyTab
              timeZone={timeZone}
              supervisor={custodian}
              onSupervisorChange={setCustodian}
            />
          )}
          {tab === 'transfers' && (
            <TransfersTab timeZone={timeZone} initialStatus={status(TRANSFER_STATUS_OPTIONS)} />
          )}
          {tab === 'floats' && <FloatsTab timeZone={timeZone} />}
          {tab === 'handovers' && <HandoversTab timeZone={timeZone} />}
          {tab === 'overdue' && <RemittanceOverdueTab timeZone={timeZone} />}
          {tab === 'variances' && (
            <VariancesTab timeZone={timeZone} initialStatus={status(VARIANCE_STATUS_OPTIONS)} />
          )}
          {tab === 'retentions' && (
            <RetentionsTab timeZone={timeZone} initialStatus={status(DECISION_STATUS_OPTIONS)} />
          )}
          {tab === 'adjustments' && (
            <AdjustmentsTab timeZone={timeZone} initialStatus={status(DECISION_STATUS_OPTIONS)} />
          )}
          {tab === 'reconciliation' && (
            <ReconciliationTab
              supervisor={custodian}
              onSupervisorChange={setCustodian}
              timeZone={timeZone}
            />
          )}
          {tab === 'reasons' && <CashReasonsTab timeZone={timeZone} />}
        </Box>
      </Paper>
    </>
  );
}
