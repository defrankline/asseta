import Add from '@mui/icons-material/Add';
import DeleteOutlined from '@mui/icons-material/DeleteOutlined';
import { Alert, Box, Button, IconButton, Paper, Tooltip, Typography } from '@mui/material';
import { FieldArray, type FormikProps } from 'formik';
import { useCallback } from 'react';
import { usePlatformInvoicingService } from '../../../api/services/platformInvoicingService';
import type { ProductDto } from '../../../api/types';
import { LOOKUP_PAGE_SIZE } from '../../../components/data/AsyncAutocomplete';
import { FormikAsyncIdAutocomplete } from '../../../components/forms/FormikAsyncIdAutocomplete';
import { FormikDateField } from '../../../components/forms/FormikDateField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { KIND_EFFECTS, KIND_LABELS, priceSummary } from '../catalog/catalogForm';
import { EMPTY_LINE, MAX_LINES, type RaiseInvoiceValues } from './raiseInvoiceForm';

const itemId = (i: ProductDto) => i.id;
const itemLabel = (i: ProductDto) =>
  `${i.code} · ${i.name} (${KIND_LABELS[i.product_type]}, ${priceSummary(i)})`;

interface InvoiceLinesStepProps {
  formik: FormikProps<RaiseInvoiceValues>;
}

/**
 * Repeating invoice lines: catalog item (server search) with quantity, negotiated unit price and
 * discount %; subscription fees take only the billing period start.
 */
export function InvoiceLinesStep({ formik }: InvoiceLinesStepProps) {
  const service = usePlatformInvoicingService();
  const { currency, lines } = formik.values;
  const searchItems = useCallback(
    async (q: string, signal: AbortSignal) =>
      (await service.listProducts({ page: 1, page_size: LOOKUP_PAGE_SIZE, q }, signal)).items,
    [service],
  );
  const resolveItem = useCallback(
    (id: string, signal: AbortSignal) => service.getProduct(id, signal),
    [service],
  );
  const currencyLabel = currency === '' ? "tenant's currency" : currency;

  const picked = (index: number, item: ProductDto | null) => {
    const base = `lines.${String(index)}`;
    void formik.setFieldValue(`${base}.product_type`, item?.product_type ?? '', false);
    void formik.setFieldValue(`${base}.priced_in`, Object.keys(item?.prices ?? {}), false);
  };

  return (
    <FieldArray name="lines">
      {(helpers) => (
        <Box className="flex flex-col gap-3">
          <Typography variant="body2" color="text.secondary">
            Amounts, discounts, tax and totals are computed by the server on the Review step.
          </Typography>
          {lines.map((line, index) => {
            const base = `lines.${String(index)}`;
            const subscription = line.product_type === 'SUBSCRIPTION_FEE';
            return (
              <Paper
                key={index}
                variant="outlined"
                className="flex flex-col gap-2 p-3"
                component="section"
                aria-label={`Line ${String(index + 1)}`}
              >
                <Box className="flex items-center justify-between">
                  <Typography variant="subtitle2">Line {index + 1}</Typography>
                  {lines.length > 1 && (
                    <Tooltip title="Remove line">
                      <IconButton
                        size="small"
                        aria-label={`Remove line ${String(index + 1)}`}
                        onClick={() => {
                          helpers.remove(index);
                        }}
                      >
                        <DeleteOutlined fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  )}
                </Box>
                <FormikAsyncIdAutocomplete<ProductDto>
                  name={`${base}.product_id`}
                  label="Catalog item"
                  required
                  fetchOptions={searchItems}
                  resolveOption={resolveItem}
                  getOptionId={itemId}
                  getOptionLabel={itemLabel}
                  onOptionChange={(item) => {
                    picked(index, item);
                  }}
                  noOptionsText="No active catalog items match"
                />
                {line.product_type !== '' && (
                  <Alert severity="info" variant="outlined">
                    {KIND_EFFECTS[line.product_type]}
                  </Alert>
                )}
                {subscription ? (
                  <FormikDateField
                    name={`${base}.period_start`}
                    label="Billing period start"
                    required
                    helperText="Must be the start of a billing period not yet invoiced."
                  />
                ) : (
                  <Box className="grid gap-2 sm:grid-cols-3">
                    <FormikTextField
                      name={`${base}.quantity`}
                      label="Quantity"
                      required
                      slotProps={{ htmlInput: { inputMode: 'decimal' } }}
                    />
                    <FormikTextField
                      name={`${base}.unit_price`}
                      label={`Unit price (${currencyLabel})`}
                      helperText="Empty: catalog price"
                      slotProps={{ htmlInput: { inputMode: 'decimal' } }}
                    />
                    <FormikTextField
                      name={`${base}.discount_percent`}
                      label="Discount %"
                      slotProps={{ htmlInput: { inputMode: 'decimal' } }}
                    />
                  </Box>
                )}
                <FormikTextField
                  name={`${base}.description`}
                  label="Line description (optional)"
                  helperText="Defaults to the catalog item name."
                />
              </Paper>
            );
          })}
          <Box>
            <Button
              startIcon={<Add />}
              disabled={lines.length >= MAX_LINES}
              onClick={() => {
                helpers.push(EMPTY_LINE);
              }}
            >
              Add line
            </Button>
          </Box>
        </Box>
      )}
    </FieldArray>
  );
}
