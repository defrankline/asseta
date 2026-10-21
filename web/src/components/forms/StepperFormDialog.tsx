import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Step,
  StepLabel,
  Stepper,
  type DialogProps,
} from '@mui/material';
import {
  Form,
  Formik,
  getIn,
  type FormikHelpers,
  type FormikProps,
  type FormikValues,
} from 'formik';
import { useState, type ReactNode } from 'react';
import type { ObjectSchema } from 'yup';
import { applySubmitError, statusMessage } from './submitHandling';

export interface FormStep<V> {
  label: string;
  /** Field paths validated before leaving this step. */
  fields: readonly string[];
  render: (formik: FormikProps<V>) => ReactNode;
}

export interface StepperFormDialogProps<V extends FormikValues> {
  open: boolean;
  title: string;
  steps: readonly FormStep<V>[];
  /** Content of the mandatory final Review step. */
  renderReview: (values: V) => ReactNode;
  initialValues: V;
  validationSchema: ObjectSchema<V>;
  onSubmit: (values: V, helpers: FormikHelpers<V>) => Promise<void>;
  onClose: () => void;
  submitLabel?: string;
  maxWidth?: DialogProps['maxWidth'];
}

export const REVIEW_STEP_LABEL = 'Review';

/** Multi-step Formik dialog for forms with more than three fields; always ends with Review. */
export function StepperFormDialog<V extends FormikValues>({
  open,
  title,
  steps,
  renderReview,
  initialValues,
  validationSchema,
  onSubmit,
  onClose,
  submitLabel = 'Submit',
  maxWidth = 'md',
}: StepperFormDialogProps<V>) {
  const [active, setActive] = useState(0);
  const isReview = active === steps.length;

  const close = () => {
    setActive(0);
    onClose();
  };

  const next = async (formik: FormikProps<V>) => {
    const step = steps[active];
    if (step === undefined) return;
    const errors = await formik.validateForm();
    await Promise.all(step.fields.map((f) => formik.setFieldTouched(f, true, false)));
    const blocking = step.fields.some((f) => getIn(errors, f) !== undefined);
    if (!blocking) setActive((a) => a + 1);
  };

  const handleSubmit = async (values: V, helpers: FormikHelpers<V>) => {
    helpers.setStatus(undefined);
    try {
      await onSubmit(values, helpers);
      close();
    } catch (err) {
      applySubmitError(err, helpers);
    }
  };

  return (
    <Formik
      initialValues={initialValues}
      validationSchema={validationSchema}
      onSubmit={handleSubmit}
    >
      {(formik) => (
        <Dialog
          open={open}
          onClose={formik.isSubmitting ? undefined : close}
          fullWidth
          maxWidth={maxWidth}
          aria-labelledby="stepper-dialog-title"
        >
          <Form noValidate>
            <DialogTitle id="stepper-dialog-title">{title}</DialogTitle>
            <DialogContent dividers>
              <Stack spacing={3}>
                <Stepper activeStep={active} alternativeLabel>
                  {[...steps.map((s) => s.label), REVIEW_STEP_LABEL].map((label) => (
                    <Step key={label}>
                      <StepLabel>{label}</StepLabel>
                    </Step>
                  ))}
                </Stepper>
                {statusMessage(formik.status) !== null && (
                  <Alert severity="error">{statusMessage(formik.status)}</Alert>
                )}
                <Stack spacing={2}>
                  {isReview ? renderReview(formik.values) : steps[active]?.render(formik)}
                </Stack>
              </Stack>
            </DialogContent>
            <DialogActions>
              <Button onClick={close} disabled={formik.isSubmitting}>
                Cancel
              </Button>
              <Button
                onClick={() => {
                  setActive((a) => Math.max(0, a - 1));
                }}
                disabled={active === 0 || formik.isSubmitting}
              >
                Back
              </Button>
              {isReview ? (
                <Button type="submit" variant="contained" loading={formik.isSubmitting}>
                  {submitLabel}
                </Button>
              ) : (
                <Button
                  variant="contained"
                  onClick={() => {
                    void next(formik);
                  }}
                >
                  Next
                </Button>
              )}
            </DialogActions>
          </Form>
        </Dialog>
      )}
    </Formik>
  );
}
