import Add from '@mui/icons-material/Add';
import { Button, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { customerService } from '../../../api/services/customerService';
import type { CustomerDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { ContractsPanel } from './ContractsPanel';
import { CreateCustomerDialog } from './CreateCustomerDialog';
import { RateCardSection } from './RateCardSection';

const columns: DataColumn<CustomerDto>[] = [
  { id: 'code', header: 'Code', render: (c) => <strong>{c.code}</strong> },
  { id: 'name', header: 'Name', render: (c) => c.name },
  { id: 'contact', header: 'Contact', render: (c) => c.contact_name ?? '—' },
  { id: 'phone', header: 'Phone', render: (c) => c.contact_phone ?? '—' },
  { id: 'terms', header: 'Payment terms', render: (c) => `${String(c.payment_terms_days)} days` },
  {
    id: 'active',
    header: 'Active',
    render: (c) =>
      c.is_active ? (
        <StatusChip status="ACTIVE" tones={{ ACTIVE: 'success' }} label="Active" />
      ) : (
        <StatusChip status="INACTIVE" label="Inactive" />
      ),
  },
];

/** Customers, their contracts, and the tenant's rental rate cards. */
export function CustomersPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const [creating, setCreating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [selected, setSelected] = useState<CustomerDto | null>(null);
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      customerService.list({ page: q.page, page_size: q.page_size, q: q.q }, signal),
    [],
  );
  return (
    <>
      <PageHeader
        title="Customers"
        subtitle="Customers, rental contracts and rate cards. Select a customer to see its contracts."
        actions={
          <CanMutate permission={PERMISSIONS.tenantCustomerWrite}>
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setCreating(true);
              }}
            >
              New customer
            </Button>
          </CanMutate>
        }
      />
      <Stack spacing={3}>
        <ServerDataTable<CustomerDto>
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(c) => c.id}
          searchPlaceholder="Search name or code"
          emptyTitle="No customers found"
          emptyDescription="Add customers to create contracts and jobs."
          reloadKey={reloadKey}
          onRowClick={setSelected}
        />
        {selected !== null && (
          <ContractsPanel key={selected.id} customer={selected} timeZone={timeZone} />
        )}
        <RateCardSection timeZone={timeZone} />
      </Stack>
      {creating && (
        <CreateCustomerDialog
          onClose={() => {
            setCreating(false);
          }}
          onCreated={(c) => {
            notify.success(`Customer ${c.name} created.`);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
