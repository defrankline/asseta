import Add from '@mui/icons-material/Add';
import { Alert, Box, Button, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import type { CustomerDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { recordPath, RECORD_LIST_ROUTES } from '../../../navigation/recordRoutes';
import { CustomerFilter } from '../shared/financePickers';
import { PersonName } from '../shared/PersonName';
import { RecordDetail } from '../shared/RecordDetail';
import { useRecordById } from '../shared/useRecordById';
import { DecideButton, HoursOffNotice } from './HoursDialogs';
import { PROPOSAL_STATUS_OPTIONS } from './hoursDisplay';
import {
  capitalised,
  proposalStatusChip,
  useProposalKit,
  type ProposalConfig,
  type ProposalRow,
} from './proposalKit';

/**
 * Customer proposals decided by a second person: list with status / customer filters, propose;
 * a row opens its detail page (edit / withdraw your own, decide others', revoke approved ones).
 */
export function ProposalsPage<D extends ProposalRow>(config: ProposalConfig<D>) {
  const { noun, calls, kind } = config;
  const navigate = useNavigate();
  const [status, setStatus] = useState('PROPOSED');
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const kit = useProposalKit(config, () => {
    setReloadKey((k) => k + 1);
  });
  const fetchPage = useCallback<FetchPage<D>>(
    (query, signal) => calls.list(query, signal),
    [calls],
  );
  const open = (d: D) => {
    void navigate(recordPath(kind, d.id));
  };
  const columns: DataColumn<D>[] = [
    { id: 'customer', header: 'Customer', render: kit.customer },
    ...config.valueColumns,
    { id: 'period', header: 'In effect', render: kit.period },
    {
      id: 'by',
      header: 'Proposed by',
      render: (d) => <PersonName userId={d.proposed_by} name={d.proposed_by_name} />,
    },
    { id: 'status', header: 'Status', render: (d) => proposalStatusChip(d.status) },
    {
      id: 'decide',
      header: '',
      align: 'right',
      render: (d) => (
        <Box
          className="flex justify-end gap-1"
          onClick={(e) => {
            e.stopPropagation();
          }}
        >
          {kit.canApprove && d.status === 'PROPOSED' && (
            <DecideButton
              own={kit.own(d)}
              onClick={() => {
                kit.decide(d);
              }}
            />
          )}
          <RowActionsMenu
            label={`${noun} for ${kit.customer(d)}`}
            actions={[
              {
                key: 'view',
                label: 'View details',
                onClick: () => {
                  open(d);
                },
              },
              ...kit.actionsFor(d).filter((a) => a.key !== 'decide'),
            ]}
          />
        </Box>
      ),
    },
  ];
  return (
    <>
      <PageHeader
        title={config.title}
        subtitle={config.subtitle}
        actions={
          kit.canPropose && (
            <Button variant="contained" startIcon={<Add />} onClick={kit.propose}>
              {`Propose ${noun}`}
            </Button>
          )
        }
      />
      <Stack spacing={2}>
        <HoursOffNotice off={kit.hours.status === 'known' && !kit.hours.on} />
        <Alert severity="info">
          Only approved {noun}s in effect apply. The person who proposed one cannot decide it.
        </Alert>
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(d) => d.id}
          searchable={false}
          reloadKey={reloadKey}
          filters={{ status: status === '' ? undefined : status, customer_id: customer?.id }}
          emptyTitle={`No ${noun}s`}
          onRowClick={open}
          isRowMuted={(d) => d.status !== 'PROPOSED' && d.status !== 'APPROVED'}
          toolbar={
            <Box className="flex flex-wrap gap-3">
              <StaticSelectFilter
                label="Status"
                value={status}
                options={PROPOSAL_STATUS_OPTIONS}
                allLabel="All statuses"
                onChange={setStatus}
              />
              <Box sx={{ minWidth: 240 }}>
                <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
              </Box>
            </Box>
          }
        />
      </Stack>
      {kit.dialogs}
    </>
  );
}

/** One customer proposal (exact-record link): details, the list row's commands and history. */
export function ProposalDetailPage<D extends ProposalRow>(config: ProposalConfig<D>) {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const { get } = config.calls;
  const load = useCallback((rid: string, signal: AbortSignal) => get(rid, signal), [get]);
  const res = useRecordById(load, id);
  const kit = useProposalKit(config, res.reload);
  return (
    <>
      <RecordDetail
        resource={res}
        what={config.noun}
        back={{ label: config.title, to: RECORD_LIST_ROUTES[config.kind] }}
        timeZone={timeZone}
        title={(d) => `${capitalised(config.noun)} for ${kit.customer(d)}`}
        status={(d) => proposalStatusChip(d.status)}
        actions={kit.actionsFor}
        primaryKey="decide"
        items={kit.items}
        history={kit.history}
      />
      {kit.dialogs}
    </>
  );
}
