import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  type DialogProps,
} from '@mui/material';
import { Form, Formik, type FormikHelpers, type FormikProps, type FormikValues } from 'formik';
import type { ReactNode } from 'react';
import type { ObjectSchema } from 'yup';
import { applySubmitError, statusMessage } from './submitHandling';

export interface FormDialogProps<V extends FormikValues> {
  open: boolean;
  title: string;
  initialValues: V;
  validationSchema: ObjectSchema<V>;
  /** Throw (ideally an ApiError) to keep the dialog open and show the error. */
  onSubmit: (values: V, helpers: FormikHelpers<V>) => Promise<void>;
  onClose: () => void;
  children: ReactNode | ((formik: FormikProps<V>) => ReactNode);
  submitLabel?: string;
  maxWidth?: DialogProps['maxWidth'];
  /** Close automatically after a successful submit (default true). */
  closeOnSuccess?: boolean;
}

/** MUI Dialog hosting a Formik form validated with Yup. Use StepperFormDialog for >3 fields. */
export function FormDialog<V extends FormikValues>({
  open,
  title,
  initialValues,
  validationSchema,
  onSubmit,
  onClose,
  children,
  submitLabel = 'Save',
  maxWidth = 'sm',
  closeOnSuccess = true,
}: FormDialogProps<V>) {
  const handleSubmit = async (values: V, helpers: FormikHelpers<V>) => {
    helpers.setStatus(undefined);
    try {
      await onSubmit(values, helpers);
      if (closeOnSuccess) onClose();
    } catch (err) {
      applySubmitError(err, helpers);
    }
  };

  return (
    <Formik
      initialValues={initialValues}
      validationSchema={validationSchema}
      onSubmit={handleSubmit}
      enableReinitialize
    >
      {(formik) => (
        <Dialog
          open={open}
          onClose={formik.isSubmitting ? undefined : onClose}
          fullWidth
          maxWidth={maxWidth}
          aria-labelledby="form-dialog-title"
        >
          <Form noValidate>
            <DialogTitle id="form-dialog-title">{title}</DialogTitle>
            <DialogContent dividers>
              <Stack spacing={2}>
                {statusMessage(formik.status) !== null && (
                  <Alert severity="error">{statusMessage(formik.status)}</Alert>
                )}
                {typeof children === 'function' ? children(formik) : children}
              </Stack>
            </DialogContent>
            <DialogActions>
              <Button onClick={onClose} disabled={formik.isSubmitting}>
                Cancel
              </Button>
              <Button type="submit" variant="contained" loading={formik.isSubmitting}>
                {submitLabel}
              </Button>
            </DialogActions>
          </Form>
        </Dialog>
      )}
    </Formik>
  );
}
