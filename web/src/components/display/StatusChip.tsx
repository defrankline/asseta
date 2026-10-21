import { Chip } from '@mui/material';
import { humanize } from '../../utils/text';

export type StatusTone = 'success' | 'warning' | 'error' | 'info' | 'default';

interface StatusChipProps {
  /** Raw status code, e.g. `PAST_DUE`. */
  status: string;
  /** Optional mapping from status code to tone; unknown codes render neutral. */
  tones?: Readonly<Record<string, StatusTone>>;
  /** Optional display label; defaults to the humanised status code. */
  label?: string;
}

/** Status shown as text plus a tone (never colour alone). */
export function StatusChip({ status, tones, label }: StatusChipProps) {
  const tone = tones?.[status] ?? 'default';
  return (
    <Chip
      size="small"
      label={label ?? humanize(status)}
      color={tone}
      variant={tone === 'default' ? 'outlined' : 'filled'}
    />
  );
}
