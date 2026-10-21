import { useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import { customerPaymentService } from '../../../../api/services/financeService';
import type { CustomerPaymentDto } from '../../../../api/types';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { useNotify } from '../../../../notifications/useNotify';
import { DecisionDialog } from '../../shared/DecisionDialog';
import { PAYMENT_METHOD_LABELS } from '../../shared/financeDisplay';
import { useMyUserId } from '../../shared/useFinanceLabels';
import { AllocatePaymentDialog } from './AllocatePaymentDialog';

/** Shown instead of Verify for the person who recorded the payment (segregation of duties). */
export const SOD_RECORDER_NOTE =
  'You recorded this, so someone else must verify or reject it (segregation of duties).';

type Open = { kind: 'decide' | 'allocate'; payment: CustomerPaymentDto } | null;

interface Options {
  onChanged: (payment: CustomerPaymentDto) => void;
  onView?: (payment: CustomerPaymentDto) => void;
}

/** View, allocate and verify / reject commands for a customer payment. */
export function usePaymentActions({ onChanged, onView }: Options) {
  const notify = useNotify();
  const me = useMyUserId();
  const can = useMutationGuard();
  const canVerify = can(PERMISSIONS.tenantFinanceVerify);
  const canAllocate = can(PERMISSIONS.tenantFinancePayment);
  const [open, setOpen] = useState<Open>(null);
  const close = () => {
    setOpen(null);
  };
  const isMine = (p: CustomerPaymentDto) => p.recorded_by !== null && p.recorded_by === me;

  const actionsFor = (p: CustomerPaymentDto): RowAction[] => [
    {
      key: 'view',
      label: 'View details',
      hidden: onView === undefined,
      onClick: () => onView?.(p),
    },
    {
      key: 'decide',
      label: isMine(p) ? 'Verify / reject (not allowed: you recorded it)' : 'Verify / reject',
      hidden: !canVerify || p.status !== 'CLAIMED',
      disabled: isMine(p),
      onClick: () => {
        setOpen({ kind: 'decide', payment: p });
      },
    },
    {
      key: 'allocate',
      label: 'Allocate to invoices',
      hidden: !canAllocate || p.status === 'REJECTED',
      onClick: () => {
        setOpen({ kind: 'allocate', payment: p });
      },
    },
  ];

  let dialogs: ReactNode = null;
  if (open?.kind === 'decide') {
    const p = open.payment;
    dialogs = (
      <DecisionDialog<CustomerPaymentDto>
        title="Verify customer payment"
        kind="verify"
        summary={
          <KeyValueGrid
            columns={2}
            items={[
              {
                label: 'Amount',
                value: <MoneyText amount={p.amount} currency={p.currency} strong />,
              },
              { label: 'Method', value: PAYMENT_METHOD_LABELS[p.method] },
              { label: 'Reference', value: p.reference ?? '—' },
              { label: 'Source', value: p.source },
            ]}
          />
        }
        explanation="Verify only when the money is confirmed received (bank statement, mobile money record, cash counted). Verified money reduces the customer's balance; rejecting releases its allocations."
        onDecide={(approve, note, key) =>
          customerPaymentService.decide(p.id, { verified: approve, note }, key)
        }
        onDone={(r) => {
          notify.success(r.status === 'VERIFIED' ? 'Payment verified.' : 'Payment rejected.');
          onChanged(r);
        }}
        onClose={close}
      />
    );
  } else if (open?.kind === 'allocate') {
    dialogs = (
      <AllocatePaymentDialog
        payment={open.payment}
        onClose={close}
        onAllocated={(r) => {
          notify.success('Payment allocated.');
          onChanged(r);
        }}
      />
    );
  }
  return { actionsFor, dialogs, isMine };
}
