import Add from '@mui/icons-material/Add';
import { Button, Paper, Stack, Typography } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { customerService } from '../../../api/services/customerService';
import type { ContractDto, ContractStatus, CustomerDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip, type StatusTone } from '../../../components/display/StatusChip';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { useJobSites } from '../shared/useJobSites';
import { CreateContractDialog } from './CreateContractDialog';

const CONTRACT_TONES: Readonly<Record<ContractStatus, StatusTone>> = {
  DRAFT: 'info',
  ACTIVE: 'success',
  CLOSED: 'default',
};

interface ContractsPanelProps {
  customer: CustomerDto;
  timeZone: string;
}

/** Contracts of one customer (server paged) with a create action. */
export function ContractsPanel({ customer, timeZone }: ContractsPanelProps) {
  const notify = useNotify();
  const { label: siteLabel } = useJobSites();
  const [creating, setCreating] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const filters = useMemo(() => ({ customer_id: customer.id }), [customer.id]);
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      customerService.listContracts(
        { page: q.page, page_size: q.page_size, q: q.q, filters: q.filters },
        signal,
      ),
    [],
  );
  const columns: DataColumn<ContractDto>[] = [
    { id: 'number', header: 'Contract', render: (c) => <strong>{c.contract_number}</strong> },
    {
      id: 'status',
      header: 'Status',
      render: (c) => <StatusChip status={c.status} tones={CONTRACT_TONES} />,
    },
    { id: 'starts', header: 'Starts', render: (c) => formatInstantIn(c.starts_on, timeZone) },
    {
      id: 'ends',
      header: 'Ends',
      render: (c) => (c.ends_on === null ? 'Open-ended' : formatInstantIn(c.ends_on, timeZone)),
    },
    { id: 'site', header: 'Default site', render: (c) => siteLabel(c.job_site_id) },
    { id: 'currency', header: 'Currency', render: (c) => c.currency },
    { id: 'reference', header: 'Reference', render: (c) => c.reference ?? '—' },
  ];
  return (
    <Paper variant="outlined" className="p-4">
      <Stack spacing={2}>
        <Stack direction="row" className="items-center justify-between">
          <Typography variant="subtitle1" component="h2">
            Contracts · {customer.name}
          </Typography>
          <CanMutate permission={PERMISSIONS.tenantCustomerWrite}>
            <Button
              variant="outlined"
              startIcon={<Add />}
              onClick={() => {
                setCreating(true);
              }}
            >
              New contract
            </Button>
          </CanMutate>
        </Stack>
        <ServerDataTable<ContractDto>
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(c) => c.id}
          filters={filters}
          searchable={false}
          emptyTitle="No contracts yet"
          emptyDescription="Create a contract to start booking jobs for this customer."
          reloadKey={reloadKey}
        />
      </Stack>
      {creating && (
        <CreateContractDialog
          customer={customer}
          timeZone={timeZone}
          onClose={() => {
            setCreating(false);
          }}
          onCreated={(c) => {
            notify.success(`Contract ${c.contract_number} created.`);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </Paper>
  );
}
