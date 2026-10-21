import {
  Alert,
  AlertTitle,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material';
import { Form, Formik } from 'formik';
import { useState } from 'react';
import { object, string, type ObjectSchema } from 'yup';
import { tenantBillingService } from '../../../api/services/tenantBillingService';
import type {
  ChargePreviewDto,
  EnrollAssetIn,
  EnrollmentResultDto,
  MachineDto,
} from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { FormikDateField } from '../../../components/forms/FormikDateField';
import { applySubmitError, statusMessage } from '../../../components/forms/submitHandling';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useNotify } from '../../../notifications/useNotify';
import { formatDate, isIsoDate, todayIsoDate } from '../../../utils/dates';
import { humanize } from '../../../utils/text';
import { machineLabel } from '../shared/display';

interface EnrollValues {
  effective_from: string;
}
const schema: ObjectSchema<EnrollValues> = object({
  effective_from: string()
    .required('Start date is required')
    .test('iso-date', 'Start date must be a valid date', (v) => isIsoDate(v)),
});

export function EnrollmentChargePreview({ charge }: { charge: ChargePreviewDto | null }) {
  if (charge === null) {
    return (
      <Alert severity="info">
        <AlertTitle>No proration charge</AlertTitle>
        Enrolling from this date adds no pending charge for the current period (e.g. covered by the
        minimum commitment or billed from the next period).
      </Alert>
    );
  }
  return (
    <Alert severity="warning">
      <AlertTitle>{humanize(charge.line_type)} on your next invoice</AlertTitle>
      <Stack spacing={1}>
        <KeyValueGrid
          columns={3}
          items={[
            {
              label: 'Amount',
              value: <MoneyText amount={charge.amount} currency={charge.currency} strong />,
            },
            { label: 'Days', value: `${String(charge.days)} of ${String(charge.period_days)}` },
            {
              label: 'Service period',
              value:
                charge.service_from === null
                  ? '—'
                  : `${formatDate(charge.service_from)} – ${formatDate(charge.service_to)}`,
            },
          ]}
        />
        <Typography variant="body2">{charge.explanation}</Typography>
      </Stack>
    </Alert>
  );
}

interface EnrollMachineDialogProps {
  machine: MachineDto;
  onClose: () => void;
  onEnrolled: (result: EnrollmentResultDto) => void;
}

interface Previewed {
  body: EnrollAssetIn;
  charge: ChargePreviewDto | null;
}

/**
 * Two-phase billable-asset enrollment: preview the proration effect first, then confirm exactly
 * the previewed request (separate idempotency key). Mount only while open.
 */
export function EnrollMachineDialog({ machine, onClose, onEnrolled }: EnrollMachineDialogProps) {
  const notify = useNotify();
  const previewKey = useIdempotencyKey();
  const enrollKey = useIdempotencyKey();
  const [previewed, setPreviewed] = useState<Previewed | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [initialValues] = useState<EnrollValues>(() => ({ effective_from: todayIsoDate() }));

  const confirm = async (body: EnrollAssetIn) => {
    setConfirming(true);
    try {
      const result = await tenantBillingService.enroll(body, enrollKey(body));
      onEnrolled(result);
      onClose();
    } catch (err) {
      notify.error(err);
    } finally {
      setConfirming(false);
    }
  };

  return (
    <Formik<EnrollValues>
      initialValues={initialValues}
      validationSchema={schema}
      onSubmit={async (v, helpers) => {
        helpers.setStatus(undefined);
        const body: EnrollAssetIn = { machine_id: machine.id, effective_from: v.effective_from };
        try {
          const charge = await tenantBillingService.previewEnrollment(body, previewKey(body));
          setPreviewed({ body, charge });
        } catch (err) {
          applySubmitError(err, helpers);
        }
      }}
    >
      {(formik) => (
        <Dialog
          open
          onClose={formik.isSubmitting || confirming ? undefined : onClose}
          fullWidth
          maxWidth="sm"
          aria-labelledby="enroll-machine-title"
        >
          <Form noValidate>
            <DialogTitle id="enroll-machine-title">
              Enroll as billable asset · {machineLabel(machine)}
            </DialogTitle>
            <DialogContent dividers>
              <Stack spacing={2}>
                {statusMessage(formik.status) !== null && (
                  <Alert severity="error">{statusMessage(formik.status)}</Alert>
                )}
                {previewed === null ? (
                  <>
                    <Typography variant="body2" color="text.secondary">
                      Enrolled machines are billed per your subscription agreement and can then be
                      tracked. Preview the charge before confirming.
                    </Typography>
                    <FormikDateField name="effective_from" label="Billable from" required />
                  </>
                ) : (
                  <>
                    <KeyValueGrid
                      columns={2}
                      items={[
                        { label: 'Machine', value: machineLabel(machine) },
                        {
                          label: 'Billable from',
                          value: formatDate(previewed.body.effective_from),
                        },
                      ]}
                    />
                    <EnrollmentChargePreview charge={previewed.charge} />
                  </>
                )}
              </Stack>
            </DialogContent>
            <DialogActions>
              <Button onClick={onClose} disabled={formik.isSubmitting || confirming}>
                Cancel
              </Button>
              {previewed === null ? (
                <Button type="submit" variant="contained" loading={formik.isSubmitting}>
                  Preview
                </Button>
              ) : (
                <>
                  <Button
                    onClick={() => {
                      setPreviewed(null);
                    }}
                    disabled={confirming}
                  >
                    Back
                  </Button>
                  <Button
                    variant="contained"
                    loading={confirming}
                    onClick={() => {
                      void confirm(previewed.body);
                    }}
                  >
                    Confirm enrollment
                  </Button>
                </>
              )}
            </DialogActions>
          </Form>
        </Dialog>
      )}
    </Formik>
  );
}
