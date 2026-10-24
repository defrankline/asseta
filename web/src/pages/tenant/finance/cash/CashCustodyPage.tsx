import { Box, Paper, Tab, Tabs } from '@mui/material';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router';
import { staffService } from '../../../../api/services/staffService';
import type { CashSupervisorSummaryDto, StaffDto } from '../../../../api/types';
import { PageHeader } from '../../../../components/feedback/PageHeader';
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
  { key: 'variances', label: 'Variances' },
  { key: 'retentions', label: 'Retentions' },
  { key: 'adjustments', label: 'Adjustments' },
  { key: 'reconciliation', label: 'Reconciliation' },
  { key: 'reasons', label: 'Reason lists' },
] as const;

type TabKey = (typeof CASH_TABS)[number]['key'];

const isTab = (v: string | null): v is TabKey => CASH_TABS.some((t) => t.key === v);

/**
 * Cash custody chain (accountability design C): custody per custodian, transfers, floats,
 * remittances, variances, retentions, adjustments, reconciliation drill-down and reason lists.
 * URL: `?tab=…` plus `staff_member_id` (custody / reconciliation), `id` (open a record), `status`.
 */
export function CashCustodyPage() {
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const [params, setParams] = useSearchParams();
  const raw = params.get('tab');
  const tab: TabKey = isTab(raw) ? raw : 'supervisors';
  const focusId = params.get('id');
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
  const openCustody = (row: CashSupervisorSummaryDto) => {
    staffService.get(row.staff_member_id).then(
      (staff) => {
        setCustodian(staff);
        setParams({ tab: 'custody' });
      },
      (err: unknown) => {
        notify.error(err, `Could not open ${row.staff_name}'s custody`);
      },
    );
  };
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
            setParams({ tab: v });
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
            <TransfersTab
              timeZone={timeZone}
              focusId={focusId}
              initialStatus={status(TRANSFER_STATUS_OPTIONS)}
            />
          )}
          {tab === 'floats' && <FloatsTab timeZone={timeZone} />}
          {tab === 'handovers' && <HandoversTab timeZone={timeZone} />}
          {tab === 'variances' && (
            <VariancesTab
              timeZone={timeZone}
              focusId={focusId}
              initialStatus={status(VARIANCE_STATUS_OPTIONS)}
            />
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
