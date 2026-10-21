import ArrowBack from '@mui/icons-material/ArrowBack';
import { Box, Button, Paper, Stack, Tab, Tabs } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { tenantService } from '../../../api/services/tenantService';
import type { SubscriptionDto } from '../../../api/types';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useSession } from '../../../session/useSession';
import { ROUTES } from '../../../navigation/routes';
import { CompanyPanel } from './CompanyPanel';
import { EnrollmentsTab } from './EnrollmentsTab';
import { PendingChargesTab } from './PendingChargesTab';
import { RateVersionsTab } from './RateVersionsTab';
import { SubscriptionPanel } from './SubscriptionPanel';
import { TenantInvoicesTab } from './TenantInvoicesTab';

type TabKey = 'rates' | 'enrollments' | 'pending' | 'invoices';

function SubscriptionTabs({
  tenantId,
  subscription,
  onChanged,
  version,
}: {
  tenantId: string;
  subscription: SubscriptionDto;
  onChanged: () => void;
  version: number;
}) {
  const { hasPermission } = useSession();
  const canInvoices = hasPermission(PERMISSIONS.platformInvoiceRead);
  const [tab, setTab] = useState<TabKey>('rates');
  const active = tab === 'invoices' && !canInvoices ? 'rates' : tab;
  return (
    <Paper variant="outlined">
      <Tabs
        value={active}
        onChange={(_e, v: TabKey) => {
          setTab(v);
        }}
        variant="scrollable"
        aria-label="Subscription details"
      >
        <Tab value="rates" label="Rate versions" />
        <Tab value="enrollments" label="Enrollments" />
        <Tab value="pending" label="Pending charges" />
        {canInvoices && <Tab value="invoices" label="Invoices" />}
      </Tabs>
      <Box className="p-3">
        {active === 'rates' && <RateVersionsTab key={version} subscription={subscription} />}
        {active === 'enrollments' && (
          <EnrollmentsTab subscriptionId={subscription.id} onChanged={onChanged} />
        )}
        {active === 'pending' && (
          <PendingChargesTab
            subscriptionId={subscription.id}
            currency={subscription.current_rate?.currency ?? ''}
            reloadKey={version}
          />
        )}
        {active === 'invoices' && (
          <TenantInvoicesTab tenantId={tenantId} subscriptionId={subscription.id} />
        )}
      </Box>
    </Paper>
  );
}

interface SubscriptionSectionProps {
  tenantId: string;
  /** Lifecycle changes also change the tenant's access state and reason shown in the company panel. */
  onTenantChanged: () => void;
}

function SubscriptionSection({ tenantId, onTenantChanged }: SubscriptionSectionProps) {
  const [version, setVersion] = useState(0);
  const load = useCallback(
    (signal: AbortSignal) => tenantService.getSubscription(tenantId, signal),
    [tenantId],
  );
  const subscription = useAsyncResource(load, [version]);
  const changed = () => {
    setVersion((v) => v + 1);
    onTenantChanged();
  };
  return (
    <AsyncContent
      resource={subscription}
      errorTitle="Could not load the subscription"
      loadingLabel="Loading subscription"
    >
      {(s) => (
        <Stack spacing={3}>
          <SubscriptionPanel subscription={s} onChanged={changed} />
          <SubscriptionTabs
            tenantId={tenantId}
            subscription={s}
            onChanged={changed}
            version={version}
          />
        </Stack>
      )}
    </AsyncContent>
  );
}

/** Tenant company record, subscription lifecycle and billing ledger views. */
export function TenantDetailPage() {
  const { tenantId = '' } = useParams();
  const load = useCallback(
    (signal: AbortSignal) => tenantService.get(tenantId, signal),
    [tenantId],
  );
  const tenant = useAsyncResource(load);
  return (
    <>
      <PageHeader
        title={tenant.data?.display_name ?? 'Tenant'}
        subtitle={tenant.data?.legal_name ?? 'Tenant details'}
        actions={
          <Button component={RouterLink} to={ROUTES.platformTenants} startIcon={<ArrowBack />}>
            All tenants
          </Button>
        }
      />
      <AsyncContent
        resource={tenant}
        errorTitle="Could not load the tenant"
        loadingLabel="Loading tenant"
      >
        {(t) => (
          <Stack spacing={3}>
            <CompanyPanel tenant={t} onChanged={tenant.reload} />
            <Can permission={PERMISSIONS.platformSubscriptionRead}>
              <SubscriptionSection tenantId={t.id} onTenantChanged={tenant.reload} />
            </Can>
          </Stack>
        )}
      </AsyncContent>
    </>
  );
}
