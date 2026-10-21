import { Alert, Button, Stack } from '@mui/material';
import { Form, Formik } from 'formik';
import { FormikTextField } from '../forms/FormikTextField';
import { applySubmitError, statusMessage } from '../forms/submitHandling';
import { closeSchema, type CloseValues } from './mandateUi';

interface CloseMandateFormProps {
  /** e.g. "Reason for ending". */
  reasonLabel: string;
  submitLabel: string;
  /** Throw (ideally an ApiError) to keep the form and show the error. */
  onSubmit: (reason: string) => Promise<void>;
}

/** Reason + destructive button used to end (platform) or revoke (client) a mandate. */
export function CloseMandateForm({ reasonLabel, submitLabel, onSubmit }: CloseMandateFormProps) {
  return (
    <Formik<CloseValues>
      initialValues={{ reason: '' }}
      validationSchema={closeSchema}
      onSubmit={async (v, helpers) => {
        helpers.setStatus(undefined);
        try {
          await onSubmit(v.reason.trim());
          helpers.resetForm();
        } catch (err) {
          applySubmitError(err, helpers);
        }
      }}
    >
      {(formik) => (
        <Form noValidate>
          <Stack spacing={2}>
            {statusMessage(formik.status) !== null && (
              <Alert severity="error">{statusMessage(formik.status)}</Alert>
            )}
            <FormikTextField name="reason" label={reasonLabel} required multiline minRows={2} />
            <div>
              <Button type="submit" variant="contained" color="error" loading={formik.isSubmitting}>
                {submitLabel}
              </Button>
            </div>
          </Stack>
        </Form>
      )}
    </Formik>
  );
}
