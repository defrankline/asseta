import { object, string, type ObjectSchema } from 'yup';
import type { CreditArrangementDto, DiscountDto } from '../../../api/hoursTypes';
import { creditArrangementService, discountService } from '../../../api/services/hoursService';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikDateField } from '../../../components/forms/FormikDateField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { todayIsoDate, isIsoDate } from '../../../utils/dates';
import { compareDecimal, SUPPORTED_CURRENCIES } from '../../../utils/money';
import { isoDateField, positiveDecimalField } from '../../platform/shared/validators';
import { withErrorCode } from '../shared/errorHints';
import { FormikCustomerIdPicker } from '../shared/financePickers';
import { optionalText, orNull } from '../shared/formRules';
import { HOURS_ERROR_HINTS } from './hoursDisplay';
import { FormikReasonCodePicker } from './hoursPickers';

const decimal = { htmlInput: { inputMode: 'decimal' as const } };
const CURRENCY_OPTIONS = [
  { value: '', label: 'Company currency' },
  ...SUPPORTED_CURRENCIES.map((c) => ({ value: c, label: c })),
];

const commonFields = (reasonCodeRequired: boolean) => ({
  customer_id: string().required('Choose the customer'),
  effective_from: isoDateField('Effective from'),
  effective_to: string()
    .ensure()
    .test('date', 'Enter a valid date or leave empty', (v) => v === '' || isIsoDate(v))
    .test('after', 'Must not be before the start', function (v) {
      const from = (this.parent as { effective_from: string }).effective_from;
      return v === '' || from === '' || v >= from;
    }),
  reason: string()
    .trim()
    .required('A reason is required')
    .min(3, 'At least 3 characters')
    .max(1000, 'At most 1000 characters'),
  reason_code_id: string()
    .ensure()
    .test('required', 'Choose a reason from the list', (v) => !reasonCodeRequired || v !== ''),
});

interface FormProps<D> {
  record: D | null;
  reasonCodeRequired: boolean;
  onClose: () => void;
  onSaved: (d: D) => void;
}

interface DiscountValues {
  customer_id: string;
  percent: string;
  effective_from: string;
  effective_to: string;
  reason: string;
  reason_code_id: string;
}

/** Propose (or edit your own pending) customer discount; applied automatically once approved. */
export function DiscountFormDialog({
  record,
  reasonCodeRequired,
  maxPercent,
  onClose,
  onSaved,
}: FormProps<DiscountDto> & { maxPercent: string }) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  const schema: ObjectSchema<DiscountValues> = object({
    ...commonFields(reasonCodeRequired),
    percent: positiveDecimalField('Discount').test(
      'max',
      `At most ${maxPercent} % (company policy)`,
      (v) => !/^\d+(\.\d+)?$/.test(v) || compareDecimal(v, maxPercent) <= 0,
    ),
  });
  return (
    <FormDialog<DiscountValues>
      open
      title={record === null ? 'Propose customer discount' : 'Edit discount proposal'}
      initialValues={{
        customer_id: record?.customer_id ?? '',
        percent: record?.percent ?? '',
        effective_from: record?.effective_from ?? todayIsoDate(),
        effective_to: record?.effective_to ?? '',
        reason: record?.reason ?? '',
        reason_code_id: record?.reason_code_id ?? '',
      }}
      validationSchema={schema}
      submitLabel={record === null ? 'Propose discount' : 'Save changes'}
      onClose={onClose}
      onSubmit={async (v) => {
        const fields = {
          percent: v.percent.trim(),
          effective_from: v.effective_from,
          effective_to: orNull(v.effective_to),
          reason: v.reason.trim(),
          reason_code_id: orNull(v.reason_code_id),
        };
        try {
          if (record === null) {
            const body = { ...fields, customer_id: v.customer_id };
            onSaved(await discountService.propose(body, keyFor(body)));
          } else {
            const body = { ...fields, version: record.version };
            onSaved(await guard(() => discountService.update(record.id, body, keyFor(body))));
          }
        } catch (err) {
          throw withErrorCode(err, HOURS_ERROR_HINTS);
        }
      }}
    >
      {stale && <StaleVersionAlert onReload={onClose} />}
      <FormikCustomerIdPicker
        name="customer_id"
        label="Customer"
        required
        disabled={record !== null}
      />
      <FormikTextField name="percent" label="Discount (%)" required slotProps={decimal} />
      <FormikDateField name="effective_from" label="Effective from" required />
      <FormikDateField name="effective_to" label="Effective to (optional)" />
      <FormikReasonCodePicker
        name="reason_code_id"
        kind="DISCOUNT"
        label="Reason from your list"
        required={reasonCodeRequired}
      />
      <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
    </FormDialog>
  );
}

interface CreditValues {
  customer_id: string;
  limit_amount: string;
  currency: string;
  terms: string;
  effective_from: string;
  effective_to: string;
  reason: string;
  reason_code_id: string;
}

/** Propose (or edit your own pending) credit arrangement: limit, currency, dates, terms. */
export function CreditFormDialog({
  record,
  reasonCodeRequired,
  onClose,
  onSaved,
}: FormProps<CreditArrangementDto>) {
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  const schema: ObjectSchema<CreditValues> = object({
    ...commonFields(reasonCodeRequired),
    limit_amount: positiveDecimalField('Credit limit'),
    currency: string().ensure(),
    terms: optionalText('Terms', 1000),
  });
  return (
    <FormDialog<CreditValues>
      open
      title={record === null ? 'Propose credit arrangement' : 'Edit credit proposal'}
      initialValues={{
        customer_id: record?.customer_id ?? '',
        limit_amount: record?.limit_amount ?? '',
        currency: record?.currency ?? '',
        terms: record?.terms ?? '',
        effective_from: record?.effective_from ?? todayIsoDate(),
        effective_to: record?.effective_to ?? '',
        reason: record?.reason ?? '',
        reason_code_id: record?.reason_code_id ?? '',
      }}
      validationSchema={schema}
      submitLabel={record === null ? 'Propose credit' : 'Save changes'}
      onClose={onClose}
      onSubmit={async (v) => {
        const fields = {
          limit_amount: v.limit_amount.trim(),
          terms: orNull(v.terms),
          effective_from: v.effective_from,
          effective_to: orNull(v.effective_to),
          reason: v.reason.trim(),
          reason_code_id: orNull(v.reason_code_id),
        };
        try {
          if (record === null) {
            const body = { ...fields, customer_id: v.customer_id, currency: orNull(v.currency) };
            onSaved(await creditArrangementService.propose(body, keyFor(body)));
          } else {
            const body = { ...fields, version: record.version };
            onSaved(
              await guard(() => creditArrangementService.update(record.id, body, keyFor(body))),
            );
          }
        } catch (err) {
          throw withErrorCode(err, HOURS_ERROR_HINTS);
        }
      }}
    >
      {stale && <StaleVersionAlert onReload={onClose} />}
      <FormikCustomerIdPicker
        name="customer_id"
        label="Customer"
        required
        disabled={record !== null}
      />
      <FormikTextField name="limit_amount" label="Credit limit" required slotProps={decimal} />
      <FormikSelectField
        name="currency"
        label="Currency"
        options={CURRENCY_OPTIONS}
        disabled={record !== null}
      />
      <FormikDateField name="effective_from" label="Effective from" required />
      <FormikDateField name="effective_to" label="Effective to (optional)" />
      <FormikTextField name="terms" label="Terms (optional)" multiline minRows={2} />
      <FormikReasonCodePicker
        name="reason_code_id"
        kind="CREDIT"
        label="Reason from your list"
        required={reasonCodeRequired}
      />
      <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
    </FormDialog>
  );
}
