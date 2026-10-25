import { useState, type ReactNode } from 'react';
import { useCanMutate } from '../../../access/useCanMutate';
import type { DecisionIn, ProposalStatus, ReasonIn } from '../../../api/hoursTypes';
import type { TenantListQuery } from '../../../api/services/tenantRequest';
import type { Page } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { KeyValueGrid, type KeyValueItem } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import type { RecordKind } from '../../../navigation/recordRoutes';
import { useNotify } from '../../../notifications/useNotify';
import { formatDate } from '../../../utils/dates';
import { formatInstantIn } from '../../../utils/time';
import { nameOr } from '../shared/names';
import { PersonName } from '../shared/PersonName';
import type { HistoryEvent } from '../shared/RecordDetail';
import { useMyUserId } from '../shared/useFinanceLabels';
import { DecideDialog, ReasonDialog } from './HoursDialogs';
import { OWN_REQUEST_TEXT, PROPOSAL_STATUS_LABELS, PROPOSAL_STATUS_TONES } from './hoursDisplay';
import { useHoursPolicy } from './useHoursPolicy';

/** Fields every customer proposal (discount, credit arrangement) carries. */
export interface ProposalRow {
  id: string;
  customer_id: string;
  customer_name?: string | null;
  status: ProposalStatus;
  proposed_by: string | null;
  proposed_by_name?: string | null;
  proposed_at: string;
  decided_by: string | null;
  decided_by_name?: string | null;
  decided_at: string | null;
  decision_note: string | null;
  effective_from: string;
  effective_to: string | null;
  reason: string;
  revoke_reason: string | null;
  revoked_at: string | null;
  revoked_by?: string | null;
  revoked_by_name?: string | null;
  version: number;
}

export interface ProposalCalls<D> {
  list: (query: TenantListQuery, signal?: AbortSignal) => Promise<Page<D>>;
  get: (id: string, signal?: AbortSignal) => Promise<D>;
  decide: (id: string, body: DecisionIn, key: string) => Promise<D>;
  withdraw: (id: string, body: ReasonIn, key: string) => Promise<D>;
  revoke: (id: string, body: ReasonIn, key: string) => Promise<D>;
}

/** What a kind of customer proposal needs (shared by its list and detail pages). */
export interface ProposalConfig<D extends ProposalRow> {
  kind: RecordKind;
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
  /** The proposal's own value in the details / decide summary. */
  valueItems: (d: D) => KeyValueItem[];
  approveExplanation: string;
  /** Propose (no record) or edit (record) dialog; mount only while open. */
  renderForm: (props: {
    record: D | null;
    onClose: () => void;
    onSaved: (d: D) => void;
  }) => ReactNode;
}

export const proposalStatusChip = (s: ProposalStatus) => (
  <StatusChip status={s} tones={PROPOSAL_STATUS_TONES} label={PROPOSAL_STATUS_LABELS[s]} />
);

export const capitalised = (noun: string) => `${noun[0]?.toUpperCase() ?? ''}${noun.slice(1)}`;

/**
 * Commands, dialogs and detail view of one kind of customer proposal: edit or withdraw your own,
 * decide others' (approve permission; disabled on your own), revoke approved ones.
 */
export function useProposalKit<D extends ProposalRow>(
  config: ProposalConfig<D>,
  onChanged: (d: D) => void,
) {
  const { noun, calls } = config;
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const me = useMyUserId();
  const hours = useHoursPolicy();
  const on = hours.on && (hours.policy === null || config.allowed(hours.policy));
  const canPropose = useCanMutate(config.proposePermission) && on;
  const canApprove = useCanMutate(config.approvePermission);
  const [form, setForm] = useState<{ record: D | null } | null>(null);
  const [deciding, setDeciding] = useState<D | null>(null);
  const [reasoning, setReasoning] = useState<{ kind: 'withdraw' | 'revoke'; d: D } | null>(null);
  const changed = (d: D, message: string) => {
    notify.success(message);
    onChanged(d);
  };
  const own = (d: D) => me !== null && d.proposed_by === me;
  const actionsFor = (d: D): RowAction[] => [
    {
      key: 'edit',
      label: 'Edit',
      hidden: !canPropose || d.status !== 'PROPOSED' || !own(d),
      onClick: () => {
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
  const customer = (d: D) => nameOr(d.customer_name, d.customer_id);
  const items = (d: D): KeyValueItem[] => [
    { label: 'Customer', value: customer(d) },
    ...config.valueItems(d),
    { label: 'In effect', value: period(d) },
    { label: 'Reason', value: d.reason },
    {
      label: 'Proposed by',
      value: <PersonName userId={d.proposed_by} name={d.proposed_by_name} />,
    },
    { label: 'Proposed at', value: formatInstantIn(d.proposed_at, timeZone) },
    {
      label: d.status === 'WITHDRAWN' ? 'Withdrawn by' : 'Decided by',
      value: <PersonName userId={d.decided_by} name={d.decided_by_name} />,
    },
    {
      label: d.status === 'WITHDRAWN' ? 'Withdrawn at' : 'Decided at',
      value: d.decided_at === null ? '—' : formatInstantIn(d.decided_at, timeZone),
    },
    { label: 'Decision note', value: d.decision_note ?? '—' },
    ...(d.revoked_at === null
      ? []
      : [
          {
            label: 'Revoked by',
            value: <PersonName userId={d.revoked_by ?? null} name={d.revoked_by_name} />,
          },
          { label: 'Revoked at', value: formatInstantIn(d.revoked_at, timeZone) },
          { label: 'Revoke reason', value: d.revoke_reason ?? '—' },
        ]),
  ];
  const history = (d: D): HistoryEvent[] => [
    {
      key: 'proposed',
      at: d.proposed_at,
      label: 'Proposed',
      by: <PersonName userId={d.proposed_by} name={d.proposed_by_name} />,
      note: d.reason,
    },
    {
      key: 'decided',
      at: d.status === 'PROPOSED' ? null : d.decided_at,
      label:
        d.status === 'WITHDRAWN' ? 'Withdrawn' : d.status === 'REJECTED' ? 'Rejected' : 'Approved',
      by: <PersonName userId={d.decided_by} name={d.decided_by_name} />,
      note: d.decision_note,
    },
    {
      key: 'revoked',
      at: d.revoked_at,
      label: 'Revoked',
      by: <PersonName userId={d.revoked_by ?? null} name={d.revoked_by_name} />,
      note: d.revoke_reason,
    },
  ];
  const dialogs = (
    <>
      {form !== null &&
        config.renderForm({
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
          summary={<KeyValueGrid columns={2} items={items(deciding)} />}
          explanation={config.approveExplanation}
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
  return {
    hours,
    canPropose,
    canApprove,
    own,
    period,
    customer,
    actionsFor,
    items,
    history,
    dialogs,
    propose: () => {
      setForm({ record: null });
    },
    decide: (d: D) => {
      setDeciding(d);
    },
  };
}
