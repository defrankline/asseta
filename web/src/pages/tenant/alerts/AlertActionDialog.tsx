import { Typography } from '@mui/material';
import { useState } from 'react';
import { object, string } from 'yup';
import { alertService } from '../../../api/services/alertService';
import type { AlertActionIn, AlertDto } from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';

export type AlertAction = AlertActionIn['action'];

interface AlertActionDialogProps {
  alert: AlertDto;
  action: AlertAction;
  onClose: () => void;
  onDone: (alert: AlertDto) => void;
}

interface Values {
  note: string;
}

const resolveSchema = object({
  note: string()
    .trim()
    .required('A resolution note is required')
    .max(1000, 'At most 1000 characters'),
});
const ackSchema = object({
  note: string().trim().max(1000, 'At most 1000 characters').default(''),
});

/** Acknowledge (optional note) or resolve (note required) a tracking alert. Mount while open. */
export function AlertActionDialog({ alert, action, onClose, onDone }: AlertActionDialogProps) {
  const keyFor = useIdempotencyKey();
  const [initialValues] = useState<Values>({ note: '' });
  const resolving = action === 'RESOLVE';
  return (
    <FormDialog<Values>
      open
      title={resolving ? 'Resolve alert' : 'Acknowledge alert'}
      initialValues={initialValues}
      validationSchema={resolving ? resolveSchema : ackSchema}
      submitLabel={resolving ? 'Resolve' : 'Acknowledge'}
      onClose={onClose}
      onSubmit={async (values) => {
        const note = values.note.trim();
        const body: AlertActionIn = { action, note: note === '' ? null : note };
        onDone(await alertService.act(alert.id, body, keyFor(body)));
      }}
    >
      <Typography variant="body2">{alert.title}</Typography>
      <FormikTextField
        name="note"
        label={resolving ? 'Resolution note' : 'Note (optional)'}
        required={resolving}
        multiline
        minRows={3}
        helperText={
          resolving ? 'Explain what was found and done; kept with the alert for audit.' : undefined
        }
      />
    </FormDialog>
  );
}
