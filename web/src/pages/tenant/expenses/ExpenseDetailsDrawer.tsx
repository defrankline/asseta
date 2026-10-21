import { Alert, Box, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import { expenseService } from '../../../api/services/expenseService';
import type { ExpenseDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import { AttachmentPhoto } from '../../../components/meter/AttachmentPhoto';
import { jobDetailPath, ROUTES } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import {
  actorLabel,
  EXPENSE_STATUS_OPTIONS,
  EXPENSE_STATUS_TONES,
  PAID_FROM_LABELS,
  shortId,
} from '../shared/financeDisplay';
import { labelOf } from '../shared/display';
import { useExpenseCategoryLabels, useMyUserId, useStaffLabels } from '../shared/useFinanceLabels';
import { useMachineLabels } from '../shared/useMachineLabels';

interface ExpenseDetailsDrawerProps {
  expense: ExpenseDto;
  timeZone: string;
  onClose: () => void;
}

/** Expense evidence: receipts (signed URLs on demand), GPS, policy version and approval state. */
export function ExpenseDetailsDrawer({ expense: e, timeZone, onClose }: ExpenseDetailsDrawerProps) {
  const me = useMyUserId();
  const categoryLabel = useExpenseCategoryLabels();
  const staffLabel = useStaffLabels();
  const machineLabel = useMachineLabels();
  const fetchUrl = (attachmentId: string) => expenseService.receiptUrl(e.id, attachmentId);
  return (
    <DetailsDrawer
      title={e.description}
      status={
        <StatusChip
          status={e.status}
          tones={EXPENSE_STATUS_TONES}
          label={labelOf(EXPENSE_STATUS_OPTIONS, e.status)}
        />
      }
      onClose={onClose}
    >
      {e.status === 'PENDING_APPROVAL' && (
        <Alert severity="warning">
          Above the policy’s auto-approval limit: waiting for approval by someone other than the
          submitter. It does not count as approved spending until then.{' '}
          <RouterLink to={ROUTES.tenantApprovals}>Open approvals</RouterLink>
        </Alert>
      )}
      {e.status === 'REJECTED' && (
        <Alert severity="error">
          Rejected{e.decision_note === null ? '' : `: ${e.decision_note}`}. It never counts as
          spending.
        </Alert>
      )}
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Amount', value: <MoneyText amount={e.amount} currency={e.currency} strong /> },
          { label: 'Category', value: categoryLabel(e.category_id) },
          { label: 'Supplier', value: e.supplier ?? '—' },
          { label: 'Incurred at', value: formatInstantIn(e.incurred_at, timeZone) },
          { label: 'Paid from', value: PAID_FROM_LABELS[e.paid_from] },
          { label: 'Custodian', value: staffLabel(e.custodian_staff_id) },
          {
            label: 'Machine',
            value: e.machine_id === null ? 'Unattributed' : machineLabel(e.machine_id),
          },
          {
            label: 'Job',
            value:
              e.job_id === null ? (
                '—'
              ) : (
                <RouterLink to={jobDetailPath(e.job_id)}>{shortId(e.job_id)}</RouterLink>
              ),
          },
          { label: 'Policy version', value: e.policy_version },
          { label: 'Receipt required', value: e.receipt_required ? 'Yes' : 'No' },
          { label: 'Source', value: e.source },
          { label: 'Submitted by', value: actorLabel(e.submitted_by, me) },
          { label: 'Submitted at', value: formatInstantIn(e.submitted_at, timeZone) },
          {
            label: 'Decided',
            value:
              e.decided_at === null
                ? '—'
                : `${formatInstantIn(e.decided_at, timeZone)} by ${e.decided_by === null ? 'policy (auto)' : actorLabel(e.decided_by, me)}`,
          },
          { label: 'Decision note', value: e.decision_note ?? '—' },
        ]}
      />
      <Typography variant="subtitle2">GPS at capture</Typography>
      <Typography variant="body2">
        {e.gps_status === null
          ? 'Not attempted'
          : e.gps_status === 'FIX'
            ? `${String(e.latitude)}, ${String(e.longitude)} ±${String(Math.round(e.gps_accuracy_m ?? 0))} m`
            : `No fix (${e.gps_status})`}
      </Typography>
      <Typography variant="subtitle2">Receipts</Typography>
      {e.receipt_attachment_ids.length === 0 ? (
        <Typography variant="body2">No receipts attached.</Typography>
      ) : (
        <Box className="flex flex-wrap gap-3">
          {e.receipt_attachment_ids.map((id, i) => (
            <AttachmentPhoto
              key={id}
              attachmentId={id}
              fetchUrl={fetchUrl}
              label={`View receipt ${String(i + 1)}`}
            />
          ))}
        </Box>
      )}
      <Typography variant="caption" color="text.secondary">
        Expenses are never edited after submission; corrections go through approval / rejection.
      </Typography>
    </DetailsDrawer>
  );
}
