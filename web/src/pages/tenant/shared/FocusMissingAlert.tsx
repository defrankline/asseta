import { Alert } from '@mui/material';

/** Shown when a link opened one record that is not among the entries this list could search. */
export function FocusMissingAlert({ missing }: { missing: boolean }) {
  return missing ? (
    <Alert severity="info" className="mb-3">
      That record is not among the most recent entries. Use the filters to find it.
    </Alert>
  ) : null;
}
