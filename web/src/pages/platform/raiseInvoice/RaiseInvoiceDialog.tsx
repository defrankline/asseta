import { useState } from 'react';
import { withErrorCode } from '../../../api/lifecycle';
import { usePlatformInvoicingService } from '../../../api/services/platformInvoicingService';
import type { InvoiceDto, TenantDto } from '../../../api/types';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikDateField } from '../../../components/forms/FormikDateField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { todayIsoDate } from '../../../utils/dates';
import { INVOICE_CURRENCY_OPTIONS } from './raiseInvoiceOptions';
import { resolveTenant, searchTenants, tenantId, tenantLabel } from '../shared/platformLookups';
import { InvoiceLinesStep } from './InvoiceLinesStep';
import { RaiseInvoiceReview } from './RaiseInvoiceReview';
import {
  emptyRaiseInvoice,
  lineFieldPaths,
  RAISE_ERROR_HINTS,
  raiseInvoiceSchema,
  TERMS_FIELDS,
  toRaiseBody,
  type RaiseInvoiceValues,
} from './raiseInvoiceForm';

interface RaiseInvoiceDialogProps {
  /** Pre-selects the tenant (e.g. from the tenant page). */
  tenantId?: string;
  onClose: () => void;
  onRaised: (invoice: InvoiceDto) => void;
}

/**
 * Raise an ad-hoc platform invoice at any time: tenant → lines (catalog items with quantity, unit
 * price, discount; subscription fees with a period) → Review with server-computed totals.
 * Mount only while open (one idempotency key per open).
 */
export function RaiseInvoiceDialog({
  tenantId: presetTenant,
  onClose,
  onRaised,
}: RaiseInvoiceDialogProps) {
  const service = usePlatformInvoicingService();
  const [initialValues] = useState(() => emptyRaiseInvoice(presetTenant));
  const [tenant, setTenant] = useState<TenantDto | null>(null);
  const keyFor = useIdempotencyKey();

  const steps: FormStep<RaiseInvoiceValues>[] = [
    {
      label: 'Tenant & terms',
      fields: TERMS_FIELDS,
      render: () => (
        <>
          <FormikAsyncIdAutocomplete<TenantDto>
            name="tenant_id"
            label="Tenant"
            required
            fetchOptions={searchTenants}
            resolveOption={resolveTenant}
            getOptionId={tenantId}
            getOptionLabel={tenantLabel}
            onOptionChange={setTenant}
          />
          <FormikSelectField
            name="currency"
            label="Currency"
            options={INVOICE_CURRENCY_OPTIONS}
            helperText="Default: the tenant's subscription currency."
          />
          <FormikDateField
            name="due_date"
            label="Due date"
            minDate={todayIsoDate()}
            helperText="Default: today plus the agreement's payment terms."
          />
          <FormikTextField
            name="notes"
            label="Notes (shown on the invoice)"
            multiline
            minRows={2}
          />
        </>
      ),
    },
    {
      label: 'Lines',
      fields: [],
      fieldsFor: lineFieldPaths,
      render: (formik) => <InvoiceLinesStep formik={formik} />,
    },
  ];

  return (
    <StepperFormDialog<RaiseInvoiceValues>
      open
      title="Raise invoice"
      steps={steps}
      initialValues={initialValues}
      validationSchema={raiseInvoiceSchema}
      submitLabel="Raise invoice"
      maxWidth="lg"
      onClose={onClose}
      renderReview={(v) => (
        <RaiseInvoiceReview values={v} tenantName={tenant?.display_name ?? null} />
      )}
      onSubmit={async (v) => {
        const body = toRaiseBody(v);
        try {
          onRaised(await service.raiseInvoice(body, keyFor(body)));
        } catch (err) {
          throw withErrorCode(err, RAISE_ERROR_HINTS);
        }
      }}
    />
  );
}
