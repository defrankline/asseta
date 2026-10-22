import Add from '@mui/icons-material/Add';
import DeleteOutlined from '@mui/icons-material/DeleteOutlined';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  IconButton,
  Stack,
  Typography,
} from '@mui/material';
import { FieldArray, type FormikProps } from 'formik';
import { useState } from 'react';
import { withErrorCode } from '../../../api/lifecycle';
import { usePlatformInvoicingService } from '../../../api/services/platformInvoicingService';
import type { ProductDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { StepperFormDialog, type FormStep } from '../../../components/forms/StepperFormDialog';
import { StaleVersionAlert } from '../../../components/lifecycle/StaleVersionAlert';
import { useStaleVersion } from '../../../components/lifecycle/useStaleVersion';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { formatMoney, isDecimalString } from '../../../utils/money';
import {
  CATALOG_ERROR_HINTS,
  catalogItemSchema,
  CURRENCY_OPTIONS,
  EMPTY_CATALOG_ITEM,
  EMPTY_PRICE,
  KIND_EFFECTS,
  KIND_LABELS,
  KIND_OPTIONS,
  pricingFieldPaths,
  PRODUCT_FIELDS,
  toCatalogCreate,
  toCatalogUpdate,
  valuesFromItem,
  type CatalogItemValues,
} from './catalogForm';

interface CatalogItemDialogProps {
  /** Product to edit; omit to add one. */
  item?: ProductDto;
  onClose: () => void;
  onSaved: (item: ProductDto) => void;
  onReload: () => void;
}

function PricingStep({ formik }: { formik: FormikProps<CatalogItemValues> }) {
  const { values } = formik;
  if (values.product_type === 'SUBSCRIPTION_FEE') {
    return (
      <Alert severity="info">
        Subscription fees have no list price: each invoice line is priced by the tenant&apos;s
        negotiated rate for the billing period.
      </Alert>
    );
  }
  return (
    <>
      <FormControlLabel
        control={
          <Checkbox
            checked={values.taxable}
            onChange={(e) => {
              void formik.setFieldValue('taxable', e.target.checked);
            }}
          />
        }
        label="Taxable (the tenant's tax rate applies)"
      />
      {values.product_type === 'SMS_BUNDLE' && (
        <FormikTextField
          name="sms_credits"
          label="SMS credits per bundle"
          required
          slotProps={{ htmlInput: { inputMode: 'numeric' } }}
        />
      )}
      <Typography variant="subtitle2">List prices (per currency)</Typography>
      <FieldArray name="prices">
        {(helpers) => (
          <Box className="flex flex-col gap-2">
            {values.prices.map((_p, i) => (
              <Box key={i} className="grid grid-cols-[1fr_2fr_auto] items-start gap-2">
                <FormikSelectField
                  name={`prices.${String(i)}.currency`}
                  label="Currency"
                  options={CURRENCY_OPTIONS}
                />
                <FormikTextField
                  name={`prices.${String(i)}.amount`}
                  label="Unit price"
                  required
                  slotProps={{ htmlInput: { inputMode: 'decimal' } }}
                />
                <IconButton
                  aria-label={`Remove price ${String(i + 1)}`}
                  onClick={() => {
                    helpers.remove(i);
                  }}
                >
                  <DeleteOutlined />
                </IconButton>
              </Box>
            ))}
            {typeof formik.errors.prices === 'string' && (
              <Alert severity="error">{formik.errors.prices}</Alert>
            )}
            <Box>
              <Button
                startIcon={<Add />}
                onClick={() => {
                  helpers.push(EMPTY_PRICE);
                }}
              >
                Add price
              </Button>
            </Box>
            <Typography variant="caption" color="text.secondary">
              Without a price in the invoice currency, a negotiated unit price must be given on the
              invoice line.
            </Typography>
          </Box>
        )}
      </FieldArray>
    </>
  );
}

/** Add or edit a catalog product (code and type fixed once created). Mount only while open. */
export function CatalogItemDialog({ item, onClose, onSaved, onReload }: CatalogItemDialogProps) {
  const service = usePlatformInvoicingService();
  const [initialValues] = useState(() =>
    item === undefined ? EMPTY_CATALOG_ITEM : valuesFromItem(item),
  );
  const keyFor = useIdempotencyKey();
  const { stale, guard } = useStaleVersion();
  const editing = item !== undefined;
  const fixed = editing ? { disabled: true, helperText: 'Fixed once created.' } : {};

  const steps: FormStep<CatalogItemValues>[] = [
    {
      label: 'Product',
      fields: PRODUCT_FIELDS,
      render: (f) => (
        <>
          <FormikTextField name="code" label="Code" required {...fixed} />
          <FormikTextField name="name" label="Name" required />
          <FormikSelectField
            name="product_type"
            label="Type"
            options={KIND_OPTIONS}
            required
            {...fixed}
          />
          {f.values.product_type !== '' && (
            <Alert severity="info">{KIND_EFFECTS[f.values.product_type]}</Alert>
          )}
          <FormikTextField name="description" label="Description" multiline minRows={2} />
        </>
      ),
    },
    {
      label: 'Pricing',
      fields: [],
      fieldsFor: pricingFieldPaths,
      render: (f) => <PricingStep formik={f} />,
    },
  ];

  return (
    <StepperFormDialog<CatalogItemValues>
      open
      title={item === undefined ? 'Add catalog item' : `Edit ${item.code}`}
      steps={steps}
      initialValues={initialValues}
      validationSchema={catalogItemSchema}
      submitLabel={item === undefined ? 'Add item' : 'Save changes'}
      onClose={onClose}
      renderReview={(v) => (
        <Stack spacing={2}>
          {stale && (
            <StaleVersionAlert
              onReload={() => {
                onReload();
                onClose();
              }}
            />
          )}
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Code', value: v.code.trim().toUpperCase() },
              { label: 'Name', value: v.name },
              { label: 'Type', value: v.product_type === '' ? '—' : KIND_LABELS[v.product_type] },
              {
                label: 'List prices',
                value:
                  v.product_type === 'SUBSCRIPTION_FEE'
                    ? 'Negotiated rate'
                    : v.prices
                        .map((p) =>
                          isDecimalString(p.amount) ? formatMoney(p.amount, p.currency) : p.amount,
                        )
                        .join(' · ') || 'None',
              },
              ...(v.product_type === 'SMS_BUNDLE'
                ? [{ label: 'SMS credits per bundle', value: v.sms_credits }]
                : []),
              {
                label: 'Taxable',
                value:
                  v.product_type === 'SUBSCRIPTION_FEE' ? 'Per rate' : v.taxable ? 'Yes' : 'No',
              },
              { label: 'Description', value: v.description.trim() === '' ? '—' : v.description },
            ]}
          />
        </Stack>
      )}
      onSubmit={async (v) => {
        try {
          if (item === undefined) {
            const body = toCatalogCreate(v);
            onSaved(await service.createProduct(body, keyFor(body)));
          } else {
            const body = toCatalogUpdate(v, item.version);
            onSaved(await guard(() => service.updateProduct(item.id, body, keyFor(body))));
          }
        } catch (err) {
          throw withErrorCode(err, CATALOG_ERROR_HINTS);
        }
      }}
    />
  );
}
