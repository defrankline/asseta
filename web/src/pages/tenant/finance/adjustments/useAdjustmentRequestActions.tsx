import { Typography } from '@mui/material';
import { useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useCanMutate } from '../../../../access/useCanMutate';
import type { AdjustmentRequestDto } from '../../../../api/adjustmentTypes';
import { adjustmentService } from '../../../../api/services/adjustmentService';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { useNotify } from '../../../../notifications/useNotify';
import { DecideDialog, ReasonDialog } from '../../hours/HoursDialogs';
import { OWN_REQUEST_TEXT } from '../../hours/hoursDisplay';
import { useMyUserId } from '../../shared/useFinanceLabels';
import { ADJUSTMENT_ERROR_HINTS, REQUEST_TYPE_LABELS } from './adjustmentDisplay';
import { RequestEffects } from './adjustmentRecord';

type Open = { kind: 'decide' | 'withdraw'; request: AdjustmentRequestDto } | null;

const titleOf = (r: AdjustmentRequestDto) =>
  `${REQUEST_TYPE_LABELS[r.request_type]}${r.original_reference === null ? '' : ` · ${r.original_reference}`}`;

/** Decide and withdraw on an adjustment request; the proposer can never decide their own. */
export function useAdjustmentRequestActions(onChanged: () => void) {
  const notify = useNotify();
  const me = useMyUserId();
  const canDecide = useCanMutate(PERMISSIONS.tenantAdjustmentDecide);
  const canPropose = useCanMutate(PERMISSIONS.tenantAdjustmentPropose);
  const [open, setOpen] = useState<Open>(null);
  const close = () => {
    setOpen(null);
  };
  const isMine = (r: AdjustmentRequestDto) => r.proposed_by !== null && r.proposed_by === me;
  const decide = (request: AdjustmentRequestDto) => {
    setOpen({ kind: 'decide', request });
  };
  const actionsFor = (r: AdjustmentRequestDto): RowAction[] => [
    {
      key: 'decide',
      label: 'Decide',
      hidden: !canDecide || r.status !== 'PROPOSED',
      disabled: isMine(r),
      ...(isMine(r) ? { disabledReason: OWN_REQUEST_TEXT } : {}),
      onClick: () => {
        decide(r);
      },
    },
    {
      key: 'withdraw',
      label: 'Withdraw',
      hidden: !canPropose || !isMine(r) || r.status !== 'PROPOSED',
      onClick: () => {
        setOpen({ kind: 'withdraw', request: r });
      },
    },
  ];
  let dialogs: ReactNode = null;
  if (open?.kind === 'decide') {
    const r = open.request;
    dialogs = (
      <DecideDialog<AdjustmentRequestDto>
        title={`Decide: ${titleOf(r)}`}
        summary={<RequestEffects request={r} />}
        explanation="Approving posts offsetting records; the original is never edited. All checks run again now."
        errorHints={ADJUSTMENT_ERROR_HINTS}
        onDecide={(body, key) =>
          adjustmentService.decide(
            r.id,
            { decision: body.approve ? 'APPROVE' : 'REJECT', note: body.note },
            key,
          )
        }
        onDone={(result) => {
          notify.success(result.status === 'APPROVED' ? 'Approved.' : 'Rejected.');
          onChanged();
        }}
        onClose={close}
      />
    );
  } else if (open?.kind === 'withdraw') {
    const r = open.request;
    dialogs = (
      <ReasonDialog<AdjustmentRequestDto>
        title={`Withdraw: ${titleOf(r)}`}
        submitLabel="Withdraw"
        summary={<Typography variant="body2">Nothing changes on the original record.</Typography>}
        errorHints={ADJUSTMENT_ERROR_HINTS}
        onSubmit={(body, key) => adjustmentService.withdraw(r.id, { reason: body.reason }, key)}
        onDone={() => {
          notify.success('Request withdrawn.');
          onChanged();
        }}
        onClose={close}
      />
    );
  }
  return { actionsFor, dialogs, isMine, canDecide, decide };
}
