import { Alert } from '@mui/material';
import { useState } from 'react';
import { mixed, object } from 'yup';
import { subscriptionService } from '../../../api/services/subscriptionService';
import type {
  EntitlementDto,
  SubscriptionDto,
  SubscriptionStatus,
  TransitionIn,
} from '../../../api/types';
import { FormDialog } from '../../../components/forms/FormDialog';
import { FormikDateField } from '../../../components/forms/FormikDateField';
import { FormikSelectField } from '../../../components/forms/FormikSelectField';
import { FormikTextField } from '../../../components/forms/FormikTextField';
import { useIdempotencyKey } from '../../../hooks/useIdempotencyKey';
import { todayIsoDate } from '../../../utils/dates';
import { isoDateField, reasonField } from '../shared/validators';
import { allowedLifecycleActions } from './lifecycle';

interface TransitionValues {
  to_status: SubscriptionStatus;
  effective_date: string;
  reason: string;
}

interface TransitionDialogProps {
  subscription: SubscriptionDto;
  onClose: () => void;
  onTransitioned: (result: EntitlementDto) => void;
}

/** Change the subscription lifecycle status to one of the allowed targets, with a reason. */
export function TransitionDialog({ subscription, onClose, onTransitioned }: TransitionDialogProps) {
  const keyFor = useIdempotencyKey();
  const actions = allowedLifecycleActions(subscription.status);
  const today = todayIsoDate();
  const [schema] = useState(() =>
    object({
      to_status: mixed<SubscriptionStatus>()
        .oneOf(actions.map((a) => a.to))
        .required('Choose a target status'),
      effective_date: isoDateField('Effective date').test(
        'not-backdated',
        'Effective date cannot be in the past',
        (v) => v >= today,
      ),
      reason: reasonField(),
    }),
  );
  const first = actions[0];
  if (first === undefined) return null;
  const initialValues: TransitionValues = {
    to_status: first.to,
    effective_date: today,
    reason: '',
  };

  return (
    <FormDialog<TransitionValues>
      open
      title="Change subscription status"
      initialValues={initialValues}
      validationSchema={schema}
      submitLabel="Apply"
      onClose={onClose}
      onSubmit={async (v) => {
        const body: TransitionIn = {
          to_status: v.to_status,
          effective_date: v.effective_date,
          reason: v.reason.trim(),
        };
        onTransitioned(await subscriptionService.transition(subscription.id, body, keyFor(body)));
      }}
    >
      {(formik) => (
        <>
          <FormikSelectField
            name="to_status"
            label="Action"
            options={actions.map((a) => ({ value: a.to, label: a.label }))}
            required
          />
          {formik.values.to_status === 'CANCELLED' && (
            <Alert severity="warning">
              A future effective date schedules the cancellation: the subscription stays billable
              until that date. Data is never deleted.
            </Alert>
          )}
          {formik.values.to_status === 'ACTIVE' && subscription.status === 'PENDING_ACTIVATION' && (
            <Alert severity="info">
              Activation requires a verified company record and a negotiated rate.
            </Alert>
          )}
          <FormikDateField name="effective_date" label="Effective date" required minDate={today} />
          <FormikTextField name="reason" label="Reason" required multiline minRows={2} />
        </>
      )}
    </FormDialog>
  );
}
