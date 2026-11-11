import { useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import type { PettyCashFundDto, PettyCashMovementDto } from '../../../../api/pettyCashTypes';
import { pettyCashService } from '../../../../api/services/pettyCashService';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { standardRowActions, type RowAction } from '../../../../components/lifecycle/rowActions';
import { useLifecycleDialog } from '../../../../components/lifecycle/useLifecycleDialog';
import { useNotify } from '../../../../notifications/useNotify';
import { withErrorCode } from '../../shared/errorHints';
import { DecisionDialog } from '../../shared/DecisionDialog';
import { useMyUserId } from '../../shared/useFinanceLabels';
import { FundDialog } from './FundDialog';
import {
  AdjustmentDialog,
  AdvanceDialog,
  CountDialog,
  HolderChangeDialog,
} from './PettyCashDialogs';
import {
  AcknowledgeMovementDialog,
  ConfirmReturnDialog,
  FundingDialog,
  IssueDialog,
  ReturnDialog,
} from './MovementDialogs';
import {
  FUND_DEACTIVATE_CONSEQUENCES,
  MOVEMENT_KIND_LABELS,
  PETTY_CASH_ERROR_HINTS,
} from './pettyCashDisplay';
import { usePettyCashPolicy } from './pettyCashState';

export const OWN_FUND = 'You hold this fund; someone else decides or hands over its money.';

/** A proposal decision (approve / reject) with the server's refusal shown as it comes. */
export function decide<T>(
  title: string,
  summary: ReactNode,
  onDecide: (approve: boolean, note: string | null, key: string) => Promise<T>,
  onDone: (r: T) => void,
  onClose: () => void,
) {
  return (
    <DecisionDialog<T>
      title={title}
      kind="approve"
      summary={summary}
      explanation="Approved money is handed over next and counts in the fund once the holder confirms it. Rejected requests never count. The proposer and the fund's holder cannot decide."
      onDecide={async (approve, note, key) => {
        try {
          return await onDecide(approve, note, key);
        } catch (err) {
          throw withErrorCode(err, PETTY_CASH_ERROR_HINTS);
        }
      }}
      onDone={onDone}
      onClose={onClose}
    />
  );
}

type FundOpen =
  'edit' | 'propose' | 'request' | 'return' | 'count' | 'holder' | 'adjust' | 'advance';

/**
 * Everything done to a fund (row menu and fund page): view, edit, deactivate / reactivate, change
 * holder, propose money, count, adjust; the holder's request a top-up, return money and pay an
 * advance. Each command follows the user's permissions, the fund's state and the tenant's policy.
 */
export function useFundActions({
  holds,
  onChanged,
  onView,
}: {
  holds: (fundId: string) => boolean;
  onChanged: () => void;
  onView?: (f: PettyCashFundDto) => void;
}) {
  const notify = useNotify();
  const can = useMutationGuard();
  const policy = usePettyCashPolicy();
  const canManage = can(PERMISSIONS.tenantPettyCashManage);
  const canPropose = can(PERMISSIONS.tenantPettyCashPropose);
  const canCount = can(PERMISSIONS.tenantPettyCashCount);
  const canAct = can(PERMISSIONS.tenantPettyCashRead);
  const [open, setOpen] = useState<{ kind: FundOpen; fund: PettyCashFundDto } | null>(null);
  const lifecycle = useLifecycleDialog<PettyCashFundDto>({
    labelOf: (f) => f.name,
    noun: 'petty cash fund',
    deactivate: (f, body, key) =>
      pettyCashService.deactivate(f.id, { ...body, version: f.version }, key),
    reactivate: (f, body, key) =>
      pettyCashService.reactivate(f.id, { ...body, version: f.version }, key),
    errorHints: PETTY_CASH_ERROR_HINTS,
    consequences: FUND_DEACTIVATE_CONSEQUENCES,
    onReload: onChanged,
    onDone: (f, kind) => {
      notify.success(`${f.name} ${kind === 'deactivate' ? 'deactivated' : 'reactivated'}.`);
      onChanged();
    },
  });
  const actionsFor = (f: PettyCashFundDto): RowAction[] => {
    const go = (kind: FundOpen) => () => {
      setOpen({ kind, fund: f });
    };
    const mine = holds(f.id);
    const active = f.is_active;
    const extra: RowAction[] = [
      {
        key: 'propose',
        label: 'Propose funding or top-up',
        hidden: !canPropose || !active,
        onClick: go('propose'),
      },
      {
        key: 'request',
        label: 'Request a top-up',
        hidden: !mine || !canAct || !active,
        onClick: go('request'),
      },
      {
        key: 'return',
        label: 'Return money',
        hidden: !mine || !canAct || !active,
        onClick: go('return'),
      },
      { key: 'count', label: 'Record a count', hidden: !canCount || !active, onClick: go('count') },
      {
        key: 'advance',
        label: 'Pay an advance',
        hidden: !mine || !canAct || !active || policy?.advancesEnabled !== true,
        onClick: go('advance'),
      },
      {
        key: 'adjust',
        label: 'Propose an adjustment',
        hidden: !canPropose || !active,
        onClick: go('adjust'),
      },
      {
        key: 'holder',
        label: 'Change holder',
        hidden: !canManage || !active,
        disabled: f.pending_holder_change_id != null,
        disabledReason: 'A holder change is already waiting for the new holder.',
        onClick: go('holder'),
      },
    ];
    return [
      ...standardRowActions({
        active,
        canEdit: canManage,
        canChangeState: canManage,
        ...(onView === undefined
          ? {}
          : {
              onView: () => {
                onView(f);
              },
            }),
        onEdit: go('edit'),
        onDeactivate: () => {
          lifecycle.open('deactivate', f);
        },
        onReactivate: () => {
          lifecycle.open('reactivate', f);
        },
      }).filter((a) => a.key !== 'deactivate' && a.key !== 'reactivate'),
      ...extra,
      ...standardRowActions({
        active,
        canChangeState: canManage,
        onDeactivate: () => {
          lifecycle.open('deactivate', f);
        },
        onReactivate: () => {
          lifecycle.open('reactivate', f);
        },
      }),
    ];
  };
  const close = () => {
    setOpen(null);
  };
  const done = (message: string) => () => {
    notify.success(message);
    onChanged();
  };
  let dialog: ReactNode = null;
  if (open !== null) {
    const f = open.fund;
    switch (open.kind) {
      case 'edit':
        dialog = (
          <FundDialog
            fund={f}
            onClose={close}
            onReload={onChanged}
            onSaved={done(`${f.name} updated.`)}
          />
        );
        break;
      case 'propose':
      case 'request':
        dialog = (
          <FundingDialog
            fund={f}
            mode={open.kind}
            onClose={close}
            onDone={(m) => {
              notify.success(`${MOVEMENT_KIND_LABELS[m.kind]} ${m.number} sent for approval.`);
              onChanged();
            }}
          />
        );
        break;
      case 'return':
        dialog = (
          <ReturnDialog
            fund={f}
            onClose={close}
            onDone={(m) => {
              notify.success(
                `Return ${m.number} recorded; the office confirms the amount counted.`,
              );
              onChanged();
            }}
          />
        );
        break;
      case 'count':
        dialog = (
          <CountDialog
            fund={f}
            onClose={close}
            onDone={(c) => {
              notify.success(
                c.variance_id == null
                  ? `Count ${c.number} recorded; it matches the cash expected.`
                  : `Count ${c.number} recorded; the difference is open for follow-up.`,
              );
              onChanged();
            }}
          />
        );
        break;
      case 'holder':
        dialog = (
          <HolderChangeDialog
            fund={f}
            onClose={close}
            onDone={done('Holder change started; the new holder confirms it.')}
          />
        );
        break;
      case 'adjust':
        dialog = (
          <AdjustmentDialog
            fund={f}
            onClose={close}
            onDone={done('Adjustment proposed; someone else decides it.')}
          />
        );
        break;
      case 'advance':
        dialog = (
          <AdvanceDialog
            fund={f}
            clearWithinDays={policy?.advanceClearWithinDays ?? 7}
            onClose={close}
            onDone={(a) => {
              notify.success(`Advance ${a.number} paid.`);
              onChanged();
            }}
          />
        );
        break;
    }
  }
  return {
    actionsFor,
    dialogs: (
      <>
        {lifecycle.dialog}
        {dialog}
      </>
    ),
  };
}

const movementSummary = (m: PettyCashMovementDto) => (
  <KeyValueGrid
    columns={2}
    items={[
      { label: 'Number', value: m.number },
      { label: 'Kind', value: MOVEMENT_KIND_LABELS[m.kind] },
      { label: 'Fund', value: m.petty_cash_fund_name ?? '—' },
      { label: 'Holder', value: m.holder_staff_name ?? '—' },
      { label: 'Amount', value: <MoneyText amount={m.amount} currency={m.currency} strong /> },
      { label: 'Proposed by', value: m.created_by_name ?? '—' },
      ...(m.above_cap_reason == null
        ? []
        : [{ label: 'Above the limit because', value: m.above_cap_reason }]),
    ]}
  />
);

type MovementOpen = 'decide' | 'issue' | 'ack' | 'confirm';

/** Decide, hand over, acknowledge, confirm: each by the right person, never the proposer or holder. */
export function useMovementActions(holds: (fundId: string) => boolean, onChanged: () => void) {
  const notify = useNotify();
  const can = useMutationGuard();
  const me = useMyUserId();
  const canApprove = can(PERMISSIONS.tenantPettyCashApprove);
  const canPropose = can(PERMISSIONS.tenantPettyCashPropose);
  const canRead = can(PERMISSIONS.tenantPettyCashRead);
  const [open, setOpen] = useState<{ kind: MovementOpen; m: PettyCashMovementDto } | null>(null);
  const actionsFor = (m: PettyCashMovementDto): RowAction[] => {
    const go = (kind: MovementOpen) => () => {
      setOpen({ kind, m });
    };
    const ownProposal = m.created_by !== null && m.created_by === me;
    const mine = holds(m.fund_id);
    return [
      {
        key: 'decide',
        label: 'Approve / reject',
        // The proposer never sees an approve command for their own request.
        hidden: !canApprove || m.status !== 'PROPOSED' || ownProposal,
        disabled: mine,
        disabledReason: OWN_FUND,
        onClick: go('decide'),
      },
      {
        key: 'issue',
        label: 'Hand over the money',
        hidden: !canPropose || m.status !== 'APPROVED',
        disabled: mine,
        disabledReason: OWN_FUND,
        onClick: go('issue'),
      },
      {
        key: 'ack',
        label: 'Confirm money received',
        hidden: !canRead || m.status !== 'ISSUED' || !mine,
        onClick: go('ack'),
      },
      {
        key: 'confirm',
        label: 'Confirm the return',
        hidden: !canPropose || m.status !== 'CLAIMED',
        disabled: mine || ownProposal,
        disabledReason: mine ? OWN_FUND : 'You recorded this return; someone else counts it.',
        onClick: go('confirm'),
      },
    ];
  };
  const close = () => {
    setOpen(null);
  };
  const done = (message: string) => {
    notify.success(message);
    onChanged();
  };
  let dialog: ReactNode = null;
  if (open !== null) {
    const m = open.m;
    if (open.kind === 'decide') {
      dialog = decide(
        `Decide ${MOVEMENT_KIND_LABELS[m.kind].toLowerCase()} ${m.number}`,
        movementSummary(m),
        (approve, note, key) => pettyCashService.decideMovement(m.id, { approve, note }, key),
        (r) => {
          done(
            r.status === 'APPROVED'
              ? `${r.number} approved; it can be handed over.`
              : `${r.number} rejected.`,
          );
        },
        close,
      );
    } else if (open.kind === 'issue') {
      dialog = (
        <IssueDialog
          movement={m}
          onClose={close}
          onDone={(r) => {
            done(`${r.number} handed over; the holder confirms what they received.`);
          }}
        />
      );
    } else if (open.kind === 'ack') {
      dialog = (
        <AcknowledgeMovementDialog
          movement={m}
          onClose={close}
          onDone={(r) => {
            done(r.status === 'DISPUTED' ? `${r.number} disputed.` : `${r.number} received.`);
          }}
        />
      );
    } else {
      dialog = (
        <ConfirmReturnDialog
          movement={m}
          onClose={close}
          onDone={(r) => {
            done(`Return ${r.number} confirmed.`);
          }}
        />
      );
    }
  }
  return { actionsFor, dialog };
}
