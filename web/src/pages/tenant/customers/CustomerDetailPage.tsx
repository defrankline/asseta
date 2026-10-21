import { Box, Paper, Tab, Tabs } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { useParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { customerService } from '../../../api/services/customerService';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import {
  DetailSection,
  EntityDetailsLayout,
} from '../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { ROUTES } from '../../../navigation/routes';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { CustomerBalanceTab, CustomerStatementTab } from './CustomerFinanceTabs';
import { ContractsPanel } from './ContractsPanel';
import { CustomerFields } from './CustomerViews';
import { customerLabel, useCustomerActions } from './useCustomerActions';

type TabKey = 'contracts' | 'balance' | 'statement';

/** Contracts, and with `tenant.finance.read` the receivable Balance and Statement (per currency). */
function CustomerTabs({ customerId, children }: { customerId: string; children: ReactNode }) {
  const { hasPermission } = useSession();
  const timeZone = useDisplayTimeZone();
  const [tab, setTab] = useState<TabKey>('contracts');
  if (!hasPermission(PERMISSIONS.tenantFinanceRead)) return <>{children}</>;
  return (
    <Paper variant="outlined">
      <Tabs
        value={tab}
        aria-label="Customer records"
        onChange={(_e, v: TabKey) => {
          setTab(v);
        }}
      >
        <Tab value="contracts" label="Contracts" />
        <Tab value="balance" label="Balance" />
        <Tab value="statement" label="Statement" />
      </Tabs>
      <Box className="p-3">
        {tab === 'contracts' && children}
        {tab === 'balance' && <CustomerBalanceTab customerId={customerId} />}
        {tab === 'statement' && (
          <CustomerStatementTab customerId={customerId} timeZone={timeZone} />
        )}
      </Box>
    </Paper>
  );
}

/** Customer record with its contracts, balance and statement; edit, deactivate and reactivate. */
export function CustomerDetailPage() {
  const { customerId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const load = useCallback(
    (signal: AbortSignal) => customerService.get(customerId, signal),
    [customerId],
  );
  const resource = useAsyncResource(load);
  const customer = resource.data;
  const { actionsFor, dialogs } = useCustomerActions({
    onChanged: resource.reload,
    onReload: resource.reload,
  });
  return (
    <>
      <EntityDetailsLayout
        title={customer === null ? 'Customer' : customerLabel(customer)}
        subtitle="Customer details"
        back={{ label: 'All customers', to: ROUTES.tenantCustomers }}
        {...(customer !== null
          ? {
              status: <ActiveChip active={customer.is_active} />,
              actions: <ActionButtons actions={actionsFor(customer)} />,
            }
          : {})}
        inactive={
          customer !== null && !customer.is_active
            ? {
                title:
                  'This customer is inactive: no new contracts or jobs. Its history, balance and statement are kept.',
                reason: customer.deactivation_reason ?? null,
                since:
                  customer.deactivated_at == null
                    ? null
                    : formatInstantIn(customer.deactivated_at, timeZone),
              }
            : null
        }
      >
        <AsyncContent
          resource={resource}
          errorTitle="Could not load the customer"
          loadingLabel="Loading customer"
        >
          {(c) => (
            <div className="flex flex-col gap-6">
              <DetailSection title="Customer">
                <CustomerFields customer={c} />
              </DetailSection>
              <CustomerTabs customerId={c.id}>
                <ContractsPanel key={c.id} customer={c} timeZone={timeZone} />
              </CustomerTabs>
            </div>
          )}
        </AsyncContent>
      </EntityDetailsLayout>
      {dialogs}
    </>
  );
}
