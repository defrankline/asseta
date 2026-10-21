import { Alert, AlertTitle, Button, Typography } from '@mui/material';
import { ApiError } from '../../api/ApiError';

interface ErrorStateProps {
  error: unknown;
  title?: string;
  onRetry?: () => void;
}

/** Consistent error presentation including the server correlation id for support. */
export function ErrorState({ error, title = 'Something went wrong', onRetry }: ErrorStateProps) {
  const message = error instanceof Error ? error.message : 'Unexpected error.';
  const correlationId = error instanceof ApiError ? error.correlationId : null;
  return (
    <Alert
      severity="error"
      action={
        onRetry !== undefined ? (
          <Button color="inherit" size="small" onClick={onRetry}>
            Retry
          </Button>
        ) : undefined
      }
    >
      <AlertTitle>{title}</AlertTitle>
      {message}
      {correlationId !== null && (
        <Typography variant="caption" component="div" className="mt-1 font-mono">
          Reference: {correlationId}
        </Typography>
      )}
    </Alert>
  );
}
