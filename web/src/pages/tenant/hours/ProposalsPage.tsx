import Add from '@mui/icons-material/Add';
import { Alert, Box, Button, Stack } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { useCanMutate } from '../../../access/useCanMutate';
import type { DecisionIn, ProposalStatus, ReasonIn } from '../../../api/hoursTypes';
import type { Page } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { KeyValueGrid, type KeyValueItem } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import { RowActionsMenu } from '../../../components/lifecycle/RowActionsMenu';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import type { TenantListQuery } from '../../../api/services/tenantRequest';
import type { CustomerDto } from '../../../api/types';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { formatDate } from '../../../utils/dates';
import { formatInstantIn } from '../../../utils/time';
import { CustomerFilter } from '../shared/financePickers';
import { PersonName } from '../shared/PersonName';
import { useCustomerLabels, useMyUserId } from '../shared/useFinanceLabels';
import { DecideButton, DecideDialog, HoursOffNotice, ReasonDialog } from './HoursDialogs';
import {
  OWN_REQUEST_TEXT,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_STATUS_OPTIONS,
  PROPOSAL_STATUS_TONES,
} from './hoursDisplay';
import { useHoursPolicy } from './useHoursPolicy';

/** Fields every customer proposal (discount, credit arrangement) carries. */
export interface ProposalRow {
  id: string;
  customer_id: string;
  status: ProposalStatus;
  proposed_by: string | null;
  proposed_at: string;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
  effective_from: string;
  effective_to: string | null;
  reason: string;
  revoke_reason: string | null;
  revoked_at: string | null;
  version: number;
}

export interface ProposalCalls<D> {
  list: (query: TenantListQuery, signal?: AbortSignal) => Promise<Page<D>>;
  decide: (id: string, body: DecisionIn, key: string) => Promise<D>;
  withdraw: (id: string, body: ReasonIn, key: string) => Promise<D>;
  revoke: (id: string, body: ReasonIn, key: string) => Promise<D>;
}

interface ProposalsPageProps<D extends ProposalRow> {
  title: string;
  subtitle: string;
  /** e.g. "discount" (toasts, buttons). */
  noun: string;
  calls: ProposalCalls<D>;
  proposePermission: string;
  approvePermission: string;
  /** Capability allowed by the tenant policy in addition to `hours.enabled`. */
  allowed: (policy: NonNullable<ReturnType<typeof useHoursPolicy>['policy']>) => boolean;
  /** The proposal's own value (percent, limit) as table columns. */
  valueColumns: DataColumn<D>[];
  /** The proposal's own value in the details drawer / decide summary. */
  valueItems: (d: D) => KeyValueItem[];
  approveExplanation: string;
  /** Propose (no record) or edit (record) dialog; mount only while open. */
  renderForm: (props: {
    record: D | null;
    onClose: () => void;
    onSaved: (d: D) => void;
  }) => ReactNode;
}

/**
 * Customer proposals decided by a second person: list with status / customer filters, propose,
 * edit or withdraw your own proposal, decide others' (approve permission), revoke approved ones.
 */
export function ProposalsPage<D extends ProposalRow>({
  title,
  subtitle,
  noun,
  calls,
  proposePermission,
  approvePermission,
  allowed,
  valueColumns,
  valueItems,
  approveExplanation,
  renderForm,
}: ProposalsPageProps<D>) {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const customerName = useCustomerLabels();
  const me = useMyUserId();
  const hours = useHoursPolicy();
  const on = hours.on && (hours.policy === null || allowed(hours.policy));
  const canPropose = useCanMutate(proposePermission) && on;
  const canApprove = useCanMutate(approvePermission);
  const [status, setStatus] = useState('PROPOSED');
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [form, setForm] = useState<{ record: D | null } | null>(null);
  const [viewing, setViewing] = useState<D | null>(null);
  const [deciding, setDeciding] = useState<D | null>(null);
  const [reasoning, setReasoning] = useState<{ kind: 'withdraw' | 'revoke'; d: D } | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<D>>(
    (query, signal) => calls.list(query, signal),
    [calls],
  );
  const changed = (d: D, message: string) => {
    notify.success(message);
    setReloadKey((k) => k + 1);
    setViewing((v) => (v?.id === d.id ? d : v));
  };
  const own = (d: D) => me !== null && d.proposed_by === me;
  const actionsFor = (d: D): RowAction[] => [
    {
      key: 'view',
      label: 'View details',
      onClick: () => {
        setViewing(d);
      },
    },
    {
      key: 'edit',
      label: 'Edit',
      hidden: !canPropose || d.status !== 'PROPOSED' || !own(d),
      onClick: () => {
        setViewing(null);
        setForm({ record: d });
      },
    },
    {
      key: 'decide',
      label: 'Decide',
      hidden: !canApprove || d.status !== 'PROPOSED',
      disabled: own(d),
      disabledReason: OWN_REQUEST_TEXT,
      onClick: () => {
        setDeciding(d);
      },
    },
    {
      key: 'withdraw',
      label: 'Withdraw',
      hidden: !canPropose || d.status !== 'PROPOSED' || !own(d),
      onClick: () => {
        setReasoning({ kind: 'withdraw', d });
      },
    },
    {
      key: 'revoke',
      label: 'Revoke',
      destructive: true,
      hidden: !canApprove || d.status !== 'APPROVED',
      onClick: () => {
        setReasoning({ kind: 'revoke', d });
      },
    },
  ];
  const period = (d: D) =>
    `${formatDate(d.effective_from)} – ${d.effective_to === null ? 'open-ended' : formatDate(d.effective_to)}`;
  const columns: DataColumn<D>[] = [
    { id: 'customer', header: 'Customer', render: (d) => customerName(d.customer_id) },
    ...valueColumns,
    { id: 'period', header: 'In effect', render: period },
    { id: 'by', header: 'Proposed by', render: (d) => <PersonName userId={d.proposed_by} /> },
    {
      id: 'status',
      header: 'Status',
      render: (d) => (
        <StatusChip
          status={d.status}
          tones={PROPOSAL_STATUS_TONES}
          label={PROPOSAL_STATUS_LABELS[d.status]}
        />
      ),
    },
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
          {canApprove && d.status === 'PROPOSED' && (
            <DecideButton
              own={own(d)}
              onClick={() => {
                setDeciding(d);
              }}
            />
          )}
          <RowActionsMenu
            label={`${noun} for ${customerName(d.customer_id)}`}
            actions={actionsFor(d).filter((a) => a.key !== 'decide')}
          />
        </Box>
      ),
    },
  ];
  const detailItems = (d: D): KeyValueItem[] => [
    { label: 'Customer', value: customerName(d.customer_id) },
    ...valueItems(d),
    { label: 'In effect', value: period(d) },
    { label: 'Reason', value: d.reason },
    { label: 'Proposed by', value: <PersonName userId={d.proposed_by} /> },
    { label: 'Proposed at', value: formatInstantIn(d.proposed_at, timeZone) },
    { label: 'Decided by', value: <PersonName userId={d.decided_by} /> },
    {
      label: 'Decided at',
      value: d.decided_at === null ? '—' : formatInstantIn(d.decided_at, timeZone),
    },
    { label: 'Decision note', value: d.decision_note ?? '—' },
    ...(d.revoked_at === null
      ? []
      : [
          { label: 'Revoked at', value: formatInstantIn(d.revoked_at, timeZone) },
          { label: 'Revoke reason', value: d.revoke_reason ?? '—' },
        ]),
  ];
  return (
    <>
      <PageHeader
        title={title}
        subtitle={subtitle}
        actions={
          canPropose && (
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setForm({ record: null });
              }}
            >
              {`Propose ${noun}`}
            </Button>
          )
        }
      />
      <Stack spacing={2}>
        <HoursOffNotice off={hours.status === 'known' && !hours.on} />
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
          onRowClick={setViewing}
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
      {viewing !== null && (
        <DetailsDrawer
          title={`${noun[0]?.toUpperCase() ?? ''}${noun.slice(1)} for ${customerName(viewing.customer_id)}`}
          status={
            <StatusChip
              status={viewing.status}
              tones={PROPOSAL_STATUS_TONES}
              label={PROPOSAL_STATUS_LABELS[viewing.status]}
            />
          }
          actions={
            <ActionButtons
              actions={actionsFor(viewing).filter((a) => a.key !== 'view')}
              primaryKey="decide"
            />
          }
          onClose={() => {
            setViewing(null);
          }}
        >
          <KeyValueGrid columns={2} items={detailItems(viewing)} />
        </DetailsDrawer>
      )}
      {form !== null &&
        renderForm({
          record: form.record,
          onClose: () => {
            setForm(null);
          },
          onSaved: (d) => {
            changed(d, form.record === null ? `${noun} proposed.` : `${noun} updated.`);
          },
        })}
      {deciding !== null && (
        <DecideDialog
          title={`Decide ${noun}`}
          summary={<KeyValueGrid columns={2} items={detailItems(deciding)} />}
          explanation={approveExplanation}
          onDecide={(body, key) => calls.decide(deciding.id, body, key)}
          onDone={(d) => {
            changed(d, `${noun} ${d.status === 'APPROVED' ? 'approved' : 'rejected'}.`);
          }}
          onClose={() => {
            setDeciding(null);
          }}
        />
      )}
      {reasoning !== null && (
        <ReasonDialog
          title={`${reasoning.kind === 'withdraw' ? 'Withdraw' : 'Revoke'} ${noun}`}
          submitLabel={reasoning.kind === 'withdraw' ? 'Withdraw' : 'Revoke'}
          onSubmit={(body, key) =>
            (reasoning.kind === 'withdraw' ? calls.withdraw : calls.revoke)(
              reasoning.d.id,
              { reason: body.reason },
              key,
            )
          }
          onDone={(d) => {
            changed(d, `${noun} ${reasoning.kind === 'withdraw' ? 'withdrawn' : 'revoked'}.`);
          }}
          onClose={() => {
            setReasoning(null);
          }}
        />
      )}
    </>
  );
}
