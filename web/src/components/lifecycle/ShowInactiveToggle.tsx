import { FormControlLabel, Switch } from '@mui/material';

interface ShowInactiveToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Domain wording, e.g. `Show retired` or `Show closed` (default `Show inactive`). */
  label?: string;
}

/**
 * List toolbar switch that includes deactivated records. Pair with `inactiveFilter(checked)`
 * (src/api/lifecycle.ts) so the flag is sent to the server, never filtered in the browser.
 */
export function ShowInactiveToggle({
  checked,
  onChange,
  label = 'Show inactive',
}: ShowInactiveToggleProps) {
  return (
    <FormControlLabel
      control={
        <Switch
          checked={checked}
          onChange={(e) => {
            onChange(e.target.checked);
          }}
        />
      }
      label={label}
    />
  );
}
