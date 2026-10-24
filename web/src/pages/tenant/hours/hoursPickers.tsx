/**
 * Server-search pickers for customer hours forms. Every lookup passes the typed text to the API
 * (`q`) and asks for one page; nothing is filtered in the browser.
 */
import type { HoursPurchaseDto, ReasonCodeDto, ReasonKind } from '../../../api/hoursTypes';
import { customerPaymentService } from '../../../api/services/financeService';
import { hoursReasonService, hoursService } from '../../../api/services/hoursService';
import type { CustomerPaymentDto } from '../../../api/types';
import { LOOKUP_PAGE_SIZE } from '../../../components/data/AsyncAutocomplete';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { optionId } from '../shared/lookups';
import { paymentLabel, purchaseLabel, reasonCodeLabel } from './hoursDisplay';

const one = (q: string) => ({ page: 1, page_size: LOOKUP_PAGE_SIZE, q });

interface PickerProps {
  name: string;
  label: string;
  required?: boolean;
  disabled?: boolean;
  helperText?: string;
}

/** Active reason of one kind from the tenant's list (code / label search). */
export function FormikReasonCodePicker({ kind, ...props }: PickerProps & { kind: ReasonKind }) {
  return (
    <FormikAsyncIdAutocomplete<ReasonCodeDto>
      {...props}
      fetchOptions={(q, signal) => hoursReasonService.search(kind, q, signal)}
      resolveOption={(id, signal) => hoursReasonService.get(id, signal)}
      getOptionId={optionId}
      getOptionLabel={reasonCodeLabel}
      noOptionsText="No matching reason in your company list"
    />
  );
}

/** Open hours purchase (purchase-number search), optionally of one customer. */
export function FormikPurchaseIdPicker({
  customerId,
  onOptionChange,
  ...props
}: PickerProps & {
  customerId?: string | undefined;
  onOptionChange?: (p: HoursPurchaseDto | null) => void;
}) {
  return (
    <FormikAsyncIdAutocomplete<HoursPurchaseDto>
      {...props}
      {...(onOptionChange !== undefined ? { onOptionChange } : {})}
      fetchOptions={async (q, signal) =>
        (
          await hoursService.listPurchases(
            { ...one(q), filters: { customer_id: customerId, cancelled: 'false' } },
            signal,
          )
        ).items
      }
      resolveOption={(id, signal) => hoursService.getPurchase(id, signal)}
      getOptionId={optionId}
      getOptionLabel={purchaseLabel}
    />
  );
}

/** A customer's payment (reference search) to allocate to a purchase (the API refuses rejected ones). */
export function FormikCustomerPaymentPicker({
  customerId,
  ...props
}: PickerProps & { customerId: string }) {
  return (
    <FormikAsyncIdAutocomplete<CustomerPaymentDto>
      {...props}
      fetchOptions={async (q, signal) =>
        (
          await customerPaymentService.list(
            { ...one(q), filters: { customer_id: customerId } },
            signal,
          )
        ).items
      }
      getOptionId={optionId}
      getOptionLabel={paymentLabel}
      noOptionsText="No payment of this customer matches"
    />
  );
}
