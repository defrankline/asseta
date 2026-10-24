import { Box, Button, Paper, Tab, Tabs } from '@mui/material';
import { Link as RouterLink, Navigate, useSearchParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { CASH_TABS_MOVED, cashTabPath, ROUTES } from '../../../navigation/routes';
import { useSession } from '../../../session/useSession';
import { InvoicesTab } from './invoices/InvoicesTab';
import { PaymentsTab } from './payments/PaymentsTab';

const TABS = [
  { key: 'invoices', label: 'Hire invoices' },
  { key: 'payments', label: 'Customer payments' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

const isTab = (v: string | null): v is TabKey => TABS.some((t) => t.key === v);

/** Tenant hire finance: customer invoices and receivables (R1-G). Cash custody has its own page. */
export function FinancePage() {
  const timeZone = useDisplayTimeZone();
  const { hasPermission } = useSession();
  const [params, setParams] = useSearchParams();
  const raw = params.get('tab');
  if (raw !== null && CASH_TABS_MOVED.has(raw)) {
    // Older links (notifications, cases) to the cash tabs that moved to the cash custody page.
    return <Navigate to={cashTabPath(raw)} replace />;
  }
  const tab: TabKey = isTab(raw) ? raw : 'invoices';
  return (
    <>
      <PageHeader
        title="Hire finance"
        subtitle="Customer hire invoices and payments. Separate from your Asseta subscription invoices."
        actions={
          hasPermission(PERMISSIONS.tenantFinanceRead) ? (
            <Button component={RouterLink} to={ROUTES.tenantCashCustody} variant="outlined">
              Cash custody
            </Button>
          ) : undefined
        }
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
        </Box>
      </Paper>
    </>
  );
}
