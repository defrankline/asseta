import { useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import type {
  PettyCashAdjustmentDto,
  PettyCashAdvanceDto,
  PettyCashHolderChangeDto,
} from '../../../../api/pettyCashTypes';
import { pettyCashService } from '../../../../api/services/pettyCashService';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { type RowAction } from '../../../../components/lifecycle/rowActions';
import { useNotify } from '../../../../notifications/useNotify';
import { useMyUserId } from '../../shared/useFinanceLabels';
import { AnswerDialog, ClearAdvanceDialog } from './PettyCashDialogs';

import { decide, OWN_FUND } from './pettyCashActions';

/** Approve or reject a proposed adjustment (never the proposer). */
export function useAdjustmentActions(holds: (fundId: string) => boolean, onChanged: () => void) {
  const notify = useNotify();
  const can = useMutationGuard();
  const me = useMyUserId();
  const canApprove = can(PERMISSIONS.tenantPettyCashApprove);
  const [open, setOpen] = useState<PettyCashAdjustmentDto | null>(null);
  const actionsFor = (a: PettyCashAdjustmentDto): RowAction[] => [
    {
      key: 'decide',
      label: 'Approve / reject',
      hidden:
        !canApprove || a.status !== 'PENDING' || (a.created_by !== null && a.created_by === me),
      disabled: holds(a.fund_id),
      disabledReason: OWN_FUND,
      onClick: () => {
        setOpen(a);
      },
    },
  ];
  const dialog =
    open === null
      ? null
      : decide(
          `Decide adjustment ${open.number}`,
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Fund', value: open.petty_cash_fund_name ?? '—' },
              {
                label: 'Amount',
                value: <MoneyText amount={open.amount} currency={open.currency} strong />,
              },
              { label: 'Reason', value: open.reason },
              { label: 'Proposed by', value: open.created_by_name ?? '—' },
            ]}
          />,
          (approve, note, key) =>
            pettyCashService.decideAdjustment(open.id, { approve, note }, key),
          (r) => {
            notify.success(
              r.status === 'APPROVED' ? `${r.number} approved.` : `${r.number} rejected.`,
            );
            onChanged();
          },
          () => {
            setOpen(null);
          },
        );
  return { actionsFor, dialog };
}

/** The new holder accepts or declines; a manager may cancel a waiting change. */
export function useHolderChangeActions(holds: (fundId: string) => boolean, onChanged: () => void) {
  const notify = useNotify();
  const can = useMutationGuard();
  const me = useMyUserId();
  const canRead = can(PERMISSIONS.tenantPettyCashRead);
  const canManage = can(PERMISSIONS.tenantPettyCashManage);
  const [open, setOpen] = useState<{
    kind: 'answer' | 'cancel';
    c: PettyCashHolderChangeDto;
  } | null>(null);
  const actionsFor = (c: PettyCashHolderChangeDto): RowAction[] => [
    {
      key: 'answer',
      label: 'Accept / decline the fund',
      // The current holder and the person who started it are not the new holder.
      hidden: !canRead || c.status !== 'PENDING' || holds(c.fund_id) || c.requested_by === me,
      onClick: () => {
        setOpen({ kind: 'answer', c });
      },
    },
    {
      key: 'cancel',
      label: 'Cancel the change',
      destructive: true,
      hidden: !canManage || c.status !== 'PENDING',
      onClick: () => {
        setOpen({ kind: 'cancel', c });
      },
    },
  ];
  let dialog: ReactNode = null;
  if (open !== null) {
    const c = open.c;
    const summary = (
      <KeyValueGrid
        columns={2}
        items={[
          { label: 'Fund', value: c.petty_cash_fund_name ?? '—' },
          { label: 'From', value: c.from_staff_name ?? '—' },
          { label: 'To', value: c.to_staff_name ?? '—' },
          { label: 'Note', value: c.note ?? '—' },
        ]}
      />
    );
    dialog =
      open.kind === 'answer' ? (
        <AnswerDialog<PettyCashHolderChangeDto>
          title={`Take over ${c.petty_cash_fund_name ?? 'the fund'}`}
          summary={summary}
          onAnswer={(accept, note, key) =>
            pettyCashService.answerHolderChange(c.id, { accept, note }, key)
          }
          onDone={(r) => {
            notify.success(
              r.status === 'ACKNOWLEDGED' ? 'You now hold the fund.' : 'Holder change declined.',
            );
            onChanged();
          }}
          onClose={() => {
            setOpen(null);
          }}
        />
      ) : (
        <AnswerDialog<PettyCashHolderChangeDto>
          title="Cancel the holder change"
          summary={summary}
          choice="cancel"
          onAnswer={(yes, note, key) =>
            yes ? pettyCashService.cancelHolderChange(c.id, note, key) : Promise.resolve(c)
          }
          onDone={(r) => {
            if (r.status === 'CANCELLED') notify.success('Holder change cancelled.');
            onChanged();
          }}
          onClose={() => {
            setOpen(null);
          }}
        />
      );
  }
  return { actionsFor, dialog };
}

/** The fund's holder takes the change back once the advance's expenses are decided. */
export function useAdvanceActions(holds: (fundId: string) => boolean, onChanged: () => void) {
  const notify = useNotify();
  const can = useMutationGuard();
  const canRead = can(PERMISSIONS.tenantPettyCashRead);
  const [open, setOpen] = useState<PettyCashAdvanceDto | null>(null);
  const actionsFor = (a: PettyCashAdvanceDto): RowAction[] => [
    {
      key: 'clear',
      label: 'Clear (change handed back)',
      hidden: !canRead || a.status !== 'OUTSTANDING' || !holds(a.fund_id),
      onClick: () => {
        setOpen(a);
      },
    },
  ];
  const dialog =
    open === null ? null : (
      <ClearAdvanceDialog
        advance={open}
        onClose={() => {
          setOpen(null);
        }}
        onDone={(r) => {
          notify.success(`Advance ${r.number} cleared.`);
          onChanged();
        }}
      />
    );
  return { actionsFor, dialog };
}
