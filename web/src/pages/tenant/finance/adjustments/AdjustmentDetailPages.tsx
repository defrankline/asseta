import { Typography } from '@mui/material';
import { useParams } from 'react-router';
import type { AdjustmentEntryDto, AdjustmentRequestDto } from '../../../../api/adjustmentTypes';
import { adjustmentService } from '../../../../api/services/adjustmentService';
import type { KeyValueItem } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { DetailSection } from '../../../../components/lifecycle/EntityDetailsLayout';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { ADJUSTMENT_ROUTES } from '../../../../navigation/adjustmentRoutes';
import { EvidenceList } from '../../engineHours/allocations/EvidenceUpload';
import { hoursText } from '../../hours/hoursDisplay';
import { machineText } from '../../shared/names';
import { PersonName } from '../../shared/PersonName';
import { RecordDetail } from '../../shared/RecordDetail';
import { useRecordById } from '../../shared/useRecordById';
import {
  ADJUSTMENT_TYPE_LABELS,
  ENTRY_STATUS_LABELS,
  ENTRY_STATUS_TONES,
  REQUEST_STATUS_LABELS,
  REQUEST_STATUS_TONES,
  REQUEST_TYPE_LABELS,
  SETTLEMENT_LABELS,
  unitValue,
} from './adjustmentDisplay';
import { RecordLink, RequestEffects } from './adjustmentRecord';
import { useAdjustmentRequestActions } from './useAdjustmentRequestActions';

const loadEntry = (id: string, signal: AbortSignal) => adjustmentService.getEntry(id, signal);
const loadRequest = (id: string, signal: AbortSignal) => adjustmentService.getRequest(id, signal);

function entryItems(e: AdjustmentEntryDto): KeyValueItem[] {
  const value = (v: string | null) => unitValue(v, e.unit, e.currency);
  return [
    { label: 'Type', value: ADJUSTMENT_TYPE_LABELS[e.adjustment_type] },
    {
      label: 'Original record',
      value: <RecordLink type={e.original_type} id={e.original_id} label={e.original_reference} />,
    },
    {
      label: 'Decision record',
      value: <RecordLink type={e.source_type} id={e.source_id} label="Open the decision" />,
    },
    { label: 'Original value', value: value(e.original_value) },
    { label: 'New value', value: value(e.new_value) },
    { label: 'Amount', value: value(e.amount) },
    { label: 'Resulting balance', value: value(e.resulting_balance) },
    { label: 'Customer', value: e.customer_name ?? '—' },
    {
      label: 'Machine',
      value:
        e.machine_id === null ? '—' : machineText(e.machine_code, e.machine_name, e.machine_id),
    },
    { label: 'Custodian', value: e.staff_member_name ?? '—' },
    { label: 'Reason from the list', value: e.reason_label ?? '—' },
    { label: 'Reason', value: e.reason ?? '—' },
  ];
}

/** One decided adjustment: what changed, why, who asked, who decided, with its evidence. */
export function AdjustmentEntryDetailPage() {
  const { entryId } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(loadEntry, entryId);
  return (
    <RecordDetail<AdjustmentEntryDto>
      resource={res}
      what="adjustment"
      back={{ label: 'Adjustments ledger', to: ADJUSTMENT_ROUTES.ledger }}
      timeZone={timeZone}
      title={(e) => ADJUSTMENT_TYPE_LABELS[e.adjustment_type]}
      subtitle={(e) => e.original_reference ?? 'Adjustments ledger entry'}
      status={(e) => (
        <StatusChip
          status={e.status}
          tones={ENTRY_STATUS_TONES}
          label={ENTRY_STATUS_LABELS[e.status]}
        />
      )}
      items={entryItems}
      history={(e) => [
        {
          key: 'req',
          at: e.requested_at,
          label: 'Requested',
          by: <PersonName userId={e.requested_by} name={e.requested_by_name} />,
          note: e.reason,
        },
        {
          key: 'dec',
          at: e.approved_at,
          label: ENTRY_STATUS_LABELS[e.status],
          by: <PersonName userId={e.approved_by} name={e.approved_by_name} />,
          note: e.decision_note,
        },
        { key: 'post', at: e.posted_at, label: 'Posted to the ledger' },
      ]}
    >
      {(e) => (
        <DetailSection title="Evidence">
          <EvidenceList ids={e.evidence_attachment_ids} />
        </DetailSection>
      )}
    </RecordDetail>
  );
}

function requestItems(r: AdjustmentRequestDto): KeyValueItem[] {
  return [
    { label: 'Type', value: REQUEST_TYPE_LABELS[r.request_type] },
    {
      label: 'Original record',
      value: <RecordLink type={r.original_type} id={r.original_id} label={r.original_reference} />,
    },
    { label: 'Customer', value: r.customer_name ?? '—' },
    {
      label: 'Machine',
      value:
        r.machine_id === null ? '—' : machineText(r.machine_code, r.machine_name, r.machine_id),
    },
    { label: 'Hours', value: r.hours === null ? '—' : hoursText(r.hours) },
    {
      label: 'Amount',
      value:
        r.amount === null || r.currency === null ? (
          '—'
        ) : (
          <MoneyText amount={r.amount} currency={r.currency} strong />
        ),
    },
    { label: 'Settlement', value: r.settlement === null ? '—' : SETTLEMENT_LABELS[r.settlement] },
    { label: 'Reason from the list', value: r.reason_label ?? '—' },
    { label: 'Reason', value: r.reason },
  ];
}

/** One request: what it would do (or did), its evidence, decide and withdraw. */
export function AdjustmentRequestDetailPage() {
  const { requestId } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(loadRequest, requestId);
  const { actionsFor, dialogs } = useAdjustmentRequestActions(res.reload);
  return (
    <>
      <RecordDetail<AdjustmentRequestDto>
        resource={res}
        what="adjustment request"
        back={{ label: 'Adjustment requests', to: ADJUSTMENT_ROUTES.requests }}
        timeZone={timeZone}
        title={(r) => REQUEST_TYPE_LABELS[r.request_type]}
        subtitle={(r) => r.original_reference ?? 'Adjustment request'}
        status={(r) => (
          <StatusChip
            status={r.status}
            tones={REQUEST_STATUS_TONES}
            label={REQUEST_STATUS_LABELS[r.status]}
          />
        )}
        actions={actionsFor}
        primaryKey="decide"
        items={requestItems}
        history={(r) => [
          {
            key: 'prop',
            at: r.proposed_at,
            label: 'Proposed',
            by: <PersonName userId={r.proposed_by} name={r.proposed_by_name} />,
            note: r.reason,
          },
          {
            key: 'dec',
            at: r.decided_at,
            label: REQUEST_STATUS_LABELS[r.status],
            by: <PersonName userId={r.decided_by} name={r.decided_by_name} />,
            note: r.decision_note,
          },
        ]}
      >
        {(r) => (
          <>
            <DetailSection title={r.status === 'PROPOSED' ? 'If approved (forecast)' : 'Outcome'}>
              {r.status === 'PROPOSED' || r.status === 'APPROVED' ? (
                <RequestEffects request={r} />
              ) : (
                <Typography variant="body2" color="text.secondary">
                  Not applied: nothing changed on the original record.
                </Typography>
              )}
            </DetailSection>
            <DetailSection title="Evidence">
              <EvidenceList ids={r.evidence_attachment_ids} />
            </DetailSection>
          </>
        )}
      </RecordDetail>
      {dialogs}
    </>
  );
}
