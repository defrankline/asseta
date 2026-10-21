import { Alert, Button, Typography } from '@mui/material';
import { useState, type ReactNode } from 'react';
import { object, string, type ObjectSchema } from 'yup';
import { isStaleVersion, REASON_MAX, REASON_MIN, withErrorCode } from '../../api/lifecycle';
import { useIdempotencyKey } from '../../hooks/useIdempotencyKey';
import { FormDialog } from '../forms/FormDialog';
import { FormikTextField } from '../forms/FormikTextField';

/** `none`: the endpoint takes no reason (the dialog is a plain confirmation). */
export type ReasonMode = 'required' | 'optional' | 'none';

export const STALE_RECORD_MESSAGE =
  'This record was changed by someone else since you opened it. Reload to see the latest version, then try again.';

interface ReasonValues {
  reason: string;
}

const SCHEMAS: Readonly<Record<ReasonMode, ObjectSchema<ReasonValues>>> = {
  required: object({
    reason: string()
      .trim()
      .required('A reason is required')
      .min(REASON_MIN, `At least ${String(REASON_MIN)} characters`)
      .max(REASON_MAX, `At most ${String(REASON_MAX)} characters`),
  }),
  optional: object({
    reason: string()
      .trim()
      .ensure()
      .test(
        'min',
        `At least ${String(REASON_MIN)} characters`,
        (v) => v === '' || v.length >= REASON_MIN,
      )
      .max(REASON_MAX, `At most ${String(REASON_MAX)} characters`),
  }),
  none: object({ reason: string().ensure() }),
};

export interface LifecycleActionDialogProps<T> {
  title: string;
  /** What happens, in plain language (shown above the reason). */
  description: ReactNode;
  confirmLabel: string;
  destructive?: boolean;
  reason?: ReasonMode;
  reasonLabel?: string;
  reasonHelp?: string;
  /**
   * Performs the action with the trimmed reason (empty when not collected) and an idempotency key
   * for this payload. Throw (ideally an ApiError) to keep the dialog open with the error.
   */
  onConfirm: (reason: string, idempotencyKey: string) => Promise<T>;
  /** Called with the result after a successful action; the dialog then closes. */
  onDone: (result: T) => void;
  onClose: () => void;
  /** Offered as "Reload" when the server answers STALE_VERSION (closes the dialog). */
  onReload?: () => void;
  /** Stable error code → what the user can do about it (shown with the server message). */
  errorHints?: Readonly<Record<string, string>>;
}

const NO_HINTS: Readonly<Record<string, string>> = {};

/**
 * Confirm one lifecycle action (deactivate, reactivate, retire, cancel, close, …) with a reason.
 * Server business errors stay in the dialog with their code; STALE_VERSION offers a reload.
 * Mount only while open.
 */
export function LifecycleActionDialog<T>({
  title,
  description,
  confirmLabel,
  destructive = false,
  reason = 'required',
  reasonLabel = 'Reason',
  reasonHelp,
  onConfirm,
  onDone,
  onClose,
  onReload,
  errorHints = NO_HINTS,
}: LifecycleActionDialogProps<T>) {
  const keyFor = useIdempotencyKey();
  const [stale, setStale] = useState(false);
  return (
    <FormDialog<ReasonValues>
      open
      title={title}
      initialValues={{ reason: '' }}
      validationSchema={SCHEMAS[reason]}
      submitLabel={confirmLabel}
      onClose={onClose}
      onSubmit={async (v) => {
        const text = reason === 'none' ? '' : v.reason.trim();
        try {
          const result = await onConfirm(text, keyFor({ reason: text }));
          onDone(result);
        } catch (err) {
          if (isStaleVersion(err)) setStale(true);
          throw withErrorCode(err, errorHints);
        }
      }}
    >
      {stale && (
        <Alert
          severity="warning"
          action={
            onReload !== undefined ? (
              <Button
                color="inherit"
                size="small"
                onClick={() => {
                  onReload();
                  onClose();
                }}
              >
                Reload
              </Button>
            ) : undefined
          }
        >
          {STALE_RECORD_MESSAGE}
        </Alert>
      )}
      <Typography variant="body2" component="div">
        {description}
      </Typography>
      {reason !== 'none' && (
        <FormikTextField
          name="reason"
          label={reason === 'required' ? reasonLabel : `${reasonLabel} (optional)`}
          required={reason === 'required'}
          multiline
          minRows={2}
          {...(reasonHelp !== undefined ? { helperText: reasonHelp } : {})}
        />
      )}
      {destructive && (
        <Typography variant="caption" color="text.secondary">
          Nothing is deleted: the record and its history are kept for audit.
        </Typography>
      )}
    </FormDialog>
  );
}
