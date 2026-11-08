import { Alert } from '@mui/material';
import { useFormikContext } from 'formik';
import { useCallback, useEffect } from 'react';
import { CAPABILITY, useCapabilityEnabled } from '../../../../access/capabilities';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { cashService } from '../../../../api/services/cashService';
import type { CashCustodyBalanceDto } from '../../../../api/types';
import { FormikTextField } from '../../../../components/forms/FormikTextField';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useSession } from '../../../../session/useSession';
import { isPartialRemittance, type HandoverValues } from './cashForms';
import { useCashPolicy } from './custodyHooks';
import { FormikCashReasonIdPicker } from './custodyPickers';

/** The chosen currency's balance; with no currency chosen, the only balance the custodian holds. */
const balanceOf = (rows: readonly CashCustodyBalanceDto[] | null, currency: string) => {
  if (rows === null) return null;
  if (currency !== '') return rows.find((b) => b.currency === currency) ?? null;
  return rows.length === 1 ? (rows[0] ?? null) : null;
};

/**
 * Under the full-balance policy, a remittance short of the custodian's balance needs a reason (the
 * tenant's list plus the words). When the balance cannot be read the fields stay available and the
 * server's refusal explains the rule.
 */
export function PartialRemittanceFields({
  ownCustody,
  staffId,
}: {
  ownCustody: boolean;
  staffId: string;
}) {
  const { values, setFieldValue } = useFormikContext<HandoverValues>();
  const { hasPermission } = useSession();
  const controlsOn = useCapabilityEnabled(CAPABILITY.cashCustody);
  const policy = useCashPolicy();
  const fullBalance = controlsOn && (policy?.remitFullBalance ?? false);
  const custodian = ownCustody ? '' : values.staff_member_id || staffId;
  const mine = custodian === '';
  const canRead =
    mine || hasPermission([PERMISSIONS.tenantFinanceRead, PERMISSIONS.tenantFinanceCash], 'any');
  const load = useCallback(
    (signal: AbortSignal) =>
      mine ? cashService.myCustody(signal) : cashService.custody(custodian, signal),
    [mine, custodian],
  );
  const res = useAsyncResource(load, [custodian], fullBalance && canRead);
  const balance = balanceOf(res.data, values.currency);
  const short = balance !== null && isPartialRemittance(balance, values.amount.trim());
  useEffect(() => {
    void setFieldValue('partial_required', fullBalance && short, false);
  }, [fullBalance, short, setFieldValue]);
  if (!fullBalance) return null;
  if (balance !== null && !short) return null;
  return (
    <>
      <Alert severity={short ? 'warning' : 'info'}>
        {short
          ? 'This leaves part of the balance with the custodian. Your company policy expects the full balance, so say why; someone else decides the reason.'
          : 'If this is less than the custodian’s full balance, say why.'}
      </Alert>
      <FormikCashReasonIdPicker
        kind="PARTIAL_REMITTANCE"
        name="partial_reason_id"
        label="Reason (from the tenant's list)"
        helperText="Required when your organisation keeps a partial remittance reason list."
      />
      <FormikTextField
        name="partial_reason"
        label="Why part of the balance stays"
        required={short}
        multiline
        minRows={2}
      />
    </>
  );
}
