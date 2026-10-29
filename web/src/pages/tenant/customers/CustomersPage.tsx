import Add from '@mui/icons-material/Add';
import { Box, Button, Stack } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { inactiveFilter } from '../../../api/lifecycle';
import { customerService } from '../../../api/services/customerService';
import type { CustomerDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { ActiveChip } from '../../../components/lifecycle/ActiveChip';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { ShowInactiveToggle } from '../../../components/lifecycle/ShowInactiveToggle';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useScrollIntoView } from '../../../hooks/useScrollIntoView';
import { customerDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { CreateCustomerDialog } from './CreateCustomerDialog';
import { RateCardSection } from './RateCardSection';
import { customerLabel, useCustomerActions } from './useCustomerActions';

/** Customers (open one for its contracts) and the tenant's rental rate cards. */
export function CustomersPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const [creating, setCreating] = useState(false);
  const [params] = useSearchParams();
  /** `?section=rate-cards` (e.g. from the go-live checklist) opens on the rate cards. */
  const rateCardsRef = useScrollIntoView<HTMLDivElement>(params.get('section') === 'rate-cards');
  const [showInactive, setShowInactive] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const refresh = () => {
    setReloadKey((k) => k + 1);
  };
  const view = (c: CustomerDto) => {
    void navigate(customerDetailPath(c.id));
  };
  const { actionsFor, dialogs } = useCustomerActions({
    onChanged: refresh,
    onReload: refresh,
    onView: view,
  });
  const filters = useMemo(() => inactiveFilter(showInactive), [showInactive]);
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      customerService.list(
        { page: q.page, page_size: q.page_size, q: q.q, filters: q.filters },
        signal,
      ),
    [],
  );
  const columns: DataColumn<CustomerDto>[] = [
    { id: 'code', header: 'Code', render: (c) => <strong>{c.code}</strong> },
    { id: 'name', header: 'Name', render: (c) => c.name },
    { id: 'contact', header: 'Contact', render: (c) => c.contact_name ?? '—' },
    { id: 'phone', header: 'Phone', render: (c) => c.contact_phone ?? '—' },
    {
      id: 'terms',
      header: 'Payment terms',
      render: (c) => `${String(c.payment_terms_days)} days`,
    },
    { id: 'active', header: 'State', render: (c) => <ActiveChip active={c.is_active} /> },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (c) => <RowActionsMenu label={customerLabel(c)} actions={actionsFor(c)} />,
    },
  ];
  return (
    <>
      <PageHeader
        title="Customers"
        subtitle="Customers, rental contracts and rate cards. Open a customer to see its contracts."
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
          filters={filters}
          toolbar={<ShowInactiveToggle checked={showInactive} onChange={setShowInactive} />}
          searchPlaceholder="Search name or code"
          emptyTitle="No customers found"
          emptyDescription="Add customers to create contracts and jobs."
          reloadKey={reloadKey}
          isRowMuted={(c) => !c.is_active}
          onRowClick={view}
        />
        <Box ref={rateCardsRef} id="rate-cards" sx={{ scrollMarginTop: 80 }}>
          <RateCardSection timeZone={timeZone} />
        </Box>
      </Stack>
      {creating && (
        <CreateCustomerDialog
          onClose={() => {
            setCreating(false);
          }}
          onCreated={(c) => {
            notify.success(`Customer ${c.name} created.`);
            refresh();
          }}
        />
      )}
      {dialogs}
    </>
  );
}
