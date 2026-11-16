import { Button, Paper } from '@mui/material';
import { Link as RouterLink, Navigate, useSearchParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { CASH_TABS_MOVED, cashTabPath, ROUTES } from '../../../navigation/routes';
import { useSession } from '../../../session/useSession';
import { PaymentsTab } from './payments/PaymentsTab';

/** Tenant hire finance: customer payments (R1-G). Cash custody has its own page. */
export function FinancePage() {
  const timeZone = useDisplayTimeZone();
  const { hasPermission } = useSession();
  const [params] = useSearchParams();
  const raw = params.get('tab');
  if (raw !== null && CASH_TABS_MOVED.has(raw)) {
    // Older links (notifications, cases) to the cash tabs that moved to the cash custody page.
    return <Navigate to={cashTabPath(raw)} replace />;
  }
  return (
    <>
      <PageHeader
        title="Hire finance"
        subtitle="Customer payments. Separate from your Asseta subscription invoices."
        actions={
          hasPermission(PERMISSIONS.tenantFinanceRead) ? (
            <Button component={RouterLink} to={ROUTES.tenantCashCustody} variant="outlined">
              Cash custody
            </Button>
          ) : undefined
        }
      />
      <Paper variant="outlined" className="p-3">
        <PaymentsTab timeZone={timeZone} />
      </Paper>
    </>
  );
}
