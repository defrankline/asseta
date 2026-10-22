import { Box } from '@mui/material';
import { useCallback, useState } from 'react';
import type { TenantDto } from '../../../api/types';
import { AsyncAutocomplete } from '../../../components/data/AsyncAutocomplete';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { searchTenants, tenantLabel } from '../shared/platformLookups';
import { SmsWalletView } from './SmsWalletView';

/** Platform console: pick a tenant (server search) and view its SMS wallet. */
export function PlatformSmsWalletsPage() {
  const [tenant, setTenant] = useState<TenantDto | null>(null);
  const same = useCallback((a: TenantDto, b: TenantDto) => a.id === b.id, []);
  return (
    <>
      <PageHeader
        title="SMS wallets"
        subtitle="Tenant SMS credits: funded by paid SMS bundle invoice lines, spent per message"
      />
      <Box className="mb-4 max-w-md">
        <AsyncAutocomplete<TenantDto>
          label="Tenant"
          value={tenant}
          onChange={setTenant}
          fetchOptions={searchTenants}
          getOptionLabel={tenantLabel}
          isOptionEqualToValue={same}
        />
      </Box>
      {tenant === null ? (
        <EmptyState
          title="Choose a tenant"
          description="Search for a tenant to see its SMS wallet."
        />
      ) : (
        <SmsWalletView key={tenant.id} tenantId={tenant.id} />
      )}
    </>
  );
}

/** Tenant console: the active tenant's own SMS wallet (read-only). */
export function TenantSmsWalletPage() {
  return (
    <>
      <PageHeader
        title="SMS wallet"
        subtitle="SMS credits used for notifications; top up by paying an SMS bundle invoice"
      />
      <SmsWalletView tenantId={null} />
    </>
  );
}
