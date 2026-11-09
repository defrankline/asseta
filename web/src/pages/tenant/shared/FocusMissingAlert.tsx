import { Alert } from '@mui/material';

/** Shown when a link opened one record that cannot be loaded. */
export function FocusMissingAlert({ missing }: { missing: boolean }) {
  return missing ? (
    <Alert severity="info" className="mb-3">
      That record could not be opened. It may not exist, or you may not have access to it.
    </Alert>
  ) : null;
}
