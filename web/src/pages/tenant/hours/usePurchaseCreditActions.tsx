import { useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type { HoursPurchaseDto } from '../../../api/hoursTypes';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { isZeroDecimal } from '../../../utils/money';
import { nameOr } from '../shared/names';
import { useMyUserId } from '../shared/useFinanceLabels';
import { money } from './hoursQuote';
import { ActivateOnCreditDialog, RejectCreditDialog } from './PurchaseActionDialogs';

/**
 * The credit decisions on an order: activate hours on credit, or reject the credit part (its invoice is
 * cancelled, its hours never activate). Rejecting is never offered to the seller of the order (the server
 * refuses it too); neither is offered without `tenant.hours.credit_activate`.
 */
export function usePurchaseCreditActions(
  p: HoursPurchaseDto | null,
  {
    live,
    creditOn,
    onDone,
  }: { live: boolean; creditOn: boolean; onDone: (message: string) => void },
): { actions: RowAction[]; dialogs: ReactNode } {
  const canCredit = useCanMutate(PERMISSIONS.tenantHoursCreditActivate);
  const me = useMyUserId();
  const [open, setOpen] = useState<'activate' | 'reject' | null>(null);
  if (p === null) return { actions: [], dialogs: null };
  const ownSale = p.created_by !== null && p.created_by === me;
  const close = () => {
    setOpen(null);
  };
  const actions: RowAction[] = [
    {
      key: 'credit',
      label: 'Activate on credit',
      hidden:
        !canCredit ||
        !live ||
        !creditOn ||
        p.credit_status === 'REJECTED' ||
        isZeroDecimal(p.totals.awaiting_activation),
      onClick: () => {
        setOpen('activate');
      },
    },
    {
      key: 'rejectCredit',
      label: 'Reject credit',
      destructive: true,
      hidden: !canCredit || !live || p.credit_status !== 'AWAITING_ACTIVATION' || ownSale,
      onClick: () => {
        setOpen('reject');
      },
    },
  ];
  const dialogs = (
    <>
      {open === 'activate' && (
        <ActivateOnCreditDialog
          purchase={p}
          onClose={close}
          onDone={() => {
            onDone('Hours activated on credit.');
          }}
        />
      )}
      {open === 'reject' && (
        <RejectCreditDialog
          purchaseId={p.id}
          purchaseNumber={p.purchase_number}
          customerName={nameOr(p.customer_name, p.customer_id)}
          amount={money(p.credit_amount ?? '0', p.currency)}
          onClose={close}
          onDone={() => {
            onDone('Credit rejected; its invoice is cancelled and the seller is told why.');
          }}
        />
      )}
    </>
  );
  return { actions, dialogs };
}
