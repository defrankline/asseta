import { Box, Paper, Tab, Tabs } from '@mui/material';
import { useState } from 'react';
import { useSearchParams } from 'react-router';
import { staffService } from '../../../api/services/staffService';
import type { CashSupervisorSummaryDto, StaffDto } from '../../../api/types';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { CustodyTab } from './cash/CustodyTab';
import { HandoversTab } from './cash/HandoversTab';
import { ReconciliationTab } from './cash/ReconciliationTab';
import { SupervisorsTab } from './cash/SupervisorsTab';
import { InvoicesTab } from './invoices/InvoicesTab';
import { PaymentsTab } from './payments/PaymentsTab';

const TABS = [
  { key: 'invoices', label: 'Hire invoices' },
  { key: 'payments', label: 'Customer payments' },
  { key: 'supervisors', label: 'All supervisors' },
  { key: 'custody', label: 'Cash custody' },
  { key: 'handovers', label: 'Handovers' },
  { key: 'reconciliation', label: 'Reconciliation' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

const isTab = (v: string | null): v is TabKey => TABS.some((t) => t.key === v);

/** Tenant hire finance: customer invoices and receivables, supervisor cash custody (R1-G). */
export function FinancePage() {
  const timeZone = useDisplayTimeZone();
  const [params, setParams] = useSearchParams();
  const raw = params.get('tab');
  const tab: TabKey = isTab(raw) ? raw : 'invoices';
  /** Shared between custody and reconciliation so switching tabs keeps the supervisor. */
  const [supervisor, setSupervisor] = useState<StaffDto | null>(null);
  const notify = useNotify();
  /** A row of the all-supervisors summary opens that supervisor's custody tab. */
  const openCustody = (row: CashSupervisorSummaryDto) => {
    staffService.get(row.staff_member_id).then(
      (staff) => {
        setSupervisor(staff);
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
        title="Hire finance"
        subtitle="Customer hire invoices, payments and supervisor cash. Separate from your Asseta subscription invoices."
      />
      <Paper variant="outlined">
        <Tabs
          value={tab}
          variant="scrollable"
          aria-label="Hire finance"
          onChange={(_e, v: TabKey) => {
            setParams({ tab: v });
          }}
        >
          {TABS.map((t) => (
            <Tab key={t.key} value={t.key} label={t.label} />
          ))}
        </Tabs>
        <Box className="p-3">
          {tab === 'invoices' && <InvoicesTab timeZone={timeZone} />}
          {tab === 'payments' && <PaymentsTab timeZone={timeZone} />}
          {tab === 'supervisors' && <SupervisorsTab onOpenSupervisor={openCustody} />}
          {tab === 'custody' && (
            <CustodyTab
              timeZone={timeZone}
              supervisor={supervisor}
              onSupervisorChange={setSupervisor}
            />
          )}
          {tab === 'handovers' && <HandoversTab timeZone={timeZone} />}
          {tab === 'reconciliation' && (
            <ReconciliationTab supervisor={supervisor} onSupervisorChange={setSupervisor} />
          )}
        </Box>
      </Paper>
    </>
  );
}
