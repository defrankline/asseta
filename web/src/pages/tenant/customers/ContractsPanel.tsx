import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { CanMutate } from '../../../access/CanMutate';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import { inactiveFilter } from '../../../api/lifecycle';
import { customerService } from '../../../api/services/customerService';
import type { ContractDto, CustomerDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { ServerQuery } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { DetailSection } from '../../../components/lifecycle/EntityDetailsLayout';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { ShowInactiveToggle } from '../../../components/lifecycle/ShowInactiveToggle';
import { useLifecycleDialog } from '../../../components/lifecycle/useLifecycleDialog';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { useJobSites } from '../shared/useJobSites';
import { ContractDetailsDrawer } from './ContractDetailsDrawer';
import { CreateContractDialog } from './CreateContractDialog';
import {
  CONTRACT_CLOSE_CONSEQUENCES,
  CONTRACT_ERROR_HINTS,
  CONTRACT_TONES,
} from './customerLifecycle';
import { EditContractDialog } from './EditContractDialog';

interface ContractsPanelProps {
  customer: CustomerDto;
  timeZone: string;
}

/** Contracts of one customer: view, create, edit, close and reopen (closed hidden by default). */
export function ContractsPanel({ customer, timeZone }: ContractsPanelProps) {
  const notify = useNotify();
  const canWrite = useCanMutate(PERMISSIONS.tenantCustomerWrite);
  const { label: siteLabel } = useJobSites();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ContractDto | null>(null);
  const [viewing, setViewing] = useState<ContractDto | null>(null);
  const [showClosed, setShowClosed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const refresh = () => {
    setReloadKey((k) => k + 1);
  };
  const filters = useMemo(
    () => ({ customer_id: customer.id, ...inactiveFilter(showClosed) }),
    [customer.id, showClosed],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      customerService.listContracts(
        { page: q.page, page_size: q.page_size, q: q.q, filters: q.filters },
        signal,
      ),
    [],
  );
  const lifecycle = useLifecycleDialog<ContractDto>({
    labelOf: (c) => c.contract_number,
    noun: 'contract',
    deactivateLabel: 'Close contract',
    reactivateLabel: 'Reopen contract',
    consequences: CONTRACT_CLOSE_CONSEQUENCES,
    errorHints: CONTRACT_ERROR_HINTS,
    deactivate: (c, body, key) =>
      customerService.closeContract(c.id, { ...body, version: c.version }, key),
    reactivate: (c, body, key) =>
      customerService.reopenContract(c.id, { ...body, version: c.version }, key),
    onDone: (c, kind) => {
      notify.success(
        `Contract ${c.contract_number} ${kind === 'deactivate' ? 'closed' : 'reopened'}.`,
      );
      setViewing(null);
      refresh();
    },
    onReload: refresh,
  });
  const actionsFor = (c: ContractDto, inDrawer: boolean): RowAction[] => {
    const closed = c.status === 'CLOSED';
    return [
      {
        key: 'view',
        label: 'View details',
        hidden: inDrawer,
        onClick: () => {
          setViewing(c);
        },
      },
      {
        key: 'edit',
        label: 'Edit',
        hidden: !canWrite || closed,
        onClick: () => {
          setViewing(null);
          setEditing(c);
        },
      },
      {
        key: 'close',
        label: 'Close contract',
        destructive: true,
        hidden: !canWrite || closed,
        onClick: () => {
          lifecycle.open('deactivate', c);
        },
      },
      {
        key: 'reopen',
        label: 'Reopen contract',
        hidden: !canWrite || !closed,
        onClick: () => {
          lifecycle.open('reactivate', c);
        },
      },
    ];
  };
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
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (c) => (
        <RowActionsMenu label={`contract ${c.contract_number}`} actions={actionsFor(c, false)} />
      ),
    },
  ];
  const customerLabel = `${customer.code} · ${customer.name}`;
  return (
    <DetailSection
      title="Contracts"
      actions={
        customer.is_active ? (
          <CanMutate permission={PERMISSIONS.tenantCustomerWrite}>
            <Button
              variant="outlined"
              size="small"
              startIcon={<Add />}
              onClick={() => {
                setCreating(true);
              }}
            >
              New contract
            </Button>
          </CanMutate>
        ) : undefined
      }
    >
      <Box>
        <ServerDataTable<ContractDto>
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(c) => c.id}
          filters={filters}
          searchPlaceholder="Search contract number or reference"
          toolbar={
            <ShowInactiveToggle checked={showClosed} onChange={setShowClosed} label="Show closed" />
          }
          emptyTitle="No contracts"
          emptyDescription="Create a contract to start booking jobs for this customer."
          reloadKey={reloadKey}
          isRowMuted={(c) => c.status === 'CLOSED'}
          onRowClick={setViewing}
        />
      </Box>
      {viewing !== null && (
        <ContractDetailsDrawer
          contract={viewing}
          customerLabel={customerLabel}
          siteLabel={siteLabel}
          timeZone={timeZone}
          actions={actionsFor(viewing, true)}
          onClose={() => {
            setViewing(null);
          }}
        />
      )}
      {creating && (
        <CreateContractDialog
          customer={customer}
          timeZone={timeZone}
          onClose={() => {
            setCreating(false);
          }}
          onCreated={(c) => {
            notify.success(`Contract ${c.contract_number} created.`);
            refresh();
          }}
        />
      )}
      {editing !== null && (
        <EditContractDialog
          contract={editing}
          customer={customer}
          timeZone={timeZone}
          onClose={() => {
            setEditing(null);
          }}
          onReload={refresh}
          onSaved={(c) => {
            notify.success(`Contract ${c.contract_number} updated.`);
            refresh();
          }}
        />
      )}
      {lifecycle.dialog}
    </DetailSection>
  );
}
