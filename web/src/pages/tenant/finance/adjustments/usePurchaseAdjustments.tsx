import { useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useCanMutate } from '../../../../access/useCanMutate';
import type { AdjustmentRequestDto } from '../../../../api/adjustmentTypes';
import type { HoursPurchaseDto } from '../../../../api/hoursTypes';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { adjustmentRequestPath } from '../../../../navigation/adjustmentRoutes';
import { useNotify } from '../../../../notifications/useNotify';
import { isZeroDecimal } from '../../../../utils/money';
import {
  CorrectHoursDialog,
  RefundHoursDialog,
  ReversePurchaseDialog,
} from './PurchaseAdjustmentDialogs';

type Open = 'correct' | 'refund' | 'reverse' | null;

/** "Correct hours", "Refund unused hours" and "Reverse purchase" on an hours purchase. */
export function usePurchaseAdjustments(
  purchase: HoursPurchaseDto | null,
  { live, refundAllowed }: { live: boolean; refundAllowed: boolean },
): { actions: RowAction[]; dialogs: ReactNode } {
  const navigate = useNavigate();
  const notify = useNotify();
  const canPropose = useCanMutate(PERMISSIONS.tenantAdjustmentPropose);
  const [open, setOpen] = useState<Open>(null);
  const close = () => {
    setOpen(null);
  };
  const onDone = (r: AdjustmentRequestDto) => {
    notify.success('Proposed; someone else decides it.');
    void navigate(adjustmentRequestPath(r.id));
  };
  if (purchase === null) return { actions: [], dialogs: null };
  const show = canPropose && live;
  const actions: RowAction[] = [
    {
      key: 'correct-hours',
      label: 'Correct hours',
      hidden: !show,
      onClick: () => {
        setOpen('correct');
      },
    },
    {
      key: 'refund-hours',
      label: 'Refund unused hours',
      hidden: !show || !refundAllowed || isZeroDecimal(purchase.totals.remaining),
      onClick: () => {
        setOpen('refund');
      },
    },
    {
      key: 'reverse-purchase',
      label: 'Reverse purchase',
      destructive: true,
      hidden: !show,
      onClick: () => {
        setOpen('reverse');
      },
    },
  ];
  const props = { purchase, onClose: close, onDone };
  const dialogs = (
    <>
      {open === 'correct' && <CorrectHoursDialog {...props} />}
      {open === 'refund' && <RefundHoursDialog {...props} />}
      {open === 'reverse' && <ReversePurchaseDialog {...props} />}
    </>
  );
  return { actions, dialogs };
}
