import { Link, Typography } from '@mui/material';
import { useCallback } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import type {
  PettyCashAdjustmentDto,
  PettyCashAdvanceDto,
  PettyCashCountDto,
  PettyCashHolderChangeDto,
  PettyCashMovementDto,
} from '../../../../api/pettyCashTypes';
import { pettyCashService } from '../../../../api/services/pettyCashService';
import type { DataColumn } from '../../../../components/data/ServerDataTable';
import { StaticTable } from '../../../../components/data/StaticTable';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { DetailSection } from '../../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import {
  PETTY_CASH_ROUTES,
  pettyCashFundPath,
  pettyCashPath,
  type PettyCashRecord,
} from '../../../../navigation/pettyCashRoutes';
import { recordPath } from '../../../../navigation/recordRoutes';
import { useSession } from '../../../../session/useSession';
import { formatInstantIn } from '../../../../utils/time';
import { EvidenceList } from '../../engineHours/allocations/EvidenceUpload';
import { PersonName } from '../../shared/PersonName';
import { RecordDetail } from '../../shared/RecordDetail';
import { useRecordById } from '../../shared/useRecordById';
import { useMovementActions } from './pettyCashActions';
import { useAdjustmentActions, useAdvanceActions, useHolderChangeActions } from './recordActions';
import {
  ADVANCE_LABELS,
  ADVANCE_TONES,
  COUNT_REASON_LABELS,
  DECISION_LABELS,
  DECISION_TONES,
  HOLDER_CHANGE_LABELS,
  HOLDER_CHANGE_TONES,
  MOVEMENT_KIND_LABELS,
  MOVEMENT_STATUS_LABELS,
  MOVEMENT_STATUS_TONES,
} from './pettyCashDisplay';
import { useMyFunds } from './pettyCashState';
import type { PettyCashTab } from '../../../../navigation/pettyCashRoutes';
import { pettyCashTabPath } from '../../../../navigation/pettyCashRoutes';
import type { TopUpExpenseDto } from '../../../../api/pettyCashTypes';

const load = {
  movement: (id: string, s: AbortSignal) => pettyCashService.movement(id, s),
  count: (id: string, s: AbortSignal) => pettyCashService.count(id, s),
  holderChange: (id: string, s: AbortSignal) => pettyCashService.holderChange(id, s),
  adjustment: (id: string, s: AbortSignal) => pettyCashService.adjustment(id, s),
  advance: (id: string, s: AbortSignal) => pettyCashService.advance(id, s),
};

const LIST: Readonly<Record<Exclude<PettyCashRecord, 'funds'>, [PettyCashTab, string]>> = {
  movements: ['fundings', 'Fundings & top-ups'],
  counts: ['counts', 'Counts'],
  'holder-changes': ['holder-changes', 'Holder changes'],
  adjustments: ['adjustments', 'Adjustments'],
  advances: ['advances', 'Advances'],
};

/** Office users go back to the petty cash list; holders to their own petty cash page. */
function useBack(kind: Exclude<PettyCashRecord, 'funds'>) {
  const { hasPermission } = useSession();
  const office = hasPermission(
    [
      PERMISSIONS.tenantPettyCashManage,
      PERMISSIONS.tenantPettyCashPropose,
      PERMISSIONS.tenantPettyCashApprove,
    ],
    'any',
  );
  const [tab, label] = LIST[kind];
  return office
    ? { label, to: pettyCashTabPath(tab) }
    : { label: 'My petty cash', to: PETTY_CASH_ROUTES.field };
}

const fundLink = (fundId: string, name: string | null | undefined) => (
  <Link component={RouterLink} to={pettyCashFundPath(fundId)}>
    {name ?? 'Open the fund'}
  </Link>
);

const varianceLink = (varianceId: string | null | undefined) =>
  varianceId == null ? (
    '—'
  ) : (
    <Link component={RouterLink} to={recordPath('CASH_VARIANCE', varianceId)}>
      Open the variance
    </Link>
  );

const money = (amount: string | null, currency: string) =>
  amount == null ? '—' : <MoneyText amount={amount} currency={currency} />;

/** The approved spending a top-up proposal was based on (what the approver checks). */
function TopUpBasis({
  movement: m,
  timeZone,
}: {
  movement: PettyCashMovementDto;
  timeZone: string;
}) {
  const fetcher = useCallback(
    (s: AbortSignal) => pettyCashService.movementExpenses(m.id, s),
    [m.id],
  );
  const res = useAsyncResource(fetcher, [m.id]);
  const columns: DataColumn<TopUpExpenseDto>[] = [
    { id: 'at', header: 'Incurred', render: (e) => formatInstantIn(e.incurred_at, timeZone) },
    {
      id: 'desc',
      header: 'Description',
      render: (e) => (
        <Link component={RouterLink} to={`/tenant/expenses/${encodeURIComponent(e.id)}`}>
          {e.description}
        </Link>
      ),
    },
    { id: 'amount', header: 'Amount', align: 'right', render: (e) => money(e.amount, m.currency) },
  ];
  return (
    <AsyncContent
      resource={res}
      loadingLabel="Loading spending"
      errorTitle="Could not load the spending"
    >
      {(rows) =>
        rows.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No approved spending behind this request.
          </Typography>
        ) : (
          <StaticTable
            columns={columns}
            rows={rows}
            getRowId={(e) => e.id}
            ariaLabel="Spending behind the top-up"
          />
        )
      }
    </AsyncContent>
  );
}

/** /tenant/finance/petty-cash/movements/:id — a funding, top-up or return. */
export function PettyCashMovementDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(load.movement, id);
  const mine = useMyFunds();
  const { actionsFor, dialog } = useMovementActions(mine.holds, res.reload);
  return (
    <>
      <RecordDetail<PettyCashMovementDto>
        resource={res}
        what="petty cash record"
        back={useBack('movements')}
        timeZone={timeZone}
        title={(m) => `${m.number} · ${MOVEMENT_KIND_LABELS[m.kind]}`}
        status={(m) => (
          <StatusChip
            status={m.status}
            tones={MOVEMENT_STATUS_TONES}
            label={MOVEMENT_STATUS_LABELS[m.status]}
          />
        )}
        actions={actionsFor}
        primaryKey="decide"
        items={(m) => [
          { label: 'Fund', value: fundLink(m.fund_id, m.petty_cash_fund_name) },
          { label: 'Holder', value: m.holder_staff_name ?? '—' },
          { label: 'Amount', value: money(m.amount, m.currency) },
          {
            label: m.kind === 'RETURN' ? 'Counted by the office' : 'Received by the holder',
            value: money(m.amount_received, m.currency),
          },
          ...(m.kind === 'TOP_UP'
            ? [{ label: 'Suggested', value: money(m.suggested_amount, m.currency) }]
            : []),
          { label: 'Most that brings it to its limit', value: money(m.cap_amount, m.currency) },
          { label: 'Above the limit because', value: m.above_cap_reason ?? '—' },
          { label: 'Company account', value: m.deposit_account_name ?? '—' },
          { label: 'Reference', value: m.reference ?? '—' },
          { label: 'Note', value: m.note ?? '—' },
          { label: 'Variance', value: varianceLink(m.variance_id) },
          { label: 'Recorded on', value: m.source === 'API' ? 'Web' : m.source },
        ]}
        history={(m) => [
          {
            key: 'created',
            at: m.created_at,
            label: m.kind === 'RETURN' ? 'Return recorded' : 'Proposed',
            by: <PersonName userId={m.created_by} name={m.created_by_name} />,
            note: m.note,
          },
          {
            key: 'decided',
            at: m.decided_at,
            label: m.status === 'REJECTED' ? 'Rejected' : 'Approved',
            by: <PersonName userId={m.decided_by} name={m.decided_by_name} />,
            note: m.decision_note,
          },
          {
            key: 'issued',
            at: m.issued_at,
            label: 'Handed over',
            by: <PersonName userId={m.issued_by} name={m.issued_by_name} />,
          },
          {
            key: 'received',
            at: m.received_at,
            label:
              m.kind === 'RETURN'
                ? 'Confirmed by the office'
                : m.status === 'DISPUTED'
                  ? 'Disputed by the holder'
                  : 'Received by the holder',
            by: <PersonName userId={m.received_by} name={m.received_by_name} />,
            note: m.receipt_note,
          },
        ]}
      >
        {(m) => (
          <>
            {m.kind === 'TOP_UP' && (
              <DetailSection title="Spending behind this top-up">
                <TopUpBasis movement={m} timeZone={timeZone} />
              </DetailSection>
            )}
            <DetailSection title="Evidence">
              <EvidenceList ids={m.evidence_attachment_ids} />
            </DetailSection>
          </>
        )}
      </RecordDetail>
      {dialog}
    </>
  );
}

/** /tenant/finance/petty-cash/counts/:id */
export function PettyCashCountDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(load.count, id);
  return (
    <RecordDetail<PettyCashCountDto>
      resource={res}
      what="petty cash count"
      back={useBack('counts')}
      timeZone={timeZone}
      title={(c) => `${c.number} · ${c.petty_cash_fund_name ?? 'Count'}`}
      status={(c) =>
        c.self_count ? (
          <StatusChip status="SELF" tones={{ SELF: 'info' }} label="Self-count" />
        ) : null
      }
      items={(c) => [
        { label: 'Fund', value: fundLink(c.fund_id, c.petty_cash_fund_name) },
        { label: 'Why', value: COUNT_REASON_LABELS[c.reason] },
        { label: 'Holder', value: c.holder_staff_name ?? '—' },
        { label: 'Cash expected', value: money(c.expected_amount, c.currency) },
        { label: 'Cash counted', value: money(c.counted_amount, c.currency) },
        {
          label: 'Difference',
          value: <MoneyText amount={c.difference} currency={c.currency} strong />,
        },
        {
          label: 'Witness',
          value: c.witness_user_name ?? (c.witness_user_id == null ? 'None' : '—'),
        },
        { label: 'Variance', value: varianceLink(c.variance_id) },
        { label: 'Note', value: c.note ?? '—' },
        { label: 'Policy version', value: c.policy_version ?? '—' },
      ]}
      history={(c) => [
        {
          key: 'counted',
          at: c.counted_at,
          label: 'Counted',
          by: <PersonName userId={c.counted_by} name={c.counted_by_name} />,
          note: c.note,
        },
      ]}
    >
      {(c) => (
        <DetailSection title="Evidence">
          <EvidenceList ids={c.evidence_attachment_ids} />
        </DetailSection>
      )}
    </RecordDetail>
  );
}

/** /tenant/finance/petty-cash/holder-changes/:id */
export function PettyCashHolderChangeDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(load.holderChange, id);
  const mine = useMyFunds();
  const { actionsFor, dialog } = useHolderChangeActions(mine.holds, res.reload);
  return (
    <>
      <RecordDetail<PettyCashHolderChangeDto>
        resource={res}
        what="holder change"
        back={useBack('holder-changes')}
        timeZone={timeZone}
        title={(c) => `Holder change · ${c.petty_cash_fund_name ?? 'fund'}`}
        status={(c) => (
          <StatusChip
            status={c.status}
            tones={HOLDER_CHANGE_TONES}
            label={HOLDER_CHANGE_LABELS[c.status]}
          />
        )}
        actions={actionsFor}
        primaryKey="answer"
        items={(c) => [
          { label: 'Fund', value: fundLink(c.fund_id, c.petty_cash_fund_name) },
          { label: 'From', value: c.from_staff_name ?? '—' },
          { label: 'To', value: c.to_staff_name ?? '—' },
          {
            label: 'Count at the change',
            value: (
              <Link component={RouterLink} to={pettyCashPath('counts', c.count_id)}>
                Open the count
              </Link>
            ),
          },
          { label: 'Note', value: c.note ?? '—' },
        ]}
        history={(c) => [
          {
            key: 'started',
            at: c.requested_at,
            label: 'Started',
            by: <PersonName userId={c.requested_by} name={c.requested_by_name} />,
            note: c.note,
          },
          {
            key: 'decided',
            at: c.decided_at,
            label: HOLDER_CHANGE_LABELS[c.status],
            by: <PersonName userId={c.decided_by} name={c.decided_by_name} />,
            note: c.decision_note,
          },
        ]}
      />
      {dialog}
    </>
  );
}

/** /tenant/finance/petty-cash/adjustments/:id */
export function PettyCashAdjustmentDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(load.adjustment, id);
  const mine = useMyFunds();
  const { actionsFor, dialog } = useAdjustmentActions(mine.holds, res.reload);
  return (
    <>
      <RecordDetail<PettyCashAdjustmentDto>
        resource={res}
        what="fund adjustment"
        back={useBack('adjustments')}
        timeZone={timeZone}
        title={(a) => `${a.number} · Adjustment`}
        status={(a) => (
          <StatusChip status={a.status} tones={DECISION_TONES} label={DECISION_LABELS[a.status]} />
        )}
        actions={actionsFor}
        primaryKey="decide"
        items={(a) => [
          { label: 'Fund', value: fundLink(a.fund_id, a.petty_cash_fund_name) },
          {
            label: 'Amount (signed)',
            value: <MoneyText amount={a.amount} currency={a.currency} strong />,
          },
          { label: 'Reason', value: a.reason },
        ]}
        history={(a) => [
          {
            key: 'proposed',
            at: a.created_at,
            label: 'Proposed',
            by: <PersonName userId={a.created_by} name={a.created_by_name} />,
            note: a.reason,
          },
          {
            key: 'decided',
            at: a.decided_at,
            label: DECISION_LABELS[a.status],
            by: <PersonName userId={a.decided_by} name={a.decided_by_name} />,
            note: a.decision_note,
          },
        ]}
      >
        {(a) => (
          <DetailSection title="Evidence">
            <EvidenceList ids={a.evidence_attachment_ids} />
          </DetailSection>
        )}
      </RecordDetail>
      {dialog}
    </>
  );
}

/** /tenant/finance/petty-cash/advances/:id */
export function PettyCashAdvanceDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(load.advance, id);
  const mine = useMyFunds();
  const { actionsFor, dialog } = useAdvanceActions(mine.holds, res.reload);
  return (
    <>
      <RecordDetail<PettyCashAdvanceDto>
        resource={res}
        what="advance"
        back={useBack('advances')}
        timeZone={timeZone}
        title={(a) => `${a.number} · Advance to ${a.recipient_staff_name ?? '—'}`}
        status={(a) => (
          <StatusChip status={a.status} tones={ADVANCE_TONES} label={ADVANCE_LABELS[a.status]} />
        )}
        actions={actionsFor}
        primaryKey="clear"
        items={(a) => [
          { label: 'Fund', value: fundLink(a.fund_id, a.petty_cash_fund_name) },
          { label: 'Paid to', value: a.recipient_staff_name ?? '—' },
          { label: 'Amount', value: money(a.amount, a.currency) },
          { label: 'For', value: a.purpose },
          {
            label: 'Clear by',
            value: `${formatInstantIn(a.due_at, timeZone)}${a.overdue ? ' (past due)' : ''}`,
          },
          { label: 'Approved spending', value: money(a.approved_spending, a.currency) },
          { label: 'Spending waiting for approval', value: money(a.pending_spending, a.currency) },
          { label: 'Change expected', value: money(a.remaining, a.currency) },
          { label: 'Change handed back', value: money(a.change_returned, a.currency) },
          { label: 'Variance', value: varianceLink(a.variance_id) },
        ]}
        history={(a) => [
          {
            key: 'issued',
            at: a.issued_at,
            label: 'Paid',
            by: <PersonName userId={a.issued_by} name={a.issued_by_name} />,
            note: a.purpose,
          },
          {
            key: 'cleared',
            at: a.cleared_at,
            label: 'Cleared',
            by: <PersonName userId={a.cleared_by} name={a.cleared_by_name} />,
            note: a.clear_note,
          },
        ]}
      />
      {dialog}
    </>
  );
}
