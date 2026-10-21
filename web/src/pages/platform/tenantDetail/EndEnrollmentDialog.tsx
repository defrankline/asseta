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
import { mixed, object } from 'yup';
import { subscriptionService } from '../../../api/services/subscriptionService';
import type {
  ChargePreviewDto,
  EndEnrollmentIn,
  EnrollmentDto,
  EnrollmentEndReason,
  EnrollmentResultDto,
} from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { humanize } from '../../../utils/text';
import { FormikDateField } from '../../../components/forms/FormikDateField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { applySubmitError, statusMessage } from '../../../components/forms/submitHandling';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { useNotify } from '../../../notifications/useNotify';
import { formatDate, todayIsoDate } from '../../../utils/dates';
import { END_REASON_OPTIONS, optionLabel } from '../shared/billingDisplay';
import { isoDateField } from '../shared/validators';

interface EndValues {
  effective_to: string;
  reason: EnrollmentEndReason;
}

const schema = object({
  effective_to: isoDateField('End date'),
  reason: mixed<EnrollmentEndReason>()
    .oneOf(END_REASON_OPTIONS.map((o) => o.value))
    .required('Reason is required'),
});

interface Previewed {
  body: EndEnrollmentIn;
  charge: ChargePreviewDto | null;
}

export function ChargePreviewView({ charge }: { charge: ChargePreviewDto | null }) {
  if (charge === null) {
    return (
      <Alert severity="info">
        <AlertTitle>No proration effect</AlertTitle>
        Ending this enrollment creates no pending charge or credit (e.g. covered by the minimum
        commitment or the removal policy).
      </Alert>
    );
  }
  return (
    <Alert severity="warning">
      <AlertTitle>{humanize(charge.line_type)}</AlertTitle>
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

interface EndEnrollmentDialogProps {
  subscriptionId: string;
  enrollment: EnrollmentDto;
  onClose: () => void;
  onEnded: (result: EnrollmentResultDto) => void;
}

/**
 * Two-phase removal of a billable asset: preview the proration effect first, then confirm
 * exactly the previewed request.
 */
export function EndEnrollmentDialog({
  subscriptionId,
  enrollment,
  onClose,
  onEnded,
}: EndEnrollmentDialogProps) {
  const notify = useNotify();
  const previewKey = useIdempotencyKey();
  const endKey = useIdempotencyKey();
  const [previewed, setPreviewed] = useState<Previewed | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [initialValues] = useState<EndValues>(() => ({
    effective_to: todayIsoDate(),
    reason: 'REMOVED_FROM_FLEET',
  }));

  const confirm = async (body: EndEnrollmentIn) => {
    setConfirming(true);
    try {
      const result = await subscriptionService.endEnrollment(
        subscriptionId,
        enrollment.id,
        body,
        endKey(body),
      );
      onEnded(result);
      onClose();
    } catch (err) {
      notify.error(err);
    } finally {
      setConfirming(false);
    }
  };

  return (
    <Formik<EndValues>
      initialValues={initialValues}
      validationSchema={schema}
      onSubmit={async (v, helpers) => {
        helpers.setStatus(undefined);
        const body: EndEnrollmentIn = { effective_to: v.effective_to, reason: v.reason };
        try {
          const charge = await subscriptionService.previewEndEnrollment(
            subscriptionId,
            enrollment.id,
            body,
            previewKey(body),
          );
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
          aria-labelledby="end-enrollment-title"
        >
          <Form noValidate>
            <DialogTitle id="end-enrollment-title">
              End enrollment · {enrollment.asset_label}
            </DialogTitle>
            <DialogContent dividers>
              <Stack spacing={2}>
                {statusMessage(formik.status) !== null && (
                  <Alert severity="error">{statusMessage(formik.status)}</Alert>
                )}
                {previewed === null ? (
                  <>
                    <Typography variant="body2" color="text.secondary">
                      Enrolled since {formatDate(enrollment.effective_from)}. The end date must fall
                      in the current billing period (no backdating).
                    </Typography>
                    <FormikDateField name="effective_to" label="End date" required />
                    <FormikSelectField
                      name="reason"
                      label="Reason"
                      options={END_REASON_OPTIONS}
                      required
                    />
                  </>
                ) : (
                  <>
                    <KeyValueGrid
                      columns={2}
                      items={[
                        { label: 'End date', value: formatDate(previewed.body.effective_to) },
                        {
                          label: 'Reason',
                          value: optionLabel(END_REASON_OPTIONS, previewed.body.reason),
                        },
                      ]}
                    />
                    <ChargePreviewView charge={previewed.charge} />
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
                    color="error"
                    loading={confirming}
                    onClick={() => {
                      void confirm(previewed.body);
                    }}
                  >
                    Confirm end
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
